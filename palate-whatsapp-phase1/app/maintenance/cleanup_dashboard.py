from __future__ import annotations

import argparse
from datetime import datetime

from sqlalchemy import delete

from app.core.config import Settings
from app.db.models import JourneyEvent, MessageLog, PaymentEvent, WebhookEvent, WhatsAppSession
from app.db.session import get_session_factory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove historical dashboard/test telemetry.")
    parser.add_argument(
        "--before-utc",
        required=True,
        help="Delete dashboard telemetry created before this UTC ISO timestamp.",
    )
    return parser.parse_args()


def parse_cutoff(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    cutoff = datetime.fromisoformat(normalized)
    if cutoff.tzinfo is None:
        raise SystemExit("--before-utc must include timezone, for example 2026-05-13T18:30:00+00:00")
    return cutoff


def main() -> None:
    args = parse_args()
    cutoff = parse_cutoff(args.before_utc)
    settings = Settings()
    session_factory = get_session_factory(settings)
    models = [JourneyEvent, MessageLog, WebhookEvent, PaymentEvent, WhatsAppSession]

    counts: dict[str, int] = {}
    with session_factory() as db:
        for model in models:
            result = db.execute(delete(model).where(model.created_at < cutoff))
            counts[model.__tablename__] = result.rowcount or 0
        db.commit()

    print({"cutoff_utc": cutoff.isoformat(), "deleted": counts})


if __name__ == "__main__":
    main()
