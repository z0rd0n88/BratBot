# BratBot V2 Engagement Features -- Design Spec

## Context

BratBot has under 100 Discord users. Before building monetization infrastructure, we need engagement features that make users stick and invite friends. This spec covers three features built sequentially: new personalities, conversation memory, and leaderboards/achievements.

**Goal:** Grow user base to 500+ active users, at which point monetization (see `docs/monetization-strategies.md`) becomes viable.

---

## Phase 1: New Personalities

### What

Add 3 new AI personalities: Mommy, Tsundere, Drill Sergeant. Each follows the established pattern: prompt file + model API endpoint + Discord command + SMS route.

### Prerequisite Refactor

Extract a shared helper in `model/app.py` to eliminate duplication between personality endpoints.

**Current state:** The `bratchat()` and `camichat()` endpoint functions are nearly identical -- both build an Ollama payload, send it, handle errors, and return. Adding 3 more copies is untenable.

**Refactor:**
```python
async def _generate_response(
    system_prompt: str,
    user_message: str,
    request_id: str,
    history: list[dict] | None = None,  # prepared for Phase 2
) -> str:
    """Shared Ollama inference logic for all personalities."""
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": OLLAMA_TEMPERATURE,
            "num_predict": OLLAMA_NUM_PREDICT,
            "num_ctx": OLLAMA_NUM_CTX,
        },
    }
    # POST to Ollama /api/chat, handle errors, return reply text
```

Each endpoint becomes ~5 lines: validate request, get system prompt, call helper, return response. The `history` parameter is included now but unused until Phase 2.

### New Personality Definitions

| Personality | Command | Endpoint | Prompt File | SMS Prefix | Request Model |
|---|---|---|---|---|---|
| Mommy | `/mommychat` | `POST /mommychat` | `model/prompts/mommy.txt` | `mommy:` | `message` only (like CamiChatRequest) |
| Tsundere | `/tsunderechat` | `POST /tsunderechat` | `model/prompts/tsundere.txt` | `tsundere:` | `message` only (like CamiChatRequest) |
| Drill Sergeant | `/drillchat` | `POST /drillchat` | `model/prompts/drill_sergeant.txt` | `drill:` | `message` only (like CamiChatRequest) |

All new personalities use simple `message`-only request models (no `brat_level` parameter). Only BratBot has adjustable sass levels.

### Files to Create

- `model/prompts/mommy.txt` -- Nurturing but firm personality prompt
- `model/prompts/tsundere.txt` -- Classic tsundere personality prompt
- `model/prompts/drill_sergeant.txt` -- Aggressive motivational personality prompt
- `src/bratbot/commands/mommy.py` -- Discord cog (auto-discovered)
- `src/bratbot/commands/tsundere.py` -- Discord cog (auto-discovered)
- `src/bratbot/commands/drill.py` -- Discord cog (auto-discovered)

### Files to Modify

- `model/app.py` -- Refactor shared helper + add 3 new endpoints + request models
- `src/bratbot/services/llm_client.py` -- Add `mommy_chat()`, `tsundere_chat()`, `drill_chat()` methods
- `src/bratbot/commands/bratchat.py` -- No changes needed (existing pattern unchanged by refactor)
- `sms/app.py` -- Update `_parse_route()` to support new prefixes. **Note:** SMS prefix matching uses `lower.startswith(prefix)` with a colon/space delimiter check -- existing code already requires the delimiter, so "drilled a hole" won't falsely match "drill:".

### Design Decision: Individual Commands vs. Personality Picker

**Choice: Keep individual commands for Discord/SMS, but consider a parameterized model API endpoint.**

Discord layer: Individual commands (`/mommychat`, `/tsunderechat`, etc.) for discoverability and per-personality descriptions. SMS layer: Individual prefixes for consistency.

Model API layer: While individual endpoints are fine for 5 personalities, a future refactor to `POST /chat/{personality}` with a personality registry (dict mapping name to prompt path) would make adding personalities zero-code at the API layer. **Not doing this now** -- the shared `_generate_response()` helper already eliminates the duplication that matters. Revisit if personality count exceeds 8.

### Tests

