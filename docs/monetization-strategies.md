# BratBot Monetization Strategies

## Current Feature Inventory

### What BratBot Has Today

| Feature | Platform | Status | Monetization Potential |
|---|---|---|---|
| `/bratchat` (3 brat levels) | Discord | Production | High -- brat_level is a natural tier axis |
| `/camichat` (Cami personality) | Discord | Production | High -- premium personality |
| @mention responses | Discord | Production | Medium -- usage-based gating |
| SMS/RCS messaging | Twilio | Production | High -- per-message or subscription |
| SMS personality routing ("cami:", "brat:") | Twilio | Production | Medium -- premium routing |
| Per-user rate limiting (5s cooldown) | All | Production | High -- tier-based limits |
| Per-channel rate limiting (10/min) | Discord | Production | High -- server-level tiers |
| Request queue (5 depth) | Discord | Production | Medium -- priority queuing |
| Self-hosted LLM (qwen3-14b) | Backend | Production | High -- model selection per tier |
| Graceful degradation (Redis down) | All | Production | Low -- reliability feature |

### Architecture Advantages for Monetization

- **`brat_level` parameter (1-3)** is already wired end-to-end: Discord command -> Model API -> Ollama. Gating levels 2-3 behind a paywall requires minimal code changes.
- **Rate limiter** is Redis-backed with configurable windows. Changing limits per-user based on tier is a natural extension.
- **Multiple personalities** (BratBot, Cami) are separate endpoints. Adding new personalities = adding new prompt files + API endpoints + Discord commands.
- **SMS gateway** runs independently on port 8001. SMS monetization can be layered on without touching Discord code.
- **Request queue** already has max-depth and timeout controls. Priority queuing for paid users is architecturally straightforward.

---

## Free + Tiered Revenue Model

### Tier Structure

#### Free Tier
- `/bratchat` at brat_level 1 only (helpful but mildly sassy)
- 10 messages per hour (Discord)
- No SMS access
- No Cami personality
- Standard queue priority
- Community support only

#### Pro Tier -- $4.99/mo
- `/bratchat` at all brat levels (1-3, including maximum brat)
- 100 messages per hour (Discord)
- `/camichat` access (Cami personality)
- SMS access (50 messages/mo included)
- Priority queue (skip ahead of free users)
- Pro role in Discord server

#### Ultra Tier -- $14.99/mo
- Everything in Pro
- Unlimited messages (Discord)
- Unlimited SMS messages
- Early access to new personalities
- Custom brat_level tuning (choose your own sass level 1-10)
- Dedicated queue (never wait)
- Ultra role in Discord server
- Vote on new features/personalities

### Why These Price Points

- **$4.99** is impulse-buy territory. Low enough that users won't overthink it. Covers ~33 users to break even on RunPod hosting ($150/mo).
- **$14.99** targets power users and superfans. 10 Ultra subscribers = $150/mo (covers hosting alone). Everything above is profit.
- **Free tier** is essential for growth. Users need to experience the bot before paying. Level 1 gives a taste of the personality without the full experience.

---

## Revenue Streams

### 1. Discord Subscriptions (Primary)

**How it works:** Users subscribe via Stripe/LemonSqueezy. Bot checks subscription status before executing gated commands. Tier info stored in Redis (cached) with Stripe as source of truth.

**Implementation leverage:**
- `brat_level` parameter already exists -- just gate levels 2-3
- Rate limiter already configurable -- add per-tier limits
- Cami endpoint already separate -- check tier before calling

**Estimated revenue:** 500 active users x 5% conversion = 25 Pro subs = $125/mo. With 2% Ultra conversion = 10 Ultra subs = $150/mo. **Total: ~$275/mo** at modest adoption.

### 2. SMS/RCS Subscriptions (Secondary)

**How it works:** SMS access is Pro+ only. Free users get a teaser (one free SMS to try it, then paywall). Pro gets 50/mo, Ultra unlimited.

**Why SMS is premium:**
- Twilio costs ~$0.0079/segment to send. 50 messages/mo = ~$0.40/user cost. At $4.99/mo, strong margin.
- SMS feels more personal/private than Discord. Users will pay for the intimacy.
- RCS (rich messaging) is coming via Twilio -- future upsell opportunity.

**Implementation leverage:**
- SMS gateway already tracks per-phone rate limits via Redis
- Add message counter per billing period, check against tier allowance
- Twilio costs are variable -- SMS tier pricing must account for per-message cost

### 3. Server Subscriptions (Growth)

**How it works:** Discord server admins pay for BratBot access in their server. Different from individual user subscriptions.

| Server Plan | Price | What It Includes |
|---|---|---|
| Starter | Free | brat_level 1, 50 msgs/day server-wide |
| Server Pro | $9.99/mo | All levels, 500 msgs/day, Cami access |
| Server Ultra | $29.99/mo | Unlimited, all personalities, priority |

**Why this works:**
- Server owners already pay for other bots (MEE6 Premium: $11.95/mo, Dyno Premium: $4.49/mo)
- BratBot is unique -- no direct competitor with this personality niche
- Per-channel rate limiting already exists, just needs per-server tier enforcement

