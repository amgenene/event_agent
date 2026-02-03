"""Unit tests for calendar agent module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone
from src.calendar_agent.scheduler import CalendarAgent, CalendarEvent


class TestCalendarAgent:
    """Test cases for CalendarAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create calendar agent instance with mocked calendar service."""
        with patch('src.calendar_agent.scheduler.CalendarService'):
            agent = CalendarAgent(participants=['user@example.com'])
            return agent
    
    @pytest.fixture
    def sample_availabilities(self):
        """Create sample availability slots."""
        return [
            {
                "start_time": int(datetime(2026, 1, 21, 9, 0, tzinfo=timezone.utc).timestamp()),
                "end_time": int(datetime(2026, 1, 21, 10, 0, tzinfo=timezone.utc).timestamp()),
                "emails": ['user@example.com']
            },
            {
                "start_time": int(datetime(2026, 1, 21, 14, 0, tzinfo=timezone.utc).timestamp()),
                "end_time": int(datetime(2026, 1, 21, 15, 0, tzinfo=timezone.utc).timestamp()),
                "emails": ['user@example.com']
            },
        ]
    
    def test_agent_initialization(self, agent):
        """Test agent initialization."""
        assert agent.participants == ['user@example.com']
        assert agent.calendar_service is not None
    
    def test_get_calendar_availability_returns_list(self, agent, sample_availabilities):
        """Test that get_calendar_availability returns a list of availabilities."""
        # Mock the calendar service
        agent.calendar_service.get_availability = MagicMock(return_value=sample_availabilities)
        
        result = agent.get_calendar_availability()
        
        assert isinstance(result, list)
        assert len(result) == 2
        
        # Print availabilities in readable format
        print("\n📅 Calendar Availabilities:")
        print(f"Total slots found: {len(result)}\n")
        
        for i, avail in enumerate(result, 1):
            start_time = datetime.fromtimestamp(avail['start_time'], tz=timezone.utc)
            end_time = datetime.fromtimestamp(avail['end_time'], tz=timezone.utc)
            duration = (end_time - start_time).total_seconds() / 60
            
            print(f"Slot {i}:")
            print(f"  Start: {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"  End:   {end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"  Duration: {int(duration)} minutes\n")
    
    def test_get_calendar_availability_calls_service(self, agent, sample_availabilities):
        """Test that get_calendar_availability calls calendar service."""
        agent.calendar_service.get_availability = MagicMock(return_value=sample_availabilities)
        
        agent.get_calendar_availability()
        
        # Verify service was called with participants
        agent.calendar_service.get_availability.assert_called_once_with(agent.participants)
    
    def test_get_calendar_availability_with_multiple_participants(self):
        """Test calendar availability with multiple participants."""
        with patch('src.calendar_agent.scheduler.CalendarService'):
            participants = ['user1@example.com', 'user2@example.com']
            agent = CalendarAgent(participants=participants)
            
            assert agent.participants == participants
            assert len(agent.participants) == 2
    
    def test_availability_has_timestamps(self, agent, sample_availabilities):
        """Test that availabilities have proper timestamp fields."""
        agent.calendar_service.get_availability = MagicMock(return_value=sample_availabilities)
        
        result = agent.get_calendar_availability()
        
        for availability in result:
            assert 'start_time' in availability
            assert 'end_time' in availability
            assert isinstance(availability['start_time'], int)
            assert isinstance(availability['end_time'], int)
    
    def test_validate_travel_time_within_limit(self, agent):
        """Test travel time validation."""
        is_valid = agent.validate_travel_time(
            travel_time_minutes=20,
            max_transit_minutes=30
        )
        
        assert isinstance(is_valid, bool)
        assert is_valid is True  # 20 min travel is within 30 min limit
    
    def test_validate_travel_time_exceeds_limit(self, agent):
        """Test travel time validation when exceeding limit."""
        is_valid = agent.validate_travel_time(
            travel_time_minutes=50,
            max_transit_minutes=30
        )
        
        assert is_valid is False
    
    def test_calendar_event_creation(self):
        """Test CalendarEvent dataclass."""
        event = CalendarEvent(
            id="1",
            title="Test Event",
            start_time=datetime(2026, 1, 21, 19, 0),
            end_time=datetime(2026, 1, 21, 20, 0),
            location="Downtown"
        )
        
        assert event.title == "Test Event"
        assert event.location == "Downtown"
        assert event.id == "1"
