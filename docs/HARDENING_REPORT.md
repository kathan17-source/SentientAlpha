# SentientAlpha — Milestone 1 engineering hardening report

Date: October 13, 2026, America/Chicago. Version: 0.1.1.
Scope: audit/harden existing M1, perform feasible integration checks, prepare M2 infrastructure.
**No feature engine or other Milestone 2 implementation was started.** Existing module layout
and application architecture were preserved. Original migration 0001 is byte-for-byte unchanged.

## 1. Original status

Baseline reproduced: 40 tests passed, 11 subtests, Ruff passed, one Starlette deprecation warning.
The original implementation actually supported typed API ingestion/reads, deterministic synthetic
prices, SQLite migrations, revision-aware as-of filtering, audit runs and simulation-only settings.
Its synthetic dataset had 24 symbols × 65 weekdays = 1,560 bars. Provider success/failure behavior
was mocked; no real acquisition, PostgreSQL, Docker or type check had been verified.
No features, NLP, predictive models, strategy discovery, agents, optimizer, backtests, frontend
or paper execution existed. Their documentation described future milestones, not working code.

## 2. Problems found and fixes

| Finding / original weakness | Change and evidence |
|---|---|
| SQLite NUMERIC silently loses large-price decimals | Reproduced `900000000001.12345678 -> 900000000001.12341309`. Added dialect-specific exact decimal type: PostgreSQL NUMERIC / SQLite fixed-width text. Exact/max-price round trips pass. Lossy SQLite downgrade refused. Legacy conversion is explicitly flagged and audited. |
| Source records had no market-close/acquisition distinction or adjustment status | Added scheduled session close, observation/acquisition time, calendar, currency, adjustment status, revision numbers and quality flags. Legacy unknown values stay unknown. |
| Metadata integer/list could raise raw AttributeError/TypeError | Explicit symbol/timezone shape validation; sanitized ProviderError regression tests. Foreign venue suffixes rejected, avoiding accidental USD labeling. |
| Public demo request received entitlement failure | Actual canonical public endpoint succeeded while adapter's explicit outputsize request failed. Adapter now uses canonical default-compact URL for public demo access; live IBM ingestion verified. |
| Dates used weekday intuition / strict calendar-boundary rejection | XNYS calendar validation with holiday, early-close and DST tests. Weekend/holiday boundary handling uses actual expected sessions. Weekday synthetic model remains separately labeled. |
| Missing sessions and suspicious discontinuities unreported | Persisted quality reports for missing dates, >30% absolute adjacent raw-close moves and source conflicts. No fill, adjustment or automatic suspicious-price repair. |
| Duplicate JSON keys silently overwritten by JSON parser | Reject duplicate transport fields before parsing prices; regression test. |
| Tied ingestion timestamps ordered by random UUID | Deterministic per-asset/source/session revision sequence with uniqueness constraint and tie regression. Corrections/reversions retained. |
| Locking an asset row did not cover first concurrent creation | PostgreSQL transaction advisory lock keyed by ticker; SQLite BEGIN IMMEDIATE before reads. Four-thread SQLite first-import test passes. Native PostgreSQL multiprocess test remains unverified. |
| Availability/ingestion consistency and synthetic attribution not constrained in DB | Added timestamp, provenance, currency, adjustment, finite bounds and revision CHECK/UNIQUE constraints. Negative SQLite tests exercise actual constraints. |
| Unexpected provider exception could leave running audit | Catch/sanitize unexpected failures and mark failed attempt. If DB failure prevents audit completion, log sanitized audit-unavailable event; do not falsely claim success. Process crashes still require future job recovery. |
| Default validation responses echo invalid request input | Typed error envelope suppresses submitted input; accidental-secret request regression. UUID run-ID validation and bounded asset reads added. |
| Type checking had never run; five original errors | Fixed provider protocol variance, nullable ORM retrieval and CLI provider unions. Mypy now checks all application modules with untyped definitions prohibited. |
| Connection timeouts/disposal incomplete | Bounded PostgreSQL connect/statement/lock timeouts; hidden SQL parameters; API lifespan and failed migrations dispose engines. Connection-refusal API returns 503 while liveness remains 200. |
| Existing rollback test failed before SQL was emitted | Fault injection now runs after insert, so DB writes actually precede rollback. Additional real duplicate-key test flushes a successful insert, then violates a constraint and verifies rollback. |
| PostgreSQL password interpolated directly into URL | Separate DATABASE_PASSWORD is URL-encoded via SQLAlchemy; special-character regression passes. No private password/key requested. |
| Docker root-owned working dir broke optional SQLite mode; runtime included dev tools | Writable /data owned by nonroot user, separate runtime lock, read-only/capability-restricted Compose API and excluded generated build metadata. Configuration verified; image build remains blocked. |
| Verification claims lacked explicit execution boundaries | Added live/HTTP/environment evidence, exact file-change inventory, status matrix and truthful README/architecture updates. |

