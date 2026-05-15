# Railway Deployment

This project is ready for Railway as a Docker-deployed FastAPI service with PostgreSQL.

## Railway Environment Variables

Required:

- `DATABASE_URL`
- `INTERNAL_API_KEY`
- `SESSION_TOKEN_PEPPER`
- `WHATSAPP_PROVIDER`
- `RAZORPAY_WEBHOOK_SECRET`

Required when `WHATSAPP_PROVIDER=meta`:

- `PALATE_WHATSAPP_NUMBER`
- `META_VERIFY_TOKEN`
- `META_APP_SECRET`
- `META_ACCESS_TOKEN`
- `META_PHONE_NUMBER_ID`

Required when `WHATSAPP_PROVIDER=twilio`:

- `PUBLIC_BASE_URL`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_FROM`

Recommended explicit values:

- `APP_NAME=Palate WhatsApp Phase 1`
- `ENVIRONMENT=production`
- `LOG_LEVEL=INFO`
- `WHATSAPP_SESSION_TTL_MINUTES=1440`
- `META_GRAPH_API_VERSION=v25.0`
- `META_TIMEOUT_SECONDS=15`
- `META_SEND_ENABLED=true`
- `META_SEND_MAX_ATTEMPTS=3`
- `META_RETRY_BACKOFF_SECONDS=1.0`
- `DEMO_MODE=false`

Optional:

- `CORS_ALLOW_ORIGINS=https://your-frontend-domain.com`
- `TWILIO_WEBHOOK_AUTH_ENABLED=true`

## Exact Meta Values Needed

### `META_VERIFY_TOKEN`

This is not issued by Meta.
You create it yourself as a long random secret string.

Use the same exact value in:

- Railway env var `META_VERIFY_TOKEN`
- Meta webhook configuration screen when subscribing the callback URL

### `META_APP_SECRET`

From your Meta app settings.

Path:

```text
Meta App Dashboard -> App Settings -> Basic -> App Secret
```

### `META_ACCESS_TOKEN`

Use a production token that can send messages for the business phone number.
Typically this is the system user or business integration token used for WhatsApp Cloud API.

### `META_PHONE_NUMBER_ID`

This is the WhatsApp Business phone number ID, not the visible phone number string.

You get it from:

- Meta WhatsApp Manager
- or Graph API assets for the WABA phone number

### `PALATE_WHATSAPP_NUMBER`

This is the visible business WhatsApp number in E.164 format.

Example:

```text
+919999999999
```

This is used to build the `wa.me` verification link.

## Meta Setup Checklist

1. Create or select the Meta app used for WhatsApp Cloud API.
2. Connect the correct WhatsApp Business Account and phone number.
3. Collect:
   - `META_APP_SECRET`
   - `META_ACCESS_TOKEN`
   - `META_PHONE_NUMBER_ID`
   - visible business number for `PALATE_WHATSAPP_NUMBER`
4. Set webhook callback URL:

```text
https://<your-railway-domain>/webhooks/meta/whatsapp
```

5. Set verify token in Meta to match `META_VERIFY_TOKEN`.
6. Subscribe to WhatsApp message webhooks.

## Railway Deployment Steps

1. Create a PostgreSQL service in Railway.
2. Create a new app service from this folder/repo.
3. Railway will build using `Dockerfile` because `railway.toml` points to it.
4. Add all required environment variables.
5. Deploy the service.
6. Migration:

```text
alembic upgrade head
```

The included Docker `entrypoint.sh` already runs `alembic upgrade head` before starting Uvicorn. Run the command manually only if you are not using the provided Docker entrypoint.

7. Confirm:

- `GET /health` returns `200`
- `GET /ready` returns `200`

8. Configure Meta webhook callback.
9. Configure Razorpay webhook callback:

```text
https://<your-railway-domain>/webhooks/payments/razorpay
```

## Recommended Secrets Guidance

- `INTERNAL_API_KEY`: long random internal-only shared secret
- `SESSION_TOKEN_PEPPER`: long random secret distinct from API key
- `META_VERIFY_TOKEN`: long random secret used only for webhook verification
- `RAZORPAY_WEBHOOK_SECRET`: copied from Razorpay webhook configuration

Do not reuse the same value across these fields.

## Retry Handling Now Implemented

The backend now retries transient WhatsApp send failures for:

- network transport failures
- `429`
- `500`
- `502`
- `503`
- `504`

Config:

- `META_SEND_MAX_ATTEMPTS`
- `META_RETRY_BACKOFF_SECONDS`

This keeps production behavior lean without adding queues or workers in Phase 1.

## Optional Twilio Demo Deploy

If you want a separate Railway demo using Twilio before client Meta credentials are ready:

1. Create a separate Railway service or environment.
2. Set:

```text
WHATSAPP_PROVIDER=twilio
DEMO_MODE=true
PUBLIC_BASE_URL=https://<demo-railway-domain>
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_FROM=...
TWILIO_WEBHOOK_AUTH_ENABLED=true
```

3. Configure Twilio webhook:

```text
https://<demo-railway-domain>/webhooks/twilio/whatsapp
```

4. Use:

```text
https://<demo-railway-domain>/demo
```

See [TWILIO_DEMO_TESTING.md](<C:/Users/G Sai Prakash/Downloads/zrai-lead-oss-main/palate-whatsapp-phase1/TWILIO_DEMO_TESTING.md>) for the full flow.

## AWS Handover Note

For AWS, deploy the same Docker image to ECS Fargate or App Runner and point `DATABASE_URL` to RDS PostgreSQL. Set the same environment variables in AWS Secrets Manager, Parameter Store, or the service environment. The dashboard is served by this FastAPI backend at `/dashboard/basic`; it does not require a separate frontend host.
