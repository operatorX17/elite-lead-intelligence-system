from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.security import normalize_phone


class TwilioWhatsAppClient:
    provider_name = "twilio_whatsapp"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_text_message(self, to_phone: str, body: str, preview_url: bool = False) -> dict[str, Any]:
        if self.settings.whatsapp_provider != "twilio":
            raise AppError(409, "twilio_provider_inactive", "Twilio WhatsApp sending is not active for this deployment")
        if self.settings.twilio_account_sid is None or self.settings.twilio_auth_token is None or not self.settings.twilio_whatsapp_from:
            raise AppError(503, "twilio_not_configured", "Twilio WhatsApp credentials are incomplete")

        from_phone = normalize_phone(self.settings.twilio_whatsapp_from)
        to_phone_normalized = normalize_phone(to_phone)
        if from_phone is None or to_phone_normalized is None:
            raise AppError(422, "twilio_phone_invalid", "Twilio send requires valid WhatsApp phone numbers")

        endpoint = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{self.settings.twilio_account_sid.get_secret_value()}/Messages.json"
        )
        payload = {
            "From": f"whatsapp:{from_phone}",
            "To": f"whatsapp:{to_phone_normalized}",
            "Body": body,
        }
        auth = (
            self.settings.twilio_account_sid.get_secret_value(),
            self.settings.twilio_auth_token.get_secret_value(),
        )

        async with httpx.AsyncClient(timeout=self.settings.meta_timeout_seconds, auth=auth) as client:
            response = await client.post(endpoint, data=payload)

        if response.is_error:
            detail = "Twilio send failed"
            try:
                data = response.json()
                detail = data.get("message") or detail
            except Exception:
                detail = response.text[:200] or detail
            raise AppError(response.status_code, "twilio_send_failed", detail)

        return response.json()

    async def send_template_message(
        self,
        to_phone: str,
        template_name: str,
        language_code: str,
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        raise AppError(
            409,
            "template_not_supported_for_provider",
            "send-template is only supported when WHATSAPP_PROVIDER=meta or mock",
        )
