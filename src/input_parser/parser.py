"""Input parser implementation for converting voice/text to structured intent."""

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

from src.location.geo import resolve_location_from_coords
from src.location.country import normalize_country

logger = logging.getLogger(__name__)


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
    participants: list[str] = None

    def __post_init__(self):
        if self.genres is None:
            self.genres = []
        if self.participants is None:
            self.participants = []


class InputParser:
    """Parses voice input or text to structured intent."""

    _DATE_PATTERNS = [
        (r"\btonight\b", 1),
        (r"\btoday\b", 1),
        (r"\btomorrow\b", 1),
        (r"\bthis\s+week(end)?\b", 7),
        (r"\bnext\s+week\b", 14),
        (r"\bthis\s+month\b", 30),
    ]

    _RADIUS_PATTERNS = [
        (r"(\d+)\s*(mi|miles)", 1),
        (r"nearby", 5),
        (r"close\s*by", 5),
        (r"around\s*(?:the\s*)?(?:area|city|town)", 10),
    ]

    _TRANSIT_PATTERNS = [
        (r"(\d+)\s*(min|minutes?)\s*(away|travel|drive)", 1),
        (r"within\s*(\d+)\s*(min|minutes?)", 1),
    ]

    _PARTICIPANT_PATTERNS = [
        r"with\s+([\w\s,]+?)(?:\s+at|\s+in|\s+near|\s+for|$)",
        r"for\s+(?:me\s+and\s+)?([\w\s,]+?)(?:\s+at|\s+in|\s+near|\s+for|$)",
    ]

    def __init__(self, llm_client=None):
        """Initialize the input parser."""
        self.llm_client = llm_client
        self.default_home_city = None
        self.default_genres = ["music", "arts", "tech"]

    def parse_input(
        self, user_input: str, user_preferences: dict = None
    ) -> ParsedIntent:
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
            resolved_location, resolved_country = resolve_location_from_coords(
                latitude, longitude
            )

        if self.llm_client:
            return self._parse_with_llm(
                user_input,
                user_preferences,
                resolved_location,
                resolved_country,
                latitude,
                longitude,
            )

        return self._parse_rule_based(
            user_input,
            user_preferences,
            resolved_location,
            resolved_country,
            latitude,
            longitude,
        )

    def _parse_with_llm(
        self,
        user_input: str,
        user_preferences: dict,
        resolved_location: Optional[str],
        resolved_country: Optional[str],
        latitude: Optional[float],
        longitude: Optional[float],
    ) -> ParsedIntent:
        """Use LLM to extract structured intent from user input."""
        prompt = (
            "You are an event search intent parser. Extract the following information from the user's input.\n"
            "Return ONLY a JSON object with these fields (use null for missing values):\n"
            "- query: the core event search phrase (e.g., 'jazz concerts', 'tech meetups')\n"
            "- location: city or area name if mentioned\n"
            "- genres: list of event types (e.g., ['jazz', 'music'], ['tech', 'meetup'])\n"
            "- date: specific date if mentioned (YYYY-MM-DD format) or relative (tonight, this weekend)\n"
            "- radius_miles: search radius in miles if mentioned (default 5)\n"
            "- max_transit_minutes: max travel time in minutes if mentioned (default 30)\n"
            "- time_window_days: how many days ahead to search (1=today, 7=this week, 14=next week, 30=this month)\n"
            "- participants: list of friend names/emails mentioned for group planning\n\n"
            f"User input: {user_input}"
        )

        try:
            if hasattr(self.llm_client, "chat") and hasattr(
                self.llm_client.chat, "completions"
            ):
                response = self.llm_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=200,
                )
                content = response.choices[0].message.content.strip()
            elif hasattr(self.llm_client, "invoke"):
                content = self.llm_client.invoke(prompt)
            else:
                logger.warning("Unknown LLM client type: %s", type(self.llm_client))
                return self._parse_rule_based(
                    user_input,
                    user_preferences,
                    resolved_location,
                    resolved_country,
                    latitude,
                    longitude,
                )

            result = json.loads(content)

            genres = result.get("genres") or user_preferences.get(
                "favorite_genres", self.default_genres
            )
            if isinstance(genres, str):
                genres = [genres]

            return ParsedIntent(
                query=result.get("query") or user_input,
                location=result.get("location")
                or resolved_location
                or user_preferences.get("home_city"),
                genres=genres,
                date=result.get("date"),
                radius_miles=result.get("radius_miles")
                or user_preferences.get("radius_miles", 5),
                max_transit_minutes=result.get("max_transit_minutes")
                or user_preferences.get("max_transit_minutes", 30),
                time_window_days=result.get("time_window_days")
                or user_preferences.get("time_window_days", 7),
                country=normalize_country(
                    result.get("country")
                    or resolved_country
                    or user_preferences.get("country")
                ),
                search_lang=user_preferences.get("search_lang"),
                latitude=latitude,
                longitude=longitude,
                participants=result.get("participants") or [],
            )
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning("LLM parsing failed, falling back to rule-based: %s", exc)
            return self._parse_rule_based(
                user_input,
                user_preferences,
                resolved_location,
                resolved_country,
                latitude,
                longitude,
            )

    def _parse_rule_based(
        self,
        user_input: str,
        user_preferences: dict,
        resolved_location: Optional[str],
        resolved_country: Optional[str],
        latitude: Optional[float],
        longitude: Optional[float],
    ) -> ParsedIntent:
        """Rule-based parsing fallback."""
        location = self._extract_location(
            user_input, user_preferences, resolved_location
        )
        genres = self._extract_genres(user_input, user_preferences)
        date = self._extract_date(user_input)
        radius = self._extract_radius(user_input)
        transit = self._extract_transit_time(user_input)
        time_window = self._extract_time_window(user_input)
        participants = self._extract_participants(user_input)

        normalized_country = normalize_country(
            user_preferences.get("country") or resolved_country
        )

        return ParsedIntent(
            query=user_input,
            location=location,
            genres=genres,
            date=date,
            radius_miles=radius or user_preferences.get("radius_miles", 5),
            max_transit_minutes=transit
            or user_preferences.get("max_transit_minutes", 30),
            time_window_days=time_window or user_preferences.get("time_window_days", 7),
            country=normalized_country,
            search_lang=user_preferences.get("search_lang"),
            latitude=latitude,
            longitude=longitude,
            participants=participants,
        )

    def _extract_location(
        self, input_text: str, preferences: dict, resolved_location: Optional[str]
    ) -> Optional[str]:
        """Extract location from input or use user's home city or device location."""
        location_keywords = ["in", "near", "around", "at"]
        for keyword in location_keywords:
            if keyword in input_text.lower():
                pass
        if preferences.get("home_city"):
            return preferences.get("home_city")
        if resolved_location:
            return resolved_location
        return None

    def _extract_genres(self, input_text: str, preferences: dict) -> list[str]:
        """Extract event genres/categories from input."""
        user_genres = preferences.get("favorite_genres", self.default_genres)
        return user_genres

    def _extract_date(self, input_text: str) -> Optional[str]:
        """Extract date from input if mentioned."""
        lower = input_text.lower()
        for pattern, _ in self._DATE_PATTERNS:
            if re.search(pattern, lower):
                return re.search(pattern, lower).group()
        return None

    def _extract_radius(self, input_text: str) -> Optional[int]:
        """Extract search radius from input."""
        lower = input_text.lower()
        for pattern, group in self._RADIUS_PATTERNS:
            match = re.search(pattern, lower)
            if match:
                if match.groups():
                    return int(match.group(group))
                return match.group(group)
        return None

    def _extract_transit_time(self, input_text: str) -> Optional[int]:
        """Extract max transit time from input."""
        lower = input_text.lower()
        for pattern, group in self._TRANSIT_PATTERNS:
            match = re.search(pattern, lower)
            if match and match.groups():
                return int(match.group(group))
        return None

    def _extract_time_window(self, input_text: str) -> Optional[int]:
        """Extract time window in days from input."""
        lower = input_text.lower()
        for pattern, days in self._DATE_PATTERNS:
            if re.search(pattern, lower):
                return days
        return None

    def _extract_participants(self, input_text: str) -> list[str]:
        """Extract participant names/emails from input."""
        participants = []
        for pattern in self._PARTICIPANT_PATTERNS:
            match = re.search(pattern, input_text, re.IGNORECASE)
            if match:
                raw = match.group(1).strip()
                participants = [
                    p.strip()
                    for p in re.split(r"[,\s]+and\s+|[,\s]+", raw)
                    if p.strip()
                ]
                break
        return participants
