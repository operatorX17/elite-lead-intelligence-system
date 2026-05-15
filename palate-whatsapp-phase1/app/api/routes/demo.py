from __future__ import annotations

import io
import secrets
from datetime import timezone
from decimal import Decimal
from uuid import UUID

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_settings
from app.core.config import Settings
from app.core.exceptions import AppError
from app.db.base import utcnow
from app.db.models import Order, WhatsAppSession
from app.schemas import SessionStatusResponse
from app.services.dispatch import resolve_target, send_text_and_log
from app.services.orders import (
    compose_bill_message,
    compose_feedback_message,
    compose_order_summary,
    compose_payment_success_message,
)
from app.services.session_links import create_session_link_for_context
from app.services.tracking import create_tracked_link, log_journey_event, log_session_started

router = APIRouter(tags=["demo"])

DEMO_ENTRY_POINTS = (
    "menu",
    "cart",
    "order_review",
    "bill",
    "payment",
    "feedback",
    "dish_review",
    "captain_pos",
)


def _ensure_demo_mode(settings: Settings) -> None:
    if not settings.demo_mode:
        raise AppError(404, "demo_mode_disabled", "Demo mode is disabled")


def _base_url(request: Request, settings: Settings) -> str:
    return settings.public_base_url.rstrip("/") if settings.public_base_url else str(request.base_url).rstrip("/")


def _session_action(session_status: str) -> tuple[bool, bool, str, str]:
    if session_status == "verified":
        return True, True, "resume_flow", "Continue"
    if session_status == "expired":
        return False, False, "restart_verification", "Verify on WhatsApp"
    return False, False, "complete_whatsapp", "Open WhatsApp"


def _build_demo_urls(base_url: str, external_order_id: str) -> dict[str, str]:
    return {
        "menu_url": f"{base_url}/demo?screen=menu&order={external_order_id}",
        "order_url": f"{base_url}/demo?screen=order&order={external_order_id}",
        "bill_url": f"{base_url}/demo?screen=bill&order={external_order_id}",
        "payment_url": f"{base_url}/demo?screen=payment&order={external_order_id}",
        "feedback_url": f"{base_url}/demo?screen=feedback&order={external_order_id}",
    }


def _demo_resume_url(order: Order, entry_point: str) -> str | None:
    mapping = {
        "menu": order.menu_url,
        "cart": order.order_url,
        "order_review": order.order_url,
        "bill": order.bill_url,
        "payment": order.payment_url,
        "feedback": order.feedback_url,
        "dish_review": order.feedback_url,
        "captain_pos": order.order_url,
    }
    return mapping.get(entry_point, order.order_url)


def _demo_intent(entry_point: str) -> str:
    if entry_point in {"bill", "payment"}:
        return "send_payment_link"
    if entry_point in {"feedback", "dish_review"}:
        return "collect_feedback"
    if entry_point == "captain_pos":
        return "link_order"
    return "verify_before_payment"


def _apply_demo_tracked_urls(db: Session, base_url: str, order: Order) -> None:
    external_order_id = order.external_order_id or str(order.id)
    direct_urls = _build_demo_urls(base_url, external_order_id)
    order.menu_url = create_tracked_link(
        db, base_url, direct_urls["menu_url"], stage="menu", action="open_menu", restaurant_id=order.restaurant_id, order_id=order.id
    )
    order.order_url = create_tracked_link(
        db, base_url, direct_urls["order_url"], stage="order_review", action="view_order_review", restaurant_id=order.restaurant_id, order_id=order.id
    )
    order.bill_url = create_tracked_link(
        db, base_url, direct_urls["bill_url"], stage="bill", action="view_bill", restaurant_id=order.restaurant_id, order_id=order.id
    )
    order.payment_url = create_tracked_link(
        db, base_url, direct_urls["payment_url"], stage="payment", action="pay_now", restaurant_id=order.restaurant_id, order_id=order.id
    )
    order.feedback_url = create_tracked_link(
        db, base_url, direct_urls["feedback_url"], stage="feedback", action="leave_feedback", restaurant_id=order.restaurant_id, order_id=order.id
    )
    notes = dict(order.notes or {})
    dish_reviews: list[dict[str, str]] = []
    for index, item in enumerate(order.line_items or [], start=1):
        dish_id = str(item.get("dish_id") or f"dish_{index}")
        dish_name = str(item.get("name") or item.get("title") or f"Dish {index}")
        review_target = f"{base_url}/demo?screen=feedback&order={external_order_id}&dish={dish_id}"
        dish_reviews.append(
            {
                "dish_id": dish_id,
                "dish_name": dish_name,
                "review_url": create_tracked_link(
                    db,
                    base_url,
                    review_target,
                    stage="dish_review",
                    action=f"review_{dish_id}",
                    restaurant_id=order.restaurant_id,
                    order_id=order.id,
                ),
            }
        )
    notes["dish_reviews"] = dish_reviews
    order.notes = notes


def _get_order_or_404(db: Session, order_id: UUID) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise AppError(404, "order_not_found", "Order not found")
    return order


def _get_order_by_reference_or_404(db: Session, order_reference: str) -> Order:
    order = db.execute(select(Order).where(Order.external_order_id == order_reference)).scalar_one_or_none()
    if order is None:
        raise AppError(404, "order_not_found", "Order not found")
    return order