- `test_model_api.py` -- New endpoints: request validation, error responses
- `test_llm_client.py` -- New client methods: request/response format, timeout handling
- `test_sms_gateway.py` -- New prefix routing: "mommy:", "tsundere:", "drill:" parse correctly

---

## Phase 2: Conversation Memory + Basic Stats

### Conversation Memory

#### What

Bot remembers conversation context within a session. Currently every message is stateless (system prompt + single user message). With memory, the Ollama payload includes recent conversation history.

#### Service: `src/bratbot/services/conversation_memory.py`

```python
class ConversationMemory:
    def __init__(self, redis: Redis, window_size: int = 10, ttl_seconds: int = 1800):
        ...

    async def get_history(self, personality: str, user_id: int, scope: str) -> list[dict]:
        """Returns [{role: "user", content: "..."}, {role: "assistant", content: "..."}, ...]"""

    async def add_turn(self, personality: str, user_id: int, scope: str,
                       user_message: str, assistant_reply: str) -> None:
        """Appends a user+assistant exchange and trims to window_size."""

    async def clear(self, personality: str, user_id: int, scope: str) -> None:
        """Clears conversation history for a specific context."""
```

#### Redis Storage

- **Key format:** `conv:{personality}:{scope}:{user_id}`
  - Discord DMs: scope = `dm`
  - Discord guild channels: scope = `channel:{channel_id}`
  - SMS: scope = `sms`
  - @mention handler: scope = `channel:{channel_id}`, personality = `brat` (mentions always use brat personality)
- **Data structure:** Redis list. Each element is a JSON-serialized `{role, content}` dict.
- **Operations per turn:**
  1. `RPUSH` user message and assistant reply (2 elements)
  2. `LTRIM -N -1` where N = `window_size * 2` (keeps most recent N elements from the right)
  3. `EXPIRE` to reset TTL (default 30 minutes)
- **Graceful degradation:** If Redis is down, return empty history (stateless fallback).

**Design decision: per-user-per-channel memory (not shared per-channel).** Each user gets their own conversation thread with each personality in each channel. This prevents user A's context from bleeding into user B's replies. A shared channel memory would mean the bot's response to user B might reference something user A said, which is confusing and could leak context users didn't intend to share.

#### Model API Changes

Add optional `history` field to all chat request models:

```python
class BratChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    brat_level: int = Field(default=3, ge=1, le=3)
    history: list[dict] | None = None
```

Backwards-compatible -- callers that omit `history` get current stateless behavior. The `_generate_response()` helper (from Phase 1 refactor) already handles this.

**Security note:** The `history` field accepts arbitrary `{role, content}` dicts. The model API must validate that `role` is only `"user"` or `"assistant"` (never `"system"`) to prevent prompt injection via crafted history. Add validation in `_generate_response()`:
```python
if history:
    for entry in history:
        if entry.get("role") not in ("user", "assistant"):
            raise HTTPException(400, "Invalid role in history")
    messages.extend(history)
```

#### Context Window Budget

- System prompt: ~500-1000 tokens
- 10-turn conversation history: ~2000-6000 tokens
- Current user message: ~100-500 tokens
- **Total: ~2600-7500 tokens** out of 32,768 (`OLLAMA_NUM_CTX`)
- Fits comfortably. Log a warning if estimated tokens exceed 80% of context window.

#### LLM Client Changes

Add optional `history` parameter to all chat methods in `llm_client.py`:

```python
async def chat(self, message: str, brat_level: int | None = None,
               history: list[dict] | None = None) -> dict:
```

Include `history` in the JSON payload only if not None.

#### Cog Handler Changes -- CRITICAL: History Must Be Fetched Inside the Queued Coroutine

Each personality cog defines a nested `_call_llm()` coroutine that is passed to `request_queue.enqueue()`. The request queue serializes execution per-channel. **Both history fetch and history store must happen inside `_call_llm()`**, not outside it.

**Why:** If two users in the same channel fire commands near-simultaneously, and history is fetched *before* `enqueue()`, both users read the same history. The queue then serializes the LLM calls, but user B's history is already stale (doesn't include user A's just-completed exchange). By fetching inside the queued coroutine, the queue ensures sequential access.

