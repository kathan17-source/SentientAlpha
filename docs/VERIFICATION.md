# Verification and remaining gates

The cleanup was initially prepared independently on main `e36d976`. The owner subsequently merged [browser repair PR #3](https://github.com/kathan17-source/SentientAlpha/pull/3). This cleanup branch is now updated from reviewed main `527ef48`, so it includes those existing browser/dependency fixes while its diff remains documentation and evidence cleanup only. No PR was merged by the assistant. Current cleanup CI is visible in [PR #4 checks](https://github.com/kathan17-source/SentientAlpha/pull/4/checks); no pending run is presumed green.

## Executed verification

[Browser repair CI](https://github.com/kathan17-source/SentientAlpha/actions/runs/40447148226) passed on repair revision `b1b9fbb`, whose code was merged into main:

| Check | Executed result |
|---|---|
| Hosted combined offline/release browser suite | 51 passed, zero failed/skipped |
| Hosted standalone paper suite | 4 passed, zero failed/skipped |
| Route/viewport axe, layout, visible focus, headings and runtime errors | 44 passed: eleven routes × 1440/1280/820/390 px; zero axe violations |
| Hosted component/static/build checks | 60 component tests; types, lint, format, API generation and production build passed |
| Hosted Python 3.12/3.14 core, each | 605 passed + 11 subtests; one optional-model skip |
| Hosted PostgreSQL 16 integration, each Python | 198 passed, two SQLite-only process-death tests skipped |
| Hosted security | Core/developer/NLP and npm scans and strengthened source guard passed |

The optional filelock/setuptools advisory findings were fixed with minimal pins in the browser repair. Model weights remain external and independently licensed. Local Python 3.12 with the patched optional stack and trusted pinned FinBERT passed 606 tests + 11 subtests. A separate local composition of browser fixes and cleanup passed 606 backend tests + 11 subtests, 60 component tests, static/build checks and the source guard; it was byte-identical to this branch before documentation status updates.

Cleanup-only checks on the initially independent tree passed Python 3.12 606 + 11 subtests and Python 3.14 605 + 11 with one optional skip, 59 component tests, static/build checks, full SQLite migrations and alembic check. A new combined synthetic demo generated five fills, an independent paused zero-fill veto and equivalent replay in both. Its production Next/API stack passed 38 actual HTTP checks. A fresh API process preserved exact portfolio values, five fills and equivalent replay. Removing historical evidence did not require changing source, fixtures or assertions. Initial cleanup CI correctly exposed inherited browser/advisory failures before the reviewed fixes were brought in; those historical failures remain recorded.

## Reproduce authorized checks

Follow the owner/authorized-evaluator setup in README. Install requirements.lock for developer checks. Run `python -m pytest -q`, `python -m ruff check .`, `python -m ruff format --check .`, `python -m mypy`, and `python scripts/release_scan.py`. Run frontend `typecheck`, `lint`, `format:check`, `test`, `generate:api` and `build`. API generation must not change `frontend/types/openapi.ts` unexpectedly.

The combined synthetic demo applies migrations through `0012_paper_operations`. Use a new database/report path; compare persisted cash/holdings, fills, veto session and replay. Against that migrated demo, `python -m alembic check` should report no new upgrade operations. Destructive integration fixtures require a fresh disposable test database.

On a permitted browser host, run the existing offline/release suites against the combined demo and paper suite against its independent synthetic fixture. Current CI retains failure diagnostics privately for three days; it does not upload databases, private environments, model caches or server logs. The standalone paper suite runs even after a combined-suite failure without masking the failed workflow.

## Remaining limits

Docker application runtime/restart and intended deployment remain unverified; native local PostgreSQL initialization was blocked by shared-memory policy even though hosted PostgreSQL integration passed. Local browser tooling was restricted; hosted execution supplies the rendered evidence. Full manual accessibility, sustained availability, disk-failure recovery, production identity/authorization/tenancy, complete CSP and operational security are not certified. Version locks are not artifact-hash or container-digest supply-chain certification. The retained httpx test-client deprecation warning is not a failed financial assertion.

Public source visibility remains an explicit owner decision, separate from publicly deploying a financial application. Neither is authorized by these test results. Keep loopback-only operation, simulation-only modes and independent third-party/model/provider terms.
