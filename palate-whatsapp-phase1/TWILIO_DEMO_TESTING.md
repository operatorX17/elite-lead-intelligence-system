# Twilio Demo Testing

This document covers the Twilio WhatsApp adapter and the demo/QR flow built on top of it.

Recommended production default for Palate remains:

```text
WHATSAPP_PROVIDER=meta
DEMO_MODE=false
```

Twilio can be used in three ways:

- as the live provider in a Twilio-backed deployment
- as a temporary test deployment before Meta credentials are ready
- as an alternate provider strategy if the client later chooses to operate through Twilio instead of Meta

## What This Adds

- provider abstraction: `meta | twilio | mock`
- Twilio outbound text send adapter
- Twilio inbound webhook adapter at `POST /webhooks/twilio/whatsapp`
- public demo page at `GET /demo`
- QR route at `GET /demo/qr`
- demo payment success simulator at `POST /demo/simulate-payment-success`
- local demo smoke script:
  - [scripts/smoke_test_twilio_demo.py](<C:/Users/G Sai Prakash/Downloads/zrai-lead-oss-main/palate-whatsapp-phase1/scripts/smoke_test_twilio_demo.py>)

## Railway Twilio Env Variables

Required for a Twilio-backed deployment:

- `DATABASE_URL`
- `INTERNAL_API_KEY`
- `SESSION_TOKEN_PEPPER`
- `WHATSAPP_PROVIDER=twilio`
- `DEMO_MODE=true`
- `PUBLIC_BASE_URL=https://<your-railway-domain>`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_FROM`
- `TWILIO_WEBHOOK_AUTH_ENABLED=true`
- `RAZORPAY_WEBHOOK_SECRET`

Recommended:

- `APP_NAME=Palate WhatsApp Phase 1`
- `ENVIRONMENT=production`
- `LOG_LEVEL=INFO`
- `WHATSAPP_SESSION_TTL_MINUTES=1440`

Optional for keeping Meta paths available on the same codebase without using them in demo mode:

- `META_VERIFY_TOKEN`
- `META_APP_SECRET`
- `META_ACCESS_TOKEN`
- `META_PHONE_NUMBER_ID`
- `PALATE_WHATSAPP_NUMBER`

## Twilio Webhook URL

Configure Twilio WhatsApp incoming webhook to:

```text
https://<your-railway-domain>/webhooks/twilio/whatsapp
```

The webhook must use `HTTP POST`.

If `TWILIO_WEBHOOK_AUTH_ENABLED=true`, the backend validates the `X-Twilio-Signature` header using `TWILIO_AUTH_TOKEN` and `PUBLIC_BASE_URL`.

## Local Run

Use this when you want to test the demo UI and simulated Twilio inbound flow locally.

1. Copy `.env.example` to `.env`.
2. Set:

```text
WHATSAPP_PROVIDER=twilio
DEMO_MODE=true
PUBLIC_BASE_URL=http://127.0.0.1:8000
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=replace-me
TWILIO_WHATSAPP_FROM=+14155238886
TWILIO_WEBHOOK_AUTH_ENABLED=false
```

3. Run migrations:

```bash
alembic upgrade head
```

4. Start the API:

```bash
uvicorn app.main:app --reload
```

5. Open:

```text
http://127.0.0.1:8000/demo
```

6. For automated local verification of the demo flow, run:

```bash
python scripts/smoke_test_twilio_demo.py --base-url http://127.0.0.1:8000
```

Important:

- The local smoke path simulates Twilio inbound webhook calls.
- Real outbound Twilio sending still needs valid Twilio credentials.
- For fully real phone testing, deploy to Railway or expose your local server through a public HTTPS tunnel and set `PUBLIC_BASE_URL` to that public URL.

## Railway Deploy

1. Create a separate Railway service for the Twilio-backed deployment.
2. Attach PostgreSQL.
3. Deploy this folder.
4. Set the Twilio demo env vars above.
5. Run:

```text
alembic upgrade head
```

6. Visit:

```text
https://<your-railway-domain>/demo
```

7. Configure Twilio incoming webhook to `https://<your-railway-domain>/webhooks/twilio/whatsapp`.
8. Scan the QR or open `/demo` directly on your phone.

## How To Test The QR / WhatsApp Flow

1. Open `/demo`.
2. Optionally type a customer name.
3. Tap `Continue with WhatsApp`.
4. WhatsApp opens with the prefilled token message.
5. Send the message.
6. Twilio forwards the inbound WhatsApp message to `/webhooks/twilio/whatsapp`.
7. Backend extracts `PALATE_*`, matches the session, verifies the sender phone, and marks the session verified.
8. The demo page polls session status and flips from `pending` to `verified`.
9. Tap:
   - `Send order list on WhatsApp`
   - `Receive bill on WhatsApp`
   - `Send feedback link`
10. Tap `Simulate payment success` to mark the demo order paid and send the payment-success message path.

## If You Want Meta As The Final Production Default

If Palate finally chooses Meta Cloud API as the main production provider, switch cleanly:

1. Set:

```text
WHATSAPP_PROVIDER=meta
DEMO_MODE=false
```

2. Ensure:

- `META_MOCK_MODE=false`
- Twilio webhook is removed or disabled in Twilio Console
- demo Railway service is archived or clearly labeled non-production

3. Keep Twilio credentials out of the client’s final production handover pack unless they explicitly want the Twilio adapter retained for operations.

## Recommended Positioning To Client

Position this as a real second provider adapter.

- Meta Cloud API remains the default recommendation.
- Twilio is a supported alternate adapter.
- The QR/demo surface is only one testing experience built on top of the Twilio adapter.
