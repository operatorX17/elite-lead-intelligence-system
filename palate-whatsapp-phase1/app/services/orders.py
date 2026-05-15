from __future__ import annotations

from decimal import Decimal

from app.db.models import Order, WhatsAppSession
from app.services.copy_utils import display_customer_name, short_restaurant_name
from app.services.first_session_message import compose_first_session_welcome, should_send_first_session_welcome


def _amount_text(amount: Decimal | None, currency: str) -> str:
    if amount is None:
        return f"{currency} 0.00"
    return f"{currency} {amount:.2f}"


def _order_reference(order: Order) -> str:
    return order.external_order_id or str(order.id)


def _items_summary(order: Order) -> str:
    if not order.line_items:
        return "Items will be shared at the restaurant."
    labels: list[str] = []
    for item in order.line_items[:5]:
        name = item.get("name") or item.get("title") or "Item"
        quantity = item.get("quantity") or item.get("qty") or 1
        labels.append(f"{quantity} x {name}")
    return ", ".join(labels)


def _item_lines(order: Order) -> list[str]:
    if not order.line_items:
        return ["Items: will be shared at the restaurant."]
    lines = ["Items:"]
    for item in order.line_items[:5]:
        name = item.get("name") or item.get("title") or "Item"
        quantity = item.get("quantity") or item.get("qty") or 1
        lines.append(f"- {quantity} x {name}")
    return lines


def _amount_due(order: Order) -> Decimal:
    return (order.total_amount or Decimal("0")) - (order.amount_paid or Decimal("0"))


def _dish_review_lines(order: Order) -> list[str]:
    notes = order.notes or {}
    dish_reviews = notes.get("dish_reviews") or []
    if not isinstance(dish_reviews, list):
        return []

    lines: list[str] = []
    for entry in dish_reviews[:4]:
        if not isinstance(entry, dict):
            continue
        dish_name = entry.get("dish_name") or entry.get("name") or "Ordered dish"
        review_url = entry.get("review_url")
        if review_url:
            lines.append(f"Review {dish_name}: {review_url}")
    return lines


def compose_order_summary(order: Order) -> str:
    reference = _order_reference(order)
    parts = [
        f"{order.restaurant_name}: order {reference} is linked on WhatsApp.",
        *_item_lines(order),
        f"Total: {_amount_text(order.total_amount, order.currency)}",
    ]
    if order.order_url:
        parts.append(f"View order: {order.order_url}")
    elif order.menu_url:
        parts.append(f"Browse menu: {order.menu_url}")
    return "\n".join(parts)


def compose_bill_message(order: Order) -> str:
    amount_due = _amount_due(order)
    message = [
        f"{order.restaurant_name}: bill for order {_order_reference(order)}.",
        *_item_lines(order),
        f"Subtotal: {_amount_text(order.subtotal_amount, order.currency)}",
        f"Tax: {_amount_text(order.tax_amount, order.currency)}",
        f"Total: {_amount_text(order.total_amount, order.currency)}",
    ]
    if (order.amount_paid or Decimal("0")) > Decimal("0"):
        message.append(f"Paid already: {_amount_text(order.amount_paid, order.currency)}")
    message.append(f"Amount due: {_amount_text(amount_due, order.currency)}")
    if amount_due > Decimal("0") and order.payment_url:
        message.append(f"Pay now: {order.payment_url}")
    elif order.bill_url:
        message.append(f"View detailed bill: {order.bill_url}")
    return "\n".join(message)


def compose_feedback_message(order: Order) -> str:
    message = [
        f"{order.restaurant_name}: thanks for ordering with us.",
        f"Order: {_order_reference(order)}",
        f"Total: {_amount_text(order.total_amount, order.currency)}",
        "How was your experience?",
    ]
    dish_review_lines = _dish_review_lines(order)
    if dish_review_lines:
        message.append("Rate the dishes you ordered:")
        message.extend(dish_review_lines)
    if order.feedback_url:
        message.append(f"Share feedback: {order.feedback_url}")
    else:
        message.append("Reply here with your feedback when convenient.")
    return "\n".join(message)


def _verified_phone_text(whatsapp_session: WhatsAppSession) -> str:
    return whatsapp_session.phone_e164 or whatsapp_session.provided_phone or "your WhatsApp number"


def _personalized_greeting(whatsapp_session: WhatsAppSession) -> str:
    return f"Hi {display_customer_name(whatsapp_session.provided_name)},"


def _demo_entry_point(whatsapp_session: WhatsAppSession) -> str:
    metadata = whatsapp_session.metadata_json or {}
    return str(metadata.get("entry_point") or whatsapp_session.entry_point or "menu")


