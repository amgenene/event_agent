"""Input parser implementation for converting voice/text to structured intent."""

from dataclasses import dataclass
from typing import Optional

from src.location.geo import resolve_location_from_coords


@dataclass
class ParsedIntent:
    """Structured representation of user intent."""
    
    query: str
    location: Optional[str] = None
    genres: list[str] = None
    date: Optional[str] = None
    radius_miles: int = 5
    max_transit_minutes: int = 30
    time_window_days: int = 7
    country: Optional[str] = None
    search_lang: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    def __post_init__(self):
        if self.genres is None:
            self.genres = []


class InputParser:
    """Parses voice input or text to structured intent."""
    
    def __init__(self):
        """Initialize the input parser."""
        self.default_home_city = None
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
        
        latitude = user_preferences.get("latitude")
        longitude = user_preferences.get("longitude")

        resolved_location = None
        resolved_country = None
        if latitude is not None and longitude is not None:
            resolved_location, resolved_country = resolve_location_from_coords(latitude, longitude)

        # Extract location from input or use defaults
        location = self._extract_location(user_input, user_preferences, resolved_location)
        
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
            max_transit_minutes=user_preferences.get("max_transit_minutes", 30),
            time_window_days=user_preferences.get("time_window_days", 7),
            country=user_preferences.get("country") or resolved_country,
            search_lang=user_preferences.get("search_lang"),
            latitude=latitude,
            longitude=longitude,
        )
    
    def _extract_location(self, input_text: str, preferences: dict, resolved_location: Optional[str]) -> str:
        """Extract location from input or use user's home city or device location."""
        # Placeholder implementation
        location_keywords = ["in", "near", "around", "at"]
        for keyword in location_keywords:
            if keyword in input_text.lower():
                # Would parse location here
                pass
        if preferences.get("home_city"):
            return preferences.get("home_city")
        if resolved_location:
            return resolved_location
        return None
    
    def _extract_genres(self, input_text: str, preferences: dict) -> list[str]:
        """Extract event genres/categories from input."""
        # Placeholder implementation
        user_genres = preferences.get("favorite_genres", self.default_genres)
        return user_genres
    
    def _extract_date(self, input_text: str) -> Optional[str]:
        """Extract date from input if mentioned."""
        # Placeholder implementation
        return None
