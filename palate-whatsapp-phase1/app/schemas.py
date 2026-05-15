from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(ApiModel):
    status: str
    service: str
    timestamp: datetime


class ReadyResponse(ApiModel):
    status: str
    ready: bool
    checks: dict[str, Any]


class SessionLinkRequest(ApiModel):
    order_id: UUID | None = None
    external_order_id: str | None = Field(default=None, max_length=128)
    customer_id: UUID | None = None
    external_customer_id: str | None = Field(default=None, max_length=128)
    restaurant_id: str | None = Field(default=None, max_length=128)
    restaurant_name: str | None = Field(default=None, max_length=255)
    browser_session_id: str | None = Field(default=None, max_length=255)
    cart_id: str | None = Field(default=None, max_length=128)
    customer_name: str | None = Field(default=None, max_length=255)
    provided_phone: str | None = Field(default=None, max_length=32)
    entry_point: str = Field(default="unknown", max_length=32)
    intent: str = Field(default="verify_phone", max_length=32)
    resume_url: str | None = None
    expires_in_minutes: int | None = Field(default=None, ge=5, le=10080)


class SessionLinkResponse(ApiModel):
    session_id: UUID
    wa_url: str
    token_hint: str
    expires_at: datetime


class SessionStatusResponse(ApiModel):
    session_id: UUID
    order_id: UUID | None = None
    customer_id: UUID | None = None
    session_status: str
    is_verified: bool
    can_proceed: bool
    next_action: str
    recommended_cta_label: str
    entry_point: str
    intent: str
    provided_name: str | None = None
    verified_phone: str | None = None
    resume_url: str | None = None
    expires_at: datetime
    verified_at: datetime | None = None


class SendMessageRequest(ApiModel):
    to_phone: str | None = None
    customer_id: UUID | None = None
    order_id: UUID | None = None
    session_id: UUID | None = None
    body: str = Field(min_length=1, max_length=4096)
    preview_url: bool = False


class SendTemplateRequest(ApiModel):
    to_phone: str | None = None
    customer_id: UUID | None = None
    order_id: UUID | None = None
    session_id: UUID | None = None
    template_helper: str | None = None
    template_name: str = Field(min_length=1, max_length=255)
    language_code: str = Field(default="en_US", min_length=2, max_length=32)
    components: list[dict[str, Any]] = Field(default_factory=list)


class OrderMessageRequest(ApiModel):
    preview_url: bool = False
    template_helper: str | None = None
    template_name: str | None = None
    language_code: str = Field(default="en_US", min_length=2, max_length=32)
    components: list[dict[str, Any]] = Field(default_factory=list)


class CaptainOrderCreateRequest(ApiModel):
    external_order_id: str | None = Field(default=None, max_length=128)
    external_customer_id: str | None = Field(default=None, max_length=128)
    customer_name: str | None = Field(default=None, max_length=255)
    customer_phone: str | None = Field(default=None, max_length=32)
    customer_email: str | None = Field(default=None, max_length=255)
    restaurant_id: str = Field(min_length=1, max_length=128)
    restaurant_name: str = Field(min_length=1, max_length=255)
    order_status: str = Field(default="created", max_length=32)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    subtotal_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    total_amount: Decimal | None = None
    amount_paid: Decimal | None = None
    summary_text: str | None = None
    menu_url: str | None = None
    order_url: str | None = None
    bill_url: str | None = None
    payment_url: str | None = None
    feedback_url: str | None = None
    notes: dict[str, Any] = Field(default_factory=dict)
    line_items: list[dict[str, Any]] = Field(default_factory=list)
    dish_reviews: list[dict[str, Any]] = Field(default_factory=list)
    auto_create_session_link: bool = False


class MessageResponse(ApiModel):
    status: str
    message_log_id: UUID
    provider: str | None = None
    provider_message_id: str | None = None
    meta_message_id: str | None = None


class CaptainOrderResponse(ApiModel):
    order_id: UUID
    customer_id: UUID | None = None
    session_link: SessionLinkResponse | None = None


class IntegrationIntakeSubmissionRequest(ApiModel):
    respondent_name: str | None = Field(default=None, max_length=255)
    respondent_role: str | None = Field(default=None, max_length=255)
    respondent_email: str | None = Field(default=None, max_length=255)
    respondent_phone: str | None = Field(default=None, max_length=32)
    provider_primary: str | None = Field(default=None, max_length=32)
    provider_backup: str | None = Field(default=None, max_length=32)
    real_urls: dict[str, str] = Field(default_factory=dict)
    order_sources: list[str] = Field(default_factory=list)
    verification_points: list[str] = Field(default_factory=list)
    customer_inputs: list[str] = Field(default_factory=list)
    canonical_order_reference: str | None = None
    payment_provider: str | None = Field(default=None, max_length=64)
    payment_mapping_notes: str | None = None
    required_messages: list[str] = Field(default_factory=list)
    messaging_rules_notes: str | None = None
    production_domain: str | None = None
    ownership: dict[str, str] = Field(default_factory=dict)
    final_flow_notes: str | None = None
    general_notes: str | None = None


class IntegrationIntakeSubmissionResponse(ApiModel):
    submission_id: UUID
    status: str
    project_key: str
    created_at: datetime


class IntegrationIntakeSubmissionItem(ApiModel):
    submission_id: UUID
    status: str
    project_key: str
    respondent_name: str | None = None
    respondent_role: str | None = None
    respondent_email: str | None = None
    respondent_phone: str | None = None
    provider_primary: str | None = None
    provider_backup: str | None = None
    real_urls: dict[str, Any]
    order_sources: list[str]
    verification_points: list[str]
    customer_inputs: list[str]
    canonical_order_reference: str | None = None
    payment_provider: str | None = None
    payment_mapping_notes: str | None = None
    required_messages: list[str]
    messaging_rules_notes: str | None = None
    production_domain: str | None = None
    ownership: dict[str, Any]
    final_flow_notes: str | None = None
    general_notes: str | None = None
    created_at: datetime