All prices normalize to documented eight-decimal precision at the domain boundary; synthetic
math and its modeled calendar remain test data. Original SQLite precision lost before this
pass cannot be repaired by a migration. New data storage preserves accepted decimal values.

## 3. Critical-component status matrix

VERIFIED means the named behavior was executed successfully in the stated environment;
PARTIALLY VERIFIED means evidence exists but important paths remain unverified;
BLOCKED means the required environment/data is unavailable; FAILED identifies actual failures.

| Component | Classification | Evidence / remaining limit |
|---|---|---|
| SQLite ingestion/revisions/idempotency | **VERIFIED** | Real database writes, as-of/source queries, corrections/reversions, four concurrent first imports |
| SQLite price precision/integrity | **VERIFIED** | Exact/max supported decimal round trips; database checks; audited legacy migration; lossy downgrade refusal |
| SQLite migration/model agreement | **VERIFIED** | Three revisions, fresh upgrade/down, schema drift, legacy preservation; original demo upgraded after backup |
| API startup/health/readiness/OpenAPI | **VERIFIED** | ASGI request-to-DB tests plus running Uvicorn HTTP smoke; v0.1.1, 24 assets, bounded price page |
| Typed input/errors/pagination | **VERIFIED** | Invalid ranges/seeds/IDs, unknown assets, empty assets, provider/internal failures, DB refusal and secret-safe errors |
| Simulation restriction | **VERIFIED** | Invalid live mode rejected; literal false health flag; no broker/order implementation or endpoint |
| Real Alpha Vantage raw sample | **VERIFIED** for public IBM sample | Seven real Oct 1–9 bars persisted/repeated/restarted/source-isolated; not broad-universe coverage |
| Real provider wider operation | **PARTIALLY VERIFIED** | Timeouts/retries/429/malformed data mocked; actual entitlement failure observed earlier; no private quota exhaustion or full historical universe |
| Corporate actions/adjusted series | **BLOCKED** | Not implemented by the existing raw compact adapter; no split/dividend ledger or adjusted close acquisition |
| Quality diagnostics/source conflicts | **PARTIALLY VERIFIED** | Actual public sample calendar/provenance; controlled gaps/jumps/conflicts. No real-feed anomaly study or missing-session repair |
| Native PostgreSQL 16 | **BLOCKED** | Native 16.2 binary downloaded; initdb denied shared-memory syscall, including mmap settings |
| PostgreSQL dialect fallback | **PARTIALLY VERIFIED** | Real PostgreSQL 18.6 WASM/PGlite engine via psycopg/SQLAlchemy; many schema/read/write/API paths passed |
| Fallback post-error transaction handling | **FAILED** | Full fallback run: 23 passed, 3 failed, 2 setup errors. Rollback returned zero results; later authentication protocol state failed |
| Native PostgreSQL concurrency/rollback/persistence | **BLOCKED** | Cannot certify multiprocess server behavior through a single-user WASM multiplexer; CI remains required |
| Compose configuration | **VERIFIED** | Official Compose v2.39.4 `config --quiet`, actual command successful |
| Docker image/services/volume restart | **BLOCKED** | Runtime/dry-run cannot connect to absent daemon; not claimed as passing |
| Lint/format/types/dependencies | **VERIFIED** | Ruff; 19 application modules under Mypy; pip consistency in fresh Python 3.12 and Python 3.14 |
| Remote deployment controls | **PARTIALLY VERIFIED** | Loopback exposure/nonroot configuration checked. Auth, TLS, quotas, separate DB roles, restore drills not delivered; no public deployment |
| Historical research inputs / historical universe | **BLOCKED** | Only compact real sample and current-symbol synthetic universe; PIT coverage, delistings, actions and long history absent |

