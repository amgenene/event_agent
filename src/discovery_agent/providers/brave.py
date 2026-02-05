"""Brave Search API provider implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import httpx
import logging

from .base import SearchProvider, SearchRequest, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class BraveConfig:
    """Configuration for Brave Search API."""

    api_key: str
    base_url: str = "https://api.search.brave.com/res/v1/web/search"
    timeout_seconds: int = 15


class BraveSearchProvider(SearchProvider):
    """Search provider using Brave Search API."""

    def __init__(self, config: BraveConfig):
        self.config = config
        self._client = httpx.Client(timeout=self.config.timeout_seconds)

    def search(self, request: SearchRequest) -> List[SearchResult]:
        params = {
            "q": request.query,
            "count": request.count,
        }

        if request.country:
            params["country"] = request.country
        if request.search_lang:
            params["search_lang"] = request.search_lang

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.config.api_key,
        }

        logger.debug(
            "Brave search request: q=%s count=%s country=%s lang=%s",
            request.query,
            request.count,
            request.country,
            request.search_lang,
        )

        try:
            print(self.config.api_key, "api_key")
            response = self._client.get(self.config.base_url, params=params, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception("Brave search request failed: %s", exc)
            raise

        data = response.json()
        web = data.get("web", {})
        results = web.get("results", [])
        logger.debug("Brave search results: %s items", len(results))

        normalized: List[SearchResult] = []
        for item in results:
            title = item.get("title") or ""
            url = item.get("url") or ""
            description = item.get("description") or item.get("snippet")
            source = None
            profile = item.get("profile")
            if isinstance(profile, dict):
                source = profile.get("long_name") or profile.get("name")

            if not title or not url:
                continue

            normalized.append(
                SearchResult(
                    title=title,
                    url=url,
                    description=description,
                    source=source,
                )
            )

        logger.info("Brave search normalized %s results", len(normalized))
        return normalized