async def _send_demo_order_message(
    db: Session,
    settings: Settings,
    *,
    order: Order,
    body: str,
) -> dict[str, str]:
    to_phone, customer, _, whatsapp_session = resolve_target(
        db,
        to_phone=None,
        customer_id=order.customer_id,
        order_id=order.id,
        session_id=None,
        require_verified=True,
    )
    message_log = await send_text_and_log(
        db,
        settings,
        to_phone=to_phone,
        body=body,
        preview_url=True,
        customer=customer,
        order=order,
        whatsapp_session=whatsapp_session,
    )
    return {"status": message_log.status, "message_log_id": str(message_log.id)}


def _demo_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Palate Demo</title>
  <style>
    :root {
      --bg: #f6efe5;
      --ink: #192126;
      --muted: #5d645f;
      --brand: #0d5c63;
      --accent: #d08c60;
      --card: rgba(255, 252, 247, 0.92);
      --ok: #1f7a4b;
      --warn: #b96d16;
      --bad: #a13d2d;
      --line: rgba(25, 33, 38, 0.08);
      font-family: "Segoe UI", "Helvetica Neue", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(208, 140, 96, 0.18), transparent 28%),
        radial-gradient(circle at left bottom, rgba(13, 92, 99, 0.14), transparent 32%),
        linear-gradient(160deg, #faf5ed 0%, var(--bg) 100%);
    }
    .shell {
      max-width: 1024px;
      margin: 0 auto;
      padding: 24px;
      display: grid;
      gap: 20px;
    }
    .hero {
      background: linear-gradient(135deg, rgba(13, 92, 99, 0.95), rgba(29, 54, 71, 0.92));
      color: white;
      border-radius: 28px;
      padding: 24px;
      display: grid;
      gap: 16px;
      box-shadow: 0 24px 60px rgba(22, 36, 45, 0.18);
    }
    .hero h1 { margin: 0; font-size: clamp(32px, 6vw, 52px); line-height: 0.95; }
    .hero p { margin: 0; max-width: 62ch; color: rgba(255,255,255,0.84); }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 20px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 20px;
      box-shadow: 0 18px 40px rgba(18, 28, 35, 0.08);
      backdrop-filter: blur(10px);
    }
    .card h2, .card h3 { margin: 0 0 10px; }
    .subtle { color: var(--muted); font-size: 14px; }
    .field {
      width: 100%;
      margin-top: 14px;
      padding: 12px 14px;
      border: 1px solid rgba(25,33,38,0.12);
      border-radius: 14px;
      background: rgba(255,255,255,0.9);
      font-size: 15px;
    }
    .stack { display: grid; gap: 12px; }
    .row { display: flex; gap: 12px; flex-wrap: wrap; }
    button {
      border: 0;
      border-radius: 999px;
      padding: 12px 16px;
      cursor: pointer;
      font-weight: 700;
      font-size: 14px;
      transition: transform 0.15s ease, opacity 0.15s ease;
    }
    button:hover { transform: translateY(-1px); }
    button:disabled { opacity: 0.45; cursor: not-allowed; transform: none; }
    .primary { background: var(--accent); color: #1b1612; }
    .secondary { background: var(--brand); color: white; }
    .ghost { background: rgba(25,33,38,0.08); color: var(--ink); }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 13px;
      font-weight: 700;
      background: rgba(25,33,38,0.06);
    }
    .pill.pending { color: var(--warn); background: rgba(185, 109, 22, 0.12); }
    .pill.verified { color: var(--ok); background: rgba(31, 122, 75, 0.12); }
    .pill.expired { color: var(--bad); background: rgba(161, 61, 45, 0.12); }
    .qr {
      width: min(260px, 100%);
      display: block;
      margin: 12px auto 0;
      padding: 10px;
      background: white;
      border-radius: 20px;
    }
    pre {
      margin: 0;
      padding: 14px;
      overflow: auto;
      border-radius: 16px;
      background: #16242d;
      color: #e9f3f6;
      font-size: 13px;
      min-height: 180px;
    }
    .facts { display: grid; gap: 10px; font-size: 14px; color: var(--muted); }
    .facts strong { color: var(--ink); }
    .advanced-facts { display: none; }
    .advanced-facts.show { display: grid; }
    .notice {
      display: none;
      margin-top: 12px;
      padding: 12px 14px;
      border-radius: 16px;
      background: rgba(13, 92, 99, 0.08);
      color: var(--ink);
      font-size: 14px;
      line-height: 1.45;
    }
    .notice.show { display: block; }
    .notice a {
      color: var(--brand);
      font-weight: 700;
      text-decoration: none;
    }
    .notice a:hover { text-decoration: underline; }
    .debug-card { display: none; }
    .debug-card.show { display: block; }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="pill pending" id="status-pill">Status: pending</div>
      <h1>Palate Demo Bistro</h1>
      <p>Scan the QR, tap WhatsApp, send the prefilled token, and this demo backend will verify the sender phone and unlock order, bill, payment, and feedback WhatsApp messages.</p>
    </section>

    <section class="grid">
      <div class="card stack">
        <div>
          <h2>Customer Flow</h2>
          <div class="subtle">Optional name capture first, WhatsApp verification next, then message actions unlock.</div>
          <div class="subtle">Choose the origin screen first. Each tap on Continue creates one fresh demo order and one fresh verification session for that screen.</div>
        </div>
        <input id="customer-name" class="field" placeholder="Enter customer name (optional)" />
        <select id="entry-point" class="field">
          <option value="menu">Menu screen</option>
          <option value="cart">Cart screen</option>
          <option value="order_review">Order review screen</option>
          <option value="bill">Bill screen</option>
          <option value="payment">Payment screen</option>
          <option value="feedback">Feedback screen</option>
          <option value="dish_review">Dish review screen</option>
          <option value="captain_pos">Captain / POS flow</option>
        </select>
        <div class="row">
          <button id="continue-btn" class="primary">Continue with WhatsApp</button>
          <button id="order-btn" class="secondary" disabled>Send order list on WhatsApp</button>
        </div>
        <div class="row">
          <button id="bill-btn" class="secondary" disabled>Receive bill on WhatsApp</button>
          <button id="feedback-btn" class="secondary" disabled>Send feedback link</button>
        </div>
        <div class="row">
          <button id="payment-btn" class="ghost" disabled>Simulate payment success</button>
        </div>
        <div id="wa-notice" class="notice">
          WhatsApp link is ready.
          <a id="wa-link" href="#" target="_blank" rel="noopener noreferrer">Open WhatsApp message</a>
        </div>
        <div class="facts">
          <div><strong>Verification status:</strong> <span id="verification-state">pending</span></div>
          <div><strong>Captured name:</strong> <span id="customer-name-view">pending</span></div>
          <div><strong>Origin screen:</strong> <span id="entry-point-view">menu</span></div>
          <div><strong>Verified phone:</strong> <span id="verified-phone">pending</span></div>
        </div>
        <div id="advanced-facts" class="facts advanced-facts">
          <div><strong>Session:</strong> <span id="session-id">not started</span></div>
          <div><strong>Order reference:</strong> <span id="order-id">not started</span></div>
          <div><strong>Where to continue:</strong> <span id="resume-url">waiting for verification</span></div>
        </div>
      </div>

      <div class="card">
        <h3>QR Test</h3>
        <div class="subtle">Use this on another phone to open the live demo entry route over Railway.</div>
        <img class="qr" alt="Palate demo QR" src="/demo/qr" />
        <div class="subtle">QR target: <a id="qr-target-link" href="/d">/d</a></div>
        <div class="subtle">If scan fails, open this directly on the phone: <a id="phone-open-link" href="/d">Open demo</a></div>
      </div>
    </section>

    <section id="debug-card" class="card debug-card">
      <h3>Live Debug</h3>
      <pre id="output">Waiting for actions...</pre>
    </section>
  </div>

  <script>
    const DEBUG_MODE = new URLSearchParams(window.location.search).get("debug") === "1";
    const state = { sessionId: null, orderId: null, pollTimer: null, sentActions: new Set() };
    const output = document.getElementById("output");
    const debugCard = document.getElementById("debug-card");
    const advancedFacts = document.getElementById("advanced-facts");
    const statusPill = document.getElementById("status-pill");
    const verificationState = document.getElementById("verification-state");
    const sessionLabel = document.getElementById("session-id");
    const orderLabel = document.getElementById("order-id");
    const verifiedPhone = document.getElementById("verified-phone");
    const customerNameView = document.getElementById("customer-name-view");
    const entryPointView = document.getElementById("entry-point-view");
    const resumeUrl = document.getElementById("resume-url");
    const waNotice = document.getElementById("wa-notice");
    const waLink = document.getElementById("wa-link");
    const qrTargetLink = document.getElementById("qr-target-link");
    const phoneOpenLink = document.getElementById("phone-open-link");
    const buttons = {
      continue: document.getElementById("continue-btn"),
      order: document.getElementById("order-btn"),
      bill: document.getElementById("bill-btn"),
      feedback: document.getElementById("feedback-btn"),
      payment: document.getElementById("payment-btn"),
    };
    const buttonLabels = {
      order: "Send order list on WhatsApp",
      bill: "Receive bill on WhatsApp",
      feedback: "Send feedback link",
      payment: "Simulate payment success",
    };

    if (DEBUG_MODE) {
      debugCard.classList.add("show");
      advancedFacts.classList.add("show");
    }

    function log(data) {
      if (!DEBUG_MODE) return;
      output.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    }

    const directOpenUrl = `${window.location.origin}/d`;
    qrTargetLink.href = directOpenUrl;
    qrTargetLink.textContent = directOpenUrl;
    phoneOpenLink.href = directOpenUrl;

    function setStatus(status, payload = {}) {
      statusPill.textContent = `Status: ${status}`;
      statusPill.className = `pill ${status}`;
      verificationState.textContent = status;
      verifiedPhone.textContent = payload.verified_phone || "pending";
      customerNameView.textContent = payload.provided_name || document.getElementById("customer-name").value.trim() || "pending";
      entryPointView.textContent = payload.entry_point || document.getElementById("entry-point").value;
      resumeUrl.textContent = payload.resume_url || "waiting for verification";
      const verified = status === "verified";
      buttons.order.disabled = !verified || state.sentActions.has("order");
      buttons.bill.disabled = !verified || state.sentActions.has("bill");
      buttons.feedback.disabled = !verified || state.sentActions.has("feedback");
      buttons.payment.disabled = !verified || state.sentActions.has("payment");
    }

    function setNotice(message, href) {
      waNotice.classList.add("show");
      waLink.href = href;
      waLink.textContent = message;
    }

    async function callJson(url, options = {}) {
      const response = await fetch(url, {
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        ...options,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.message || payload.detail || response.statusText);
      }
      return payload;
    }

    async function pollStatus() {
      if (!state.sessionId) return;
      try {
        const payload = await callJson(`/demo/sessions/${state.sessionId}`);
        setStatus(payload.session_status, payload);
        log(payload);
        if (payload.session_status === "verified" || payload.session_status === "expired") {
          clearInterval(state.pollTimer);
          state.pollTimer = null;
        }
      } catch (error) {
        log({ error: String(error) });
      }
    }

    buttons.continue.addEventListener("click", async () => {
      try {
        const customerName = document.getElementById("customer-name").value.trim();
        const entryPoint = document.getElementById("entry-point").value;
        const payload = await callJson("/demo/session-link", {
          method: "POST",
          body: JSON.stringify({ customer_name: customerName || null, entry_point: entryPoint }),
        });
        state.sessionId = payload.session_id;
        state.orderId = payload.order_id;
        state.sentActions = new Set();
        sessionLabel.textContent = payload.session_id;
        orderLabel.textContent = payload.external_order_id;
        Object.entries(buttonLabels).forEach(([key, label]) => {
          buttons[key].textContent = label;
        });
        setStatus("pending", {
          entry_point: entryPoint,
          provided_name: customerName || null,
          resume_url: payload.resume_url || "waiting for verification",
        });
        setNotice("Open WhatsApp message", payload.wa_url);
        const popup = window.open(payload.wa_url, "_blank", "noopener,noreferrer");
        if (!popup || popup.closed || typeof popup.closed === "undefined") {
          log({
            info: "WhatsApp link prepared. Use the visible link on the page if the popup did not open.",
            session_id: payload.session_id,
            external_order_id: payload.external_order_id,
            wa_url: payload.wa_url,
          });
        } else {
          log(payload);
        }
        if (state.pollTimer) clearInterval(state.pollTimer);
        state.pollTimer = setInterval(pollStatus, 3000);
        pollStatus();
      } catch (error) {
        log({ error: String(error) });
      }
    });

    async function sendAction(actionKey, path) {
      if (!state.orderId) {
        log("Start a demo session first.");
        return;
      }
      if (state.sentActions.has(actionKey)) {
        log(`${buttonLabels[actionKey]} was already sent for this demo session.`);
        return;
      }
      const button = buttons[actionKey];
      try {
        button.disabled = true;
        button.textContent = "Sending...";
        const payload = await callJson(path, { method: "POST" });
        state.sentActions.add(actionKey);
        button.textContent = "Sent";
        log(payload);
      } catch (error) {
        button.disabled = false;
        button.textContent = buttonLabels[actionKey];
        log({ error: String(error) });
      }
    }

    buttons.order.addEventListener("click", () => sendAction("order", `/demo/orders/${state.orderId}/send-order-list`));
    buttons.bill.addEventListener("click", () => sendAction("bill", `/demo/orders/${state.orderId}/send-bill`));
    buttons.feedback.addEventListener("click", () => sendAction("feedback", `/demo/orders/${state.orderId}/send-feedback`));
    buttons.payment.addEventListener("click", () => sendAction("payment", `/demo/simulate-payment-success?order_id=${state.orderId}`));
  </script>
