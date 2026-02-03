# 📅 EventFinder AI: Complete Technical Architecture

## 1. System Overview
EventFinder is an autonomous, multi-agent concierge designed to turn natural language voice commands into a verified, conflict-free itinerary of **free** events. It mimics the "Super Whisper" user experience but operates with the complex orchestration of a professional booking agent.

---

## 2. High-Level Agentic Workflow
The system consists of a **Desktop Application** for user interaction and a backend **State Graph** architecture. If any node (Search, Calendar, or Audit) fails, the "Manager" agent routes the flow back to a previous state to adjust parameters.



### The 5-Step Loop:
1.  **Ingestion:** Converts voice to structured intent (JSON).
2.  **Constraint Check:** Scans the user's calendar for availability gaps.
3.  **Discovery:** Searches live web sources for events with a `$0` price tag.
4.  **Verification (The Auditor):** Confirms the event is actually free and the user can arrive on time.
5.  **Relaxation (Edge Case Handler):** If 0 results are found, the agent broadens the search and restarts.

---

## 3. Detailed Component Breakdown

### A. The Frontend (User Interface)
* **Tech:** Tauri, React, Typescript.
* **Task:** Captures voice commands, displays real-time agent status, and renders the final itinerary.

### B. The Input Parser (The "Whisper" Layer)
* **Tech:** OpenAI Whisper-v3 or Deepgram for STT.
* **Task:** Uses an LLM to map prose to a query schema.
* **Edge Case:** If the input is vague (e.g., "Find me stuff"), it defaults to the user's "Home City" and "Favorite Genres" stored in the database.

### B. The Discovery Agent (Live Search)
* **Tech:** Tavily AI or Exa.ai.
* **Strategy:** Instead of generic search, it uses a "Domain-Specific" crawl:
    * `site:eventbrite.com "free"`
    * `site:meetup.com "no cover charge"`
    * `"open to public" + "no tickets required"`

### C. The Calendar Agent (The Logic Gap)
* **Tech:** Nylas API (Unified Google/Outlook/iCloud access).
* **Constraint Logic:** * Calculates `Meeting_End_Time` + `Transit_Time` (via Google Maps API).
    * If the travel time exceeds the user's "Max Transit" preference, the event is discarded even if it's free.

---

## 4. Resilience & Edge Case Matrix

| Failure Mode | Agent Response | Relaxation Strategy |
| :--- | :--- | :--- |
| **Zero Results** | `RelaxationNode` | 1. Expand search radius (e.g., 5mi -> 15mi).<br>2. Broaden category (e.g., "Jazz" -> "Live Music"). |
| **Schedule Conflict** | `CalendarNode` | Look for "Drop-in" events where being 30 minutes late is acceptable. |
| **Hidden Costs** | `AuditorNode` | LLM scans the event description for "suggested donation" or "drink minimum" and warns the user. |
| **API Timeout** | `ManagerNode` | Failover to a secondary search engine (e.g., switch from SerpApi to Tavily). |

---

## 5. Technical Stack

* **Frontend:** **Tauri + React** (Native-feeling desktop app).
* **Orchestration:** **LangGraph** (Critical for handling the "Loop back" logic).
* **STT:** **Deepgram Aura** (Optimized for speed/latency).
* **Calendar API:** **Nylas** (One integration for all calendar providers).
* **Web Search:** **Tavily AI** (Built for LLMs, filters out SEO/Ads).
* **State/Memory:** **Redis** (To store the session state while the agent "thinks").

---

## 6. Verification Logic (The "Auditor" Prompt)
To ensure the PoC stays "Free," the Auditor Agent uses the following logic gate:

```python
def verify_event_free(event_description):
    """
    LLM-powered check to ensure no hidden costs.
    """
    prompt = f"Analyze this event description: '{event_description}'. 
              Identify if there is any mention of:
              - Tickets
              - Paid entry
              - Drink minimums
              - Suggested donations
              Return 'FREE' or 'PAID'."
    return llm.invoke(prompt)