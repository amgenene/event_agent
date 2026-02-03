# Technical Stack

## Core Technologies

### Orchestration
* **LangGraph** - Critical for handling "loop back" logic and state management

### Speech-to-Text (STT)
* **Deepgram Aura** - Optimized for speed and latency

### Calendar Integration
* **Nylas** - Unified access to Google/Outlook/iCloud calendars

### Web Search
* **Tavily AI** - Built for LLMs, filters out SEO and ads

### State & Memory
* **Redis** - Stores session state while agent processes requests

### Maps & Travel
* **Google Maps API** - Calculate travel times between locations

## Architecture Pattern
* **State Graph** - Routes workflow with backtracking on failures
* **Multi-Agent System** - Coordinated agents for specialized tasks
* **Resilience-First Design** - Built-in relaxation strategies for edge cases