</body>
</html>"""


def _screen_badge(screen: str) -> str:
    labels = {
        "menu": "Menu",
        "order": "Order",
        "bill": "Bill",
        "payment": "Payment",
        "feedback": "Feedback",
    }
    return labels.get(screen, "Palate")


def _screen_intro(screen: str) -> tuple[str, str]:
    copy = {
        "menu": (
            "Browse the menu",
            "This is the kind of page the client app would open from WhatsApp or QR before checkout.",
        ),
        "order": (
            "Order summary",
            "This is the clean web/app screen customers should land on after WhatsApp verification.",
        ),
        "bill": (
            "Bill breakdown",
            "WhatsApp should send the totals. The app/web page can show the richer receipt and payment context.",
        ),
        "payment": (
            "Payment step",
            "WhatsApp confirms identity and nudges payment. The actual payment step happens on a page like this.",
        ),
        "feedback": (
            "Feedback capture",
            "WhatsApp asks for feedback. The rich feedback form can live on the app or web page.",
        ),
    }
    return copy.get(screen, ("Palate screen", "Palate customer screen"))


def _order_total_text(order: Order) -> str:
    return f"{order.currency} {(order.total_amount or Decimal('0')):.2f}"


def _amount_due_text(order: Order) -> str:
    amount_due = (order.total_amount or Decimal("0")) - (order.amount_paid or Decimal("0"))
    return f"{order.currency} {amount_due:.2f}"


def _items_markup(order: Order) -> str:
    items = order.line_items or []
    if not items:
        return "<li class='line-item'><span>Items will be shared at the restaurant.</span><strong></strong></li>"
    lines: list[str] = []
    for item in items:
        quantity = item.get("quantity") or item.get("qty") or 1
        name = item.get("name") or item.get("title") or "Item"
        lines.append(
            f"<li class='line-item'><span>{quantity} x {name}</span><strong></strong></li>"
        )
    return "".join(lines)


def _menu_cards_markup(order: Order) -> str:
    items = order.line_items or []
    cards: list[str] = []
    for index, item in enumerate(items, start=1):
        quantity = item.get("quantity") or item.get("qty") or 1
        name = item.get("name") or item.get("title") or f"Item {index}"
        cards.append(
            f"""
            <article class="menu-card">
              <div class="menu-number">0{index}</div>
              <h3>{name}</h3>
              <p>Guest-selected item. Quantity reserved in the cart: {quantity}.</p>
              <div class="menu-meta">Ready for kitchen confirmation</div>
            </article>
            """
        )
    return "".join(cards)


def _demo_screen_html(order: Order, screen: str, base_url: str) -> str:
    title, subtitle = _screen_intro(screen)
    payment_pending = (order.amount_paid or Decimal("0")) < (order.total_amount or Decimal("0"))
    payment_button = ""
    if screen == "payment":
        if payment_pending:
            payment_button = f"""
            <button id="simulate-payment" class="primary-action">Mark Payment Successful</button>
            <p class="helper-copy">This triggers the same backend payment-success WhatsApp message path without Razorpay.</p>
            """
        else:
            payment_button = "<div class='success-chip'>Payment already marked as received.</div>"

    feedback_panel = ""
    if screen == "feedback":
        feedback_panel = """
        <div class="feedback-grid">
          <button class="feedback-pill active">Loved the food</button>
          <button class="feedback-pill">Service could be faster</button>
          <button class="feedback-pill">Would order again</button>
        </div>
        <textarea class="feedback-box" placeholder="Tell Palate what stood out about the meal or service."></textarea>
        <button class="primary-action ghost-action">Submit feedback mock</button>
        """

    detail_panel = {
        "menu": f"""
          <section class="phone-card tall">
            <div class="eyebrow">Live menu preview</div>
            <div class="menu-grid">{_menu_cards_markup(order)}</div>
            <div class="sticky-bar">
              <div>
                <strong>{_order_total_text(order)}</strong>
                <span>{len(order.line_items or [])} items in cart</span>
              </div>
              <a class="primary-action" href="{order.order_url or '#'}">Review order</a>
            </div>
          </section>
        """,
        "order": f"""
          <section class="phone-card">
            <div class="eyebrow">Verified order context</div>
            <h2>Order {order.external_order_id or order.id}</h2>
            <ul class="line-list">{_items_markup(order)}</ul>
            <div class="totals">
              <div><span>Total</span><strong>{_order_total_text(order)}</strong></div>
              <div><span>Status</span><strong>{order.order_status.title()}</strong></div>
            </div>
            <a class="primary-action" href="{order.bill_url or order.payment_url or '#'}">View bill</a>
          </section>
        """,
        "bill": f"""
          <section class="phone-card receipt">
            <div class="eyebrow">Bill</div>
            <h2>{order.restaurant_name}</h2>
            <ul class="line-list">{_items_markup(order)}</ul>
            <div class="receipt-totals">
              <div><span>Subtotal</span><strong>{order.currency} {(order.subtotal_amount or Decimal('0')):.2f}</strong></div>
              <div><span>Tax</span><strong>{order.currency} {(order.tax_amount or Decimal('0')):.2f}</strong></div>
              <div class="grand"><span>Amount due</span><strong>{_amount_due_text(order)}</strong></div>
            </div>
            <a class="primary-action" href="{order.payment_url or '#'}">Continue to payment</a>
          </section>
        """,
        "payment": f"""
          <section class="phone-card">
            <div class="eyebrow">Payment</div>
            <h2>Complete payment</h2>
            <p class="screen-copy">WhatsApp should carry the reminder and confidence signal. The actual payment UX belongs here.</p>
            <div class="payment-hero">
              <strong>{_amount_due_text(order)}</strong>
              <span>Outstanding for order {order.external_order_id or order.id}</span>
            </div>
            {payment_button}
          </section>
        """,
        "feedback": f"""
          <section class="phone-card">
            <div class="eyebrow">Feedback</div>
            <h2>Tell us how it went</h2>
            <p class="screen-copy">WhatsApp prompts the action. This page captures the richer response cleanly.</p>
            {feedback_panel}
          </section>
        """,
    }.get(screen, "")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Palate Demo {title}</title>
  <style>
    :root {{
      --sand: #f4efe7;
      --ink: #13232d;
      --muted: #6d746f;
      --teal: #0f5c63;
      --sage: #9ec2be;
      --amber: #d38957;
      --paper: rgba(255, 252, 247, 0.9);
      --line: rgba(19, 35, 45, 0.08);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(211, 137, 87, 0.2), transparent 24%),
        radial-gradient(circle at right center, rgba(15, 92, 99, 0.14), transparent 28%),
        linear-gradient(160deg, #fbf7f0 0%, var(--sand) 100%);
    }}
    .frame {{
      min-height: 100vh;
      max-width: 1160px;
      margin: 0 auto;
      padding: 28px 18px 48px;
      display: grid;
      gap: 22px;
    }}
    .hero {{
      background: linear-gradient(140deg, #102d39, #315362);
      color: white;
      border-radius: 32px;
      padding: 28px;
      box-shadow: 0 28px 60px rgba(16, 45, 57, 0.2);
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,0.12);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .hero h1 {{
      margin: 16px 0 10px;
      font-size: clamp(34px, 6vw, 58px);
      line-height: 0.94;
    }}
    .hero p {{
      margin: 0;
      max-width: 64ch;
      color: rgba(255,255,255,0.82);
      font-size: 17px;
      line-height: 1.5;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: 1.05fr 0.95fr;
      gap: 22px;
      align-items: start;
    }}
    .card {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 28px;
      padding: 22px;
      box-shadow: 0 16px 44px rgba(20, 30, 38, 0.08);
      backdrop-filter: blur(12px);
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
    }}
    .meta-box {{
      background: rgba(255,255,255,0.74);
      border-radius: 18px;
      padding: 14px;
    }}
    .meta-box span {{
      display: block;
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 8px;
    }}
    .meta-box strong {{
      font-size: 18px;
      line-height: 1.2;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 22px;
    }}
    .narrative {{
      display: grid;
      gap: 16px;
    }}
    .narrative h2, .phone-card h2 {{
      margin: 0;
      font-size: 30px;
      line-height: 1.05;
    }}
    .narrative p, .screen-copy {{
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
      font-size: 16px;
    }}
    .flow-list {{
      display: grid;
      gap: 12px;
      margin-top: 2px;
    }}
    .flow-step {{
      display: grid;
      grid-template-columns: 44px 1fr;
      gap: 12px;
      align-items: start;
    }}
    .flow-step b {{
      width: 44px;
      height: 44px;
      display: grid;
      place-items: center;
      border-radius: 16px;
      background: rgba(15, 92, 99, 0.12);
      color: var(--teal);
      font-size: 14px;
    }}
    .flow-step div {{
      padding-top: 2px;
      line-height: 1.45;
    }}
    .cta-row {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 10px;
    }}
    .cta-row a, .primary-action, .ghost-action {{
      text-decoration: none;
      border: 0;
      border-radius: 999px;
      padding: 13px 18px;
      font-weight: 700;
      font-size: 14px;
      cursor: pointer;
    }}
    .primary-action {{
      background: var(--amber);
      color: #1a1410;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }}
    .secondary-link {{
      background: rgba(15, 92, 99, 0.12);
      color: var(--teal);
    }}
    .phone-card {{
      min-height: 100%;
      background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(247,242,235,0.95));
      border-radius: 34px;
      padding: 22px;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.8);
      display: grid;
      gap: 16px;
    }}
    .phone-card.tall {{ min-height: 620px; }}
    .line-list {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 10px;
    }}
    .line-item {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 0;
      border-bottom: 1px solid rgba(19, 35, 45, 0.08);
    }}
    .totals, .receipt-totals {{
      display: grid;
      gap: 10px;
      padding-top: 4px;
    }}
    .totals div, .receipt-totals div {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      color: var(--muted);
    }}
    .receipt-totals .grand {{
      color: var(--ink);
      font-weight: 800;
      padding-top: 10px;
      border-top: 1px solid rgba(19, 35, 45, 0.08);
    }}
    .menu-grid {{
      display: grid;
      gap: 14px;
    }}
    .menu-card {{
      border-radius: 24px;
      padding: 18px;
      background: rgba(255,255,255,0.76);
      border: 1px solid rgba(19,35,45,0.08);
    }}
    .menu-card h3 {{
      margin: 10px 0 8px;
      font-size: 24px;
    }}
    .menu-card p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
    }}
    .menu-number {{
      width: 36px;
      height: 36px;
      border-radius: 14px;
      display: grid;
      place-items: center;
      background: rgba(211, 137, 87, 0.16);
      color: #8a502c;
      font-weight: 800;
    }}
    .menu-meta {{
      margin-top: 12px;
      color: var(--teal);
      font-size: 13px;
      font-weight: 700;
    }}
    .sticky-bar {{
      margin-top: auto;
      padding: 16px 18px;
      border-radius: 22px;
      background: #13232d;
      color: white;
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: center;
    }}
    .sticky-bar span {{
      display: block;
      color: rgba(255,255,255,0.74);
      font-size: 13px;
      margin-top: 4px;
    }}
    .payment-hero {{
      padding: 18px;
      border-radius: 24px;
      background: rgba(15, 92, 99, 0.1);
      display: grid;
      gap: 6px;
    }}
    .payment-hero strong {{
      font-size: 34px;
      line-height: 1;
    }}
    .helper-copy {{
      margin: 0;
      font-size: 13px;
      color: var(--muted);
    }}
    .success-chip {{
      display: inline-flex;
      padding: 12px 14px;
      border-radius: 999px;
      background: rgba(31, 122, 75, 0.12);
      color: #1f7a4b;
      font-weight: 800;
      width: fit-content;
    }}
    .feedback-grid {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .feedback-pill {{
      border: 1px solid rgba(19,35,45,0.1);
      background: rgba(255,255,255,0.7);
      border-radius: 999px;
      padding: 10px 14px;
      font-weight: 700;
      color: var(--ink);
    }}
    .feedback-pill.active {{
      background: rgba(15, 92, 99, 0.12);
      color: var(--teal);
      border-color: rgba(15, 92, 99, 0.16);
    }}
    .feedback-box {{
      min-height: 130px;
      border-radius: 22px;
      border: 1px solid rgba(19,35,45,0.1);
      background: rgba(255,255,255,0.76);
      padding: 16px;
      font: inherit;
      resize: vertical;
    }}
    .ghost-action {{
      background: rgba(19,35,45,0.08);
      color: var(--ink);
    }}
    @media (max-width: 900px) {{
      .hero-grid, .layout {{
        grid-template-columns: 1fr;
      }}
      .meta-grid {{
        grid-template-columns: 1fr;
      }}
      .sticky-bar {{
        flex-direction: column;
        align-items: stretch;
      }}
    }}
  </style>
</head>
<body>
  <div class="frame">
    <section class="hero">
      <div class="eyebrow">{_screen_badge(screen)}</div>
      <div class="hero-grid">
        <div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
          <div class="meta-grid">
            <div class="meta-box"><span>Restaurant</span><strong>{order.restaurant_name}</strong></div>
            <div class="meta-box"><span>Order</span><strong>{order.external_order_id or order.id}</strong></div>
            <div class="meta-box"><span>Total</span><strong>{_order_total_text(order)}</strong></div>
          </div>
        </div>
        <div class="card">
          <div class="eyebrow">How integration works</div>
          <div class="flow-list">
            <div class="flow-step"><b>01</b><div>The web or app page calls Palate backend to create a WhatsApp verification session.</div></div>
            <div class="flow-step"><b>02</b><div>User taps WhatsApp. Backend verifies the real sender phone from the webhook.</div></div>
            <div class="flow-step"><b>03</b><div>Backend links the verified phone to this order, then sends useful updates on WhatsApp.</div></div>
          </div>
        </div>
      </div>
    </section>

    <section class="layout">
      <div class="card narrative">
        <div class="eyebrow">Product meaning</div>
        <h2>App and WhatsApp work together.</h2>
        <p>WhatsApp should not replace the full app. It should verify identity, carry high-intent updates, and pull the user back into the best page when richer UI is needed.</p>
        <div class="flow-list">
          <div class="flow-step"><b>A</b><div><strong>App/web owns rich UX:</strong> menu browsing, bill breakdown, payment UI, feedback forms.</div></div>
          <div class="flow-step"><b>B</b><div><strong>WhatsApp owns recovery and continuity:</strong> verification, reminders, bill nudge, payment confirmation, feedback prompt.</div></div>
          <div class="flow-step"><b>C</b><div><strong>The backend is the connector:</strong> it stores the order, session, customer, verified phone, and message history.</div></div>
        </div>
        <div class="cta-row">
          <a class="primary-action" href="{base_url}/demo">Back to demo landing</a>
          <a class="secondary-link primary-action" href="{order.order_url or base_url + '/demo'}">Open order route</a>
        </div>
      </div>
      {detail_panel}
    </section>
  </div>
  <script>
    const paymentButton = document.getElementById("simulate-payment");
    if (paymentButton) {{
      paymentButton.addEventListener("click", async () => {{
        paymentButton.disabled = true;
        paymentButton.textContent = "Sending payment success...";
        try {{
          const response = await fetch("/demo/simulate-payment-success?order_id={order.id}", {{
            method: "POST",
          }});
          const payload = await response.json();
          paymentButton.textContent = payload.status === "accepted" ? "Payment success sent on WhatsApp" : "Retry";
        }} catch (error) {{
          paymentButton.disabled = false;
          paymentButton.textContent = "Mark Payment Successful";
        }}
      }});
    }}
  </script>
</body>
</html>"""


