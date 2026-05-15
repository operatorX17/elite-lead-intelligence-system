from __future__ import annotations

import argparse
import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.config import Settings
from app.db.urls import normalize_database_url


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Palate WhatsApp Phase 1 go-live preflight against a deployed or local service."
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Target API base URL. Defaults to PUBLIC_BASE_URL, then http://127.0.0.1:8000.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=15.0,
        help="HTTP timeout for live probes.",
    )
    return parser.parse_args()


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    return Settings()


def resolve_base_url(settings: Settings, requested_base_url: str | None) -> str:
    candidate = requested_base_url or settings.public_base_url or "http://127.0.0.1:8000"
    return candidate.rstrip("/")


def _secret_value(secret: Any) -> str | None:
    if secret is None:
        return None
    if hasattr(secret, "get_secret_value"):
        return secret.get_secret_value()
    return str(secret)


def _safe_json(response: Any) -> dict[str, Any] | None:
    try:
        payload = response.json()
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _response_summary(response: Any) -> str:
    payload = _safe_json(response)
    if payload is not None:
        return json.dumps(payload, sort_keys=True)
    text = getattr(response, "text", "")
    return text.strip() or "<empty>"


def _import_alembic_symbols() -> tuple[Any, Any, Any]:
    original_sys_path = sys.path[:]
    try:
        sys.path = [entry for entry in sys.path if Path(entry or ".").resolve() != PROJECT_ROOT]
        config_module = importlib.import_module("alembic.config")
        script_module = importlib.import_module("alembic.script")
        migration_module = importlib.import_module("alembic.runtime.migration")
    finally:
        sys.path = original_sys_path
    return config_module.Config, script_module.ScriptDirectory, migration_module.MigrationContext


def _build_engine(settings: Settings) -> Engine:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    database_url = normalize_database_url(settings.database_url)
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(database_url, future=True, connect_args=connect_args)


def local_configuration_checks(settings: Settings, base_url: str) -> list[CheckResult]:
    results: list[CheckResult] = []
    missing = settings.missing_required_settings()
    results.append(
        CheckResult(
            name="env.required",
            ok=not missing,
            detail="all required settings present" if not missing else f"missing: {', '.join(missing)}",
        )
    )

    assumption_issues: list[str] = []
    if settings.environment.lower() != "production":
        assumption_issues.append(f"ENVIRONMENT={settings.environment!r} should be 'production'")
    if settings.demo_mode:
        assumption_issues.append("DEMO_MODE must be false for handover")
    if settings.whatsapp_provider == "mock":
        assumption_issues.append("WHATSAPP_PROVIDER=mock is not handover-ready")
    if settings.whatsapp_provider == "meta" and settings.meta_mock_mode:
        assumption_issues.append("META_MOCK_MODE must be false")
    if settings.whatsapp_provider == "meta" and not settings.meta_send_enabled:
        assumption_issues.append("META_SEND_ENABLED must be true")
    if settings.public_base_url and settings.public_base_url.rstrip("/") != base_url:
        assumption_issues.append(
            f"PUBLIC_BASE_URL={settings.public_base_url.rstrip('/')} does not match probe target {base_url}"
        )

    results.append(
        CheckResult(
            name="env.handover_profile",
            ok=not assumption_issues,
            detail="production-oriented flags look correct" if not assumption_issues else "; ".join(assumption_issues),
        )
    )
    return results


def alembic_state_check(settings: Settings) -> CheckResult:
    if not settings.database_url:
        return CheckResult("db.alembic", False, "DATABASE_URL is not configured")

    Config, ScriptDirectory, MigrationContext = _import_alembic_symbols()
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    expected_heads = tuple(script.get_heads())

    try:
        engine = _build_engine(settings)
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_heads = tuple(context.get_current_heads())
    except Exception as exc:
        return CheckResult("db.alembic", False, f"unable to inspect alembic state: {exc}")

    if set(current_heads) != set(expected_heads):
        return CheckResult(
            "db.alembic",
            False,
            f"current={list(current_heads) or ['<none>']} expected={list(expected_heads)}",
        )
    return CheckResult("db.alembic", True, f"at head {', '.join(expected_heads)}")


