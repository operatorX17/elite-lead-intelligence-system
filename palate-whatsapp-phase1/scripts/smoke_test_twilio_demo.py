from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import parse_qs, urlparse

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Palate Twilio demo smoke flow against a local or deployed server.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--twilio-from", default="+14155238886")
    parser.add_argument("--customer-name", default="Twilio Demo User")
    parser.add_argument("--customer-phone", default="+919876543210")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timeout = httpx.Timeout(30.0)

    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=timeout) as client:
        results: dict[str, object] = {}

        results["health"] = client.get("/health").json()
        ready_response = client.get("/ready")
        ready_response.raise_for_status()
        results["ready"] = ready_response.json()

        demo_page = client.get("/demo")
        demo_page.raise_for_status()
        results["demo_page"] = {"status_code": demo_page.status_code}

        session_link = client.post("/demo/session-link", json={"customer_name": args.customer_name})
        session_link.raise_for_status()
        results["session_link"] = session_link.json()

        wa_url = results["session_link"]["wa_url"]  # type: ignore[index]
        session_id = results["session_link"]["session_id"]  # type: ignore[index]
        order_id = results["session_link"]["order_id"]  # type: ignore[index]
        token = parse_qs(urlparse(wa_url).query)["text"][0].split("Token: ", 1)[1]

        twilio_webhook = client.post(
            "/webhooks/twilio/whatsapp",
            data={
                "From": f"whatsapp:{args.customer_phone}",
                "To": f"whatsapp:{args.twilio_from}",
                "Body": f"Hi Palate, continuing demo. Token: {token}",
                "MessageSid": "SM-smoke-demo-001",
                "WaId": args.customer_phone.lstrip("+"),
                "ProfileName": args.customer_name,
            },
        )
        twilio_webhook.raise_for_status()
        results["twilio_webhook"] = {"status_code": twilio_webhook.status_code, "body": twilio_webhook.text}

        session_status = client.get(f"/demo/sessions/{session_id}")
        session_status.raise_for_status()
        results["session_status"] = session_status.json()

        order_send = client.post(f"/demo/orders/{order_id}/send-order-list")
        order_send.raise_for_status()
        results["send_order_list"] = order_send.json()

        bill_send = client.post(f"/demo/orders/{order_id}/send-bill")
        bill_send.raise_for_status()
        results["send_bill"] = bill_send.json()

        feedback_send = client.post(f"/demo/orders/{order_id}/send-feedback")
        feedback_send.raise_for_status()
        results["send_feedback"] = feedback_send.json()

        payment_success = client.post("/demo/simulate-payment-success", params={"order_id": order_id})
        payment_success.raise_for_status()
        results["simulate_payment_success"] = payment_success.json()

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except httpx.HTTPError as exc:
        print(f"Twilio demo smoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
