# Ambient Heartbeat & Operator Profiles — Implementation Plan

## Context

IF has an existing heartbeat system (`heartbeat/runner.py`) that monitors channel activity and initiates pondering conversations after an idle threshold (6h default, with cooldown and quiet hours). Currently it's a simple check-in — the agent reaches out with a pondering message using stored user facts.

Two expansions needed:

1. **Ambient fact retrieval** — the heartbeat should proactively gather information relevant to the operator: local weather, local news, industry news, market data, etc. This information gets injected into the heartbeat message or stored as context so the agent has something useful to say rather than just "checking in."

2. **Multi-user operator profiles** — right now IF is single-operator. When the agent encounters a new user (e.g., someone new messages in a Discord channel), it should provision them: create a profile in DynamoDB, give them their own facts/RAG database, and track their interests so the ambient system knows what to fetch for each person.

These are two related systems — the profiles tell the ambient system WHAT to fetch, and the ambient system populates context FOR each profiled user.

## Part 1: Ambient Fact Retrieval

### What the heartbeat should do on each cycle

Current: check idle → send pondering message using stored facts.

New: check idle → gather ambient context → enrich message with relevant info → send.

### Ambient context sources

These should be modular — each source is a small async function that fetches data and returns structured facts. The heartbeat runner calls all enabled sources, collects results, and injects them into the heartbeat message context.

| Source | What it fetches | How | Requires |
|--------|----------------|-----|----------|
| Weather | Current conditions + forecast for operator's location | Weather API (OpenWeatherMap, WeatherAPI, etc.) | Operator profile: location |
| Local news | Headlines for operator's city/region | News API, Google News RSS, or web search | Operator profile: location |
| Industry news | Headlines in operator's professional domains | News API filtered by topic, RSS feeds, or web search | Operator profile: industries/interests |
| Market data | Price movements for watched tickers | Existing Yahoo Finance / Alpha Vantage MCPs | Operator profile: watched tickers |
| Calendar | Upcoming events (if calendar integration exists) | Calendar API / MCP | Operator profile: calendar access |
| Health status | Training program status, upcoming sessions | Existing health DynamoDB tools | Operator profile: health module enabled |
| Financial status | Portfolio changes, goal progress | Existing finance DynamoDB tools | Operator profile: finance module enabled |

### Ambient source interface

```python
class AmbientSource(ABC):
    """Fetches contextual information for an operator."""
    
    @abstractmethod
    async def fetch(self, profile: OperatorProfile) -> list[AmbientFact]:
        """Fetch relevant facts for this operator. Return empty list if nothing relevant."""
        
    @abstractmethod
    def source_name(self) -> str:
        """Identifier for this source."""
        
    @abstractmethod
    def required_profile_fields(self) -> list[str]:
        """Which profile fields this source needs (e.g., ['location', 'industries'])."""
```

```python
@dataclass
class AmbientFact:
    source: str           # e.g., "weather", "industry_news"
    content: str          # human-readable fact
    relevance: float      # 0-1, how relevant to this operator
    timestamp: datetime
    ttl_hours: int        # how long this fact stays useful (weather=3, news=12, market=1)
    category: str         # maps to user fact categories if we want to store it
```

### Fact storage and TTL

Ambient facts are ephemeral — they're not the same as user facts (which are long-lived knowledge about the operator). Two approaches:

**Option A — Ephemeral only**: Ambient facts live in memory, attached to the heartbeat context. They're fetched fresh each cycle and discarded after use. Simple, no storage overhead.

**Option B — Two-tier facts DB**: 
- **Durable facts** — existing user facts in LanceDB (personal info, preferences, opinions, etc.)
- **Ambient facts** — short-lived contextual facts with TTL. Could be a separate LanceDB table or a DynamoDB table with TTL attributes. Queryable by the agent between heartbeats.

Option B is more useful because the agent can reference ambient facts during normal conversations too (e.g., "it's supposed to rain later" during a morning check-in, or "I saw X company had layoffs" when discussing career stuff). But Option A is simpler to start with.

