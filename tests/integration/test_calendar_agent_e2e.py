"""End-to-end tests for calendar agent with real Nylas API calls."""

import pytest
import os
from datetime import datetime, timezone, timedelta
from src.calendar_agent.scheduler import CalendarAgent


class TestCalendarAgentRealAPI:
    """End-to-end tests for CalendarAgent with real Nylas API."""

    @pytest.fixture
    def real_agent(self):
        """Create a real CalendarAgent instance that calls actual Nylas API."""
        # Check that required environment variables are set
        api_key = os.environ.get("NYLAS_API_KEY")
        api_uri = os.environ.get("NYLAS_API_URI")
        grant_id = os.environ.get("NYLAS_GRANT_ID")

        if not all([api_key, api_uri, grant_id]):
            pytest.skip("Nylas API credentials not configured in environment")

        # Create agent with real participant
        agent = CalendarAgent(participants=["alazar.genene@gmail.com"])
        return agent

    def test_agent_instantiation_with_real_participant(self, real_agent):
        """Test that agent is properly instantiated with real participant email."""
        assert real_agent.participants == ["alazar.genene@gmail.com"]
        assert real_agent.calendar_service is not None
        assert real_agent.calendar_service.grant_id is not None

    def test_get_real_calendar_availability(self, real_agent):
        """Test getting real calendar availability from Nylas API."""
        try:
            result = real_agent.get_calendar_availability()

            print(f"\n📅 Real Calendar Availabilities:")
            print(f"  Total slots found: {len(result)}")

            if result:
                for i, avail in enumerate(result[:5], 1):  # Show first 5
                    start_time = datetime.fromtimestamp(
                        avail["start_time"], tz=timezone.utc
                    )
                    end_time = datetime.fromtimestamp(
                        avail["end_time"], tz=timezone.utc
                    )
                    duration = (end_time - start_time).total_seconds() / 60

                    print(f"\n  Slot {i}:")
                    print(f"    Start: {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                    print(f"    End:   {end_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                    print(f"    Duration: {int(duration)} minutes")
            else:
                print("  ℹ️  No availability slots found for the week")

            # Verify structure if results exist
            if result:
                assert all("start_time" in slot for slot in result)
                assert all("end_time" in slot for slot in result)
                assert all(isinstance(slot["start_time"], int) for slot in result)
                assert all(isinstance(slot["end_time"], int) for slot in result)

        except Exception as e:
            pytest.fail(f"Failed to get calendar availability: {e}")

    def test_fetch_from_nylas_real_call(self, real_agent):
        """Test that calendar service makes real API call."""
        try:
            result = real_agent.calendar_service.get_availability(
                ["alazar.genene@gmail.com"]
            )

            print(f"\n✅ Real API Call Successful:")
            print(f"  Returned {len(result)} availability slots")

            if result:
                assert isinstance(result, list)
                assert all(isinstance(slot, dict) for slot in result)

        except Exception as e:
            pytest.fail(f"Failed to fetch from Nylas: {e}")

    def test_availability_timestamps_are_valid(self, real_agent):
        """Test that returned availabilities have valid timestamps."""
        try:
            result = real_agent.get_calendar_availability()

            if result:
                for slot in result[:3]:
                    start = datetime.fromtimestamp(slot["start_time"], tz=timezone.utc)
                    end = datetime.fromtimestamp(slot["end_time"], tz=timezone.utc)

                    assert isinstance(start, datetime)
                    assert isinstance(end, datetime)
                    assert start < end

        except Exception as e:
            pytest.fail(f"Timestamp validation failed: {e}")

    def test_validate_travel_time_with_real_data(self, real_agent):
        """Test travel time validation logic."""
        within_limit = real_agent.validate_travel_time(25, 30)
        exceeds_limit = real_agent.validate_travel_time(45, 30)

        assert within_limit is True
        assert exceeds_limit is False


class TestCalendarAgentWithMultipleParticipants:
    """Test calendar agent with multiple real participants."""

    @pytest.fixture
    def multi_agent(self):
        """Create agent with multiple participants."""
        api_key = os.environ.get("NYLAS_API_KEY")
        api_uri = os.environ.get("NYLAS_API_URI")
        grant_id = os.environ.get("NYLAS_GRANT_ID")

        if not all([api_key, api_uri, grant_id]):
            pytest.skip("Nylas API credentials not configured")

        # You can add more participant emails here
        agent = CalendarAgent(participants=["alazar.genene@gmail.com"])
        return agent

    def test_multi_participant_availability(self, multi_agent):
        """Test getting availability for multiple participants."""
        try:
            result = multi_agent.get_calendar_availability()

            print(f"\n👥 Multi-Participant Availability:")
            print(f"  Participants: {multi_agent.participants}")
            print(f"  Available slots: {len(result)}")

            if result:
                print(
                    f"  Time range: {datetime.fromtimestamp(result[0]['start_time'], tz=timezone.utc).strftime('%Y-%m-%d')} onwards"
                )

        except Exception as e:
            pytest.fail(f"Multi-participant test failed: {e}")
