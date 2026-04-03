"""Integration tests for Tavily provider with full search pipeline."""

import os
import pytest
from unittest.mock import MagicMock, patch

from src.discovery_agent.providers.tavily import TavilyProvider
from src.discovery_agent.providers.base import SearchRequest, SearchResult
from src.discovery_agent.searcher import DiscoveryAgent


class TestTavilyProviderIntegration:
    """Integration tests for Tavily provider."""

    @pytest.fixture
    def provider(self):
        """Create Tavily provider with mocked client."""
        with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
            with patch(
                "src.discovery_agent.providers.tavily.TavilyClient"
            ) as mock_client:
                mock_instance = MagicMock()
                mock_client.return_value = mock_instance
                mock_instance.search.return_value = {
                    "results": [
                        {
                            "title": "Free Jazz Festival in SF",
                            "url": "https://eventbrite.com/e/free-jazz-festival",
                            "content": "Join us for a free jazz festival this weekend at Golden Gate Park. No tickets required, open to the public.",
                            "published_date": "2026-03-15",
                        },
                        {
                            "title": "Tech Meetup: AI & ML",
                            "url": "https://meetup.com/tech-sf/events/ai-ml",
                            "content": "Free tech meetup discussing AI and machine learning. Free pizza and networking.",
                            "published_date": "2026-03-20",
                        },
                    ],
                    "answer": "Found 2 free events in San Francisco.",
                }
                mock_instance.extract.return_value = {
                    "results": [
                        {
                            "url": "https://eventbrite.com/e/free-jazz-festival",
                            "raw_content": "Free Jazz Festival\nDate: March 15, 2026\nTime: 2:00 PM - 8:00 PM\nLocation: Golden Gate Park, San Francisco\nPrice: Free admission",
                        }
                    ]
                }
                yield TavilyProvider()

    def test_search_returns_normalized_results(self, provider):
        """Test that search returns properly normalized SearchResult objects."""
        request = SearchRequest(
            query="free jazz events",
            location="San Francisco",
            country="us",
            search_lang="en",
            time_window_days=7,
            count=10,
        )

        results = provider.search(request)

        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].title == "Free Jazz Festival in SF"
        assert results[0].url == "https://eventbrite.com/e/free-jazz-festival"
        assert "free jazz festival" in results[0].description.lower()
        assert results[0].source == "eventbrite.com"
        assert results[0].published == "2026-03-15"

    def test_search_with_empty_response(self, provider):
        """Test handling of empty search results."""
        provider._client.search.return_value = {"results": []}

        request = SearchRequest(
            query="nonexistent event type",
            location="Nowhere",
            country="us",
            search_lang="en",
            time_window_days=7,
        )

        results = provider.search(request)
        assert results == []

    def test_search_with_partial_results(self, provider):
        """Test handling of results missing required fields."""
        provider._client.search.return_value = {
            "results": [
                {
                    "title": "Valid Event",
                    "url": "https://example.com/1",
                    "content": "Good event",
                },
                {"title": "", "url": "https://example.com/2", "content": "No title"},
                {"title": "No URL", "url": "", "content": "Missing URL"},
            ]
        }

        request = SearchRequest(
            query="test",
            location="SF",
            country="us",
            search_lang="en",
            time_window_days=7,
        )

        results = provider.search(request)
        assert len(results) == 1
        assert results[0].title == "Valid Event"

    def test_extract_event_details(self, provider):
        """Test extracting event details from URLs."""
        urls = [
            "https://eventbrite.com/e/free-jazz-festival",
            "https://meetup.com/tech-sf/events/ai-ml",
        ]

        details = provider.extract_event_details(urls)

        assert len(details) == 1
        provider._client.extract.assert_called_once_with(
            urls=urls,
            extract_depth="advanced",
        )

    def test_extract_empty_urls(self, provider):
        """Test extract with empty URL list."""
        details = provider.extract_event_details([])
        assert details == []

    def test_extract_truncates_to_20_urls(self, provider):
        """Test that extract truncates to max 20 URLs."""
        urls = [f"https://example.com/event/{i}" for i in range(25)]

        provider.extract_event_details(urls)

        provider._client.extract.assert_called_once()
        call_args = provider._client.extract.call_args
        assert len(call_args.kwargs["urls"]) == 20

    def test_search_date_filtering(self, provider):
        """Test that time_window_days maps to correct time_range."""
        request = SearchRequest(
            query="today events",
            location="SF",
            country="us",
            search_lang="en",
            time_window_days=1,
        )
        provider.search(request)
        call_args = provider._client.search.call_args
        assert call_args.kwargs["time_range"] == "day"

        request = SearchRequest(
            query="week events",
            location="SF",
            country="us",
            search_lang="en",
            time_window_days=3,
        )
        provider.search(request)
        call_args = provider._client.search.call_args
        assert call_args.kwargs["time_range"] == "week"

        request = SearchRequest(
            query="month events",
            location="SF",
            country="us",
            search_lang="en",
            time_window_days=10,
        )
        provider.search(request)
        call_args = provider._client.search.call_args
        assert call_args.kwargs["time_range"] == "month"

    def test_search_includes_event_domains(self, provider):
        """Test that search includes event platform domains."""
        request = SearchRequest(
            query="events",
            location="SF",
            country="us",
            search_lang="en",
            time_window_days=7,
        )

        provider.search(request)

        call_args = provider._client.search.call_args
        domains = call_args.kwargs.get("include_domains", [])
        assert "eventbrite.com" in domains
        assert "meetup.com" in domains
        assert "lu.ma" in domains

    def test_source_extraction(self):
        """Test domain extraction from URLs."""
        assert (
            TavilyProvider._extract_source("https://eventbrite.com/e/event")
            == "eventbrite.com"
        )
        assert (
            TavilyProvider._extract_source("https://www.meetup.com/event")
            == "meetup.com"
        )
        assert TavilyProvider._extract_source("https://lu.ma/abc123") == "lu.ma"
        assert TavilyProvider._extract_source("invalid-url") == ""

    def test_discovery_agent_with_tavily_provider(self, provider):
        """Test full discovery agent integration with Tavily provider."""
        agent = DiscoveryAgent(provider=provider)

        events, query_used = agent.search_events(
            query="jazz",
            location="San Francisco",
            genres=["music"],
            radius_miles=10,
            country="us",
            time_window_days=7,
        )

        assert isinstance(events, list)
        assert len(events) == 2
        assert isinstance(query_used, str)
        assert all(hasattr(e, "title") for e in events)
        assert all(hasattr(e, "url") for e in events)