## 4. Exact checks and actual results

| Executed | Result |
|---|---|
| Baseline Python 3.14.5 pytest | 40 passed; 11 subtests |
| Final Python 3.12.15 complete suite | **82 passed; 11 subtests; zero skipped** |
| Final Python 3.14.5 complete suite | **82 passed; 11 subtests; zero skipped** |
| Ruff lint / format | Passed |
| Mypy | Passed; 19 application modules; type holes at third-party calendar boundary use explicit Any |
| `pip check` | Passed in both interpreters; fresh 3.12 pinned install and editable package build successful |
| Compile backend/migrations/scripts | Passed |
| SQLite migration drift (`alembic check`) | Passed in tests and upgraded original demo |
| Four-thread SQLite first ingestion | 1 asset, 4 stored prices, 12 deduplicated across four successful runs |
| Hardened demo after legacy backup/upgrade | Added 1,560 new version-2 snapshots; prior snapshots retained; next same-seed run inserted 0/deduplicated 1,560 |
| Actual public-provider verification script | 7 real IBM bars; repeated ingestion 0 inserts/7 deduplicated; restart preserved data; synthetic records isolated |
| Running HTTP smoke | `/health`, `/ready`, assets, market page and generated OpenAPI passed |
| Official Compose configuration | Passed |
| Compose runtime attempt | Failed to connect to absent Docker daemon — **BLOCKED**, not a passing smoke test |
| Native PostgreSQL initdb | Failed on sandbox `shmget` — **BLOCKED** |
| Final fallback suite | **23 passed, 3 failed, 2 setup errors**, no skipped tests |
| Isolated fallback exact-price/max-price probes after restart | **2 passed**; full-suite failures remain unresolved and explicitly reported |

The fallback suite had 28 test cases. Four independently exercise local SQLite, connection
refusal or configuration, so 23 passes do **not** mean 23 distinct PostgreSQL-backed behaviors.
The verifier disables prepared statements only in its client hook: the fallback multiplexer
shares a backend and otherwise collides on prepared names. Application production code is not
modified to hide fallback failures. The failed tests were timestamp violation, duplicate-price
violation and duplicate-asset rollback. Two later setup errors reported invalid authentication
protocol state. Native PostgreSQL must pass the regular suite without this hook.

One Starlette httpx deprecation warning persists in each Python suite. It is not a skipped
check. Frontend checks are inapplicable because the frontend remains a planned milestone.

### What is mocked or injected

Provider contract/transport tests deliberately supply payloads for 429, timeouts, malformed
JSON, symbol/timezone errors, missing sessions and quota messages. Controlled provider classes
exercise conflicting sources, gaps and jumps. ORM insert-failure tests inject an exception after
actual SQL insertion. These prove failure behavior, not that live quotas or feed anomalies were
observed. Live public IBM and local HTTP/API tests use actual network responses and databases.
Database-unavailable tests connect to a reserved non-listening local port, not a mocked ORM.

## 5. Security findings

No private environment files, private keys or AWS key patterns were found in the deliverable;
no private environment file or credential was requested/read for this task. Public `demo` and
explicit dummy test values are not private credentials. CI credentials are solely for ephemeral
local services. Pattern scanning is a bounded audit, not a guarantee against every secret format.
Application logging/errors suppress provider URLs, submitted invalid input and SQL bind values.
Provider host is fixed; inputs are typed and SQL values parameterized. There is no dynamic
strategy execution, broker adapter or real-order code. Simulation-only mode remains enforced.

The service is local and unauthenticated. Public hosting, request quotas, user authorization,
separate least-privilege PostgreSQL roles and backup-restore certification remain future gates.
Downloaded binaries, raw provider payload, environments, execution logs and backup DB are scratch
artifacts outside the packaged source. Source archives exclude caches, .env, databases and
build metadata. The original demo was backed up before migration and its revisions preserved.

## 6. Milestone 2 assessment

**Ready for local feature-engine development using controlled data. Not certified for production
PostgreSQL or research-valid historical investment experiments.**

Existing boundaries support explicit session windows, UTC cutoffs, provider isolation, missingness,
revision manifests and multi-asset collection. M2 must define warmup/null handling, exact indicator
formulas, corporate-action policy, historical reconstruction versus strict PIT, universe membership
and chronological target/split rules. A 65-weekday-per-asset synthetic sample and seven real IBM
bars cannot establish ML validity or trading performance. Native DB/container and data-coverage
gates remain open. See [MILESTONE2_READINESS.md](MILESTONE2_READINESS.md).

