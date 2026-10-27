# Verification and remaining gates

This cleanup branch is independently based on merged main `e36d976`; it does not include the separate browser repair in [PR #3](https://github.com/kathan17-source/SentientAlpha/pull/3). Do not treat results from that branch as passes of this checkout. After both owner-reviewed PRs are merged, run the combined tree again before changing its publication status.

## Executed baseline, before cleanup

The source-publication verification reproduced Python 3.12: 606 tests + 11 subtests with the optional pinned cached FinBERT, and Python 3.14 core: 605 + 11 with one optional-model skip. Frontend component baseline: 59 tests. The synthetic demo generated five fills, a separate paused zero-fill veto session, equivalent replay and exact portfolio persistence across an API restart; 38 HTTP checks passed. These are historical executed results, not presumed cleanup reruns.

Hosted CI at application revision `4a2bfeb` passed both Python core suites (605 + 11 subtests, one optional skip each), actual PostgreSQL 16 integration (198 passed, two SQLite-specific process-death cases skipped each), and security. Its combined browser suite completed with 4 passes and 45 failures involving label locators/duplicate h1; route axe/layout assertions were not reached. No browser/accessibility success is claimed for unmodified main. [Historical run](https://github.com/kathan17-source/SentientAlpha/actions/runs/39690184592).

## Reproduce authorized local checks

Follow the owner/authorized-evaluator setup in the root README. Install requirements.lock for developer checks. Run `python -m pytest -q`, `python -m ruff check .`, `python -m ruff format --check .`, `python -m mypy`, and `python scripts/release_scan.py`. Run frontend `typecheck`, `lint`, `format:check`, `test`, `generate:api` and `build` scripts. The OpenAPI generator must not change `frontend/types/openapi.ts` unexpectedly.

The combined synthetic demo applies migrations through `0012_paper_operations`. Use a new database/report path, then check persisted paper fills, cash/holdings, risk-veto session and replay. Against the migrated demo, `python -m alembic check` should report no new upgrade operations. Run destructive integration fixtures only against an empty disposable test database.

On a permitted browser host, use the existing offline/release browser suites against the combined demo, and the paper suite against its independent fixture. Tests cover all eleven routes at 1440, 1280, 820 and 390 pixels, keyboard/overflow/axe and actual cash/veto behavior. Configuration or assertions alone do not prove they passed. Cleanup-specific results and full file classifications are recorded in the cleanup PR and owner's local evidence.

## Remaining limitations

Docker application runtime/restart and intended deployment are unverified; native local PostgreSQL initialization was blocked by shared-memory policy even though hosted PostgreSQL integration subsequently passed. Local browser tooling was restricted; hosted results are reported separately. Full manual accessibility, sustained availability, disk-failure recovery, production identity/authorization/tenancy, complete CSP and operational security are not certified. Version locks are not artifact-hash or container-digest supply-chain certification. The retained httpx test-client warning is a compatibility limitation, not a failed financial assertion.

Public source visibility is a separate owner decision from publicly exposing a financial application. Neither is authorized by a test pass. Keep loopback-only operation, simulation-only modes and independent third-party/model/provider terms.
