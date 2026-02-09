"""
GMAIL INTEGRATION - Send emails using Google OAuth.

Uses the user's existing OAuth credentials to send personalized outreach emails.
"""

import os
import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class GmailSender:
    """
    Send emails via Gmail API using OAuth credentials.
    
    Setup:
    1. Enable Gmail API in Google Cloud Console
    2. Download OAuth credentials JSON
    3. Set GMAIL_CREDENTIALS_FILE in .env
    4. First run will open browser for authorization
    """
    
    def __init__(self, credentials_file: str = None):
        """
        Initialize Gmail sender.
        
        Args:
            credentials_file: Path to OAuth credentials JSON file
        """
        self.credentials_file = credentials_file or os.getenv(
            "GMAIL_CREDENTIALS_FILE",
            "client_secret_995991197845-vur7dbpfo07utmfc5rmr8v2cr17pt67c.apps.googleusercontent.com.json"
        )
        self.token_file = "gmail_token.json"
        self.service = None
        self._initialized = False
        
    def _get_service(self):
        """Get or create Gmail API service."""
        if self.service:
            return self.service
            
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError:
            logger.error("Gmail dependencies not installed. Run: pip install google-auth-oauthlib google-api-python-client")
            return None
            
        SCOPES = ['https://www.googleapis.com/auth/gmail.send']
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            
        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    logger.error(f"Credentials file not found: {self.credentials_file}")
                    return None
                    
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)
                
            # Save token for next time
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
                
        self.service = build('gmail', 'v1', credentials=creds)
        self._initialized = True
        return self.service
        
    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: str = None,
        attachments: List[Dict[str, Any]] = None,
        cc: List[str] = None,
        bcc: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email via Gmail.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            attachments: List of {"filename": str, "data": bytes, "mime_type": str}
            cc: CC recipients
            bcc: BCC recipients
            
        Returns:
            {"success": bool, "message_id": str, "error": str}
        """
        service = self._get_service()
        if not service:
            return {"success": False, "error": "Gmail service not initialized"}
            
        try:
            # Create message
            if html_body or attachments:
                message = MIMEMultipart('alternative')
                message.attach(MIMEText(body, 'plain'))
                if html_body:
                    message.attach(MIMEText(html_body, 'html'))
            else:
                message = MIMEText(body)
                
            message['to'] = to
            message['subject'] = subject
            
            if cc:
                message['cc'] = ', '.join(cc)
            if bcc:
                message['bcc'] = ', '.join(bcc)
                
            # Add attachments
            if attachments:
                for attachment in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment['data'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="{attachment["filename"]}"'
                    )
                    message.attach(part)
                    
            # Encode and send
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            result = service.users().messages().send(
                userId='me',
                body={'raw': raw}
            ).execute()
            
            logger.info(f"✉️ Email sent to {to}: {subject}")
            return {
                "success": True,
                "message_id": result.get('id'),
                "thread_id": result.get('threadId'),
            }
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {"success": False, "error": str(e)}
            
    def send_outreach_email(
        self,
        lead: Dict[str, Any],
        subject: str,
        body: str,
        proof_pdf: bytes = None,
        booking_url: str = None,
    ) -> Dict[str, Any]:
        """
        Send a personalized outreach email to a lead.
        
        Args:
            lead: Lead data with email, business_name, etc.
            subject: Email subject (can include {business_name} tokens)
            body: Email body (can include tokens)
            proof_pdf: Optional PDF proof deck to attach
            booking_url: Calendar booking URL to include
            
        Returns:
            Send result
        """
        # Get email from lead
        email = lead.get("email")
        if not email:
            # Try to extract from enrichment
            email = lead.get("enrichment", {}).get("email")
            
        if not email:
            return {"success": False, "error": "No email address for lead"}
            
        # Personalize content
        business_name = lead.get("business_name", "your business")
        owner_name = lead.get("owner_name", "")
        
        personalized_subject = subject.format(
            business_name=business_name,
            owner_name=owner_name,
        )
        
        personalized_body = body.format(
            business_name=business_name,
            owner_name=owner_name,
            booking_url=booking_url or "[BOOKING_URL]",
        )
        
        # Add booking link if provided
        if booking_url and booking_url not in personalized_body:
            personalized_body += f"\n\nBook a call: {booking_url}"
            
        # Prepare attachments
        attachments = []
        if proof_pdf:
            attachments.append({
                "filename": f"{business_name.replace(' ', '_')}_Analysis.pdf",
                "data": proof_pdf,
                "mime_type": "application/pdf",
            })
            
        return self.send_email(
            to=email,
            subject=personalized_subject,
            body=personalized_body,
            attachments=attachments if attachments else None,
        )


# Convenience function
def send_goldmine_email(
    lead: Dict[str, Any],
    monthly_loss: float,
    proof_pdf: bytes = None,
    booking_url: str = None,
) -> Dict[str, Any]:
    """
    Send a Goldmine outreach email with proof of money leak.
    
    Args:
        lead: Lead data
        monthly_loss: Calculated monthly revenue loss
        proof_pdf: PDF proof deck
        booking_url: Calendar booking URL
        
    Returns:
        Send result
    """
    sender = GmailSender()
    
    business_name = lead.get("business_name", "your business")
    
    subject = f"Quick question about {business_name}"
    
    body = f"""Hi,

I was researching {business_name} and noticed something that might be costing you money.

Based on my analysis, you could be losing around ${monthly_loss:,.0f}/month in missed opportunities.

I put together a quick breakdown showing exactly where the leaks are. Would you be open to a 15-minute call to walk through it?

{f"Book a time here: {booking_url}" if booking_url else "Let me know what works for your schedule."}

Best,
[Your Name]

P.S. I've attached a detailed analysis if you want to see the numbers first.
"""
    
    return sender.send_outreach_email(
        lead=lead,
        subject=subject,
        body=body,
        proof_pdf=proof_pdf,
        booking_url=booking_url,
    )
