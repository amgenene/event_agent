"""Input parser implementation for converting voice/text to structured intent."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedIntent:
    """Structured representation of user intent."""
    
    query: str
    location: Optional[str] = None
    genres: list[str] = None
    date: Optional[str] = None
    radius_miles: int = 5
    max_transit_minutes: int = 30
    
    def __post_init__(self):
        if self.genres is None:
            self.genres = []


class InputParser:
    """Parses voice input or text to structured intent."""
    
    def __init__(self):
        """Initialize the input parser."""
        self.default_home_city = "San Francisco"
        self.default_genres = ["music", "arts", "tech"]
    
    def parse_input(self, user_input: str, user_preferences: dict = None) -> ParsedIntent:
        """
        Convert raw user input to structured intent.
        
        Args:
            user_input: Raw voice/text input from user
            user_preferences: User's saved preferences (home city, favorite genres, etc.)
        
        Returns:
            ParsedIntent: Structured intent object
        """
        user_preferences = user_preferences or {}
        
        # Extract location from input or use default
        location = self._extract_location(user_input, user_preferences)
        
        # Extract genres from input or use defaults
        genres = self._extract_genres(user_input, user_preferences)
        
        # Extract date if mentioned
        date = self._extract_date(user_input)
        
        return ParsedIntent(
            query=user_input,
            location=location,
            genres=genres,
            date=date,
            radius_miles=user_preferences.get("radius_miles", 5),
            max_transit_minutes=user_preferences.get("max_transit_minutes", 30)
        )
    
    def _extract_location(self, input_text: str, preferences: dict) -> str:
        """Extract location from input or use user's home city."""
        # Placeholder implementation
        location_keywords = ["in", "near", "around", "at"]
        for keyword in location_keywords:
            if keyword in input_text.lower():
                # Would parse location here
                pass
        
        return preferences.get("home_city", self.default_home_city)
    
    def _extract_genres(self, input_text: str, preferences: dict) -> list[str]:
        """Extract event genres/categories from input."""
        # Placeholder implementation
        user_genres = preferences.get("favorite_genres", self.default_genres)
        return user_genres
    
    def _extract_date(self, input_text: str) -> Optional[str]:
        """Extract date from input if mentioned."""
        # Placeholder implementation
        return None