Correct flow inside `_call_llm()`:
1. Fetch history from `ConversationMemory`
2. Call `LLMClient` with history
3. Store the turn in `ConversationMemory`
4. Record stats in `StatsTracker`
5. Return the reply

`ConversationMemory` instance initialized in `BratBot.setup_hook()` and stored as `self.conversation_memory` (same pattern as `self.rate_limiter`, `self.request_queue`).

**Cleanup:** Add `conversation_memory` and `stats_tracker` to `BratBot.close()` cleanup alongside existing `llm_client` and Redis cleanup.

#### SMS Memory

The SMS gateway (`sms/app.py`) is a separate FastAPI process, not a Python package. Since `sms/` and `src/bratbot/` cannot import from each other:

**Decision: Duplicate `ConversationMemory` as `sms/conversation_memory.py`.** The class is small (~50 lines of Redis list operations). Duplication is acceptable here because:
- The alternative (shared package) would require restructuring the project
- The class is simple and unlikely to diverge
- Both copies use the same Redis instance (same `REDIS_URL`), so conversation data is shared

**Cross-platform identity note:** Discord identifies users by `user_id` (int) and SMS by phone number (string). These never collide in Redis keys, so a user interacting via both channels will have separate conversation histories and separate stats. This is acceptable -- merging identities would require a user account system, which is out of scope.

#### `/clearhistory` Command

New cog `src/bratbot/commands/clearhistory.py`:
- Clears conversation memory for the invoking user in the current context
- Accepts optional `personality` parameter (default: clear all personalities for current scope)
- In-character response: "Fine, I'll pretend I don't know you. Again."

#### Config Settings

In `src/bratbot/config/settings.py`:
- `memory_window_size: int = 10`
- `memory_ttl_seconds: int = 1800`
- `enable_conversation_memory: bool = True` (feature flag for runtime disable)

In `sms/settings.py`:
- Same settings

### Basic Stats Tracking

#### Service: `src/bratbot/services/stats_tracker.py`

```python
@dataclass
class UserStats:
    total_messages: int
    personalities_used: set[str]
    first_seen: str  # ISO timestamp

class StatsTracker:
    def __init__(self, redis: Redis):
        ...

    async def record_interaction(self, user_id: int, personality: str) -> None:
        """Atomically increment message counts using Redis pipeline."""

    async def get_user_stats(self, user_id: int) -> UserStats:
        """Returns typed stats object."""
```

#### Redis Keys

- `stats:total_messages` -- sorted set (member=user_id, score=count) for leaderboard
- `stats:personality:{name}` -- sorted set (member=user_id, score=count) per personality
- `stats:user:{user_id}:first_seen` -- string, ISO timestamp

**Removed `stats:user:{user_id}:personalities` set.** The set of personalities a user has tried can be derived by checking `ZSCORE` on each `stats:personality:{name}` sorted set. This avoids maintaining a redundant data structure and eliminates inconsistency risk. For achievement checks, pipeline the `ZSCORE` calls (5 round-trips -> 1 pipeline).

#### `/stats` Command

New cog `src/bratbot/commands/stats.py`:
- Shows invoking user's stats: total messages, personalities used, member since
- Discord embed format
- In-character framing: "Ugh, you've wasted my time 47 times now..."

#### Instrumentation

`record_interaction()` called inside `_call_llm()` right after storing the conversation turn. One pass through the cog handlers covers both memory and stats. Use Redis pipeline for the stats writes (2-3 operations atomically).

### Files to Create (Phase 2)

- `src/bratbot/services/conversation_memory.py`
- `src/bratbot/services/stats_tracker.py`
- `src/bratbot/commands/clearhistory.py`
- `src/bratbot/commands/stats.py`
- `sms/conversation_memory.py` (duplicated from bratbot, ~50 lines)

### Files to Modify (Phase 2)

