# Auditor (Verification Logic)

## Overview
Ensures events are truly free by analyzing event descriptions for hidden costs.

## Verification Logic
LLM-powered verification that scans for:
- Ticket requirements
- Paid entry fees
- Drink minimums
- Suggested donations

## Key Functions
- Parse event descriptions
- Identify hidden cost indicators
- Confirm free event status
- Flag questionable events with warnings

## Implementation
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
```
