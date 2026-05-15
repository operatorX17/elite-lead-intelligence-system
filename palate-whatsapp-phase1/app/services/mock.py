from __future__ import annotations

import uuid
from typing import Any


class MockWhatsAppClient:
    provider_name = "mock_whatsapp"

    async def send_text_message(self, to_phone: str, body: str, preview_url: bool = False) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "to": to_phone,
            "body": body,
            "preview_url": preview_url,
            "messages": [{"id": f"mock-{uuid.uuid4()}"}],
        }

    async def send_template_message(
        self,
        to_phone: str,
        template_name: str,
        language_code: str,
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "to": to_phone,
            "template_name": template_name,
            "language_code": language_code,
            "components": components or [],
            "messages": [{"id": f"mock-{uuid.uuid4()}"}],
        }
