"""Event discovery agent using provider-based search with LangGraph."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from typing import Optional

from .graph import build_search_graph
from .providers.base import SearchProvider
from .providers.brave import BraveConfig, BraveSearchProvider


@dataclass
class Event:
    """Represents a discovered event."""
    
    id: str
    title: str
    location: str
    date: str
    time: str
    description: str
    url: str
    price: str = "Free"
    category: Optional[str] = None


class DiscoveryAgent:
    """Searches live web sources for free events."""
    
    def __init__(self, provider: Optional[SearchProvider] = None):
        """
        Initialize discovery agent.
        
        Args:
            provider: Search provider implementation
        """
        self.provider = provider or self._build_default_provider()
        self.graph = build_search_graph(self.provider) if self.provider else None
    
    def search_events(
        self,
        query: str,
        location: str,
        genres: list[str] = None,
        radius_miles: int = 5,
        country: Optional[str] = None,
        search_lang: Optional[str] = None,
        time_window_days: int = 7,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        count: int = 10,
    ) -> list[Event]:
        """
        Search for free events matching criteria.
        
        Args:
            query: Search query
            location: Location to search in
            genres: List of event genres/categories to filter
            radius_miles: Search radius in miles
            country: ISO country code for search results
            search_lang: Search language (e.g., en)
            time_window_days: Time window in days from today
            count: Max number of results to return
        
        Returns:
            List of Event objects
        """
        if not self.provider or not self.graph:
            raise ValueError("Discovery provider not configured")

        state = {
            "query": query,
            "location": location,
            "country": country,
            "search_lang": search_lang,
            "time_window_days": time_window_days,
            "latitude": latitude,
            "longitude": longitude,
            "count": count,
        }

        result_state = self.graph.invoke(state)
        results = result_state.get("results", []) or []

        events: list[Event] = []
        for result in results:
            events.append(self._result_to_event(result, location))

        return events

    def _result_to_event(self, result, location: str) -> Event:
        title = getattr(result, "title", "") or ""
        url = getattr(result, "url", "") or ""
        description = getattr(result, "description", "") or ""

        event_id = hashlib.md5(url.encode("utf-8")).hexdigest() if url else hashlib.md5(
            title.encode("utf-8")
        ).hexdigest()

        return Event(
            id=event_id,
            title=title,
            location=location or "",
            date="TBD",
            time="TBD",
            description=description,
            url=url,
            price="Free",
            category=None,
        )

    def _build_default_provider(self) -> Optional[SearchProvider]:
        provider_name = os.environ.get("DISCOVERY_PROVIDER", "brave").lower()

        if provider_name == "brave":
            api_key = os.environ.get("BRAVE_API_KEY")
            if not api_key:
                return None
            base_url = os.environ.get("BRAVE_API_BASE_URL") or "https://api.search.brave.com/res/v1/web/search"
            timeout = int(os.environ.get("BRAVE_API_TIMEOUT_SECONDS", "15"))
            config = BraveConfig(
                api_key=api_key,
                base_url=base_url,
                timeout_seconds=timeout,
            )
            return BraveSearchProvider(config)

        raise ValueError(f"Unknown discovery provider: {provider_name}")
