# Palate Phase 1 Foundation

This backend is now modeled around a simple product truth:

```text
capture identity anywhere
verify before money or completion
prefer WhatsApp for low friction
do not hard-wire the whole system to only one channel
```

## Product Decision

Phase 1 should treat onboarding as a state machine, not a single screen.

Possible entry points:

- landing page
- menu page
- cart page
- order page
- captain/manual order assist
- payment step

At any of those points, Palate can collect:

- name
- optional phone
- restaurant context
- resume URL
- intent such as `browse_menu`, `build_order`, `verify_before_payment`, or `link_order`

Verification can then happen later, before:

- order confirmation
- bill generation
- payment link delivery
- post-order feedback journey

## Recommended Phase 1 Path

Primary path:

```text
frontend collects partial profile
-> backend creates onboarding/verification session
-> customer taps WhatsApp
-> customer sends prefilled message
-> webhook verifies real sender phone
-> backend upgrades customer to verified
-> backend resumes the journey with bill/payment/order/menu links
```

This is the lowest-friction web-compatible path.

## Why This Is Better

- Works from web, captain flow, or app.
- Does not force OTP entry in the normal case.
- Lets users skip identity early and verify later.
- Keeps the verified identity source separate from payment confirmation.
- Leaves room for future fallback channels if WhatsApp deliverability changes.

## What Phase 1 Supports Now

- order-linked WhatsApp verification
- pre-order restaurant-linked verification
- entry-point aware sessions such as `menu`, `cart`, `order`, `payment`, `captain`
- resume URLs so the frontend can continue the journey after verification
- menu/order/bill/payment/feedback links on messages
- verified customer creation even when there was no order at verification time
- session status polling for frontend orchestration

## What Is Deliberately Deferred

- SMS OTP provider integration
- app-native WhatsApp one-tap/zero-tap auth
- retry/queue workers
- automatic multi-step journey orchestration UI
- full customer app screens

## Fallback Strategy

The data model is now channel-agnostic enough to support:

```text
phone_verification_channel = whatsapp | sms | app_auth
```

Only `whatsapp` is implemented in Phase 1.

That means the system can later add:

- SMS OTP fallback if WhatsApp is unavailable
- mobile app one-tap/zero-tap auth
- assisted captain verification workflows

without rebuilding the customer/order/session model.
