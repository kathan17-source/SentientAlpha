# Local operation and deployment verification

This is a single-user loopback research/simulation application. Local SQLite operation is verified. Native PostgreSQL, Docker runtime and external deployment are **BLOCKED/unverified**. No remote service was published. No authentication, authorization or tenant isolation exists.

## Tested installation

Follow README using Python 3.12, Node 24 and a new virtual environment. Install `requirements-runtime.lock`, then `python -m pip install --no-deps -e .` with normal build isolation. A clean installation was executed. An initial experiment with `--no-build-isolation` failed because fresh environments lack setuptools; it is deliberately absent from the documented instructions. Use `requirements.lock` for developer tests. Optional NLP is not necessary for the default demo; its post-release pinned stack now has a clean advisory scan and real FinBERT compatibility evidence in SECURITY.md.

The demo applies all migrations through **0012_paper_operations** automatically. For an empty manually configured database: `python -m alembic upgrade head`. Do not run integration tests against a database containing user data: fixtures refuse existing tables and downgrade their disposable database at teardown. `DATABASE_URL` is explicit; Python does not automatically load .env. Keep source and data backups separately. Stop the explicit paper worker before modifying a database or release source.

Run FastAPI on `127.0.0.1:8000` and Next on `127.0.0.1:3000`. If using port 8100, set `API_BASE_URL=http://127.0.0.1:8100` on the **Next server process**. These are server settings; never put secrets into NEXT_PUBLIC variables. Custom local frontend ports require matching DASHBOARD_ORIGINS. Default trusted hosts are localhost/loopback and the reserved test-client hostname testserver. Compose additionally allows internal host api. Do not set wildcard hosts/origins or bind host services publicly.

## PostgreSQL next steps (not locally passed)

Native PostgreSQL initdb was executed on this host using installed PostgreSQL binaries:

```sh
initdb -D /tmp/sentientalpha-disposable-pg --auth-local=trust --auth-host=reject --no-locale --encoding=UTF8
```

Actual error: `FATAL: could not create shared memory segment: Operation not permitted`; `shmget(... size=56 ...)`. Network permission was available, but does not grant this OS primitive. No production database was contacted. Earlier PGlite emulation failures are retained in historical reports and are not PostgreSQL certification.

On an authorized native PostgreSQL host, create an empty **disposable** database owned by a dedicated test user. Export TEST_DATABASE_URL with a PostgreSQL+psycopg URL and run the PostgreSQL test list from `.github/workflows/test.yml`, once on each Python version. The workflow uses a disposable PostgreSQL 16 service. Also test native restart persistence and concurrent commands before changing the release classification. Never point the destructive test fixture at a user/production database. Supply actual passwords privately; do not copy CI's publicly labeled ephemeral fixture password into a deployment.

## Containers (static configuration passed; runtime blocked)

The backend uses a slim non-root Python image. The frontend uses a Node 24 multistage build and minimal standalone runtime. API/frontend host ports bind loopback only; PostgreSQL has no host port. Compose orders database health, migrations, API readiness and frontend health. Both application containers have read-only roots, /tmp tmpfs, dropped capabilities and no-new-privileges. PostgreSQL persists in its named volume. No claim of resource quotas or high availability is made.

```sh
# Supply a unique local POSTGRES_PASSWORD in the shell, never commit it.
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
curl -f http://127.0.0.1:8000/ready
curl -f http://127.0.0.1:3000/api/backend/ready
docker compose restart api frontend
# Verify saved session/portfolio and reconcile before deleting any volume.
docker compose down
```

Only the configuration check was executed successfully. Runtime attempt returned `Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?`. No images were built here. Node standalone output builds locally, which does not verify Linux image startup/networking. The Compose stack starts an empty migrated PostgreSQL database, not the SQLite demo: no cross-database copy is implied. Use actual API ingestion/research on that disposable stack and verify the complete operation before claiming deployment success. Do not use `down -v` on data that must be retained.

## Backup and recovery

Local backup was tested with sqlite3's online backup API, followed by `PRAGMA integrity_check`, a new backend process pointed at the backup, exact portfolio equality and paper reconciliation/replay. This is local recovery evidence, not a backup retention/restore SLA. Keep the compatible release source with the database because paper replay intentionally checks its build hash.

