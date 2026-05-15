# Meta Template Submissions

This document contains the recommended naming conventions and sample template definitions for Palate Phase 1 WhatsApp template submission.

These recommendations are based on current official Meta documentation for [template overview](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/overview) and [template components](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/components/).

## Naming Conventions

Use these rules for template names:

- lowercase only
- alphanumeric characters and underscores only
- stable, descriptive names
- version suffix at the end
- avoid business-specific copy in the name

Recommended format:

```text
palate_<use_case>_v1
```

Examples:

- `palate_order_summary_v1`
- `palate_bill_payment_link_v1`
- `palate_payment_success_v1`
- `palate_payment_failed_v1`
- `palate_feedback_link_v1`
- `palate_return_to_app_v1`

## Category Guidance

For this Phase 1 scope, all six templates should be submitted as:

```text
UTILITY
```

Reason:

- order updates
- bill/payment follow-up
- payment state communication
- feedback after a transaction
- return-to-app continuation linked to an active order journey

## Parameter Strategy

Use named parameters where possible for maintainability.

Suggested language:

```text
en_US
```

## Submission Pack

### 1. Order Summary

Recommended name:

```text
palate_order_summary_v1
```

Category:

```text
UTILITY
```

Sample create payload:

```json
{
  "name": "palate_order_summary_v1",
  "language": "en_US",
  "category": "UTILITY",
  "parameter_format": "named",
  "components": [
    {
      "type": "BODY",
      "text": "Hi {{customer_name}}, your order {{order_number}} at {{restaurant_name}} is ready on Palate. Total: {{total_amount}}.",
      "example": {
        "body_text_named_params": [
          {"param_name": "customer_name", "example": "Riya"},
          {"param_name": "order_number", "example": "ORD-1001"},
          {"param_name": "restaurant_name", "example": "Palate Bistro"},
          {"param_name": "total_amount", "example": "INR 850.00"}
        ]
      }
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "View Order",
          "url": "https://app.palate.example/orders/{{1}}",
          "example": ["ORD-1001"]
        }
      ]
    }
  ]
}
```

### 2. Bill / Payment Link

Recommended name:

```text
palate_bill_payment_link_v1
```

Category:

```text
UTILITY
```

Sample create payload:

```json
{
  "name": "palate_bill_payment_link_v1",
  "language": "en_US",
  "category": "UTILITY",
  "parameter_format": "named",
  "components": [
    {
      "type": "BODY",
      "text": "Hi {{customer_name}}, your bill for order {{order_number}} at {{restaurant_name}} is ready. Amount due: {{amount_due}}.",
      "example": {
        "body_text_named_params": [
          {"param_name": "customer_name", "example": "Riya"},
          {"param_name": "order_number", "example": "ORD-1001"},
          {"param_name": "restaurant_name", "example": "Palate Bistro"},
          {"param_name": "amount_due", "example": "INR 850.00"}
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "Use the button below to complete payment."
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "Pay Now",
          "url": "https://pay.palate.example/{{1}}",
          "example": ["ORD-1001"]
        }
      ]
    }
  ]
}
```

### 3. Payment Success

Recommended name:

```text
palate_payment_success_v1
```

Category:

```text
UTILITY
```

Sample create payload:

```json
{
  "name": "palate_payment_success_v1",
  "language": "en_US",
  "category": "UTILITY",
  "parameter_format": "named",
  "components": [
    {
      "type": "BODY",
      "text": "Payment received for order {{order_number}} at {{restaurant_name}}. Paid amount: {{paid_amount}}. Thank you.",
      "example": {
        "body_text_named_params": [
          {"param_name": "order_number", "example": "ORD-1001"},
          {"param_name": "restaurant_name", "example": "Palate Bistro"},
          {"param_name": "paid_amount", "example": "INR 850.00"}
        ]
      }
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "View Order",
          "url": "https://app.palate.example/orders/{{1}}",
          "example": ["ORD-1001"]
        }
      ]
    }
  ]
}
```

### 4. Payment Failed

Recommended name:

```text
palate_payment_failed_v1
```

Category:

```text
UTILITY
```

Sample create payload:

```json
{
  "name": "palate_payment_failed_v1",
  "language": "en_US",
  "category": "UTILITY",
  "parameter_format": "named",
  "components": [
    {
      "type": "BODY",
      "text": "We could not confirm payment for order {{order_number}} at {{restaurant_name}}. Outstanding amount: {{amount_due}}.",
      "example": {
        "body_text_named_params": [
          {"param_name": "order_number", "example": "ORD-1001"},
          {"param_name": "restaurant_name", "example": "Palate Bistro"},
          {"param_name": "amount_due", "example": "INR 850.00"}
        ]
      }
    },
    {
      "type": "FOOTER",
      "text": "You can retry using the payment button."
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "Retry Payment",
          "url": "https://pay.palate.example/{{1}}",
          "example": ["ORD-1001"]
        }
      ]
    }
  ]
}
```

### 5. Feedback Link

Recommended name:

```text
palate_feedback_link_v1
```

Category:

```text
UTILITY
```

Sample create payload:

```json
{
  "name": "palate_feedback_link_v1",
  "language": "en_US",
  "category": "UTILITY",
  "parameter_format": "named",
  "components": [
    {
      "type": "BODY",
      "text": "Thanks for ordering from {{restaurant_name}}. Share feedback for order {{order_number}} when convenient.",
      "example": {
        "body_text_named_params": [
          {"param_name": "restaurant_name", "example": "Palate Bistro"},
          {"param_name": "order_number", "example": "ORD-1001"}
        ]
      }
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "Give Feedback",
          "url": "https://app.palate.example/feedback/{{1}}",
          "example": ["ORD-1001"]
        }
      ]
    }
  ]
}
```

### 6. Return To App

Recommended name:

```text
palate_return_to_app_v1
```

Category:

```text
UTILITY
```

Sample create payload:

```json
{
  "name": "palate_return_to_app_v1",
  "language": "en_US",
  "category": "UTILITY",
  "parameter_format": "named",
  "components": [
    {
      "type": "BODY",
      "text": "Your phone is verified on Palate for {{restaurant_name}}. Tap below to continue your order.",
      "example": {
        "body_text_named_params": [
          {"param_name": "restaurant_name", "example": "Palate Bistro"}
        ]
      }
    },
    {
      "type": "BUTTONS",
      "buttons": [
        {
          "type": "URL",
          "text": "Continue",
          "url": "https://app.palate.example/continue/{{1}}",
          "example": ["checkout-123"]
        }
      ]
    }
  ]
}
```

## Operational Notes

- Create templates first in `en_US`.
- Wait for `APPROVED` status before wiring production sends.
- Keep text factual and transaction-linked to stay within `UTILITY`.
- Use one primary URL button per template for higher approval clarity and better UX.
- If the client wants multilingual rollout later, submit translated variants with the same base name and a different language code.

## Mapping To Backend Helper Keys

- `order_summary` -> `palate_order_summary_v1`
- `bill_payment_link` -> `palate_bill_payment_link_v1`
- `payment_success` -> `palate_payment_success_v1`
- `payment_failed` -> `palate_payment_failed_v1`
- `feedback_link` -> `palate_feedback_link_v1`
- `return_to_app` -> `palate_return_to_app_v1`
