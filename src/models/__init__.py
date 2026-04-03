"""Pydantic models for API request/response schemas."""

from typing import List, Optional

from pydantic import BaseModel


class UserPreferences(BaseModel):
    """User preferences for event discovery."""

    home_city: Optional[str] = None
    favorite_genres: Optional[List[str]] = None
    radius_miles: Optional[int] = 5
    max_transit_minutes: Optional[int] = 30
    time_window_days: Optional[int] = 7
    country: Optional[str] = None
    search_lang: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class EventSearchRequest(BaseModel):
    """Request model for event search."""

    query: str
    preferences: Optional[UserPreferences] = None


class EventResponse(BaseModel):
    """Response model for discovered event."""

    id: str
    title: str
    location: str
    date: str
    time: str
    description: str
    url: str
    price: str = "Free"
    category: Optional[str] = None


class SearchResponse(BaseModel):
    """Response model for search results."""

    success: bool
    events: List[EventResponse]
    message: str
    query_used: Optional[str] = None


class VerifyEventRequest(BaseModel):
    """Request model for event verification."""

    description: str


class VerifyEventResponse(BaseModel):
    """Response model for event verification."""

    status: str
    warnings: List[str]


class TranscribeFileRequest(BaseModel):
    """Request model for transcribing a file by path."""

    file_path: str
