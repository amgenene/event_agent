# Discovery Agent (Live Search)

## Overview
Searches live web sources for free events using domain-specific crawling strategies.

## Technology
* **Primary:** Tavily AI
* **Secondary:** Exa.ai (for failover)

## Search Strategy
Implements domain-specific crawling instead of generic search:
- `site:eventbrite.com "free"`
- `site:meetup.com "no cover charge"`
- `"open to public" + "no tickets required"`

## Key Functions
- Query event discovery APIs
- Filter results by location and genre
- Identify high-confidence free events
- Handle API timeouts with fallbacks
