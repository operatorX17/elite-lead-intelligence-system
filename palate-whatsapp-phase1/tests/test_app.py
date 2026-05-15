from __future__ import annotations

import asyncio
import hmac
import json
import uuid
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.base import Base
from app.db.models import Order
from app.db.models import WhatsAppSession
from app.db.session import get_engine, get_session_factory
from app.services.meta import MetaWhatsAppClient
from app.main import create_app
from app.schemas import CaptainOrderCreateRequest
from app.core.config import Settings
from app.services.orders import compose_demo_verification_message
from app.services.session_tokens import build_prefilled_message


def build_settings(tmp_path: Path) -> Settings:
    return Settings.model_validate(
        {
            "DATABASE_URL": f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
            "INTERNAL_API_KEY": "internal-test-key",
            "DASHBOARD_PASSWORD": "dashboard-pass",
            "SESSION_TOKEN_PEPPER": "pepper-test",
            "PALATE_WHATSAPP_NUMBER": "+919999999999",
            "META_VERIFY_TOKEN": "verify-me",
            "META_APP_SECRET": "meta-secret",
            "META_ACCESS_TOKEN": "meta-token",
            "META_PHONE_NUMBER_ID": "123456",
            "META_SEND_ENABLED": True,
            "RAZORPAY_WEBHOOK_SECRET": "rzp-secret",
        }
    )


def create_test_client(tmp_path: Path) -> tuple[TestClient, Settings]:
    settings = build_settings(tmp_path)
    engine = get_engine(settings)
    Base.metadata.create_all(bind=engine)
    return TestClient(create_app(settings)), settings


def create_test_client_with_settings(settings: Settings) -> TestClient:
    engine = get_engine(settings)
    Base.metadata.create_all(bind=engine)
    return TestClient(create_app(settings))


def test_meta_webhook_verification(tmp_path: Path) -> None:
    client, _ = create_test_client(tmp_path)
    response = client.get(
        "/webhooks/meta/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "12345",
            "hub.verify_token": "verify-me",
        },
    )
    assert response.status_code == 200
    assert response.text == "12345"


def test_prefilled_message_uses_short_restaurant_name() -> None:
    message = build_prefilled_message(
        "PALATE_ABC12345",
        "Dalchini, 5730, State Hwy 64, Bhekrai Nagar, Pune, Maharashtra 412308, India",
        "menu",
    )

    assert message == "Start my Palate session and show me Dalchini's menu\nToken: PALATE_ABC12345"
    assert "5730" not in message
    assert "Reference:" not in message


def test_session_link_and_verification_flow(tmp_path: Path, monkeypatch) -> None:
    client, settings = create_test_client(tmp_path)

    async def fake_send_text_message(self, to_phone: str, body: str, preview_url: bool = False):
        return {"messages": [{"id": "wamid.test-1"}], "contacts": [{"input": to_phone}]}

    monkeypatch.setattr("app.services.meta.MetaWhatsAppClient.send_text_message", fake_send_text_message)

    create_order_payload = CaptainOrderCreateRequest(
        external_order_id="ORD-1",
        customer_name="Riya",
        restaurant_id="rest-1",
        restaurant_name="Palate Test",
        total_amount="1200.00",
        auto_create_session_link=False,
    )
    order_response = client.post(
        "/api/v1/captain/orders",
        headers={"X-API-Key": "internal-test-key"},
        json=create_order_payload.model_dump(mode="json"),
    )
    assert order_response.status_code == 200
    order_id = order_response.json()["order_id"]

    session_response = client.post(
        "/api/v1/whatsapp/session-link",
        headers={"X-API-Key": "internal-test-key"},
        json={"order_id": order_id},
    )
    assert session_response.status_code == 200

    wa_url = session_response.json()["wa_url"]
    token = parse_qs(urlparse(wa_url).query)["text"][0].split("Token: ", 1)[1]

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.inbound-1",
                                    "from": "919876543210",
                                    "type": "text",
                                    "text": {"body": f"Token: {token}"},
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }
    raw_body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(settings.meta_app_secret.get_secret_value().encode("utf-8"), raw_body, sha256).hexdigest()

    webhook_response = client.post(
        "/webhooks/meta/whatsapp",
        headers={"X-Hub-Signature-256": f"sha256={signature}"},
        content=raw_body,
    )
    assert webhook_response.status_code == 200
    assert webhook_response.json()["status"] == "ok"

    session_factory = get_session_factory(settings)
    with session_factory() as db:
        session = db.execute(text("SELECT session_status, phone_e164 FROM whatsapp_sessions")).first()
        assert session[0] == "verified"
        assert session[1] == "+919876543210"


