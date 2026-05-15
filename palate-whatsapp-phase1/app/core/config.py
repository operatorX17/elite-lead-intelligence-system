from __future__ import annotations

from typing import List, Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Palate WhatsApp Phase 1"
    environment: str = "development"
    log_level: str = "INFO"
    cors_allow_origins: str = ""

    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    internal_api_key: SecretStr | None = Field(default=None, alias="INTERNAL_API_KEY")
    session_token_pepper: SecretStr | None = Field(default=None, alias="SESSION_TOKEN_PEPPER")
    dashboard_password: SecretStr | None = Field(default=None, alias="DASHBOARD_PASSWORD")

    whatsapp_provider: Literal["meta", "twilio", "mock"] = Field(default="meta", alias="WHATSAPP_PROVIDER")
    demo_mode: bool = Field(default=False, alias="DEMO_MODE")
    public_base_url: str | None = Field(default=None, alias="PUBLIC_BASE_URL")
    palate_whatsapp_number: str | None = Field(default=None, alias="PALATE_WHATSAPP_NUMBER")
    whatsapp_session_ttl_minutes: int = Field(default=1440, alias="WHATSAPP_SESSION_TTL_MINUTES")

    meta_verify_token: SecretStr | None = Field(default=None, alias="META_VERIFY_TOKEN")
    meta_app_secret: SecretStr | None = Field(default=None, alias="META_APP_SECRET")
    meta_access_token: SecretStr | None = Field(default=None, alias="META_ACCESS_TOKEN")
    meta_phone_number_id: str | None = Field(default=None, alias="META_PHONE_NUMBER_ID")
    meta_graph_api_version: str = Field(default="v25.0", alias="META_GRAPH_API_VERSION")
    meta_timeout_seconds: float = Field(default=15.0, alias="META_TIMEOUT_SECONDS")
    meta_send_enabled: bool = Field(default=True, alias="META_SEND_ENABLED")
    meta_mock_mode: bool = Field(default=False, alias="META_MOCK_MODE")
    meta_send_max_attempts: int = Field(default=3, alias="META_SEND_MAX_ATTEMPTS")
    meta_retry_backoff_seconds: float = Field(default=1.0, alias="META_RETRY_BACKOFF_SECONDS")

    twilio_account_sid: SecretStr | None = Field(default=None, alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: SecretStr | None = Field(default=None, alias="TWILIO_AUTH_TOKEN")
    twilio_whatsapp_from: str | None = Field(default=None, alias="TWILIO_WHATSAPP_FROM")
    twilio_webhook_auth_enabled: bool = Field(default=True, alias="TWILIO_WEBHOOK_AUTH_ENABLED")

    razorpay_webhook_secret: SecretStr | None = Field(default=None, alias="RAZORPAY_WEBHOOK_SECRET")

    @property
    def cors_origins(self) -> List[str]:
        if not self.cors_allow_origins.strip():
            return []
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def session_link_whatsapp_number(self) -> str | None:
        if self.whatsapp_provider == "twilio":
            return self.twilio_whatsapp_from
        return self.palate_whatsapp_number

    def missing_required_settings(self) -> list[str]:
        missing: list[str] = []
        required: dict[str, object | None] = {
            "DATABASE_URL": self.database_url,
            "INTERNAL_API_KEY": self.internal_api_key,
            "SESSION_TOKEN_PEPPER": self.session_token_pepper,
            "RAZORPAY_WEBHOOK_SECRET": self.razorpay_webhook_secret,
        }
        if self.whatsapp_provider in {"meta", "mock"}:
            required["PALATE_WHATSAPP_NUMBER"] = self.palate_whatsapp_number
        if self.whatsapp_provider == "meta":
            required["META_VERIFY_TOKEN"] = self.meta_verify_token
            required["META_APP_SECRET"] = self.meta_app_secret
            required["META_ACCESS_TOKEN"] = self.meta_access_token
            required["META_PHONE_NUMBER_ID"] = self.meta_phone_number_id
        if self.whatsapp_provider == "twilio":
            required["TWILIO_ACCOUNT_SID"] = self.twilio_account_sid
            required["TWILIO_AUTH_TOKEN"] = self.twilio_auth_token
            required["TWILIO_WHATSAPP_FROM"] = self.twilio_whatsapp_from
            required["PUBLIC_BASE_URL"] = self.public_base_url
        if self.demo_mode:
            required["PUBLIC_BASE_URL"] = self.public_base_url

        for key, value in required.items():
            if value is None:
                missing.append(key)
                continue
            if isinstance(value, SecretStr) and not value.get_secret_value().strip():
                missing.append(key)
                continue
            if isinstance(value, str) and not value.strip():
                missing.append(key)
        return missing
