"""Service for routing and travel time calculations via OpenRouteService."""

import os
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path='.env.local')


class RoutesService:
    """Handles travel time and routing via OpenRouteService API."""
    
    def __init__(self):
        """Initialize with OpenRouteService API key and base URL."""
        self.api_key = os.environ.get("OPENROUTE_SERVICE_API_KEY")
        self.base_url = os.environ.get("OPENROUTE_SERVICE_BASE_URL")
        
        if not self.api_key:
            raise ValueError("OPENROUTE_SERVICE_API_KEY not set in environment")
        if not self.base_url:
            raise ValueError("OPENROUTE_SERVICE_BASE_URL not set in environment")
    
    def get_travel_time(
        self,
        start_location: tuple[float, float],  # (lon, lat)
        end_location: tuple[float, float],    # (lon, lat)
        profile: str = "driving-car"
    ) -> int:
        """
        Get travel time between two locations.
        
        Args:
            start_location: (longitude, latitude) tuple
            end_location: (longitude, latitude) tuple
            profile: Routing profile (driving-car, foot-walking, cycling-regular)
        
        Returns:
            Travel time in minutes
            
        Reference: OpenRouteService Matrix API returns durations array
        """
        request_body = {
            "locations": [list(start_location), list(end_location)],
            "profile": profile,
            "metrics": ["duration"]
        }
        
        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/v2/matrix/{profile}",
                json=request_body,
                headers=headers
            )
            response.raise_for_status()
            
            # Extract duration from durations array [0][1] = from first to second location
            data = response.json()
            duration_seconds = data['durations'][0][1]
            return int(duration_seconds / 60)  # Convert to minutes
            
        except Exception as e:
            print(f"❌ OpenRouteService Error: {e}")
            raise
