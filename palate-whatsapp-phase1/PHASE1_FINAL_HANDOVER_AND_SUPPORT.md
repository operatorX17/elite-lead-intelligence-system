# Palate WhatsApp Phase 1 - Final Handover and Support Notes

## Current Status

The Phase 1 backend is ready for production handover and go-live validation of the agreed WhatsApp onboarding flow.

Current testing backend:

```text
https://palate-whatsapp-api-production.up.railway.app
```

Current basic tracking dashboard:

```text
https://palate-whatsapp-api-production.up.railway.app/dashboard/basic
```

The backend is Docker-based and can be hosted by Palate in its own production environment, such as AWS, with environment variables updated for the production domain, database, WhatsApp provider, and webhook secrets.

## Phase 1 Flow Ready Now

The ready go-live flow is:

```text
QR / landing page
-> Continue with WhatsApp
-> WhatsApp opens with prefilled session token
-> user sends message
-> backend verifies real WhatsApp sender phone
-> backend links phone to session / restaurant / customer context
-> welcome + menu link message is sent
-> short separate follow-up message is sent
-> user continues to Palate menu
```

This supports the current onboarding direction where WhatsApp verification happens before the user continues into the menu experience.

## Current First-Session Messages

User prefilled message:

```text
Start my Palate session and show me <Restaurant>'s menu
Token: <session_token>
```

Backend welcome/menu message:

```text
Hi <Name>, welcome to Palate.
Here is <Restaurant>'s menu. Tap any dish to leave a review:
<menu_url>
```

Separate follow-up message:

```text
One thing that makes us different: you rate the dish, not the restaurant.
Because one place can have a brilliant dal and a forgettable paneer, and you deserve to know which is which.
```

The session token is required for secure backend mapping. The user-facing copy stays simple, while the token protects session verification.

## What Phase 1 Includes

- FastAPI backend for WhatsApp integration.
- Meta Cloud API provider support.
- Twilio WhatsApp provider support for testing or fallback.
- Mock provider for local/smoke testing.
- Secure `PALATE_XXXXXXXX` session token generation.
- Session token hashing with server-side pepper.
- Verified WhatsApp sender phone capture from webhook.
- Customer/session/restaurant/order context mapping.
- WhatsApp welcome/menu message after successful verification.
- Separate first-session follow-up message.
- Dynamic URL support for menu, order, bill, payment, feedback, and dish review links.
- Captain/manual order endpoint foundation.
- Razorpay webhook signature verification and payment event mapping.
- Basic operational dashboard.
- Dockerfile, Railway config, Alembic migrations, and PostgreSQL-ready setup.
- Smoke test and preflight commands for handover validation.

## Order, Payment, and Review Foundation

The backend already has foundation endpoints for future order/payment/review flows.

Palate can send dynamic order context to:

```text
POST /api/v1/captain/orders
```

The payload can include:

```json
{
  "external_order_id": "PAL-1001",
  "external_customer_id": "cust_123",
  "customer_name": "Sai",
  "customer_phone": "+919999999999",
  "restaurant_id": "rest_123",
  "restaurant_name": "Dalchini",
  "order_status": "created",
  "currency": "INR",
  "subtotal_amount": "720.00",
  "tax_amount": "130.00",
  "total_amount": "850.00",
  "amount_paid": "0.00",
  "summary_text": "2 x Truffle Pasta, 1 x Tiramisu",
  "menu_url": "https://development-vendors.palatepower.com/menu/dalchini",
  "bill_url": "https://development-vendors.palatepower.com/invoice/<invoice_id>",
  "payment_url": "https://<payment-link>",
  "feedback_url": "https://<feedback-link>",
  "dish_reviews": [
    {
      "dish_id": "867",
      "dish_name": "Truffle Pasta",
      "review_url": "https://ratemyplate-dev.palatepower.com/#/webFirstPage?autoCamera=true&vendorDishId=867"
    }
  ],
  "line_items": [
    {
      "name": "Truffle Pasta",
      "quantity": 2
    },
    {
      "name": "Tiramisu",
      "quantity": 1
    }
  ],
  "auto_create_session_link": false
}
```

These flows can be tested when the corresponding Palate-side pages, URLs, and data are ready.

## What Is Not Part Of Current Phase 1

The current Phase 1 is the WhatsApp foundation and onboarding flow, not the full long-term WhatsApp automation product.

Not included in current Phase 1:

- Full 24-hour timed automation sequence.
- Branching message journeys.
- Diet preference capture and personalization engine.
- App-download suppression logic.
- Leaderboard/points automation.
- Campaign automation.
- AI chatbot or human handoff system.
- Full analytics product.
- Palate frontend screens.
- Payment gateway implementation inside Palate.
- Review/camera/photo upload implementation inside Palate.
- Loyalty/offers systems.

These can be scoped as Phase 2 once Phase 1 is handed over and stable.

