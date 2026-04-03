# EventFinder AI — Improvements & Release Plan

> Comprehensive plan for transitioning from PoC to a production-ready, containerized event planning product with friends.

---

## Table of Contents

1. [Current State Assessment](#1-current-state-assessment)
2. [Tavily API Migration](#2-tavily-api-migration)
3. [Multi-Friend Event Planning Feature](#3-multi-friend-event-planning-feature)
4. [Containerization Strategy](#4-containerization-strategy)
5. [Architecture Improvements](#5-architecture-improvements)
6. [Release Roadmap](#6-release-roadmap)
7. [Quick Wins](#7-quick-wins)

---

## 1. Current State Assessment

### What's Working Well
- **Multi-agent architecture** with LangGraph state graph is well-designed for the 5-step loop
- **Provider pattern** for search APIs (Brave + Tavily) is clean and extensible
- **LangGraph pipeline** for discovery (format → build → search) is solid
- **Resilience layer** with relaxation strategies is thoughtfully designed
- **Nylas integration** for multi-participant calendar availability is already wired up
- **Tauri frontend** provides a native-feeling desktop experience
- **Tests** exist for all major components

### Critical Issues to Fix Before Release
| Severity | Issue | File |
|----------|-------|------|
| 🔴 | Tavily provider returns raw dict, not `List[SearchResult]` — breaks Protocol contract | `providers/tavily.py` |
| 🔴 | `Config.timeout_seconds` typed as `string` instead of `int` | `providers/base.py:35` |
| 🔴 | `searcher.py:100` calls `.keys()` on what may be a list | `searcher.py` |
| 🟡 | 9 `print()` debug statements across 3 files | `searcher.py`, `manager.py`, `api.py` |
| 🟡 | Auditor LLM analysis is commented out — uses only keyword matching | `auditor/verifier.py` |
| 🟡 | Input parser extraction methods are placeholders | `input_parser/parser.py` |
| 🟡 | Calendar agent doesn't integrate with the manager workflow | `manager.py:127` |

### Bugs Already Identified in CODEBASE_AUDIT.md
All items from the audit remain valid. See `CODEBASE_AUDIT.md` §2.1 for the full list.

---

## 2. Tavily API Migration

### Why Tavily Over Brave Search

| Dimension | Tavily | Brave Search |
|-----------|--------|--------------|
| **Built for AI agents** | Yes — designed from day one for LLM workflows | General-purpose search with API added later |
| **Content extraction** | Built-in (`/extract`, `/crawl`, `/map`) | Requires separate scraping step |
| **Research agent** | Full autonomous `/research` endpoint with multi-step searching | Not available |
| **Domain targeting** | `include_domains` / `exclude_domains` (300/150) | Less granular domain control |
| **Date filtering** | `start_date`/`end_date` + `time_range` | Implicit freshness only |
| **Semantic re-ranking** | Automatic, query-context-aware | Manual via Search Goggles |
| **LLM-generated answers** | `include_answer` returns synthesized answer | Not available |
| **Agent firewall** | Blocks prompt injection in retrieved content | Not available |
| **Free tier** | 1,000 credits/month | 2,000 queries/month |
| **Async SDK** | `AsyncTavilyClient` built-in | Manual httpx async |

### Tavily Endpoints to Leverage

#### `/search` — Primary Event Discovery
```python
results = client.search(
    query="tech meetups San Francisco March 2026",
    topic="news",
    time_range="month",
    include_domains=["eventbrite.com", "meetup.com", "lu.ma", "facebook.com/events"],
    max_results=10,
    include_raw_content="markdown",  # Get cleaned event details
    country="us",
)
```

#### `/extract` — Pull Full Event Details
After finding event URLs via search, extract structured content from up to 20 URLs in one call:
```python
urls = [r.url for r in search_results[:20]]
details = client.extract(
    urls=urls[:20],
    extract_depth="advanced",  # Includes tables, embedded content
    query="event date time location price"  # Rerank for relevant chunks
)
```

#### `/research` — Autonomous Multi-Step Event Research
For complex queries like "What are the best free outdoor concerts in Austin this month?":
```python
research = client.research(
    input="Best free outdoor concerts in Austin TX this month",
    model="mini",  # 4-110 credits
    output_schema={  # Enforce structured output
        "type": "object",
        "properties": {
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "date": {"type": "string"},
                        "location": {"type": "string"},
                        "url": {"type": "string"},
                    }
                }
            }
        }
    }
)
```

#### `/map` + `/crawl` — Deep Venue Discovery
Map all event pages on a specific organizer's site, then crawl for details:
```python
# Lightweight URL discovery
sitemap = client.map(
    url="https://eventbrite.com/o/austin-tech-meetups-123456",
    instructions="Find all upcoming event pages"
)

# Deep crawl with extraction
crawl = client.crawl(
    url="https://eventbrite.com/o/austin-tech-meetups-123456",
    max_depth=2,
    limit=50,
    instructions="Extract event title, date, time, location, and price"
)
```

### Implementation Plan for Tavily Migration

#### Phase 1: Fix Tavily Provider (`providers/tavily.py`)
Current implementation is broken — it returns raw dicts instead of `SearchResult` objects. Needs:
- Normalize response to `List[SearchResult]`
- Add support for `include_raw_content`
- Add support for `include_domains` / `exclude_domains`
- Add support for `time_range` / date filtering
- Add `AsyncTavilyClient` support for async workflows

#### Phase 2: Enhance Search Query Building (`query_formatter.py`)
Current query formatter is rule-based. For Tavily, enhance with:
- Domain-specific query templates (Eventbrite, Meetup, Luma)
- Date-aware query generation
- Location-aware query building with coordinates
- Category-specific search patterns

#### Phase 3: Add Extract Pipeline
New node in the LangGraph pipeline:
```
format_query → build_query → search_web → extract_details → END
```
After search finds URLs, use `/extract` to pull structured event data.

#### Phase 4: Add Research Mode (Optional)
For complex queries, use `/research` endpoint as an alternative path in the graph:
```
format_query → route{simple? complex?} → search_web / research_web → END
```

### Tavily-Specific TavilyProvider Implementation Sketch

```python
class TavilyProvider(SearchProvider):
    def search(self, request: SearchRequest) -> List[SearchResult]:
        params = {
            "query": request.query,
            "max_results": request.count,
            "search_depth": "advanced",
            "topic": "news",
        }
        
        if request.country:
            params["country"] = request.country
        
        # Domain targeting for event platforms
        params["include_domains"] = [
            "eventbrite.com", "meetup.com", "lu.ma",
            "facebook.com", "ticketmaster.com"
        ]
        
        # Date filtering
        if request.time_window_days <= 1:
            params["time_range"] = "day"
        elif request.time_window_days <= 7:
            params["time_range"] = "week"
        else:
            params["time_range"] = "month"
        
        response = self._client.search(**params)
        
        # Normalize to SearchResult
        results = []
        for item in response.get("results", []):
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                description=item.get("content") or item.get("snippet"),
                source=self._extract_source(item.get("url")),
                published=item.get("published_date"),
            ))
        return results
    
    def extract_event_details(self, urls: List[str]) -> List[dict]:
        """Use Tavily /extract to pull structured event data."""
        response = self._client.extract(
            urls=urls[:20],  # Max 20 per call
            extract_depth="advanced",
        )
        return response.get("results", [])
```

---

## 3. Multi-Friend Event Planning Feature

### Core Capabilities Needed

#### 3.1 Multi-Participant Calendar Availability
**Current state:** Nylas `getAvailability()` is already wired up for multiple participants via `CalendarService`.

**What's missing:**
- The `CalendarAgent` takes `participants: list[str]` but the manager only passes empty list
- Need to surface overlapping free times to the event discovery step
- Need to integrate travel time calculation between calendar gaps and event locations

**Implementation:**
```python
# In manager.py _step_constraint_check:
state.calendar_gaps = self.calendar_agent.find_overlapping_free_time(
    participants=state.parsed_intent.get("participants", []),
    time_window_days=state.parsed_intent.get("time_window_days", 7),
    duration_minutes=120,  # Default event duration
)
```

#### 3.2 Group Event Voting System
**Data model:**
```python
class GroupPlan(BaseModel):
    id: str
    organizer_id: str
    title: str
    suggested_events: List[Event]
    participants: List[str]  # emails
    votes: Dict[str, Dict[str, str]]  # {email: {event_id: "yes"|"no"|"maybe"}}
    proposed_times: List[TimeSlot]
    status: str  # "draft" | "voting" | "confirmed" | "cancelled"
    created_at: datetime
    expires_at: datetime
```

**UX Pattern (recommended):**
1. Organizer searches events → picks 3-5 candidates
2. System creates a shareable plan link
3. Friends open link → vote yes/no/maybe on each event
4. Real-time updates via WebSocket/SSE
5. When quorum reached (e.g., 60% yes), event is confirmed

**Open-source reference:** [Rallly](https://github.com/lukevella/rallly) (5k+ stars) — full-featured scheduling poll app, great for UX inspiration.

#### 3.3 Shareable Plans
- Generate unique URLs: `/plan/{plan_id}`
- Magic link participation (no account needed for voters)
- Open Graph meta tags for rich previews in Slack/iMessage
- Email invitations via Resend or Nylas Email API

#### 3.4 Finding Overlapping Free Time
**Algorithm:**
1. Fetch busy blocks for each participant via Nylas FreeBusy
2. Define search window (next 7-14 days)
3. Generate candidate slots (30-min increments, 9am-9pm)
4. For each slot, check against all participants' busy ranges
5. Return slots where all (or threshold %) are free
6. Rank by number of free participants

**Nylas already handles this** via `getAvailability()` — it returns ready-to-use time slots with the intersection logic server-side.

#### 3.5 Architecture for Group Planning

```
┌─────────────────────────────────────────────────┐
│                  Tauri Frontend                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  Search  │  │  Plan    │  │  Voting Grid  │  │
│  │  View    │  │  View    │  │  (heatmap)    │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
└──────────────────────┬──────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────────┐
│                 FastAPI Backend                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  Plan    │  │  Voting  │  │  Notification │  │
│  │  Service │  │  Service │  │  Service      │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
│  ┌──────────────────────────────────────────┐    │
│  │         Existing Agent Pipeline          │    │
│  │  Parser → Calendar → Discovery → Audit  │    │
│  └──────────────────────────────────────────┘    │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              Data Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │PostgreSQL│  │  Redis   │  │    Nylas      │  │
│  │(plans,   │  │(cache,   │  │   (calendars) │  │
│  │ votes)   │  │ realtime)│  │               │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
└─────────────────────────────────────────────────┘
```

---

## 4. Containerization Strategy

### Key Finding: Tauri Should NOT Run in Docker
Tauri produces native desktop binaries (`.app`, `.exe`, `.deb`) and requires a display server. Docker containers are headless. The community consensus is clear: **Docker Compose should handle backend services only. Run Tauri natively during development.**

### Recommended Architecture

```
project/
├── docker-compose.yml              # Base (backend services)
├── docker-compose.override.yml     # Dev overrides (auto-loaded)
├── docker-compose.prod.yml         # Production overrides
├── .env.example                    # Template (committed)
├── .env                            # Local secrets (gitignored)
├── backend/
│   ├── Dockerfile                  # Multi-stage production build
│   ├── Dockerfile.dev              # Dev with hot-reload
│   └── ...
├── tauri_frontend/                 # Runs natively on host
│   └── ...
└── Makefile                        # Workflow automation
```

### Recommended docker-compose.yml

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - .:/app:cached
      - /app/venv  # Don't overwrite container venv
      - model_cache:/root/.cache  # Cache Whisper/LLM models
    env_file:
      - .env
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/eventfinder
      - REDIS_URL=redis://redis:6379/0
    command: uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
    develop:
      watch:
        - path: ./src
          action: sync
          target: /app/src
          ignore:
            - "**/__pycache__"
            - "**/*.pyc"
        - path: ./requirements.txt
          action: rebuild
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - backend

  db:
    image: postgres:16-alpine
    restart: unless-stopped
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=eventfinder
    ports:
      - "5432:5432"  # Dev only
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 10
    networks:
      - backend

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"  # Dev only
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
    networks:
      - backend

networks:
  backend:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
  model_cache:
```

### Dockerfile (Multi-Stage Production)

```dockerfile
# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Production
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

COPY . .
RUN pip install -e .

EXPOSE 8000

# Production: use gunicorn with uvicorn workers
CMD ["gunicorn", "src.api:app", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--workers", "4"]
```

### Handling Secrets

**Development:** `.env` file (gitignored) with `.env.example` template

**Production:** Docker Secrets (file-based, mounted at `/run/secrets/`):
```yaml
services:
  api:
    secrets:
      - openai_api_key
      - tavily_api_key
      - nylas_api_key
    environment:
      OPENAI_API_KEY_FILE: /run/secrets/openai_api_key
      TAVILY_API_KEY_FILE: /run/secrets/tavily_api_key

secrets:
  openai_api_key:
    file: ./secrets/openai_api_key.txt
  tavily_api_key:
    file: ./secrets/tavily_api_key.txt
```

### Makefile for Developer Experience

```makefile
.PHONY: up down logs shell test lint

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

shell:
	docker compose exec api bash

test:
	docker compose exec api pytest tests/ -v

lint:
	docker compose exec api ruff check src/

dev:
	docker compose up --watch
```

### One-Command Developer Experience

After `docker compose up -d`:
1. Backend API runs at `http://localhost:8000`
2. Swagger docs at `http://localhost:8000/docs`
3. Tauri frontend runs natively: `cd tauri_frontend/event_agent_frontend && npm run tauri dev`
4. Tauri connects to `http://localhost:8000`

---

## 5. Architecture Improvements

### 5.1 Fix the Tavily Provider (Priority #1)
**File:** `src/discovery_agent/providers/tavily.py`

The current implementation:
- Returns raw Tavily dict instead of `List[SearchResult]`
- Doesn't use any Tavily-specific features
- Doesn't pass the `SearchRequest` parameters to the API

**Fix:** See implementation sketch in [Section 2](#2-tavily-api-migration).

### 5.2 Make the Workflow Async
**File:** `src/orchestration/manager.py`

Current: All agents called synchronously on the main thread.
Problem: Web searches, LLM calls, and calendar lookups are I/O-bound but run sequentially.

**Fix:** Convert `execute_workflow()` to `async execute_workflow()` and use `asyncio.gather()` for independent steps:
```python
async def execute_workflow(self, user_input: str, user_preferences: dict = None) -> dict:
    # Steps 2-4 can potentially run in parallel for initial results
    discovery_task = self._step_discovery_async(state)
    calendar_task = self._step_constraint_check_async(state)
    
    await asyncio.gather(discovery_task, calendar_task)
    # Then verify results
    state = await self._step_verification_async(state)
```

### 5.3 Activate the LLM Auditor
**File:** `src/auditor/verifier.py`

Current: Only uses keyword matching. LLM analysis is commented out.

**Fix:** Uncomment and implement the LLM-powered verification:
```python
async def _analyze_with_llm(self, event_description: str) -> EventStatus:
    response = await self.llm_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "system",
            "content": "You are an event cost analyzer. Determine if this event is truly free."
        }, {
            "role": "user",
            "content": f"Analyze: {event_description}"
        }],
        response_format={"type": "json_object"}
    )
    return EventStatus(json.loads(response.choices[0].message.content)["status"])
```

### 5.4 Complete the Input Parser
**File:** `src/input_parser/parser.py`

Current: All extraction methods are placeholders.

**Fix:** Use an LLM to extract structured intent:
```python
def parse_input(self, user_input: str, user_preferences: dict = None) -> ParsedIntent:
    response = self.llm_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "system",
            "content": "Extract event search intent from user input. Return JSON."
        }, {
            "role": "user",
            "content": user_input
        }],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "event_intent",
                "schema": ParsedIntent.model_json_schema()
            }
        }
    )
    return ParsedIntent(**json.loads(response.choices[0].message.content))
```

### 5.5 Add PostgreSQL for Persistent State
**Why:** Group plans, votes, RSVPs, and user preferences need persistence.

**Schema:**
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE group_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizer_id UUID REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    suggested_events JSONB NOT NULL DEFAULT '[]',
    participants VARCHAR(255)[] NOT NULL DEFAULT '{}',
    votes JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE TABLE user_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID REFERENCES group_plans(id),
    external_id VARCHAR(255),
    title VARCHAR(255),
    url TEXT,
    description TEXT,
    location VARCHAR(255),
    date DATE,
    metadata JSONB DEFAULT '{}'
);
```

### 5.6 Add Redis for Caching & Real-Time
**Use cases:**
- Cache calendar availability (invalidate on webhook)
- Cache search results (TTL: 1 hour)
- WebSocket pub/sub for real-time voting updates
- Rate limiting for API calls
- Session state for LangGraph checkpoints

### 5.7 LangGraph Checkpointing
For resilience and resumability, add LangGraph checkpointing with Redis or Postgres:
```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver(connection_pool)
graph = build_search_graph(provider).compile(checkpointer=checkpointer)
```

### 5.8 API Failover Strategy
**Current:** `EdgeCaseHandler.handle_api_timeout()` returns a failover name but doesn't implement it.

**Fix:** Implement provider failover in the discovery agent:
```python
def _build_default_provider(self) -> SearchProvider:
    primary = os.environ.get("DISCOVERY_PROVIDER", "tavily")
    fallback = "brave" if primary == "tavily" else "tavily"
    
    try:
        return self._create_provider(primary)
    except Exception:
        logger.warning("Primary provider %s failed, falling back to %s", primary, fallback)
        return self._create_provider(fallback)
```

---

## 6. Release Roadmap

### Phase 1: Foundation (Week 1-2)
**Goal:** Fix all bugs, make Tavily the primary provider, clean up codebase

- [ ] Fix Tavily provider to return `List[SearchResult]`
- [ ] Fix `Config.timeout_seconds` type bug
- [ ] Remove all `print()` statements
- [ ] Activate LLM-powered auditor
- [ ] Complete input parser with LLM extraction
- [ ] Update `docker-compose.yml` with Redis + PostgreSQL
- [ ] Create multi-stage Dockerfile
- [ ] Create `.env.example` template
- [ ] Add Makefile for developer experience
- [ ] Run full test suite, fix failures

### Phase 2: Enhanced Discovery (Week 2-3)
**Goal:** Leverage full Tavily capabilities

- [ ] Add Tavily `/extract` pipeline to LangGraph
- [ ] Add domain targeting for event platforms
- [ ] Add date-aware query generation
- [ ] Implement Tavily async client support
- [ ] Add search result caching (Redis)
- [ ] Add LangGraph checkpointing

### Phase 3: Group Planning MVP (Week 3-5)
**Goal:** Basic multi-friend event planning

- [ ] Add PostgreSQL models for plans/votes
- [ ] Create `/plans` API endpoints (CRUD)
- [ ] Create `/plans/{id}/vote` endpoint
- [ ] Add shareable plan link generation
- [ ] Integrate multi-participant calendar availability into workflow
- [ ] Add WebSocket/SSE for real-time vote updates
- [ ] Update Tauri frontend with Plan View

### Phase 4: Production Readiness (Week 5-6)
**Goal:** Containerized, one-command deployment

- [ ] Finalize docker-compose.yml for production
- [ ] Add health checks to all services
- [ ] Add Docker secrets handling
- [ ] Add rate limiting (Redis token bucket)
- [ ] Add structured logging
- [ ] Add API metrics/monitoring
- [ ] Write deployment documentation
- [ ] End-to-end testing

### Phase 5: Polish & Launch (Week 6-8)
**Goal:** User-friendly release

- [ ] Frontend polish (component split, styling)
- [ ] Email invitations
- [ ] Magic link participation
- [ ] Mobile-responsive web view (for plan sharing)
- [ ] Open Graph meta tags for rich previews
- [ ] User onboarding flow
- [ ] Documentation

---

## 7. Quick Wins

These can be done in a single session and have immediate impact:

1. **Fix Tavily provider** — 30 min, unblocks Tavily migration
2. **Remove print() statements** — 10 min, cleaner logs
3. **Add `.env.example`** — 5 min, better developer onboarding
4. **Add `develop.watch` to docker-compose** — 10 min, better DX
5. **Add Makefile** — 10 min, one-command workflows
6. **Activate LLM auditor** — 30 min, much better verification
7. **Add health checks to docker-compose** — 10 min, reliable startup
8. **Fix `Config.timeout_seconds` type** — 2 min, prevents runtime crash
9. **Add CORS origin restriction** — 5 min, security improvement
10. **Add request logging middleware** — 15 min, observability

---

## Appendix A: Tavily Pricing Estimation

For a typical user session:
- 1 search query (basic): **1 credit**
- 1 extract call (5 URLs, basic): **1 credit**
- Total per session: **~2 credits**

With free tier (1,000 credits/month): **~500 user sessions/month**
With Project tier ($30/mo, 4,000 credits): **~2,000 user sessions/month**
With Bootstrap tier ($100/mo, 15,000 credits): **~7,500 user sessions/month**

## Appendix B: API Keys Required for Full Functionality

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| `TAVILY_API_KEY` | Web search & extraction | 1,000 credits/mo |
| `OPENAI_API_KEY` | LLM (parser, auditor) | $5 free credit |
| `NYLAS_API_KEY` | Calendar integration | Free tier available |
| `NYLAS_GRANT_ID` | Calendar access grant | Included with Nylas |
| `OPENROUTE_SERVICE_API_KEY` | Travel time calculation | Free tier available |

## Appendix C: References

- [Tavily Documentation](https://docs.tavily.com/)
- [Tavily Python SDK](https://github.com/tavily-ai/tavily-python)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Nylas Calendar API](https://docs.nylas.com/)
- [Docker Compose Best Practices](https://docs.docker.com/compose/)
- [Rallly (Open-source scheduling)](https://github.com/lukevella/rallly)
- [Tauri Dev Containers](https://github.com/brklntmhwk/dev-container-tauri)
