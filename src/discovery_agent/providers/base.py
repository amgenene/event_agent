"""Provider interfaces and shared models for discovery search."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, List


@dataclass
class SearchRequest:
    """Normalized search request for external providers."""

    query: str
    location: Optional[str]
    country: Optional[str]
    search_lang: Optional[str]
    time_window_days: int
    count: int = 10


@dataclass
class SearchResult:
    """Normalized search result from providers."""

    title: str
    url: str
    description: Optional[str] = None
    source: Optional[str] = None
    published: Optional[str] = None


class SearchProvider(Protocol):
    """Provider interface for external search APIs."""

    def search(self, request: SearchRequest) -> List[SearchResult]:
        """Execute a search query and return normalized results."""
        ...