def test_razorpay_webhook_dedupes_by_event_id(tmp_path: Path) -> None:
    client, settings = create_test_client(tmp_path)
    payload = {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": "pay_1", "amount": 5000, "currency": "INR", "notes": {}}}},
    }
    raw_body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(settings.razorpay_webhook_secret.get_secret_value().encode("utf-8"), raw_body, sha256).hexdigest()
    headers = {
        "X-Razorpay-Signature": signature,
        "x-razorpay-event-id": "evt_1",
    }

    first = client.post("/webhooks/payments/razorpay", headers=headers, content=raw_body)
    second = client.post("/webhooks/payments/razorpay", headers=headers, content=raw_body)

    assert first.status_code == 200
    assert first.json()["status"] == "ok"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"


def test_capture_anywhere_session_without_order_creates_verified_customer(tmp_path: Path, monkeypatch) -> None:
    client, settings = create_test_client(tmp_path)

    send_calls = {"count": 0}

    async def fake_send_text_message(self, to_phone: str, body: str, preview_url: bool = False):
        send_calls["count"] += 1
        return {"messages": [{"id": f"wamid.test-2-{send_calls['count']}"}], "contacts": [{"input": to_phone}]}

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.services.meta.MetaWhatsAppClient.send_text_message", fake_send_text_message)
    monkeypatch.setattr("app.api.routes.webhooks.asyncio.sleep", fake_sleep)

    session_response = client.post(
        "/api/v1/whatsapp/session-link",
        headers={"X-API-Key": "internal-test-key"},
        json={
            "restaurant_id": "rest-2",
            "restaurant_name": "Palate Anywhere",
            "customer_name": "Aarav",
            "entry_point": "menu",
            "intent": "verify_before_payment",
            "resume_url": "https://palate.test/menu/cart",
        },
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["session_id"]

    wa_url = session_response.json()["wa_url"]
    token = parse_qs(urlparse(wa_url).query)["text"][0].split("Token: ", 1)[1]

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.inbound-2",
                                    "from": "918888777766",
                                    "type": "text",
                                    "text": {"body": f"Token: {token}"},
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }
    raw_body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(settings.meta_app_secret.get_secret_value().encode("utf-8"), raw_body, sha256).hexdigest()

    webhook_response = client.post(
        "/webhooks/meta/whatsapp",
        headers={"X-Hub-Signature-256": f"sha256={signature}"},
        content=raw_body,
    )
    assert webhook_response.status_code == 200

    status_response = client.get(
        f"/api/v1/whatsapp/sessions/{session_id}",
        headers={"X-API-Key": "internal-test-key"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["session_status"] == "verified"
    assert status_response.json()["is_verified"] is True
    assert status_response.json()["can_proceed"] is True
    assert status_response.json()["next_action"] == "resume_flow"
    assert status_response.json()["entry_point"] == "menu"
    assert status_response.json()["verified_phone"] == "+918888777766"
    assert status_response.json()["resume_url"].startswith("http://testserver/r/")

    session_factory = get_session_factory(settings)
    with session_factory() as db:
        customer = db.execute(text("SELECT display_name, onboarding_status, phone_verification_channel FROM customers")).first()
        assert customer[0] == "Aarav"
        assert customer[1] == "verified"
        assert customer[2] == "whatsapp"


def test_first_session_sends_welcome_and_one_delayed_followup(tmp_path: Path, monkeypatch) -> None:
    client, settings = create_test_client(tmp_path)

    calls = {"bodies": []}

    async def fake_send_text_message(self, to_phone: str, body: str, preview_url: bool = False):
        calls["bodies"].append(body)
        return {"messages": [{"id": f"wamid.followup-{len(calls['bodies'])}"}], "contacts": [{"input": to_phone}]}

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.services.meta.MetaWhatsAppClient.send_text_message", fake_send_text_message)
    monkeypatch.setattr("app.api.routes.webhooks.asyncio.sleep", fake_sleep)

    session_response = client.post(
        "/api/v1/whatsapp/session-link",
        headers={"X-API-Key": "internal-test-key"},
        json={
            "restaurant_id": "rest-menu",
            "restaurant_name": "Brand A",
            "entry_point": "menu",
            "resume_url": "https://menu.palate.app/brand-a",
        },
    )
    token = parse_qs(urlparse(session_response.json()["wa_url"]).query)["text"][0].split("Token: ", 1)[1]
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {"messages": [{"id": "wamid.inbound-sequence", "from": "919876500000", "type": "text", "text": {"body": token}}]}}]}],
    }
    raw_body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(settings.meta_app_secret.get_secret_value().encode("utf-8"), raw_body, sha256).hexdigest()
    assert client.post("/webhooks/meta/whatsapp", headers={"X-Hub-Signature-256": f"sha256={signature}"}, content=raw_body).status_code == 200
    assert "welcome to Palate" in calls["bodies"][0]
    assert "https://menu.palate.app/brand-a" in calls["bodies"][0]
    assert "you rate the dish, not the restaurant" not in calls["bodies"][0]
    assert "you rate the dish, not the restaurant" in calls["bodies"][1]
    assert len(calls["bodies"]) == 2


