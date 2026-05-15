from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings, require_internal_api_key
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.security import constant_time_compare, sha256_text
from app.db.models import JourneyEvent, Order, WhatsAppSession
from app.services.tracking import log_journey_event

router = APIRouter(tags=["tracking"])


TRACKED_RESTAURANT_REQUIRED = True
DASHBOARD_AUTH_COOKIE = "palate_dashboard_auth"
LEGACY_STAGES = ("demo", "order")
SCREEN_STAGES = (
    "menu",
    "cart",
    "order_review",
    "bill",
    "payment",
    "feedback",
    "dish_review",
    "captain_pos",
)

STAGE_LABELS = {
    "menu": "Menu",
    "cart": "Cart",
    "order_review": "Order review",
    "bill": "Bill",
    "payment": "Payment",
    "feedback": "Feedback",
    "dish_review": "Dish review",
    "captain_pos": "Captain / POS",
    "demo": "Old demo traffic",
    "order": "Old order-review traffic",
}


def _stage_label(stage: str | None) -> str:
    if not stage:
        return "Unknown"
    return STAGE_LABELS.get(stage, stage.replace("_", " ").title())


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    if len(digits) <= 6:
        return digits
    if digits.startswith("+") and len(digits) > 7:
        return f"{digits[:4]}***{digits[-3:]}"
    return f"{digits[:3]}***{digits[-3:]}"


def _dashboard_secret(settings: Settings) -> str | None:
    if settings.dashboard_password is not None:
        secret = settings.dashboard_password.get_secret_value().strip()
        if secret:
            return secret
    if settings.internal_api_key is not None:
        secret = settings.internal_api_key.get_secret_value().strip()
        if secret:
            return secret
    return None


def _dashboard_auth_token(settings: Settings) -> str | None:
    secret = _dashboard_secret(settings)
    if not secret:
        return None
    pepper = settings.session_token_pepper.get_secret_value() if settings.session_token_pepper is not None else "palate-dashboard"
    return sha256_text(f"{secret}:{pepper}:dashboard")


def _is_dashboard_authenticated(request: Request, settings: Settings) -> bool:
    expected = _dashboard_auth_token(settings)
    if not expected:
        return True
    provided = request.cookies.get(DASHBOARD_AUTH_COOKIE)
    return provided is not None and constant_time_compare(provided, expected)


def _base_event_filter(include_system: bool, include_legacy: bool):
    filters = []
    if not include_system:
        filters.extend([JourneyEvent.restaurant_id.is_not(None), JourneyEvent.event_type != "link_created"])
    if not include_legacy:
        filters.append((JourneyEvent.stage.is_(None)) | (~JourneyEvent.stage.in_(LEGACY_STAGES)))
    if not filters:
        return True
    clause = filters[0]
    for extra in filters[1:]:
        clause = clause & extra
    return clause


def _count(db: Session, event_type: str, *, include_system: bool = False, include_legacy: bool = False) -> int:
    return db.execute(
        select(func.count())
        .select_from(JourneyEvent)
        .where(_base_event_filter(include_system, include_legacy), JourneyEvent.event_type == event_type)
    ).scalar_one()


def _total_count(db: Session, *, include_system: bool = False, include_legacy: bool = False) -> int:
    return db.execute(select(func.count()).select_from(JourneyEvent).where(_base_event_filter(include_system, include_legacy))).scalar_one()


def _group_counts(db: Session, column, *, event_type: str | None = None, include_system: bool = False, include_legacy: bool = False) -> list[dict[str, Any]]:
    statement = select(column, func.count()).select_from(JourneyEvent).where(_base_event_filter(include_system, include_legacy))
    if event_type:
        statement = statement.where(JourneyEvent.event_type == event_type)
    statement = statement.group_by(column).order_by(func.count().desc())
    return [{"key": key or "unknown", "count": count} for key, count in db.execute(statement).all()]


def _count_for_stage(db: Session, stage: str, *, event_type: str, include_system: bool = False, include_legacy: bool = False) -> int:
    return db.execute(
        select(func.count())
        .select_from(JourneyEvent)
        .where(_base_event_filter(include_system, include_legacy), JourneyEvent.stage == stage, JourneyEvent.event_type == event_type)
    ).scalar_one()


