"""Integration test for RoutesService with real OpenRouteService API."""

import os
import pytest
from src.services.routes_service import RoutesService

@pytest.mark.skipif(
    not os.environ.get("OPENROUTE_SERVICE_API_KEY") or not os.environ.get("OPENROUTE_SERVICE_BASE_URL"),
    reason="OpenRouteService API credentials not set"
)
def test_get_travel_time_real_api():
    """Test get_travel_time with real OpenRouteService API for two locations."""
    routes = RoutesService()
    # San Francisco to Los Angeles
    sf_coords = (-122.4194, 37.7749)
    la_coords = (-118.2437, 34.0522)
    travel_time = routes.get_travel_time(sf_coords, la_coords)
    print(f"Travel time SF to LA: {travel_time} minutes")
    assert isinstance(travel_time, int)
    assert travel_time > 0

    # New York to Boston
    ny_coords = (-74.0060, 40.7128)
    boston_coords = (-71.0589, 42.3601)
    travel_time2 = routes.get_travel_time(ny_coords, boston_coords)
    print(f"Travel time NY to Boston: {travel_time2} minutes")
    assert isinstance(travel_time2, int)
    assert travel_time2 > 0
