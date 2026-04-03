import os
import logging
from typing import List, Optional
from urllib.parse import urlparse
from .base import SearchProvider, SearchRequest, SearchResult

from tavily import TavilyClient

logger = logging.getLogger(__name__)


class TavilyProvider(SearchProvider):
    """Search provider using Tavily Search API."""

    DEFAULT_EVENT_DOMAINS = [
        "eventbrite.com",
        "meetup.com",
        "lu.ma",
        "facebook.com",
        "ticketmaster.com",
        "eventbrite.co.uk",
        "meetup.com",
    ]

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("TAVILY_API_KEY")
        if not key:
            raise ValueError("TAVILY_API_KEY not set")
        self._client = TavilyClient(key)

    def search(self, request: SearchRequest) -> List[SearchResult]:
        params = {
            "query": request.query,
            "max_results": request.count,
            "search_depth": "advanced",
            "topic": "news",
            "include_answer": True,
        }

        if request.country:
            params["country"] = request.country.lower()

        params["include_domains"] = self.DEFAULT_EVENT_DOMAINS

        if request.time_window_days <= 1:
            params["time_range"] = "day"
        elif request.time_window_days <= 3:
            params["time_range"] = "week"
        elif request.time_window_days <= 14:
            params["time_range"] = "month"
        else:
            params["time_range"] = "year"

        logger.debug(
            "Tavily search: query=%s country=%s window_days=%s count=%s",
            request.query,
            request.country,
            request.time_window_days,
            request.count,
        )

        try:
            response = self._client.search(**params)
        except Exception as exc:
            logger.exception("Tavily search request failed: %s", exc)
            raise

        raw_results = response.get("results") or []
        logger.debug("Tavily returned %s raw results", len(raw_results))

        normalized: List[SearchResult] = []
        for item in raw_results:
            title = item.get("title") or ""
            url = item.get("url") or ""
            description = item.get("content") or item.get("snippet") or ""
            published = item.get("published_date")

            if not title or not url:
                continue

            normalized.append(
                SearchResult(
                    title=title,
                    url=url,
                    description=description if description else None,
                    source=self._extract_source(url),
                    published=published,
                )
            )

        logger.info("Tavily normalized %s results", len(normalized))
        return normalized

    def extract_event_details(self, urls: List[str]) -> List[dict]:
        """Use Tavily /extract to pull structured event data from up to 20 URLs."""
        if not urls:
            return []

        truncated = urls[:20]
        logger.info("Extracting details from %d URLs via Tavily", len(truncated))

        try:
            response = self._client.extract(
                urls=truncated,
                extract_depth="advanced",
            )
        except Exception as exc:
            logger.exception("Tavily extract request failed: %s", exc)
            return []

        return response.get("results") or []

    @staticmethod
    def _extract_source(url: str) -> Optional[str]:
        try:
            domain = urlparse(url).netloc
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return None
