# EventFinder AI

Autonomous event planning with friends. Discover what's happening, check everyone's availability, vote on options, and confirm — all in one flow.

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.10+ (for local dev)
- Node.js & Rust (for Tauri frontend)

### Option 1: Docker Compose (Recommended)

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# 2. Start all backend services
make up

# 3. Verify API is running
curl http://localhost:8000/health
# Swagger docs: http://localhost:8000/docs

# 4. Run Tauri frontend (separate terminal)
cd tauri_frontend/event_agent_frontend
npm install && npm run tauri dev
```

### Option 2: Local Development

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then edit with your keys
uvicorn src.api:app --reload
```

### Hot Reload

```bash
make dev
# Changes to src/ sync automatically without container restarts
```

## Configuration

```bash
cp .env.example .env
```

| Variable | Purpose | Get It |
|----------|---------|--------|
| `TAVILY_API_KEY` | Web search & event discovery | [tavily.com](https://tavily.com) |
| `OPENAI_API_KEY` | LLM (parser, auditor) | [platform.openai.com](https://platform.openai.com) |
| `NYLAS_API_KEY` | Calendar integration | [nylas.com](https://nylas.com) |
| `NYLAS_GRANT_ID` | Calendar access grant | Nylas dashboard |
| `NYLAS_API_URI` | Nylas API endpoint | Nylas dashboard |
| `OPENROUTE_SERVICE_API_KEY` | Travel time calculation | [openrouteservice.org](https://openrouteservice.org) |

## Makefile Commands

```bash
make up           # Start all services
make down         # Stop all services
make logs         # Follow API logs
make shell        # Open shell in API container
make test         # Run test suite (115 tests)
make test-cov     # Run with coverage
make test-unit    # Unit tests only
make test-int     # Integration tests only
make lint         # Run linter
make lint-fix     # Auto-fix lint issues
make format       # Format code with black
make dev          # Start with hot-reload watch mode
make clean        # Stop and remove all volumes
```

## API Endpoints

### Core Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/search` | Search for free events |
| `POST` | `/verify` | Verify if an event is truly free |
| `POST` | `/transcribe` | Transcribe uploaded audio |
| `GET` | `/health` | Health check |

### Group Planning

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/plans` | Create a new plan |
| `GET` | `/api/plans/{slug}` | Get plan details (public) |
| `PATCH` | `/api/plans/{slug}/admin` | Update plan (admin token required) |
| `DELETE` | `/api/plans/{slug}/admin` | Cancel plan |
| `POST` | `/api/plans/{slug}/votes` | Submit vote |
| `GET` | `/api/plans/{slug}/stream` | SSE stream for live updates |
| `POST` | `/api/plans/{slug}/availability` | Compute group availability |
| `POST` | `/api/plans/{slug}/invite` | Send email invitations |

## How It Works

### The Agentic Loop

1. **Intent Parsing** — LLM extracts structured search intent from voice or text
2. **Availability Check** — Nylas scans all participants' calendars for overlapping free time
3. **Event Discovery** — Tavily AI searches event platforms with domain targeting and date filtering
4. **Verification** — LLM-powered auditor confirms events are truly free, flags hidden costs
5. **Relaxation** — If zero results, automatically broadens parameters and retries

### Group Planning Flow

1. **Search** — Find events via voice or text
2. **Create Plan** — Select events, add friends, pick time slots (auto-calculated from calendars)
3. **Share Link** — System generates a shareable voting link
4. **Vote** — Friends open the link, swipe yes/maybe/no on each event card
5. **Confirm** — When quorum is reached (60%+ yes), the plan is confirmed and everyone is notified

### Live Sync

Availability recalculates continuously as participants' calendars change. The voting page shows live activity as friends vote. Plans auto-expire after 7 days.

## Running Tests

```bash
pytest                    # All 115 tests
pytest --cov=src tests/   # With coverage
pytest tests/integration/ # Integration tests only
pytest tests/unit/        # Unit tests only
make test                 # Inside Docker
```

## Architecture

```
┌─────────────────────────────────────────────┐
│           Tauri Frontend (Native)           │
│  Search · Plans · Voting · Calendar         │
└─────────────────────┬───────────────────────┘
                      │ HTTP + SSE
┌─────────────────────▼───────────────────────┐
│          Docker Compose Services            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  FastAPI │  │PostgreSQL│  │  Redis   │  │
│  │  :8000   │  │  :5432   │  │  :6379   │  │
│  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────┬───────────────────────┘
                      │
              ┌───────┴───────┐
              │  External APIs │
              │  Tavily · Nylas│
              │  OpenRoute     │
              └───────────────┘
```

### Technology Stack

| Component | Technology |
|-----------|-----------|
| **Orchestration** | LangGraph |
| **Frontend** | Tauri, React, TypeScript |
| **Backend** | FastAPI, Python 3.11 |
| **Web Search** | Tavily AI (primary), Brave (fallback) |
| **LLM** | OpenAI GPT-4o-mini |
| **Calendars** | Nylas (Google, Outlook, iCloud) |
| **Maps/Travel** | OpenRouteService |
| **Database** | PostgreSQL |
| **Cache/Real-time** | Redis (SSE pub/sub, availability cache) |
| **Email** | Resend |
| **Testing** | Pytest (115 tests) |

## Edge Case Handling

| Failure | Response |
|---------|----------|
| **Zero Results** | Expand radius or broaden categories |
| **Schedule Conflict** | Accept drop-in events with grace period |
| **Hidden Costs** | LLM auditor flags and excludes |
| **API Timeout** | Failover to secondary provider |
| **Calendar Changed** | Auto-recalculate availability, notify group |

## Project Structure

```
event_searcher/
├── src/
│   ├── api.py                          # FastAPI application
│   ├── deps.py                         # Dependency injection
│   ├── input_parser/parser.py          # LLM + rule-based intent parsing
│   ├── discovery_agent/
│   │   ├── searcher.py                 # Event discovery via Tavily
│   │   ├── graph.py                    # LangGraph pipeline
│   │   ├── query_formatter.py          # Search query optimization
│   │   └── providers/
│   │       ├── base.py                 # Provider interface
│   │       ├── tavily.py               # Tavily (primary)
│   │       └── brave.py                # Brave (fallback)
│   ├── calendar_agent/scheduler.py     # Calendar + travel time
│   ├── auditor/verifier.py             # LLM-powered free event check
│   ├── resilience/edge_case_handler.py # Relaxation strategies
│   ├── orchestration/manager.py        # 5-step workflow
│   ├── services/
│   │   ├── calendar_service.py         # Nylas integration
│   │   └── routes_service.py           # OpenRouteService
│   ├── models/schemas.py               # Pydantic models
│   ├── location/                       # Geocoding + country normalization
│   └── transcription/transcriber.py    # Whisper STT
├── tauri_frontend/                     # Desktop app (runs natively)
├── tests/
│   ├── unit/                           # 80+ unit tests
│   └── integration/                    # 35+ integration tests
├── docker-compose.yml                  # API + PostgreSQL + Redis
├── Dockerfile.prod                     # Multi-stage production build
├── Dockerfile.dev                      # Dev with hot-reload
├── Makefile                            # One-command workflows
└── .opencode/plans/                    # Design docs & prototypes
    ├── improvements.md                 # Full refactor & release plan
    ├── group-planning-design.md        # Group planning architecture
    └── prototype.html                  # Interactive UI prototype
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/name`)
3. Commit changes
4. Push and open a Pull Request

## License

MIT
