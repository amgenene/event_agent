"""Manager agent orchestrating the 5-step event discovery workflow."""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class WorkflowStep(Enum):
    """Steps in the event discovery workflow."""
    
    INGESTION = "ingestion"
    CONSTRAINT_CHECK = "constraint_check"
    DISCOVERY = "discovery"
    VERIFICATION = "verification"
    RELAXATION = "relaxation"


@dataclass
class WorkflowState:
    """State of the workflow execution."""
    
    current_step: WorkflowStep
    user_input: str
    parsed_intent: Optional[dict] = None
    calendar_gaps: Optional[list] = None
    discovered_events: Optional[list] = None
    verified_events: Optional[list] = None
    relaxation_attempts: int = 0
    max_relaxation_attempts: int = 3
    error: Optional[str] = None


class Manager:
    """Manages the 5-step event discovery workflow."""
    
    def __init__(self, input_parser=None, calendar_agent=None, 
                 discovery_agent=None, auditor=None, edge_case_handler=None):
        """
        Initialize manager with required agents.
        
        Args:
            input_parser: InputParser instance
            calendar_agent: CalendarAgent instance
            discovery_agent: DiscoveryAgent instance
            auditor: Auditor instance
            edge_case_handler: EdgeCaseHandler instance
        """
        self.input_parser = input_parser
        self.calendar_agent = calendar_agent
        self.discovery_agent = discovery_agent
        self.auditor = auditor
        self.edge_case_handler = edge_case_handler
    
    def execute_workflow(self, user_input: str, user_preferences: dict = None) -> dict:
        """
        Execute the complete 5-step workflow.
        
        Args:
            user_input: User's voice/text input
            user_preferences: User's saved preferences
        
        Returns:
            Dictionary with verified events and workflow state
        """
        state = WorkflowState(
            current_step=WorkflowStep.INGESTION,
            user_input=user_input
        )
        
        try:
            # Step 1: Ingestion - parse voice to intent
            state = self._step_ingestion(state, user_preferences)
            
            # Step 2: Constraint Check - check calendar
            state = self._step_constraint_check(state)
            
            # Step 3: Discovery - search for events
            state = self._step_discovery(state)
            
            # Step 4: Verification - audit events
            state = self._step_verification(state)
            
            # Step 5: Relaxation - handle edge cases
            if not state.verified_events and state.relaxation_attempts < state.max_relaxation_attempts:
                state = self._step_relaxation(state)
        
        except Exception as e:
            state.error = str(e)
        
        return {
            "events": state.verified_events or [],
            "state": state,
            "success": bool(state.verified_events)
        }
    
    def _step_ingestion(self, state: WorkflowState, user_preferences: dict) -> WorkflowState:
        """Step 1: Parse voice input to structured intent."""
        state.current_step = WorkflowStep.INGESTION
        
        if self.input_parser:
            parsed = self.input_parser.parse_input(state.user_input, user_preferences)
            state.parsed_intent = {
                "query": parsed.query,
                "location": parsed.location,
                "genres": parsed.genres,
                "date": parsed.date,
                "radius_miles": parsed.radius_miles,
                "max_transit_minutes": parsed.max_transit_minutes,
                "time_window_days": parsed.time_window_days,
                "country": parsed.country,
                "search_lang": parsed.search_lang,
                "latitude": parsed.latitude,
                "longitude": parsed.longitude,
            }
        
        return state
    
    def _step_constraint_check(self, state: WorkflowState) -> WorkflowState:
        """Step 2: Check calendar for availability gaps."""
        state.current_step = WorkflowStep.CONSTRAINT_CHECK
        
        if self.calendar_agent and state.parsed_intent:
            # Would fetch calendar and find gaps
            state.calendar_gaps = []
        
        return state
    
    def _step_discovery(self, state: WorkflowState) -> WorkflowState:
        """Step 3: Discover events from web sources."""
        state.current_step = WorkflowStep.DISCOVERY
        
        if self.discovery_agent and state.parsed_intent:
            state.discovered_events = self.discovery_agent.search_events(
                query=state.parsed_intent.get("query", ""),
                location=state.parsed_intent.get("location", ""),
                genres=state.parsed_intent.get("genres", []),
                radius_miles=state.parsed_intent.get("radius_miles", 5),
                country=state.parsed_intent.get("country"),
                search_lang=state.parsed_intent.get("search_lang"),
                time_window_days=state.parsed_intent.get("time_window_days", 7),
                latitude=state.parsed_intent.get("latitude"),
                longitude=state.parsed_intent.get("longitude"),
                count=10,
            )
        
        return state
    
    def _step_verification(self, state: WorkflowState) -> WorkflowState:
        """Step 4: Verify events are actually free."""
        state.current_step = WorkflowStep.VERIFICATION
        
        state.verified_events = []
        
        if self.auditor and state.discovered_events:
            for event in state.discovered_events:
                status = self.auditor.verify_event_free(event.description)
                if status.value == "FREE":
                    state.verified_events.append(event)
        
        return state
    
    def _step_relaxation(self, state: WorkflowState) -> WorkflowState:
        """Step 5: Relax constraints and retry if needed."""
        state.current_step = WorkflowStep.RELAXATION
        
        if self.edge_case_handler:
            state.relaxation_attempts += 1
            relaxed_params = self.edge_case_handler.handle_zero_results(state.parsed_intent)
            state.parsed_intent = relaxed_params
            
            # Retry discovery with relaxed parameters
            state = self._step_discovery(state)
            state = self._step_verification(state)
        
        return state