@router.get("/demo", response_class=HTMLResponse)
def demo_page(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    _ensure_demo_mode(settings)
    screen = (request.query_params.get("screen") or "").strip().lower()
    order_reference = (request.query_params.get("order") or "").strip()
    if screen in {"menu", "order", "bill", "payment", "feedback"} and order_reference:
        order = _get_order_by_reference_or_404(db, order_reference)
        return HTMLResponse(_demo_screen_html(order, screen, _base_url(request, settings)))
    return HTMLResponse(_demo_html())


@router.get("/demo/open")
def demo_open(request: Request, settings: Settings = Depends(get_settings)) -> RedirectResponse:
    _ensure_demo_mode(settings)
    return RedirectResponse(url=f"{_base_url(request, settings)}/demo", status_code=307)


@router.get("/d")
def demo_short_open(request: Request, settings: Settings = Depends(get_settings)) -> RedirectResponse:
    _ensure_demo_mode(settings)
    return RedirectResponse(url=f"{_base_url(request, settings)}/demo", status_code=307)


@router.get("/demo/qr")
def demo_qr(request: Request, settings: Settings = Depends(get_settings)) -> Response:
    _ensure_demo_mode(settings)
    target_url = f"{_base_url(request, settings)}/d"
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=12,
        border=6,
    )
    qr.add_data(target_url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    qr_image.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")


@router.post("/demo/session-link")
def create_demo_session_link(
    payload: dict[str, str | None],
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    _ensure_demo_mode(settings)
    base_url = _base_url(request, settings)
    customer_name = (payload.get("customer_name") or "").strip() or None
    entry_point = (payload.get("entry_point") or "menu").strip() or "menu"
    if entry_point not in DEMO_ENTRY_POINTS:
        raise AppError(422, "demo_entry_point_invalid", "Unsupported demo entry point")
    external_order_id = f"DEMO-{secrets.token_hex(4).upper()}"
    urls = _build_demo_urls(base_url, external_order_id)
    order = Order(
        external_order_id=external_order_id,
        restaurant_id="palate-demo",
        restaurant_name="Palate Demo Bistro",
        order_status="created",
        currency="INR",
        subtotal_amount=Decimal("720.00"),
        tax_amount=Decimal("130.00"),
        total_amount=Decimal("850.00"),
        amount_paid=Decimal("0.00"),
        summary_text="2 x Truffle Pasta, 1 x Tiramisu",
        menu_url=urls["menu_url"],
        order_url=urls["order_url"],
        bill_url=urls["bill_url"],
        payment_url=urls["payment_url"],
        feedback_url=urls["feedback_url"],
        notes={"demo_mode": True},
        line_items=[
            {"name": "Truffle Pasta", "quantity": 2},
            {"name": "Tiramisu", "quantity": 1},
        ],
    )
    db.add(order)
    db.flush()
    _apply_demo_tracked_urls(db, base_url, order)
    resume_url = _demo_resume_url(order, entry_point)
    session_link = create_session_link_for_context(
        db,
        settings,
        order=order,
        customer=None,
        restaurant_id=order.restaurant_id,
        restaurant_name=order.restaurant_name,
        customer_name=customer_name,
        provided_phone=None,
        entry_point=entry_point,
        intent=_demo_intent(entry_point),
        resume_url=resume_url,
        metadata={"demo_mode": True, "external_order_id": external_order_id, "entry_point": entry_point},
        expires_in_minutes=settings.whatsapp_session_ttl_minutes,
    )
    session = db.get(WhatsAppSession, session_link.session_id)
    if session is not None:
        log_session_started(db, session, request)
    db.commit()
    return {
        "session_id": str(session_link.session_id),
        "order_id": str(order.id),
        "external_order_id": external_order_id,
        "wa_url": session_link.wa_url,
        "token_hint": session_link.token_hint,
        "resume_url": resume_url or "",
        "entry_point": entry_point,
        "expires_at": session_link.expires_at.isoformat(),
    }


@router.get("/demo/sessions/{session_id}", response_model=SessionStatusResponse)
def get_demo_session_status(
    session_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SessionStatusResponse:
    _ensure_demo_mode(settings)
    session = db.get(WhatsAppSession, session_id)
    if session is None:
        raise AppError(404, "session_not_found", "WhatsApp session not found")

    current_status = session.session_status
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if current_status == "pending" and expires_at < utcnow():
        current_status = "expired"
    is_verified, can_proceed, next_action, recommended_cta_label = _session_action(current_status)

    return SessionStatusResponse(
        session_id=session.id,
        order_id=session.order_id,
        customer_id=session.customer_id,
        session_status=current_status,
        is_verified=is_verified,
        can_proceed=can_proceed,
        next_action=next_action,
        recommended_cta_label=recommended_cta_label,
        entry_point=session.entry_point,
        intent=session.intent,
        provided_name=session.provided_name,
        verified_phone=session.phone_e164,
        resume_url=session.resume_url,
        expires_at=session.expires_at,
        verified_at=session.verified_at,
    )


@router.post("/demo/orders/{order_id}/send-order-list")
async def demo_send_order_list(
    order_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    _ensure_demo_mode(settings)
    order = _get_order_or_404(db, order_id)
    log_journey_event(db, event_type="demo_action", stage="order_review", action="send_order_list", restaurant_id=order.restaurant_id, order_id=order.id)
    return await _send_demo_order_message(db, settings, order=order, body=compose_order_summary(order))


@router.post("/demo/orders/{order_id}/send-bill")
async def demo_send_bill(
    order_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    _ensure_demo_mode(settings)
    order = _get_order_or_404(db, order_id)
    log_journey_event(db, event_type="demo_action", stage="bill", action="send_bill", restaurant_id=order.restaurant_id, order_id=order.id)
    return await _send_demo_order_message(db, settings, order=order, body=compose_bill_message(order))


@router.post("/demo/orders/{order_id}/send-feedback")
async def demo_send_feedback(
    order_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    _ensure_demo_mode(settings)
    order = _get_order_or_404(db, order_id)
    log_journey_event(db, event_type="demo_action", stage="feedback", action="send_feedback", restaurant_id=order.restaurant_id, order_id=order.id)
    return await _send_demo_order_message(db, settings, order=order, body=compose_feedback_message(order))


@router.post("/demo/simulate-payment-success")
async def demo_simulate_payment_success(
    order_id: UUID,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    _ensure_demo_mode(settings)
    order = _get_order_or_404(db, order_id)
    order.amount_paid = order.total_amount or Decimal("0.00")
    order.order_status = "paid"
    log_journey_event(db, event_type="payment_confirmed", stage="payment", action="demo_payment_success", restaurant_id=order.restaurant_id, order_id=order.id, target_url=order.payment_url)
    db.commit()
    db.refresh(order)
    return await _send_demo_order_message(db, settings, order=order, body=compose_payment_success_message(order))