def test_session_link_stores_palate_screen_context_metadata(tmp_path: Path) -> None:
    client, settings = create_test_client(tmp_path)

    session_response = client.post(
        "/api/v1/whatsapp/session-link",
        headers={"X-API-Key": "internal-test-key"},
        json={
            "restaurant_id": "rest-docs-1",
            "restaurant_name": "Palate Docs Bistro",
            "browser_session_id": "browser_abc_123",
            "cart_id": "cart_456",
            "external_order_id": "PAL-1001",
            "external_customer_id": "cust_123",
            "customer_name": "Sai",
            "provided_phone": "+919999999999",
            "entry_point": "cart",
            "intent": "verify_before_payment",
            "resume_url": "https://palate.test/cart/cart_456",
        },
    )
    assert session_response.status_code == 200

    session_factory = get_session_factory(settings)
    with session_factory() as db:
        whatsapp_session = db.get(WhatsAppSession, uuid.UUID(session_response.json()["session_id"]))
        assert whatsapp_session is not None
        assert whatsapp_session.restaurant_id == "rest-docs-1"
        assert whatsapp_session.entry_point == "cart"
        assert whatsapp_session.intent == "verify_before_payment"
        assert whatsapp_session.resume_url.startswith("http://testserver/r/")
        assert whatsapp_session.provided_name == "Sai"
        assert whatsapp_session.provided_phone == "+919999999999"
        assert whatsapp_session.metadata_json["browser_session_id"] == "browser_abc_123"
        assert whatsapp_session.metadata_json["cart_id"] == "cart_456"
        assert whatsapp_session.metadata_json["external_order_id"] == "PAL-1001"
        assert whatsapp_session.metadata_json["external_customer_id"] == "cust_123"
        assert whatsapp_session.metadata_json["original_resume_url"] == "https://palate.test/cart/cart_456"


def test_pending_session_polling_returns_pending_status(tmp_path: Path) -> None:
    client, _ = create_test_client(tmp_path)

    session_response = client.post(
        "/api/v1/whatsapp/session-link",
        headers={"X-API-Key": "internal-test-key"},
        json={
            "restaurant_id": "rest-pending",
            "restaurant_name": "Pending Bistro",
            "entry_point": "menu",
            "intent": "verify_before_payment",
            "resume_url": "https://palate.test/menu",
        },
    )
    assert session_response.status_code == 200

    status_response = client.get(
        f"/api/v1/whatsapp/sessions/{session_response.json()['session_id']}",
        headers={"X-API-Key": "internal-test-key"},
    )
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["session_status"] == "pending"
    assert payload["is_verified"] is False
    assert payload["can_proceed"] is False
    assert payload["next_action"] == "complete_whatsapp"


def test_order_summary_template_helper_builds_components(tmp_path: Path, monkeypatch) -> None:
    client, _ = create_test_client(tmp_path)
    captured: dict[str, object] = {}

    async def fake_send_template_message(self, to_phone: str, template_name: str, language_code: str, components):
        captured["to_phone"] = to_phone
        captured["template_name"] = template_name
        captured["components"] = components
        return {"messages": [{"id": "wamid.template-1"}], "contacts": [{"input": to_phone}]}

    monkeypatch.setattr("app.services.meta.MetaWhatsAppClient.send_template_message", fake_send_template_message)

    create_order_payload = CaptainOrderCreateRequest(
        external_order_id="ORD-TPL-1",
        customer_name="Meera",
        customer_phone="+919111111111",
        restaurant_id="rest-tpl-1",
        restaurant_name="Palate Template",
        total_amount="950.00",
        order_url="https://palate.test/orders/ORD-TPL-1",
    )
    order_response = client.post(
        "/api/v1/captain/orders",
        headers={"X-API-Key": "internal-test-key"},
        json=create_order_payload.model_dump(mode="json"),
    )
    assert order_response.status_code == 200
    order_id = order_response.json()["order_id"]

    session_factory = get_session_factory(build_settings(tmp_path))
    with session_factory() as db:
        db.execute(
            text("UPDATE customers SET phone_verified_at = CURRENT_TIMESTAMP WHERE phone_e164 = :phone"),
            {"phone": "+919111111111"},
        )
        db.commit()

    response = client.post(
        f"/api/v1/orders/{order_id}/send-whatsapp-summary",
        headers={"X-API-Key": "internal-test-key"},
        json={
            "template_name": "order_summary_v1",
            "template_helper": "order_summary",
        },
    )
    assert response.status_code == 200
    assert captured["template_name"] == "order_summary_v1"
    components = captured["components"]
    assert isinstance(components, list)
    assert components[0]["type"] == "body"


