"""Service for calendar operations via Nylas API."""

import os
from datetime import datetime, timezone, timedelta
from nylas import Client
from dotenv import load_dotenv

load_dotenv(dotenv_path='.env.local')


class CalendarService:
    """Handles calendar operations and Nylas API integration."""
    
    def __init__(self):
        """Initialize with Nylas API credentials."""
        api_key = os.environ.get("NYLAS_API_KEY")
        api_uri = os.environ.get("NYLAS_API_URI")
        self.grant_id = os.environ.get("NYLAS_GRANT_ID")
        
        if not api_key:
            raise ValueError("NYLAS_API_KEY not set in environment")
        if not api_uri:
            raise ValueError("NYLAS_API_URI not set in environment")
        if not self.grant_id:
            raise ValueError("NYLAS_GRANT_ID not set in environment")
        
        self.nylas = Client(api_key, api_uri)
    
    def get_availability(self, participants: list[str]) -> list:
        """
        Fetch calendar availability from Nylas API.
        
        Args:
            participants: List of participant email addresses to check calendars for
        
        Returns:
            List of dicts with 'start_time', 'end_time', and 'emails' keys
            
        Reference: https://docs.nylas.com/v3/endpoints/calendar/availability/get-availability
        """
        now = datetime.now(timezone.utc)
        
        # Round to nearest 5 minutes (Nylas requirement)
        remainder = now.minute % 5
        if remainder >= 3:
            now = now.replace(minute=((now.minute // 5) + 1) * 5, second=0, microsecond=0)
        else:
            now = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)
        
        # Handle hour overflow
        if now.minute == 60:
            now = now.replace(minute=0) + timedelta(hours=1)
        
        # Calculate end of week (Sunday)
        days_until_sunday = 6 - now.weekday()
        if days_until_sunday < 0:
            days_until_sunday += 7
        
        end_of_week = (now + timedelta(days=days_until_sunday)).replace(
            hour=23, minute=55, second=0, microsecond=0  # 23:55 to ensure multiple of 5
        )

        start_time = int(now.timestamp())
        end_time = int(end_of_week.timestamp())
        
        # Build participants array per Nylas spec
        participants_array = []
        for email in participants:
            participant = {
                "email": email,
                "open_hours": [
                    {
                        "days": [0, 1, 2, 3, 4],  # Monday-Friday
                        "timezone": "America/Los_Angeles",
                        "start": "9:00",
                        "end": "17:00",
                        "exdates": []
                    }
                ]
            }
            # Add grant_id only for the main participant
            if email == participants[0]:
                participant["grant_id"] = self.grant_id
            participants_array.append(participant)
        
        # Build request body per Nylas API spec
        request_body = {
            "participants": participants_array,
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": 60,  # Required, must be multiple of 5
            "interval_minutes": 30,  # Find slots every 30 minutes
            "round_to": 15,  # Round to nearest 15 minutes
            "availability_rules": {
                "availability_method": "max-availability",  # Find times when person is most available
                "buffer": {
                    "before": 15,   # 15 min buffer before meetings
                    "after": 15     # 15 min buffer after meetings
                }
            }
        }
        
        print(f"\n📤 Nylas API Request:")
        print(f"  Participants: {[p['email'] for p in participants_array]}")
        print(f"  Start: {datetime.fromtimestamp(start_time, tz=timezone.utc).strftime('%Y-%m-%d %H:%M %Z')}")
        print(f"  End: {datetime.fromtimestamp(end_time, tz=timezone.utc).strftime('%Y-%m-%d %H:%M %Z')}")
        print(f"  Duration: 60 minutes | Interval: 30 minutes")
        
        try:
            response = self.nylas.calendars.get_availability(request_body=request_body)
            
            # Unpack the tuple response from Nylas SDK
            # Returns: (GetAvailabilityResponse, request_id, headers)
            if isinstance(response, tuple):
                availability_response = response[0]
            else:
                availability_response = response
            
            # Extract time slots from the response object
            if hasattr(availability_response, 'time_slots'):
                time_slots = availability_response.time_slots
            elif hasattr(availability_response, 'data') and hasattr(availability_response.data, 'time_slots'):
                time_slots = availability_response.data.time_slots
            else:
                return []
            
            # Convert TimeSlot objects to dicts for consistent interface
            result = []
            for slot in time_slots:
                result.append({
                    'start_time': slot.start_time,
                    'end_time': slot.end_time,
                    'emails': slot.emails if hasattr(slot, 'emails') else participants
                })
            
            return result
            
        except Exception as e:
            print(f"\n❌ Nylas API Error: {e}")
            raise
