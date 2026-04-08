# EventFinder AI

Autonomous event planning with friends. Discover what's happening, check everyone's availability, vote on options, and confirm — all in one flow.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                  │
│  [Web Browser (Next.js)] ──HTTPS──► Cloudflare CDN (Pages)      │
│  [Tauri Desktop (optional)] ──HTTP──► same API                  │
└─────────────────────┬────────────────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────────────────┐
│                  CLOUDFLARE EDGE (Workers)                        │
│  ┌────────────┐  ┌─────────────┐  ┌──────────────────────┐      │
│  │ Clerk Auth │  │ Hono API    │  │ Durable Objects      │     │
│  │ JWT verify │  │ /search     │  │ (Voting WebSocket)   │     │
│  │ Rate limit │  │ /transcribe │  │ per-group state      │     │
│  └────────────┘  │ /groups     │  └──────────────────────┘      │
│                  │ /votes      │  ┌──────────────────────┐       │
│                  └──────┬──────┘  │ D1 (SQLite)          │      │
│                         │         │ R2 (audio storage)   │      │
│                         │         │ KV (sessions/cache)  │      │
│                         │         │ Queues (async jobs)  │      │
│                         │         └──────────────────────┘       │
└─────────────────────────┬────────────────────────────────────────┘
                          │ Queue Consumer → HTTP
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│              COOLIFY VPS (FastAPI Agent Pipeline)                 │
│  LangGraph · Tavily · Nylas · faster-whisper · Auditor          │
└─────────────────────┬────────────────────────────────────────────┘
                      │
              ┌───────┴───────┐
              │ External APIs  │
              │ Tavily · OpenAI│
              │ Nylas · Resend │
              └────────────────┘
```

### Technology Stack

| Layer | Technology | Hosting |
|---|---|---|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind v4, shadcn/ui | Cloudflare Pages |
| **Auth** | Clerk (Hobby → Pro at 50K MRU) | Clerk-hosted |
| **API Layer** | TypeScript + Hono | Cloudflare Workers |
| **Database** | D1 (SQLite) | Cloudflare edge |
| **Storage** | R2 (S3-compatible, zero egress) | Cloudflare edge |
| **Sessions/Cache** | KV | Cloudflare edge |
| **Real-Time** | Durable Objects + WebSockets | Cloudflare edge |
| **Async Jobs** | Cloudflare Queues + Dead Letter Queues | Cloudflare edge |
| **Agent Pipeline** | Python FastAPI + LangGraph + faster-whisper | Coolify VPS |
| **Email** | Resend (3K free/mo) | Resend API |
| **Error Tracking** | Sentry (frontend), D1 error log (backend) | Sentry + D1 |

## Quick Start

### Prerequisites

- Node.js 20+
- Docker & Docker Compose (for local backend dev)
- Python 3.10+ (for local backend dev)

### Option 1: Web Frontend (Recommended)

```bash
# 1. Install dependencies
cd web && npm install

# 2. Configure environment
cp .env.local.example .env.local
# Edit .env.local with your Clerk keys and API URL

# 3. Start development server
npm run dev
# Open http://localhost:3000
```

### Option 2: Backend Agent Pipeline (Local)

```bash
# 1. Set up Python environment
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Start FastAPI server
uvicorn src.api:app --reload
# Open http://localhost:8000/docs for API docs
```

### Option 3: Docker Compose (Backend Only)

```bash
# Start all backend services
make up