- `model/app.py` -- Add `history` field to all request models + role validation
- `src/bratbot/services/llm_client.py` -- Add `history` parameter to all chat methods
- `src/bratbot/commands/bratchat.py` -- Fetch/store memory + record stats inside `_call_llm()`
- `src/bratbot/commands/cami.py` -- Same
- `src/bratbot/commands/mommy.py` -- Same (from Phase 1)
- `src/bratbot/commands/tsundere.py` -- Same
- `src/bratbot/commands/drill.py` -- Same
- `src/bratbot/events/messages.py` -- Same (for @mention handler, personality=`brat`)
- `src/bratbot/bot.py` -- Initialize ConversationMemory and StatsTracker in setup_hook() + close()
- `src/bratbot/config/settings.py` -- New memory settings + feature flag
- `sms/app.py` -- Fetch/store memory, record stats
- `sms/settings.py` -- New memory settings

### Tests (Phase 2)

- `tests/test_conversation_memory.py` -- Window trimming, TTL, clear, graceful degradation, role validation
- `tests/test_stats_tracker.py` -- Increment, multi-personality tracking, first-seen, pipeline atomicity
- `tests/test_model_api.py` -- History field acceptance, backwards compatibility, invalid role rejection
- `tests/test_llm_client.py` -- History parameter forwarding
- Update existing cog tests if any exist

---

## Phase 3: Leaderboards & Achievements

### Leaderboard

#### `/leaderboard` Command

New cog `src/bratbot/commands/leaderboard.py`:
- Shows top 10 users by message count
- Discord embed with rank numbers, user mentions, message counts
- Optional personality filter: `/leaderboard personality:brat`
- Uses `ZREVRANGE` on `stats:total_messages` (or `stats:personality:{name}`)
- In-character framing: "Here are my most annoyingly persistent fans..."
- Add `@app_commands.checks.cooldown(1, 10)` to prevent spam (Redis-free, Discord built-in)

### Achievements

#### Service: `src/bratbot/services/achievements.py`

```python
ALL_PERSONALITIES = ["brat", "cami", "mommy", "tsundere", "drill"]

@dataclass
class Achievement:
    id: str
    name: str
    desc: str
    threshold: int | None = None
    stat: str | None = None  # key into UserStats fields or "personality:{name}"

    def is_unlocked(self, stats: UserStats) -> bool:
        """Check if this achievement is unlocked given current stats."""
        ...
```

Declarative achievement definitions:

```python
ACHIEVEMENTS = [
    Achievement(id="first_roast", name="First Roast",
                desc="Got your first response", threshold=1, stat="total_messages"),
    Achievement(id="hundred_club", name="Hundred Club",
                desc="Survived 100 insults", threshold=100, stat="total_messages"),
    Achievement(id="personality_sampler", name="Personality Sampler",
                desc=f"Tried all {len(ALL_PERSONALITIES)} personalities",
                threshold=len(ALL_PERSONALITIES), stat="personalities_used_count"),
    Achievement(id="brat_specialist", name="Brat Specialist",
                desc="50 messages with maximum brat", threshold=50, stat="personality:brat"),
    Achievement(id="cami_devotee", name="Cami Devotee",
                desc="50 messages with Cami", threshold=50, stat="personality:cami"),
    Achievement(id="mommy_devotee", name="Mommy's Favorite",
                desc="50 messages with Mommy", threshold=50, stat="personality:mommy"),
    Achievement(id="tsundere_devotee", name="Tsundere Target",
                desc="50 messages with Tsundere", threshold=50, stat="personality:tsundere"),
    Achievement(id="drill_devotee", name="Reporting for Duty",
                desc="50 messages with Drill Sergeant", threshold=50, stat="personality:drill"),
]
```

**No lambda-based checks.** All achievements use `threshold` + `stat` for declarative, testable, serializable definitions. The `personalities_used_count` stat is derived from `StatsTracker.get_user_stats()` which pipelines `ZSCORE` calls across all personalities.

#### Achievement Checking (Performance)

Achievement checks happen after each interaction. To minimize Redis round-trips:
1. Pipeline all reads: `HGETALL achievements:{user_id}` + `ZSCORE` calls for relevant stats
2. Only check achievements not already unlocked
3. Only check achievements relevant to the personality just used (e.g., after a brat interaction, only check `brat_specialist`, `first_roast`, `hundred_club`, `personality_sampler` -- skip `cami_devotee`)