### 4. New Personalities (Feature Expansion)

**Potential new personalities to develop:**

| Personality | Description | Tier |
|---|---|---|
| **Brat (existing)** | Sassy, condescending, secretly loves you | Free (L1) / Pro (L2-3) |
| **Cami (existing)** | Submissive, eager to please | Pro |
| **Mommy** | Nurturing but firm, "I'm not mad, just disappointed" | Pro |
| **Tsundere** | "It's not like I wanted to help you or anything!" | Pro |
| **Drill Sergeant** | Aggressive motivation, "DROP AND GIVE ME CODE" | Pro |
| **Valley Girl** | "Okay so like, your code is literally broken?" | Free (teaser) |
| **Professor** | Condescending academic, "As I explained in my seminal paper..." | Ultra |
| **Chaos Gremlin** | Chaotic neutral, might help, might roast, unpredictable | Ultra |

**Implementation:** Each personality = 1 prompt file + 1 API endpoint + 1 Discord command. The pattern is already established with BratBot and Cami.

**Revenue impact:** New personalities drive upgrades. Release one free personality to hook users, gate the rest behind Pro/Ultra. Seasonal or limited-time personalities create urgency.

### 5. Merchandise (Passive)

**Low-effort approach (start here):**
- Redbubble/TeeSpring store with BratBot-themed designs
- Link in Discord bot's profile, `/merch` command
- Designs: catchphrases, personality quotes, logo
- **Expected:** $50-200/mo passive income with minimal effort

**Scaled approach (if community grows):**
- Discord store integration (native purchasing)
- Seasonal drops (holiday-themed designs, community-voted)
- Sticker packs for Discord/iMessage
- **Expected:** $500-2k/mo with active community engagement

### 6. Tips/Donations (Supplementary)

- Ko-fi or Buy Me a Coffee integration
- `/tip` command in Discord
- Tip jar link in bot responses (subtle, not spammy)
- **Expected:** $50-100/mo from superfans. Low effort, worth having.

---

## Proposed New Features (Revenue-Driving)

### Conversation Memory (Pro+)
- Remember context within a session (Redis-backed conversation history)
- Free users get stateless interactions (each message is independent)
- Pro/Ultra get 10/50 message memory window
- **Why it drives revenue:** Continuity makes the bot feel like a relationship, not a tool

### Custom Personas (Ultra)
- Users create their own personality prompt
- Name it, set the sass level, define the vibe
- Share custom personas with friends (viral growth)
- **Why it drives revenue:** Personalization is the ultimate premium feature

### Voice Messages (Ultra)
- TTS (text-to-speech) responses in Discord voice channels
- Choose from personality-matched voices
- **Why it drives revenue:** Voice is intimate and novel. Discord bots with voice are rare.

### Image Reactions (Pro+)
- BratBot sends personality-appropriate reaction images/GIFs
- Curated library of bratty, sassy, submissive reaction media
- **Why it drives revenue:** Visual content increases engagement and shareability

### Leaderboards & Achievements (Free, drives engagement)
- Track who gets roasted the most, who asks the dumbest questions
- Achievement badges: "Survived 100 insults", "Made Brat speechless"
- Public leaderboard in Discord server
- **Why it drives revenue:** Engagement loop that keeps users coming back. Free feature that increases conversion.

### DM Mode (Pro+)
- Private conversations with BratBot in DMs
- More personal, less public. Users may ask things they wouldn't in a server.
- DMs already work technically -- just gate them behind tier check
- **Why it drives revenue:** Privacy is premium. Users will pay for private access.

---

## Payment Infrastructure

### Recommended: Stripe + Discord Roles

**Flow:**
1. User visits payment link (Stripe Checkout or LemonSqueezy)
2. On successful payment, webhook fires to your backend
3. Backend assigns Discord role (Pro/Ultra) via Discord API
4. Bot checks role before executing gated commands
5. Stripe handles recurring billing, cancellations, upgrades

**Why Stripe:**
- Industry standard, lowest friction
- Handles subscriptions, invoices, tax
- Webhook system integrates cleanly with FastAPI
- No PCI burden (Stripe Checkout is hosted)

**Alternative: LemonSqueezy**
- Even simpler than Stripe (built for indie creators)
- Handles EU VAT automatically
- Slightly higher fees but zero tax/compliance headache
- Good if you want to avoid Stripe's complexity

### Role-Based Gating (Discord)

- Free: No special role (default)
- Pro: `@BratBot Pro` role (assigned by payment webhook)
- Ultra: `@BratBot Ultra` role (assigned by payment webhook)
- Bot checks role on every gated command before executing
- Redis caches tier status (avoid Discord API call on every message)

---

## Revenue Projections

### Conservative (Side Income Target)

| Stream | Users | Conversion | Revenue/mo |
|---|---|---|---|
| Discord Pro | 500 active | 5% (25 subs) | $125 |
| Discord Ultra | 500 active | 2% (10 subs) | $150 |
| SMS Pro (included) | -- | -- | $0 (bundled) |
| Server Pro | 3 servers | -- | $30 |
| Merch | -- | -- | $75 |
| Tips | -- | -- | $50 |
| **Total** | | | **~$430/mo** |
| **Costs** (RunPod + Twilio) | | | **-$175/mo** |
| **Net** | | | **~$255/mo** |

