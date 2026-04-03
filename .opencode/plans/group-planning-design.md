# Group Event Planning — Deep Design Plan

> Architecture for shareable plans, group voting, calendar coordination, and notifications.

---

## Table of Contents

1. [The Core Insight](#1-the-core-insight)
2. [System Architecture](#2-system-architecture)
3. [Shareable Plans & Links](#3-shareable-plans--links)
4. [Group Voting System](#4-group-voting-system)
5. [Calendar Overlap Engine](#5-calendar-overlap-engine)
6. [Notification Strategy](#6-notification-strategy)
7. [Database Schema](#7-database-schema)
8. [API Endpoints](#8-api-endpoints)
9. [Real-Time Updates](#9-real-time-updates)
10. [Cost Analysis](#10-cost-analysis)
11. [Implementation Phases](#11-implementation-phases)

---

## 1. The Core Insight

The hardest part of group event planning isn't finding events — it's **coordinating people**. The system needs to solve three problems in sequence:

1. **Discovery** — "What's happening?" (already solved by Tavily)
2. **Availability** — "When is everyone free?" (Nylas + overlap algorithm)
3. **Agreement** — "What do we all want to do?" (shareable plans + voting)

The flow:

```
Organizer: "Find jazz events for me, Alice, and Bob this weekend"
    │
    ▼
┌─────────────────────────────────────────────┐
│ 1. Parse intent: query + participants + date│
└──────────────────┬──────────────────────────┘
                   │
    ┌──────────────▼──────────────┐
    │ 2. Check all 3 calendars    │
    │    → find overlapping slots │
    └──────────────┬──────────────┘
                   │
    ┌──────────────▼──────────────┐
    │ 3. Search events in those   │
    │    time windows only        │
    └──────────────┬──────────────┘
                   │
    ┌──────────────▼──────────────┐
    │ 4. Create plan, generate    │
    │    shareable link           │
    └──────────────┬──────────────┘
                   │
    ┌──────────────▼──────────────┐
    │ 5. Send link to Alice & Bob │
    │    → they vote yes/no/maybe│
    └──────────────┬──────────────┘
                   │
    ┌──────────────▼──────────────┐
    │ 6. Quorum reached → confirm │
    │    → notify everyone        │
    └─────────────────────────────┘
```

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Tauri Frontend                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  Search  │  │  Plan    │  │  Voting  │  │  Calendar    │  │
│  │  View    │  │  Creator │  │  Grid    │  │  Overlay     │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP + SSE
┌────────────────────────▼─────────────────────────────────────┐
│                     FastAPI Backend                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐  │
│  │  Plan API  │  │  Vote API  │  │  Availability Engine   │  │
│  │  (CRUD)    │  │  (CRUD)    │  │  (sweep-line merge)    │  │
│  └────────────┘  └────────────┘  └────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │              Existing Agent Pipeline                    │   │
│  │   Parser → Calendar → Discovery → Auditor → Results    │   │
│  └────────────────────────────────────────────────────────┘   │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐  │
│  │  Notifier  │  │  OG Tags   │  │  Link Generator        │  │
│  │  (email)   │  │  (dynamic) │  │  (NanoID + tokens)     │  │
│  └────────────┘  └────────────┘  └────────────────────────┘  │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                      Data Layer                               │
│  ┌──────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  PostgreSQL  │  │  Redis   │  │  Nylas   │  │  Resend  │  │
│  │  (plans,     │  │  (cache, │  │  (cals)  │  │  (email) │  │
│  │   votes,     │  │  SSE,    │  │          │  │          │  │
│  │   users)     │  │  pub/sub)│  │          │  │          │  │
│  └──────────────┘  └──────────┘  └──────────┘  └──────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Shareable Plans & Links

### URL Structure

Following Rallly's proven pattern — two separate tokens per plan:

```
Public voting page:  /plan/{nanoid-16}
Admin page:          /plan/{nanoid-16}/admin?token={admin_secret}
Edit own vote:       /plan/{nanoid-16}/edit?token={participant_token}
```

**Why two tokens:**
- The public link is shareable with anyone — they can vote but not modify the plan
- The admin token lets the organizer change events, extend deadline, cancel
- Each participant gets a unique edit token so they can change their own vote

### Link Generation

```python
import secrets
import nanoid

def generate_plan_links():
    plan_id = nanoid.generate(size=16)  # e.g., "Xk7mB9qR2nF4vL8w"
    admin_token = secrets.token_urlsafe(32)
    return {
        "public_url": f"/plan/{plan_id}",
        "admin_url": f"/plan/{plan_id}/admin?token={admin_token}",
        "plan_id": plan_id,
        "admin_token": admin_token,
    }
```

### Open Graph Meta Tags

Critical for rich previews when shared in iMessage, Slack, WhatsApp. Server-rendered per plan:

```html
<meta property="og:title" content="You're invited: Jazz Night — 3 options" />
<meta property="og:description" content="Alazar is planning an event. 2 of 4 friends have voted. Vote by Friday." />
<meta property="og:image" content="https://app.com/api/og/plan/Xk7mB9qR2nF4vL8w" />
<meta property="og:url" content="https://app.com/plan/Xk7mB9qR2nF4vL8w" />
<meta property="og:type" content="website" />
```

Dynamic OG image generated server-side showing plan title, response count, and deadline.

### Link Expiration

- Plans expire after 7 days by default (configurable)
- Soft-delete via `pg_cron` daily job
- Expired plans show "This plan has expired" with option for organizer to extend

---

## 4. Group Voting System

### Voting Model

Each participant votes on each suggested event:

| Vote Type | Meaning |
|-----------|---------|
| **Yes** | I'm in, count me |
| **Maybe** | I could go if no one else can |
| **No** | Can't make it / not interested |

### The Voting Flow

```
1. Organizer searches events → picks 3-5 candidates
2. System creates a plan with those events + suggested time slots
3. Organizer adds participant emails
4. System sends email invitations with voting link
5. Each participant opens link → votes yes/maybe/no on each event
6. Real-time updates show everyone's votes (anonymized or named)
7. When quorum reached (e.g., 60% yes on any event) → confirmed
8. All participants get confirmation notification
```

### Quorum Logic

```python
def check_quorum(plan):
    total_participants = len(plan.participants)
    responded = len([p for p in plan.participants if p.has_voted])
    
    for event in plan.suggested_events:
        yes_votes = len([v for v in event.votes if v.type == "yes"])
        maybe_votes = len([v for v in event.votes if v.type == "maybe"])
        
        yes_pct = yes_votes / total_participants
        
        # Auto-confirm if 60%+ say yes
        if yes_pct >= 0.6:
            return "confirmed", event
        
        # Suggest if all responded and no clear winner
        if responded == total_participants and yes_votes > 0:
            # Pick event with highest yes + maybe combined
            best = max(plan.suggested_events, 
                      key=lambda e: yes_votes + 0.5 * maybe_votes)
            return "suggest", best
    
    return "pending", None
```

### Anonymous vs Named Voting

- Organizer chooses: show names or anonymous
- Default: named (friends planning together usually want to see who's coming)
- Anonymous mode shows "3 people said yes" without names

---

## 5. Calendar Overlap Engine

### Algorithm: Sweep-Line Interval Merge

The most efficient approach for finding common free time across N calendars:

```python
def find_common_free_time(participants, window_start, window_end, duration_minutes=120):
    """
    Find time slots where ALL participants are free.
    
    Uses sweep-line algorithm:
    1. Collect all busy intervals from all calendars
    2. Sort by start time
    3. Merge overlapping intervals
    4. Invert to get free slots
    5. Filter slots by minimum duration
    """
    # Step 1: Collect all busy intervals (parallel fetch via Nylas)
    all_busy = []
    for participant in participants:
        busy_intervals = fetch_busy_intervals(participant.email, window_start, window_end)
        all_busy.extend(busy_intervals)
    
    if not all_busy:
        # Everyone is completely free — return the full window
        return [(window_start, window_end)]
    
    # Step 2: Sort by start time
    all_busy.sort(key=lambda x: x.start)
    
    # Step 3: Merge overlapping intervals
    merged = [all_busy[0]]
    for interval in all_busy[1:]:
        if interval.start <= merged[-1].end:
            merged[-1].end = max(merged[-1].end, interval.end)
        else:
            merged.append(interval)
    
    # Step 4: Invert to get free slots
    free_slots = []
    cursor = window_start
    for busy in merged:
        if busy.start > cursor:
            gap = busy.start - cursor
            if gap.total_seconds() >= duration_minutes * 60:
                free_slots.append((cursor, busy.start))
        cursor = max(cursor, busy.end)
    
    # Check trailing free time
    if window_end > cursor and (window_end - cursor).total_seconds() >= duration_minutes * 60:
        free_slots.append((cursor, window_end))
    
    return free_slots
```

### Complexity

| Metric | Value |
|--------|-------|
| Time | O(M log M) where M = total events across all calendars |
| Space | O(M) for storing intervals |
| Practical | ~10-50 events/person × 2-10 people = 20-500 intervals — trivial |

### Timezone Handling

- All computations in UTC
- Each participant's calendar events normalized to UTC via Nylas
- Search window defined in organizer's timezone, converted to UTC
- Display times in each viewer's local timezone

### Caching Strategy

```
Redis key: availability:{sorted_participant_emails}:{window_start}:{window_end}
TTL: 5 minutes
Invalidation: Nylas webhook on calendar change, or TTL expiry
```

### Progressive Search Window

```
1. Check next 3 days (fast path — most plans are imminent)
2. If < 2 slots found, expand to 7 days
3. If still < 2 slots, expand to 14 days
4. Stop at 14 days — beyond that calendars are too unreliable
```

### Slot Scoring & Ranking

After finding all valid slots, rank them:

```python
def score_slot(slot, organizer_tz, participants):
    score = 1.0
    local_hour = slot.start.astimezone(organizer_tz).hour
    
    # Prefer afternoons (12-6pm)
    if 12 <= local_hour <= 18:
        score *= 1.3
    
    # Avoid early morning and late night
    if local_hour < 9 or local_hour > 21:
        score *= 0.5
    
    # Avoid Mondays
    if slot.start.weekday() == 0:
        score *= 0.8
    
    # Timezone fairness — penalize slots that are unreasonable for anyone
    for p in participants:
        p_local_hour = slot.start.astimezone(p.tz).hour
        if p_local_hour < 7 or p_local_hour > 22:
            score *= 0.3
    
    # Prefer slots with more buffer from now (prep time)
    hours_from_now = (slot.start - datetime.now(timezone.utc)).total_seconds() / 3600
    score *= min(1.0, hours_from_now / 2)
    
    return score
```

---

## 6. Notification Strategy

### Cost-Optimal Approach: Email First, SMS Fallback

| Channel | Cost/Message | Open Rate | Use For |
|---------|-------------|-----------|---------|
| **Email (Resend)** | $0.0004 (free tier: 3K/mo) | 20-30% | Primary invitations, updates |
| **Email (AWS SES)** | $0.0001 | 20-30% | High-volume, backup |
| **SMS (Telnyx)** | $0.008 all-in | 98% | Urgent reminders, confirmations |
| **In-app** | $0 | N/A | Real-time updates for logged-in users |

### Recommended Stack

**Primary: Resend** (email)
- 3,000 emails/month free (100/day)
- $20/mo for 50K
- Great developer experience, React email templates
- Perfect for plan invitations and vote reminders

**Fallback: Telnyx** (SMS)
- $0.004/message + carrier fees ≈ $0.008 total
- Only for time-sensitive notifications: "Event starts in 1 hour!"
- Requires A2P 10DLC registration (~$27 one-time + $1.50/mo)

### Notification Types

| Type | Channel | Trigger |
|------|---------|---------|
| Plan invitation | Email | Organizer creates plan |
| Vote reminder | Email | 24h before deadline, no vote yet |
| Vote received | Email/SSE | Someone votes (to organizer) |
| Quorum reached | Email + in-app | 60%+ yes on an event |
| Plan confirmed | Email | Final confirmation to all |
| Event reminder | SMS (optional) | 1 hour before event |
| Plan expired | Email | Plan deadline passed with no quorum |

### Email Template Structure

```
Subject: You're invited: {Plan Title}

Hi {Name},

{Organizer} is planning an event and wants to know if you're free.

📅 Suggested Events:
1. {Event 1} — {Date} at {Time}
2. {Event 2} — {Date} at {Time}  
3. {Event 3} — {Date} at {Time}

🗓 Available Times (based on everyone's calendars):
• Saturday 2:00 PM - 5:00 PM
• Sunday 1:00 PM - 4:00 PM

👥 Who's Invited: {Organizer}, {Participant 1}, {Participant 2}

Vote on your preferences:
→ {Voting Link}

This link expires on {Deadline}.
```

---

## 7. Database Schema

```sql
-- Plans (the core entity)
CREATE TABLE plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(16) UNIQUE NOT NULL,          -- NanoID for URL
    organizer_id UUID REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    admin_token VARCHAR(64) UNIQUE NOT NULL,   -- Secret admin token
    status VARCHAR(20) DEFAULT 'draft',         -- draft | voting | confirmed | cancelled | expired
    quorum_threshold FLOAT DEFAULT 0.6,         -- 60% yes to auto-confirm
    show_names BOOLEAN DEFAULT TRUE,            -- Show voter names or anonymous
    require_email BOOLEAN DEFAULT FALSE,        -- Require email to vote
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    confirmed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ                      -- Soft delete
);

-- Suggested events within a plan
CREATE TABLE plan_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID REFERENCES plans(id) ON DELETE CASCADE,
    external_id VARCHAR(255),                   -- Original event ID from Tavily
    title VARCHAR(255) NOT NULL,
    url TEXT,
    description TEXT,
    location VARCHAR(255),
    event_date DATE,
    event_time TIME,
    metadata JSONB DEFAULT '{}',
    position INT DEFAULT 0,                     -- Display order
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Suggested time slots (from calendar overlap)
CREATE TABLE plan_time_slots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID REFERENCES plans(id) ON DELETE CASCADE,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    score FLOAT DEFAULT 1.0,                    -- Ranked by preferences
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Participants (identity layer — works for anonymous voters)
CREATE TABLE plan_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID REFERENCES plans(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),          -- NULL for anonymous
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    edit_token VARCHAR(64) UNIQUE NOT NULL,     -- Unique token for editing own vote
    has_voted BOOLEAN DEFAULT FALSE,
    invited_at TIMESTAMPTZ DEFAULT NOW(),
    responded_at TIMESTAMPTZ,
    UNIQUE(plan_id, email)                      -- One entry per email per plan
);

-- Votes (yes/maybe/no per event per participant)
CREATE TABLE plan_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID REFERENCES plans(id) ON DELETE CASCADE,
    participant_id UUID REFERENCES plan_participants(id) ON DELETE CASCADE,
    event_id UUID REFERENCES plan_events(id) ON DELETE CASCADE,
    vote_type VARCHAR(10) NOT NULL,             -- yes | maybe | no
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(participant_id, event_id)            -- One vote per participant per event
);

-- Time slot preferences (optional — participants can vote on times too)
CREATE TABLE plan_slot_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID REFERENCES plans(id) ON DELETE CASCADE,
    participant_id UUID REFERENCES plan_participants(id) ON DELETE CASCADE,
    slot_id UUID REFERENCES plan_time_slots(id) ON DELETE CASCADE,
    vote_type VARCHAR(10) NOT NULL,             -- yes | maybe | no
    UNIQUE(participant_id, slot_id)
);

-- Notification log (prevent duplicate sends)
CREATE TABLE plan_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID REFERENCES plans(id) ON DELETE CASCADE,
    participant_id UUID REFERENCES plan_participants(id) ON DELETE CASCADE,
    notification_type VARCHAR(50) NOT NULL,     -- invitation | reminder | confirmed | expired
    channel VARCHAR(20) NOT NULL,               -- email | sms
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'sent',          -- sent | failed | bounced
    UNIQUE(participant_id, notification_type)   -- One invitation per person
);

-- Users (optional — for organizers who want accounts)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    preferences JSONB DEFAULT '{}',
    nylas_grant_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_plans_slug ON plans(slug);
CREATE INDEX idx_plans_status ON plans(status);
CREATE INDEX idx_plan_events_plan_id ON plan_events(plan_id);
CREATE INDEX idx_plan_participants_plan_id ON plan_participants(plan_id);
CREATE INDEX idx_plan_votes_plan_id ON plan_votes(plan_id);
CREATE INDEX idx_plan_votes_event_id ON plan_votes(event_id);
CREATE INDEX idx_plan_notifications_plan_id ON plan_notifications(plan_id);
```

---

## 8. API Endpoints

### Plans

```
POST   /api/plans                          — Create a new plan
GET    /api/plans/{slug}                   — Get plan details (public)
GET    /api/plans/{slug}/admin?token=...   — Get plan with admin access
PATCH  /api/plans/{slug}/admin?token=...   — Update plan (add events, extend deadline)
DELETE /api/plans/{slug}/admin?token=...   — Cancel plan
GET    /api/plans/{slug}/og                — Dynamic OG image
```

### Voting

```
POST   /api/plans/{slug}/votes             — Submit vote (anonymous or named)
GET    /api/plans/{slug}/votes             — Get all votes (for organizer)
PATCH  /api/plans/{slug}/votes/{id}?token=... — Update own vote
DELETE /api/plans/{slug}/votes/{id}?token=... — Remove own vote
```

### Time Slots

```
POST   /api/plans/{slug}/availability      — Compute availability for participants
GET    /api/plans/{slug}/time-slots        — Get suggested time slots
POST   /api/plans/{slug}/slot-votes       — Vote on time slot preferences
```

### Notifications

```
POST   /api/plans/{slug}/invite            — Send invitations to participants
POST   /api/plans/{slug}/remind            — Send reminder to non-responders
```

### Real-Time

```
GET    /api/plans/{slug}/stream            — SSE endpoint for live vote updates
```

---

## 9. Real-Time Updates

### Server-Sent Events (SSE)

Simpler than WebSockets, perfect for one-way updates (new votes appear):

```python
# FastAPI SSE endpoint
from fastapi.responses import StreamingResponse
import asyncio
import json

async def vote_stream(plan_id: str):
    client_id = id(asyncio.current_task())
    subscribers[plan_id].add(client_id)
    
    try:
        while True:
            message = await message_queue.get()
            if message["plan_id"] == plan_id:
                yield f"data: {json.dumps(message)}\n\n"
    except asyncio.CancelledError:
        subscribers[plan_id].discard(client_id)

@app.get("/api/plans/{slug}/stream")
async def stream_votes(slug: str):
    return StreamingResponse(
        vote_stream(slug),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
```

### Client-Side

```typescript
const eventSource = new EventSource(`/api/plans/${planId}/stream`);
eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "vote_added") {
        updateVoteGrid(data.vote);
    } else if (data.type === "quorum_reached") {
        showConfirmation(data.event);
    }
};
```

### Redis Pub/Sub for Multi-Worker

If running multiple FastAPI workers, use Redis pub/sub to broadcast:

```python
# On new vote:
await redis.publish(f"plan:{plan_id}", json.dumps({
    "type": "vote_added",
    "participant": participant.name,
    "event_id": event.id,
    "vote": vote_type,
}))

# SSE subscriber reads from Redis:
async def vote_stream(plan_id: str):
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"plan:{plan_id}")
    async for message in pubsub.listen():
        yield f"data: {message['data']}\n\n"
```

---

## 10. Cost Analysis

### Per-Plan Cost Estimate

Assuming a typical plan with 4 participants and 3 suggested events:

| Component | Cost | Notes |
|-----------|------|-------|
| **Tavily search** | 1 credit ($0.0075) | One search per plan |
| **Tavily extract** | 1 credit ($0.0075) | Extract details from 3-5 event URLs |
| **Nylas availability** | $0 | Free tier covers it |
| **Email invitations** | $0 | 4 emails on Resend free tier |
| **Email reminders** | $0 | 1-2 reminders on free tier |
| **Database** | $0 | PostgreSQL included in Docker Compose |
| **Total per plan** | **~$0.015** | Essentially free at small scale |

### Monthly Cost at Scale

| Users | Plans/Mo | Tavily | Email | Total |
|-------|----------|--------|-------|-------|
| 100 | 200 | $1.50 | $0 (free tier) | **$1.50** |
| 1,000 | 2,000 | $15 | $0 (free tier) | **$15** |
| 5,000 | 10,000 | $75 | $20 (Resend) | **$95** |
| 10,000 | 20,000 | $150 | $40 (Resend) | **$190** |

### SMS Optional Add-On

If adding SMS reminders at scale:
- 10,000 users × 0.5 SMS/user/month × $0.008 = **$40/month**
- Only worth it for time-critical reminders, not primary invitations

---

## 11. Implementation Phases

### Phase 1: Database + Plan CRUD (Week 1)
- [ ] Add PostgreSQL schema (plans, plan_events, plan_participants, plan_votes)
- [ ] SQLAlchemy/SQLModel models
- [ ] Alembic migrations
- [ ] Plan CRUD API endpoints
- [ ] NanoID-based slug generation + admin token generation
- [ ] Basic plan creation flow in Tauri frontend

### Phase 2: Calendar Overlap Engine (Week 1-2)
- [ ] Implement sweep-line merge algorithm
- [ ] Nylas multi-participant availability fetch
- [ ] Timezone normalization (UTC everywhere)
- [ ] Slot scoring and ranking
- [ ] Progressive search window (3d → 7d → 14d)
- [ ] Redis caching layer for availability
- [ ] `POST /api/plans/{slug}/availability` endpoint

### Phase 3: Voting System (Week 2-3)
- [ ] Vote submission API (anonymous, email-based identity)
- [ ] Vote update/delete with participant token
- [ ] Quorum checking logic
- [ ] Vote aggregation and display
- [ ] Voting page in Tauri frontend (or web view)
- [ ] Dynamic OG meta tags per plan

### Phase 4: Email Notifications (Week 3)
- [ ] Resend integration
- [ ] Email template system (React emails or Jinja2)
- [ ] Invitation sending on plan creation
- [ ] Reminder logic (24h before deadline)
- [ ] Confirmation emails on quorum reached
- [ ] Notification log to prevent duplicates

### Phase 5: Real-Time Updates (Week 3-4)
- [ ] SSE endpoint for live vote streaming
- [ ] Redis pub/sub for multi-worker support
- [ ] Frontend SSE client with reconnection
- [ ] Live vote grid updates

### Phase 6: Polish (Week 4)
- [ ] Plan expiration and cleanup (pg_cron job)
- [ ] Plan cancellation flow
- [ ] Error handling and edge cases
- [ ] Integration tests for full voting flow
- [ ] Performance testing with 10+ participants

---

## Tradeoffs & Decisions

### Email vs SMS for Invitations
**Decision: Email primary, SMS optional.**
- Email is 10-80x cheaper
- Resend free tier covers 3,000 emails/month
- SMS requires A2P 10DLC registration ($27+ one-time, compliance overhead)
- SMS open rate is higher (98% vs 20-30%) but for friend-group planning, email is sufficient
- SMS can be added later for urgent reminders

### Anonymous vs Account-Based Voting
**Decision: Anonymous with email identity.**
- No account creation required for participants — reduces friction dramatically
- Email deduplication via upsert on (plan_id, email)
- Organizer can optionally require accounts later
- Bridges to authenticated model via nullable `user_id` on participants

### SSE vs WebSockets vs Polling
**Decision: SSE primary, polling fallback.**
- SSE is simpler (unidirectional, HTTP-based, no special server config)
- Polling every 15-30 seconds is acceptable fallback
- WebSockets are overkill for vote updates
- Redis pub/sub handles multi-worker broadcasting

### Self-Hosted vs Managed
**Decision: Self-hosted via Docker Compose.**
- PostgreSQL and Redis run in Docker Compose alongside the API
- Resend is managed (email delivery is hard to self-host reliably)
- No need for Kubernetes or complex orchestration at this scale
- Can scale to ~10K users on a single $20-40/mo VPS
