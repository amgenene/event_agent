"""Unit tests for Tavily search provider."""

import os
import pytest
from unittest.mock import MagicMock, patch
from src.discovery_agent.providers.tavily import TavilyProvider
from src.discovery_agent.providers.base import SearchRequest


class TestTavilyProvider:
    """Test cases for TavilyProvider."""

    @patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"})
    @patch("src.discovery_agent.providers.tavily.TavilyClient")
    def test_search_success(self, mock_tavily_client):
        """Test successful search with Tavily."""
        # Setup mock response
        mock_instance = mock_tavily_client.return_value
        mock_instance.search.return_value = {
            "results": [
                {
                    "title": "Tavily Event",
                    "url": "https://tavily.com/event",
                    "snippet": "A great free event found by Tavily",
                }
            ]
        }

        provider = TavilyProvider()
        request = SearchRequest(
            query="test",
            location="SF",
            country=None,
            search_lang=None,
            time_window_days=7,
        )

        results = provider.search(request)

        assert len(results) == 1
        assert results[0].title == "Tavily Event"
        assert results[0].url == "https://tavily.com/event"
        assert results[0].description is not None
        mock_instance.search.assert_called_once()
        call_kwargs = mock_instance.search.call_args.kwargs
        assert call_kwargs["query"] == "test"

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_api_key(self):
        """Test that TavilyProvider raises error if API key is missing."""
        with pytest.raises(ValueError, match="TAVILY_API_KEY not set"):
            TavilyProvider()
