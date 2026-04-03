# EventFinder AI — Implementation Kickoff

> This document aligns the team (human + agents) on architecture decisions, coding conventions, implementation order, and the full scope of work. Read this before writing any code.

---

## 1. Architecture Summary

### Stack
| Layer | Technology | Hosting |
|---|---|---|
| Frontend | Next.js 15 (App Router) | Cloudflare Pages |
| API Layer | TypeScript + Hono | Cloudflare Workers |
| Auth | Clerk (Hobby tier → Pro at 50K MRU) | Clerk-hosted |
| Database | D1 (SQLite) | Cloudflare edge |
| Storage | R2 (S3-compatible, zero egress) | Cloudflare edge |
| Sessions/Cache | KV | Cloudflare edge |
| Real-Time | Durable Objects + WebSockets | Cloudflare edge |
| Async Jobs | Cloudflare Queues + DLQ | Cloudflare edge |
| Agent Pipeline | Python FastAPI + LangGraph | Coolify VPS (Hetzner €4.49/mo) |
| Transcription | `faster-whisper` (local) | Coolify VPS |
| Email | Resend (3K free/mo) | Resend API |
| Error Tracking | Sentry (frontend), D1 error log (backend) | Sentry + D1 |

### Data Flow
```
User (Web/Tauri)
  → Cloudflare Pages (Next.js SSR)
    → Cloudflare Workers (Hono API + Clerk auth)
      → R2 (audio storage)
      → Cloudflare Queues (async job processing)
        → Queue Consumer Worker → Coolify VPS (FastAPI + LangGraph + Whisper)
      → D1 (persistent data)
      → Durable Objects (real-time voting via WebSocket)
      → KV (sessions, cache)
```

### Key Design Principles
1. **API-first**: All features exposed via REST/WebSocket. Both web and Tauri use the same API.
2. **Swappable modules**: The agent pipeline adapter is a single module. Swapping Coolify → Cloudflare Python Worker → any other backend is one URL change.
3. **Async by default**: Transcription and search are queued. Users get job IDs and poll or receive real-time updates.
4. **Edge-native where possible**: Auth, routing, storage, cache, real-time — all on Cloudflare's edge.
5. **Heavy compute isolated**: LangGraph, Whisper, Tavily calls run on the VPS behind a queue. The VPS never gets overwhelmed.

---

## 2. Decisions Made

| Decision | Choice | Rationale |
|---|---|---|
| Agent Pipeline | Coolify VPS | Zero code changes, full Python, `faster-whisper` works. Cloudflare Python Workers can't run C++ extensions |
| Transcription | `faster-whisper` on VPS | Free, best quality, works with Coolify. Queue protects VPS from overload |
| Email | Resend | Best DX, 3K free/mo, React Email. Cloudflare Email Routing can't send transactional emails |
| v1 Scope | Standard (auth + search + groups + voting) | Group voting is the differentiator. Without it, it's just a voice search engine |
| Tauri Desktop | Thin companion app | ~200 lines Rust. Native audio + global shortcut, minimal maintenance |
| Observability | Standard (Sentry + D1 error log) | Essential error tracking. Grafana can wait until real traffic |
| Real-Time | Durable Objects + WebSockets | Native to Cloudflare, scales automatically, WebSocket hibernation |
| Async Jobs | Cloudflare Queues + DLQ | Backpressure, retries, dead-letter handling, controlled throughput |

---

## 3. Clerk — Auth + Future Billing

### Auth (v1 — Required)
- **Plan**: Hobby (free, 50K MRU)
- **Features**: Social login (Google, GitHub), email codes, email links, magic links
- **Integration**: `clerkMiddleware()` in Next.js, Clerk JWT verification in Workers
- **Webhooks**: `user.created`, `user.updated`, `user.deleted` → sync to D1 `users` table
- **Session**: Fixed 7-day lifetime on Hobby plan

