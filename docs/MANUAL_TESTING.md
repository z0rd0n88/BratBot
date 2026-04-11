# Manual Testing Checklist

Use this checklist to verify all bot features in a live Discord server.
Each section covers one feature area with exact steps and expected results.

> **Prerequisites**: Both bots online, model server running and warmed up, Redis available.
> Run `/ping` on both bots first to confirm they're alive.

---

## BratBot Commands

### /ping
| Step | Expected Result |
|---|---|
| Run `/ping` | Responds with "Pong!" and latency in ms |

### /bratchat
| Step | Expected Result |
|---|---|
| `/bratchat How do loops work?` | Responds with bratty explanation (in-character) |
| `/bratchat` with empty message | Discord prevents submission (message param is required) |
| Send 2 messages within 5 seconds | Second message gets rate-limited reply: "Slow down..." |
| Send in a channel with 10+ messages/min | Channel rate limit reply appears |
| Run while model is cold (just restarted) | Gets warming-up reply: "My brain's still booting up..." |

### /camichat
| Step | Expected Result |
|---|---|
| `/camichat What is a closure?` | Responds in Cami's submissive personality |
| Set pronoun to female, then `/camichat hello` | Response uses "Mommy" address |
| Set pronoun to male, then `/camichat hello` | Response uses "Daddy" address |
| Set pronoun to other, then `/camichat hello` | Response uses neutral address (no gendered pet name) |

### /verbose
| Step | Expected Result |
|---|---|
| `/verbose` (no argument) | Shows current verbosity or "not set" if default |
| `/verbose 1` | Confirms short mode set. Next `/bratchat` gives 1-2 sentence reply |
| `/verbose 2` | Confirms medium mode set. Next `/bratchat` gives normal-length reply |
| `/verbose 3` | Confirms long mode set. Next `/bratchat` gives thorough, detailed reply |

### /pronoun
| Step | Expected Result |
|---|---|
| `/pronoun` (no argument) | Shows current pronoun or "not set" if default |
| `/pronoun male` | Confirms male pronoun set |
| `/pronoun female` | Confirms female pronoun set |
| `/pronoun other` | Confirms other pronoun set |

### /forget
| Step | Expected Result |
|---|---|
| Chat with `/bratchat` 2-3 times, then `/forget bratbot` | Confirms history cleared. Next `/bratchat` has no memory of previous messages |
| Chat with `/camichat` 2-3 times, then `/forget cami` | Confirms Cami history cleared |

### /forgetall
| Step | Expected Result |
|---|---|
| Chat with both `/bratchat` and `/camichat`, then `/forgetall` | Confirms all history cleared for all personas |

### /help
| Step | Expected Result |
|---|---|
| `/help` | Shows all commands: `/bratchat`, `/camichat`, `/verbose`, `/pronoun`, `/ping` |

### Age Verification (BratBot only)
| Step | Expected Result |
|---|---|
| First-time user runs `/bratchat` | Gets age verification modal with warning + "I confirm I am 18+" button |
| Click "I confirm I am 18 or older" | Shows checkmark confirmation, then executes the original command |
| Subsequent `/bratchat` calls | No verification prompt (permanently verified) |
| Let verification view timeout (60s) | Button becomes disabled |
| `/ping` without verification | Works without age gate (ping is exempt) |
| `/help` without verification | Works without age gate (help is exempt) |

### @Mention (BratBot)
| Step | Expected Result |
|---|---|
| @BratBot how do variables work? | Bot replies in-channel with bratty explanation |
| @BratBot (empty mention, no text) | Bot replies with empty-mention message: "You pinged me just to say nothing?" |
| @BratBot in rapid succession | Rate limit enforced (same as slash commands) |
| @BratBot in DM | Ignored (mentions only work in guilds) |

---

## BonnieBot Commands

### /ping
| Step | Expected Result |
|---|---|
| Run `/ping` | Responds with "Pong!" and latency in ms |

### /bonniebot
| Step | Expected Result |
|---|---|
| `/bonniebot Hello!` | Responds in Bonnie's sweet/seductive personality |
| Rate limit test (2 messages in 5s) | Gets rate-limited reply: "Easy there, sweetheart..." |
| Run while model is cold | Gets warming-up reply: "Hold on, honey bun..." |

### /verbose (BonnieBot)
| Step | Expected Result |
|---|---|
| `/verbose` (no argument) | Shows current verbosity |
| `/verbose 1` | Confirms short mode. Next `/bonniebot` gives brief reply |
| `/verbose 3` | Confirms long mode. Next `/bonniebot` gives thorough reply |

### /pronoun (BonnieBot)
| Step | Expected Result |
|---|---|
| `/pronoun female` | Confirms female pronoun set. Next `/bonniebot` uses "Ma'am" |
| `/pronoun male` | Confirms male pronoun set. Next `/bonniebot` uses "Sir" |

### /forget (BonnieBot)
| Step | Expected Result |
|---|---|
| `/forget` | Confirms history cleared |

### /forgetall (BonnieBot)
| Step | Expected Result |
|---|---|
| `/forgetall` | Confirms all persona history cleared |

### /help (BonnieBot)
| Step | Expected Result |
|---|---|
| `/help` | Shows all commands: `/bonniebot`, `/verbose`, `/pronoun`, `/ping` |

