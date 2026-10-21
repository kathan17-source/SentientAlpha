"""Optional bounded local poller. Must remain running; no always-on claim."""

import argparse
import signal
import threading
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.config import Settings
from sentientalpha.data.alphavantage import AlphaVantageProvider
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.base import new_id, now
from sentientalpha.database.session import make_engine, serialize_writer, session_factory
from sentientalpha.paper.contracts import Advance, Create, Update
from sentientalpha.paper.storage import advance, append, digest, error, existing, get
from sentientalpha.services.ingestion import ingest


def update(
    sessions: sessionmaker[Session], id: str, q: Update, settings: Settings
) -> dict[str, Any]:
    request = q.model_dump(mode="json")
    with sessions() as s:
        serialize_writer(s, "paper:" + id)
        row = get(s, id)
        old = existing(s, id, q.key, request)
        if old:
            return old.payload["result"]
        if row.status not in {"READY", "RUNNING", "PAUSED"} or row.mode == "historical_replay":
            raise error("Data updates require an operational paper session")
        config = Create.model_validate(row.configuration)
    # M1 owns provider timeouts/rate-limit diagnostics and idempotent revisions.
    runs = []
    try:
        provider = (
            SyntheticProvider()
            if config.provider == "synthetic"
            else AlphaVantageProvider(settings.alpha_vantage_api_key)
        )
        for t in config.tickers:
            run = ingest(sessions, provider, t, q.start, q.end)
            runs.append(run.id)
        result = {
            "status": "updated",
            "ingestion_runs": runs,
            "provider": config.provider,
            "at": now().isoformat(),
        }
    except Exception:
        result = {
            "status": "provider_update_failed",
            "ingestion_runs": runs,
            "provider": config.provider,
            "at": now().isoformat(),
            "reason": (
                "See sanitized M1 ingestion diagnostics; a new command key is required "
                "for an explicit retry."
            ),
        }
    with sessions() as s:
        serialize_writer(s, "paper:" + id)
        row = get(s, id)
        old = existing(s, id, q.key, request)
        if old:
            return old.payload["result"]
        if result["status"] != "updated":
            row.warning = "provider_update_failed; no fabricated prices"
        append(
            s, row, q.key, "provider_update", {"request_hash": digest(request), "result": result}
        )
        s.commit()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    if not 10 <= args.poll_seconds <= 86400 or not 1 <= args.iterations <= 10000:
        parser.error("Bounded polling/iteration values required")
    settings = Settings.from_env()
    engine = make_engine(settings.database_url)
    sessions = session_factory(engine)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    try:
        for iteration in range(args.iterations):
            if stop.is_set():
                break
            if args.fetch:
                end = now().date() - timedelta(days=1)
                update(
                    sessions,
                    args.session,
                    Update(key="worker-update-" + new_id(), start=end - timedelta(days=7), end=end),
                    settings,
                )
            try:
                advance(sessions, args.session, Advance(key="worker-advance-" + new_id()))
            except Exception:
                # No uncertain in-memory queue is retried. Durable state is inspected next run.
                with sessions() as s:
                    serialize_writer(s, "paper:" + args.session)
                    row = get(s, args.session)
                    if row.status == "RUNNING":
                        row.status = "PAUSED"
                        row.warning = (
                            "worker_failure; inspect durable events and reconcile before resume"
                        )
                        append(
                            s,
                            row,
                            "worker-error-" + new_id(),
                            "worker_failure",
                            {"reason": row.warning},
                        )
                        s.commit()
            if iteration + 1 == args.iterations or stop.wait(args.poll_seconds) or stop.is_set():
                break
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
