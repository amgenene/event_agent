"""Unit tests for discovery agent module."""

import pytest
from src.discovery_agent.searcher import DiscoveryAgent, Event


class TestDiscoveryAgent:
    """Test cases for DiscoveryAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create discovery agent instance."""
        return DiscoveryAgent(tavily_api_key="test_key")
    
    def test_agent_initialization(self):
        """Test agent initialization with API key."""
        agent = DiscoveryAgent(tavily_api_key="test_key")
        assert agent.tavily_api_key == "test_key"
    
    def test_agent_requires_api_key(self):
        """Test that agent requires API key."""
        agent = DiscoveryAgent()
        
        with pytest.raises(ValueError, match="Tavily API key not configured"):
            agent.search_events("test", "SF")
    
    def test_search_events_returns_list(self, agent):
        """Test that search_events returns a list."""
        result = agent.search_events(
            query="jazz",
            location="San Francisco",
            genres=["music"]
        )
        
        assert isinstance(result, list)
    
    def test_domain_strategies_set(self, agent):
        """Test that domain search strategies are initialized."""
        assert len(agent.domain_strategies) > 0
        assert 'site:eventbrite.com "free"' in agent.domain_strategies
        assert 'site:meetup.com "no cover charge"' in agent.domain_strategies
    
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
