"""
LOOM VIDEO INTEGRATION - Personalized video messages.

Send personalized Loom-style video messages to leads.
Options:
1. Loom API (if you have Loom Business)
2. HeyGen API (AI avatar videos)
3. Synthesia API (AI avatar videos)
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class LoomVideo:
    """
    Loom video integration for personalized outreach.
    
    Setup for Loom:
    1. Get Loom Business account
    2. Generate API key from Settings > Developer
    3. Add to .env: LOOM_API_KEY=xxx
    
    Alternative - HeyGen:
    1. Create HeyGen account
    2. Get API key
    3. Add to .env: HEYGEN_API_KEY=xxx
    """
    
    def __init__(self):
        """Initialize video service."""
        self.loom_api_key = os.getenv("LOOM_API_KEY")
        self.heygen_api_key = os.getenv("HEYGEN_API_KEY")
        self.synthesia_api_key = os.getenv("SYNTHESIA_API_KEY")
        
        self.service = None
        if self.loom_api_key:
            self.service = "loom"
            logger.info("✅ Loom API configured")
        elif self.heygen_api_key:
            self.service = "heygen"
            logger.info("✅ HeyGen API configured")
        elif self.synthesia_api_key:
            self.service = "synthesia"
            logger.info("✅ Synthesia API configured")
        else:
            logger.warning("No video API configured. Set LOOM_API_KEY, HEYGEN_API_KEY, or SYNTHESIA_API_KEY")
            
    def is_configured(self) -> bool:
        """Check if any video service is configured."""
        return self.service is not None
        
    def create_personalized_video(
        self,
        lead: Dict[str, Any],
        monthly_loss: float,
        script: str = None,
        booking_url: str = None,
    ) -> Dict[str, Any]:
        """
        Create a personalized video for a lead.
        
        Args:
            lead: Lead data
            monthly_loss: Calculated monthly loss
            script: Custom script (or auto-generate)
            booking_url: Calendar booking URL
            
        Returns:
            {"success": bool, "video_url": str, "error": str}
        """
        business_name = lead.get("business_name", "your business")
        
        # Generate script if not provided
        if not script:
            script = self._generate_script(lead, monthly_loss, booking_url)
            
        if self.service == "loom":
            return self._create_loom_video(script, lead)
        elif self.service == "heygen":
            return self._create_heygen_video(script, lead)
        elif self.service == "synthesia":
            return self._create_synthesia_video(script, lead)
        else:
            # Return script for manual recording
            return {
                "success": False,
                "error": "No video service configured",
                "script": script,
                "suggestion": "Record this script manually and upload to Loom",
            }
            
    def _generate_script(
        self,
        lead: Dict[str, Any],
        monthly_loss: float,
        booking_url: str = None,
    ) -> str:
        """Generate a personalized video script."""
        business_name = lead.get("business_name", "your business")
        category = lead.get("category", "business")
        
        script = f"""
Hey there!

I was doing some research on {category} businesses in your area, and I came across {business_name}.

I noticed a few things that might be costing you money - and I wanted to share what I found.

Based on my analysis, you could be missing out on around ${monthly_loss:,.0f} per month in potential customers.

Now, I know that sounds like a lot, but here's the thing - most of these are pretty easy fixes.

I put together a quick breakdown showing exactly where the opportunities are.

Would you be open to a 15-minute call to walk through it? I think you'll find it valuable.

{f"You can book a time at {booking_url}" if booking_url else "Just reply to this and let me know what works for your schedule."}

Looking forward to connecting!
"""
        return script.strip()
        
    def _create_loom_video(self, script: str, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Create video using Loom API."""
        import requests
        
        # Note: Loom API is limited - mainly for embedding/sharing existing videos
        # For automated video creation, HeyGen or Synthesia are better options
        
        try:
            # Loom doesn't have a video creation API yet
            # This would be for managing existing videos
            headers = {
                "Authorization": f"Bearer {self.loom_api_key}",
                "Content-Type": "application/json",
            }
            
            # Return script for manual recording
            return {
                "success": False,
                "error": "Loom API doesn't support automated video creation yet",
                "script": script,
                "suggestion": "Record this script in Loom and share the link",
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def _create_heygen_video(self, script: str, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Create AI avatar video using HeyGen API."""
        import requests
        
        try:
            headers = {
                "X-Api-Key": self.heygen_api_key,
                "Content-Type": "application/json",
            }
            
            # Create video
            payload = {
                "video_inputs": [{
                    "character": {
                        "type": "avatar",
                        "avatar_id": "josh_lite3_20230714",  # Default avatar
                        "avatar_style": "normal",
                    },
                    "voice": {
                        "type": "text",
                        "input_text": script,
                        "voice_id": "1bd001e7e50f421d891986aad5158bc8",  # Default voice
                    },
                }],
                "dimension": {
                    "width": 1280,
                    "height": 720,
                },
                "test": False,  # Set to True for testing (watermarked)
            }
            
            response = requests.post(
                "https://api.heygen.com/v2/video/generate",
                headers=headers,
                json=payload,
            )
            
            if response.status_code == 200:
                data = response.json()
                video_id = data.get("data", {}).get("video_id")
                
                logger.info(f"🎬 HeyGen video created: {video_id}")
                return {
                    "success": True,
                    "video_id": video_id,
                    "status": "processing",
                    "message": "Video is being generated. Check status with get_video_status()",
                }
            else:
                return {
                    "success": False,
                    "error": response.text,
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def _create_synthesia_video(self, script: str, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Create AI avatar video using Synthesia API."""
        import requests
        
        try:
            headers = {
                "Authorization": self.synthesia_api_key,
                "Content-Type": "application/json",
            }
            
            payload = {
                "test": False,  # Set to True for testing
                "input": [{
                    "script": script,
                    "avatar": "anna_costume1_cameraA",  # Default avatar
                    "background": "white_studio",
                }],
            }
            
            response = requests.post(
                "https://api.synthesia.io/v2/videos",
                headers=headers,
                json=payload,
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                video_id = data.get("id")
                
                logger.info(f"🎬 Synthesia video created: {video_id}")
                return {
                    "success": True,
                    "video_id": video_id,
                    "status": "processing",
                }
            else:
                return {
                    "success": False,
                    "error": response.text,
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def get_video_status(self, video_id: str) -> Dict[str, Any]:
        """Check the status of a video being generated."""
        import requests
        
        if self.service == "heygen":
            headers = {"X-Api-Key": self.heygen_api_key}
            response = requests.get(
                f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
                headers=headers,
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "status": data.get("data", {}).get("status"),
                    "video_url": data.get("data", {}).get("video_url"),
                }
                
        elif self.service == "synthesia":
            headers = {"Authorization": self.synthesia_api_key}
            response = requests.get(
                f"https://api.synthesia.io/v2/videos/{video_id}",
                headers=headers,
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "status": data.get("status"),
                    "video_url": data.get("download"),
                }
                
        return {"success": False, "error": "Could not get video status"}


# Convenience function
def create_outreach_video(
    lead: Dict[str, Any],
    monthly_loss: float,
    booking_url: str = None,
) -> Dict[str, Any]:
    """Create a personalized outreach video."""
    video = LoomVideo()
    return video.create_personalized_video(
        lead=lead,
        monthly_loss=monthly_loss,
        booking_url=booking_url,
    )