### Billing (Future — Not v1)
- **Status**: Clerk Billing is currently in Beta
- **How it works**: Clerk handles Stripe integration. You pay 0.7% of billing volume + Stripe's 2.9% + $0.30 per transaction
- **Features**: Subscription management, usage-based billing, billing-aware authorization, prebuilt pricing page components
- **Webhooks**: `subscriptionItem.active`, `subscriptionItem.pastDue`, `paymentAttempt.updated`
- **When to add**: When you're ready to monetize (premium features, higher usage tiers, team plans)
- **Architecture note**: Billing will be a separate module that plugs into the existing Clerk webhook handler. No structural changes needed.

---

## 3. AI Agent Skills Setup

Before coding begins, install these skills to give agents specialized knowledge:

### Installation (run once)
```bash
npx skills add clerk/skills && \
npx skills add shadcn-ui/ui && \
npx skills add vercel-labs/agent-skills
```

### What Each Skill Provides

| Skill | Source | What It Does |
|---|---|---|
| `/clerk-setup` | clerk/skills | Add Clerk auth to Next.js correctly |
| `/clerk-custom-ui` | clerk/skills | Custom sign-in forms with proper styling |
| `/clerk-nextjs-patterns` | clerk/skills | Server Actions, middleware, caching patterns |
| `/clerk-webhooks` | clerk/skills | Webhook handling, D1 user sync |
| `/clerk-orgs` | clerk/skills | Multi-tenant B2B organizations (future) |
| `/clerk-backend-api` | clerk/skills | Clerk Backend REST API explorer |
| `/clerk-testing` | clerk/skills | E2E testing for auth flows |
| `shadcn` | shadcn-ui/ui | Proper shadcn component usage, CLI commands, theming |
| `react-best-practices` | vercel-labs/agent-skills | 40+ rules: waterfalls, bundle size, SSR, re-renders |
| `web-design-guidelines` | vercel-labs/agent-skills | 100+ rules: accessibility, performance, UX |
| `composition-patterns` | vercel-labs/agent-skills | React composition patterns that scale |

**Why these matter:** Without skills, agents guess at Clerk APIs, invent shadcn props, and miss React performance patterns. With skills, agents follow official best practices automatically.

---

## 4. Coding Conventions

### TypeScript (Workers + Frontend)
- **Framework**: Hono for Workers, Next.js App Router for frontend
- **Type safety**: Strict mode, no `any`, explicit return types on all functions
- **Error handling**: Never swallow errors. All errors logged with context. User-facing errors return structured JSON with `error` field
- **Validation**: Zod for all request/response validation at API boundaries
- **Imports**: Absolute imports from `@/` alias. Group imports: external → internal → relative
- **Naming**: `camelCase` for variables/functions, `PascalCase` for components/types, `UPPER_SNAKE_CASE` for constants
- **Comments**: JSDoc on public functions. No inline comments explaining obvious code
- **File structure**: One export per file. Co-locate related files (routes, middleware, services)

### Python (Agent Pipeline — Coolify)
- **Framework**: FastAPI (existing codebase)
- **Type hints**: All function signatures typed. Use Pydantic v2 models
- **Error handling**: FastAPI exception handlers for all expected error types
- **Logging**: `structlog` for structured JSON logs. Include request ID, user ID, duration
- **Dependencies**: Pin versions in `requirements.txt`. No unpinned dependencies

### Database (D1)
- **Migrations**: Version-controlled SQL files in `infra/d1/migrations/`. Apply with `wrangler d1 migrations apply`
- **Naming**: `snake_case` for tables/columns. Plural table names (`users`, `events`, `votes`)
- **Foreign keys**: Always `ON DELETE CASCADE` unless there's a business reason to preserve orphaned records
- **Indexes**: Create indexes on all foreign keys and frequently queried columns
- **JSON columns**: Store as TEXT, use `JSON_EXTRACT()` for queries. Document the expected JSON shape

