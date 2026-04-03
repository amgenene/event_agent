# EventFinder AI

## The Problem

Planning events with friends is fragmented. You juggle group chats, cross-reference calendars, search multiple platforms for what's happening, and still end up with no plan. The friction isn't finding events — it's coordinating people.

## The Solution

**EventFinder AI** is an autonomous event planning assistant that discovers what's happening near you, checks everyone's availability, and surfaces verified options your whole group can actually attend. Voice it, type it, or let the agent work in the background.

Think of it as a personal concierge that handles the entire flow: discovery, scheduling, verification, and group coordination — in one shot.

---

## How It Works

Powered by **LangGraph**, the system orchestrates specialized agents in a resilient state machine:

1. **Intent Parsing** — Natural language input (voice or text) is converted into structured search intent using LLM extraction
2. **Availability Check** — Nylas scans all participants' calendars to find overlapping free time windows
3. **Event Discovery** — Tavily AI searches event platforms (Eventbrite, Meetup, Luma) with domain targeting and date-aware filtering
4. **Verification** — An LLM-powered auditor confirms events are accurately described and flags hidden costs
5. **Resilience Loop** — If results don't match criteria, the agent automatically broadens parameters and retries

---

## What Makes It Different

| | Traditional Approach | EventFinder AI |
|---|---|---|
| **Discovery** | Manually browse 3-4 platforms | Single query across all platforms |
| **Scheduling** | "When are you free?" group chat | Automatic calendar overlap detection |
| **Verification** | Show up and find out | LLM audits event details beforehand |
| **Coordination** | Endless back-and-forth | Shareable plans with group voting |
| **Fallback** | Give up and stay in | Agent relaxes constraints and retries |

---

## Technical Architecture

- **Orchestration:** LangGraph state machine with backtracking and resilience
- **Search:** Tavily AI with domain targeting, content extraction, and date filtering
- **Calendars:** Nylas unified API (Google, Outlook, iCloud)
- **LLM:** OpenAI for intent parsing and event verification
- **Frontend:** Tauri + React desktop app
- **Backend:** FastAPI with PostgreSQL and Redis
- **Deployment:** Docker Compose — one command to run everything

---

## Roadmap

### Now
- [x] Multi-agent orchestration with LangGraph
- [x] Tavily-powered event discovery with domain targeting
- [x] LLM-powered intent parsing and event verification
- [x] Multi-participant calendar availability via Nylas
- [x] Containerized deployment (Docker Compose)
- [x] Full test suite (115 tests)

### Next
- [ ] Group planning with shareable links and voting
- [ ] Real-time coordination via WebSocket
- [ ] Persistent agent mode for proactive event alerts
- [ ] Mobile-responsive web view for plan sharing
- [ ] Email and push notification invitations