def compose_demo_verification_message(order: Order | None, whatsapp_session: WhatsAppSession) -> str:
    entry_point = _demo_entry_point(whatsapp_session)
    intro = f"{_personalized_greeting(whatsapp_session)} your WhatsApp number {_verified_phone_text(whatsapp_session)} is now verified with {short_restaurant_name(whatsapp_session.restaurant_name)}."

    if entry_point == "menu":
        parts = [intro, "You can keep browsing the menu here:"]
        if whatsapp_session.resume_url:
            parts.append(whatsapp_session.resume_url)
        return "\n".join(parts)

    if entry_point == "cart":
        parts = [intro, "Your cart is now linked on WhatsApp."]
        if whatsapp_session.resume_url:
            parts.append(f"Continue with your cart here: {whatsapp_session.resume_url}")
        return "\n".join(parts)

    if entry_point == "order_review":
        parts = [intro, "Your order review is ready."]
        if order is not None:
            parts.append(f"Order reference: {_order_reference(order)}")
        if whatsapp_session.resume_url:
            parts.append(f"Review it here: {whatsapp_session.resume_url}")
        return "\n".join(parts)

    if entry_point == "bill":
        parts = [intro, "Your bill is ready."]
        if order is not None:
            parts.append(f"Amount due: {_amount_text(_amount_due(order), order.currency)}")
        if whatsapp_session.resume_url:
            parts.append(f"Open the bill here: {whatsapp_session.resume_url}")
        return "\n".join(parts)

    if entry_point == "payment":
        parts = [intro, "Your payment step is ready."]
        if order is not None:
            parts.append(f"Amount due: {_amount_text(_amount_due(order), order.currency)}")
        if whatsapp_session.resume_url:
            parts.append(f"Pay here: {whatsapp_session.resume_url}")
        return "\n".join(parts)

    if entry_point == "feedback":
        parts = [intro, "Your feedback page is ready."]
        if whatsapp_session.resume_url:
            parts.append(f"Share feedback here: {whatsapp_session.resume_url}")
        return "\n".join(parts)

    if entry_point == "dish_review":
        parts = [intro, "Your dish review page is ready."]
        if whatsapp_session.resume_url:
            parts.append(f"Review the dish here: {whatsapp_session.resume_url}")
        return "\n".join(parts)

    if entry_point == "captain_pos":
        parts = [intro, "Your order is now linked on WhatsApp."]
        if order is not None:
            parts.append(f"Order reference: {_order_reference(order)}")
        if whatsapp_session.resume_url:
            parts.append(f"Continue here: {whatsapp_session.resume_url}")
        return "\n".join(parts)

    parts = [intro, "We will send your next steps here on WhatsApp."]
    if whatsapp_session.resume_url:
        parts.append(f"Continue here: {whatsapp_session.resume_url}")
    return "\n".join(parts)


def compose_post_verification_message(order: Order | None, whatsapp_session: WhatsAppSession) -> str:
    if order is None and should_send_first_session_welcome(whatsapp_session):
        return compose_first_session_welcome(whatsapp_session)

    if (whatsapp_session.metadata_json or {}).get("demo_mode"):
        return compose_demo_verification_message(order, whatsapp_session)

    if order is None:
        parts = [
            f"{_personalized_greeting(whatsapp_session)} your phone number {_verified_phone_text(whatsapp_session)} is now verified on Palate with {short_restaurant_name(whatsapp_session.restaurant_name)}."
        ]
        parts.append("We will send your next steps here on WhatsApp.")
        if whatsapp_session.resume_url:
            parts.append(f"Continue here: {whatsapp_session.resume_url}")
        return "\n".join(parts)

    parts = [
        f"{_personalized_greeting(whatsapp_session)} your phone number {_verified_phone_text(whatsapp_session)} is now verified with {short_restaurant_name(order.restaurant_name)}.",
        f"Linked order: {_order_reference(order)}",
        f"Items: {_items_summary(order)}",
        f"Total: {_amount_text(order.total_amount, order.currency)}",
        "We will send your bill and updates here on WhatsApp.",
    ]
    if whatsapp_session.resume_url:
        parts.append(f"Continue: {whatsapp_session.resume_url}")
    return "\n".join(parts)


def compose_payment_success_message(order: Order) -> str:
    message = [
        f"{order.restaurant_name}: payment received for order {_order_reference(order)}.",
        f"Paid amount: {_amount_text(order.amount_paid or order.total_amount, order.currency)}",
    ]
    if order.feedback_url:
        message.append(f"Share feedback: {order.feedback_url}")
    elif order.bill_url:
        message.append(f"View bill: {order.bill_url}")
    return "\n".join(message)


def compose_payment_failed_message(order: Order) -> str:
    message = [
        f"{order.restaurant_name}: your payment is still pending for order {_order_reference(order)}.",
        f"Amount due: {_amount_text(_amount_due(order), order.currency)}",
    ]
    if order.payment_url:
        message.append(f"Try again: {order.payment_url}")
    return "\n".join(message)
