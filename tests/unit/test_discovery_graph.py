"""Unit tests for discovery graph helpers."""

from src.discovery_agent.graph import build_query, _time_window_phrase, format_query


def test_time_window_phrase():
    assert _time_window_phrase(1) == "today"
    assert _time_window_phrase(3) == "this weekend"
    assert _time_window_phrase(7) == "this week"
    assert _time_window_phrase(10) == "next 10 days"


def test_build_query_uses_location():
    state = {
        "query": "free jazz events",
        "location": "Boston, MA",
        "time_window_days": 7,
    }
    result = build_query(state)
    assert "Boston, MA" in result["built_query"]


def test_build_query_uses_coords_when_no_location():
    state = {
        "query": "free jazz events",
        "latitude": 41.8781,
        "longitude": -87.6298,
        "time_window_days": 7,
    }
    result = build_query(state)
    assert "near 41.8781, -87.6298" in result["built_query"]


def test_format_query_removes_polite_prefix():
    state = {"query": "Can you find me jazz shows?"}
    result = format_query(state)
    assert "free" in result["formatted_query"]
    assert "jazz" in result["formatted_query"]
    assert "\"jazz\"" in result["formatted_query"]
