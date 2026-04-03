"""Dependency injection for FastAPI endpoints."""

from functools import lru_cache

from src.auditor.verifier import Auditor
from src.calendar_agent.scheduler import CalendarAgent
from src.discovery_agent.providers.tavily import TavilyProvider
from src.discovery_agent.searcher import DiscoveryAgent
from src.input_parser.parser import InputParser
from src.orchestration.manager import Manager
from src.resilience.edge_case_handler import EdgeCaseHandler


@lru_cache
def get_input_parser() -> InputParser:
    """Get InputParser singleton."""
    return InputParser()


@lru_cache
def get_calendar_agent() -> CalendarAgent:
    """Get CalendarAgent singleton."""
    return CalendarAgent(participants=["alazar.genene@gmail.com"])


@lru_cache
def get_tavily_provider() -> TavilyProvider:
    """Get TavilyProvider singleton."""
    return TavilyProvider()


@lru_cache
def get_discovery_agent() -> DiscoveryAgent:
    """Get DiscoveryAgent singleton."""
    return DiscoveryAgent(get_tavily_provider())


@lru_cache
def get_auditor() -> Auditor:
    """Get Auditor singleton."""
    return Auditor()


@lru_cache
def get_edge_case_handler() -> EdgeCaseHandler:
    """Get EdgeCaseHandler singleton."""
    return EdgeCaseHandler()


@lru_cache
def get_manager() -> Manager:
    """Get Manager singleton with all dependencies injected."""
    return Manager(
        input_parser=get_input_parser(),
        calendar_agent=get_calendar_agent(),
        discovery_agent=get_discovery_agent(),
        auditor=get_auditor(),
        edge_case_handler=get_edge_case_handler(),
    )
