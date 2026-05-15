# Palate WhatsApp Phase 1 - Handover Ready Status

## Current Production-Test Backend

- Base URL: `https://palate-whatsapp-api-production.up.railway.app`
- Health: `GET /health`
- Readiness: `GET /ready`
- Dashboard: `GET /dashboard/basic`
- Twilio webhook: `POST /webhooks/twilio/whatsapp`
- Meta webhook: `GET|POST /webhooks/meta/whatsapp`
- Razorpay webhook: `POST /webhooks/payments/razorpay`

## Current Phase 1 Scope

This handover is the core WhatsApp integration foundation:

- WhatsApp session-link creation
- user-initiated token verification
- verified WhatsApp sender phone capture
- customer/session/restaurant/order mapping
- welcome/menu WhatsApp message after verification
- internal API-key protected private endpoints
- Meta, Twilio, Razorpay webhook guards
- basic operational dashboard
- Docker deployment package for Railway or AWS

## Not Included In Phase 1

These are intentionally outside the current handover:

- campaign automation
- automated reminder sequences
- diet preference branching and memory
- rewards automation
- ranking automation
- app-download tracking and suppression
- A/B testing
- full admin/vendor dashboard
- loyalty/offers/AI chatbot systems

## Deployment Model

The backend and dashboard are served by the same FastAPI container. Palate can host it on:

- AWS ECS Fargate + RDS PostgreSQL
- AWS App Runner + RDS PostgreSQL
- Railway + Railway PostgreSQL

The Docker entrypoint runs `alembic upgrade head` before starting the API.

## Verification Completed

- Local tests: `python -m pytest tests/test_app.py tests/test_preflight.py -q`
- Result: `23 passed`
- Live `/health`: passing
- Live `/ready`: passing with database OK and no missing settings
- Live private route guard: returns `401` without `X-API-Key`
- Live session-link smoke: returns session id, expiry, and WhatsApp token URL
- Railway logs: container starts, Alembic uses PostgreSQL, API boots successfully

## Current Railway Mode

The current Railway backend is configured for Twilio provider testing:

- `WHATSAPP_PROVIDER=twilio`
- `DEMO_MODE=false`

For Palate-owned Meta Cloud API production, set:

```text
WHATSAPP_PROVIDER=meta
DEMO_MODE=false
META_MOCK_MODE=false
META_SEND_ENABLED=true
```

and configure the Meta credentials listed in `RAILWAY_DEPLOYMENT.md`.
