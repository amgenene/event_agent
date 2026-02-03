"""Unit tests for calendar service."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from src.services.calendar_service import CalendarService


class MockTimeSlot:
    """Mock TimeSlot object from Nylas SDK."""
    def __init__(self, start_time, end_time, emails=None):
        self.start_time = start_time
        self.end_time = end_time
        self.emails = emails or ['user@example.com']


class MockGetAvailabilityResponse:
    """Mock GetAvailabilityResponse object from Nylas SDK."""
    def __init__(self, time_slots):
        self.time_slots = time_slots


class TestCalendarService:
    """Test cases for CalendarService."""
    
    @pytest.fixture
    def mock_nylas_client(self):
        """Create mock Nylas client."""
        return MagicMock()
    
    @pytest.fixture
    def service(self, mock_nylas_client):
        """Create CalendarService instance with mocked Nylas client."""
        with patch.dict('os.environ', {
            'NYLAS_API_KEY': 'test_key',
            'NYLAS_API_URI': 'test_uri',
            'NYLAS_GRANT_ID': 'test_grant_id'
        }):
            with patch('src.services.calendar_service.Client', return_value=mock_nylas_client):
                return CalendarService()
    
    @pytest.fixture
    def sample_response(self):
        """Create sample availability response."""
        time_slots = [
            MockTimeSlot(
                start_time=int(datetime(2026, 1, 21, 9, 0, tzinfo=timezone.utc).timestamp()),
                end_time=int(datetime(2026, 1, 21, 10, 0, tzinfo=timezone.utc).timestamp()),
                emails=['user@example.com']
            ),
            MockTimeSlot(
                start_time=int(datetime(2026, 1, 21, 14, 0, tzinfo=timezone.utc).timestamp()),
                end_time=int(datetime(2026, 1, 21, 15, 0, tzinfo=timezone.utc).timestamp()),
                emails=['user@example.com']
            ),
        ]
        # Return as tuple like real SDK: (response_object, request_id, headers)
        return (MockGetAvailabilityResponse(time_slots), 'test_request_id', {})
    
    def test_service_initialization(self, service):
        """Test CalendarService initialization."""
        assert service.grant_id == 'test_grant_id'
        assert service.nylas is not None
    
    def test_service_missing_api_key(self):
        """Test that service raises error when API key is missing."""
        with patch.dict('os.environ', {
            'NYLAS_API_URI': 'test_uri',
            'NYLAS_GRANT_ID': 'test_grant_id'
        }, clear=True):
            with pytest.raises(ValueError, match="NYLAS_API_KEY"):
                CalendarService()
    
    def test_service_missing_api_uri(self):
        """Test that service raises error when API URI is missing."""
        with patch.dict('os.environ', {
            'NYLAS_API_KEY': 'test_key',
            'NYLAS_GRANT_ID': 'test_grant_id'
        }, clear=True):
            with pytest.raises(ValueError, match="NYLAS_API_URI"):
                CalendarService()
    
    def test_service_missing_grant_id(self):
        """Test that service raises error when grant ID is missing."""
        with patch.dict('os.environ', {
            'NYLAS_API_KEY': 'test_key',
            'NYLAS_API_URI': 'test_uri'
        }, clear=True):
            with pytest.raises(ValueError, match="NYLAS_GRANT_ID"):
                CalendarService()
    
    def test_get_availability_returns_list(self, service, mock_nylas_client, sample_response):
        """Test that get_availability returns a list of dicts."""
        mock_nylas_client.calendars.get_availability.return_value = sample_response
        
        result = service.get_availability(['user@example.com'])
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(slot, dict) for slot in result)
        assert all('start_time' in slot for slot in result)
        assert all('end_time' in slot for slot in result)
        assert all('emails' in slot for slot in result)
    
    def test_get_availability_calls_api(self, service, mock_nylas_client, sample_response):
        """Test that get_availability calls Nylas API."""
        mock_nylas_client.calendars.get_availability.return_value = sample_response
        
        service.get_availability(['user@example.com'])
        
        assert mock_nylas_client.calendars.get_availability.called
        call_kwargs = mock_nylas_client.calendars.get_availability.call_args
        assert 'request_body' in call_kwargs.kwargs
    
    def test_get_availability_with_multiple_participants(self, service, mock_nylas_client, sample_response):
        """Test get_availability with multiple participants."""
        mock_nylas_client.calendars.get_availability.return_value = sample_response
        
        participants = ['user1@example.com', 'user2@example.com']
        result = service.get_availability(participants)
        
        assert isinstance(result, list)
        
        # Verify request included both participants
        call_kwargs = mock_nylas_client.calendars.get_availability.call_args
        request_body = call_kwargs.kwargs['request_body']
        assert len(request_body['participants']) == 2
    
    def test_get_availability_empty_response(self, service, mock_nylas_client):
        """Test handling of empty availability response."""
        empty_response = (MockGetAvailabilityResponse([]), 'test_id', {})
        mock_nylas_client.calendars.get_availability.return_value = empty_response
        
        result = service.get_availability(['user@example.com'])
        
        assert result == []
    
    def test_get_availability_api_error(self, service, mock_nylas_client):
        """Test handling of API errors."""
        mock_nylas_client.calendars.get_availability.side_effect = Exception("API Error")
        
        with pytest.raises(Exception, match="API Error"):
            service.get_availability(['user@example.com'])