### @Mention (BonnieBot)
| Step | Expected Result |
|---|---|
| @BonnieBot hello | Bot replies in-channel in Bonnie's personality |
| @BonnieBot (empty) | Bot replies with empty-mention message |

---

## Shared Infrastructure

### Conversation History
| Step | Expected Result |
|---|---|
| `/bratchat What is Python?` then `/bratchat Tell me more about that` | Second response references Python (history injected) |
| `/camichat What is Rust?` then `/camichat Tell me more` | Cami remembers Rust from prior message |
| BratBot and Cami histories are isolated | `/bratchat` doesn't see Cami's history and vice versa |
| History persists across channels | Same user in different channel gets fresh history |

### Rate Limiting
| Step | Expected Result |
|---|---|
| Send 2 slash commands within 5 seconds | Second command gets in-character rate limit reply |
| 11+ messages in one channel within 60 seconds | Channel rate limit kicks in |
| Rate limit with Redis down | Commands still go through (graceful degradation) |

### Request Queue
| Step | Expected Result |
|---|---|
| Send multiple @mentions quickly in one channel | Bot shows typing indicator, processes sequentially |
| Send 6+ messages in one channel rapidly | Queue full — excess messages silently dropped |

### Error Handling
| Step | Expected Result |
|---|---|
| All error messages are in-character | No stack traces or technical errors shown to users |
| LLM server down → `/bratchat` | Gets LLM connection error reply (in personality voice) |
| LLM server timeout | Gets timeout error reply (in personality voice) |

### Response Variety
| Step | Expected Result |
|---|---|
| Ask the same question 3-5 times | Responses vary in tone/mood (mood injection working) |
| Check responses aren't repetitive | `repeat_penalty=1.2` prevents repetitive phrasing |

---

## Model Server API

### Health Check
| Step | Expected Result |
|---|---|
| `GET /health` | Returns `{"status": "ok"}` when model is loaded |
| `GET /health` during warmup | Returns 503 with warming status |

### Chat Endpoints
| Step | Expected Result |
|---|---|
| `POST /bratchat {"message": "test"}` | Returns `{"request_id": "...", "reply": "..."}` |
| `POST /camichat {"message": "test", "pronoun": "female"}` | Returns reply with female-addressing tone |
| `POST /bonniebot {"message": "test"}` | Returns reply in Bonnie's voice |
| Send message that would produce >2000 char reply | Response truncated to Discord limit (2000 chars) |

### Personality Prompts
| Step | Expected Result |
|---|---|
| `python scripts/encrypt-prompts.py decrypt` | Materializes `.txt` files from `.txt.enc` |
| `python scripts/encrypt-prompts.py encrypt` | Re-encrypts `.txt` → `.txt.enc` |
| Start model server with wrong `PROMPTS_ENCRYPTION_KEY` | Server crashes at startup (loud failure) |
| Start model server with `BRATBOT_TEST_MODE=1` | Uses test sentinel prompts (no decryption needed) |

---

## Test Harness (Automated)

### scripts/test_bots.py
| Step | Expected Result |
|---|---|
| `python scripts/test_bots.py` | Sends test queries to all endpoints, outputs terminal summary |
| `python scripts/test_bots.py --html` | Generates HTML report |
| `python scripts/test_bots.py --bots bratbot` | Tests only BratBot endpoint |
| `python scripts/test_bots.py --base-url http://remote:8000` | Tests against remote server |

---

## Feature Inventory

> **Last updated**: 2026-04-11
> When adding a new feature, add a test section above and update this inventory.

| Feature | BratBot | BonnieBot | Location |
|---|---|---|---|
| Main chat command | `/bratchat` | `/bonniebot` | `commands/bratchat.py`, `commands/bonniebot.py` |
| Cami personality variant | `/camichat` | N/A | `commands/cami.py` |
| Verbosity control | `/verbose` | `/verbose` | `common/services/verbosity_store.py` |
| Pronoun preference | `/pronoun` | `/pronoun` | `common/services/pronoun_store.py` |
| Conversation history | 2 personas (bratbot, cami) | 1 persona (bonniebot) | `common/services/conversation_history.py` |
| History clear (single) | `/forget <persona>` | `/forget` | `commands/forget.py` |
| History clear (all) | `/forgetall` | `/forgetall` | `commands/forget.py` |
| Age verification gate | Yes (18+ modal) | No | `bratbot/utils/age_gate.py` |
| Rate limiting (user) | 1 req / 5s | 1 req / 5s | `common/services/rate_limiter.py` |
| Rate limiting (channel) | 10 req / 60s | 10 req / 60s | `common/services/rate_limiter.py` |
| Request queue | 5 per channel | 5 per channel | `common/services/request_queue.py` |
| @Mention support | Yes | Yes | `common/events/messages.py` |
| Message deduplication | Yes (1000 ID cache) | Yes | `common/events/messages.py` |
| Mood injection | 8 moods | 7 moods | `model/app.py` |
| LLM warmup handling | Yes | Yes | `model/app.py` |
| Typing indicator | Yes | Yes | `common/services/request_queue.py` |
| Health check | `/ping` | `/ping` | `commands/ping.py` |
| Help command | `/help` | `/help` | `commands/help.py` |
| In-character errors | Yes | Yes | `common/events/errors.py` |
| Encrypted prompts | Yes | Yes | `model/app.py`, `scripts/encrypt-prompts.py` |
