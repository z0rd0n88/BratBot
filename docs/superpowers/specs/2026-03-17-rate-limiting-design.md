# Rate Limiting Design for BratBot Discord Commands

**Date:** 2026-03-17
**Status:** Design Approved

## Overview

Implement per-user rate limiting for Discord bot commands using Redis. Users will be limited to 5 commands per 60-second window. When rate limited, they receive a bratty, in-character response.

**Scope:** Discord bot commands only (API rate limiting deferred to future work)

## Requirements

- **Limit:** 5 commands per user per 60 seconds
- **Scope:** Per-user (not per-guild or per-channel)
- **Backend:** Redis (hosted account on RunPod)
- **Response:** Bratty error message matching bot's personality
- **Graceful degradation:** If Redis is unavailable, allow commands (don't break the bot)

## Architecture

### High-Level Flow

1. User runs a command
2. `@rate_limit` decorator intercepts the call
3. Decorator checks Redis for request count in current 60s window
4. If count < 5: increment counter, execute command
5. If count >= 5: send bratty response, don't execute command
6. Redis key auto-expires after 60 seconds

### Redis Key Design

```
rate_limit:discord:<user_id>
Value: integer (request count)
TTL: 60 seconds
```

Example: `rate_limit:discord:123456789` → `3`

## Components

### 1. Rate Limit Decorator (`src/bratbot/rate_limit.py`)

**Purpose:** Wraps command handlers to enforce rate limiting before execution.

**Interface:**
```python
@rate_limit(max_calls=5, time_window=60)
@app_command.command(name="ask", description="Ask me something")
async def ask(interaction: discord.Interaction, question: str) -> None:
    # command logic
    pass
```

**Behavior:**
- Check Redis for current request count
- If allowed: increment counter, set TTL, execute command
- If blocked: send bratty response, don't execute
- If Redis error: log warning, allow command (graceful degradation)

### 2. Redis Client

**Location:** `src/bratbot/redis_client.py`

**Responsibilities:**
- Initialize async Redis connection from `REDIS_URL`
- Provide helper methods: `check_limit()`, `increment_counter()`, `reset_counter()`
- Handle connection errors gracefully

### 3. Bratty Responses

**Location:** `src/bratbot/responses.py` (or similar)

**Store:** List of rate-limit messages with personality
- Examples: "Slow down, you're annoying me", "Take a breath, I'm not going anywhere", "Five commands a minute? Really?"
- Randomly selected when user is rate limited

## Data Flow

```
User Command
    ↓
@rate_limit decorator
    ↓
Query Redis: GET rate_limit:discord:<user_id>
    ↓
    ├─ Key doesn't exist or count < 5
    │   ↓
    │   INCR + EXPIRE (60s)
    │   ↓
    │   Execute command
    │
    └─ count >= 5
        ↓
        Send bratty response
        ↓
        Return (command not executed)
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Redis unavailable | Log warning, allow command |
| Malformed key | Skip rate limiting, allow command |
| Decorator misuse (invalid params) | Raise clear error during bot startup |
| User at exactly 5 commands | Send bratty response, don't execute 6th command |

## Testing Strategy

### Unit Tests (pytest)
- Decorator logic with mocked Redis
- Bratty response selection
- Edge cases: first command, exactly 5th, 6th after reset

### Integration Tests
- Real Redis instance (Docker or test container)
- TTL behavior verification
- Concurrent commands from multiple users

### Test Cases
- User runs 1-4 commands → all execute
- User runs 5th command → executes
- User runs 6th command within 60s → blocked, gets bratty response
- User waits 60s, runs command → executes (key expired)
- Redis connection fails → commands still work

## Implementation Order

1. Create `redis_client.py` with async Redis connection
2. Create `rate_limit.py` with decorator
3. Add bratty response messages
4. Add decorator to bot commands
5. Write tests
6. Test on RunPod with real Redis account

## Environment Configuration

- `REDIS_URL` environment variable (format: `redis://[user:password@]host:port`)
- Set in RunPod Pod Runtime Settings → Environment
- Local dev: can use Docker Compose or test Redis instance

## Future Considerations

- API endpoint rate limiting (separate design)
- Per-guild limits (if needed)
- Different limits for different command types
- Rate limit reset/admin override commands
