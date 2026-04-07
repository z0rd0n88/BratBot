# BratBot Roadmap

> Generated from [open GitHub issues](https://github.com/z0rd0n88/BratBot/issues) on 2026-03-21.

---

## Phase 1 — Stability & Core Fixes

Quick wins that fix broken behavior and fill foundational gaps before new features land.

| Issue | Title | Why first? |
|-------|-------|------------|
| [#7](https://github.com/z0rd0n88/BratBot/issues/7) | Bug: apostrophes in user input cause an error | Blocks normal conversation — users can't type "what's up" |
| [#5](https://github.com/z0rd0n88/BratBot/issues/5) | Include user input query in LLM prompt | Bot can't properly respond without seeing what the user said |

### Key deliverables
- Identify and fix the apostrophe/special-character processing bug across all clients (Discord, Telegram)
- Add test coverage for special characters in user input
- Ensure the user's original message is always passed to the LLM alongside the system prompt and conversation history

---

## Phase 2 — Architecture & Unified Command System

Restructure internals so every feature built after this point works on all clients automatically.

| Issue | Title | Why here? |
|-------|-------|-----------|
| [#11](https://github.com/z0rd0n88/BratBot/issues/11) | Unify commands across Discord clients | Eliminates duplicated logic; every later feature benefits from write-once commands |
| [#13](https://github.com/z0rd0n88/BratBot/issues/13) | Spec Review: Race condition in cog pattern + Redis pipeline batching | Architectural review that must inform the unified design |
| [#12](https://github.com/z0rd0n88/BratBot/issues/12) | Phase 2: Fix race condition in conversation memory + Redis pipeline for achievements | Move memory ops inside the serialized queue; batch Redis calls via pipelines |

### Key deliverables
- Shared command handler module with per-client prefix mapping
- Existing Discord commands migrated to shared system
- Race condition fixed — all memory operations (fetch history, store turn, record stats) moved inside the queued `_call_llm()` coroutine
- Redis pipeline batching for achievement checks (5+ round-trips → 1)

---

## Phase 3 — User Identity & Preferences

Give users control over their experience and let the bot remember who they are.

| Issue | Title | Why here? |
|-------|-------|-----------|
| [#3](https://github.com/z0rd0n88/BratBot/issues/3) | Per-user context window and preference memory | Foundation for all personalization — sliding conversation window + Redis-backed preferences |
| [#4](https://github.com/z0rd0n88/BratBot/issues/4) | Settings command: gender, severity, verbosity, model, bot personality | User-facing interface to configure preferences |
| [#2](https://github.com/z0rd0n88/BratBot/issues/2) | Mommy/Mistress mode: honorific override for female users | Depends on settings command + preference memory |

### Key deliverables
- Sliding window of recent conversation history (configurable, 10-20 messages) sent to the LLM
- Per-user preferences stored in Redis (name, honorific, intensity, topics/boundaries)
- `/settings` command with flat subcommand interface (`/settings gender female`, `/settings severity 7`, etc.)
- Honorific override system — users choose their preferred term, defaults to existing behavior
- Preferences follow users across all clients

---

## Phase 4 — Access Control & Safety

Lock down who can use the bot and ensure age-appropriate gating.

| Issue | Title | Why here? |
|-------|-------|-----------|
| [#6](https://github.com/z0rd0n88/BratBot/issues/6) | Age verification gate (18+) | Adult-themed content requires verification before interaction |
| [#10](https://github.com/z0rd0n88/BratBot/issues/10) | Allowlist-based access control | Restrict bot access to approved users/servers |

### Key deliverables
- One-time 18+ confirmation per user, stored in Redis, cross-client
- Bot responds only with verification prompt until user confirms
- Allowlist supporting Discord server IDs and Discord usernames
- Admin commands to manage allowlist entries
- Non-allowlisted users denied with a message

---

## Phase 5 — New Personalities & Platform Expansion

Broaden the bot's reach with new voices and new clients.

| Issue | Title | Why here? |
|-------|-------|-----------|
| [#8](https://github.com/z0rd0n88/BratBot/issues/8) | Create custom voice/personality for Bonnie | Analyze Bonnie's message history to build a distinct personality profile |
| [#9](https://github.com/z0rd0n88/BratBot/issues/9) | Telegram client integration | New platform — benefits from unified commands, preferences, and access control already in place |

### Key deliverables
- Bonnie personality profile generated from message history analysis (tone, vocabulary, phrases, mannerisms)
- Bonnie selectable via `/settings bot bonnie`
- Telegram bot client using `python-telegram-bot` or similar (future platform expansion)
- Telegram integrated into Docker Compose and RunPod deployment
- All existing features (preferences, age gate, allowlist, rate limiting) work on Telegram out of the box

---

## Dependency Graph

```
Phase 1 (Bugs & Foundations)
  │
  ▼
Phase 2 (Unified Commands & Architecture)
  │
  ▼
Phase 3 (User Identity & Preferences)
  │
  ├──► Phase 4 (Access Control & Safety)
  │
  └──► Phase 5 (Personalities & Platforms)
```

Phases 4 and 5 can be worked in parallel once Phase 3 is complete.