With workers stopped and a new backup destination:

```sh
python - <<'PY'
import sqlite3
from pathlib import Path
source, target = Path('demo.db').resolve(), Path('backup.db')
if target.exists():
    raise SystemExit('Refusing to replace a backup')
with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src:
    with sqlite3.connect(target) as dst:
        src.backup(dst)
        assert dst.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
PY
```

Start a fresh API process with DATABASE_URL pointing to the backup. Open the same session, compare persisted cash/positions/fill counts, and use Reconcile before resuming. Never repair discrepancies by manually changing holdings. If source/build or configuration hashes differ, retain the original source and investigate. PostgreSQL backup/restore, disk failure and process supervision remain unverified.

## CI and public hosting

The owner authorized this cleaned source snapshot for the existing private GitHub repository. Current upload and remote CI status are recorded in GITHUB_PORTFOLIO_PREPARATION.md. Earlier source-release checks were local only. Public visibility, deployment and releases remain unauthorized. The configured workflow covers Python 3.12/3.14, disposable PostgreSQL, frontend tests/build/browser setup and runtime/developer dependency/credential guards. It now scans the optional NLP lock as well; a clean version scan is not an arbitrary-model security certification. Public operation additionally needs identity/authorization, isolation, job budgets, rate controls, monitoring, TLS/proxy hardening, comprehensive CSP, backup policies, recovery exercises and intended-environment security review. Those are not implemented or certified by this release.


## Minimal remaining host verification (post-release)

These procedures are provided for a permitted host; they were **not** completed here. The script's CLI/configuration and missing-Docker preflight were checked, but no container workflow pass is claimed. It uses a fresh Compose project, random ephemeral password and retained named volume; it never deletes existing volumes. Ports8000/3000 must be free. No software is installed or system setting changed by the script.

With Docker already enabled by the host owner:

```sh
source .venv/bin/activate
python scripts/verify_infrastructure.py docker
```

This builds/starts the four-service stack, migrates, checks both health endpoints, ingests explicit synthetic AAPL data, creates/advances a paper session through the existing committee/risk/ledger, checks fills, restarts database/API/frontend, compares portfolio/fills, retries the same command and reconciles. It shuts down only its unique project; the printed named volume remains for inspection. A success would provide container runtime evidence only after actually executing it. Inspect failures and preserve diagnostics rather than changing financial assertions.

With a native PostgreSQL server already running on loopback and a local role authorized to create a disposable database:

```sh
python -m pip install -r requirements.lock
createdb sentientalpha_verify_test
export TEST_DATABASE_URL='postgresql+psycopg://localhost/sentientalpha_verify_test'
python scripts/verify_infrastructure.py postgres
```

The script refuses non-loopback targets and database names without `_test`; existing tests also refuse any existing tables. It uses exactly the PostgreSQL file list maintained in the CI workflow, avoiding a divergent second list. Use a fresh empty database for each Python3.12/3.14 execution and run in the matching virtual environment. Supply credentials privately if local authentication requires them. Do not run against a production/user database. PostgreSQL engine restart/concurrent-process operational checks remain necessary after the suite before broad certification; the Docker procedure additionally exercises actual database restart.

For browser/axe review, start the README combined synthetic demo and both servers. On a host whose browser execution is permitted:

```sh
cd frontend
npx playwright install chromium
DASHBOARD_URL=http://127.0.0.1:3000 npm run test:e2e -- offline.spec.ts release.spec.ts
```

This installation is for user execution on the host, not a way around the current tool-policy denial. The release suite collects45 checks:44 route/viewport render/keyboard/overflow/axe checks plus a persisted cash/veto test. It stores real screenshots/axe results only when executed. Current post-release execution was `--list` only; that proves collection, not browser success. The older genuine-data workstation suite requires its documented genuine database and must not be passed off as an offline-demo test. Existing separate paper.spec.ts expects its original single normal paper fixture; CI seeds that separately.

Remote CI remains unexecuted. After the owner explicitly authorizes a repository/remote and publication, push/run the existing workflow and inspect actual logs/artifacts. `workflow_dispatch` is configured, but no remote was created or triggered in this pass. Choose the source license/clear materials first; see LICENSE_REVIEW.md.
