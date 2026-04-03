# EventFinder AI — Cloudflare Self-Hosted Architecture Plan

> Migrating from Tauri desktop + FastAPI + Docker Compose to Cloudflare + Clerk + modular
> compute.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Component Deep-Dives](#3-component-deep-dives)
   - [3.1 Frontend — Cloudflare Pages + Next.js](#31-frontend--cloudflare-pages--nextjs)
   - [3.2 Voice Recording — Browser MediaRecorder API](#32-voice-recording--browser-mediarecorder-api)
   - [3.3 API Layer — Cloudflare Workers (TypeScript)](#33-api-layer--cloudflare-workers-typescript)
   - [3.4 Agent Pipeline — Compute Strategy](#34-agent-pipeline--compute-strategy)
   - [3.5 Auth — Clerk](#35-auth--clerk)
   - [3.6 Database — Cloudflare D1](#36-database--cloudflare-d1)
   - [3.7 Storage — Cloudflare R2](#37-storage--cloudflare-r2)
   - [3.8 Sessions/Cache — Cloudflare KV](#38-sessionscache--cloudflare-kv)
   - [3.9 Real-Time Voting — Durable Objects + WebSockets](#39-real-time-voting--durable-objects--websockets)
   - [3.10 Observability — What Survives](#310-observability--what-survives)
   - [3.11 Async Job Processing — Cloudflare Queues](#311-async-job-processing--cloudflare-queues)
   - [3.12 Updated Architecture Diagram](#312-updated-architecture-diagram)
4. [Database Schema (D1)](#4-database-schema-d1)
5. [API Design](#5-api-design)
6. [Cost Matrix](#6-cost-matrix)
7. [Coolify vs Cloudflare — Decision Framework](#7-coolify-vs-cloudflare--decision-framework)
8. [Migration Strategy (Incremental)](#8-migration-strategy-incremental)
9. [Interoperability with Tauri Desktop](#9-interoperability-with-tauri-desktop)
10. [Implementation Phases](#10-implementation-phases)
11. [Key Decisions Needed](#11-key-decisions-needed)

---

## 1. Executive Summary

The goal is to move EventFinder AI to a **fully hosted, globally distributed, low-ops** architecture using Cloudflare (frontend, API, storage, database, real-time) and Clerk (auth). The Tauri desktop app becomes an optional companion; the web app becomes the primary product. The Python/LangGraph agent pipeline can run either on Cloudflare Python Workers or on a self-hosted Coolify VPS — the architecture makes this swappable.

**The architecture is designed so any "shortcut" decision can be fronted by a module or adapter, making it easy to extend or refactor later.** (Your request.)

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLIENTS                                    │
│                                                                      │
│   [Web Browser] ──HTTPS──► Cloudflare CDN (Pages)                   │
│        │                    │                                       │
│        │                    ▼                                       │
│        │            Next.js SSR + Clerk UI                          │
│        │                    │                                       │
│        └──HTTPS──► [Tauri Desktop App] ──HTTP──► same API          │
│                                                                      │
└──────────────┬──────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    CLOUDFLARE EDGE (Workers)                         │
│                                                                      │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────┐      │
│  │ Auth Worker  │  │ API Worker     │  │ Durable Objects      │     │
│  │ (TypeScript) │  │ (TypeScript    │  │ (Voting State)       │     │
│  │ - Clerk JWT  │  │  Hono-based)  │  │ per-group WebSocket  │     │
│  │ - Rate limit │  │ - /search     │  │ hibernation          │     │
│  └──────────────┘  │ - /vote       │  └──────────────────────┘      │
│                     │ - /groups     │                               │
│                     │ - /calendar   │  ┌──────────────────────┐      │
│                     └───────┬───────┘  │ D1 Database          │     │
│                             │          │ (global SQLite)       │     │
│                             │          └──────────────────────┘     │
│                             │          ┌──────────────────────┐      │
│                             │          │ R2 Object Storage    │     │
│                             │          │ (audio files)         │     │
│                             │          └──────────────────────┘     │
│                             │          ┌──────────────────────┐      │
│                             │          │ KV Store             │     │
│                             │          │ (sessions, cache)    │     │
│                             │          └──────────────────────┘     │
│                             │          ┌──────────────────────┐      │
│                             │          │ Cloudflare Queues    │     │
│                             │          │ transcription-queue  │     │
│                             │          │ search-queue         │     │
│                             │          │ notification-queue   │     │
│                             │          │ + Dead Letter Queues │     │
│                             │          └──────────────────────┘     │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │ Queue Consumer Worker
                                      │ (controlled concurrency)
                                      ▼
                    ┌──────────────────────────────────────┐
                    │       AGENT PIPELINE (swappable)     │
                    │                                      │
                    │  Coolify VPS (FastAPI)               │
                    │                                      │
                    │  - LangGraph orchestration          │
                    │  - Tavily search                     │
                    │  - Nylas calendar                    │
                    │  - Auditor (LLM + keyword)          │
                    │  - faster-whisper transcription     │
                    └──────────────────┬───────────────────┘
                                       │
                                       ▼
                              Tavily / OpenAI / Nylas
                              (external APIs, unchanged)
```

**Key principle: The API contract between the Cloudflare Workers layer and the agent pipeline is stable. Either compute option (Cloudflare Python Worker or Coolify FastAPI) implements the same interface.**

---

## 3. Component Deep-Dives

### 3.1 Frontend — Cloudflare Pages + Next.js

**What it replaces:** Tauri desktop app (`src-tauri/` + React frontend)

**Technology:** Next.js 15 deployed on Cloudflare Pages with the `@cloudflare/next-on-pages` adapter.

```bash
# Deployment is one command:
npx @cloudflare/next-on-pages
wrangler pages deploy .next/
```

**Why Next.js over plain React/SvelteKit/Astro:**
- Clerk has first-class Next.js integration (`clerkMiddleware()`, `auth()`, `Route Handlers`)
- Server Components + streaming for SSR without cold-start latency
- Built-in API Routes can act as a lightweight API layer before needing full Workers
- `export const runtime = "edge"` makes pages run on Cloudflare's edge — no origin server

**What gets migrated:**
- `MinimalRecorder.tsx` → Browser `MediaRecorder` (see section 3.2)
- `App.tsx` state → Next.js Server Components + React Query / SWR for data fetching
- Sentry error boundary → Keep Sentry on frontend, drop Rust-level capture
- Location persistence → Cloudflare KV instead of Tauri filesystem

**What gets dropped from Tauri:**
- Rust `cpal` audio recording → Browser API (section 3.2)
- Rust global shortcut (Alt+E) → Browser Keyboard API + optional browser extension
- Tauri filesystem config → Cloudflare KV

**Interoperability note:** The Next.js frontend calls the same REST API that a Tauri companion app would call. See Section 9.

---

### 3.2 Voice Recording — Browser MediaRecorder API

**Current state:** Tauri Rust backend captures microphone via `cpal` crate, writes WAV, sends to `/transcribe` endpoint.

**Migration:** Replace entirely with browser APIs. No backend code change needed for the transcription flow.

```typescript
// Browser-side voice recording (replaces Rust cpal)
const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
const chunks: BlobPart[] = [];

// Optional: real-time waveform visualization via Web Audio API
const audioContext = new AudioContext();
const analyser = audioContext.createAnalyser();
analyser.connectMediaStreamSource(stream);
// → use requestAnimationFrame + analyser.getByteTimeDomainData() for waveform

mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
mediaRecorder.onstop = async () => {
  const blob = new Blob(chunks, { type: 'audio/webm' });
  const formData = new FormData();
  formData.append('file', blob, 'recording.webm');
  await fetch('/api/transcribe', { method: 'POST', body: formData });
};
mediaRecorder.start();
```

**Advantages over Tauri recording:**
- Works on mobile browsers
- No install required
- Waveform visualization is actually easier via Web Audio API
- Transcribed via the same `/api/transcribe` endpoint — no change to FastAPI backend

**Limitations:**
- No global shortcut (Alt+E) in browser. Alternatives:
  - Browser extension (native browser extension APIs for shortcuts)
  - PWA with service worker for background listening
  - Simple "tap to record" — arguably better UX for an event app

---

### 3.3 API Layer — Cloudflare Workers (TypeScript)

**What it replaces:** FastAPI backend routes (the routing/API concern, not the agent logic)

**Technology:** TypeScript Workers with [Hono](https://hono.dev) framework — lightweight, fast, Cloudflare-native.

```typescript
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { bearerAuth } from 'hono/bearer-auth';
import { getCookie, setCookie } from 'hono/cookie';

const app = new Hono();

// All routes protected by Clerk JWT verification
app.use('/*', async (c, next) => {
  const token = c.req.header('Authorization')?.replace('Bearer ', '');
  if (!token) return c.json({ error: 'Unauthorized' }, 401);
  // Clerk's authenticateRequest for server-side verification
  const payload = await verifyToken(token, env);
  c.set('userId', payload.sub);
  await next();
});

app.post('/api/search', async (c) => {
  const body = await c.req.json();
  // Forward to agent pipeline (TypeScript or Python)
  const result = await AGENT_SERVICE.search(body);
  return c.json(result);
});

app.post('/api/transcribe', async (c) => {
  const body = await c.req.formData();
  const file = body.get('file') as File;
  // Upload to R2, then call agent pipeline
  const key = await uploadToR2(file);
  const result = await AGENT_SERVICE.transcribe(key);
  return c.json(result);
});

app.get('/api/groups/:id/votes', async (c) => {
  // Real-time voting via Durable Object WebSocket
  const doId = c.env.VOTING.idFromName(c.req.param('id'));
  const doStub = c.env.VOTING.get(doId);
  return doStub.fetch(c.req.raw);
});

export default app;
```

**What lives here:**
- Clerk JWT verification on every request
- Rate limiting (using Cloudflare's built-in rate limiting or KV-based)
- Request validation (using Zod or Valibot)
- R2 presigned URL generation for audio uploads
- Durable Object coordination (fetching the right DO per group)
- Calls to the agent pipeline (TypeScript or forwarding to Python service)

**What does NOT live here:**
- LangGraph orchestration (agent pipeline, Python)
- Whisper transcription (agent pipeline, Python)
- Tavily/Nylas calls (agent pipeline, Python)

**Why TypeScript + Hono over staying with FastAPI here:**
- Zero cold starts (Cloudflare Workers start in <1ms vs FastAPI's uvicorn bootstrap)
- Native Cloudflare bindings (D1, KV, R2, Durable Objects) — no database connection pooling
- Cheaper at low traffic (100K req/day free)
- Clerk has native TypeScript SDK

---

### 3.4 Agent Pipeline — Compute Strategy

> This is the most complex decision. The architecture supports two options with a stable interface.

**Current FastAPI services that need to live somewhere:**

| Service | Language | Compute Type | External Calls |
|---|---|---|---|
| `orchestration/manager.py` | Python | CPU | LangGraph, OpenAI |
| `discovery_agent/searcher.py` | Python | CPU | Tavily API |
| `calendar_agent/scheduler.py` | Python | CPU | Nylas API |
| `auditor/verifier.py` | Python | CPU | OpenAI (LLM) |
| `input_parser/parser.py` | Python | CPU | OpenAI (LLM) |
| `transcription/transcriber.py` | Python | GPU/CPU | faster-whisper |
| `discovery_agent/graph.py` | Python | CPU | LangGraph |

**Option A: Cloudflare Python Worker (via Pyodide)**

Cloudflare Workers now support Python via Pyodide (WebAssembly). As of 2025-12, cold starts are fast and `uv` package management is supported.

```toml
# wrangler.toml
main = "src/index.py"
compatibility_flags = ["python_packages"]
runtime = "python"
```

```python
# src/index.py
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
import json

async def on_fetch(request, env):
    body = await request.json()
    result = await run_search(body)
    return Response.json(result)
```

**Constraints:**
- Memory: ~128MB limit per worker. LangChain + LangGraph compressed is ~5-10MB, plus OpenAI SDK, httpx — fits, but tight.
- `faster-whisper` (C++ extension) will NOT work in Pyodide — must be a separate service or replaced with a cloud transcription API (Whisper API, Deepgram, AssemblyAI)
- Pyodide Python is synchronous by default. `asyncio` support exists but is limited.
- CPU time limit: 10ms/request on free tier, 50ms+/request on paid. Agent pipelines often take 2-10s. **This is a blocker for direct Worker hosting.**
- Solution: Use Cloudflare **Queues** for async job processing, Workers for API entry points only.

**Option B: Coolify VPS (recommended for agent pipeline)**

Deploy the existing FastAPI app on a Coolify-managed VPS. Your existing Docker setup (`Dockerfile.dev`, `Dockerfile.prod`) works with zero changes.

**Coolify details:**
- Self-hosted free: install on any VPS (Hetzner ~€4/mo, Contabo ~€6/mo, DigitalOcean ~$4/mo)
- Coolify Cloud (managed): starts at $5/mo
- Free tier: unlimited deployments, automatic SSL, Git-based deploys
- What's included: Docker + Git integration, automatic domain/SSL, health checks, rollbacks

```bash
# One command install on a VPS
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
# Then connect your GitHub repo, point at your Dockerfile.prod
```

**Coolify vs other options:**

| Option | Cost | Python Support | Whisper | LangGraph | Cold Start | Complexity |
|---|---|---|---|---|---|---|
| Cloudflare Python Worker | ~$0-20/mo | Pyodide (limited) | No | Partial | <50ms | High |
| Cloudflare Container | ~$130/mo | Full | Yes | Yes | <1s | Medium |
| Coolify Self-Hosted VPS | ~€4-10/mo | Full | Yes | Yes | 2-5s (keeps warm) | Low |
| Coolify Cloud | $5/mo | Full | Yes | Yes | 2-5s | Very Low |
| Railway/Render | ~$5-20/mo | Full | Yes | Yes | 2-10s | Low |

**Decision:** Use **Coolify** for the agent pipeline. It's the cheapest full-Python option, keeps your existing code with zero changes, and the architecture isolates it behind a stable API contract so it can be replaced later.

**The API contract** (implemented by the agent pipeline, called by TypeScript Workers):
```typescript
interface AgentService {
  search(params: SearchParams): Promise<SearchResponse>;       // POST /search
  verify(params: VerifyParams): Promise<VerifyResponse>;       // POST /verify
  transcribe(audioKey: string): Promise<TranscribeResponse>;   // POST /transcribe
  calendarOverlap(params: CalendarParams): Promise<OverlapResponse>; // POST /calendar/overlap
}
```

This `AgentService` interface is fronted by a module in the TypeScript Workers codebase. Swapping from Coolify FastAPI to Cloudflare Python Worker requires only changing the HTTP endpoint URL and adapting the response shapes.

---

### 3.5 Auth — Clerk

**What it replaces:** Custom auth (user table, sessions, JWT, etc.) + Tauri session management.

**Setup:**

```typescript
// middleware.ts (Next.js App Router)
import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server';

const isProtectedRoute = createRouteMatcher(['/api/search(.*)', '/api/groups(.*)']);

export default clerkMiddleware((auth, req) => {
  if (isProtectedRoute(req)) auth().protect();
});

// app/api/search/route.ts (Route Handler)
import { auth } from '@clerk/nextjs/server';
export async function POST(req: Request) {
  const { userId } = await auth();
  if (!userId) return Response.json({ error: 'Unauthorized' }, { status: 401 });
  // ... call agent pipeline with userId
}
```

**Clerk → D1 user sync via webhooks:**

Clerk doesn't write to your D1 directly. You need a Worker to receive webhook events:

```typescript
// workers/clerk-webhook/index.ts
app.post('/webhooks/clerk', async (c) => {
  const payload = await c.req.json();
  const svix = await verifyWebhook(payload, env.CLERK_WEBHOOK_SECRET);
  
  if (payload.type === 'user.created') {
    await env.DB.prepare(
      'INSERT INTO users (clerk_id, email, name, created_at) VALUES (?, ?, ?, ?)'
    ).bind(
      payload.data.id,
      payload.data.email_addresses[0].email_address,
      payload.data.first_name + ' ' + payload.data.last_name,
      new Date().toISOString()
    ).run();
  }
  
  return c.json({ received: true });
});
```

**Clerk webhook events to handle:**
| Event | Action |
|---|---|
| `user.created` | Insert into `users` table |
| `user.updated` | Update `users` table |
| `user.deleted` | Soft-delete or archive user |
| `organization.created` | Insert into `organizations` table (for group features) |

**Clerk pricing:**
- **Free tier (Hobby):** $0/mo, 50K monthly retained users, 3 dashboard seats
- **Pro:** $25/mo, 50K MRU included + $0.02/mo per additional user
- **B2B add-on:** $100/mo, 100 MRO included — for organization/group features

**Recommendation:** Start with the **Hobby (free)** plan. Upgrade to Pro when approaching 50K MRU. The B2B add-on is only needed for organization/multi-team features.

---

### 3.6 Database — Cloudflare D1

**What it replaces:** PostgreSQL (currently in docker-compose, not yet actively used) + Redis (for caching).

**D1 overview:**
- SQLite at the edge, globally replicated
- Free: 5GB storage, 100K reads/day, 100K writes/day
- Paid: $0.20/GB-month storage, $0.15/million reads, $1/million writes
- Supports: generated columns, JSON functions, full-text search (`FTS5`), window functions
- NOT supports: JSONB (use JSON text), advanced PostgreSQL features, pgcrypto extensions

**Migrations:** Use `wrangler d1 migrations apply` — version-controlled SQL migrations.

**D1 limitations that matter for EventFinder:**
- No `INTERVAL` type (dates are stored as TEXT/INTEGER)
- No native `ARRAY` type (use JSON text)
- `JSON_EXTRACT` works but PostgreSQL's JSONB operators don't — queries need adjustment
- 10GB max per database (free tier)
- No connection pooling needed — edge-native

**Comparison vs PostgreSQL:**

| Feature | D1 (SQLite) | PostgreSQL |
|---|---|---|
| Storage limit | 10GB | Unlimited |
| JSON support | JSON text | JSONB (binary) |
| Full-text search | FTS5 (built-in) | tsvector (better) |
| Replication | Automatic global | Manual/config |
| Connection pooling | Not needed | Required |
| Price at 1M users | ~$50/mo (writes) | ~$20/mo (RDS) |
| Complex queries | Limited | Full SQL power |
| Agent checkpointing | Via LangGraph SQLite | Via LangGraph Postgres |

**For LangGraph checkpointing:** LangGraph supports SQLite as a checkpoint backend. The agent pipeline (Coolify) can use its own local SQLite file or connect to D1 via HTTP (requires a proxy Worker). **Recommendation: Keep LangGraph state local to the agent service (SQLite file on the VPS) for simplicity.**

---

### 3.7 Storage — Cloudflare R2

**What it replaces:** File system storage for audio recordings (Tauri config dir), potential future uploads.

**Setup:**
```typescript
// workers/api/src/upload.ts
app.post('/api/upload-audio', async (c) => {
  const formData = await c.req.formData();
  const file = formData.get('audio') as File;
  
  const key = `audio/${crypto.randomUUID()}.webm`;
  await c.env.ASSETS.put(key, file.stream(), {
    httpMetadata: { contentType: file.type },
    customMetadata: { userId: c.get('userId') }
  });
  
  return c.json({ key });
});
```

**R2 vs S3:** R2 is S3-compatible (same API, different SDK binding). Egress is **free** on R2 (vs ~$0.09/GB on S3). Critical for an app that stores audio.

**Pricing:**
- Free: 10GB storage, 1M Class A ops, 10M Class B ops/month
- Paid: $0.015/GB-month storage, $0.36/million Class A, $0.09/million Class B

**Recommendation:** Start with R2. At typical usage (audio files ~1MB each, moderate traffic), you'll stay well within the free tier.

---

### 3.8 Sessions/Cache — Cloudflare KV

**What it replaces:** Redis (currently in docker-compose) for session state and cache.

**KV vs Redis comparison:**

| Feature | KV | Redis |
|---|---|---|
| Read latency | 10-30ms (edge) | 1-5ms (same-region) |
| Global replication | Automatic | Requires Redis Cluster |
| Expiration | Native TTL | Native EXPIRE |
| Data types | Strings only | Strings, hashes, lists, sets |
| Atomic ops | No | Lua scripting |
| Free tier | 1GB, 100K reads/day | None |
| Price | $0.20/million reads | ~$0-50/mo (managed) |

**What to store in KV:**
- User session tokens (after Clerk verifies, cache in KV with TTL)
- Rate limiting counters
- Temporary search result cache (so Tavily isn't called twice for the same query within minutes)
- Group state snapshots (for crash recovery of Durable Objects)

**Limitation:** KV only stores strings/bytes. Complex data must be serialized/deserialized.

**Alternative:** Cloudflare **Cache API** (free, HTTP-based) for read-heavy cached data. Use KV only for mutable state with TTL.

---

### 3.9 Real-Time Voting — Durable Objects + WebSockets

**What it replaces:** The real-time update requirement from `group-planning-design.md`. Redis pub/sub is no longer needed.

**Architecture:**
- One Durable Object **per group/plan** (keyed by group ID)
- WebSocket hibernation keeps connections alive without consuming CPU time
- State is event-sourced: votes are appended to an in-memory array, periodically persisted to D1

```typescript
// workers/durable-objects/voting.ts
export class VotingCoordinator implements DurableObject {
  private votes: Map<string, VoteRecord> = new Map();
  private websocketPairs: Map<WebSocket, number> = new Map();
  private db: D1Database;

  async fetch(request: Request): Promise<Response> {
    if (request.headers.get('Upgrade') === 'WebSocket') {
      const { 0: client, 1: server } = new WebSocketPair();
      const userId = this.verifyToken(request);
      
      server.accept();
      server.addEventListener('message', (msg) => {
        const vote = JSON.parse(msg.data);
        this.votes.set(userId, vote);
        // Broadcast to all connected clients
        this.websocketPairs.forEach((_, ws) => {
          if (ws !== server) ws.send(JSON.stringify({ type: 'vote_update', vote }));
        });
        // Periodically persist to D1 (every 10 votes or 30s)
        this.persistIfNeeded();
      });
      
      this.websocketPairs.set(server, userId);
      return new Response(null, { webSocket: client });
    }
    return new Response('Expected WebSocket', { status: 426 });
  }

  private async persistIfNeeded() {
    if (this.votes.size % 10 === 0) {
      await this.db
        .prepare('UPDATE groups SET votes_json = ? WHERE id = ?')
        .bind(JSON.stringify([...this.votes]), this.groupId)
        .run();
    }
  }
}
```

**Durable Object pricing:**
- Free: 100K requests/day, 1GB storage, 200K GB-s/day
- Paid: $0.30/million requests, $0.20/GB-month storage, $12.50/million GB-s

**At typical scale:** A group with 10 people voting = ~10 WebSocket messages/second. 100 concurrent groups = 1K messages/second. Well within free tier.

**SSE fallback:** If WebSocket support is too complex initially, Durable Objects also support SSE (Server-Sent Events). The same DO can expose both.

---

### 3.10 Observability — What Survives

**Current stack:** Sentry (Python + JS), Prometheus + Grafana (Docker)

**Cloudflare-native alternatives:**

| Concern | Current | Cloudflare Replacement |
|---|---|---|
| Python errors | Sentry Python SDK | Workers AI log parsing + D1 error table |
| Frontend errors | @sentry/react | Browser SDK → D1 error log OR external Sentry (still works!) |
| Metrics | prometheus-client | Cloudflare Analytics dashboard (built-in, free) |
| Tracing | Manual (structlog) | Workers traces (built-in, tail workers) |
| Uptime | Manual | Cloudflare Health Checks (free) |
| APM | Grafana + Prometheus | Cloudflare Logs (Logpush to R2 or third-party) |

**Recommendation:** Keep **Sentry for frontend errors** (the JS SDK works on Cloudflare Pages with no changes). Replace Python error tracking with a D1-backed error log table written by the agent pipeline. The Prometheus + Grafana Docker setup can be replaced with a free Cloudflare Analytics dashboard initially, then Grafana + Cloudflare Metrics API later if needed.

---

### 3.11 Async Job Processing — Cloudflare Queues + Coolify

> This section explains how Cloudflare Queues sits between the TypeScript Workers layer and the Coolify agent pipeline, providing backpressure, retries, dead-letter handling, and controlled throughput.

#### The Problem

The Coolify VPS has finite capacity:
- A 4GB VPS running `faster-whisper` can handle ~2-4 concurrent transcriptions (each uses 1-2GB RAM).
- LangGraph agent pipelines are CPU-bound and can't handle unlimited parallel requests.
- Without a queue, a traffic spike (e.g., 50 users recording simultaneously) overwhelms the VPS → OOM crashes, dropped requests, poor UX.

#### The Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        ASYNC JOB FLOW                                         │
│                                                                               │
│  [User] ──► /api/transcribe endpoint (TypeScript Worker)                     │
│               │                                                               │
│               │ 1. Upload audio to R2                                        │
│               │ 2. Enqueue job to Cloudflare Queue                           │
│               │ 3. Return job_id immediately (202 Accepted)                  │
│               ▼                                                               │
│  ┌──────────────────────────┐                                                │
│  │ Cloudflare Queue         │                                                │
│  │ "transcription-queue"    │                                                │
│  │                          │                                                │
│  │ - Max 5,000 msg/sec      │                                                │
│  │ - 128KB max message size │                                                │
│  │ - Configurable retention │                                                │
│  │ - Dead Letter Queue      │                                                │
│  └───────────┬──────────────┘                                                │
│              │                                                               │
│              │ Queue Consumer Worker (TypeScript)                            │
│              │ - Pulls 1-5 messages at a time                                │
│              │ - Forwards to Coolify VPS via HTTP                            │
│              │ - Controls concurrency (max N simultaneous requests)          │
│              ▼                                                               │
│  ┌──────────────────────────┐                                                │
│  │ Coolify VPS (FastAPI)    │                                                │
│  │                          │                                                │
│  │ /api/transcribe          │                                                │
│  │ - Downloads audio from R2│                                                │
│  │ - Runs faster-whisper    │                                                │
│  │ - Returns transcript     │                                                │
│  └───────────┬──────────────┘                                                │
│              │                                                               │
│              │ 4. Store result in D1                                         │
│              │ 5. Notify user via Durable Object / SSE / polling             │
│              ▼                                                               │
│  [User polls / receives update] ◄── /api/jobs/:id/status                    │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### Queue Configuration

```typescript
// wrangler.toml
[[queues.consumers]]
queue = "transcription-queue"
max_batch_size = 5          // Process 5 transcriptions per batch
max_batch_timeout = 30      // Wait up to 30s for a full batch
max_retries = 3             // Retry failed transcriptions 3 times
dead_letter_queue = "transcription-dlq"
max_concurrency = 2         // Max 2 simultaneous consumer invocations

[[queues.producers]]
queue = "transcription-queue"
binding = "TRANSCRIPTION_QUEUE"

[[queues.consumers]]
queue = "transcription-dlq"
max_batch_size = 10
max_retries = 0             // DLQ messages are not retried

[[queues.producers]]
queue = "transcription-dlq"
binding = "TRANSCRIPTION_DLQ"
```

#### Producer: Enqueue Transcription Job

```typescript
// workers/api/src/routes/transcription.ts
app.post('/api/transcribe', async (c) => {
  const userId = c.get('userId');
  const formData = await c.req.formData();
  const file = formData.get('audio') as File;

  // Step 1: Upload to R2
  const key = `audio/${crypto.randomUUID()}.webm`;
  await c.env.ASSETS.put(key, file.stream(), {
    httpMetadata: { contentType: file.type },
    customMetadata: { userId }
  });

  // Step 2: Create job record in D1
  const jobId = crypto.randomUUID();
  await c.env.DB.prepare(
    'INSERT INTO transcription_jobs (id, user_id, audio_key, status, created_at) VALUES (?, ?, ?, ?, ?)'
  ).bind(jobId, userId, key, 'queued', new Date().toISOString()).run();

  // Step 3: Enqueue to Cloudflare Queue
  await c.env.TRANSCRIPTION_QUEUE.send({
    jobId,
    userId,
    audioKey: key,
    language: formData.get('language') || 'en',
    retries: 0
  });

  // Step 4: Return immediately (async processing)
  return c.json({
    jobId,
    status: 'queued',
    message: 'Transcription started. Poll /api/jobs/:id/status for results.'
  }, 202);
});
```

#### Consumer: Process Queue Messages

```typescript
// workers/transcription-consumer/index.ts
export default {
  async queue(batch: MessageBatch, env: Env): Promise<void> {
    const COOLIFY_BASE = env.COOLIFY_URL; // e.g., https://api.eventfinder.ai
    const CONCURRENCY_LIMIT = 2; // Max simultaneous transcriptions

    // Process messages with controlled concurrency
    const results = await Promise.allSettled(
      batch.messages.map(async (message) => {
        const job = message.body as TranscriptionJob;

        try {
          // Forward to Coolify VPS
          const response = await fetch(`${COOLIFY_BASE}/api/transcribe`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${env.AGENT_SECRET}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              audio_key: job.audioKey,
              language: job.language,
              job_id: job.jobId
            })
          });

          if (!response.ok) {
            throw new Error(`Coolify returned ${response.status}: ${await response.text()}`);
          }

          const result = await response.json();

          // Store result in D1
          await env.DB.prepare(
            'UPDATE transcription_jobs SET status = ?, transcript = ?, completed_at = ? WHERE id = ?'
          ).bind('completed', result.text, new Date().toISOString(), job.jobId).run();

          // Notify user via Durable Object (if they have an active WebSocket connection)
          await notifyUser(env, job.userId, {
            type: 'transcription_complete',
            jobId: job.jobId,
            text: result.text
          });

        } catch (error) {
          // Retry logic: if retries < max, let Queue handle it
          // If max retries exceeded, send to DLQ
          if (job.retries >= 3) {
            // Store failure in D1
            await env.DB.prepare(
              'UPDATE transcription_jobs SET status = ?, error = ?, failed_at = ? WHERE id = ?'
            ).bind('failed', error.message, new Date().toISOString(), job.jobId).run();

            // Send to Dead Letter Queue for manual review
            await env.TRANSCRIPTION_DLQ.send({
              ...job,
              error: error.message,
              failedAt: new Date().toISOString()
            });

            // Notify user of failure
            await notifyUser(env, job.userId, {
              type: 'transcription_failed',
              jobId: job.jobId,
              error: error.message
            });
          } else {
            // Let the Queue retry mechanism handle it
            message.retry({ delay: Math.pow(2, job.retries) * 1000 }); // Exponential backoff
          }
        }
      })
    );

    // Log batch results
    const succeeded = results.filter(r => r.status === 'fulfilled').length;
    const failed = results.filter(r => r.status === 'rejected').length;
    console.log(`Batch processed: ${succeeded} succeeded, ${failed} failed`);
  }
};
```

#### Dead Letter Queue Handler

```typescript
// workers/dlq-consumer/index.ts
export default {
  async queue(batch: MessageBatch, env: Env): Promise<void> {
    for (const message of batch.messages) {
      const failedJob = message.body as FailedTranscriptionJob;

      // Log to D1 for manual review
      await env.DB.prepare(
        'INSERT INTO transcription_failures (job_id, user_id, audio_key, error, failed_at, retry_count) VALUES (?, ?, ?, ?, ?, ?)'
      ).bind(
        failedJob.jobId,
        failedJob.userId,
        failedJob.audioKey,
        failedJob.error,
        failedJob.failedAt,
        failedJob.retries
      ).run();

      // Optionally: send alert to admin (email, Slack webhook)
      // await sendAdminAlert(`Transcription failed: ${failedJob.jobId} - ${failedJob.error}`);

      // Don't retry — this is the dead letter queue
      message.ack();
    }
  }
};
```

#### Job Status Polling Endpoint

```typescript
// workers/api/src/routes/jobs.ts
app.get('/api/jobs/:id/status', async (c) => {
  const jobId = c.req.param('id');
  const userId = c.get('userId');

  const result = await c.env.DB.prepare(
    'SELECT * FROM transcription_jobs WHERE id = ? AND user_id = ?'
  ).bind(jobId, userId).first();

  if (!result) {
    return c.json({ error: 'Job not found' }, 404);
  }

  return c.json({
    jobId: result.id,
    status: result.status, // 'queued' | 'processing' | 'completed' | 'failed'
    transcript: result.transcript || null,
    error: result.error || null,
    createdAt: result.created_at,
    completedAt: result.completed_at || null
  });
});
```

#### Queue Limits & Capacity Planning

| Metric | Limit | Notes |
|---|---|---|
| Max message size | 128 KB | Transcription job payload is ~200 bytes — well within limit |
| Max throughput | 5,000 msg/sec | Far exceeds EventFinder's needs |
| Max backlog | 25 GB | ~125 million jobs at 200 bytes each |
| Message retention | Up to 14 days (paid) | Configurable; 24h on free tier |
| Max retries | 100 | We use 3 with exponential backoff |
| Max concurrent consumers | 250 | We limit to 2 to protect the VPS |
| Consumer wall time | 15 min | Plenty for transcription |

#### Concurrency Control Strategy

The key insight: **the queue consumer controls how many requests hit the VPS at once.**

```
VPS Capacity: 2-4 concurrent transcriptions (RAM-limited)
Queue Consumer: max_concurrency = 2
Batch Size: 5 messages
Result: Max 2 × 5 = 10 simultaneous requests, but the consumer processes them sequentially within each invocation
```

If you need more throughput:
1. **Scale up the VPS** (more RAM = more concurrent transcriptions)
2. **Increase `max_concurrency`** on the queue consumer
3. **Add a second VPS** and split the queue into two consumers

#### Pricing

| Metric | Free Tier | At 10K DAU | At 50K DAU |
|---|---|---|---|
| Operations included | 10K/day | — | — |
| Cost per million ops | — | $0.40 | $0.40 |
| Est. operations/month | 300K | 3M | 15M |
| **Monthly cost** | **$0** | **~$0.80** | **~$5.60** |

Calculation: 3 ops per message (write + read + delete). 10K DAU × 2 transcriptions/day × 3 ops × 30 days = 1.8M ops/month. After 1M free = 800K billed × $0.40/M = $0.32/mo.

#### Why This Pattern Works

| Problem | How Queues Solve It |
|---|---|
| VPS overload from traffic spikes | Queue absorbs spikes, processes at controlled rate |
| Transcription failures | Retries with exponential backoff, then DLQ |
| Lost jobs | Queue persists messages for up to 14 days |
| No visibility into failures | DLQ stores failed jobs in D1 for review |
| User waiting indefinitely | Job status polling + Durable Object notifications |
| Cost unpredictability | Queue pricing is linear and predictable |

#### Extending to Other Workloads

The same queue pattern can handle:
- **Event search** — queue LangGraph pipeline jobs if the VPS is overloaded
- **Calendar sync** — queue Nylas API calls (rate-limited to 100 req/min)
- **Email notifications** — queue Resend API calls
- **Audio cleanup** — queue R2 file deletion after transcription completes

Each gets its own queue:
```
transcription-queue → transcription-dlq
search-queue → search-dlq
notification-queue → notification-dlq
```

---

### 3.12 Updated Architecture Diagram

---

## 4. Database Schema (D1)

```sql
-- Migrations: manage with wrangler d1 migrations apply

CREATE TABLE users (
  id TEXT PRIMARY KEY,               -- UUID, not Clerk ID (for portability)
  clerk_id TEXT UNIQUE NOT NULL,      -- Clerk user ID
  email TEXT NOT NULL,
  name TEXT,
  home_city TEXT,
  preferred_radius_km INTEGER DEFAULT 25,
  preferred_genres TEXT,              -- JSON array
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE events (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,               -- 'tavily', 'manual', etc.
  title TEXT NOT NULL,
  description TEXT,
  location TEXT,
  latitude REAL,
  longitude REAL,
  start_time TEXT,                    -- ISO 8601
  end_time TEXT,
  url TEXT,
  cost REAL DEFAULT 0,
  free Boolean DEFAULT TRUE,
  organizer TEXT,
  tags TEXT,                          -- JSON array
  created_by TEXT REFERENCES users(id),
  created_at TEXT NOT NULL
);

CREATE TABLE groups (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  created_by TEXT REFERENCES users(id),
  public_token TEXT UNIQUE NOT NULL, -- Shareable link token
  admin_token TEXT UNIQUE NOT NULL, -- Creator/admin link token
  status TEXT DEFAULT 'open',        -- 'open', 'voting', 'finalized', 'cancelled'
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE group_members (
  group_id TEXT REFERENCES groups(id) ON DELETE CASCADE,
  user_id TEXT REFERENCES users(id),
  role TEXT DEFAULT 'member',        -- 'admin', 'member', 'guest'
  joined_at TEXT NOT NULL,
  PRIMARY KEY (group_id, user_id)
);

CREATE TABLE group_events (
  group_id TEXT REFERENCES groups(id) ON DELETE CASCADE,
  event_id TEXT REFERENCES events(id) ON DELETE CASCADE,
  added_by TEXT REFERENCES users(id),
  status TEXT DEFAULT 'pending',     -- 'pending', 'voting', 'selected', 'rejected'
  created_at TEXT NOT NULL,
  PRIMARY KEY (group_id, event_id)
);

CREATE TABLE votes (
  id TEXT PRIMARY KEY,
  group_id TEXT REFERENCES groups(id) ON DELETE CASCADE,
  event_id TEXT REFERENCES events(id) ON DELETE CASCADE,
  user_id TEXT REFERENCES users(id),
  score INTEGER NOT NULL,            -- 1-5 scale
  created_at TEXT NOT NULL,
  UNIQUE(group_id, event_id, user_id)
);

CREATE TABLE calendar_slots (
  user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
  date TEXT,                         -- YYYY-MM-DD
  start_time TEXT,                   -- HH:MM
  end_time TEXT,
  busy INTEGER DEFAULT 0,             -- 0=free, 1=busy
  source TEXT,                       -- 'nylas', 'manual'
  PRIMARY KEY (user_id, date, start_time)
);

CREATE TABLE notifications (
  id TEXT PRIMARY KEY,
  user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
  type TEXT NOT NULL,                -- 'vote_reminder', 'event_selected', 'group_invite'
  payload TEXT,                       -- JSON
  read INTEGER DEFAULT 0,
  created_at TEXT NOT NULL
);

-- Full-text search for events
CREATE VIRTUAL TABLE events_fts USING fts5(
  title, description, tags, content=events, content_rowid=rowid
);

-- Indexes
CREATE INDEX idx_votes_group ON votes(group_id);
CREATE INDEX idx_votes_event ON votes(event_id);
CREATE INDEX idx_group_members_user ON group_members(user_id);
CREATE INDEX idx_calendar_user_date ON calendar_slots(user_id, date);
CREATE INDEX idx_notifications_user ON notifications(user_id, read);
```

---

## 5. API Design

All endpoints are exposed from the **TypeScript Cloudflare Worker** layer.

### Authentication
All endpoints except `/auth/*` and public group pages require Clerk Bearer token.

```
Authorization: Bearer <clerk_jwt>
```

### Endpoints

| Method | Path | Description | Auth |
|---|---|---|---|
| `GET` | `/api/health` | Health check | No |
| `POST` | `/api/search` | Discover events (proxies to agent pipeline) | Yes |
| `POST` | `/api/verify` | Verify event is free | Yes |
| `POST` | `/api/transcribe` | Upload audio → R2 → enqueue job → return 202 | Yes |
| `GET` | `/api/jobs/:id/status` | Poll transcription job status | Yes |
| `DELETE` | `/api/jobs/:id` | Cancel a queued job | Yes |
| `GET` | `/api/groups` | List user's groups | Yes |
| `POST` | `/api/groups` | Create new group | Yes |
| `GET` | `/api/groups/:id` | Get group details | Yes |
| `GET` | `/api/groups/:id` | Group detail (public token works too) | Partial |
| `POST` | `/api/groups/:id/events` | Add event to group | Yes |
| `GET` | `/api/groups/:id/events` | List group's events | Yes |
| `POST` | `/api/groups/:id/vote` | Cast a vote | Yes |
| `DELETE` | `/api/groups/:id/vote/:eventId` | Remove vote | Yes |
| `WS` | `/api/groups/:id/live` | WebSocket for real-time voting | Yes |
| `GET` | `/api/groups/:id/votes` | Get all votes | Yes |
| `POST` | `/api/groups/:id/finalize` | Finalize selection | Yes |
| `GET` | `/api/calendar/overlap` | Calendar overlap for group | Yes |
| `POST` | `/api/calendar/sync` | Sync Nylas calendar | Yes |
| `GET` | `/api/users/me` | Get current user profile | Yes |
| `PATCH` | `/api/users/me` | Update preferences | Yes |
| `POST` | `/api/upload-url` | Get R2 presigned upload URL | Yes |

### Request/Response Shapes

```typescript
// POST /api/search
interface SearchRequest {
  query: string;
  location?: { lat: number; lng: number };
  radiusKm?: number;
  dateFrom?: string;
  dateTo?: string;
  genres?: string[];
}

interface SearchResponse {
  events: Event[];
  query: string;
  searchId: string;
  cached: boolean;
}

// POST /api/groups/:id/vote
interface VoteRequest {
  eventId: string;
  score: number; // 1-5
}

// WS /api/groups/:id/live — WebSocket messages
type LiveMessage =
  | { type: 'vote_update'; userId: string; eventId: string; score: number }
  | { type: 'user_joined'; userId: string; name: string }
  | { type: 'user_left'; userId: string }
  | { type: 'group_status'; status: GroupStatus }
  | { type: 'finalized'; eventId: string };
```

---

## 6. Cost Matrix

### Cloudflare — Monthly Cost by Usage

| Component | Free Tier | 1K DAU | 10K DAU | 50K DAU |
|---|---|---|---|---|
| **Workers (TypeScript API)** | 100K req/day | ~$0 | ~$5 | ~$25 |
| **D1 reads** | 100K/day | ~$0 | ~$20 | ~$100 |
| **D1 writes** | 100K/day | ~$0 | ~$30 | ~$150 |
| **D1 storage** | 5GB | ~$0 | ~$1 | ~$5 |
| **R2 storage** | 10GB | ~$0 | ~$0 | ~$5 |
| **R2 ops** | 10M/month | ~$0 | ~$0 | ~$0 |
| **KV** | 1GB, 100K reads/day | ~$0 | ~$5 | ~$20 |
| **Durable Objects** | 100K req/day | ~$0 | ~$0 | ~$10 |
| **Queues** | 10K ops/day | ~$0 | ~$1 | ~$6 |
| **Subtotal Cloudflare** | | **~$0** | **~$66/mo** | **~$340/mo** |

### Coolify (Agent Pipeline) — Monthly Cost

| Provider | Instance | Specs | Cost |
|---|---|---|---|
| Hetzner (EU) | CX21 | 4 vCPU, 4GB RAM | €4.49/mo |
| Contabo (EU) | VPS S | 4 vCPU, 8GB RAM | €5.99/mo |
| DigitalOcean | Basic | 2 vCPU, 4GB RAM | $24/mo |
| Coolify Cloud | Starter | Managed | $5/mo |

**Recommended:** Hetzner CX21 (€4.49/mo) with Coolify self-hosted. Upgrade to Coolify Cloud ($5/mo) or a larger instance if needed.

### Clerk — Monthly Cost

| Plan | MRU Limit | Price |
|---|---|---|
| Hobby | 50K | $0 |
| Pro | 50K + $0.02/user | $25/mo + usage |
| Business | Unlimited | $300/mo |

**Start with Hobby (free).** Upgrade when approaching 50K MRU.

### Total Monthly Cost

| Scale | Cloudflare | Coolify VPS | Clerk | **Total** |
|---|---|---|---|---|
| Launch (0-1K DAU) | ~$0-5 | €4.49-5 | $0 | **~$5-10/mo** |
| Growth (10K DAU) | ~$66 | €4.49 | $0-25 | **~$70-95/mo** |
| Scale (50K DAU) | ~$340 | €4.49 | $25+ | **~$370+/mo** |

### vs. Current (Docker on local hardware)

| Component | Current Cost | Cloudflare Equivalent |
|---|---|---|
| VPS/server | $0-20/mo | Workers (free tier) |
| PostgreSQL | $0-15/mo | D1 (free tier) |
| Redis | $0-10/mo | KV (free tier) |
| Object storage | $0-5/mo | R2 (free tier) |
| Domain/SSL | $10-15/mo | Free (Cloudflare) |
| **Total** | **$0-50/mo** | **~$0-5/mo** |

**The Cloudflare migration actually reduces infrastructure costs at small-medium scale, while adding Clerk as a new cost ($0-25/mo).**

---

## 7. Coolify vs Cloudflare — Decision Framework

The architecture is designed so this decision is **localized to one module** — the `AgentService` adapter in the TypeScript Workers layer.

### Decision Tree

```
Is the agent pipeline latency-critical?
│
├─ YES: Need < 200ms per search request
│   └─ Consider Cloudflare Python Worker with Queues (async)
│      Tradeoff: Complexity, Whisper must be external API
│
└─ NO: Standard latency is fine (1-5s for search)
    │
    ├─ Want zero ops / fully managed? → Coolify Cloud ($5/mo)
    │
    ├─ Want cheapest option? → Coolify Self-Hosted on Hetzner (€4.49/mo)
    │
    └─ Expect high traffic (>1M searches/day)?
        Calculate: Coolify VPS (unlimited req) vs Cloudflare Workers ($0.30/M req)
        Break-even: 1M req/mo = $0.30 on Workers = €4.49 on VPS
        Above 1M req/mo → Coolify is cheaper
```

### The Swappable Interface

```typescript
// workers/agent-service/index.ts

// === OPTION A: Coolify FastAPI ===
const COOLIFY_BASE = 'https://api.your-coolify-instance.com';

export async function search(params: SearchParams): Promise<SearchResponse> {
  const res = await fetch(`${COOLIFY_BASE}/search`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${env.AGENT_SECRET}` },
    body: JSON.stringify(params)
  });
  return res.json();
}

// === OPTION B: Cloudflare Python Worker ===
// (activated by swapping the env variable)
const CF_WORKER_URL = 'https://agent.your-worker.workers.dev';

export async function search(params: SearchParams): Promise<SearchResponse> {
  const res = await fetch(`${CF_WORKER_URL}/search`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${env.AGENT_SECRET}` },
    body: JSON.stringify(params)
  });
  return res.json();
}
```

**The entire Coolify vs Cloudflare decision is: change one URL constant and redeploy the Worker.** This is what "fronted by a module" means in practice.

---

## 8. Migration Strategy (Incremental)

The migration follows a "strangle the monolith" pattern — new pieces go live alongside old ones, with zero big-bang switches.

### Phase 0: Infrastructure Setup
1. Create Cloudflare account + domain
2. Set up Clerk application (Hobby tier)
3. Provision D1 database + apply migrations
4. Provision R2 bucket
5. Create Cloudflare Workers project (TypeScript + Hono)
6. Set up Coolify on a Hetzner VPS
7. Deploy existing FastAPI app to Coolify
8. Configure `wrangler.toml` with all bindings (D1, KV, R2, Durable Objects)
9. Set up GitHub Actions CI/CD for Workers and Pages

### Phase 1: Auth + Basic API
1. Deploy Clerk webhooks Worker → D1 user sync
2. Migrate user table schema to D1
3. Deploy TypeScript API Worker with auth middleware
4. Point Tauri desktop app at new API (test interoperability)
5. Deploy Next.js frontend to Cloudflare Pages
6. Set up Clerk authentication UI (sign-in, sign-up, profile)
7. Test full auth flow (web + Tauri)

### Phase 2: Core Event Features
1. Migrate event search to Workers → Coolify agent pipeline
2. Add R2 audio upload (presigned URLs from Worker)
3. Deploy transcription Worker → Coolify (existing faster-whisper code)
4. Migrate calendar endpoints (Nylas) to Coolify agent pipeline
5. Add observability: Sentry for frontend, D1 error log for backend

### Phase 3: Group Planning (from group-planning-design.md)
1. Migrate groups, members, events tables to D1
2. Implement shareable link pattern (public_token + admin_token)
3. Deploy Durable Objects for voting state
4. Add WebSocket endpoint for live voting
5. Implement SSE fallback for group updates
6. Add notification system (email via Cloudflare Email Workers, or Resend)

### Phase 4: Polish & Deprecate
1. Deprecate Tauri API endpoints if web app is sufficient
2. Archive `tauri_frontend/` as reference/component library
3. Set up Cloudflare Analytics + Grafana dashboards
4. Load test at target scale
5. Document operational runbook

---

## 9. Interoperability with Tauri Desktop

The user's stated reason for Tauri was **interoperability**. Here's how the web version preserves and improves this:

**Problem with current Tauri:** The Tauri app bundles the entire frontend + a Rust backend that does recording and IPC. If the backend changes, users need to update the desktop app.

**Better approach: API-first design**

The Cloudflare-hosted API is the **single source of truth**. Both the web app and the Tauri desktop app call the same API endpoints.

```rust
// Tauri companion app — src-tauri/src/commands.rs
// The Rust backend no longer needs a FastAPI server.
// It just calls the Cloudflare API:

#[tauri::command]
async fn search_events(query: String) -> Result<SearchResponse, String> {
    let token = get_saved_token().map_err(|e| e.to_string())?;
    let client = reqwest::Client::new();
    let res = client
        .post("https://api.eventfinder.ai/search")
        .bearer_auth(&token)
        .json(&json!({ "query": query }))
        .send()
        .await
        .map_err(|e| e.to_string())?;
    let body = res.json::<SearchResponse>().await.map_err(|e| e.to_string())?;
    Ok(body)
}
```

**What the Tauri companion app looks like after migration:**
- Rust `cpal` audio recording → Still useful (better quality than browser MediaRecorder)
- Rust HTTP client → Calls Cloudflare API (instead of local FastAPI)
- Global shortcut (Alt+E) → Preserved
- No local database → Everything persisted to Cloudflare D1/KV
- Single executable, no Docker dependency for the app user

**This means:**
- Desktop users get native audio quality
- Web users get zero-install convenience
- Both use the same backend
- The Tauri companion can be a thin wrapper, much simpler than the current full-stack Tauri app

---

## 10. Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
**Goal:** Cloudflare Pages + Clerk + D1 + R2 working in production

- [ ] Set up Cloudflare account, add domain, configure DNS
- [ ] Create Clerk application, configure webhooks
- [ ] Initialize D1 database, write migrations
- [ ] Initialize R2 bucket with appropriate CORS settings
- [ ] Create TypeScript Workers project with Hono
- [ ] Implement Clerk JWT verification middleware
- [ ] Implement `/auth/webhook` endpoint (Clerk → D1 user sync)
- [ ] Implement basic CRUD endpoints for users
- [ ] Deploy Next.js frontend to Cloudflare Pages
- [ ] Configure `wrangler.toml` with all bindings
- [ ] Set up GitHub Actions: lint → test → deploy Workers + Pages
- [ ] Point Tauri desktop app at new API, verify auth flow

### Phase 2: Event Discovery (Weeks 3-4)
**Goal:** Full event search pipeline working via web + Tauri

- [ ] Deploy existing FastAPI agent pipeline to Coolify
- [ ] Add R2 presigned URL generation to Workers
- [ ] Create Cloudflare Queues (`transcription-queue`, `transcription-dlq`)
- [ ] Deploy transcription consumer Worker (pulls from queue → Coolify)
- [ ] Deploy DLQ consumer Worker (logs failures to D1)
- [ ] Implement `/api/transcribe` (upload → R2 → enqueue → 202 Accepted)
- [ ] Implement `/api/jobs/:id/status` (polling endpoint)
- [ ] Add Durable Object notification for transcription completion
- [ ] Implement `/api/search` (Workers → Coolify agent → Tavily → response)
- [ ] Add Web Audio API waveform visualization to frontend recorder
- [ ] Replace Tauri `cpal` recording with MediaRecorder in web app
- [ ] Implement transcription result display (polling + real-time update)
- [ ] Add caching layer (KV) for repeated searches

### Phase 3: Group Planning (Weeks 5-7)
**Goal:** Full group planning from `group-planning-design.md` working**

- [ ] Implement groups CRUD (D1)
- [ ] Implement shareable link pattern (public + admin tokens)
- [ ] Deploy Durable Object for voting state
- [ ] Implement WebSocket endpoint for live voting
- [ ] Implement sweep-line calendar overlap algorithm
- [ ] Add Nylas calendar sync endpoint
- [ ] Implement SSE fallback for groups without WebSocket
- [ ] Add email notifications (Resend or Cloudflare Email)

### Phase 4: Polish (Weeks 8+)
**Goal:** Production-ready with good DX

- [ ] Add Sentry to frontend (keep existing setup)
- [ ] Add D1-backed error logging for agent pipeline
- [ ] Set up Cloudflare Analytics + Grafana dashboards
- [ ] Document deployment runbook
- [ ] Build Tauri companion app (thin wrapper)
- [ ] Performance test at 10K DAU scale
- [ ] Cost optimization pass

---

## 11. Decision Tradeoff Analysis

> This section walks through each decision with full context — not just cost, but feature implications, migration risk, and lock-in. Review with fresh eyes.

---

### Decision 1: Agent Pipeline — Coolify VPS vs Cloudflare Python Worker

This is the biggest architectural fork. It affects **every search request**, transcription quality, and your ability to iterate on the agent pipeline.

#### Option A: Coolify VPS (FastAPI, existing code, zero changes)

**What you get:**
- Your entire existing codebase runs as-is. `faster-whisper`, LangGraph, Tavily, Nylas, all 45 requirements — everything works.
- LangGraph checkpointing uses local SQLite on the VPS — no proxy needed.
- `faster-whisper` runs on CPU (no GPU needed for short audio clips). Quality is identical to your current setup.
- You control the server. SSH in, `docker logs`, `htop`, `curl localhost:8000/health` — full observability.
- Coolify manages SSL, Git deploys, rollbacks, health checks.

**What you give up:**
- One more server to manage (even with Coolify, it's a VPS). If Hetzner has an outage, your agent pipeline is down.
- Cold start if the VPS sleeps (Coolify can keep it warm, but it's not serverless).
- Not "edge-native" — requests from the Cloudflare Workers layer travel to one region (EU for Hetzner).
- Latency: ~50-200ms extra round-trip from Workers → VPS → Workers.

**What you gain (with Cloudflare Queues):**
- **Backpressure protection:** Queue absorbs traffic spikes. If 50 users record simultaneously, the VPS processes at its own pace (2-4 concurrent). The rest wait in the queue.
- **Controlled throughput:** `max_concurrency` on the queue consumer limits how many requests hit the VPS at once. Prevents OOM crashes.
- **Automatic retries:** Failed transcriptions retry with exponential backoff (1s → 2s → 4s). No manual intervention needed.
- **Dead Letter Queue:** Jobs that fail after max retries go to a DLQ. Stored in D1 for manual review. Users get notified of failures.
- **Job status tracking:** Users poll `/api/jobs/:id/status` or receive real-time updates via Durable Objects. No hanging HTTP connections.
- **Extensible pattern:** Same queue architecture works for search, calendar sync, and email notifications.

**Cost:** €4.49/mo (Hetzner CX21) — fixed, regardless of traffic.

**Lock-in risk:** Near zero. FastAPI on Docker runs anywhere. Moving to Railway, Render, Fly.io, or Cloudflare Containers later is a one-line change.

**Risk level:** LOW. This is the safest option.

---

#### Option B: Cloudflare Python Worker (Pyodide WASM)

**What you get:**
- Fully edge-native. No VPS, no server management, no Docker.
- Memory snapshots at deploy time cut cold starts to ~1s (vs 2-5s for a VPS waking up).
- 100% managed by Cloudflare. Zero ops.
- Native Cloudflare bindings (D1, KV, R2, Queues) — no HTTP round-trips for state.

**What you give up (these are real constraints):**

| Constraint | Impact on EventFinder | Severity |
|---|---|---|
| **`faster-whisper` won't run** (C++ extension, no WASM build) | Must switch to Whisper API, Deepgram, or AssemblyAI for transcription | HIGH |
| **Pyodide runs 3-5x slower than native Python** (WASM translation) | LangGraph orchestration + LLM calls will be slower, but network-bound so CPU impact is moderate | MEDIUM |
| **128 MB memory limit per isolate** | LangChain + LangGraph + OpenAI SDK + httpx + tavily-python = ~50-80MB. Fits, but tight. Any memory leak = crash | MEDIUM |
| **No threads, no multiprocessing, no sockets** | `asyncio` works but with limitations. No parallel processing for batch jobs | MEDIUM |
| **Worker bundle size limit: 10MB compressed** | Your `requirements.txt` with langgraph, langchain, openai, tavily, faster-whisper, nylas, etc. will likely exceed 10MB compressed. Must split across Workers or trim dependencies | HIGH |
| **Recent Pyodide versions removed polars, pyarrow, duckdb** | Not directly relevant to EventFinder, but signals ecosystem instability | LOW |
| **Regional deployment requires enterprise plan** | You can't pin your Python Worker to a specific region. Data sovereignty compliance is harder | MEDIUM |
| **CPU time limit: 5 min max on paid plan** | Agent pipeline can take 2-10s per search. Well within limit, but you're consuming CPU time budget | LOW |

**Cost:** ~$0-5/mo for Workers compute + $0.006/min for Whisper API (replacing faster-whisper).

**Lock-in risk:** MEDIUM. Cloudflare Python Workers are a relatively new product (2024). The Pyodide ecosystem is less mature than native Python. If Cloudflare changes Pyodide support or removes a library you depend on, you'll need to rewrite.

**Risk level:** MEDIUM-HIGH. The `faster-whisper` incompatibility alone means you'd need to rewrite the transcription module. The bundle size limit means you'd need to split the agent pipeline into multiple Workers (one for search, one for transcription, one for calendar).

---

#### Verdict

| Factor | Coolify VPS | Cloudflare Python Worker |
|---|---|---|
| Cost | €4.49/mo fixed | ~$0-5/mo + Whisper API |
| Code changes | Zero | Significant (Whisper, bundle split) |
| Migration risk | None | Medium-high |
| Ops burden | Low (Coolify manages) | None |
| Latency | +50-200ms | Edge-native |
| Whisper quality | `faster-whisper` (local, free) | Whisper API (cloud, $0.006/min) |
| LangGraph support | Full | Partial (bundle size, memory) |
| Lock-in risk | Near zero | Medium |
| **Overall** | **Recommended** | **Not recommended for v1** |

**Bottom line:** The Cloudflare Python Worker option is a **cost decision only** (saves ~$5/mo vs VPS). The **feature cost** is: rewriting transcription, splitting your agent pipeline into multiple Workers, accepting bundle size limits, and depending on a relatively new product. The €4.49/mo VPS is not worth the engineering time to avoid.

**Migration path:** Start with Coolify. If Cloudflare Python Workers mature (better library support, larger bundle limits), the swappable adapter pattern means you can switch later with zero frontend changes.

---

### Decision 2: Transcription — `faster-whisper` (local) vs Cloud Transcription API

This decision is tightly coupled with Decision 1. If you choose Coolify VPS, `faster-whisper` works. If you choose Cloudflare Python Workers, you must use a cloud API.

#### Option A: Keep `faster-whisper` on Coolify VPS (with Queue)

**What you get:**
- Zero code changes. Your existing `transcription/transcriber.py` works as-is.
- Free transcription (no per-minute cost). At 100 transcriptions/day × 30s each = 50 min/day = 25 hours/month. That's $1.50/mo on Whisper API — not huge, but it adds up.
- Privacy: audio never leaves your server.
- Offline capability: works even if OpenAI/Deepgram is down.
- Quality: `faster-whisper` with `large-v3` model is state-of-the-art.
- **Queue protection:** Cloudflare Queues ensures the VPS never gets overwhelmed. Traffic spikes are absorbed, failures are retried, dead letters are tracked.

**What you give up:**
- VPS memory: `faster-whisper` with `large-v3` model uses ~2-3GB RAM. On a 4GB VPS, that leaves ~1GB for FastAPI + LangGraph. Tight but workable.
- `medium` model uses ~1GB RAM — safer for a 4GB VPS.
- Startup time: loading the Whisper model on cold start takes 5-10s.
- Async flow: users don't get immediate results. They poll `/api/jobs/:id/status` or wait for a Durable Object notification.

**Cost:** $0 (included in VPS cost).

---

#### Option B: Cloud Transcription API (Whisper API / Deepgram / AssemblyAI)

**Pricing comparison:**

| Provider | Cost/min | Languages | Diarization | Quality |
|---|---|---|---|---|
| OpenAI Whisper API | $0.006 | 99+ | No | Excellent (Whisper) |
| Deepgram | $0.0043 | 36 | Yes | Excellent (custom model) |
| AssemblyAI | $0.01 | 99+ | Yes | Excellent (custom model) |
| Groq Whisper | $0.002 | 99+ | No | Good (large-v3) |

**At 100 transcriptions/day × 30s average:**
- OpenAI Whisper API: $0.90/mo
- Deepgram: $0.65/mo
- AssemblyAI: $1.50/mo
- Groq: $0.30/mo

**What you get:**
- No model loading on the VPS (saves 2-3GB RAM).
- Faster transcription (cloud GPUs vs VPS CPU).
- No dependency on C++ extensions in your deployment.
- Required if you choose Cloudflare Python Workers.

**What you give up:**
- Per-minute cost (small but non-zero).
- Audio data leaves your infrastructure.
- Dependency on a third-party API's uptime.
- Groq is cheapest but quality is lower than Whisper API's managed service.

---

#### Verdict

| Factor | `faster-whisper` (local) | Cloud API |
|---|---|---|
| Cost | $0 | $0.30-1.50/mo |
| RAM usage | 1-3GB on VPS | 0 |
| Code changes | Zero | Small (swap API call) |
| Privacy | Audio stays local | Audio sent to API |
| Quality | `large-v3` = best | Depends on provider |
| Required for | Coolify VPS | Cloudflare Python Worker |
| **Overall** | **Recommended with Coolify** | **Required for Cloudflare Python** |

**Bottom line:** This decision is **forced by Decision 1**. If you choose Coolify (recommended), keep `faster-whisper`. If you choose Cloudflare Python Workers, you must use a cloud API. The cost difference is negligible ($0 vs $0.30-1.50/mo), so the real question is whether you want the RAM savings vs the privacy/offline benefits.

---

### Decision 3: Notifications — Email Provider

EventFinder needs email for: group invites, vote reminders, event finalization notifications.

#### Option A: Resend (Recommended)

**What you get:**
- 3,000 emails/month free (enough for launch).
- React Email integration — write email templates as React components.
- Best-in-class developer experience. Setup in 5 minutes.
- Clean API, modern dashboard, good deliverability.
- $20/mo for 50K emails after free tier.

**What you give up:**
- No visual template editor (code-only, but React Email is great for this).
- Less mature than SendGrid at massive scale (but you're not there yet).

**Cost:** $0 initially, $20/mo at 50K emails/month.

---

#### Option B: Cloudflare Email Routing

**What you get:**
- Free, included with your Cloudflare account.
- Email forwarding (receive emails at your domain, forward to Gmail).

**What you give up:**
- **Cloudflare Email Routing is NOT a transactional email service.** It forwards incoming emails — it doesn't send outgoing transactional emails.
- No API for sending emails programmatically.
- No templates, no analytics, no webhooks.

**Verdict:** Not suitable for EventFinder's needs. Cloudflare Email Routing is for receiving, not sending.

---

#### Option C: SendGrid

**What you get:**
- 100 emails/day free (~3K/month).
- Enterprise-grade deliverability, battle-tested at massive scale.
- Visual template editor (Handlebars-based).
- Advanced analytics, A/B testing, marketing suite.

**What you give up:**
- Dated developer experience. Complex API, confusing documentation.
- $19.95/mo for 50K emails (similar to Resend, worse DX).
- Owned by Twilio — enterprise pricing can surprise you.

---

#### Verdict

| Factor | Resend | Cloudflare Email | SendGrid |
|---|---|---|---|
| Free tier | 3K/mo | N/A (not for sending) | 3K/mo |
| DX | Excellent | N/A | Dated |
| React templates | Native | N/A | No |
| Cost at 50K/mo | $20 | N/A | $20 |
| Setup time | 5 min | N/A | 30+ min |
| **Overall** | **Recommended** | **Not suitable** | **Overkill** |

**Bottom line:** Resend is the clear choice. Cloudflare Email Routing doesn't do transactional sending. SendGrid is enterprise-grade but has worse DX and no advantages at EventFinder's scale.

---

### Decision 4: v1 Scope — What Ships First

#### Option A: Minimum (Auth + Search + Transcription)

**Includes:** Clerk auth, Next.js frontend, Cloudflare Workers API, Coolify agent pipeline, event search, voice transcription.

**Excludes:** Group planning, voting, calendar sync, notifications, Durable Objects.

**Time to ship:** 3-4 weeks.

**Pros:** Fastest path to a usable product. Validates the core value proposition (voice → event discovery).

**Cons:** No group features — the "shareable plans + voting" is what differentiates EventFinder from a search engine. Without it, it's just a voice-powered event search.

---

#### Option B: Standard (Minimum + Group Planning + Voting)

**Includes:** Everything in Minimum, plus groups, shareable links, Durable Objects for real-time voting, calendar overlap.

**Excludes:** Email notifications, calendar sync via Nylas, Tauri companion app.

**Time to ship:** 6-8 weeks.

**Pros:** Ships the full product vision. Group voting is the differentiator.

**Cons:** More complex. Durable Objects + WebSockets add operational complexity.

---

#### Option C: Full (Everything)

**Includes:** All of the above, plus Nylas calendar sync, email notifications, Tauri companion app, full observability.

**Time to ship:** 10-12 weeks.

**Pros:** Complete product.

**Cons:** Longest time to market. Risk of building features nobody uses.

---

#### Verdict

**Recommended: Option B (Standard).** The group planning feature is what makes EventFinder unique. Without it, you're building a voice-powered search engine — interesting, but not defensible. The minimum viable product should include at least the core differentiator (group voting). Calendar sync and email notifications can be Phase 4 additions.

---

### Decision 5: Tauri Desktop — Deprecate, Sync, or Archive

#### Option A: Deprecate (Web is Primary)

**What it means:** The web app becomes the main product. The Tauri code is kept as-is but not actively maintained. Users who want the desktop experience can use the existing Tauri app, but it points to the new Cloudflare API.

**Pros:** Zero maintenance overhead. Web app gets all your attention.

**Cons:** Desktop users get a stale experience. If the API changes significantly, the Tauri app breaks.

---

#### Option B: Keep in Sync

**What it means:** Every web feature gets a Tauri equivalent. The Tauri app mirrors the web app's functionality.

**Pros:** Best desktop experience. Global shortcut, native audio quality, offline capability.

**Cons:** 2x development effort. Every feature needs web + desktop implementations.

---

#### Option C: Thin Companion (Recommended)

**What it means:** The Tauri app becomes a thin wrapper around the Cloudflare API. It handles:
- Native audio recording (cpal — better than browser MediaRecorder)
- Global shortcut (Alt+E)
- System tray presence
- Everything else is the same API calls as the web app

**Pros:** Desktop users get native audio quality + global shortcut. Minimal maintenance (just HTTP calls + audio recording).

**Cons:** Still some maintenance overhead, but much less than full sync.

---

#### Verdict

| Factor | Deprecate | Keep in Sync | Thin Companion |
|---|---|---|---|
| Dev effort | Zero | 2x | 0.2x |
| Desktop UX | Stale | Best | Good |
| Maintenance | None | High | Low |
| **Overall** | **Too aggressive** | **Too expensive** | **Recommended** |

**Bottom line:** The thin companion approach gives you the best of both worlds. The Tauri app becomes ~200 lines of Rust (audio recording + HTTP client + global shortcut) instead of the current full-stack application.

---

### Decision 6: Observability — How Much

#### Option A: Minimal (Cloudflare Built-in)

**What you get:** Cloudflare's free analytics dashboard (request counts, error rates, latency percentiles). Workers Logs for debugging.

**What you lose:** No error tracking, no performance tracing, no custom dashboards.

**Cost:** $0.

---

#### Option B: Standard (Cloudflare + Sentry)

**What you get:** Everything in Minimal, plus Sentry for frontend error tracking (keep existing `@sentry/react` setup). D1-backed error log table for Python backend errors.

**What you lose:** No custom Grafana dashboards, no LangSmith agent tracing.

**Cost:** $0 (Sentry free tier: 5K errors/month).

---

#### Option C: Full (Everything)

**What you get:** Everything in Standard, plus Grafana + Cloudflare Metrics API, LangSmith for agent tracing, Prometheus for Coolify VPS metrics.

**Cost:** $0-25/mo (LangSmith, Grafana Cloud free tier).

---

#### Verdict

**Recommended: Option B (Standard).** Sentry for frontend errors is essential. D1 error log for the Python backend is cheap and effective. Grafana + LangSmith can wait until you have real traffic to monitor.

---

## 12. Key Decisions Needed

## 13. Summary of Recommendations

| Decision | Recommendation | Rationale |
|---|---|---|
| **Agent Pipeline** | Coolify VPS (€4.49/mo) | Zero code changes, full Python support, `faster-whisper` works. Cloudflare Queues provides backpressure, retries, and dead-letter handling |
| **Transcription** | Keep `faster-whisper` on VPS | Free, best quality, works with Coolify. Cloud API only needed if you choose Cloudflare Python Workers |
| **Email** | Resend | Best DX, 3K free/mo, React Email. Cloudflare Email Routing can't send transactional emails |
| **v1 Scope** | Standard (auth + search + groups + voting) | Group voting is the differentiator. Without it, it's just a voice search engine |
| **Tauri Desktop** | Thin companion app | ~200 lines of Rust. Native audio + global shortcut, minimal maintenance |
| **Observability** | Standard (Sentry + D1 error log) | Essential error tracking. Grafana can wait until real traffic |

**Total recommended monthly cost: ~$10-15/mo** (Coolify €4.49 + Resend $0 initially + Clerk $0 initially + Cloudflare ~$0-5)

---

## 14. Appendix: File Structure

```
event_searcher/
├── web/                           # NEW: Next.js frontend (Cloudflare Pages)
│   ├── src/
│   │   ├── app/                   # Next.js App Router
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx           # Landing/home
│   │   │   ├── search/page.tsx
│   │   │   ├── groups/page.tsx
│   │   │   ├── groups/[id]/page.tsx
│   │   │   └── api/               # Server Actions / Route Handlers
│   │   ├── components/
│   │   │   ├── VoiceRecorder.tsx  # MediaRecorder-based (replaces Tauri)
│   │   │   ├── Waveform.tsx       # Web Audio API visualization
│   │   │   ├── EventCard.tsx
│   │   │   ├── GroupVoting.tsx    # Durable Object WebSocket client
│   │   │   └── ...
│   │   ├── lib/
│   │   │   ├── agent.ts           # Agent service adapter (swappable)
│   │   │   ├── api.ts             # API client
│   │   │   └── durableObjects.ts  # WebSocket client
│   │   └── instrumentation.ts     # Sentry
│   ├── middleware.ts              # Clerk auth middleware
│   ├── wrangler.toml
│   └── package.json
│
├── workers/                       # NEW: Cloudflare Workers (TypeScript API)
│   ├── api/                       # Main API Worker
│   │   ├── src/
│   │   │   ├── index.ts           # Hono app entry
│   │   │   ├── routes/
│   │   │   │   ├── search.ts
│   │   │   │   ├── groups.ts
│   │   │   │   ├── votes.ts
│   │   │   │   ├── calendar.ts
│   │   │   │   ├── transcription.ts  # Enqueue jobs
│   │   │   │   └── jobs.ts           # Job status polling
│   │   │   ├── middleware/
│   │   │   │   ├── auth.ts        # Clerk JWT verification
│   │   │   │   └── rateLimit.ts
│   │   │   ├── services/
│   │   │   │   └── agent.ts      # Agent pipeline adapter (swappable)
│   │   │   └── durableObjects/
│   │   │       └── voting.ts      # Durable Object for voting
│   │   └── wrangler.toml
│   │
│   ├── transcription-consumer/    # Queue Consumer Worker
│   │   ├── src/index.ts           # Processes transcription jobs
│   │   └── wrangler.toml
│   │
│   ├── dlq-consumer/              # Dead Letter Queue Consumer
│   │   ├── src/index.ts           # Handles failed jobs
│   │   └── wrangler.toml
│   │
│   └── clerk-webhook/             # Clerk webhook Worker
│       ├── src/index.ts
│       └── wrangler.toml
│
├── agent/                         # NEW: Agent pipeline (existing FastAPI code)
│   ├── src/                       # Copy of existing src/ (FastAPI)
│   │   ├── api.py
│   │   ├── orchestration/
│   │   ├── discovery_agent/
│   │   ├── calendar_agent/
│   │   ├── auditor/
│   │   └── transcription/
│   ├── Dockerfile.prod            # Existing Dockerfile (works with Coolify)
│   ├── docker-compose.yml        # For local dev (unchanged)
│   └── requirements.txt          # Existing (unchanged)
│
├── infra/                         # NEW: Infrastructure as code
│   ├── d1/
│   │   └── migrations/
│   │       ├── 0001_init.sql
│   │       └── ...
│   ├── r2/
│   │   └── cors.json
│   └── wrangler.toml             # Root wrangler config
│
├── tauri_frontend/               # Keep as-is initially, refactor in Phase 4
│   ├── src/                       # React frontend (will migrate to web/)
│   ├── src-tauri/                # Rust backend (will become thin companion)
│   └── ...
│
├── src/                          # CURRENT FastAPI backend (deprecate after migration)
│   ├── api.py
│   ├── ...
│
├── docs/                         # Keep existing
├── tests/                        # Keep existing, add Worker tests
│
├── .env.example                  # Update with Cloudflare + Clerk vars
├── Makefile                      # Update with new commands
├── docker-compose.yml            # Deprecate after migration
└── README.md                      # Update with new architecture
```

---

*Plan created: March 2026. Cloudflare and Clerk pricing/features are subject to change. Verify current docs at developers.cloudflare.com and clerk.com/pricing before implementation.*
