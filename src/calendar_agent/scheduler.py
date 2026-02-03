"""Calendar agent for checking availability and travel time constraints."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from src.services.calendar_service import CalendarService


@dataclass
class CalendarEvent:
    """Represents a calendar event."""
    
    id: str
    title: str
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None


class CalendarAgent:
    """Manages calendar integration and scheduling constraints."""
    
    def __init__(self, participants: list[str]):
        """
        Initialize calendar agent.
        
        Args:
            participants: List of participant email addresses
        """
        self.calendar_service = CalendarService()
        self.participants = participants
    
    def get_calendar_availability(self) -> list:
        """
        Fetch calendar availability for the current week.
        
        Returns:
            List of dicts with 'start_time', 'end_time', and 'emails' keys
        """
        return self.calendar_service.get_availability(self.participants)
    
    def validate_travel_time(
        self,
        travel_time_minutes: int,
        max_transit_minutes: int
    ) -> bool:
        """
        Validate that user can reach event with travel time.
        
        Args:
            travel_time_minutes: Actual travel time in minutes
            max_transit_minutes: Maximum acceptable transit time
        
        Returns:
            True if event is reachable in time, False otherwise
        """
        return travel_time_minutes <= max_transit_minutes
