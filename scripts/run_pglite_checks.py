"""Opt-in fallback only. Requires a running PGlite socket and TEST_DATABASE_URL.

Disables client prepared statements because the fallback multiplexer shares a backend.
This is not a substitute for native PostgreSQL tests. Every failure remains a failure.
"""

import os
import sys

import pytest
from sqlalchemy import Engine, event


def configure_client(connection: object, record: object) -> None:
    if hasattr(connection, "prepare_threshold"):
        connection.prepare_threshold = None


def main() -> None:
    if not os.environ.get("TEST_DATABASE_URL"):
        raise SystemExit("Supply a disposable PGlite TEST_DATABASE_URL explicitly")
    event.listen(Engine, "connect", configure_client)
    raise SystemExit(pytest.main(sys.argv[1:]))


if __name__ == "__main__":
    main()
