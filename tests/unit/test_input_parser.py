"""Unit tests for input parser module."""

import pytest
from src.input_parser.parser import InputParser, ParsedIntent


class TestInputParser:
    """Test cases for InputParser."""
    
    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return InputParser()
    
    def test_parse_simple_input(self, parser):
        """Test parsing simple user input."""
        result = parser.parse_input("Find me live music events")
        
        assert isinstance(result, ParsedIntent)
        assert result.query == "Find me live music events"
        assert result.location == "San Francisco"
        assert result.genres == ["music", "arts", "tech"]
    
    def test_parse_with_user_preferences(self, parser):
        """Test parsing with user preferences."""
        preferences = {
            "home_city": "New York",
            "favorite_genres": ["jazz", "rock"],
            "radius_miles": 10,
            "max_transit_minutes": 45
        }
        
        result = parser.parse_input("Find events", preferences)
        
        assert result.location == "New York"
        assert result.genres == ["jazz", "rock"]
        assert result.radius_miles == 10
        assert result.max_transit_minutes == 45
    
    def test_parse_vague_input_uses_defaults(self, parser):
        """Test that vague input defaults to user preferences."""
        preferences = {
            "home_city": "Los Angeles",
            "favorite_genres": ["comedy", "theater"]
        }
        
        result = parser.parse_input("Find me stuff", preferences)
        
        assert result.location == "Los Angeles"
        assert result.genres == ["comedy", "theater"]
    
    def test_parsed_intent_has_default_radius(self, parser):
        """Test that ParsedIntent has default radius."""
        result = parser.parse_input("Find music events")
        
        assert result.radius_miles == 5
    
    def test_parsed_intent_has_default_transit(self, parser):
        """Test that ParsedIntent has default max transit time."""
        result = parser.parse_input("Find music events")
        
        assert result.max_transit_minutes == 30
