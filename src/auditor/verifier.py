"""Auditor agent for verifying events are truly free."""

from enum import Enum


class EventStatus(Enum):
    """Status of event verification."""
    
    FREE = "FREE"
    PAID = "PAID"
    CONDITIONAL = "CONDITIONAL"
    UNKNOWN = "UNKNOWN"


class Auditor:
    """Verifies events are truly free using LLM analysis."""
    
    def __init__(self, llm_client=None):
        """
        Initialize auditor.
        
        Args:
            llm_client: LLM client for analysis (e.g., OpenAI)
        """
        self.llm_client = llm_client
        self.cost_indicators = [
            "ticket",
            "pay",
            "paid entry",
            "cover charge",
            "admission",
            "suggested donation",
            "drink minimum",
            "cost",
            "price",
            "fee"
        ]
    
    def verify_event_free(self, event_description: str) -> EventStatus:
        """
        Verify if an event is actually free.
        
        Args:
            event_description: Event description to analyze
        
        Returns:
            EventStatus indicating if event is free, paid, or conditional
        """
        if not event_description:
            return EventStatus.UNKNOWN
        
        # Quick check for cost indicators
        lower_desc = event_description.lower()
        
        for indicator in self.cost_indicators:
            if indicator in lower_desc:
                # Check context to distinguish "free tickets" from "pay for tickets"
                if "free" in lower_desc and indicator == "ticket":
                    continue
                return EventStatus.PAID
        
        # Would use LLM for more nuanced analysis
        # return self._analyze_with_llm(event_description)
        
        return EventStatus.FREE
    
    def _analyze_with_llm(self, event_description: str) -> EventStatus:
        """Use LLM to analyze event description for hidden costs."""
        if not self.llm_client:
            return EventStatus.UNKNOWN
        
        prompt = f"""Analyze this event description: '{event_description}'.
        Identify if there is any mention of:
        - Tickets
        - Paid entry
        - Drink minimums
        - Suggested donations
        - Cover charges
        
        Return 'FREE', 'PAID', or 'CONDITIONAL'."""
        
        # response = self.llm_client.invoke(prompt)
        # return EventStatus[response]
        
        return EventStatus.UNKNOWN
    
    def get_warnings(self, event_description: str) -> list[str]:
        """
        Get warnings about potential hidden costs.
        
        Args:
            event_description: Event description to analyze
        
        Returns:
            List of warning messages
        """
        warnings = []
        lower_desc = event_description.lower()
        
        if "suggested donation" in lower_desc:
            warnings.append("Event includes suggested donation")
        
        if "drink minimum" in lower_desc:
            warnings.append("Event has drink minimum requirement")
        
        if "cover charge" in lower_desc:
            warnings.append("Event has cover charge")
        
        if "membership" in lower_desc:
            warnings.append("Event may require membership")
        
        return warnings
