"""Edge case handler for resilience and search relaxation."""

from enum import Enum
from dataclasses import dataclass


class FailureMode(Enum):
    """Types of failures that can occur."""
    
    ZERO_RESULTS = "zero_results"
    SCHEDULE_CONFLICT = "schedule_conflict"
    HIDDEN_COSTS = "hidden_costs"
    API_TIMEOUT = "api_timeout"


@dataclass
class RelaxationStrategy:
    """Strategy for relaxing search constraints."""
    
    failure_mode: FailureMode
    action: str
    description: str


class EdgeCaseHandler:
    """Handles failures and implements relaxation strategies."""
    
    def __init__(self):
        """Initialize edge case handler."""
        self.strategies = {
            FailureMode.ZERO_RESULTS: [
                RelaxationStrategy(
                    FailureMode.ZERO_RESULTS,
                    "expand_radius",
                    "Expand search radius (e.g., 5mi -> 15mi)"
                ),
                RelaxationStrategy(
                    FailureMode.ZERO_RESULTS,
                    "broaden_category",
                    "Broaden category (e.g., 'Jazz' -> 'Live Music')"
                ),
            ],
            FailureMode.SCHEDULE_CONFLICT: [
                RelaxationStrategy(
                    FailureMode.SCHEDULE_CONFLICT,
                    "find_dropins",
                    "Look for 'Drop-in' events where being 30 minutes late is acceptable"
                ),
            ],
            FailureMode.API_TIMEOUT: [
                RelaxationStrategy(
                    FailureMode.API_TIMEOUT,
                    "failover_search",
                    "Failover to secondary search engine"
                ),
            ],
        }
    
    def handle_zero_results(self, search_params: dict) -> dict:
        """
        Handle case where search returns no results.
        
        Args:
            search_params: Current search parameters
        
        Returns:
            Relaxed search parameters
        """
        relaxed_params = search_params.copy()
        
        # Expand radius
        current_radius = relaxed_params.get("radius_miles", 5)
        relaxed_params["radius_miles"] = min(current_radius * 3, 50)
        
        return relaxed_params
    
    def handle_schedule_conflict(self, event, calendar_events: list) -> bool:
        """
        Handle case where event conflicts with calendar.
        
        Args:
            event: Event that has conflict
            calendar_events: User's calendar events
        
        Returns:
            True if event is acceptable with relaxed criteria, False otherwise
        """
        # For drop-in events, allow 30-minute grace period
        event_flexible = hasattr(event, "is_dropin") and event.is_dropin
        
        return event_flexible
    
    def handle_api_timeout(self, failed_api: str) -> str:
        """
        Handle API timeout with failover.
        
        Args:
            failed_api: Name of API that timed out
        
        Returns:
            Name of failover API to use
        """
        failover_map = {
            "tavily": "exa",
            "exa": "tavily",
            "google_maps": "open_routes",
            "nylas": "caldav"
        }
        
        return failover_map.get(failed_api, "unknown")
    
    def get_relaxation_strategies(self, failure_mode: FailureMode) -> list[RelaxationStrategy]:
        """
        Get available relaxation strategies for a failure mode.
        
        Args:
            failure_mode: The type of failure
        
        Returns:
            List of available strategies
        """
        return self.strategies.get(failure_mode, [])
