"""Unit tests for routes service."""

import pytest
from unittest.mock import patch, MagicMock
from src.services.routes_service import RoutesService


class TestRoutesService:
    """Test cases for RoutesService."""
    
    @pytest.fixture
    def routes_service(self):
        """Create RoutesService instance with mocked environment."""
        with patch.dict('os.environ', {
            'OPENROUTE_SERVICE_API_KEY': 'test_api_key',
            'OPENROUTE_SERVICE_BASE_URL': 'https://api.openrouteservice.org'
        }):
            return RoutesService()
    
    def test_routes_service_initialization(self, routes_service):
        """Test RoutesService initialization."""
        assert routes_service.api_key == 'test_api_key'
        assert routes_service.base_url == 'https://api.openrouteservice.org'
    
    def test_routes_service_missing_api_key(self):
        """Test that RoutesService raises error when API key is missing."""
        with patch.dict('os.environ', {
            'OPENROUTE_SERVICE_BASE_URL': 'https://api.openrouteservice.org'
        }, clear=True):
            with pytest.raises(ValueError, match="OPENROUTE_SERVICE_API_KEY"):
                RoutesService()
    
    def test_routes_service_missing_base_url(self):
        """Test that RoutesService raises error when base URL is missing."""
        with patch.dict('os.environ', {
            'OPENROUTE_SERVICE_API_KEY': 'test_key'
        }, clear=True):
            with pytest.raises(ValueError, match="OPENROUTE_SERVICE_BASE_URL"):
                RoutesService()
    
    @patch('src.services.routes_service.requests.post')
    def test_get_travel_time_success(self, mock_post, routes_service):
        """Test successful travel time retrieval."""
        # Mock the API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'durations': [[0.0, 23400.0], [23400.0, 0.0]],
            'destinations': [
                {'location': [-122.4194, 37.7749]},
                {'location': [-118.2437, 34.0522]}
            ]
        }
        mock_post.return_value = mock_response
        
        # Test get_travel_time
        start = (-122.4194, 37.7749)  # SF
        end = (-118.2437, 34.0522)    # LA
        travel_time = routes_service.get_travel_time(start, end)
        
        # 23400 seconds = 390 minutes
        assert travel_time == 390
        
        # Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert 'https://api.openrouteservice.org/v2/matrix/driving-car' in call_args[0]
    
    @patch('src.services.routes_service.requests.post')
    def test_get_travel_time_different_profile(self, mock_post, routes_service):
        """Test travel time with different routing profile."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'durations': [[0.0, 5400.0], [5400.0, 0.0]]
        }
        mock_post.return_value = mock_response
        
        travel_time = routes_service.get_travel_time(
            (-122.4194, 37.7749),
            (-118.2437, 34.0522),
            profile='foot-walking'
        )
        
        # 5400 seconds = 90 minutes
        assert travel_time == 90
        
        # Verify the profile was used in URL
        call_args = mock_post.call_args
        assert 'foot-walking' in call_args[0][0]
    
    @patch('src.services.routes_service.requests.post')
    def test_get_travel_time_zero_distance(self, mock_post, routes_service):
        """Test travel time for same location (zero distance)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'durations': [[0.0, 0.0], [0.0, 0.0]]
        }
        mock_post.return_value = mock_response
        
        travel_time = routes_service.get_travel_time(
            (-122.4194, 37.7749),
            (-122.4194, 37.7749)
        )
        
        assert travel_time == 0
    
    @patch('src.services.routes_service.requests.post')
    def test_get_travel_time_api_error(self, mock_post, routes_service):
        """Test handling of API errors."""
        mock_post.side_effect = Exception("API Error")
        
        with pytest.raises(Exception, match="API Error"):
            routes_service.get_travel_time(
                (-122.4194, 37.7749),
                (-118.2437, 34.0522)
            )
