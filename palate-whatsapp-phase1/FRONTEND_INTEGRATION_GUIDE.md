# Frontend Integration Guide

This guide is now aligned to the Palate routes and trigger points Rohit shared.

It is intentionally split into:

- what Palate can connect right now
- what stays pending on Palate's side

## Current Palate URLs Confirmed

Development base:

```text
https://development-vendors.palatepower.com
```

Production base today:

```text
https://vendors.palatepower.com
```

Future production host mentioned by Palate:

```text
https://portal.palatepower.com
```

Currently available Palate routes:

- menu: `/menu/[slug]`
- menu example: `/menu/dalchini`
- menu with table: `/menu/dalchini?table=Floor-1-1`
- cart: `/menu/[slug]/cart`
- bill / invoice: `/invoice/{invoice_uuid}`
- per-dish review: RatemyPlate web flow URL

Still pending on Palate side:

- final order review route
- final payment route
- final feedback route
- Razorpay order mapping contract

## What Can Be Integrated Right Now

Use the backend immediately for:

- menu QR landing verification
- cart-page verification before payment
- captain or cashier invoice send on WhatsApp
- per-dish review link send on WhatsApp

Leave these pending until Palate finishes them:

- payment page handoff
- general feedback page
- final order review page
- Razorpay mapping webhook completion

## Backend Contract To Use Now

### 1. Menu screen

When user lands on:

```text
/menu/[slug]
```

show CTA such as:

```text
Get updates on WhatsApp
```

Call:

```text
POST /api/v1/whatsapp/session-link
```

Payload shape:

```json
{
  "restaurant_id": "dalchini_restaurant_id",
  "restaurant_name": "Dalchini",
  "browser_session_id": "browser_session_abc",
  "customer_name": "Sai",
  "entry_point": "menu",
  "intent": "browse_menu",
  "resume_url": "https://development-vendors.palatepower.com/menu/dalchini?table=Floor-1-1"
}
```

Important:

- the backend now wraps `resume_url` in a tracked redirect automatically
- session status and WhatsApp "continue here" will return the tracked link, not the raw Palate URL
- the final destination still remains the Palate menu page

### 2. Cart screen

When user reaches:

```text
/menu/[slug]/cart
```

and Palate wants verification before payment, call:

```text
POST /api/v1/whatsapp/session-link
```

Payload shape:

```json
{
  "restaurant_id": "dalchini_restaurant_id",
  "restaurant_name": "Dalchini",
  "browser_session_id": "browser_session_abc",
  "cart_id": "cart_456",
  "customer_name": "Sai",
  "entry_point": "cart",
  "intent": "verify_before_payment",
  "resume_url": "https://development-vendors.palatepower.com/menu/dalchini/cart"
}
```

Recommended CTA:

```text
Verify on WhatsApp before payment
```

This is the current best fit for Palate because payment is not finished yet but the cart route already exists.

### 3. Bill or invoice flow

When captain or cashier creates invoice:

```text
/invoice/{invoice_uuid}
```

Palate should first create or update the backend order context:

```text
POST /api/v1/captain/orders
```

Send:

- restaurant identifiers
- external order ID
- external customer ID if available
- customer name if available
- invoice URL in `bill_url`
- menu URL if available
- line items
- totals

Then use:

```text
POST /api/v1/orders/{order_id}/send-bill
```

The backend will send the bill message on WhatsApp using the stored invoice URL.

### 4. Per-dish review flow

Palate confirmed per-dish review URLs.

When ordered dishes are known, include:

```json
{
  "dish_reviews": [
    {
      "dish_id": "867",
      "dish_name": "Example Dish",
      "review_url": "https://ratemyplate-dev.palatepower.com/#/webFirstPage?autoCamera=true&mapsPlaceId=ChIJG28QvePpwjsR1sodBwBaoAI&vendorDishId=867"
    }
  ]
}
```

through:

```text
POST /api/v1/captain/orders
```

Then send:

```text
POST /api/v1/orders/{order_id}/send-feedback
```

The backend will include per-dish review links in the WhatsApp feedback message.

## What Palate Still Owns

Palate still owns:

- menu UI
- cart UI
- final order review UI
- invoice UI
- payment UI
- RatemyPlate review experience

This backend only:

- creates verification sessions
- verifies the real WhatsApp sender phone
- stores screen and order context
- returns tracked continue links
- sends WhatsApp messages
- records basic journey events

## Current Recommended CTA Placements

Use these now:

- menu page: `Get updates on WhatsApp`
- cart page: `Verify on WhatsApp before payment`
- invoice page or captain action: `Send bill on WhatsApp`
- post-order dish review: `Rate this dish`

## Current Pending Items

These are not blocked by the backend. They are waiting on Palate product or backend completion:

- exact order review URL format
- final payment URL
- final feedback page URL
- Razorpay mapping details such as `notes.order_id` and `notes.external_order_id`

## Current Integration Sequence

Ship in this order:

1. menu verification
2. cart verification before payment
3. captain or cashier invoice send
4. per-dish review send
5. later plug in payment and general feedback once Palate finishes those pages

That gets the currently available Palate flow live without waiting for unfinished payment work.
