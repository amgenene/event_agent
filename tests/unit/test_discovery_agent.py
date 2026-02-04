"""Unit tests for discovery agent module."""

import pytest

from src.discovery_agent.searcher import DiscoveryAgent, Event
from src.discovery_agent.providers.base import SearchRequest, SearchResult, SearchProvider


class TestDiscoveryAgent:
    """Test cases for DiscoveryAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create discovery agent instance."""
        class StubProvider(SearchProvider):
            def search(self, request: SearchRequest):
                return [
                    SearchResult(
                        title="Test Event",
                        url="https://example.com/event",
                        description="Free community event"
                    )
                ]

        return DiscoveryAgent(provider=StubProvider())
    
    def test_agent_initialization(self):
        """Test agent initialization with API key."""
        agent = DiscoveryAgent(provider=None)
        assert agent is not None
    
    def test_agent_requires_api_key(self):
        """Test that agent requires API key."""
        agent = DiscoveryAgent(provider=None)
        
        with pytest.raises(ValueError, match="Discovery provider not configured"):
            agent.search_events("test", "SF")
    
    def test_search_events_returns_list(self, agent):
        """Test that search_events returns a list."""
        result = agent.search_events(
            query="jazz",
            location="San Francisco",
            genres=["music"]
        )
        
        assert isinstance(result, list)
    
    def test_event_dataclass(self):
        """Test Event dataclass creation."""
        event = Event(
            id="1",
            title="Jazz Night",
            location="SF",
            date="2026-02-01",
            time="19:00",
            description="Free jazz night",
            url="https://example.com"
        )
        
        assert event.id == "1"
        assert event.title == "Jazz Night"
        assert event.price == "Free"
