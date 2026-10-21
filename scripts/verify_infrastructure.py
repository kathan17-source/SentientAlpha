"""Host-only infrastructure verification. Does not install software or delete volumes."""

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str], env: dict[str, str]) -> None:
    subprocess.run(args, cwd=ROOT, env=env, check=True, timeout=1200)


def request(path: str, body: dict | None = None, port: int = 8000) -> dict:
    q = urllib.request.Request(
        f"http://127.0.0.1:{port}" + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(q, timeout=120) as response:
        return json.load(response)


def postgres(env: dict[str, str]) -> None:
    import yaml
    from sqlalchemy.engine import make_url

    url = make_url(env.get("TEST_DATABASE_URL", ""))
    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"127.0.0.1", "localhost"}
        or not (url.database or "").endswith("_test")
    ):
        raise SystemExit("Use loopback PostgreSQL with an EMPTY disposable database ending _test")
    workflow = yaml.safe_load((ROOT / ".github/workflows/test.yml").read_text())
    step = next(
        s for s in workflow["jobs"]["verify"]["steps"] if "TEST_DATABASE_URL" in s.get("env", {})
    )
    run([sys.executable, "-m", *step["run"].split()], env)


def docker(env: dict[str, str]) -> None:
    if shutil.which("docker") is None:
        raise SystemExit("BLOCKED: Docker CLI absent; enable Docker on the host first")
    for port in [8000, 3000]:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                raise SystemExit(
                    f"Port {port} busy; stop only the service you own before verification"
                )
    env = {**env, "POSTGRES_PASSWORD": secrets.token_urlsafe(32)}
    project = "sentientalpha-verify-" + str(os.getpid())
    compose = ["docker", "compose", "-p", project]
    try:
        run(compose + ["config", "--quiet"], env)
        run(compose + ["up", "--build", "-d", "--wait", "--wait-timeout", "180"], env)
        request("/ready")
        request("/api/backend/ready", port=3000)
        request(
            "/api/market/ingest",
            {"ticker": "AAPL", "provider": "synthetic", "start": "2024-01-02", "end": "2024-04-12"},
        )
        row = request(
            "/api/paper/sessions",
            {
                "key": "host-verification-create",
                "mode": "synthetic_demo",
                "tickers": ["AAPL"],
                "provider": "synthetic",
                "capital": "10000",
                "history_start": "2024-01-02",
                "simulation_start": "2024-04-01",
                "committee_policy": {
                    "effective_at": "2023-12-31T00:00:00Z",
                    "minimum_independent_groups": 1,
                },
                "risk_policy": {
                    "id": "host-verification",
                    "version": "1",
                    "effective_at": "2023-12-31T00:00:00Z",
                    "constraints": {"cash_maximum": 1, "concentration": 0.4},
                    "estimator": {"minimum_observations": 20},
                },
            },
        )
        path = "/api/paper/sessions/" + row["id"]
        for action in ["ready", "start"]:
            request(path + "/" + action, {"key": "host-" + action})
        command = {"key": "host-advance", "maximum_events": 5}
        request(path + "/advance", command)
        before = request(path)["portfolio"]
        fills = request(path + "/fills")["items"]
        assert fills, "No actual simulated fills"
        run(compose + ["restart", "db", "api", "frontend"], env)
        for attempt in range(60):
            try:
                request("/api/backend/ready", port=3000)
                break
            except OSError:
                if attempt == 59:
                    raise
                time.sleep(1)
        assert request(path)["portfolio"] == before
        request(path + "/advance", command)
        assert request(path)["portfolio"] == before
        assert request(path + "/fills")["items"] == fills
        assert request(path + "/reconcile", {"key": "host-reconcile"})["data"]["equivalent"]
        print("VERIFIED: synthetic container workflow, DB/service restart and ledger replay")
    finally:
        subprocess.run(compose + ["down"], cwd=ROOT, env=env, check=False, timeout=120)
        print(f"Isolated project {project}; any created named volume retained, no volume deleted")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=["postgres", "docker"])
    args = parser.parse_args()
    (postgres if args.target == "postgres" else docker)(dict(os.environ))


if __name__ == "__main__":
    main()
