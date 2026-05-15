# Palate Current Integration Status

This document is the exact "what can we connect now" status based on Rohit's reply.

## Ready To Connect Now

These flows can be integrated and tested immediately:

- menu QR landing verification
- cart verification before payment
- captain or cashier invoice send on WhatsApp
- per-dish review links back into RatemyPlate web flow

## Palate Routes Confirmed

Development base:

```text
https://development-vendors.palatepower.com
```

Production base:

```text
https://vendors.palatepower.com
```

Future production host mentioned by Palate:

```text
https://portal.palatepower.com
```

Confirmed route patterns:

- menu: `/menu/[slug]`
- menu example: `/menu/dalchini`
- menu example with table: `/menu/dalchini?table=Floor-1-1`
- cart: `/menu/[slug]/cart`
- invoice: `/invoice/{invoice_uuid}`
- per-dish review: RatemyPlate web review URL

## Recommended Current CTA Placement

Use these now:

- menu page: `Get updates on WhatsApp`
- cart page: `Verify on WhatsApp before payment`
- invoice action from captain or cashier: `Send bill on WhatsApp`
- post-order dish review prompt: `Rate this dish`

## Backend Features Already Supporting This

The backend already supports:

- `POST /api/v1/whatsapp/session-link`
- `GET /api/v1/whatsapp/sessions/{session_id}`
- `POST /api/v1/captain/orders`
- `POST /api/v1/orders/{order_id}/send-bill`
- `POST /api/v1/orders/{order_id}/send-feedback`

It also now wraps session `resume_url` values into tracked redirect links, so menu and cart continuation clicks are measurable.

## Still Pending On Palate Side

These are not backend blockers. They are not available yet from Palate:

- final order review route
- final payment route
- final feedback route
- Razorpay mapping details

## Best Current Integration Order

1. menu verification
2. cart verification before payment
3. invoice send
4. per-dish review send
5. later connect payment and general feedback when Palate completes them

That gets the present live subset working without waiting for unfinished payment work.
