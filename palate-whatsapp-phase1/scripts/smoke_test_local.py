from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
from urllib.parse import parse_qs, urlparse

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Palate WhatsApp Phase 1 local smoke test flow.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--meta-verify-token", required=True)
    parser.add_argument("--meta-app-secret", required=True)
    parser.add_argument("--razorpay-webhook-secret", required=True)
    parser.add_argument("--restaurant-id", default="rest_smoke_001")
    parser.add_argument("--restaurant-name", default="Palate Smoke Test")
    parser.add_argument("--order-id", default="ORD-SMOKE-1001")
    parser.add_argument("--customer-id", default="CUST-SMOKE-1001")
    parser.add_argument("--customer-name", default="Riya Smoke")
    parser.add_argument("--customer-phone", default="+919876543210")
    parser.add_argument("--use-captain-auto-session", action="store_true")
    return parser.parse_args()


def sign_meta(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def sign_razorpay(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def main() -> int:
    args = parse_args()
    private_headers = {"X-API-Key": args.api_key}
    timeout = httpx.Timeout(30.0)

    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=timeout) as client:
        results: dict[str, object] = {}

        results["health"] = client.get("/health").json()
        ready_response = client.get("/ready")
        ready_response.raise_for_status()
        results["ready"] = ready_response.json()

        captain_payload = {
            "external_order_id": args.order_id,
            "external_customer_id": args.customer_id,
            "customer_name": args.customer_name,
            "customer_phone": args.customer_phone,
            "customer_email": "riya.smoke@example.com",
            "restaurant_id": args.restaurant_id,
            "restaurant_name": args.restaurant_name,
            "order_status": "created",
            "currency": "INR",
            "subtotal_amount": "720.00",
            "tax_amount": "130.00",
            "total_amount": "850.00",
            "amount_paid": "0.00",
            "summary_text": "2 x pasta, 1 x tiramisu",
            "menu_url": "https://app.palate.example/menu/rest_smoke_001",
            "order_url": "https://app.palate.example/orders/ORD-SMOKE-1001",
            "bill_url": "https://app.palate.example/bill/ORD-SMOKE-1001",
            "payment_url": "https://pay.palate.example/ORD-SMOKE-1001",
            "feedback_url": "https://app.palate.example/feedback/ORD-SMOKE-1001",
            "notes": {"table": "T7"},
            "dish_reviews": [
                {
                    "dish_id": "dish_smoke_pasta",
                    "dish_name": "Truffle Pasta",
                    "review_url": "https://app.palate.example/review/dish_smoke_pasta?order_id=ORD-SMOKE-1001",
                }
            ],
            "line_items": [
                {"name": "Truffle Pasta", "quantity": 2},
                {"name": "Tiramisu", "quantity": 1},
            ],
            "auto_create_session_link": args.use_captain_auto_session,
        }
        captain_order = client.post("/api/v1/captain/orders", headers=private_headers, json=captain_payload)
        captain_order.raise_for_status()
        results["captain_order"] = captain_order.json()
        order_id = results["captain_order"]["order_id"]  # type: ignore[index]

        if args.use_captain_auto_session:
            session_link = results["captain_order"]["session_link"]  # type: ignore[index]
        else:
            session_link_response = client.post(
                "/api/v1/whatsapp/session-link",
                headers=private_headers,
                json={
                    "order_id": order_id,
                    "entry_point": "payment",
                    "intent": "verify_before_payment",
                    "resume_url": "https://app.palate.example/checkout/review",
                },
            )
            session_link_response.raise_for_status()
            session_link = session_link_response.json()
            results["session_link"] = session_link

        wa_url = session_link["wa_url"]
        text_payload = parse_qs(urlparse(wa_url).query)["text"][0]
        token = text_payload.split("Token: ", 1)[1]
        session_id = session_link["session_id"]

        verify_response = client.get(
            "/webhooks/meta/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "12345",
                "hub.verify_token": args.meta_verify_token,
            },
        )
        verify_response.raise_for_status()
        results["webhook_verify_get"] = verify_response.text

        inbound_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "919999999999",
                                    "phone_number_id": "1234567890",
                                },
                                "contacts": [
                                    {
                                        "profile": {"name": args.customer_name},
                                        "wa_id": args.customer_phone.lstrip("+"),
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": args.customer_phone.lstrip("+"),
                                        "id": "wamid.smoke-inbound-1",
                                        "timestamp": "1714020300",
                                        "type": "text",
                                        "text": {
                                            "body": (
                                                f"Hi {args.restaurant_name}, I want to continue on Palate. "
                                                f"Reference: {args.order_id}. Token: {token}"
                                            )
                                        },
                                    }
                                ],
                            },
                        }
                    ]
                }
            ],
        }
        inbound_payload_json = json.dumps(inbound_payload, separators=(",", ":"))
        inbound_response = client.post(
            "/webhooks/meta/whatsapp",
            headers={"X-Hub-Signature-256": sign_meta(inbound_payload_json, args.meta_app_secret)},
            content=inbound_payload_json,
        )
        inbound_response.raise_for_status()
        results["incoming_token_webhook"] = inbound_response.json()

        session_status = client.get(f"/api/v1/whatsapp/sessions/{session_id}", headers=private_headers)
        session_status.raise_for_status()
        results["session_status"] = session_status.json()

        send_message = client.post(
            "/api/v1/whatsapp/send-message",
            headers=private_headers,
            json={
                "order_id": order_id,
                "body": f"Your table is confirmed. View order: https://app.palate.example/orders/{args.order_id}",
                "preview_url": True,
            },
        )
        send_message.raise_for_status()
        results["send_message"] = send_message.json()

        send_template = client.post(
            "/api/v1/whatsapp/send-template",
            headers=private_headers,
            json={
                "order_id": order_id,
                "template_name": "order_summary_v1",
                "template_helper": "order_summary",
                "language_code": "en_US",
            },
        )
        send_template.raise_for_status()
        results["send_template"] = send_template.json()

        summary_send = client.post(
            f"/api/v1/orders/{order_id}/send-whatsapp-summary",
            headers=private_headers,
            json={"preview_url": True},
        )
        summary_send.raise_for_status()
        results["send_order_summary"] = summary_send.json()

        bill_send = client.post(
            f"/api/v1/orders/{order_id}/send-bill",
            headers=private_headers,
            json={"preview_url": True},
        )
        bill_send.raise_for_status()
        results["send_bill"] = bill_send.json()

        feedback_send = client.post(
            f"/api/v1/orders/{order_id}/send-feedback",
            headers=private_headers,
            json={"preview_url": True},
        )
        feedback_send.raise_for_status()
        results["send_feedback"] = feedback_send.json()

        razorpay_payload = {
            "entity": "event",
            "account_id": "acc_smoke",
            "event": "payment.captured",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_smoke_123",
                        "entity": "payment",
                        "amount": 85000,
                        "currency": "INR",
                        "status": "captured",
                        "order_id": "order_smoke_123",
                        "method": "upi",
                        "notes": {
                            "order_id": order_id,
                            "external_order_id": args.order_id,
                        },
                    }
                }
            },
        }
        razorpay_payload_json = json.dumps(razorpay_payload, separators=(",", ":"))
        razorpay_response = client.post(
            "/webhooks/payments/razorpay",
            headers={
                "X-Razorpay-Signature": sign_razorpay(razorpay_payload_json, args.razorpay_webhook_secret),
                "x-razorpay-event-id": "evt_smoke_123",
            },
            content=razorpay_payload_json,
        )
        razorpay_response.raise_for_status()
        results["razorpay_webhook"] = razorpay_response.json()

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except httpx.HTTPError as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