### API Design
- **Versioning**: No version prefix for v1. Add `/v1/` when breaking changes are needed
- **Response format**: Consistent JSON shape — `{ data: ..., error: null }` on success, `{ data: null, error: { code, message } }` on failure
- **Status codes**: 200 (success), 201 (created), 202 (accepted/queued), 400 (bad request), 401 (unauthorized), 404 (not found), 429 (rate limited), 500 (server error)
- **Rate limiting**: Cloudflare's built-in rate limiting + KV-based per-user counters

### Testing
- **Workers**: Vitest with `@cloudflare/vitest-pool-workers`
- **Frontend**: Jest + React Testing Library
- **Agent Pipeline**: Existing pytest suite (115 tests passing)
- **Integration tests**: Test the full flow — Worker → Queue → Coolify → D1

---

## 5. Implementation Order

### Phase 0: Infrastructure Setup (Week 1)
**Goal**: All infrastructure provisioned, CI/CD working

1. Cloudflare account + domain + DNS
2. Clerk application (Hobby tier) + webhook configuration
3. D1 database + initial migrations
4. R2 bucket + CORS configuration
5. KV namespace
6. Cloudflare Queues (`transcription-queue`, `transcription-dlq`)
7. Coolify on Hetzner VPS
8. Deploy existing FastAPI to Coolify
9. GitHub Actions: lint → test → deploy Workers + Pages
10. `wrangler.toml` with all bindings

### Phase 1: Auth + Basic API (Week 2)
**Goal**: Users can sign up, sign in, and the API is protected

1. Clerk webhook Worker → D1 user sync
2. Clerk JWT verification middleware (Hono)
3. Basic user CRUD endpoints
4. Next.js frontend deployed to Cloudflare Pages
5. Clerk auth UI (sign-in, sign-up, profile)
6. Point Tauri desktop app at new API, verify auth flow

### Phase 2: Event Discovery (Weeks 3-4)
**Goal**: Full event search + transcription pipeline working

1. R2 presigned URL generation
2. Cloudflare Queues consumer Worker (transcription)
3. DLQ consumer Worker (failed jobs)
4. `/api/transcribe` endpoint (upload → R2 → enqueue → 202)
5. `/api/jobs/:id/status` polling endpoint
6. Durable Object notification for job completion
7. `/api/search` endpoint (Workers → Coolify → Tavily → response)
8. Web Audio API waveform visualization
9. Browser MediaRecorder recording component
10. KV caching for repeated searches

### Phase 3: Group Planning (Weeks 5-7)
**Goal**: Shareable plans, voting, calendar overlap

1. Groups CRUD (D1)
2. Shareable link pattern (public + admin tokens)
3. Durable Object for voting state + WebSocket
4. Sweep-line calendar overlap algorithm
5. Nylas calendar sync endpoint
6. SSE fallback for groups without WebSocket
7. Email notifications (Resend)

### Phase 4: Polish (Weeks 8+)
**Goal**: Production-ready

1. Sentry integration (frontend)
2. D1 error log (backend)
3. Cloudflare Analytics + Grafana dashboards
4. Tauri thin companion app
5. Load testing at 10K DAU
6. Cost optimization pass

---

## 6. Module Boundaries

Each module is isolated and can be developed/tested independently.

```
┌─────────────────────────────────────────────────────────────┐
│                     MODULE BOUNDARIES                        │
│                                                              │
│  [web/]              Next.js frontend                        │
│    ├── app/          Pages, layouts, Server Actions          │
│    ├── components/   React components                        │
│    └── lib/          API client, agent adapter, DO client    │
│                                                              │
│  [workers/api/]      Main API Worker (Hono)                  │
│    ├── routes/       Endpoint handlers                       │
│    ├── middleware/   Auth, rate limiting, validation         │
│    └── services/     Agent pipeline adapter (swappable)      │
│                                                              │
│  [workers/transcription-consumer/]  Queue Consumer           │
│    └── Pulls from queue → Coolify → D1                      │
│                                                              │
│  [workers/dlq-consumer/]  Dead Letter Queue Consumer         │
│    └── Logs failures to D1, notifies users                  │
│                                                              │
│  [workers/clerk-webhook/]  Clerk Webhook Handler             │
│    └── Syncs Clerk user events → D1                         │
│                                                              │
│  [workers/durable-objects/]  Real-Time State                 │
│    └── VotingCoordinator per group                          │
│                                                              │
│  [agent/]            FastAPI agent pipeline (Coolify)        │
│    └── Existing codebase, zero changes                      │
│                                                              │
│  [infra/]            Infrastructure as code                  │
│    ├── d1/migrations/  SQL migrations                       │
│    └── r2/            CORS config                           │
└─────────────────────────────────────────────────────────────┘
```

