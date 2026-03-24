"""
CALENDAR BOOKING - Book meetings in seconds.

Integrates with:
- Cal.com (free, open source)
- Calendly (popular, easy)
- Direct calendar links
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class CalendarBooking:
    """
    Calendar booking integration.
    
    Setup options:
    
    1. Simple (just a link):
       Add to .env: BOOKING_URL=https://calendly.com/yourname/15min
       
    2. Cal.com API:
       Add to .env: CAL_COM_API_KEY=xxx
       
    3. Calendly API:
       Add to .env: CALENDLY_API_KEY=xxx
    """
    
    def __init__(self):
        """Initialize calendar service."""
        self.booking_url = os.getenv("BOOKING_URL")
        self.cal_api_key = os.getenv("CAL_COM_API_KEY")
        self.calendly_api_key = os.getenv("CALENDLY_API_KEY")
        
        self.service = None
        if self.cal_api_key:
            self.service = "cal"
            logger.info("✅ Cal.com API configured")
        elif self.calendly_api_key:
            self.service = "calendly"
            logger.info("✅ Calendly API configured")
        elif self.booking_url:
            self.service = "link"
            logger.info(f"✅ Booking URL configured: {self.booking_url}")
        else:
            logger.warning("No calendar configured. Set BOOKING_URL, CAL_COM_API_KEY, or CALENDLY_API_KEY")
            
    def is_configured(self) -> bool:
        """Check if calendar is configured."""
        return self.service is not None or self.booking_url is not None
        
    def get_booking_url(
        self,
        lead: Dict[str, Any] = None,
        prefill: bool = True,
    ) -> str:
        """
        Get a booking URL, optionally prefilled with lead data.
        
        Args:
            lead: Lead data for prefilling
            prefill: Whether to prefill form fields
            
        Returns:
            Booking URL
        """
        base_url = self.booking_url
        
        if not base_url:
            # Default Cal.com format
            base_url = "https://cal.com/your-username/15min"
            
        if not prefill or not lead:
            return base_url
            
        # Add prefill parameters
        params = {}
        
        if lead.get("email"):
            params["email"] = lead["email"]
        if lead.get("owner_name"):
            params["name"] = lead["owner_name"]
        elif lead.get("business_name"):
            params["name"] = lead["business_name"]
        if lead.get("phone"):
            params["phone"] = lead["phone"]
            
        # Add custom fields
        if lead.get("business_name"):
            params["company"] = lead["business_name"]
            
        if params:
            separator = "&" if "?" in base_url else "?"
            return f"{base_url}{separator}{urlencode(params)}"
            
        return base_url
        
    def get_available_slots(
        self,
        days_ahead: int = 7,
        duration_minutes: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Get available booking slots.
        
        Args:
            days_ahead: How many days to look ahead
            duration_minutes: Meeting duration
            
        Returns:
            List of available slots
        """
        if self.service == "cal":
            return self._get_cal_slots(days_ahead, duration_minutes)
        elif self.service == "calendly":
            return self._get_calendly_slots(days_ahead, duration_minutes)
        else:
            # Return placeholder slots
            return self._generate_placeholder_slots(days_ahead)
            
    def _get_cal_slots(self, days_ahead: int, duration: int) -> List[Dict[str, Any]]:
        """Get available slots from Cal.com."""
        import requests
        
        try:
            headers = {
                "Authorization": f"Bearer {self.cal_api_key}",
                "Content-Type": "application/json",
            }
            
            start_date = datetime.now().isoformat()
            end_date = (datetime.now() + timedelta(days=days_ahead)).isoformat()
            
            response = requests.get(
                f"https://api.cal.com/v1/availability",
                headers=headers,
                params={
                    "startTime": start_date,
                    "endTime": end_date,
                    "eventTypeId": os.getenv("CAL_EVENT_TYPE_ID", "1"),
                },
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("slots", [])
            else:
                logger.error(f"Cal.com API error: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to get Cal.com slots: {e}")
            return []
            
    def _get_calendly_slots(self, days_ahead: int, duration: int) -> List[Dict[str, Any]]:
        """Get available slots from Calendly."""
        import requests
        
        try:
            headers = {
                "Authorization": f"Bearer {self.calendly_api_key}",
                "Content-Type": "application/json",
            }
            
            # First get user URI
            user_response = requests.get(
                "https://api.calendly.com/users/me",
                headers=headers,
            )
            
            if user_response.status_code != 200:
                return []
                
            user_uri = user_response.json().get("resource", {}).get("uri")
            
            # Get event types
            events_response = requests.get(
                "https://api.calendly.com/event_types",
                headers=headers,
                params={"user": user_uri},
            )
            
            if events_response.status_code == 200:
                events = events_response.json().get("collection", [])
                # Return event type scheduling URLs
                return [
                    {
                        "name": e.get("name"),
                        "url": e.get("scheduling_url"),
                        "duration": e.get("duration"),
                    }
                    for e in events
                ]
                
            return []
            
        except Exception as e:
            logger.error(f"Failed to get Calendly slots: {e}")
            return []
            
    def _generate_placeholder_slots(self, days_ahead: int) -> List[Dict[str, Any]]:
        """Generate placeholder slots for display."""
        slots = []
        now = datetime.now()
        
        for day in range(1, days_ahead + 1):
            date = now + timedelta(days=day)
            if date.weekday() < 5:  # Weekdays only
                for hour in [9, 10, 11, 14, 15, 16]:  # Business hours
                    slot_time = date.replace(hour=hour, minute=0, second=0)
                    slots.append({
                        "start": slot_time.isoformat(),
                        "end": (slot_time + timedelta(minutes=15)).isoformat(),
                        "available": True,
                    })
                    
        return slots[:10]  # Return first 10 slots
        
    def create_booking(
        self,
        lead: Dict[str, Any],
        slot: Dict[str, Any],
        notes: str = None,
    ) -> Dict[str, Any]:
        """
        Create a booking for a lead.
        
        Args:
            lead: Lead data
            slot: Selected time slot
            notes: Optional meeting notes
            
        Returns:
            {"success": bool, "booking_id": str, "confirmation_url": str}
        """
        if self.service == "cal":
            return self._create_cal_booking(lead, slot, notes)
        elif self.service == "calendly":
            # Calendly doesn't support programmatic booking creation
            # Return the scheduling URL instead
            return {
                "success": False,
                "error": "Calendly requires user to book via URL",
                "booking_url": self.get_booking_url(lead),
            }
        else:
            return {
                "success": False,
                "error": "No calendar API configured",
                "booking_url": self.get_booking_url(lead),
            }
            
    def _create_cal_booking(
        self,
        lead: Dict[str, Any],
        slot: Dict[str, Any],
        notes: str,
    ) -> Dict[str, Any]:
        """Create a booking via Cal.com API."""
        import requests
        
        try:
            headers = {
                "Authorization": f"Bearer {self.cal_api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "eventTypeId": int(os.getenv("CAL_EVENT_TYPE_ID", "1")),
                "start": slot.get("start"),
                "responses": {
                    "name": lead.get("owner_name") or lead.get("business_name"),
                    "email": lead.get("email"),
                    "notes": notes or f"Lead from Goldmine: {lead.get('business_name')}",
                },
                "metadata": {
                    "lead_id": lead.get("lead_id"),
                    "business_name": lead.get("business_name"),
                },
            }
            
            response = requests.post(
                "https://api.cal.com/v1/bookings",
                headers=headers,
                json=payload,
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                logger.info(f"📅 Booking created for {lead.get('business_name')}")
                return {
                    "success": True,
                    "booking_id": data.get("id"),
                    "confirmation_url": data.get("confirmationUrl"),
                    "start_time": slot.get("start"),
                }
            else:
                return {
                    "success": False,
                    "error": response.text,
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}


# Convenience functions
def get_booking_link(lead: Dict[str, Any] = None) -> str:
    """Get a booking link for a lead."""
    calendar = CalendarBooking()
    return calendar.get_booking_url(lead)


def get_available_times(days: int = 7) -> List[Dict[str, Any]]:
    """Get available booking times."""
    calendar = CalendarBooking()
    return calendar.get_available_slots(days)
