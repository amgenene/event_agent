"""Unit tests for resilience/edge case handler module."""

import pytest
from src.resilience.edge_case_handler import EdgeCaseHandler, FailureMode, RelaxationStrategy


class TestEdgeCaseHandler:
    """Test cases for EdgeCaseHandler."""
    
    @pytest.fixture
    def handler(self):
        """Create edge case handler instance."""
        return EdgeCaseHandler()
    
    def test_handler_initialization(self, handler):
        """Test handler initialization."""
        assert handler.strategies is not None
        assert FailureMode.ZERO_RESULTS in handler.strategies
    
    def test_handle_zero_results_expands_radius(self, handler):
        """Test that zero results relaxation expands radius."""
        params = {"radius_miles": 5, "genres": ["jazz"]}
        relaxed = handler.handle_zero_results(params)
        
        assert relaxed["radius_miles"] > params["radius_miles"]
        assert relaxed["genres"] == params["genres"]
    
    def test_handle_zero_results_caps_radius(self, handler):
        """Test that radius expansion is capped."""
        params = {"radius_miles": 20}
        relaxed = handler.handle_zero_results(params)
        
        assert relaxed["radius_miles"] <= 50
    
    def test_handle_schedule_conflict_with_non_dropin(self, handler):
        """Test schedule conflict handling for non-drop-in events."""
        class MockEvent:
            is_dropin = False
        
        event = MockEvent()
        result = handler.handle_schedule_conflict(event, [])
        
        assert result is False
    
    def test_handle_schedule_conflict_with_dropin(self, handler):
        """Test schedule conflict handling for drop-in events."""
        class MockEvent:
            is_dropin = True
        
        event = MockEvent()
        result = handler.handle_schedule_conflict(event, [])
        
        assert result is True
    
    def test_handle_api_timeout_tavily_failover(self, handler):
        """Test API timeout handling with Tavily failover."""
        failover = handler.handle_api_timeout("tavily")
        
        assert failover == "exa"
    
    def test_handle_api_timeout_google_maps_failover(self, handler):
        """Test API timeout handling with Google Maps failover."""
        failover = handler.handle_api_timeout("google_maps")
        
        assert failover == "open_routes"
    
    def test_get_relaxation_strategies_for_zero_results(self, handler):
        """Test getting strategies for zero results."""
        strategies = handler.get_relaxation_strategies(FailureMode.ZERO_RESULTS)
        
        assert len(strategies) > 0
        assert all(isinstance(s, RelaxationStrategy) for s in strategies)
    
    def test_get_relaxation_strategies_for_schedule_conflict(self, handler):
        """Test getting strategies for schedule conflict."""
        strategies = handler.get_relaxation_strategies(FailureMode.SCHEDULE_CONFLICT)
        
        assert len(strategies) > 0
    
    def test_get_relaxation_strategies_for_api_timeout(self, handler):
        """Test getting strategies for API timeout."""
        strategies = handler.get_relaxation_strategies(FailureMode.API_TIMEOUT)
        
        assert len(strategies) > 0
