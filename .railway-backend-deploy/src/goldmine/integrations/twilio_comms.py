"""
TWILIO COMMUNICATIONS - Voice, SMS, and WhatsApp.

The multi-channel outreach engine:
- SMS for quick follow-ups
- Voice for AI phone calls
- WhatsApp for direct messaging
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class TwilioComms:
    """
    Twilio integration for multi-channel communication.
    
    Setup:
    1. Create Twilio account at twilio.com
    2. Get Account SID and Auth Token from Console
    3. Buy a phone number
    4. For WhatsApp: Set up WhatsApp Business API
    5. Add to .env:
       TWILIO_ACCOUNT_SID=ACxxx
       TWILIO_AUTH_TOKEN=xxx
       TWILIO_PHONE_NUMBER=+1xxx
       TWILIO_WHATSAPP_NUMBER=+1xxx (optional)
    """
    
    def __init__(self):
        """Initialize Twilio client."""
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.phone_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER")
        self.client = None
        
        if self.account_sid and self.auth_token:
            try:
                from twilio.rest import Client
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("✅ Twilio initialized")
            except ImportError:
                logger.warning("Twilio not installed. Run: pip install twilio")
                
    def is_configured(self) -> bool:
        """Check if Twilio is properly configured."""
        return self.client is not None
        
    # =========================================================================
    # SMS
    # =========================================================================
    
    def send_sms(
        self,
        to: str,
        message: str,
        media_url: str = None,
    ) -> Dict[str, Any]:
        """
        Send an SMS message.
        
        Args:
            to: Phone number (E.164 format: +1234567890)
            message: Text message (max 1600 chars)
            media_url: Optional MMS media URL
            
        Returns:
            {"success": bool, "sid": str, "error": str}
        """
        if not self.is_configured():
            return {"success": False, "error": "Twilio not configured"}
            
        if not self.phone_number:
            return {"success": False, "error": "No Twilio phone number configured"}
            
        try:
            params = {
                "body": message,
                "from_": self.phone_number,
                "to": to,
            }
            
            if media_url:
                params["media_url"] = [media_url]
                
            msg = self.client.messages.create(**params)
            
            logger.info(f"📱 SMS sent to {to}: {message[:50]}...")
            return {
                "success": True,
                "sid": msg.sid,
                "status": msg.status,
            }
            
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return {"success": False, "error": str(e)}
            
    def send_outreach_sms(
        self,
        lead: Dict[str, Any],
        message_template: str = None,
        booking_url: str = None,
    ) -> Dict[str, Any]:
        """
        Send an outreach SMS to a lead.
        
        Args:
            lead: Lead data with phone number
            message_template: Custom message (supports {business_name} tokens)
            booking_url: Calendar booking URL
            
        Returns:
            Send result
        """
        phone = lead.get("phone")
        if not phone:
            return {"success": False, "error": "No phone number for lead"}
            
        business_name = lead.get("business_name", "your business")
        
        if message_template:
            message = message_template.format(
                business_name=business_name,
                booking_url=booking_url or "",
            )
        else:
            message = f"Hi! I found some opportunities for {business_name} that could help you get more customers. Mind if I share? {booking_url or ''}"
            
        return self.send_sms(to=phone, message=message)
        
    # =========================================================================
    # WHATSAPP
    # =========================================================================
    
    def send_whatsapp(
        self,
        to: str,
        message: str,
        media_url: str = None,
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp message.
        
        Args:
            to: Phone number (E.164 format)
            message: Text message
            media_url: Optional media URL
            
        Returns:
            {"success": bool, "sid": str, "error": str}
        """
        if not self.is_configured():
            return {"success": False, "error": "Twilio not configured"}
            
        whatsapp_from = self.whatsapp_number or self.phone_number
        if not whatsapp_from:
            return {"success": False, "error": "No WhatsApp number configured"}
            
        try:
            params = {
                "body": message,
                "from_": f"whatsapp:{whatsapp_from}",
                "to": f"whatsapp:{to}",
            }
            
            if media_url:
                params["media_url"] = [media_url]
                
            msg = self.client.messages.create(**params)
            
            logger.info(f"💬 WhatsApp sent to {to}: {message[:50]}...")
            return {
                "success": True,
                "sid": msg.sid,
                "status": msg.status,
            }
            
        except Exception as e:
            logger.error(f"Failed to send WhatsApp: {e}")
            return {"success": False, "error": str(e)}
            
    # =========================================================================
    # VOICE CALLS
    # =========================================================================
    
    def make_call(
        self,
        to: str,
        twiml_url: str = None,
        twiml: str = None,
        record: bool = True,
    ) -> Dict[str, Any]:
        """
        Make an outbound voice call.
        
        Args:
            to: Phone number to call
            twiml_url: URL returning TwiML instructions
            twiml: Raw TwiML string (alternative to URL)
            record: Whether to record the call
            
        Returns:
            {"success": bool, "sid": str, "error": str}
        """
        if not self.is_configured():
            return {"success": False, "error": "Twilio not configured"}
            
        if not self.phone_number:
            return {"success": False, "error": "No Twilio phone number configured"}
            
        try:
            params = {
                "from_": self.phone_number,
                "to": to,
                "record": record,
            }
            
            if twiml_url:
                params["url"] = twiml_url
            elif twiml:
                params["twiml"] = twiml
            else:
                # Default: Simple message
                params["twiml"] = """
                <Response>
                    <Say voice="alice">
                        Hi, this is a quick call about your business. 
                        I found some opportunities that could help you get more customers.
                        Press 1 to learn more, or I'll send you an email with the details.
                    </Say>
                    <Gather numDigits="1" timeout="5">
                        <Say>Press 1 to speak with someone now.</Say>
                    </Gather>
                    <Say>Thanks! I'll send you an email with more information.</Say>
                </Response>
                """
                
            call = self.client.calls.create(**params)
            
            logger.info(f"📞 Call initiated to {to}")
            return {
                "success": True,
                "sid": call.sid,
                "status": call.status,
            }
            
        except Exception as e:
            logger.error(f"Failed to make call: {e}")
            return {"success": False, "error": str(e)}
            
    def make_ai_call(
        self,
        to: str,
        lead: Dict[str, Any],
        monthly_loss: float,
        booking_url: str = None,
    ) -> Dict[str, Any]:
        """
        Make an AI-powered outreach call.
        
        Uses TwiML to deliver a personalized pitch based on the lead's data.
        
        Args:
            to: Phone number
            lead: Lead data
            monthly_loss: Calculated monthly loss
            booking_url: Calendar booking URL
            
        Returns:
            Call result
        """
        business_name = lead.get("business_name", "your business")
        
        # Create personalized TwiML
        twiml = f"""
        <Response>
            <Say voice="Polly.Matthew">
                Hi, this is a quick call about {business_name}.
            </Say>
            <Pause length="1"/>
            <Say voice="Polly.Matthew">
                I was doing some research and noticed you might be missing out on 
                about {int(monthly_loss)} dollars a month in potential customers.
            </Say>
            <Pause length="1"/>
            <Say voice="Polly.Matthew">
                I put together a quick analysis showing exactly where the opportunities are.
                Would you have 15 minutes this week to go over it?
            </Say>
            <Gather numDigits="1" timeout="10" action="/handle-response">
                <Say voice="Polly.Matthew">
                    Press 1 if you'd like to schedule a call, 
                    or press 2 if you'd prefer I send the analysis by email.
                </Say>
            </Gather>
            <Say voice="Polly.Matthew">
                No problem! I'll send you an email with all the details. 
                Have a great day!
            </Say>
        </Response>
        """
        
        return self.make_call(to=to, twiml=twiml)
        
    # =========================================================================
    # MULTI-CHANNEL SEQUENCE
    # =========================================================================
    
    def execute_outreach_sequence(
        self,
        lead: Dict[str, Any],
        channels: List[str] = None,
        booking_url: str = None,
    ) -> Dict[str, Any]:
        """
        Execute a multi-channel outreach sequence.
        
        Args:
            lead: Lead data
            channels: List of channels to use ["sms", "whatsapp", "call"]
            booking_url: Calendar booking URL
            
        Returns:
            Results for each channel
        """
        if channels is None:
            channels = ["sms"]  # Default to SMS only
            
        results = {}
        phone = lead.get("phone")
        
        if not phone:
            return {"success": False, "error": "No phone number for lead"}
            
        business_name = lead.get("business_name", "your business")
        
        for channel in channels:
            if channel == "sms":
                results["sms"] = self.send_outreach_sms(
                    lead=lead,
                    booking_url=booking_url,
                )
            elif channel == "whatsapp":
                message = f"Hi! 👋 I found some growth opportunities for {business_name}. Would you like me to share? {booking_url or ''}"
                results["whatsapp"] = self.send_whatsapp(
                    to=phone,
                    message=message,
                )
            elif channel == "call":
                monthly_loss = lead.get("estimated_monthly_loss", 5000)
                results["call"] = self.make_ai_call(
                    to=phone,
                    lead=lead,
                    monthly_loss=monthly_loss,
                    booking_url=booking_url,
                )
                
        return {
            "success": all(r.get("success") for r in results.values()),
            "results": results,
        }


# Convenience functions
def send_quick_sms(phone: str, message: str) -> Dict[str, Any]:
    """Send a quick SMS."""
    comms = TwilioComms()
    return comms.send_sms(to=phone, message=message)


def send_quick_whatsapp(phone: str, message: str) -> Dict[str, Any]:
    """Send a quick WhatsApp message."""
    comms = TwilioComms()
    return comms.send_whatsapp(to=phone, message=message)
