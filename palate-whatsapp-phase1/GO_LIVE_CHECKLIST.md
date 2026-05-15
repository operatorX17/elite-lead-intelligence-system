# Go-Live Checklist

Use this checklist for Palate Phase 1 backend deployment and handover.

## 0. One-command preflight

Run this from the project root with the deployed env vars loaded, ideally from Railway shell:

```bash
python -m app.preflight --base-url https://<your-railway-domain>
```

The command fails fast on missing env, non-ready health state, stale Alembic revision, broken private auth, or missing webhook signature guards.

## 1. Railway Deploy

- Create Railway service from the `palate-whatsapp-phase1` project.
- Confirm `Dockerfile` is used for build.
- Add all required environment variables.
- Confirm `WHATSAPP_PROVIDER=meta` for production handover.
- Confirm `DEMO_MODE=false` for production handover.
- Set `ENVIRONMENT=production`.
- Set `LOG_LEVEL=INFO`.
- Set correct frontend origin in `CORS_ALLOW_ORIGINS`.
- Deploy successfully.
- Confirm `GET /health` returns `200`.
- Confirm `GET /ready` returns `200`.

## 2. Postgres Migration

- Confirm Railway PostgreSQL service is attached.
- Confirm `DATABASE_URL` points to Railway Postgres.
- Run `alembic upgrade head`.
- Verify tables exist:
  - `customers`
  - `orders`
  - `whatsapp_sessions`
  - `message_logs`
  - `webhook_events`
  - `payment_events`
- Confirm `alembic_version` is at repo head.

## 3. Meta Webhook Config

- Set callback URL to:

```text
https://<railway-domain>/webhooks/meta/whatsapp
```

- Set verify token in Meta to match `META_VERIFY_TOKEN`.
- Subscribe the app to WhatsApp message webhooks.
- Confirm GET verification succeeds.
- Send a real test message and confirm POST webhook reaches Railway.

## 4. Phone Number Registration

- Confirm the correct WhatsApp business phone number is registered in Cloud API.
- Confirm `META_PHONE_NUMBER_ID` matches the registered number.
- Confirm `PALATE_WHATSAPP_NUMBER` matches the visible E.164 number.
- Confirm the display name is approved.
- Confirm the number can send production messages.

## 5. WABA Subscribed App

- Confirm the correct Meta app is subscribed to the correct WABA.
- Confirm the production app, not only the sandbox/test app, is used.
- Confirm the app has the required permissions/token access.
- Confirm webhook subscriptions are active on the production app.

## 6. Razorpay Webhook Setup

- Create webhook endpoint in Razorpay:

```text
https://<railway-domain>/webhooks/payments/razorpay
```

- Copy webhook secret into `RAZORPAY_WEBHOOK_SECRET`.
- Enable required events:
  - `payment.authorized`
  - `payment.captured`
  - `payment.failed`
  - `order.paid`
  - optional `payment_link.paid` if used later
- Confirm a test event is accepted and deduped correctly.

## 7. Live WhatsApp Test

- Create a real captain/order payload in production-like data.
- Generate a session link.
- Open the returned `wa.me` link on a real phone.
- Send the prefilled message.
- Confirm webhook marks session `verified`.
- Confirm `GET /api/v1/whatsapp/sessions/{session_id}` returns:
  - `is_verified=true`
  - `can_proceed=true`
  - `next_action=resume_flow`
- Confirm outbound text send works.
- Confirm outbound template send works once approved templates are live.

## 8. Template Readiness

- Submit all Phase 1 utility templates.
- Wait for `APPROVED` status.
- Record approved template names exactly.
- Map approved names in backend callers/integrations.
- Test every approved template once with a real WhatsApp recipient.

## 9. Retry / Send Settings

- Confirm `META_SEND_ENABLED=true`.
- Confirm `META_MOCK_MODE=false` in production.
- Confirm retry settings:
  - `META_SEND_MAX_ATTEMPTS`
  - `META_RETRY_BACKOFF_SECONDS`
- Review logs for repeated `429` or `5xx` failures after test sends.

## 10. Handover

- Share:
  - `.env` variable list
  - API endpoint list
  - `API_EXAMPLES.md`
  - `FRONTEND_INTEGRATION_GUIDE.md`
  - `META_TEMPLATE_SUBMISSIONS.md`
  - `RAILWAY_DEPLOYMENT.md`
  - `TWILIO_DEMO_TESTING.md` only if the client wants the optional backup/demo adapter documented
  - this go-live checklist
- Confirm who owns:
  - Railway
  - Meta app / WABA
  - phone number
  - Razorpay webhook
  - template submission
  - frontend integration
- Confirm the client knows this Phase 1 scope excludes:
  - dashboards
  - loyalty/offers/campaigns
  - AI chatbot
  - analytics platform
  - app/frontend screen implementation

## 11. Demo Safety Reset

- Confirm `WHATSAPP_PROVIDER=meta`.
- Confirm `DEMO_MODE=false`.
- Confirm `META_MOCK_MODE=false`.
- Confirm Twilio webhook is not pointing at the production service unless the client explicitly wants it as a backup adapter later.
- Confirm `/demo` returns disabled in production.

## Final Acceptance

Phase 1 is handover-ready when all of the below are true:

- backend deployed on Railway
- Postgres migration applied
- Meta webhook verified and receiving messages
- live phone verification flow works
- outbound text send works
- outbound approved template send works
- Razorpay webhook updates payment state
- frontend team has payload docs and integration guide