def test_captain_order_wraps_urls_and_dish_review_links(tmp_path: Path) -> None:
    client, settings = create_test_client(tmp_path)

    order_response = client.post(
        "/api/v1/captain/orders",
        headers={"X-API-Key": "internal-test-key"},
        json={
            "external_order_id": "ORD-TRACK-1",
            "external_customer_id": "CUST-TRACK-1",
            "customer_name": "Tracked User",
            "customer_phone": "+919333333333",
            "restaurant_id": "rest-track",
            "restaurant_name": "Tracked Bistro",
            "total_amount": "450.00",
            "menu_url": "https://palate.test/menu/rest-track",
            "order_url": "https://palate.test/orders/ORD-TRACK-1",
            "bill_url": "https://palate.test/bill/ORD-TRACK-1",
            "payment_url": "https://palate.test/pay/ORD-TRACK-1",
            "feedback_url": "https://palate.test/feedback/ORD-TRACK-1",
            "dish_reviews": [
                {
                    "dish_id": "dish_1",
                    "dish_name": "Truffle Pasta",
                    "review_url": "https://palate.test/review/dish_1?order_id=ORD-TRACK-1",
                }
            ],
        },
    )
    assert order_response.status_code == 200
    order_id = order_response.json()["order_id"]

    session_factory = get_session_factory(settings)
    with session_factory() as db:
        order = db.get(Order, uuid.UUID(order_id))
        assert order is not None
        assert order.menu_url.startswith("http://testserver/r/")
        assert order.order_url.startswith("http://testserver/r/")
        assert order.bill_url.startswith("http://testserver/r/")
        assert order.payment_url.startswith("http://testserver/r/")
        assert order.feedback_url.startswith("http://testserver/r/")
        notes = order.notes
        assert notes["dish_reviews"][0]["review_url"].startswith("http://testserver/r/")
        assert notes["dish_reviews"][0]["original_review_url"] == "https://palate.test/review/dish_1?order_id=ORD-TRACK-1"