def live_http_checks(client: Any, settings: Settings, base_url: str) -> list[CheckResult]:
    results: list[CheckResult] = []

    try:
        response = client.get("/health")
        payload = _safe_json(response)
        ok = response.status_code == 200 and payload is not None and payload.get("status") == "ok"
        detail = (
            f"200 {payload.get('service')}" if ok and payload is not None else f"{response.status_code} {_response_summary(response)}"
        )
    except Exception as exc:
        ok = False
        detail = str(exc)
    results.append(CheckResult("http.health", ok, detail))

    try:
        response = client.get("/ready")
        payload = _safe_json(response)
        checks = payload.get("checks", {}) if payload else {}
        ok = (
            response.status_code == 200
            and payload is not None
            and payload.get("ready") is True
            and checks.get("database") == "ok"
            and checks.get("missing_settings") == []
        )
        detail = (
            "ready=true, database=ok, missing_settings=[]"
            if ok
            else f"{response.status_code} {_response_summary(response)}"
        )
    except Exception as exc:
        ok = False
        detail = str(exc)
    results.append(CheckResult("http.ready", ok, detail))

    if settings.internal_api_key is None:
        results.append(CheckResult("http.private_auth", False, "INTERNAL_API_KEY is not configured locally"))
    else:
        expected_key = settings.internal_api_key.get_secret_value()
        try:
            unauthorized = client.get("/api/v1/tracking/summary")
            authorized = client.get("/api/v1/tracking/summary", headers={"X-API-Key": expected_key})
            unauthorized_payload = _safe_json(unauthorized) or {}
            ok = (
                unauthorized.status_code == 401
                and (unauthorized_payload.get("error") or {}).get("code") == "missing_api_key"
                and authorized.status_code == 200
            )
            detail = (
                "401 without key, 200 with key"
                if ok
                else (
                    f"unauthorized={unauthorized.status_code} {_response_summary(unauthorized)}; "
                    f"authorized={authorized.status_code} {_response_summary(authorized)}"
                )
            )
        except Exception as exc:
            ok = False
            detail = str(exc)
        results.append(CheckResult("http.private_auth", ok, detail))

    if settings.whatsapp_provider == "meta":
        verify_token = _secret_value(settings.meta_verify_token)
        if verify_token is None:
            results.append(CheckResult("webhook.meta_verify_get", False, "META_VERIFY_TOKEN is not configured locally"))
        else:
            try:
                response = client.get(
                    "/webhooks/meta/whatsapp",
                    params={
                        "hub.mode": "subscribe",
                        "hub.challenge": "preflight",
                        "hub.verify_token": verify_token,
                    },
                )
                ok = response.status_code == 200 and response.text == "preflight"
                detail = "verification challenge echoed" if ok else f"{response.status_code} {_response_summary(response)}"
            except Exception as exc:
                ok = False
                detail = str(exc)
            results.append(CheckResult("webhook.meta_verify_get", ok, detail))

        try:
            response = client.post("/webhooks/meta/whatsapp", content=b"{}")
            payload = _safe_json(response) or {}
            ok = response.status_code == 401 and (payload.get("error") or {}).get("code") == "meta_signature_invalid"
            detail = "unsigned request rejected with meta_signature_invalid" if ok else f"{response.status_code} {_response_summary(response)}"
        except Exception as exc:
            ok = False
            detail = str(exc)
        results.append(CheckResult("webhook.meta_signature_guard", ok, detail))

    try:
        response = client.post("/webhooks/payments/razorpay", content=b"{}")
        payload = _safe_json(response) or {}
        ok = response.status_code == 401 and (payload.get("error") or {}).get("code") == "razorpay_signature_invalid"
        detail = "unsigned request rejected with razorpay_signature_invalid" if ok else f"{response.status_code} {_response_summary(response)}"
    except Exception as exc:
        ok = False
        detail = str(exc)
    results.append(CheckResult("webhook.razorpay_signature_guard", ok, detail))

    if settings.whatsapp_provider == "twilio" and settings.twilio_webhook_auth_enabled:
        if not settings.public_base_url:
            results.append(
                CheckResult(
                    "webhook.twilio_signature_guard",
                    False,
                    "PUBLIC_BASE_URL must be set when probing signed Twilio assumptions",
                )
            )
        else:
            try:
                response = client.post(
                    "/webhooks/twilio/whatsapp",
                    data={
                        "From": "whatsapp:+919999999999",
                        "To": "whatsapp:+14155238886",
                        "Body": "preflight",
                        "MessageSid": "SMpreflight",
                    },
                )
                payload = _safe_json(response) or {}
                ok = response.status_code == 401 and (payload.get("error") or {}).get("code") == "twilio_signature_invalid"
                detail = (
                    "unsigned request rejected with twilio_signature_invalid"
                    if ok
                    else f"{response.status_code} {_response_summary(response)}"
                )
            except Exception as exc:
                ok = False
                detail = str(exc)
            results.append(CheckResult("webhook.twilio_signature_guard", ok, detail))

    return results


def print_results(results: list[CheckResult], base_url: str) -> None:
    print(f"Palate WhatsApp Phase 1 preflight target: {base_url}")
    for result in results:
        prefix = "PASS" if result.ok else "FAIL"
        print(f"{prefix:4} {result.name:<32} {result.detail}")

    failed = [result for result in results if not result.ok]
    print("")
    if failed:
        print(f"HANDOVER READY: NO ({len(failed)} failed check{'s' if len(failed) != 1 else ''})")
    else:
        print("HANDOVER READY: YES")


def run_preflight(base_url: str, timeout_seconds: float) -> int:
    settings = load_settings()
    results = local_configuration_checks(settings, base_url)
    results.append(alembic_state_check(settings))

    timeout = httpx.Timeout(timeout_seconds)
    transport = httpx.HTTPTransport(retries=0)
    try:
        with httpx.Client(base_url=base_url, timeout=timeout, transport=transport, follow_redirects=False) as client:
            results.extend(live_http_checks(client, settings, base_url))
    except Exception as exc:
        results.append(CheckResult("http.connectivity", False, str(exc)))

    print_results(results, base_url)
    return 0 if all(result.ok for result in results) else 1


def main() -> int:
    args = parse_args()
    settings = load_settings()
    base_url = resolve_base_url(settings, args.base_url)
    return run_preflight(base_url=base_url, timeout_seconds=args.timeout_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
