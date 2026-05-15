from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_engine
from app.main import create_app
from app.preflight import alembic_state_check, live_http_checks, local_configuration_checks, _import_alembic_symbols


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def build_settings(tmp_path: Path) -> Settings:
    return Settings.model_validate(
        {
            "environment": "production",
            "DATABASE_URL": f"sqlite+pysqlite:///{tmp_path / 'preflight.db'}",
            "INTERNAL_API_KEY": "internal-test-key",
            "SESSION_TOKEN_PEPPER": "pepper-test",
            "WHATSAPP_PROVIDER": "meta",
            "DEMO_MODE": False,
            "PUBLIC_BASE_URL": "http://testserver",
            "PALATE_WHATSAPP_NUMBER": "+919999999999",
            "META_VERIFY_TOKEN": "verify-me",
            "META_APP_SECRET": "meta-secret",
            "META_ACCESS_TOKEN": "meta-token",
            "META_PHONE_NUMBER_ID": "123456",
            "META_SEND_ENABLED": True,
            "META_MOCK_MODE": False,
            "RAZORPAY_WEBHOOK_SECRET": "rzp-secret",
        }
    )


def test_local_configuration_checks_pass_for_handover_profile(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    results = local_configuration_checks(settings, "http://testserver")
    assert all(result.ok for result in results)


def test_alembic_state_check_reports_head_revision(tmp_path: Path, monkeypatch) -> None:
    settings = build_settings(tmp_path)
    monkeypatch.setenv("DATABASE_URL", settings.database_url or "")

    Config, _, _ = _import_alembic_symbols()
    command = importlib.import_module("alembic.command")
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    command.upgrade(config, "head")

    result = alembic_state_check(settings)
    assert result.ok is True
    assert "20260511_0004" in result.detail


def test_live_http_checks_cover_ready_auth_and_signature_guards(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    engine = get_engine(settings)
    Base.metadata.create_all(bind=engine)

    with TestClient(create_app(settings)) as client:
        results = live_http_checks(client, settings, "http://testserver")

    by_name = {result.name: result for result in results}
    assert by_name["http.health"].ok is True
    assert by_name["http.ready"].ok is True
    assert by_name["http.private_auth"].ok is True
    assert by_name["webhook.meta_verify_get"].ok is True
    assert by_name["webhook.meta_signature_guard"].ok is True
    assert by_name["webhook.razorpay_signature_guard"].ok is True