**Communication between modules:**
- `web/` → `workers/api/` via HTTP (same domain, no CORS)
- `workers/api/` → `agent/` via HTTP (AgentService adapter)
- `workers/api/` → Queues via Cloudflare binding
- `workers/transcription-consumer/` → `agent/` via HTTP
- `workers/transcription-consumer/` → D1 via Cloudflare binding
- `workers/clerk-webhook/` → D1 via Cloudflare binding
- `workers/durable-objects/` → D1 via Cloudflare binding

---

## 7. Skills & Agent Guidelines

### Installed Skills (Section 3)
The following skills should be installed before coding begins:
- **Clerk** (`clerk/skills`) - Auth setup, webhooks, Next.js patterns, orgs
- **shadcn** (`shadcn-ui/ui`) - Component usage, CLI, theming
- **Vercel Agent Skills** (`vercel-labs/agent-skills`) - React best practices, web design guidelines, composition patterns

### Agent Guidelines
- **Always read existing code** before writing new code. Match the patterns.
- **Never commit** unless explicitly asked.
- **Run tests** after any code change. If tests fail, fix them before proceeding.
- **One change at a time**. Don't batch multiple unrelated changes into one commit.
- **Ask before making architectural decisions**. If the plan doesn't cover a scenario, ask.
- **Error handling is not optional**. Every API endpoint must handle errors gracefully.
- **Type safety is not optional**. No `any`, no missing return types.
- **Use installed skills** — agents should reference skill documentation when implementing Clerk, shadcn, or React patterns.

---

## 8. Environment Variables

### Cloudflare Workers (`wrangler.toml` / `.dev.vars`)
```
CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
CLERK_JWT_VERIFICATION_KEY=-----BEGIN PUBLIC KEY-----...
AGENT_SECRET=shared-secret-for-coolify-communication
COOLIFY_URL=https://api.your-coolify-instance.com
SENTRY_DSN=https://...@sentry.io/...
RESEND_API_KEY=re_...
```

### Coolify VPS (`.env`)
```
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
NYLAS_API_KEY=nylas-...
OPENROUTESERVICE_API_KEY=...
AGENT_SECRET=shared-secret-for-coolify-communication
WHISPER_MODEL_SIZE=medium  # or large-v3
```

