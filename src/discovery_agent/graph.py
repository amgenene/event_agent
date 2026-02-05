"""LangGraph pipeline for discovery search."""

from __future__ import annotations

from typing import List, Optional, TypedDict

from langgraph.graph import StateGraph, END

from .providers.base import SearchProvider, SearchRequest, SearchResult
from .query_formatter import format_search_query


class SearchState(TypedDict, total=False):
    """State for discovery search workflow."""

    query: str
    location: Optional[str]
    country: Optional[str]
    search_lang: Optional[str]
    time_window_days: int
    count: int
    latitude: Optional[float]
    longitude: Optional[float]
    formatted_query: str
    built_query: str
    results: List[SearchResult]


def _time_window_phrase(days: int) -> str:
    if days <= 1:
        return "today"
    if days <= 3:
        return "this weekend"
    if days <= 7:
        return "this week"
    return f"next {days} days"


def build_query(state: SearchState) -> SearchState:
    query = state.get("formatted_query") or state.get("query", "")
    location = state.get("location")
    latitude = state.get("latitude")
    longitude = state.get("longitude")
    days = state.get("time_window_days", 7)
    time_phrase = _time_window_phrase(days)

    parts = [query]
    if location:
        parts.append(location)
    elif latitude is not None and longitude is not None:
        parts.append(f"near {latitude:.4f}, {longitude:.4f}")
    if time_phrase:
        parts.append(time_phrase)

    built = " ".join(part for part in parts if part)
    return {"built_query": built}


def search_web(provider: SearchProvider, state: SearchState) -> SearchState:
    request = SearchRequest(
        query=state.get("built_query") or state.get("query", ""),
        location=state.get("location"),
        country=state.get("country"),
        search_lang=state.get("search_lang"),
        time_window_days=state.get("time_window_days", 7),
        count=state.get("count", 10),
    )

    results = provider.search(request)
    return {"results": results}


def build_search_graph(provider: SearchProvider):
    graph = StateGraph(SearchState)

    graph.add_node("format_query", format_query)
    graph.add_node("build_query", build_query)
    graph.add_node("search_web", lambda state: search_web(provider, state))

    graph.set_entry_point("format_query")
    graph.add_edge("format_query", "build_query")
    graph.add_edge("build_query", "search_web")
    graph.add_edge("search_web", END)

    return graph.compile()
def format_query(state: SearchState) -> SearchState:
    raw_query = state.get("query", "")
    formatted = format_search_query(raw_query)
    return {"formatted_query": formatted}
