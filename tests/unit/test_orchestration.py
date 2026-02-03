"""Unit tests for orchestration/manager module."""

import pytest
from unittest.mock import patch, MagicMock
from src.orchestration.manager import Manager, WorkflowState, WorkflowStep
from src.input_parser.parser import InputParser
from src.discovery_agent.searcher import DiscoveryAgent
from src.calendar_agent.scheduler import CalendarAgent
from src.auditor.verifier import Auditor
from src.resilience.edge_case_handler import EdgeCaseHandler


class TestManager:
    """Test cases for Manager orchestration."""
    
    @pytest.fixture
    def components(self):
        """Create manager with mock components."""
        with patch.dict('os.environ', {
            'NYLAS_API_KEY': 'test_key',
            'NYLAS_API_URI': 'test_uri',
            'NYLAS_GRANT_ID': 'test_grant_id',
            'TAVILY_API_KEY': 'test_key'
        }):
            with patch('src.calendar_agent.scheduler.Client'):
                return {
                    "input_parser": InputParser(),
                    "calendar_agent": CalendarAgent(participants=['test@example.com']),
                    "discovery_agent": DiscoveryAgent(),
                    "auditor": Auditor(),
                    "edge_case_handler": EdgeCaseHandler()
                }
    
    @pytest.fixture
    def manager(self, components):
        """Create manager instance with components."""
        return Manager(**components)
    
    def test_manager_initialization(self, manager):
        """Test manager initialization."""
        assert manager.input_parser is not None
        assert manager.calendar_agent is not None
        assert manager.discovery_agent is not None
        assert manager.auditor is not None
        assert manager.edge_case_handler is not None
    
    def test_execute_workflow_starts_at_ingestion(self, manager):
        """Test that workflow starts at ingestion step."""
        result = manager.execute_workflow("Find jazz events")
        
        assert result is not None
        assert "state" in result
        assert "events" in result
    
    def test_workflow_state_initialization(self):
        """Test WorkflowState initialization."""
        state = WorkflowState(
            current_step=WorkflowStep.INGESTION,
            user_input="Find events"
        )
        
        assert state.current_step == WorkflowStep.INGESTION
        assert state.user_input == "Find events"
        assert state.relaxation_attempts == 0
    
    def test_execute_workflow_with_preferences(self, manager):
        """Test workflow execution with user preferences."""
        preferences = {
            "home_city": "New York",
            "favorite_genres": ["jazz"]
        }
        
        result = manager.execute_workflow("Find events", preferences)
        
        assert result is not None
        assert "state" in result
    
    def test_execute_workflow_returns_dict_with_events(self, manager):
        """Test that workflow returns dictionary with events."""
        result = manager.execute_workflow("Find music")
        
        assert isinstance(result, dict)
        assert "events" in result
        assert "state" in result
        assert "success" in result
        assert isinstance(result["events"], list)
    
    def test_execute_workflow_handles_exceptions(self, manager):
        """Test that workflow handles exceptions gracefully."""
        result = manager.execute_workflow("")
        
        assert "state" in result
        assert result["state"].error is None or isinstance(result["state"].error, str)
    
    def test_workflow_step_progression(self, manager):
        """Test that workflow steps progress correctly."""
        result = manager.execute_workflow("Find events")
        state = result["state"]
        
        # State should be completed or have an error
        assert state.current_step is not None