# Verify API is running
curl http://localhost:8000/health
```

## Configuration

### Frontend (`web/.env.local`)

| Variable | Purpose | Get It |
|---|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk auth (public) | [dashboard.clerk.com](https://dashboard.clerk.com) |
| `CLERK_SECRET_KEY` | Clerk auth (server) | Clerk dashboard → API Keys |
| `NEXT_PUBLIC_API_URL` | Backend API URL | Your Coolify VPS URL |
| `NEXT_PUBLIC_SENTRY_DSN` | Error tracking | [sentry.io](https://sentry.io) |

### Backend (`.env`)

| Variable | Purpose | Get It |
|---|---|---|
| `TAVILY_API_KEY` | Web search & event discovery | [tavily.com](https://tavily.com) |
| `OPENAI_API_KEY` | LLM (parser, auditor) | [platform.openai.com](https://platform.openai.com) |
| `NYLAS_API_KEY` | Calendar integration | [nylas.com](https://nylas.com) |
| `OPENROUTE_SERVICE_API_KEY` | Travel time calculation | [openrouteservice.org](https://openrouteservice.org) |

## Makefile Commands

```bash
make up           # Start backend services (Docker)
make down         # Stop all services
make logs         # Follow API logs
make shell        # Open shell in API container
make test         # Run test suite (115 tests)
make test-cov     # Run with coverage
make lint         # Run linter
make lint-fix     # Auto-fix lint issues
make format       # Format code with black
make dev          # Start with hot-reload watch mode
make clean        # Stop and remove all volumes
```

## How It Works

### The Agentic Loop

1. **Intent Parsing** — LLM extracts structured search intent from voice or text
2. **Availability Check** — Nylas scans all participants' calendars for overlapping free time
3. **Event Discovery** — Tavily AI searches event platforms with domain targeting and date filtering
4. **Verification** — LLM-powered auditor confirms events are truly free, flags hidden costs
5. **Relaxation** — If zero results, automatically broadens parameters and retries

### Voice → Events Flow

1. **Record** — Click "Start" or press ⌘E to record your voice (browser MediaRecorder)
2. **Transcribe** — Audio is uploaded and transcribed via faster-whisper (async, queued)
3. **Search** — The transcript is parsed for intent and used to search for free events
4. **Results** — Events are displayed with location, date, time, and price
5. **Group Vote** — Share events with friends, vote together, find the best option

### Group Planning Flow

1. **Search** — Find events via voice or text
2. **Create Plan** — Select events, add friends, pick time slots
3. **Share Link** — System generates a shareable voting link
4. **Vote** — Friends vote yes/maybe/no on each event card (real-time via WebSockets)
5. **Confirm** — When quorum is reached, the plan is confirmed and everyone is notified

## Project Structure

```
event_searcher/
├── web/                              # Next.js frontend
│   ├── src/
│   │   ├── app/                      # Next.js App Router
│   │   │   ├── layout.tsx            # Root layout + ClerkProvider
│   │   │   ├── page.tsx              # Landing page
│   │   │   ├── search/               # Voice search page
│   │   │   │   ├── page.tsx          # Server component (auth check)
│   │   │   │   └── SearchPageClient.tsx
│   │   │   ├── sign-in/              # Clerk sign-in
│   │   │   └── sign-up/              # Clerk sign-up
│   │   ├── components/
│   │   │   ├── recorder/             # Voice recording components
│   │   │   │   ├── useRecorder.ts    # Recording hook (MediaRecorder)
│   │   │   │   ├── WaveformCanvas.tsx
│   │   │   │   └── LocationPrompt.tsx
│   │   │   └── ui/                   # shadcn/ui components
│   │   ├── lib/                      # Utilities
│   │   └── middleware.ts             # Clerk auth middleware
│   ├── instrumentation.ts            # Sentry setup
│   └── package.json
│
├── src/                              # FastAPI backend (agent pipeline)
│   ├── api.py                        # FastAPI application
│   ├── input_parser/parser.py        # LLM + rule-based intent parsing
│   ├── discovery_agent/              # Event discovery via Tavily
│   ├── calendar_agent/scheduler.py   # Calendar + travel time
│   ├── auditor/verifier.py           # LLM-powered free event check
│   └── transcription/transcriber.py  # faster-whisper STT
│
├── workers/                          # Cloudflare Workers (TypeScript)
│   ├── api/                          # Main API Worker (Hono)
│   ├── transcription-consumer/       # Queue consumer for transcription
│   ├── dlq-consumer/                 # Dead letter queue handler
│   └── clerk-webhook/                # Clerk → D1 user sync
│
├── infra/                            # Infrastructure as code
│   └── d1/migrations/                # D1 SQL migrations
│
├── tauri_frontend/                   # Desktop companion app (legacy)
├── tests/                            # Python test suite (115 tests)
├── docker-compose.yml                # Backend services (dev)
├── Makefile                          # One-command workflows
└── .opencode/plans/                  # Design docs
    ├── cloudflare-self-hosted-architecture.md
    ├── implementation-kickoff.md
    ├── group-planning-design.md
    └── improvements.md
```

## Running Tests

```bash
# Backend tests
pytest                    # All 115 tests
pytest --cov=src tests/   # With coverage
make test                 # Inside Docker

# Frontend tests (coming soon)
cd web && npm test
```

## Edge Case Handling

| Failure | Response |
|---|---|
| **Zero Results** | Expand radius or broaden categories |
| **Schedule Conflict** | Accept drop-in events with grace period |
| **Hidden Costs** | LLM auditor flags and excludes |
| **API Timeout** | Failover to secondary provider |
| **Transcription Failure** | Retry with exponential backoff, then DLQ |
| **VPS Overload** | Cloudflare Queues absorb traffic spikes |
| **Calendar Changed** | Auto-recalculate availability, notify group |

## Deployment

### Frontend (Cloudflare Pages)

```bash
cd web
npx @cloudflare/next-on-pages
wrangler pages deploy .next/
```

### Backend (Coolify VPS)

Deploy via Coolify dashboard — connect GitHub repo, point at `Dockerfile.prod`, set environment variables.

### Infrastructure

All Cloudflare resources (D1, R2, KV, Queues, Workers) are managed via `wrangler.toml` and Cloudflare dashboard.

## License

MIT
