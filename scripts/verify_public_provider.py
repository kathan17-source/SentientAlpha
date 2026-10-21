"""Opt-in live verification using Alpha Vantage's public IBM sample, without private keys."""

import argparse
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.config import Settings
from sentientalpha.data.calendar import sessions_in_range
from sentientalpha.data.contracts import validate_range


def main() -> None:
    from datetime import date

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    validate_range(args.start, args.end)
    root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="sentientalpha-public-") as directory:
        database_url = f"sqlite:///{Path(directory) / 'verification.db'}"
        prior = {
            name: os.environ.get(name)
            for name in ("DATABASE_URL", "DATABASE_PASSWORD", "SENTIENTALPHA_MODE")
        }
        try:
            os.environ["DATABASE_URL"] = database_url
            os.environ["SENTIENTALPHA_MODE"] = "simulation"
            os.environ.pop("DATABASE_PASSWORD", None)
            command.upgrade(Config(str(root / "alembic.ini")), "head")
        finally:
            for name, value in prior.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        settings = Settings(database_url=database_url, alpha_vantage_api_key="demo")
        request = {
            "ticker": "IBM",
            "provider": "alphavantage",
            "start": str(args.start),
            "end": str(args.end),
        }
        params = {key: value for key, value in request.items() if key != "ticker"}
        with TestClient(create_app(settings)) as client:
            assert client.get("/ready").status_code == 200
            first = client.post("/api/market/ingest", json=request)
            if first.status_code != 201:
                print(
                    json.dumps(
                        {
                            "status": "FAILED",
                            "http_status": first.status_code,
                            "failure": first.json(),
                        }
                    )
                )
                raise SystemExit(1)
            repeated = client.post("/api/market/ingest", json=request)
            assert repeated.status_code == 201
            prices = client.get("/api/market/IBM", params=params).json()["prices"]
            expected = [str(day) for day in sessions_in_range("XNYS", args.start, args.end)]
            assert [row["session_date"] for row in prices] == expected
            assert all(
                row["provider"] == "alphavantage"
                and not row["is_synthetic"]
                and row["adjustment_status"] == "not_supplied"
                and row["adjusted_close"] is None
                for row in prices
            )
            assert repeated.json()["inserted"] == 0
            assert repeated.json()["deduplicated"] == len(prices)
            synthetic = client.post("/api/market/ingest", json={**request, "provider": "synthetic"})
            assert synthetic.status_code == 201
            real_after = client.get("/api/market/IBM", params=params).json()["prices"]
            assert real_after == prices
            assert client.get("/api/market/UNKNOWN", params=params).status_code == 404
            assert (
                client.post(
                    "/api/market/ingest",
                    json={**request, "start": str(args.end), "end": str(args.start)},
                ).status_code
                == 422
            )
        with TestClient(create_app(settings)) as restarted:
            assert restarted.get("/api/market/IBM", params=params).json()["prices"] == prices
        print(
            json.dumps(
                {
                    "status": "VERIFIED",
                    "provider": "alphavantage",
                    "access": "public IBM demo",
                    "start": str(args.start),
                    "end": str(args.end),
                    "rows": len(prices),
                    "sessions": expected,
                    "synthetic": False,
                    "price_basis": "raw",
                    "adjusted_close": "not supplied",
                    "corporate_actions": "not supported by this adapter",
                    "repeated_inserted": repeated.json()["inserted"],
                    "repeated_deduplicated": repeated.json()["deduplicated"],
                    "persisted_after_app_restart": True,
                    "synthetic_source_isolated": True,
                    "quality_state": first.json()["quality_report"]["state"],
                    "private_credentials_used": False,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
