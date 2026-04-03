"""Auditor agent for verifying events are truly free."""

import json
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class EventStatus(Enum):
    """Status of event verification."""

    FREE = "FREE"
    PAID = "PAID"
    CONDITIONAL = "CONDITIONAL"
    UNKNOWN = "UNKNOWN"


class Auditor:
    """Verifies events are truly free using LLM analysis."""

    COST_INDICATORS = [
        "pay",
        "paid entry",
        "cover charge",
        "admission",
        "suggested donation",
        "drink minimum",
        "cost",
        "price",
        "fee",
    ]

    def __init__(self, llm_client=None):
        """
        Initialize auditor.

        Args:
            llm_client: LLM client for analysis (e.g., OpenAI)
        """
        self.llm_client = llm_client

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

        keyword_status = self._quick_keyword_check(event_description)

        if self.llm_client:
            try:
                llm_status = self._analyze_with_llm(event_description)
                if llm_status == EventStatus.UNKNOWN:
                    return keyword_status
                return llm_status
            except Exception as exc:
                logger.warning(
                    "LLM verification failed, falling back to keyword check: %s", exc
                )
                return keyword_status

        return keyword_status

    def _quick_keyword_check(self, event_description: str) -> EventStatus:
        """Fast keyword-based check as fallback or pre-screen."""
        lower_desc = event_description.lower()

        if any(
            phrase in lower_desc
            for phrase in [
                "free entry",
                "free admission",
                "no cover",
                "no charge",
                "free event",
                "open to the public",
            ]
        ):
            return EventStatus.FREE

        for indicator in self.COST_INDICATORS:
            if indicator in lower_desc:
                if "free" in lower_desc and indicator in ("ticket", "admission"):
                    continue
                if (
                    "no " + indicator in lower_desc
                    or "no " + indicator.split()[0] in lower_desc
                ):
                    continue
                return EventStatus.PAID

        return EventStatus.FREE

    def _analyze_with_llm(self, event_description: str) -> EventStatus:
        """Use LLM to analyze event description for hidden costs."""
        if not self.llm_client:
            return EventStatus.UNKNOWN

        prompt = (
            "You are an event cost analyzer. Examine this event description and determine "
            "if the event is truly free to attend. Look for hidden costs like suggested "
            "donations, drink minimums, membership requirements, or conditional pricing.\n\n"
            f"Event description: {event_description}\n\n"
            "Respond with ONLY a JSON object in this format:\n"
            '{"status": "FREE" | "PAID" | "CONDITIONAL", "reason": "brief explanation"}'
        )

        if hasattr(self.llm_client, "chat") and hasattr(
            self.llm_client.chat, "completions"
        ):
            response = self.llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=100,
            )
            content = response.choices[0].message.content.strip()
        elif hasattr(self.llm_client, "invoke"):
            response = self.llm_client.invoke(prompt)
            content = response if isinstance(response, str) else str(response)
        else:
            logger.warning("Unknown LLM client type: %s", type(self.llm_client))
            return EventStatus.UNKNOWN

        try:
            result = json.loads(content)
            status_str = result.get("status", "UNKNOWN").upper()
            reason = result.get("reason", "")
            logger.info("LLM auditor verdict: status=%s reason=%s", status_str, reason)
            return EventStatus[status_str]
        except (json.JSONDecodeError, KeyError, AttributeError):
            logger.warning("Failed to parse LLM response: %s", content)
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

        if "rsvp required" in lower_desc or "registration required" in lower_desc:
            warnings.append("Event requires RSVP or registration")

        if "limited capacity" in lower_desc or "limited seating" in lower_desc:
            warnings.append("Event has limited capacity")

        return warnings
