"""Unit tests for Brave search provider."""

from src.discovery_agent.providers.brave import BraveConfig, BraveSearchProvider
from src.discovery_agent.providers.base import SearchRequest


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_brave_provider_normalizes_results(monkeypatch):
    payload = {
        "web": {
            "results": [
                {
                    "title": "Free Jazz Night",
                    "url": "https://example.com/jazz",
                    "description": "A free jazz event",
                    "profile": {"long_name": "Example"},
                },
                {
                    "title": "",
                    "url": "https://example.com/skip",
                    "description": "Missing title should skip",
                },
            ]
        }
    }

    provider = BraveSearchProvider(BraveConfig(api_key="test"))

    def fake_get(*_args, **_kwargs):
        return _FakeResponse(payload)

    monkeypatch.setattr(provider._client, "get", fake_get)

    results = provider.search(
        SearchRequest(
            query="free jazz",
            location="Chicago",
            country="US",
            search_lang="en",
            time_window_days=7,
            count=10,
        )
    )

    assert len(results) == 1
    assert results[0].title == "Free Jazz Night"
    assert results[0].url == "https://example.com/jazz"
