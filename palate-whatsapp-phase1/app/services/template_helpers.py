from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from app.db.models import Order


def _money_text(amount: Decimal | None, currency: str) -> str:
    safe_amount = amount or Decimal("0")
    return f"{currency} {safe_amount:.2f}"


def _text_parameter(value: str) -> dict[str, Any]:
    return {"type": "text", "text": value}


def _body_component(*values: str) -> dict[str, Any]:
    return {
        "type": "body",
        "parameters": [_text_parameter(value) for value in values],
    }


def _url_button_component(url_value: str, index: int = 0) -> dict[str, Any]:
    return {
        "type": "button",
        "sub_type": "url",
        "index": str(index),
        "parameters": [_text_parameter(url_value)],
    }


def build_order_summary_components(order: Order) -> list[dict[str, Any]]:
    components = [
        _body_component(
            order.restaurant_name,
            order.external_order_id or str(order.id),
            _money_text(order.total_amount, order.currency),
        )
    ]
    if order.order_url:
        components.append(_url_button_component(order.order_url))
    return components


def build_bill_payment_link_components(order: Order) -> list[dict[str, Any]]:
    amount_due = (order.total_amount or Decimal("0")) - (order.amount_paid or Decimal("0"))
    components = [
        _body_component(
            order.restaurant_name,
            order.external_order_id or str(order.id),
            _money_text(amount_due, order.currency),
        )
    ]
    if order.payment_url:
        components.append(_url_button_component(order.payment_url))
    return components


def build_payment_success_components(order: Order) -> list[dict[str, Any]]:
    components = [
        _body_component(
            order.restaurant_name,
            order.external_order_id or str(order.id),
            _money_text(order.amount_paid or order.total_amount, order.currency),
        )
    ]
    if order.order_url:
        components.append(_url_button_component(order.order_url))
    return components


def build_payment_failed_components(order: Order) -> list[dict[str, Any]]:
    amount_due = (order.total_amount or Decimal("0")) - (order.amount_paid or Decimal("0"))
    components = [
        _body_component(
            order.restaurant_name,
            order.external_order_id or str(order.id),
            _money_text(amount_due, order.currency),
        )
    ]
    if order.payment_url:
        components.append(_url_button_component(order.payment_url))
    return components


def build_feedback_link_components(order: Order) -> list[dict[str, Any]]:
    components = [
        _body_component(
            order.restaurant_name,
            order.external_order_id or str(order.id),
        )
    ]
    if order.feedback_url:
        components.append(_url_button_component(order.feedback_url))
    return components


def build_return_to_app_components(order: Order) -> list[dict[str, Any]]:
    resume_url = order.order_url or order.menu_url or order.payment_url or order.bill_url
    components = [
        _body_component(
            order.restaurant_name,
            order.external_order_id or str(order.id),
        )
    ]
    if resume_url:
        components.append(_url_button_component(resume_url))
    return components


TEMPLATE_HELPERS: dict[str, Callable[[Order], list[dict[str, Any]]]] = {
    "order_summary": build_order_summary_components,
    "bill_payment_link": build_bill_payment_link_components,
    "payment_success": build_payment_success_components,
    "payment_failed": build_payment_failed_components,
    "feedback_link": build_feedback_link_components,
    "return_to_app": build_return_to_app_components,
}


def build_template_components(helper_key: str, order: Order) -> list[dict[str, Any]]:
    try:
        helper = TEMPLATE_HELPERS[helper_key]
    except KeyError as exc:
        raise ValueError(f"Unknown template helper '{helper_key}'") from exc
    return helper(order)
