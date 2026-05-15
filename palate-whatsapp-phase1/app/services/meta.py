from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx

from app.core.config import Settings
from app.core.exceptions import AppError


class MetaWhatsAppClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_text_message(self, to_phone: str, body: str, preview_url: bool = False) -> dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": body,
            },
        }
        return await self._send(payload)

    async def send_template_message(
        self,
        to_phone: str,
        template_name: str,
        language_code: str,
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components or [],
            },
        }
        return await self._send(payload)

    async def _send(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.meta_send_enabled:
            raise AppError(503, "meta_send_disabled", "Meta sending is disabled")
        if self.settings.meta_mock_mode:
            return {
                "messaging_product": "whatsapp",
                "contacts": [{"input": payload.get("to")}],
                "messages": [{"id": f"wamid.mock-{uuid.uuid4()}"}],
            }

        if (
            self.settings.meta_access_token is None
            or self.settings.meta_phone_number_id is None
            or not self.settings.meta_phone_number_id.strip()
        ):
            raise AppError(503, "meta_not_configured", "Meta WhatsApp credentials are incomplete")

        endpoint = (
            f"https://graph.facebook.com/{self.settings.meta_graph_api_version}/"
            f"{self.settings.meta_phone_number_id}/messages"
        )
        headers = {
            "Authorization": f"Bearer {self.settings.meta_access_token.get_secret_value()}",
            "Content-Type": "application/json",
        }

        last_exception: Exception | None = None
        attempts = max(1, self.settings.meta_send_max_attempts)
        retryable_status_codes = {429, 500, 502, 503, 504}

        async with httpx.AsyncClient(timeout=self.settings.meta_timeout_seconds) as client:
            for attempt in range(1, attempts + 1):
                try:
                    response = await client.post(endpoint, headers=headers, json=payload)
                except httpx.TransportError as exc:
                    last_exception = exc
                    if attempt >= attempts:
                        raise AppError(503, "meta_send_failed", f"Meta send failed after {attempts} attempts") from exc
                    await asyncio.sleep(self.settings.meta_retry_backoff_seconds * attempt)
                    continue

                if not response.is_error:
                    return response.json()

                if response.status_code in retryable_status_codes and attempt < attempts:
                    await asyncio.sleep(self.settings.meta_retry_backoff_seconds * attempt)
                    continue

                detail = "Meta send failed"
                try:
                    data = response.json()
                    error = data.get("error") or {}
                    detail = error.get("message") or detail
                except Exception:
                    detail = response.text[:200] or detail
                raise AppError(response.status_code, "meta_send_failed", detail)

        raise AppError(503, "meta_send_failed", "Meta send failed") from last_exception
