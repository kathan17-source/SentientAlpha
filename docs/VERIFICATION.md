# Verification and operational limits

[Verified v0.12.0 CI](https://github.com/kathan17-source/SentientAlpha/actions/runs/40454261882) executed the checks below. These establish software behavior under the tested fixtures, not predictive alpha, complete accessibility or deployment readiness. See the [demo](../DEMO.md) and [screenshot provenance](PORTFOLIO_REVIEW.md#screenshot-provenance) for synthetic evidence.

## Executed verification

| Check                                                            | Executed result                                                                                    |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Combined offline/release/screenshot browser suite                | 52 passed, zero failed/skipped                                                                     |
| Independent paper browser suite                                  | 4 passed, zero failed/skipped                                                                      |
| Route/viewport accessibility, headings, visible focus and layout | 44 passed: eleven routes × 1440/1280/820/390 px; zero axe violations                               |
| Frontend                                                         | 62 tests; types, lint, format, unchanged API generation and production build passed                |
| Python 3.12 and 3.14 core, each                                  | 605 passed + 11 subtests; one optional-model skip                                                  |
| PostgreSQL 16 integration, each Python                           | 198 passed; two SQLite-only process-death tests skipped                                            |
| Security                                                         | Core/developer/NLP and npm audits found zero known vulnerabilities; configured source guard passed |

The SQLite core suite covers process-death recovery. The combined demo applies migrations through `0012_paper_operations`, produces five normal-session fills and a separate PAUSED zero-fill risk veto, and verifies equivalent replay for both. Paper browser checks confirm pause persistence after reload without changing holdings or fills. These are simulation and persistence checks, not evidence of profitable operation.

## Reproduce authorized checks

Follow the [README setup](../README.md#installation-and-offline-demonstration). For developer checks:

```sh
python -m pip install -r requirements.lock
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m mypy
npm --prefix frontend run generate:api
git diff --exit-code -- frontend/types/openapi.ts
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend test
npm --prefix frontend run build
python scripts/release_scan.py
```

Optional real-model verification requires the pinned NLP dependencies, independently licensed model cache and `RUN_FINBERT=1`; the core CI suite deliberately skips that test. No model weights are bundled. See [sentiment setup](SENTIMENT_ENGINEERING.md) and [model terms](../THIRD_PARTY_MATERIALS.md).

Use new disposable database/report paths with `scripts/release_demo.py`. Against that migrated database, `python -m alembic check` should report no new upgrade operations. Destructive integration fixtures must never target personal or production data. The [CI workflow](../.github/workflows/test.yml) records the PostgreSQL 16 service, explicit integration-test list and `TEST_DATABASE_URL` configuration; a configured job is not itself a passing result.

On a permitted browser host, start the demo API and production frontend as in [DEMO.md](../DEMO.md), then run:

```sh
npm --prefix frontend run test:e2e -- offline.spec.ts release.spec.ts portfolio.spec.ts
```

Run `paper.spec.ts` separately against `scripts/paper_demo.py`'s independent synthetic fixture. Set `DASHBOARD_URL` to its frontend and `API_BASE_URL` on that frontend to the matching API. The workflow demonstrates this on separate ports. Never substitute a genuine-data database for these fixtures.

CI uploads only four named synthetic PNGs after successful browser checks, retained for three days. Failure diagnostics are uploaded only for private repositories; that upload is disabled for this public repository. Databases, environments, model caches and server logs are not uploaded.

## Remaining limits

Docker application runtime/restart and deployment remain unverified. Automated browser/axe checks do not certify full manual accessibility or screen-reader behavior. Sustained availability, disk-failure recovery, production authentication/authorization/tenancy, complete CSP and operational security are not certified. Version locks are not artifact-hash or container-digest supply-chain certification. Dependency audits and the configured source guard are not exhaustive security guarantees.

The production build retains an existing warning about importing a named version from package.json; it passes. The backend tests retain an httpx test-client deprecation warning. Neither warning is a failed financial assertion.

The repository is public source for inspection, not a hosted financial application. Keep loopback-only operation, simulation-only modes and independent third-party/model/provider terms. [LICENSE](../LICENSE) grants no general execution or reuse permission; review [SECURITY.md](../SECURITY.md) before authorized operation.