def test_tracking_summary_reports_verified_screen_funnel(tmp_path: Path, monkeypatch) -> None:
    client, settings = create_test_client(tmp_path)

    async def fake_send_text_message(self, to_phone: str, body: str, preview_url: bool = False):
        return {"messages": [{"id": "wamid.track-1"}], "contacts": [{"input": to_phone}]}

    monkeypatch.setattr("app.services.meta.MetaWhatsAppClient.send_text_message", fake_send_text_message)

    session_response = client.post(
        "/api/v1/whatsapp/session-link",
        headers={"X-API-Key": "internal-test-key"},
        json={
            "restaurant_id": "rest-summary",
            "restaurant_name": "Summary Bistro",
            "entry_point": "payment",
            "intent": "send_payment_link",
            "resume_url": "https://palate.test/pay/ORD-SUMMARY-1",
        },
    )
    assert session_response.status_code == 200

    wa_url = session_response.json()["wa_url"]
    token = parse_qs(urlparse(wa_url).query)["text"][0].split("Token: ", 1)[1]
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "wamid.summary-inbound-1",
                                    "from": "919999888877",
                                    "type": "text",
                                    "text": {"body": f"Token: {token}"},
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }
    raw_body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(settings.meta_app_secret.get_secret_value().encode("utf-8"), raw_body, sha256).hexdigest()
    webhook_response = client.post(
        "/webhooks/meta/whatsapp",
        headers={"X-Hub-Signature-256": f"sha256={signature}"},
        content=raw_body,
    )
    assert webhook_response.status_code == 200

    summary_response = client.get(
        "/api/v1/tracking/summary",
        headers={"X-API-Key": "internal-test-key"},
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    payment_row = next(item for item in summary["screen_funnel"] if item["stage"] == "payment")
    assert payment_row["linked_sessions"] == 1
    assert payment_row["verified_sessions"] == 1
    assert payment_row["unique_verified_phones"] == 1
    assert payment_row["verification_rate"] == 100.0
    assert summary["unique_verified_phones"] == 1
    assert summary["phone_rollup"][0]["phone"].startswith("+919")
    assert summary["recent_verifications"][0]["stage"] == "payment"


def test_dashboard_login_and_data_show_full_phone_and_hide_legacy(tmp_path: Path) -> None:
    client, settings = create_test_client(tmp_path)
    session_factory = get_session_factory(settings)
    current_customer_id = uuid.uuid4()
    legacy_customer_id = uuid.uuid4()
    current_order_id = uuid.uuid4()
    legacy_order_id = uuid.uuid4()
    current_session_id = uuid.uuid4()
    legacy_session_id = uuid.uuid4()
    with session_factory() as db:
        db.execute(
            text(
                """
                INSERT INTO customers (id, display_name, phone_e164, onboarding_status, created_at, updated_at)
                VALUES (:id, :name, :phone, 'verified', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {"id": str(current_customer_id), "name": "Current User", "phone": "+919111111111"},
        )
        db.execute(
            text(
                """
                INSERT INTO customers (id, display_name, phone_e164, onboarding_status, created_at, updated_at)
                VALUES (:id, :name, :phone, 'verified', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {"id": str(legacy_customer_id), "name": "Signed Debug User", "phone": "+919876543210"},
        )
        db.execute(
            text(
                """
                INSERT INTO orders (id, external_order_id, customer_id, restaurant_id, restaurant_name, order_status, currency, notes, line_items, created_at, updated_at)
                VALUES (:id, :external_order_id, :customer_id, 'rest-1', 'Palate', 'created', 'INR', '{}', '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {"id": str(current_order_id), "external_order_id": "ORD-CURRENT", "customer_id": str(current_customer_id)},
        )
        db.execute(
            text(
                """
                INSERT INTO orders (id, external_order_id, customer_id, restaurant_id, restaurant_name, order_status, currency, notes, line_items, created_at, updated_at)
                VALUES (:id, :external_order_id, :customer_id, 'palate-demo', 'Palate Demo Bistro', 'created', 'INR', '{}', '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
            ),
            {"id": str(legacy_order_id), "external_order_id": "ORD-LEGACY", "customer_id": str(legacy_customer_id)},
        )
        db.execute(
            text(
                """
                INSERT INTO whatsapp_sessions (
                  id, order_id, customer_id, restaurant_id, restaurant_name, token_hash, token_hint, session_status, entry_point, intent,
                  provided_name, phone_e164, verified_at, expires_at, metadata, created_at, updated_at
                )
                VALUES (
                  :id, :order_id, :customer_id, 'rest-1', 'Palate', 'hash-current', 'hint', 'verified', 'menu', 'verify_before_payment',
                  'Current User', '+919111111111', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {"id": str(current_session_id), "order_id": str(current_order_id), "customer_id": str(current_customer_id)},
        )
        db.execute(
            text(
                """
                INSERT INTO whatsapp_sessions (
                  id, order_id, customer_id, restaurant_id, restaurant_name, token_hash, token_hint, session_status, entry_point, intent,
                  provided_name, phone_e164, verified_at, expires_at, metadata, created_at, updated_at
                )
                VALUES (
                  :id, :order_id, :customer_id, 'palate-demo', 'Palate Demo Bistro', 'hash-legacy', 'hint', 'verified', 'demo', 'verify_before_payment',
                  'Signed Debug User', '+919876543210', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {"id": str(legacy_session_id), "order_id": str(legacy_order_id), "customer_id": str(legacy_customer_id)},
        )
        db.execute(
            text(
                """
                INSERT INTO journey_events (id, event_type, stage, action, restaurant_id, order_id, session_id, metadata, created_at)
                VALUES (:id, 'session_started', 'menu', 'verify_before_payment', 'rest-1', :order_id, :session_id, '{}', CURRENT_TIMESTAMP)
                """
            ),
            {"id": str(uuid.uuid4()), "order_id": str(current_order_id), "session_id": str(current_session_id)},
        )
        db.execute(
            text(
                """
                INSERT INTO journey_events (id, event_type, stage, action, restaurant_id, order_id, session_id, metadata, created_at)
                VALUES (:id, 'session_verified', 'menu', 'verify_before_payment', 'rest-1', :order_id, :session_id, '{}', CURRENT_TIMESTAMP)
                """
            ),
            {"id": str(uuid.uuid4()), "order_id": str(current_order_id), "session_id": str(current_session_id)},
        )
        db.execute(
            text(
                """
                INSERT INTO journey_events (id, event_type, stage, action, restaurant_id, order_id, session_id, metadata, created_at)
                VALUES (:id, 'session_started', 'demo', 'verify_before_payment', 'palate-demo', :order_id, :session_id, '{}', CURRENT_TIMESTAMP)
                """
            ),
            {"id": str(uuid.uuid4()), "order_id": str(legacy_order_id), "session_id": str(legacy_session_id)},
        )
        db.execute(
            text(
                """
                INSERT INTO journey_events (id, event_type, stage, action, restaurant_id, order_id, session_id, metadata, created_at)
                VALUES (:id, 'session_verified', 'demo', 'verify_before_payment', 'palate-demo', :order_id, :session_id, '{}', CURRENT_TIMESTAMP)
                """
            ),
            {"id": str(uuid.uuid4()), "order_id": str(legacy_order_id), "session_id": str(legacy_session_id)},
        )
        db.commit()

    unauth = client.get("/dashboard/basic", follow_redirects=False)
    assert unauth.status_code == 303
    assert unauth.headers["location"] == "/dashboard/login"

    login = client.post("/dashboard/login", data={"password": "dashboard-pass"}, follow_redirects=False)
    assert login.status_code == 303
    assert login.headers["location"] == "/dashboard/basic"

    data_response = client.get("/dashboard/basic/data")
    assert data_response.status_code == 200
    payload = data_response.json()
    assert payload["unique_verified_phones"] == 1
    assert payload["phone_rollup"][0]["phone"] == "+919111111111"
    assert all(row["stage"] != "demo" for row in payload["recent_verifications"])

    legacy_response = client.get("/dashboard/basic/data?include_legacy=true")
    assert legacy_response.status_code == 200
    legacy_payload = legacy_response.json()
    phones = {row["phone"] for row in legacy_payload["phone_rollup"]}
    assert "+919111111111" in phones
    assert "+919876543210" in phones


def test_meta_client_retries_transient_failure(tmp_path: Path, monkeypatch) -> None:
    settings = build_settings(tmp_path)
    settings.meta_send_max_attempts = 3
    settings.meta_retry_backoff_seconds = 0
    client = MetaWhatsAppClient(settings)
    calls = {"count": 0}

    async def fake_post(self, url, headers=None, json=None):
        calls["count"] += 1
        request = httpx.Request("POST", url)
        if calls["count"] == 1:
            return httpx.Response(503, json={"error": {"message": "temporary"}}, request=request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.retry-ok"}]}, request=request)

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    result = asyncio.run(client.send_text_message("+919222222222", "hello"))
    assert result["messages"][0]["id"] == "wamid.retry-ok"
    assert calls["count"] == 2


def test_demo_routes_disabled_when_demo_mode_false(tmp_path: Path) -> None:
    client, _ = create_test_client(tmp_path)
    response = client.get("/demo")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "demo_mode_disabled"


def test_demo_open_redirects_to_demo(tmp_path: Path) -> None:
    settings = Settings.model_validate(
        {
            "DATABASE_URL": f"sqlite+pysqlite:///{tmp_path / 'demo-open.db'}",
            "INTERNAL_API_KEY": "internal-test-key",
            "SESSION_TOKEN_PEPPER": "pepper-test",
            "WHATSAPP_PROVIDER": "twilio",
            "DEMO_MODE": True,
            "PUBLIC_BASE_URL": "https://demo.palate.test",
            "META_VERIFY_TOKEN": "verify-me",
            "META_APP_SECRET": "meta-secret",
            "META_ACCESS_TOKEN": "meta-token",
            "META_PHONE_NUMBER_ID": "123456",
            "TWILIO_ACCOUNT_SID": "AC1234567890",
            "TWILIO_AUTH_TOKEN": "twilio-secret",
            "TWILIO_WHATSAPP_FROM": "+14155238886",
            "TWILIO_WEBHOOK_AUTH_ENABLED": False,
            "RAZORPAY_WEBHOOK_SECRET": "rzp-secret",
        }
    )
    client = create_test_client_with_settings(settings)
    response = client.get("/demo/open", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://demo.palate.test/demo"


def test_demo_short_open_redirects_to_demo_and_qr_is_png(tmp_path: Path) -> None:
    settings = Settings.model_validate(
        {
            "DATABASE_URL": f"sqlite+pysqlite:///{tmp_path / 'demo-short.db'}",
            "INTERNAL_API_KEY": "internal-test-key",
            "SESSION_TOKEN_PEPPER": "pepper-test",
            "WHATSAPP_PROVIDER": "twilio",
            "DEMO_MODE": True,
            "PUBLIC_BASE_URL": "https://demo.palate.test",
            "META_VERIFY_TOKEN": "verify-me",
            "META_APP_SECRET": "meta-secret",
            "META_ACCESS_TOKEN": "meta-token",
            "META_PHONE_NUMBER_ID": "123456",
            "TWILIO_ACCOUNT_SID": "AC1234567890",
            "TWILIO_AUTH_TOKEN": "twilio-secret",
            "TWILIO_WHATSAPP_FROM": "+14155238886",
            "TWILIO_WEBHOOK_AUTH_ENABLED": False,
            "RAZORPAY_WEBHOOK_SECRET": "rzp-secret",
        }
    )
    client = create_test_client_with_settings(settings)
    redirect_response = client.get("/d", follow_redirects=False)
    assert redirect_response.status_code == 307
    assert redirect_response.headers["location"] == "https://demo.palate.test/demo"

    qr_response = client.get("/demo/qr")
    assert qr_response.status_code == 200
    assert qr_response.headers["content-type"] == "image/png"


def test_demo_screen_renders_order_context(tmp_path: Path) -> None:
    settings = Settings.model_validate(
        {
            "DATABASE_URL": f"sqlite+pysqlite:///{tmp_path / 'demo-screen.db'}",
            "INTERNAL_API_KEY": "internal-test-key",
            "SESSION_TOKEN_PEPPER": "pepper-test",
            "WHATSAPP_PROVIDER": "twilio",
            "DEMO_MODE": True,
            "PUBLIC_BASE_URL": "https://demo.palate.test",
            "META_VERIFY_TOKEN": "verify-me",
            "META_APP_SECRET": "meta-secret",
            "META_ACCESS_TOKEN": "meta-token",
            "META_PHONE_NUMBER_ID": "123456",
            "TWILIO_ACCOUNT_SID": "AC1234567890",
            "TWILIO_AUTH_TOKEN": "twilio-secret",
            "TWILIO_WHATSAPP_FROM": "+14155238886",
            "TWILIO_WEBHOOK_AUTH_ENABLED": False,
            "RAZORPAY_WEBHOOK_SECRET": "rzp-secret",
        }
    )
    client = create_test_client_with_settings(settings)
    session_response = client.post("/demo/session-link", json={"customer_name": "Screen Demo"})
    payload = session_response.json()

    response = client.get(f"/demo?screen=bill&order={payload['external_order_id']}")
    assert response.status_code == 200
    assert "Bill breakdown" in response.text
    assert payload["external_order_id"] in response.text
    assert "Amount due" in response.text
    assert "Continue to payment" in response.text


def test_demo_landing_hides_debug_by_default(tmp_path: Path) -> None:
    settings = Settings.model_validate(
        {
            "DATABASE_URL": f"sqlite+pysqlite:///{tmp_path / 'demo-landing.db'}",
            "INTERNAL_API_KEY": "internal-test-key",
            "SESSION_TOKEN_PEPPER": "pepper-test",
            "WHATSAPP_PROVIDER": "twilio",
            "DEMO_MODE": True,
            "PUBLIC_BASE_URL": "https://demo.palate.test",
            "META_VERIFY_TOKEN": "verify-me",
            "META_APP_SECRET": "meta-secret",
            "META_ACCESS_TOKEN": "meta-token",
            "META_PHONE_NUMBER_ID": "123456",
            "TWILIO_ACCOUNT_SID": "AC1234567890",
            "TWILIO_AUTH_TOKEN": "twilio-secret",
            "TWILIO_WHATSAPP_FROM": "+14155238886",
            "TWILIO_WEBHOOK_AUTH_ENABLED": False,
            "RAZORPAY_WEBHOOK_SECRET": "rzp-secret",
        }
    )
    client = create_test_client_with_settings(settings)
    response = client.get("/demo")
    assert response.status_code == 200
    assert "Verification status:" in response.text
    assert 'id="advanced-facts"' in response.text
    assert 'class="facts advanced-facts"' in response.text
    assert 'id="debug-card" class="card debug-card"' in response.text


def test_compose_demo_verification_message_varies_by_entry_point() -> None:
    order = Order(
        external_order_id="DEMO-ORDER-1",
        restaurant_name="Palate Demo Bistro",
        currency="INR",
        total_amount=850,
        amount_paid=0,
    )

    payment_session = WhatsAppSession(
        restaurant_name="Palate Demo Bistro",
        provided_name="Riya",
        phone_e164="+919876543210",
        entry_point="payment",
        resume_url="https://palate.test/pay/demo-order-1",
        metadata_json={"demo_mode": True, "entry_point": "payment"},
    )
    payment_message = compose_demo_verification_message(order, payment_session)
    assert "your payment step is ready" in payment_message.lower()
    assert "Amount due: INR 850.00" in payment_message
    assert "Pay here: https://palate.test/pay/demo-order-1" in payment_message
    assert "keep browsing the menu here" not in payment_message.lower()

    feedback_session = WhatsAppSession(
        restaurant_name="Palate Demo Bistro",
        provided_name="Riya",
        phone_e164="+919876543210",
        entry_point="feedback",
        resume_url="https://palate.test/feedback/demo-order-1",
        metadata_json={"demo_mode": True, "entry_point": "feedback"},
    )
    feedback_message = compose_demo_verification_message(order, feedback_session)
    assert "your feedback page is ready" in feedback_message.lower()
    assert "Share feedback here: https://palate.test/feedback/demo-order-1" in feedback_message


def test_integration_intake_page_and_submission(tmp_path: Path) -> None:
    client, _ = create_test_client(tmp_path)

    page_response = client.get("/intake/palate")
    assert page_response.status_code == 200
    assert "Palate Integration Intake" in page_response.text

    submit_response = client.post(
        "/api/v1/intake/submissions",
        json={
            "respondent_name": "Sai",
            "respondent_role": "Founder",
            "provider_primary": "meta",
            "provider_backup": "twilio",
            "real_urls": {
                "menu_url": "https://app.palate.test/menu",
                "payment_url": "https://app.palate.test/pay",
            },
            "order_sources": ["website", "captain_manual"],
            "verification_points": ["cart", "payment"],
            "customer_inputs": ["name_optional", "whatsapp_profile_fallback"],
            "payment_provider": "razorpay",
            "required_messages": ["verification_success", "bill", "payment_success"],
            "ownership": {"meta_webhook": "Client tech team"},
            "final_flow_notes": "Menu to cart to WhatsApp to payment.",
        },
    )
    assert submit_response.status_code == 200
    payload = submit_response.json()
    assert payload["status"] == "new"
    assert payload["project_key"] == "palate_whatsapp_phase1"

    list_response = client.get(
        "/api/v1/intake/submissions",
        headers={"X-API-Key": "internal-test-key"},
    )
    assert list_response.status_code == 200
    submissions = list_response.json()
    assert len(submissions) == 1
    assert submissions[0]["respondent_name"] == "Sai"
    assert submissions[0]["provider_primary"] == "meta"
    assert submissions[0]["real_urls"]["payment_url"] == "https://app.palate.test/pay"
    assert submissions[0]["verification_points"] == ["cart", "payment"]


def test_twilio_demo_flow_verifies_and_sends_messages(tmp_path: Path, monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "DATABASE_URL": f"sqlite+pysqlite:///{tmp_path / 'twilio.db'}",
            "INTERNAL_API_KEY": "internal-test-key",
            "SESSION_TOKEN_PEPPER": "pepper-test",
            "WHATSAPP_PROVIDER": "twilio",
            "DEMO_MODE": True,
            "PUBLIC_BASE_URL": "https://demo.palate.test",
            "META_VERIFY_TOKEN": "verify-me",
            "META_APP_SECRET": "meta-secret",
            "META_ACCESS_TOKEN": "meta-token",
            "META_PHONE_NUMBER_ID": "123456",
            "TWILIO_ACCOUNT_SID": "AC1234567890",
            "TWILIO_AUTH_TOKEN": "twilio-secret",
            "TWILIO_WHATSAPP_FROM": "+14155238886",
            "TWILIO_WEBHOOK_AUTH_ENABLED": False,
            "RAZORPAY_WEBHOOK_SECRET": "rzp-secret",
        }
    )
    client = create_test_client_with_settings(settings)

    calls = {"count": 0, "bodies": []}

    async def fake_send_text_message(self, to_phone: str, body: str, preview_url: bool = False):
        calls["count"] += 1
        calls["bodies"].append(body)
        return {"sid": f"SMdemo{calls['count']}", "to": to_phone, "body": body}

    monkeypatch.setattr("app.services.twilio.TwilioWhatsAppClient.send_text_message", fake_send_text_message)

    demo_page = client.get("/demo")
    assert demo_page.status_code == 200

    session_response = client.post("/demo/session-link", json={"customer_name": "Twilio Demo"})
    assert session_response.status_code == 200
    session_payload = session_response.json()
    session_id = session_payload["session_id"]
    order_id = session_payload["order_id"]

    wa_url = session_payload["wa_url"]
    token = parse_qs(urlparse(wa_url).query)["text"][0].split("Token: ", 1)[1]

    twilio_webhook = client.post(
        "/webhooks/twilio/whatsapp",
        data={
            "From": "whatsapp:+919876543210",
            "To": "whatsapp:+14155238886",
            "Body": f"Hi Palate. Token: {token}",
            "MessageSid": "SMinbound123",
            "WaId": "919876543210",
            "ProfileName": "Twilio Demo",
        },
    )
    assert twilio_webhook.status_code == 200
    assert "<Response>" in twilio_webhook.text

    session_status = client.get(f"/demo/sessions/{session_id}")
    assert session_status.status_code == 200
    assert session_status.json()["session_status"] == "verified"
    assert session_status.json()["verified_phone"] == "+919876543210"
    assert session_status.json()["provided_name"] == "Twilio Demo"
    assert "Twilio Demo" in calls["bodies"][0]
    assert "+919876543210" in calls["bodies"][0]
    assert "keep browsing the menu here" in calls["bodies"][0]
    assert session_payload["resume_url"] in calls["bodies"][0]
    assert session_payload["external_order_id"] not in calls["bodies"][0]
    assert "Total: INR 850.00" not in calls["bodies"][0]
    assert "We will send updates, bill, and payment steps here on WhatsApp." not in calls["bodies"][0]

    order_message = client.post(f"/demo/orders/{order_id}/send-order-list")
    assert order_message.status_code == 200
    assert order_message.json()["status"] == "accepted"
    assert "Items:" in calls["bodies"][1]
    assert "- 2 x Truffle Pasta" in calls["bodies"][1]
    assert "Total: INR 850.00" in calls["bodies"][1]
    assert "View order:" in calls["bodies"][1]
    assert "Menu:" not in calls["bodies"][1]

    bill_message = client.post(f"/demo/orders/{order_id}/send-bill")
    assert bill_message.status_code == 200
    assert bill_message.json()["status"] == "accepted"
    assert "Subtotal: INR 720.00" in calls["bodies"][2]
    assert "Tax: INR 130.00" in calls["bodies"][2]
    assert "Amount due: INR 850.00" in calls["bodies"][2]
    assert "Pay now:" in calls["bodies"][2]
    assert "Order:" not in calls["bodies"][2]

    feedback_message = client.post(f"/demo/orders/{order_id}/send-feedback")
    assert feedback_message.status_code == 200
    assert feedback_message.json()["status"] == "accepted"
    assert "How was your experience?" in calls["bodies"][3]
    assert "Rate the dishes you ordered:" in calls["bodies"][3]
    assert "Review Truffle Pasta:" in calls["bodies"][3]
    assert "Share feedback:" in calls["bodies"][3]

    payment_message = client.post(f"/demo/simulate-payment-success?order_id={order_id}")
    assert payment_message.status_code == 200
    assert payment_message.json()["status"] == "accepted"
    assert "Paid amount: INR 850.00" in calls["bodies"][4]
    assert "Share feedback:" in calls["bodies"][4]