def _verified_session_records(db: Session, *, include_legacy: bool, show_full_phones: bool) -> list[dict[str, Any]]:
    statement = select(WhatsAppSession).where(WhatsAppSession.verified_at.is_not(None))
    if not include_legacy:
        statement = statement.where(WhatsAppSession.entry_point != "demo")
    sessions = list(db.execute(statement.order_by(WhatsAppSession.verified_at.desc())).scalars())
    records: list[dict[str, Any]] = []
    for session in sessions:
        order_reference = None
        if session.order is not None:
            order_reference = session.order.external_order_id or str(session.order.id)
        records.append(
            {
                "session_id": str(session.id),
                "stage": session.entry_point,
                "stage_label": _stage_label(session.entry_point),
                "phone": session.phone_e164 if show_full_phones else _mask_phone(session.phone_e164),
                "raw_phone": session.phone_e164,
                "customer_name": session.provided_name,
                "restaurant_id": session.restaurant_id,
                "restaurant_name": session.restaurant_name,
                "order_reference": order_reference,
                "verified_at": session.verified_at.isoformat() if session.verified_at else None,
            }
        )
    return records


def _phone_rollup(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        phone_key = record["raw_phone"] or f"session:{record['session_id']}"
        if phone_key not in grouped:
            grouped[phone_key] = {
                "phone": record["phone"] or "unknown",
                "customer_name": record["customer_name"] or "Unknown",
                "verification_count": 0,
                "last_stage": record["stage"],
                "last_stage_label": record["stage_label"],
                "last_verified_at": record["verified_at"],
                "latest_order_reference": record["order_reference"],
            }
        grouped[phone_key]["verification_count"] += 1
        grouped[phone_key]["customer_name"] = record["customer_name"] or grouped[phone_key]["customer_name"]
        grouped[phone_key]["last_stage"] = record["stage"]
        grouped[phone_key]["last_stage_label"] = record["stage_label"]
        grouped[phone_key]["last_verified_at"] = record["verified_at"]
        grouped[phone_key]["latest_order_reference"] = record["order_reference"] or grouped[phone_key]["latest_order_reference"]
    return list(grouped.values())


def _screen_funnel(db: Session, *, include_system: bool = False, include_legacy: bool = False) -> list[dict[str, Any]]:
    verified_records = _verified_session_records(db, include_legacy=include_legacy, show_full_phones=False)
    by_stage: dict[str, dict[str, Any]] = defaultdict(lambda: {"phones": set(), "last_verified_at": None})
    for record in verified_records:
        stage = record["stage"] or "unknown"
        if record["raw_phone"]:
            by_stage[stage]["phones"].add(record["raw_phone"])
        if by_stage[stage]["last_verified_at"] is None:
            by_stage[stage]["last_verified_at"] = record["verified_at"]

    rows: list[dict[str, Any]] = []
    for stage in SCREEN_STAGES:
        linked = _count_for_stage(db, stage, event_type="session_started", include_system=include_system, include_legacy=include_legacy)
        verified = _count_for_stage(db, stage, event_type="session_verified", include_system=include_system, include_legacy=include_legacy)
        messages = _count_for_stage(db, stage, event_type="message_sent", include_system=include_system, include_legacy=include_legacy)
        redirects = _count_for_stage(db, stage, event_type="link_clicked", include_system=include_system, include_legacy=include_legacy)
        payments = _count_for_stage(db, stage, event_type="payment_confirmed", include_system=include_system, include_legacy=include_legacy)
        if not any([linked, verified, messages, redirects, payments]):
            continue
        rows.append(
            {
                "stage": stage,
                "stage_label": _stage_label(stage),
                "linked_sessions": linked,
                "verified_sessions": verified,
                "unique_verified_phones": len(by_stage[stage]["phones"]),
                "verification_rate": round((verified / linked) * 100, 2) if linked else 0,
                "messages_sent": messages,
                "redirect_hits": redirects,
                "payments_confirmed": payments,
                "last_verified_at": by_stage[stage]["last_verified_at"],
            }
        )
    return rows


def _recent_events(db: Session, limit: int = 25, *, include_system: bool = False, include_legacy: bool = False) -> list[JourneyEvent]:
    return list(
        db.execute(
            select(JourneyEvent)
            .where(_base_event_filter(include_system, include_legacy))
            .order_by(JourneyEvent.created_at.desc())
            .limit(limit)
        ).scalars()
    )


def _is_safe_redirect_target(target: str) -> bool:
    if target.startswith("/"):
        return not target.startswith("//")
    parsed = urlparse(target)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _require_dashboard_access(request: Request, settings: Settings) -> None:
    if _is_dashboard_authenticated(request, settings):
        return
    raise AppError(status.HTTP_401_UNAUTHORIZED, "dashboard_login_required", "Dashboard login required")


def _dashboard_login_html(error_message: str | None = None) -> str:
    error_block = f'<p style="color:#b42318;margin:0 0 14px;">{error_message}</p>' if error_message else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Palate Dashboard Login</title>
  <style>
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: linear-gradient(135deg, #123847, #1c566a 60%, #e7efe6); font-family: "Segoe UI", sans-serif; }}
    .card {{ width: min(420px, calc(100vw - 32px)); background: rgba(255,255,255,0.96); border-radius: 20px; padding: 28px; box-shadow: 0 30px 60px rgba(10,20,30,0.24); }}
    h1 {{ margin: 0 0 8px; font-size: 30px; color: #102a43; }}
    p {{ margin: 0 0 18px; color: #52606d; line-height: 1.5; }}
    label {{ display:block; margin: 0 0 8px; font-weight: 600; color: #243b53; }}
    input {{ width: 100%; padding: 14px 15px; border-radius: 12px; border: 1px solid #cbd2d9; font-size: 16px; box-sizing: border-box; margin-bottom: 16px; }}
    button {{ width: 100%; padding: 14px 15px; border: 0; border-radius: 999px; background: #db8b52; color: #102a43; font-weight: 700; font-size: 16px; cursor: pointer; }}
    button:hover {{ filter: brightness(0.98); }}
  </style>
</head>
<body>
  <form class="card" method="post" action="/dashboard/login">
    <h1>Palate Dashboard</h1>
    <p>Sign in to view full phone numbers and operational tracking.</p>
    {error_block}
    <label for="password">Password</label>
    <input id="password" name="password" type="password" autocomplete="current-password" required />
    <button type="submit">Open dashboard</button>
  </form>
</body>
</html>"""


@router.get("/t")
@router.get("/r")
def track_redirect(
    request: Request,
    target: str,
    stage: str | None = None,
    action: str | None = None,
    restaurant_id: str | None = None,
    order_id: UUID | None = None,
    session_id: UUID | None = None,
    message_log_id: UUID | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not _is_safe_redirect_target(target):
        raise AppError(422, "target_url_invalid", "Tracked redirect target must be an absolute URL or app path")
    log_journey_event(
        db,
        event_type="link_clicked",
        stage=stage,
        action=action,
        restaurant_id=restaurant_id,
        order_id=order_id,
        session_id=session_id,
        message_log_id=message_log_id,
        target_url=target,
        request=request,
    )
    db.commit()
    return RedirectResponse(url=target, status_code=307)


@router.get("/r/{link_id}")
def track_short_redirect(
    link_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    link_event = db.get(JourneyEvent, link_id)
    if link_event is None or link_event.event_type != "link_created" or not link_event.target_url:
        raise AppError(404, "tracked_link_not_found", "Tracked link not found")
    if not _is_safe_redirect_target(link_event.target_url):
        raise AppError(422, "target_url_invalid", "Tracked redirect target must be an absolute URL or app path")
    log_journey_event(
        db,
        event_type="link_clicked",
        stage=link_event.stage,
        action=link_event.action,
        restaurant_id=link_event.restaurant_id,
        order_id=link_event.order_id,
        session_id=link_event.session_id,
        message_log_id=link_event.message_log_id,
        target_url=link_event.target_url,
        request=request,
        metadata={"tracked_link_id": str(link_event.id)},
    )
    db.commit()
    return RedirectResponse(url=link_event.target_url, status_code=307)


def build_tracking_summary(
    db: Session,
    *,
    include_system: bool,
    include_legacy: bool,
    show_full_phones: bool,
) -> dict[str, Any]:
    sessions_started = _count(db, "session_started", include_system=include_system, include_legacy=include_legacy)
    sessions_verified = _count(db, "session_verified", include_system=include_system, include_legacy=include_legacy)
    link_clicks = _count(db, "link_clicked", include_system=include_system, include_legacy=include_legacy)
    messages_sent = _count(db, "message_sent", include_system=include_system, include_legacy=include_legacy)
    payments_confirmed = _count(db, "payment_confirmed", include_system=include_system, include_legacy=include_legacy)
    payment_link_clicks = _count_for_stage(db, "payment", event_type="link_clicked", include_system=include_system, include_legacy=include_legacy)
    feedback_link_clicks = _count_for_stage(db, "feedback", event_type="link_clicked", include_system=include_system, include_legacy=include_legacy)
    dish_review_clicks = _count_for_stage(db, "dish_review", event_type="link_clicked", include_system=include_system, include_legacy=include_legacy)
    visible_events = _total_count(db, include_system=include_system, include_legacy=include_legacy)
    raw_events = _total_count(db, include_system=True)
    verification_rate = round((sessions_verified / sessions_started) * 100, 2) if sessions_started else 0
    verified_records = _verified_session_records(db, include_legacy=include_legacy, show_full_phones=show_full_phones)
    phone_rollup = _phone_rollup(verified_records)
    unique_verified_phones = len(phone_rollup)
    return {
        "window": "all_time",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "restaurant_events" if not include_system else "all_events",
        "sessions_started": sessions_started,
        "sessions_verified": sessions_verified,
        "unique_verified_phones": unique_verified_phones,
        "verification_rate": verification_rate,
        "tracked_redirect_hits": link_clicks,
        "link_clicks": link_clicks,
        "messages_sent": messages_sent,
        "payments_confirmed": payments_confirmed,
        "payment_link_clicks": payment_link_clicks,
        "feedback_link_clicks": feedback_link_clicks,
        "dish_review_clicks": dish_review_clicks,
        "visible_events": visible_events,
        "raw_events": raw_events,
        "include_legacy": include_legacy,
        "show_full_phones": show_full_phones,
        "hidden_system_events": max(raw_events - visible_events, 0),
        "by_stage": _group_counts(db, JourneyEvent.stage, include_system=include_system, include_legacy=include_legacy),
        "by_action": _group_counts(db, JourneyEvent.action, include_system=include_system, include_legacy=include_legacy),
        "screen_funnel": _screen_funnel(db, include_system=include_system, include_legacy=include_legacy),
        "recent_verifications": verified_records[:20],
        "phone_rollup": phone_rollup[:20],
        "link_clicks_by_stage": _group_counts(db, JourneyEvent.stage, event_type="link_clicked", include_system=include_system, include_legacy=include_legacy),
        "recent_events": [
            {
                "event_type": event.event_type,
                "stage": event.stage,
                "action": event.action,
                "restaurant_id": event.restaurant_id,
                "order_id": str(event.order_id) if event.order_id else None,
                "session_id": str(event.session_id) if event.session_id else None,
                "target_url": event.target_url,
                "created_at": event.created_at.isoformat(),
            }
            for event in _recent_events(db, include_system=include_system, include_legacy=include_legacy)
        ],
    }


@router.get(
    "/api/v1/tracking/summary",
    dependencies=[Depends(require_internal_api_key)],
)
def tracking_summary(db: Session = Depends(get_db), include_system: bool = False, include_legacy: bool = False) -> dict[str, Any]:
    return build_tracking_summary(
        db,
        include_system=include_system,
        include_legacy=include_legacy,
        show_full_phones=False,
    )


@router.get("/dashboard/basic/data")
def tracking_dashboard_data(
    request: Request,
    include_system: bool = False,
    include_legacy: bool = False,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    _require_dashboard_access(request, settings)
    return build_tracking_summary(
        db,
        include_system=include_system,
        include_legacy=include_legacy,
        show_full_phones=True,
    )


@router.get("/dashboard/login", response_class=HTMLResponse)
def dashboard_login_page(request: Request, settings: Settings = Depends(get_settings)) -> Response:
    if _is_dashboard_authenticated(request, settings):
        return RedirectResponse(url="/dashboard/basic", status_code=303)
    return HTMLResponse(_dashboard_login_html())


@router.post("/dashboard/login")
def dashboard_login_submit(
    request: Request,
    response: Response,
    password: str = Form(...),
    settings: Settings = Depends(get_settings),
) -> Response:
    expected = _dashboard_secret(settings)
    if not expected:
        return RedirectResponse(url="/dashboard/basic", status_code=303)
    if not constant_time_compare(password, expected):
        return HTMLResponse(_dashboard_login_html("Incorrect password."), status_code=401)
    redirect = RedirectResponse(url="/dashboard/basic", status_code=303)
    redirect.set_cookie(
        DASHBOARD_AUTH_COOKIE,
        _dashboard_auth_token(settings),
        httponly=True,
        secure=settings.environment.lower() == "production",
        samesite="lax",
        max_age=60 * 60 * 12,
    )
    return redirect


@router.post("/dashboard/logout")
def dashboard_logout() -> Response:
    redirect = RedirectResponse(url="/dashboard/login", status_code=303)
    redirect.delete_cookie(DASHBOARD_AUTH_COOKIE)
    return redirect


@router.get(
    "/tracking/dashboard",
    response_class=HTMLResponse,
)
@router.get("/dashboard/basic", response_class=HTMLResponse)
def tracking_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    if not _is_dashboard_authenticated(request, settings):
        return RedirectResponse(url="/dashboard/login", status_code=303)
    return HTMLResponse(
        """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Palate Basic Tracking</title>
  <style>
    body { margin: 0; font-family: "Segoe UI", sans-serif; background: #f6f7f8; color: #172026; }
    body:before { content: ""; position: fixed; inset: 0; pointer-events: none; background: radial-gradient(circle at 10% 0%, rgba(219,139,82,0.16), transparent 32%), radial-gradient(circle at 92% 8%, rgba(18,56,71,0.18), transparent 34%); }
    .shell { position: relative; max-width: 1280px; margin: 0 auto; padding: 28px 18px 48px; }
    .top { display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; margin-bottom: 18px; }
    h1 { margin: 0 0 6px; font-size: 34px; }
    .lede, .small { margin: 0; color: #667085; line-height: 1.45; }
    .grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin-bottom: 18px; }
    .card { background: rgba(255,255,255,0.92); border: 1px solid #e5e7eb; border-radius: 18px; padding: 18px; box-shadow: 0 18px 44px rgba(16,24,40,0.07); backdrop-filter: blur(10px); }
    .metric span { display: block; color: #6b7280; font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; }
    .metric strong { display: block; margin-top: 8px; font-size: 30px; }
    .tables { display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 18px; }
    .tables.two { grid-template-columns: 1fr 1fr; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { text-align: left; border-bottom: 1px solid #edf0f2; padding: 10px 8px; vertical-align: top; }
    th { color: #6b7280; font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; }
    .wide { margin-top: 18px; }
    .badge { display: inline-flex; border-radius: 999px; padding: 8px 11px; background: #ecfdf3; color: #067647; font-weight: 700; font-size: 13px; }
    .muted { color: #667085; }
    .toolbar { display: flex; flex-direction: column; gap: 8px; align-items: flex-end; }
    .toolbar form { margin: 0; }
    button { border: 1px solid #d0d5dd; background: white; border-radius: 999px; padding: 9px 13px; font-weight: 700; cursor: pointer; }
    button:hover { background: #f9fafb; }
    label { font-size: 13px; color: #475467; display: flex; gap: 8px; align-items: center; }
    .callout { margin-bottom: 18px; background: #102a43; border: 1px solid #24485f; border-radius: 18px; padding: 16px 18px; color: #f7f7f2; box-shadow: 0 18px 40px rgba(16,42,67,0.16); }
    .section-copy { margin: 0 0 12px; color: #667085; font-size: 14px; line-height: 1.5; }
    .status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 999px; background: #12b76a; margin-right: 8px; }
    @media (max-width: 980px) { .grid, .tables, .tables.two { grid-template-columns: 1fr; } .top { flex-direction: column; } .toolbar { align-items: flex-start; } }
  </style>
</head>
<body>
  <main class="shell">
    <section class="top">
      <div>
        <h1>Palate Basic Tracking</h1>
        <p class="lede">Phase 1 operational view. Counts update automatically every 4 seconds.</p>
        <p class="small">This page defaults to real operational traffic only. Full phone numbers are visible because this dashboard now requires sign-in.</p>
      </div>
      <div class="toolbar">
        <span class="badge" id="live-badge">Live polling</span>
        <button id="refresh-now">Refresh now</button>
        <label><input id="include-system" type="checkbox" /> include system/test events</label>
        <label><input id="include-legacy" type="checkbox" /> include old demo/debug traffic</label>
        <form method="post" action="/dashboard/logout"><button type="submit">Log out</button></form>
        <span class="small" id="updated-at">Waiting for first refresh...</span>
      </div>
    </section>
    <section class="callout">
      <strong>Read this first:</strong> Linked sessions means WhatsApp verification links created. Verified sessions means successful WhatsApp token matches. Unique phones means distinct verified phone numbers. Old demo/debug traffic is hidden unless you turn it on.
    </section>
    <section class="grid">
      <div class="card metric"><span>Linked sessions</span><strong id="sessions-started">0</strong></div>
      <div class="card metric"><span>Verified sessions</span><strong id="sessions-verified">0</strong></div>
      <div class="card metric"><span>Unique phones</span><strong id="unique-verified-phones">0</strong></div>
      <div class="card metric"><span>Verify rate</span><strong id="verification-rate">0%</strong></div>
      <div class="card metric"><span>Messages sent</span><strong id="messages-sent">0</strong></div>
    </section>
    <section class="tables">
      <div class="card">
        <h2>Verification by screen</h2>
        <p class="section-copy">This shows where customers started verification and how many actually verified from that screen.</p>
        <table><thead><tr><th>Screen</th><th>Links created</th><th>Verified sessions</th><th>Unique phones</th><th>Rate</th></tr></thead><tbody id="screen-funnel"></tbody></table>
      </div>
      <div class="card">
        <h2>What people did</h2>
        <p class="section-copy">These are the most common customer and system actions recorded so far.</p>
        <table><thead><tr><th>Action</th><th>Count</th></tr></thead><tbody id="by-action"></tbody></table>
      </div>
    </section>
    <section class="tables two wide">
      <div class="card">
        <h2>Verified phones</h2>
        <p class="section-copy">This answers who verified, where, and how many times. Full phone numbers are shown only to signed-in users.</p>
        <table><thead><tr><th>Name</th><th>Phone</th><th>Last screen</th><th>Times verified</th><th>Last order</th><th>Last seen</th></tr></thead><tbody id="phone-rollup"></tbody></table>
      </div>
      <div class="card">
        <h2>Latest verifications</h2>
        <p class="section-copy">Most recent successful WhatsApp identity matches.</p>
        <table><thead><tr><th>Time</th><th>Name</th><th>Phone</th><th>Screen</th><th>Order</th></tr></thead><tbody id="recent-verifications"></tbody></table>
      </div>
    </section>
    <section class="card wide">
      <h2>Latest activity log</h2>
      <p class="small" id="scope-note"></p>
      <table><thead><tr><th>Time</th><th>What happened</th><th>Screen</th><th>Action</th><th>Restaurant</th></tr></thead><tbody id="recent-events"></tbody></table>
    </section>
  </main>
  <script>
    const ids = {
      sessions_started: "sessions-started",
      sessions_verified: "sessions-verified",
      unique_verified_phones: "unique-verified-phones",
      verification_rate: "verification-rate",
      messages_sent: "messages-sent",
    };
    const $ = (id) => document.getElementById(id);
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    }[char]));
    function rows(items) {
      if (!items.length) return "<tr><td class='muted'>No data yet</td><td>0</td></tr>";
      return items.map((item) => `<tr><td>${escapeHtml(item.key.replaceAll("_", " "))}</td><td>${item.count}</td></tr>`).join("");
    }
    function funnelRows(items) {
      if (!items.length) return "<tr><td class='muted' colspan='5'>No screen conversion data yet</td></tr>";
      return items.map((item) => `<tr><td>${escapeHtml(item.stage_label)}</td><td>${item.linked_sessions}</td><td>${item.verified_sessions}</td><td>${item.unique_verified_phones}</td><td>${item.verification_rate}%</td></tr>`).join("");
    }
    function phoneRows(items) {
      if (!items.length) return "<tr><td class='muted' colspan='6'>No verified phones yet</td></tr>";
      return items.map((item) => `<tr><td>${escapeHtml(item.customer_name || "Unknown")}</td><td>${escapeHtml(item.phone || "unknown")}</td><td>${escapeHtml(item.last_stage_label || "Unknown")}</td><td>${item.verification_count}</td><td>${escapeHtml(item.latest_order_reference || "-")}</td><td>${escapeHtml(item.last_verified_at ? new Date(item.last_verified_at).toLocaleString() : "-")}</td></tr>`).join("");
    }
    function verificationRows(items) {
      if (!items.length) return "<tr><td class='muted' colspan='5'>No successful verifications yet</td></tr>";
      return items.map((item) => `<tr><td>${escapeHtml(item.verified_at ? new Date(item.verified_at).toLocaleString() : "-")}</td><td>${escapeHtml(item.customer_name || "Unknown")}</td><td>${escapeHtml(item.phone || "unknown")}</td><td>${escapeHtml(item.stage_label || "Unknown")}</td><td>${escapeHtml(item.order_reference || "-")}</td></tr>`).join("");
    }
    function eventRows(items) {
      if (!items.length) return "<tr><td class='muted' colspan='5'>No journey events yet</td></tr>";
      return items.map((event) => `<tr><td>${escapeHtml(new Date(event.created_at).toLocaleString())}</td><td>${escapeHtml(event.event_type.replaceAll("_", " "))}</td><td>${escapeHtml((event.stage || "").replaceAll("_", " "))}</td><td>${escapeHtml((event.action || "").replaceAll("_", " "))}</td><td>${escapeHtml(event.restaurant_id)}</td></tr>`).join("");
    }
    async function refreshDashboard() {
      const includeSystem = $("include-system").checked ? "true" : "false";
      const includeLegacy = $("include-legacy").checked ? "true" : "false";
      const response = await fetch(`/dashboard/basic/data?include_system=${includeSystem}&include_legacy=${includeLegacy}`, { cache: "no-store" });
      if (response.status === 401) {
        window.location.href = "/dashboard/login";
        return;
      }
      if (!response.ok) throw new Error(`Refresh failed: ${response.status}`);
      const summary = await response.json();
      for (const [key, id] of Object.entries(ids)) {
        $(id).textContent = key === "verification_rate" ? `${summary[key]}%` : summary[key];
      }
      $("screen-funnel").innerHTML = funnelRows(summary.screen_funnel || []);
      $("by-action").innerHTML = rows(summary.by_action);
      $("phone-rollup").innerHTML = phoneRows(summary.phone_rollup || []);
      $("recent-verifications").innerHTML = verificationRows(summary.recent_verifications || []);
      $("recent-events").innerHTML = eventRows(summary.recent_events);
      $("updated-at").textContent = `Last updated ${new Date(summary.updated_at).toLocaleTimeString()}`;
      $("scope-note").textContent = summary.hidden_system_events > 0 && !summary.scope.includes("all")
        ? `${summary.hidden_system_events} system/test event(s) hidden. Toggle include system/test events to inspect raw totals.`
        : `Showing ${summary.scope.replace("_", " ")}${summary.include_legacy ? " with old demo/debug traffic included." : " with old demo/debug traffic hidden."}`;
    }
    $("refresh-now").addEventListener("click", refreshDashboard);
    $("include-system").addEventListener("change", refreshDashboard);
    $("include-legacy").addEventListener("change", refreshDashboard);
    refreshDashboard().catch((error) => { $("updated-at").textContent = error.message; });
    setInterval(() => refreshDashboard().catch(() => {}), 4000);
  </script>
</body>
</html>"""
    )
