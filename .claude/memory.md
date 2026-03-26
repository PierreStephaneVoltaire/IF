# Memory System

User facts store using LanceDB for semantic search with all-MiniLM-L6-v2 embeddings.

**Module:** `src/memory/user_facts.py`

## Fact Schema

```python
@dataclass
class UserFact:
    id: str                    # UUID
    context_id: str            # Scope: "openwebui_{chat_id}" or "discord_{channel_id}"
    username: str              # Operator identifier
    content: str               # The fact content
    category: FactCategory     # Classification category
    source: FactSource         # How this fact was captured
    confidence: float          # 0.0 to 1.0
    cache_key: str             # Where this fact was captured
    created_at: str            # ISO timestamp
    updated_at: str            # ISO timestamp
    superseded_by: str | None  # ID of replacement fact
    active: bool               # False if superseded
    metadata: dict             # Structured data storage
```

## Categories

### Operator Facts

| Category | Description | Example |
|----------|-------------|---------|
| `personal` | Name, location, profession, relationships | "Operator lives in Boston" |
| `preference` | Language/framework preferences, communication style | "Operator prefers TypeScript" |
| `opinion` | Strong stances on technologies, approaches | "Operator dislikes microservices" |
| `skill` | Self-reported or demonstrated understanding | "Operator is a senior DevOps engineer" |
| `life_event` | Job changes, moves, competitions, milestones | "Operator started new job at TechCorp" |
| `future_direction` | Goals, timelines, aspirations | "Operator planning to learn Rust" |
| `project_direction` | Current project plans and direction | "Operator migrating Express to Fastify" |
| `mental_state` | Noted shifts in mood, stress, outlook | "Operator showing increased stress" |
| `interest_area` | Topics they gravitate toward | "Operator frequently asks about AWS networking" |
| `conversation_summary` | Auto-generated summaries of discussions | "Discussed Kubernetes deployment strategies" |
| `topic_log` | Domains discussed and when | "Topic: containerization discussed 2026-03-01" |
| `model_assessment` | Agent's observations about the operator | "Operator shows knowledge gap in subnetting" |

### Agent Self-Knowledge

| Category | Description | Example |
|----------|-------------|---------|
| `agent_identity` | Agent's self-knowledge | "I am IF, an intelligent routing agent" |
| `agent_opinion` | Agent's formed positions | "Monoliths are correct default for teams < 20" |
| `agent_principle` | Operating principles learned | "Always verify arithmetic with calculator" |

### Capability Tracking

| Category | Description | Example |
|----------|-------------|---------|
| `capability_gap` | Things agent can't do | "Cannot send emails" |
| `tool_suggestion` | Derived from frequent gaps | "email_mcp_server" |

### Opinion Pairs

| Category | Description | Example |
|----------|-------------|---------|
| `opinion_pair` | User + agent positions on topics | Topic: "Microservices", User: "Always better", Agent: "Disagree" |

### Operator Growth

| Category | Description | Example |
|----------|-------------|---------|
| `misconception` | User misunderstandings corrected | "CIDR /24 = 512 addresses (corrected to 256)" |
| `session_reflection` | Post-session learnings | "What worked: step-by-step explanations" |

## Sources

| Source | Description |
|--------|-------------|
| `user_stated` | Explicitly stated by the operator |
| `model_observed` | Observed from operator behavior |
| `model_assessed` | Agent's assessment of operator capabilities |
| `conversation_derived` | Extracted from conversation context |

## Agent Tools

**Module:** `src/agent/tools/user_facts.py`

| Tool | Parameters | Description |
|------|-----------|-------------|
| `user_facts_search` | `query`, `category?`, `limit?` | Semantic search across stored facts |
| `user_facts_add` | `content`, `category`, `source?`, `confidence?` | Store a new fact |
| `user_facts_update` | `fact_id`, `new_content`, `reason` | Supersede an existing fact |
| `user_facts_list` | `category?`, `include_history?` | List all stored facts |
| `user_facts_remove` | `fact_id` | Hard delete (requires Directive 0-1 confirmation) |

## Auto-Retrieval

During system prompt assembly, relevant facts are automatically retrieved:

```python
async def get_operator_context(messages: list[dict], store: UserFactStore) -> str:
    facts = await store.search(last_user_msg, limit=5)
    assessments = await store.search(last_user_msg, category=FactCategory.MODEL_ASSESSMENT, limit=3)
    # Returns formatted "OPERATOR CONTEXT" block
```

## Conversation Summarization

**Module:** `src/memory/summarizer.py`

After each agent execution, a fire-and-forget task generates a conversation summary:

- Only summarizes substantive exchanges (>3 messages)
- Uses `SUGGESTION_MODEL` for cheap summarization
- Stores as `conversation_summary` fact
- Zero impact on response latency

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FACTS_BASE_PATH` | `./data/facts` | LanceDB storage path |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model name |

## How to Add a New Category

1. Add to `FactCategory` enum in `src/memory/user_facts.py`:

```python
class FactCategory(str, Enum):
    # ... existing ...
    NEW_CATEGORY = "new_category"
```

2. Add description in docstring or comments
3. Update any relevant filters in tools or reflection

## Gotchas

- Facts are scoped by `context_id` (channel/chat)
- Use `superseded_by` for updates, not deletion
- Hard delete only via `user_facts_remove` with confirmation
- Embeddings are computed at write time