## 7. Evidence and reproduction

- Live public data verification (`verification/public-provider.json`, intentionally omitted; see PUBLICATION_SELECTION.md)
- [Running HTTP and legacy-demo verification](verification/http-smoke.json)
- [Environment/security/blocked checks](verification/environment-security.json)
- [Exact source change manifest](verification/changes.json)
- [Generated current OpenAPI](openapi.json)

Run `pytest -q`, `ruff check .`, `ruff format --check .`, `python -m mypy`, `pip check`, and
`alembic check`. Native DB verification uses the normal integration command in README on an
empty disposable PostgreSQL 16 database. For public sample access, use the opt-in verification
script with dates within the actual returned compact range. No private credentials are needed.

The native alternative was the pip-distributed [pgserver binary package](https://github.com/orm011/pgserver).
The fallback's [single-user/multiplexing limits](https://pglite.dev/docs/pglite-socket) explain why
its successes cannot establish native server concurrency. Session validation follows the
[exchange calendar library](https://github.com/gerrymanoim/exchange_calendars). Provider scope
and public request shape are grounded in [official Alpha Vantage documentation](https://www.alphavantage.co/documentation/).

## 8. Exact files added or modified

The following inventory is generated against the initial source snapshot. Files not listed
remain unchanged; generated caches/build metadata are excluded. No repository rewrite occurred.

| File | Change |
|---|---|
| `.dockerignore` | MODIFIED |
| `.env.example` | MODIFIED |
| `.github/workflows/test.yml` | MODIFIED |
| `.gitignore` | MODIFIED |
| `Dockerfile` | MODIFIED |
| `README.md` | MODIFIED |
| `backend/sentientalpha/__init__.py` | MODIFIED |
| `backend/sentientalpha/api/app.py` | MODIFIED |
| `backend/sentientalpha/api/schemas.py` | MODIFIED |
| `backend/sentientalpha/cli.py` | MODIFIED |
| `backend/sentientalpha/config.py` | MODIFIED |
| `backend/sentientalpha/data/alphavantage.py` | MODIFIED |
| `backend/sentientalpha/data/calendar.py` | ADDED |
| `backend/sentientalpha/data/contracts.py` | MODIFIED |
| `backend/sentientalpha/data/quality.py` | ADDED |
| `backend/sentientalpha/data/synthetic.py` | MODIFIED |
| `backend/sentientalpha/database/models.py` | MODIFIED |
| `backend/sentientalpha/database/repository.py` | MODIFIED |
| `backend/sentientalpha/database/session.py` | MODIFIED |
| `backend/sentientalpha/services/ingestion.py` | MODIFIED |
| `backend/tests/test_domain.py` | MODIFIED |
| `backend/tests/test_hardening_domain.py` | ADDED |
| `backend/tests/test_hardening_integration.py` | ADDED |
| `backend/tests/test_integration.py` | MODIFIED |
| `compose.yaml` | MODIFIED |
| `docs/ARCHITECTURE.md` | MODIFIED |
| `docs/DATABASE.md` | MODIFIED |
| `docs/HARDENING_REPORT.md` | ADDED |
| `docs/METHODOLOGY.md` | MODIFIED |
| `docs/MILESTONE2_READINESS.md` | ADDED |
| `docs/ROADMAP.md` | MODIFIED |
| `docs/VALIDATION.md` | MODIFIED |
| `docs/openapi.json` | MODIFIED |
| `docs/verification/changes.json` | ADDED |
| `docs/verification/environment-security.json` | ADDED |
| `docs/verification/http-smoke.json` | ADDED |
| `docs/verification/public-provider.json` | ADDED |
| `migrations/env.py` | MODIFIED |
| `migrations/versions/0002_data_contract.py` | ADDED |
| `migrations/versions/0003_exact_sqlite_prices.py` | ADDED |
| `pyproject.toml` | MODIFIED |
| `requirements-runtime.lock` | ADDED |
| `requirements.lock` | MODIFIED |
| `scripts/run_pglite_checks.py` | ADDED |
| `scripts/verify_public_provider.py` | ADDED |
