"""Explicit local operator commands; no side effects on import."""

import argparse
import json
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from sentientalpha.config import Settings
from sentientalpha.data.alphavantage import AlphaVantageProvider
from sentientalpha.data.contracts import (
    MarketDataProvider,
    ProviderError,
    ticker_symbol,
    validate_range,
)
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.models import Asset
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.logging import configure_logging
from sentientalpha.services.ingestion import IngestionError, ingest


def main() -> None:
    parser = argparse.ArgumentParser(description="SentientAlpha simulation-only data tools")
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser("seed", help="Load the explicitly synthetic demo universe")
    seed.add_argument("--universe", type=Path, default=Path("config/universe.json"))
    seed.add_argument("--start", type=date.fromisoformat, default=date(2024, 1, 1))
    seed.add_argument("--end", type=date.fromisoformat, default=date(2024, 3, 29))
    seed.add_argument("--seed", type=int, default=42)
    load = commands.add_parser("ingest", help="Explicitly acquire one symbol")
    load.add_argument("ticker", type=ticker_symbol)
    load.add_argument("--provider", choices=["synthetic", "alphavantage"], required=True)
    load.add_argument("--start", type=date.fromisoformat, required=True)
    load.add_argument("--end", type=date.fromisoformat, required=True)
    load.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        validate_range(args.start, args.end)
        provider: MarketDataProvider = SyntheticProvider(args.seed)
        settings = Settings.from_env()
    except ValueError:
        parser.exit(1, "Invalid dates, seed or simulation-only configuration.\n")
    configure_logging()
    engine = make_engine(settings.database_url)
    sessions = session_factory(engine)
    try:
        if args.command == "seed":
            entries = json.loads(args.universe.read_text())["assets"]
            if not 1 <= len(entries) <= 50:
                raise ValueError("Universe must contain 1–50 assets")
            tickers = [ticker_symbol(item["ticker"]) for item in entries]
            if len(set(tickers)) != len(tickers):
                raise ValueError("Universe contains duplicate symbols")
            with sessions.begin() as session:
                for item, ticker in zip(entries, tickers, strict=True):
                    if session.scalar(select(Asset).where(Asset.ticker == ticker)) is None:
                        session.add(
                            Asset(
                                ticker=ticker,
                                name=item["name"],
                                sector=item["sector"],
                                currency="USD",
                            )
                        )
            provider = SyntheticProvider(args.seed)
        else:
            tickers = [args.ticker]
            provider = (
                SyntheticProvider(args.seed)
                if args.provider == "synthetic"
                else AlphaVantageProvider(settings.alpha_vantage_api_key)
            )
        for ticker in tickers:
            run = ingest(sessions, provider, ticker, args.start, args.end)
            print(
                json.dumps(
                    {
                        "run_id": run.id,
                        "ticker": ticker,
                        "provider": provider.name,
                        "inserted": run.inserted,
                        "deduplicated": run.deduplicated,
                        "synthetic": provider.name == "synthetic",
                    }
                )
            )
    except SQLAlchemyError:
        parser.exit(1, "Database operation failed; verify connectivity and run migrations.\n")
    except (ValueError, OSError, KeyError, ProviderError, IngestionError) as exc:
        parser.exit(1, f"{exc}\n")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
