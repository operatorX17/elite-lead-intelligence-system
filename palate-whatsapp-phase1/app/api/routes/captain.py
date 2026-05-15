from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings, require_internal_api_key
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.security import normalize_phone
from app.db.models import Customer, Order, WhatsAppSession
from app.schemas import CaptainOrderCreateRequest, CaptainOrderResponse, SessionLinkResponse
from app.services.session_links import create_session_link_for_context
from app.services.tracking import create_tracked_link

router = APIRouter(prefix="/api/v1/captain", tags=["captain"], dependencies=[Depends(require_internal_api_key)])


def _find_customer(db: Session, request: CaptainOrderCreateRequest) -> Customer | None:
    if request.external_customer_id:
        statement = (
            select(Customer)
            .where(Customer.external_customer_id == request.external_customer_id)
            .order_by(Customer.updated_at.desc(), Customer.created_at.desc())
            .limit(1)
        )
        customer = db.execute(statement).scalar_one_or_none()
        if customer is not None:
            return customer
    if request.customer_phone:
        statement = (
            select(Customer)
            .where(Customer.phone_e164 == normalize_phone(request.customer_phone))
            .order_by(Customer.phone_verified_at.desc(), Customer.updated_at.desc(), Customer.created_at.desc())
            .limit(1)
        )
        customer = db.execute(statement).scalar_one_or_none()
        if customer is not None:
            return customer
    return None


def _build_session_link(order: Order, settings: Settings, db: Session) -> SessionLinkResponse:
    return create_session_link_for_context(
        db,
        settings,
        order=order,
        customer=order.customer,
        restaurant_id=order.restaurant_id,
        restaurant_name=order.restaurant_name,
        customer_name=order.customer.display_name if order.customer else None,
        provided_phone=order.customer.phone_e164 if order.customer else None,
        entry_point="captain_pos",
        intent="link_order",
        resume_url=None,
        metadata={
            "external_order_id": order.external_order_id,
            "external_customer_id": order.customer.external_customer_id if order.customer else None,
            "source": "captain_order",
        },
        expires_in_minutes=settings.whatsapp_session_ttl_minutes,
    )


def _base_url(request: Request, settings: Settings) -> str:
    return settings.public_base_url.rstrip("/") if settings.public_base_url else str(request.base_url).rstrip("/")


def _maybe_track_url(
    db: Session,
    base_url: str,
    target_url: str | None,
    *,
    stage: str,
    action: str,
    order: Order,
) -> str | None:
    if not target_url:
        return None
    if "/r/" in target_url or "/r?" in target_url:
        return target_url
    return create_tracked_link(
        db,
        base_url,
        target_url,
        stage=stage,
        action=action,
        restaurant_id=order.restaurant_id,
        order_id=order.id,
    )


def _apply_tracking_context(
    db: Session,
    request: Request,
    settings: Settings,
    order: Order,
    captain_request: CaptainOrderCreateRequest,
) -> None:
    base_url = _base_url(request, settings)
    order.menu_url = _maybe_track_url(db, base_url, captain_request.menu_url, stage="menu", action="open_menu", order=order)
    order.order_url = _maybe_track_url(db, base_url, captain_request.order_url, stage="order_review", action="view_order_review", order=order)
    order.bill_url = _maybe_track_url(db, base_url, captain_request.bill_url, stage="bill", action="view_bill", order=order)
    order.payment_url = _maybe_track_url(db, base_url, captain_request.payment_url, stage="payment", action="open_payment", order=order)
    order.feedback_url = _maybe_track_url(db, base_url, captain_request.feedback_url, stage="feedback", action="open_feedback", order=order)

    notes = dict(captain_request.notes)
    if captain_request.dish_reviews:
        tracked_reviews: list[dict[str, object]] = []
        for index, item in enumerate(captain_request.dish_reviews, start=1):
            if not isinstance(item, dict):
                continue
            dish_id = str(item.get("dish_id") or f"dish_{index}")
            dish_name = str(item.get("dish_name") or item.get("name") or f"Dish {index}")
            original_review_url = item.get("review_url")
            tracked_reviews.append(
                {
                    **item,
                    "dish_id": dish_id,
                    "dish_name": dish_name,
                    "original_review_url": original_review_url,
                    "review_url": _maybe_track_url(
                        db,
                        base_url,
                        str(original_review_url) if original_review_url else None,
                        stage="dish_review",
                        action=f"review_{dish_id}",
                        order=order,
                    ),
                }
            )
        notes["dish_reviews"] = tracked_reviews
    order.notes = notes


@router.post("/orders", response_model=CaptainOrderResponse)
def create_or_update_order(
    request: CaptainOrderCreateRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CaptainOrderResponse:
    customer = _find_customer(db, request)
    if customer is None and any([request.customer_name, request.customer_phone, request.customer_email, request.external_customer_id]):
        customer = Customer(
            external_customer_id=request.external_customer_id,
            display_name=request.customer_name,
            email=request.customer_email,
            phone_e164=normalize_phone(request.customer_phone),
            onboarding_status="identified",
            onboarding_source="captain",
        )
        db.add(customer)
        db.flush()
    elif customer is not None:
        customer.display_name = request.customer_name or customer.display_name
        customer.email = request.customer_email or customer.email
        customer.phone_e164 = normalize_phone(request.customer_phone) or customer.phone_e164
        customer.onboarding_status = "identified" if customer.phone_verified_at is None else customer.onboarding_status
        customer.onboarding_source = "captain"

    order = None
    if request.external_order_id:
        statement = select(Order).where(Order.external_order_id == request.external_order_id)
        order = db.execute(statement).scalar_one_or_none()

    if order is None:
        order = Order(
            external_order_id=request.external_order_id,
            customer_id=customer.id if customer else None,
            restaurant_id=request.restaurant_id,
            restaurant_name=request.restaurant_name,
            order_status=request.order_status,
            currency=request.currency,
            subtotal_amount=request.subtotal_amount,
            tax_amount=request.tax_amount,
            total_amount=request.total_amount,
            amount_paid=request.amount_paid,
            summary_text=request.summary_text,
            menu_url=request.menu_url,
            order_url=request.order_url,
            bill_url=request.bill_url,
            payment_url=request.payment_url,
            feedback_url=request.feedback_url,
            notes={},
            line_items=request.line_items,
        )
        db.add(order)
        db.flush()
    else:
        order.customer_id = customer.id if customer else order.customer_id
        order.restaurant_id = request.restaurant_id
        order.restaurant_name = request.restaurant_name
        order.order_status = request.order_status
        order.currency = request.currency
        order.subtotal_amount = request.subtotal_amount
        order.tax_amount = request.tax_amount
        order.total_amount = request.total_amount
        order.amount_paid = request.amount_paid
        order.summary_text = request.summary_text
        order.menu_url = request.menu_url
        order.order_url = request.order_url
        order.bill_url = request.bill_url
        order.payment_url = request.payment_url
        order.feedback_url = request.feedback_url
        order.line_items = request.line_items

    _apply_tracking_context(db, http_request, settings, order, request)

    session_link = _build_session_link(order, settings, db) if request.auto_create_session_link else None
    db.commit()

    return CaptainOrderResponse(
        order_id=order.id,
        customer_id=customer.id if customer else None,
        session_link=session_link,
    )
