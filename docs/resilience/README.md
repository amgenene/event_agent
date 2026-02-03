# Resilience & Edge Case Matrix

## Overview
Handles failure modes and implements relaxation strategies for edge cases.

## Failure Modes & Responses

| Failure Mode | Agent Response | Relaxation Strategy |
| :--- | :--- | :--- |
| **Zero Results** | `RelaxationNode` | 1. Expand search radius (e.g., 5mi -> 15mi).<br>2. Broaden category (e.g., "Jazz" -> "Live Music"). |
| **Schedule Conflict** | `CalendarNode` | Look for "Drop-in" events where being 30 minutes late is acceptable. |
| **Hidden Costs** | `AuditorNode` | LLM scans the event description for "suggested donation" or "drink minimum" and warns the user. |
| **API Timeout** | `ManagerNode` | Failover to a secondary search engine (e.g., switch from SerpApi to Tavily). |

## Key Functions
- Monitor agent failures
- Trigger relaxation strategies
- Iterate search with adjusted parameters
- Provide user feedback on adjustments
