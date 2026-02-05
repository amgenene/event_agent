"""Helpers to format user input into search-friendly queries."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_PREFIX_PATTERNS = [
    r"can you",
    r"could you",
    r"please",
    r"i want to",
    r"i would like to",
    r"i'd like to",
    r"help me",
    r"show me",
    r"find me",
    r"find",
    r"look for",
    r"search for",
    r"get me",
    r"what are",
    r"any",
]

_EVENT_KEYWORDS = [
    "event",
    "events",
    "concert",
    "show",
    "festival",
    "meetup",
    "talk",
    "lecture",
    "workshop",
    "class",
    "market",
    "fair",
    "exhibition",
]

_STOPWORDS = {
    "a",
    "an",
    "the",
    "me",
    "my",
    "for",
    "to",
    "in",
    "near",
    "around",
    "at",
    "this",
    "today",
    "tomorrow",
    "week",
    "weekend",
    "next",
    "days",
    "day",
    "free",
    "events",
    "event",
    "concert",
    "show",
    "festival",
    "meetup",
    "talk",
    "lecture",
    "workshop",
    "class",
    "market",
    "fair",
    "exhibition",
}


def _extract_core_phrase(query: str) -> str:
    tokens = [t for t in query.split() if t and t not in _STOPWORDS]
    if not tokens:
        return ""
    # Keep a short, focused phrase to quote
    return " ".join(tokens[:4])


def format_search_query(raw_query: str) -> str:
    """Format raw user input into a concise search query."""
    if not raw_query:
        return ""

    query = raw_query.strip().lower()
    query = re.sub(r"[?!.]+$", "", query).strip()

    for prefix in _PREFIX_PATTERNS:
        query = re.sub(rf"^{prefix}\s+", "", query)

    query = re.sub(r"\s+", " ", query).strip()

    if not query:
        return raw_query.strip()

    core_phrase = _extract_core_phrase(query)
    quoted = f"\"{core_phrase}\"" if core_phrase else ""

    if not re.search(rf"\b({'|'.join(_EVENT_KEYWORDS)})\b", query):
        query = f"{query} events"

    if "free" not in query:
        query = f"free {query}"

    if quoted:
        query = f"{query} {quoted}"

    logger.debug("Formatted query: '%s' -> '%s'", raw_query, query)
    return query