### Next.js Frontend (`.env.local`)
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
NEXT_PUBLIC_API_URL=https://api.eventfinder.ai
SENTRY_DSN=https://...@sentry.io/...
```

---

## 9. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Coolify VPS goes down | Low | High | Health checks, auto-restart, manual failover to backup VPS |
| Cloudflare Python Workers mature enough to replace Coolify | Medium | Low | Swappable adapter makes this easy |
| D1 write limits exceeded at scale | Low | Medium | Cache writes in KV, batch writes, upgrade to paid tier |
| Queue backlog grows too large | Low | Medium | Monitor queue depth, scale VPS or add second consumer |
| Clerk pricing changes | Low | Low | Auth is commodity. Migration to alternatives is painful but possible |
| `faster-whisper` RAM usage exceeds VPS capacity | Medium | Medium | Use `medium` model instead of `large-v3`, or scale VPS |
| Resend deliverability issues | Low | Low | Fallback to SendGrid if needed |

---

## 10. Definition of Done

A feature is "done" when:
- [ ] Code is written and follows conventions in Section 4
- [ ] Tests pass (existing + new tests for new code)
- [ ] Error handling covers all expected failure modes
- [ ] API responses follow the standard format (`{ data, error }`)
- [ ] TypeScript strict mode passes (no `any`, no implicit `any`)
- [ ] D1 migrations are version-controlled and reversible
- [ ] Environment variables are documented in `.env.example`
- [ ] The feature works on both web and Tauri (if applicable)
- [ ] Observability: errors are logged, metrics are tracked

---

## 11. What I Need From You Before Coding

### A. Accounts & API Keys (Required — Blockers)

| Service | What I Need | Where to Get It | Priority |
|---|---|---|---|
| **Cloudflare** | Account created, domain added | cloudflare.com → Sign up → Add Site | BLOCKER |
| **Clerk** | Application created, API keys | dashboard.clerk.com → Create App → API Keys | BLOCKER |
| **OpenAI** | API key | platform.openai.com → API Keys | BLOCKER |
| **Tavily** | API key | app.tavily.com → API Keys | BLOCKER |
| **Nylas** | API key + configured app | dashboard.nylas.com → API Keys | BLOCKER |
| **OpenRouteService** | API key | openrouteservice.org → Sign up → API Keys | BLOCKER |
| **Resend** | API key (or decide later) | resend.com → API Keys | Phase 3 |
| **Sentry** | DSN (or decide later) | sentry.io → Create Project → Client Keys | Phase 4 |
| **Hetzner** | VPS provisioned (or decide provider) | hetzner.com → Cloud → Create Server | Phase 0 |

### B. Decisions (Required — Blockers)

| Decision | Options | My Recommendation | Your Choice |
|---|---|---|---|
| **Domain name** | Your existing domain or new one | Whatever domain you own/prefer | ? |
| **Clerk social providers** | Google, GitHub, Apple, Microsoft | Google + GitHub minimum | ? |
| **VPS region** | Hetzner EU (€4.49), US providers (~$10+) | Hetzner EU if latency is acceptable | ? |
| **Whisper model size** | `medium` (~1GB RAM), `large-v3` (~2-3GB RAM) | `medium` on 4GB VPS, `large-v3` on 8GB | ? |
| **v1 scope** | Minimum, Standard, Full | Standard (auth + search + groups + voting) | ? |
| **Tauri companion** | Build in Phase 4, defer, or archive | Thin companion in Phase 4 | ? |

### C. Nice to Have (Can Decide Later)

| Item | Why It Matters | When Needed |
|---|---|---|
| **Monetization timeline** | Affects whether we add `subscription_status` to users table now | Phase 4+ |
| **Nylas calendar providers** | Google, Outlook, iCloud support | Phase 3 |
| **Group size limits** | Max members per group (affects Durable Object memory) | Phase 3 |
| **Notification email templates** | What should invite/reminder emails say? | Phase 3 |
| **Brand colors/theme** | For shadcn theme customization | Phase 1 |

### D. Pre-Coding Checklist

Run these commands before we start:

```bash
# 1. Install AI agent skills
npx skills add clerk/skills
npx skills add shadcn-ui/ui
npx skills add vercel-labs/agent-skills

# 2. Verify existing codebase is clean
git status
# Should show clean working tree (or only untracked files we expect)

# 3. Verify existing tests pass
# (We'll run this once the environment is set up)
```

---

## 12. Open Questions

These can be answered during implementation:

1. **Monetization timeline**: When do we want to add Clerk Billing? (affects data model — should we add `subscription_status` to users table now?)
2. **Nylas calendar scope**: Which calendar providers? (Google, Outlook, iCloud?)
3. **Group size limits**: Max members per group? (affects Durable Object memory)
4. **Notification email templates**: What should invite/reminder/finalization emails say?
5. **Brand/theme preferences**: Colors, fonts, dark mode defaults for shadcn theme?

---

*Document created: March 2026. Review before starting implementation.*