## Recommended Phase 2 Scope

If Palate wants to use the full WhatsApp 24-hour utility window properly, the next phase should be a separate automation layer.

Recommended Phase 2 modules:

- Message sequence scheduler.
- Journey state machine.
- Suppression rules for STOP/unsubscribe/app-download.
- User preference capture.
- App download/status tracking.
- Review completion tracking.
- Dynamic dish recommendation logic.
- Meta template planning for messages outside the service window.
- Expanded analytics and reporting.

This should be scoped separately with clear timeline and commercials because it is a larger product automation layer, not just the base verification integration.

## Go-Live Validation Checklist

Before production go-live, run:

1. Health check:

```text
GET /health
```

2. Readiness check:

```text
GET /ready
```

3. Create a fresh WhatsApp session from Palate page:

```text
POST /api/v1/whatsapp/session-link
```

4. Open returned `wa_url`.

5. Send the prefilled WhatsApp message.

6. Confirm backend marks session verified:

```text
GET /api/v1/whatsapp/sessions/{session_id}
```

7. Confirm response includes:

```json
{
  "is_verified": true,
  "verified_phone": "+91..."
}
```

8. Confirm WhatsApp receives:

```text
welcome/menu link message
separate follow-up message
```

9. Confirm Palate saves verified phone/status in its own customer/session model.

## Deployment Notes

The backend can be run as a standard Docker service.

Build:

```bash
docker build -t palate-whatsapp-phase1 .
```

Run:

```bash
docker run --env-file .env -p 8000:8000 palate-whatsapp-phase1
```

Apply migrations:

```bash
alembic upgrade head
```

Preflight:

```bash
python -m app.preflight --base-url https://<production-backend-domain>
```

Smoke test:

```bash
python scripts/smoke_test_local.py --base-url https://<production-backend-domain> --api-key <api-key>
```

## Required Production Environment Categories

Palate production hosting should configure:

- Database URL for PostgreSQL.
- Internal API key.
- Token pepper.
- Public base URL.
- WhatsApp provider selection.
- Meta Cloud API credentials or Twilio credentials.
- Webhook verification secrets.
- Razorpay webhook secret, if payment webhooks are enabled.
- Dashboard password.

Secrets must be stored in the hosting provider's secret manager or environment variable system. They should not be committed to Git.

## Support After Go-Live

After Phase 1 handover/go-live, support is included for 10 calendar days for the agreed Phase 1 implementation.

Support is limited to the delivered Phase 1 WhatsApp backend scope. It is not an open-ended product, operations, or strategy support arrangement.

Support availability:

```text
Mutually scheduled support slots during the 10-day support period.
```

Support calls should be booked only when needed for Phase 1 setup, testing, bugs, or go-live blockers. Each support call should be limited to 45 minutes unless both sides agree otherwise.

Support effort is capped to reasonable Phase 1 issue resolution and clarification. It is not a daily standing commitment, full-time availability, or open-ended product consultation.

For urgent go-live blockers directly related to the delivered Phase 1 backend, support can be handled on a best-effort basis during the same 10-day period.

Support includes:

- Setup clarification.
- Environment/config review.
- Webhook troubleshooting.
- WhatsApp session verification checks.
- WhatsApp delivery checks for the implemented onboarding flow.
- Fixes for issues directly related to the delivered Phase 1 backend flow.
- Guidance for running preflight/smoke tests.
- Clarification on existing endpoint payloads and expected responses.

Support does not include:

- New feature development.
- Full 24-hour automation buildout.
- Campaign engine.
- AI chatbot.
- Loyalty/offers systems.
- Full analytics dashboard.
- Palate frontend development.
- Payment gateway development inside Palate.
- Review/camera/photo upload development inside Palate.
- Ongoing operational support beyond the support window.
- Daily meetings or open-ended coordination unrelated to Phase 1 backend defects/setup.
- Product redesign, new flow design, or new commercial planning.

Any additional feature work after Phase 1 should be scoped separately before implementation.

## Handover Sequence

Recommended closeout sequence:

1. Phase 1 payment closure.
2. Code/package handover.
3. Environment variable handover checklist.
4. Palate hosts/configures the backend in its production environment.
5. Palate configures production webhooks.
6. Preflight and smoke tests are run.
7. Production WhatsApp onboarding flow is validated.
8. 10-day Phase 1 support window starts.

## Final Phase 1 Definition

Phase 1 is complete when:

- The backend package is handed over.
- Palate can create a WhatsApp session link.
- User can verify through WhatsApp.
- Backend captures the real verified WhatsApp phone.
- Palate can poll/read verification status.
- Welcome/menu message is sent.
- Separate follow-up message is sent.
- Setup/test documentation is provided.

Ordering, payment, review, and long-term automation are supported at the backend foundation level, but final production testing depends on Palate-side URLs, screens, and business rules being ready.