**Recommendation**: Start with Option A (ephemeral, fetched per heartbeat cycle). Add Option B later if the agent needs ambient context outside of heartbeat messages. If going with Option B, DynamoDB with TTL attributes is the natural fit since you're already using it for everything else.

### Heartbeat message enrichment

The heartbeat runner collects all ambient facts, filters by relevance, and injects them into the pondering message context. The agent then naturally weaves relevant information into its check-in:

Instead of: "Hey, just checking in. How's the project going?"

More like: "Morning — looks like it's going to rain this afternoon so maybe good for an indoor session. I noticed [industry company] announced [relevant thing]. How's the refactoring going?"

The ambient facts get added to the system prompt for the heartbeat conversation, NOT hardcoded into the message. The agent decides what's worth mentioning.

### Configuration

```yaml
heartbeat:
  enabled: true
  idle_hours: 6.0
  cooldown_hours: 6.0
  quiet_hours_start: 23
  quiet_hours_end: 7
  ambient:
    enabled: true
    sources:
      - weather
      - local_news
      - industry_news
      - market_data
      - health_status
      - financial_status
    weather_api_key: ${WEATHER_API_KEY}
    news_api_key: ${NEWS_API_KEY}
```

## Part 2: Multi-User Operator Profiles

### Current state

IF is single-operator. User facts are scoped by `context_id` (each context gets its own LanceDB table), and facts have a `username` field. But there's no formal operator profile — the agent learns about the operator organically through conversation.

### What needs to change

