# Heartbeat System

Proactive operator engagement by monitoring channel activity and initiating pondering conversations after idle periods.

**Modules:**
- `src/heartbeat/activity.py` — Activity tracking
- `src/heartbeat/runner.py` — Background runner

## How It Works

1. **Activity Tracking**: Every message (inbound/outbound) updates `last_message_at` for the channel
2. **Idle Detection**: Every 60 seconds, check for channels idle beyond `HEARTBEAT_IDLE_HOURS`
3. **Cooldown**: Skip channels that received a heartbeat within `HEARTBEAT_COOLDOWN_HOURS`
4. **Quiet Hours**: Skip during configured quiet hours (default: 23:00-07:00 UTC)
5. **Initiation**: Pin channel to pondering, generate contextual opening, deliver message

## Activity Log Schema

```sql
CREATE TABLE activity_log (
    cache_key TEXT PRIMARY KEY,       -- channel_id or chat_id
    webhook_id TEXT,                  -- nullable (HTTP chats have no webhook)
    last_message_at TEXT NOT NULL,    -- ISO timestamp
    last_heartbeat_at TEXT            -- ISO timestamp
);
```

## Opening Message Generation

When initiating a heartbeat, the system:

1. Pulls relevant user facts (`future_direction`, `project_direction`, general)
2. Builds context block from stored facts
3. Calls LLM to generate personalized opening
4. Falls back to cold open if no facts exist:

```
"Statement: Idle period detected. Initiating baseline calibration. Query: What are you currently working on?"
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `HEARTBEAT_ENABLED` | `true` | Enable/disable heartbeat system |
| `HEARTBEAT_IDLE_HOURS` | `6.0` | Hours of inactivity before heartbeat |
| `HEARTBEAT_COOLDOWN_HOURS` | `6.0` | Hours between heartbeats on same channel |
| `HEARTBEAT_QUIET_HOURS` | `23:00-07:00` | UTC time range to skip heartbeats |

## Structured Logging

```
[Heartbeat] Tick: 3 active webhooks, 1 idle, 0 on cooldown
[Heartbeat] Pondering initiated on "Discord #dev-chat" (channel_id=123456)
[Heartbeat] Skipped channel_id=789: on cooldown (2.3h since last)
[Cache] Pin set: abc123 → pondering
```

## How to Modify Behavior

### Change idle threshold

1. Set `HEARTBEAT_IDLE_HOURS` environment variable
2. Or edit default in `src/config.py`

### Add custom opening logic

1. Edit `src/heartbeat/runner.py`
2. Modify `generate_heartbeat_opening()` function

### Skip certain channels

1. Add channel filter in `src/heartbeat/runner.py`
2. Check `cache_key` or `webhook_id` before initiating

## Integration with Pondering

Heartbeat activates the pondering preset:

1. Channel is pinned to `pondering` preset
2. Pin never auto-releases (pondering behavior)
3. Only `/end_convo` or `/{other_preset}` releases

## Gotchas

- Quiet hours are in UTC
- Cooldown prevents spam on active channels
- Heartbeat requires active webhooks
- Falls back to cold open if no stored facts
- Uses separate thread for background tick
