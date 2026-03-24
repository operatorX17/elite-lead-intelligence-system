"""
GOLDMINE INTEGRATIONS - The nervous system of the autonomous sales machine.

This module contains all external service integrations:
- Email (Gmail API)
- Payments (Stripe)
- Voice/SMS/WhatsApp (Twilio)
- Video (Loom)
- PDF Generation
- Calendar (Cal.com)
"""

from src.goldmine.integrations.gmail import GmailSender
from src.goldmine.integrations.stripe_payments import StripePayments
from src.goldmine.integrations.twilio_comms import TwilioComms
from src.goldmine.integrations.pdf_generator import ProofDeckPDF

__all__ = [
    "GmailSender",
    "StripePayments", 
    "TwilioComms",
    "ProofDeckPDF",
]
