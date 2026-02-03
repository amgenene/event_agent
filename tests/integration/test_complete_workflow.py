"""Integration tests for complete workflow."""

import pytest
from src.input_parser.parser import InputParser
from src.discovery_agent.searcher import DiscoveryAgent
from src.calendar_agent.scheduler import CalendarAgent
from src.auditor.verifier import Auditor
from src.resilience.edge_case_handler import EdgeCaseHandler
from src.orchestration.manager import Manager


class TestCompleteWorkflow:
    """Integration tests for the complete 5-step workflow."""
    
    @pytest.fixture
    def components(self):
        """Create all components."""
        return {
            "input_parser": InputParser(),
            "calendar_agent": CalendarAgent(nylas_api_key="test"),
            "discovery_agent": DiscoveryAgent(tavily_api_key="test"),
            "auditor": Auditor(),
            "edge_case_handler": EdgeCaseHandler()
        }
    
    @pytest.fixture
    def manager(self, components):
        """Create manager with all components."""
        return Manager(**components)
    
    def test_complete_workflow_execution(self, manager):
        """Test complete workflow from input to output."""
        user_input = "Find free jazz events in San Francisco"
        preferences = {
            "home_city": "San Francisco",
            "favorite_genres": ["jazz", "live music"]
        }
        
        result = manager.execute_workflow(user_input, preferences)
        
        assert result is not None
        assert "events" in result
        assert "state" in result
        assert "success" in result
    
    def test_workflow_with_multiple_components(self, components):
        """Test that all components work together."""
        input_parser = components["input_parser"]
        auditor = components["auditor"]
        
        # Parse input
        parsed = input_parser.parse_input("Find free events")
        assert parsed.query is not None
        
        # Verify event description
        event_description = "Free community event. No tickets required."
        status = auditor.verify_event_free(event_description)
        assert status.value == "FREE"
    
    def test_workflow_returns_complete_state(self, manager):
        """Test that workflow returns complete state information."""
        result = manager.execute_workflow("Find events near me")
        state = result["state"]
        
        assert state.user_input is not None
        assert state.current_step is not None
        assert state.relaxation_attempts >= 0