This reduces from ~10 round-trips to 1 pipelined call with ~4-5 commands.

#### Redis Storage

- `achievements:{user_id}` -- hash (key=achievement_id, value=unlock_timestamp)
- Check achievements after each interaction (inside `_call_llm()`, after stats recording)

#### `/achievements` Command

New cog `src/bratbot/commands/achievements.py`:
- Shows invoking user's unlocked and locked achievements
- Discord embed with checkmark/lock indicators
- Optional user argument to view another user's badges
- Add `@app_commands.checks.cooldown(1, 10)` to prevent spam

#### Unlock Notifications

After the LLM reply is sent, check for newly unlocked achievements. If any, send **a single follow-up message** combining all unlocks (not one message per achievement). In-character: "Ugh, you unlocked 'Hundred Club.' I can't believe you've talked to me that many times."

### Redis Persistence

Add `appendonly yes` to Redis config. This ensures stats, achievements, and leaderboard data survive pod restarts.

**Implementation:**
- **docker-compose.yml:** Add `command: redis-server --appendonly yes` to the Redis service
- **Dockerfile.runpod / supervisord config:** Add `--appendonly yes` to the Redis start command in the supervisord program section

### Files to Create (Phase 3)

- `src/bratbot/services/achievements.py`
- `src/bratbot/commands/leaderboard.py`
- `src/bratbot/commands/achievements.py`

### Files to Modify (Phase 3)

- All personality cog handlers -- Add achievement checking after stats recording (inside `_call_llm()`)
- `src/bratbot/bot.py` -- Initialize Achievements service in setup_hook()
- `docker-compose.yml` -- Add `command: redis-server --appendonly yes` to Redis service
- `supervisord.runpod.conf` -- Add `--appendonly yes` to Redis program (if applicable)

### Tests (Phase 3)

- `tests/test_achievements.py` -- Threshold checking, unlock detection, idempotency, pipeline efficiency
- `tests/test_leaderboard.py` -- Top-N retrieval, personality filtering, empty state, cooldown

---

## Verification Plan

### Phase 1 Verification
1. Run `uv run pytest tests/ -v` -- all new and existing tests pass
2. Run `uv run ruff check src/ model/ sms/` -- no lint errors
3. Start model API locally: `uvicorn model.app:app --port 8000`
4. Test new endpoints: `curl -X POST localhost:8000/mommychat -H "Content-Type: application/json" -d '{"message": "test"}'`
5. Start bot: `python -m bratbot` -- verify new commands appear in Discord

### Phase 2 Verification
1. All tests pass including new memory and stats tests
2. Send multiple messages to same personality -- verify bot remembers context
3. Send `/clearhistory` -- verify memory is cleared
4. Wait 30+ minutes -- verify memory expires (TTL)
5. Send `/stats` -- verify counts are accurate
6. Test SMS memory: send multiple SMS, verify context is maintained
7. Test graceful degradation: stop Redis, verify bot still responds (stateless)
8. Test feature flag: set `ENABLE_CONVERSATION_MEMORY=false`, verify stateless behavior
9. Test history role validation: send crafted request with `role: "system"` in history, verify 400 rejection

### Phase 3 Verification
1. All tests pass including achievement and leaderboard tests
2. Send enough messages to unlock "First Roast" -- verify notification appears
3. Send `/achievements` -- verify badge is shown
4. Send `/leaderboard` -- verify ranking appears
5. Restart Redis -- verify data persists (appendonly)
6. Unlock multiple achievements in one message -- verify single combined notification

---

## Dependencies

No new Python packages required. All features use:
- `redis` (already a dependency)
- `discord.py` (already a dependency)
- `httpx` (already a dependency)
- `pydantic` (already a dependency)

**Dockerfile.runpod note:** `model/requirements.txt` and `sms/requirements.txt` do not need updates since no new packages are added. The new `sms/conversation_memory.py` file uses only `redis` and `json` (both already available).

---

## Out of Scope

- Payment infrastructure (Phase 4, after user growth)
- Tier gating (requires payment infra)
- Voice messages
- Custom user-created personas
- Image reactions
- Web dashboard
- Cross-platform identity merging (Discord user ID <-> phone number)