### Optimistic (Growth Target)

| Stream | Users | Conversion | Revenue/mo |
|---|---|---|---|
| Discord Pro | 2,000 active | 8% (160 subs) | $800 |
| Discord Ultra | 2,000 active | 3% (60 subs) | $900 |
| Server Pro | 10 servers | -- | $100 |
| Server Ultra | 3 servers | -- | $90 |
| SMS add-on | 50 users | -- | $250 |
| Merch | -- | -- | $200 |
| Tips | -- | -- | $100 |
| **Total** | | | **~$2,440/mo** |
| **Costs** (RunPod + Twilio + Stripe fees) | | | **-$300/mo** |
| **Net** | | | **~$2,140/mo** |

---

## Implementation Strategy

**Current state:** Under 100 Discord users. **Strategy: engagement first, monetize later.**

Build features that make users stick and invite friends. Payment infrastructure comes after we have an audience worth monetizing.

### Phase 1: New Personalities (1-2 days)

The fastest visible win. Follows the exact established pattern (prompt file + API endpoint + Discord command + SMS route). Zero architectural risk.

**New characters:**
| Personality | Vibe | Implementation |
|---|---|---|
| **Mommy** | Nurturing but firm, "I'm not mad, just disappointed" | `model/prompts/mommy.txt` + `/mommychat` |
| **Tsundere** | "It's not like I wanted to help you or anything!" | `model/prompts/tsundere.txt` + `/tsunderechat` |
| **Drill Sergeant** | Aggressive motivation, "DROP AND GIVE ME CODE" | `model/prompts/drill_sergeant.txt` + `/drillchat` |

**Prerequisite refactor:** Extract shared `_generate_response()` helper in `model/app.py` to eliminate copy-paste between endpoints. Currently `bratchat()` and `camichat()` are nearly identical. This helper becomes the injection point for conversation history in Phase 2.

**Files touched:**
- `model/prompts/` — 3 new `.txt` prompt files
- `model/app.py` — refactor + 3 new endpoints
- `src/bratbot/services/llm_client.py` — 3 new client methods
- `src/bratbot/commands/` — 3 new cog files (auto-discovered)
- `sms/app.py` — update `_parse_route()` for new prefixes

### Phase 2: Conversation Memory + Basic Stats (3-5 days)

The highest-impact engagement feature. Transforms BratBot from a novelty into something users return to daily.

**Conversation Memory:**
- New service: `src/bratbot/services/conversation_memory.py`
- Redis list per conversation: `conv:{personality}:{scope}:{user_id}`
- Configurable window (default 10 exchanges) + TTL (default 30 min)
- `model/app.py` gets optional `history` field on all endpoints (backwards-compatible)
- Ollama already supports message arrays — no format changes needed
- `/clearhistory` command for user control
- SMS gateway gets memory support too

**Basic Stats Tracking (piggybacks on memory work):**
- New service: `src/bratbot/services/stats_tracker.py`
- Redis sorted sets: `stats:total_messages`, `stats:personality:{name}`
- Instrumented in same cog handlers modified for memory
- `/stats` command showing user's own message count, personalities used, first-seen date

### Phase 3: Leaderboards & Achievements (3-5 days)

Supports engagement that already exists from Phases 1-2.

**Leaderboard:**
- `/leaderboard` command — top 10 users by message count
- Optional personality filter: `/leaderboard personality:brat`
- Redis `ZREVRANGE` on existing sorted sets

**Achievements:**
- Declarative achievement definitions (milestone-based)
- Examples: "First Roast" (1 msg), "Hundred Club" (100 msgs), "Personality Sampler" (tried all 5)
- `/achievements` command showing unlocked/locked badges
- In-character unlock notifications after LLM responses
- Redis hash: `achievements:{user_id}`

**Redis persistence:** Add `appendonly yes` to Redis config so stats and achievements survive pod restarts.

### Phase 4: Monetization (after reaching 500+ users)

Only build payment infrastructure when there's an audience to convert:

1. Stripe/LemonSqueezy account setup
2. Payment webhook endpoint (FastAPI)
3. Discord role assignment on payment
4. Tier checking middleware (Redis-cached role lookup)
5. Gate features behind Pro/Ultra roles
6. Per-tier rate limit configuration
7. SMS monetization (gate behind Pro tier)
8. Merch store (Redbubble, `/merch` command)

---

## Key Risks

| Risk | Mitigation |
|---|---|
| Users won't pay for a Discord bot | Free tier validates demand before building payment infra |
| Twilio costs eat SMS margin | 50 msg/mo cap on Pro, monitor per-user cost |
| GPU costs increase with usage | Queue depth limits prevent runaway inference |
| Content moderation issues | Personalities are pre-defined prompts, not user-generated |
| Stripe/payment complexity | LemonSqueezy as simpler alternative |
| Low conversion rates | Focus on engagement features (leaderboards, memory) to increase stickiness before monetizing |
