from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_internal_api_key
from app.core.exceptions import AppError
from app.db.models import IntegrationIntakeSubmission
from app.schemas import (
    IntegrationIntakeSubmissionItem,
    IntegrationIntakeSubmissionRequest,
    IntegrationIntakeSubmissionResponse,
)

router = APIRouter(tags=["intake"])


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clean_list(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value and value.strip()]


def _clean_dict(values: dict[str, str]) -> dict[str, str]:
    return {key: value.strip() for key, value in values.items() if value and value.strip()}


def _page_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Palate Integration Intake</title>
  <style>
    :root {
      --bg: #f5f1e8;
      --ink: #102733;
      --muted: #68717a;
      --card: rgba(255, 252, 247, 0.92);
      --line: rgba(16, 39, 51, 0.08);
      --brand: #0e5d63;
      --accent: #d58a56;
      --soft: rgba(14, 93, 99, 0.08);
      font-family: "SF Pro Display", "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(213, 138, 86, 0.18), transparent 22%),
        radial-gradient(circle at right center, rgba(14, 93, 99, 0.14), transparent 26%),
        linear-gradient(165deg, #fbf7ef 0%, var(--bg) 100%);
    }
    .shell {
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 18px 54px;
      display: grid;
      gap: 22px;
    }
    .hero {
      border-radius: 34px;
      padding: 30px;
      color: white;
      background: linear-gradient(135deg, #14303b, #335564);
      box-shadow: 0 30px 70px rgba(20, 48, 59, 0.2);
    }
    .hero h1 {
      margin: 16px 0 10px;
      font-size: clamp(36px, 6vw, 64px);
      line-height: 0.94;
    }
    .hero p {
      margin: 0;
      max-width: 66ch;
      color: rgba(255,255,255,0.82);
      line-height: 1.55;
      font-size: 17px;
    }
    .eyebrow {
      display: inline-flex;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,0.12);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
      font-weight: 700;
    }
    .layout {
      display: grid;
      grid-template-columns: 1.35fr 0.65fr;
      gap: 22px;
      align-items: start;
    }
    .stack { display: grid; gap: 18px; }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 28px;
      padding: 22px;
      box-shadow: 0 18px 48px rgba(16, 39, 51, 0.08);
      backdrop-filter: blur(10px);
    }
    .card h2 {
      margin: 0 0 10px;
      font-size: 28px;
      line-height: 1.08;
    }
    .subtle {
      color: var(--muted);
      line-height: 1.5;
      font-size: 14px;
    }
    .field-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .field, textarea, select {
      width: 100%;
      border: 1px solid rgba(16, 39, 51, 0.12);
      border-radius: 18px;
      padding: 13px 14px;
      background: rgba(255,255,255,0.86);
      color: var(--ink);
      font: inherit;
    }
    textarea {
      min-height: 110px;
      resize: vertical;
    }
    .question {
      display: grid;
      gap: 12px;
    }
    .question h3 {
      margin: 0;
      font-size: 19px;
    }
    .chips {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    .chip {
      position: relative;
      cursor: pointer;
    }
    .chip input {
      position: absolute;
      opacity: 0;
      pointer-events: none;
    }
    .chip span {
      display: inline-flex;
      align-items: center;
      min-height: 44px;
      padding: 10px 14px;
      border-radius: 999px;
      border: 1px solid rgba(16, 39, 51, 0.1);
      background: rgba(255,255,255,0.72);
      font-weight: 700;
      transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
    }
    .chip input:checked + span {
      background: rgba(14, 93, 99, 0.12);
      color: var(--brand);
      border-color: rgba(14, 93, 99, 0.18);
    }
    .submit-row {
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
    }
    button {
      border: 0;
      border-radius: 999px;
      padding: 14px 20px;
      background: var(--accent);
      color: #1d1611;
      font-weight: 800;
      font-size: 15px;
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .status {
      display: none;
      padding: 14px 16px;
      border-radius: 18px;
      background: var(--soft);
      color: var(--brand);
      font-weight: 700;
    }
    .status.show { display: block; }
    .status.error {
      background: rgba(168, 61, 50, 0.1);
      color: #a83d32;
    }
    .checklist {
      display: grid;
      gap: 12px;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .checklist li {
      padding: 14px;
      border-radius: 18px;
      background: rgba(255,255,255,0.68);
      border: 1px solid rgba(16, 39, 51, 0.06);
      line-height: 1.45;
    }
    @media (max-width: 980px) {
      .layout, .field-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="eyebrow">Palate Integration Intake</div>
      <h1>Answer fast. We shape the integration from this.</h1>
      <p>Tap the choices you know, skip what you do not, and leave notes where needed. This is only for the client-side integration details: real URLs, real flows, where verification should happen, and what messages must exist.</p>
    </section>

    <div class="layout">
      <form id="intake-form" class="stack">
        <section class="card stack">
          <div>
            <h2>Contact</h2>
            <div class="subtle">Who is answering this, so we know which missing details still need follow-up.</div>
          </div>
          <div class="field-grid">
            <input class="field" name="respondent_name" placeholder="Name" />
            <input class="field" name="respondent_role" placeholder="Role or team" />
            <input class="field" name="respondent_email" placeholder="Email" />
            <input class="field" name="respondent_phone" placeholder="Phone / WhatsApp" />
          </div>
        </section>

        <section class="card stack">
          <div>
            <h2>Real Product Surfaces</h2>
            <div class="subtle">Where can the customer or staff start this flow in the actual product?</div>
          </div>
          <div class="question">
            <h3>Which surfaces exist in Phase 1?</h3>
            <div class="chips">
              <label class="chip"><input type="checkbox" name="order_sources" value="website" /><span>Website</span></label>
              <label class="chip"><input type="checkbox" name="order_sources" value="mobile_app" /><span>Mobile app</span></label>
              <label class="chip"><input type="checkbox" name="order_sources" value="pos" /><span>POS</span></label>
              <label class="chip"><input type="checkbox" name="order_sources" value="captain_manual" /><span>Captain / manual</span></label>
              <label class="chip"><input type="checkbox" name="order_sources" value="qr_self_serve" /><span>QR self-serve</span></label>
            </div>
          </div>
        </section>

        <section class="card stack">
          <div>
            <h2>Real URLs</h2>
            <div class="subtle">Put actual routes if known. If not, paste route patterns or rough path names. These are the real pages WhatsApp should open.</div>
          </div>
          <div class="field-grid">
            <input class="field" name="menu_url" placeholder="menu_url" />
            <input class="field" name="order_url" placeholder="order_url" />
            <input class="field" name="bill_url" placeholder="bill_url" />
            <input class="field" name="payment_url" placeholder="payment_url" />
            <input class="field" name="feedback_url" placeholder="feedback_url" />
            <input class="field" name="return_url" placeholder="return_to_app / continue URL" />
          </div>
        </section>

        <section class="card stack">
          <div>
            <h2>Flow Triggers</h2>
            <div class="subtle">Select everywhere verification or order context may begin, and how strict it should be.</div>
          </div>
          <div class="question">
            <h3>Where should WhatsApp verification be allowed?</h3>
            <div class="chips">
              <label class="chip"><input type="checkbox" name="verification_points" value="landing" /><span>Landing</span></label>
              <label class="chip"><input type="checkbox" name="verification_points" value="menu" /><span>Menu</span></label>
              <label class="chip"><input type="checkbox" name="verification_points" value="cart" /><span>Cart</span></label>
              <label class="chip"><input type="checkbox" name="verification_points" value="order_review" /><span>Order review</span></label>
              <label class="chip"><input type="checkbox" name="verification_points" value="payment" /><span>Payment</span></label>
              <label class="chip"><input type="checkbox" name="verification_points" value="captain_manual" /><span>Captain / manual</span></label>
            </div>
          </div>
          <div class="question">
            <h3>When should verification become mandatory?</h3>
            <div class="chips">
              <label class="chip"><input type="checkbox" name="customer_inputs" value="soft_prompt_only" /><span>Soft prompt only</span></label>
              <label class="chip"><input type="checkbox" name="customer_inputs" value="required_before_bill" /><span>Required before bill</span></label>
              <label class="chip"><input type="checkbox" name="customer_inputs" value="required_before_payment" /><span>Required before payment</span></label>
              <label class="chip"><input type="checkbox" name="customer_inputs" value="required_before_order_confirm" /><span>Required before order confirmation</span></label>
            </div>
          </div>
          <div class="question">
            <h3>Customer inputs before verification</h3>
            <div class="chips">
              <label class="chip"><input type="checkbox" name="pre_verification_inputs" value="name_optional" /><span>Name optional</span></label>
              <label class="chip"><input type="checkbox" name="pre_verification_inputs" value="phone_optional" /><span>Phone optional</span></label>
              <label class="chip"><input type="checkbox" name="pre_verification_inputs" value="email_optional" /><span>Email optional</span></label>
              <label class="chip"><input type="checkbox" name="pre_verification_inputs" value="whatsapp_profile_fallback" /><span>Use WhatsApp name as fallback</span></label>
              <label class="chip"><input type="checkbox" name="pre_verification_inputs" value="otp_fallback_needed" /><span>OTP fallback needed later</span></label>
            </div>
          </div>
        </section>

        <section class="card stack">
          <div>
            <h2>Payments and Messaging</h2>
            <div class="subtle">Put only what is known. Notes are enough if exact fields still need confirmation.</div>
          </div>
          <div class="field-grid">
            <input class="field" name="payment_provider" placeholder="Payment provider (e.g. Razorpay)" />
            <input class="field" name="canonical_order_reference" placeholder="Canonical order reference / mapping key" />
          </div>
          <textarea name="payment_mapping_notes" placeholder="Payment mapping notes: order_id, payment_link_id, receipt, notes, external_order_id, anything relevant."></textarea>
          <div class="question">
            <h3>Required WhatsApp messages</h3>
            <div class="chips">
              <label class="chip"><input type="checkbox" name="required_messages" value="verification_success" /><span>Verification success</span></label>
              <label class="chip"><input type="checkbox" name="required_messages" value="order_summary" /><span>Order summary</span></label>
              <label class="chip"><input type="checkbox" name="required_messages" value="bill" /><span>Bill</span></label>
              <label class="chip"><input type="checkbox" name="required_messages" value="payment_reminder" /><span>Payment reminder</span></label>
              <label class="chip"><input type="checkbox" name="required_messages" value="payment_success" /><span>Payment success</span></label>
              <label class="chip"><input type="checkbox" name="required_messages" value="feedback_request" /><span>Feedback request</span></label>
              <label class="chip"><input type="checkbox" name="required_messages" value="return_to_app" /><span>Return to app</span></label>
              <label class="chip"><input type="checkbox" name="required_messages" value="dish_rating" /><span>Dish rating / review</span></label>
            </div>
          </div>
          <textarea name="messaging_rules_notes" placeholder="Notes: when to use session messages, when templates are needed, outside-window reminders, review flows, etc."></textarea>
        </section>

        <section class="card stack">
          <div>
            <h2>Final Flow Notes</h2>
            <div class="subtle">Describe the actual customer journeys and any missing integration detail in plain language.</div>
          </div>
          <textarea name="production_domain" placeholder="If you already know the real domain or route family, mention it here. Example: app.palate.in/order/:id or web app route not final yet."></textarea>
          <textarea name="final_flow_notes" placeholder="Describe the actual customer flow as you understand it: QR -> menu -> cart -> WhatsApp -> bill -> payment -> feedback, or captain/manual flow, etc."></textarea>
          <textarea name="general_notes" placeholder="Anything else, missing details, risks, or client notes."></textarea>
        </section>

        <div class="submit-row">
          <button id="submit-button" type="submit">Submit integration intake</button>
          <div id="status-box" class="status"></div>
        </div>
      </form>

      <aside class="stack">
        <section class="card">
          <h2>What this gives us</h2>
          <ul class="checklist">
            <li>Real route URLs so demo links can be replaced with actual app or web pages quickly.</li>
            <li>Clear flow coverage across website, mobile app, POS, QR self-serve, and captain paths.</li>
            <li>Specific verification timing decisions instead of vague “capture anywhere” talk.</li>
            <li>Message scope clarity for verification, bill, payment, feedback, and return-to-app paths.</li>
          </ul>
        </section>
        <section class="card">
          <h2>How to use it</h2>
          <ul class="checklist">
            <li>Send this page URL directly to the client or product owner.</li>
            <li>They can tap only the answers they know and write notes for the rest.</li>
            <li>The backend stores the submission so nothing is lost in chat scrollback.</li>
            <li>You can review submissions through the internal API with the existing `X-API-Key`.</li>
          </ul>
        </section>
      </aside>
    </div>
  </div>

  <script>
    const form = document.getElementById("intake-form");
    const statusBox = document.getElementById("status-box");
    const submitButton = document.getElementById("submit-button");

    function valuesFor(name) {
      return Array.from(document.querySelectorAll(`input[name="${name}"]:checked`)).map((node) => node.value);
    }

    function valueFor(name) {
      const node = document.querySelector(`[name="${name}"]`);
      return node ? node.value.trim() : "";
    }

    function showStatus(message, error = false) {
      statusBox.className = `status show${error ? " error" : ""}`;
      statusBox.textContent = message;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      submitButton.disabled = true;

      const payload = {
        respondent_name: valueFor("respondent_name") || null,
        respondent_role: valueFor("respondent_role") || null,
        respondent_email: valueFor("respondent_email") || null,
        respondent_phone: valueFor("respondent_phone") || null,
        provider_primary: "meta",
        provider_backup: null,
        real_urls: {
          menu_url: valueFor("menu_url"),
          order_url: valueFor("order_url"),
          bill_url: valueFor("bill_url"),
          payment_url: valueFor("payment_url"),
          feedback_url: valueFor("feedback_url"),
          return_url: valueFor("return_url"),
        },
        order_sources: valuesFor("order_sources"),
        verification_points: valuesFor("verification_points"),
        customer_inputs: [...valuesFor("customer_inputs"), ...valuesFor("pre_verification_inputs")],
        canonical_order_reference: valueFor("canonical_order_reference") || null,
        payment_provider: valueFor("payment_provider") || null,
        payment_mapping_notes: valueFor("payment_mapping_notes") || null,
        required_messages: valuesFor("required_messages"),
        messaging_rules_notes: valueFor("messaging_rules_notes") || null,
        production_domain: valueFor("production_domain") || null,
        ownership: {},
        final_flow_notes: valueFor("final_flow_notes") || null,
        general_notes: valueFor("general_notes") || null,
      };

      try {
        const response = await fetch("/api/v1/intake/submissions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(result?.error?.message || "Submission failed");
        }
        showStatus(`Saved. Submission ID: ${result.submission_id}`);
        form.reset();
      } catch (error) {
        showStatus(String(error), true);
      } finally {
        submitButton.disabled = false;
      }
    });
  </script>
</body>
</html>"""


@router.get("/intake/palate", response_class=HTMLResponse)
def palate_intake_page() -> HTMLResponse:
    return HTMLResponse(_page_html())


@router.post("/api/v1/intake/submissions", response_model=IntegrationIntakeSubmissionResponse)
def create_intake_submission(
    request: IntegrationIntakeSubmissionRequest,
    db: Session = Depends(get_db),
) -> IntegrationIntakeSubmissionResponse:
    submission = IntegrationIntakeSubmission(
        project_key="palate_whatsapp_phase1",
        status="new",
        respondent_name=_normalize_optional(request.respondent_name),
        respondent_role=_normalize_optional(request.respondent_role),
        respondent_email=_normalize_optional(request.respondent_email),
        respondent_phone=_normalize_optional(request.respondent_phone),
        provider_primary=_normalize_optional(request.provider_primary),
        provider_backup=_normalize_optional(request.provider_backup),
        real_urls=_clean_dict(request.real_urls),
        order_sources=_clean_list(request.order_sources),
        verification_points=_clean_list(request.verification_points),
        customer_inputs=_clean_list(request.customer_inputs),
        canonical_order_reference=_normalize_optional(request.canonical_order_reference),
        payment_provider=_normalize_optional(request.payment_provider),
        payment_mapping_notes=_normalize_optional(request.payment_mapping_notes),
        required_messages=_clean_list(request.required_messages),
        messaging_rules_notes=_normalize_optional(request.messaging_rules_notes),
        production_domain=_normalize_optional(request.production_domain),
        ownership=_clean_dict(request.ownership),
        final_flow_notes=_normalize_optional(request.final_flow_notes),
        general_notes=_normalize_optional(request.general_notes),
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return IntegrationIntakeSubmissionResponse(
        submission_id=submission.id,
        status=submission.status,
        project_key=submission.project_key,
        created_at=submission.created_at,
    )


@router.get(
    "/api/v1/intake/submissions",
    response_model=list[IntegrationIntakeSubmissionItem],
    dependencies=[Depends(require_internal_api_key)],
)
def list_intake_submissions(db: Session = Depends(get_db)) -> list[IntegrationIntakeSubmissionItem]:
    submissions = db.execute(
        select(IntegrationIntakeSubmission).where(IntegrationIntakeSubmission.project_key == "palate_whatsapp_phase1").order_by(
            IntegrationIntakeSubmission.created_at.desc()
        )
    ).scalars()
    return [
        IntegrationIntakeSubmissionItem(
            submission_id=submission.id,
            status=submission.status,
            project_key=submission.project_key,
            respondent_name=submission.respondent_name,
            respondent_role=submission.respondent_role,
            respondent_email=submission.respondent_email,
            respondent_phone=submission.respondent_phone,
            provider_primary=submission.provider_primary,
            provider_backup=submission.provider_backup,
            real_urls=submission.real_urls,
            order_sources=submission.order_sources,
            verification_points=submission.verification_points,
            customer_inputs=submission.customer_inputs,
            canonical_order_reference=submission.canonical_order_reference,
            payment_provider=submission.payment_provider,
            payment_mapping_notes=submission.payment_mapping_notes,
            required_messages=submission.required_messages,
            messaging_rules_notes=submission.messaging_rules_notes,
            production_domain=submission.production_domain,
            ownership=submission.ownership,
            final_flow_notes=submission.final_flow_notes,
            general_notes=submission.general_notes,
            created_at=submission.created_at,
        )
        for submission in submissions
    ]
