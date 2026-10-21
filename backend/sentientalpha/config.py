"""Explicit environment configuration; real execution cannot be enabled."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default="sqlite:///./sentientalpha.db", repr=False)
    finbert_cache_dir: str = ""
    mode: str = "simulation"
    alpha_vantage_api_key: str = field(default="", repr=False)

    trusted_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "[::1]", "testserver")
    trusted_origins: tuple[str, ...] = (
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    )

    def __post_init__(self) -> None:
        if self.mode not in {"simulation", "paper"}:
            raise ValueError("Only simulation and paper modes are supported")
        if not self.database_url.startswith(("sqlite:", "postgresql+psycopg:")):
            raise ValueError("Use SQLite or PostgreSQL with the psycopg driver")

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = os.getenv("DATABASE_URL", "sqlite:///./sentientalpha.db")
        password = os.getenv("DATABASE_PASSWORD")
        if password is not None:
            from sqlalchemy.engine import make_url
            from sqlalchemy.exc import ArgumentError

            try:
                parsed = make_url(database_url)
                if parsed.drivername != "postgresql+psycopg" or not password:
                    raise ValueError("A nonempty DATABASE_PASSWORD is only valid for PostgreSQL")
                database_url = parsed.set(password=password).render_as_string(hide_password=False)
            except ArgumentError:
                raise ValueError("Invalid database configuration") from None
        return cls(
            database_url=database_url,
            finbert_cache_dir=os.getenv("FINBERT_CACHE_DIR", ""),
            trusted_hosts=tuple(
                os.getenv("TRUSTED_HOSTS", "127.0.0.1,localhost,[::1],testserver").split(",")
            ),
            trusted_origins=tuple(
                os.getenv(
                    "DASHBOARD_ORIGINS",
                    "http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:8000,http://localhost:8000",
                ).split(",")
            ),
            mode=os.getenv("SENTIENTALPHA_MODE", "simulation"),
            alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY", ""),
        )
