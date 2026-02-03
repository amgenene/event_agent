# Orchestration (Manager Agent)

## Overview
Manages the 5-step workflow loop and handles state transitions between agents.

## The 5-Step Loop
1. **Ingestion:** Converts voice to structured intent (JSON)
2. **Constraint Check:** Scans user's calendar for availability gaps
3. **Discovery:** Searches live web sources for events with $0 price tag
4. **Verification (Auditor):** Confirms event is free and user can arrive on time
5. **Relaxation (Edge Case Handler):** If 0 results, broadens search and restarts

## Key Responsibilities
- Route workflow through agent nodes
- Handle node failures and backtracking
- Manage session state
- Coordinate between components
- Implement retry logic with parameter adjustment

## State Management
- Store session state in Redis
- Maintain agent decision history
- Track parameter adjustments for relaxation