When the agent receives a message from a new user (someone it hasn't seen before in that channel):

1. **Detect new user** — check if this `username` / `user_id` exists in the operator profiles table
2. **Provision profile** — create a DynamoDB entry with default fields
3. **Provision facts DB** — create a scoped LanceDB table (or DynamoDB partition) for this user's facts
4. **Greet and onboard** — the agent acknowledges the new user and explains what it can do. If they ask about domain-specific features (health, finance), inform them that a knowledge base can be provisioned for them.

### Operator profile schema (DynamoDB)

Table: `if-operator-profiles`

```python
@dataclass
class OperatorProfile:
    user_id: str              # primary key — platform user ID (e.g., Discord user ID)
    username: str             # display name
    platform: str             # discord, openwebui, api
    
    # Location (for weather, local news)
    location_city: str | None
    location_country: str | None
    timezone: str | None
    
    # Professional context (for industry news)
    industries: list[str]     # e.g., ["software", "ai", "fintech"]
    role: str | None          # e.g., "software engineer"
    
    # Market tracking (for financial ambient)
    watched_tickers: list[str]  # e.g., ["AAPL", "MSFT", "BTC-USD"]
    
    # Module access
    health_enabled: bool      # has a health knowledge base
    finance_enabled: bool     # has a finance knowledge base
    
    # Facts DB reference
    facts_context_id: str     # LanceDB context ID for this user's facts
    
    # Metadata
    first_seen: datetime
    last_active: datetime
    message_count: int
    
    # TTL (optional — for inactive users)
    ttl: int | None           # DynamoDB TTL epoch timestamp
```

### Initial operator bootstrap

For the primary operator (you), a YAML config loads the initial profile on startup:

```yaml
# config/operator.yaml
primary_operator:
  user_id: "discord_123456789"
  username: "operator"
  platform: discord
  location_city: "New York"
  location_country: "US"
  timezone: "America/New_York"
  industries: ["software", "ai", "cloud"]
  role: "software engineer"
  watched_tickers: ["AAPL", "MSFT", "AMZN"]
  health_enabled: true
  finance_enabled: true
```

On startup: load this YAML, check if the profile exists in DynamoDB, create/update if needed. This replaces the current implicit single-operator assumption.

### New user provisioning flow

```
New message arrives
  → Dispatcher extracts user_id and username from platform message
  → Check operator profiles table for user_id
  → If not found:
      1. Create OperatorProfile with defaults (no location, no industries, modules disabled)
      2. Create a facts context (LanceDB table scoped to this user)
      3. Store a system note that this is a new user
      4. Agent's first response includes a natural introduction
      5. Over time, agent learns profile fields through conversation and updates the profile
  → If found:
      1. Update last_active timestamp
      2. Load their profile for context injection
      3. Continue normally
```

### Profile learning

The agent should update operator profiles organically. When a user mentions they're in Chicago, the agent updates `location_city`. When they talk about their job in finance, `industries` gets updated. This can work through:

- A new system tool: `update_operator_profile(user_id, field, value)` — available to the main agent
- Directives that encourage the agent to notice and store profile-relevant information
- The existing user facts system captures this too, but the profile is the structured, queryable version

### Domain module provisioning

When a new user asks about health tracking, the agent:
1. Explains the health module
2. Offers to provision it: "I can set up a training knowledge base for you. Want me to do that?"
3. On confirmation: creates the DynamoDB partition for their health data, sets `health_enabled: true` on their profile
4. Same pattern for finance, diary, etc.

This means the DynamoDB health/finance tools need to be user-scoped — read/write operations key on the operator's `user_id`, not a global table. This ties into the tool registry work: health tools receive the active user's profile as context.

### Ambient system integration

The heartbeat runner now iterates over active operator profiles (or at minimum, profiles with recent activity) and runs ambient fact collection per-user:

```
Heartbeat cycle:
  → Get all operator profiles with last_active within threshold
  → For each profile:
      → Run enabled ambient sources with this profile's data
      → Collect ambient facts
      → If this user has an active channel, inject facts into heartbeat message
      → Send personalized heartbeat to their channel
```

This means heartbeats become per-user, not global. The agent checks in with different users in different channels with context specific to each person.

### TTL and cleanup

Inactive users accumulate. Options:
- **DynamoDB TTL**: set a TTL on profiles that haven't been active in N days (configurable, e.g., 90 days). DynamoDB auto-deletes expired items.
- **Facts cleanup**: when a profile expires, its LanceDB table can be cleaned up by a maintenance task
- **Or don't clean up**: storage is cheap, and a returning user shouldn't lose their context. Maybe just stop running ambient fetches for inactive users but keep the data.

## Open Questions (for planning, not implementation)

1. **Ambient fact relevance scoring** — how does the agent decide which ambient facts are worth mentioning in a heartbeat? By relevance score? By category? Let the LLM decide?

2. **Rate limiting ambient sources** — weather APIs have rate limits, news APIs have quotas. How many operators can we fetch for per cycle before hitting limits? May need a staggered schedule.

3. **Privacy boundaries between users** — in a shared Discord channel, multiple users may be present. The agent needs to know whose context to use. Does it use the profile of whoever sent the last message? The channel owner? This affects how heartbeats work in shared spaces.

4. **Ambient facts during normal conversation** — should the agent have access to ambient facts outside of heartbeat cycles? If a user asks "what's the weather?" should the agent already know from the last ambient fetch, or should it use a tool?

5. **Profile data sensitivity** — operator profiles contain location, financial tickers, industry info. This is personal data. Needs consideration for multi-user scenarios where users might not want their profile visible to others in shared channels.

## Implementation Steps

### Ambient heartbeat (implement first)
1. Read `heartbeat/runner.py` and `heartbeat/activity.py` to understand current heartbeat flow
2. Design the `AmbientSource` interface and `AmbientFact` dataclass
3. Implement weather source (pick a free weather API)
4. Implement news source (RSS or news API)
5. Implement market data source (wrap existing Yahoo Finance MCP)
6. Implement health/finance status sources (wrap existing DynamoDB reads)
7. Update heartbeat runner to call ambient sources and inject facts into heartbeat context
8. Add ambient configuration to config
9. Test with the primary operator profile

### Operator profiles (implement second)
10. Design DynamoDB table schema for `if-operator-profiles`
11. Create `OperatorProfile` dataclass and DynamoDB CRUD
12. Implement startup bootstrap from `operator.yaml`
13. Implement new user detection in the dispatcher
14. Implement provisioning flow (profile creation, facts DB creation)
15. Create `update_operator_profile` system tool for the main agent
16. Add directives encouraging the agent to learn and update profile fields
17. Scope health/finance tools to user_id from the active operator profile
18. Update heartbeat to iterate over active profiles
19. Test multi-user flow with a second Discord user
