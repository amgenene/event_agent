# Calendar Agent (The Logic Gap)

## Overview
Checks calendar availability and validates travel time constraints.

## Technology
* **API:** Nylas API (unified Google/Outlook/iCloud access)
* **Travel Time:** Google Maps API

## Constraint Logic
- Calculates `Meeting_End_Time` + `Transit_Time`
- Discards events if travel time exceeds user's "Max Transit" preference
- Identifies availability gaps for event scheduling

## Key Functions
- Fetch user calendar events
- Calculate travel times between locations
- Validate scheduling constraints
- Handle timezone conversions
