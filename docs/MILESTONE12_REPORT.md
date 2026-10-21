# SentientAlpha — Milestone 12 final engineering report

Historical M12 delivery snapshot. Current dependency/hygiene status: [post-release verification](../POST_RELEASE_VERIFICATION.md). Original outcomes remain recorded below.

Date: 2026-10-21 America/Chicago. Release: **0.12.0 local research/simulation**.

Status labels describe executed evidence, not aspirations. Full evidence: [VERIFICATION_M12.json](VERIFICATION_M12.json), [inventory](M12_INVENTORY.md), [issue register](M12_ISSUE_REGISTER.md), [integration matrix](M12_INTEGRATION_MATRIX.md).

## 1. Final project status

VERIFIED local core research/simulation release v0.12.0. Milestone12 stabilization completed within the available local environment. Deployment Verified and Production Ready are **NO**. No Git repository, public service, external artifact upload or brokerage capability was created. Optional NLP remains security-restricted. See VERIFICATION_M12.json for machine-readable distinctions.

## 2. Exact implemented scope

Added local Host/Origin/fetch-metadata boundary and actual-byte 2MiB request cap; bounded Next request streaming; frontend permissions headers; corrected paper freshness from session start age to last successful processing; added after-commit failure hook and real process-death regressions. Added frontend standalone Docker configuration, dual-Python/security CI configuration, a combined offline demo, credential guard and release documentation. No predictive model, agent, strategy, ledger or executor was added.

## 3. Architecture verification

VERIFIED existing component ownership via actual synthetic research and paper integration, retained numerical/time-safety regressions and HTTP retrieval. Source adapters → M2 features → actual M6/M7 research → M8 evidence/abstention → M5 proposals → independent M9 gates → M4 execution/Decimal ledger → persisted artifacts → FastAPI/BFF are exercised. News/model integration is separately tested; a complete genuine all-agent corpus-to-forward-performance experiment is not claimed. See M12_INVENTORY.md and M12_INTEGRATION_MATRIX.md.

## 4. Files added and modified

New backend API security module and seven-case release test file; new frontend streamed-body test; scripts/release_demo.py and release_scan.py; frontend/Dockerfile; root release docs; inventory, issue register, matrix, verification JSON and evidence. Modified API/config/paper storage, frontend BFF/config/version, package metadata, certifi pins, Compose/ignore/CI, OpenAPI, README/architecture/roadmap/sample env. RELEASE_MANIFEST.json enumerates final paths/hash/size and changes against M11. All 53 earlier test/migration files are byte-identical; existing detailed reports remain preserved.

## 5. Integration audit results

VERIFIED: clean combined demo persists actual feature/model/discovery/optimization/backtest/committee records, five simulated paper fills, and independent veto session with zero fills. Both paper sessions replay. Thirty-eight real Next/FastAPI HTTP requests check eleven HTML routes, catalog and artifact retrieval, fill counts, reconciliation and forbidden mutation origin. Actual API JSON is response-model validated; generated OpenAPI types refresh successfully. Deep flexible evidence payloads still use generic runtime objects; compile-time types and envelope validation are not exhaustive nested schema proof. No rendered UI claim follows from HTML HTTP200.

## 6. PostgreSQL verification

BLOCKED. Installed native PostgreSQL initdb was executed with disposable data path, trust-local/reject-host authentication and no external connection. Bootstrap failed: FATAL could not create shared memory segment: Operation not permitted; shmget size56. Network permission does not grant this macOS primitive. Evidence: verification/milestone12/postgres-init.txt. No native tests passed and no emulation is substituted. Affects database/deployment certification, not verified local SQLite operation. Next: on an authorized native host create an empty disposable PG16 database, export TEST_DATABASE_URL, execute the exact integration list in .github/workflows/test.yml on 3.12/3.14, then test native restart/concurrency. No authorized external database or Git remote was available.

## 7. Docker verification

PARTIALLY VERIFIED configuration; runtime BLOCKED. Added actual frontend build/runtime configuration and internal API URL. Compose parsed with four services and required password; official Compose config --quiet passed. Compose ps failed: Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Images, Linux dependencies, startup/networking, shutdown, named-volume restart and container resource behavior were not executed. Local standalone Node build/server syntax passes only. Next: use DEPLOYMENT.md commands on a permitted daemon, exercise fresh migration/research/paper state and restart; do not infer success from configuration.

## 8. Remote CI verification

PARTIALLY VERIFIED configuration, remote execution BLOCKED. Source has no Git repository/authorized remote, so no workflows were dispatched or uploaded. YAML parsed locally. Configured Python3.12/3.14 with PG16 disposable service, full regressions and PG integration list, frontend types/lint/tests/build/browser setup, pip-audit, npm audit and source credential guard. Local equivalent checks passed where executable. Next: obtain explicit remote/publication authorization, then run/inspect actual GitHub Actions; attach run URL/results before calling CI passed. Existing workflow browser configuration does not override current local policy restrictions.

## 9. Security findings and fixes

VERIFIED targeted local controls and scans, not a security certification. Direct API Host/Origin checks now precede handlers; opaque/foreign origins and cross-site browser metadata are refused. Both layers bound actual streamed request bytes before handler/forwarding. Fixed upstream/path/mutation allowlists, sanitized errors, no credential forwarding, no unsafe HTML/news execution and independent risk gates remain. No general Python eval/exec or uploaded pickle model path was found in reviewed production source. Local unauthenticated processes remain authorized by machine access; public identity/tenancy/rate isolation is NOT IMPLEMENTED and blocks public exposure. See SECURITY.md and prioritized M12_ISSUE_REGISTER.md.

## 10. Dependency audit

Actual pip-audit runtime: zero known advisories; developer lock after certifi2026.10.19: zero; npm audit: zero. Optional combined NLP scan returns nine advisory records for Transformers4.57.6, six unique IDs (duplicates in upstream records). Those findings remain OPEN and block untrusted model artifacts/public NLP deployment. The default runtime/Docker/demo omit NLP. Fixed certifi in developer/NLP locks and retested cached inference. No scanner ignore-list or untested broad major upgrade was introduced. Version locks do not include complete wheel hashes; no bit-for-bit reproducibility claim. Initial scanner cache-permission failure was resolved using /tmp explicit cache; actual final JSON reports are included.

## 11. Financial research integrity audit

VERIFIED retained golden-reference/temporal regressions on both Python versions: future price/news perturbations, non-backdated revisions, training-only preprocessing, matured labels, purging/embargo, separate calibration, locked holdout, model historical eligibility, committee policy/evidence clocks, risk as-of returns and next-observed-close order eligibility. Ledger equity remains cash plus marked holdings; M4 returns/Sharpe/Sortino/drawdown, costs and M5 covariance/weights/M9 empirical tails retain existing conventions. No numerical formula was changed to improve performance. Freshness correction changes operational pause logic only. Fixtures do not establish genuine data completeness or unbiased alpha.

## 12. Historical data limitations

Genuine IBM short retrospective evidence stays **−8.70% committee versus −4.69% buy-and-hold**. Risk controls reduced reported exposure/losses without demonstrating alpha. Current-symbol universe can be survivorship-biased; historical point-in-time macro/fundamental/sentiment coverage is incomplete; publication/revision/retrieval clocks differ. Third-party market/news/model rights and licensing require independent review. Raw genuine/private data and model caches are excluded from the source archive.

## 13. Machine-learning evaluation limitations

VERIFIED synthetic training/calibration/replay engineering, not out-of-sample market profitability. Missing eligible inputs, expired/historically unavailable models and tampered numeric artifacts fail/abstain in retained tests. Small calibration/test samples, multiple comparisons, regime drift and unavailable genuine features limit empirical interpretation. Predictive probabilities are not returns or validated alpha. FinBERT smoke demonstrates cached functionality only, not calibrated trading edge or resolved package advisories.

## 14. Strategy discovery research findings

VERIFIED bounded declarative search/persistence and holdout controls. Demo executes six actual candidates and preserves failures; already-inspected holdouts are labeled. No strategy was added or selected using future locked outcomes. Discovery rankings are exploratory and do not establish profitable untouched prospective performance. Earlier negative/robustness reports remain in docs.

## 15. Multi-agent evaluation findings

VERIFIED evidence/provenance, policy eligibility, persisted decision traces and abstention controls. Agents do not fabricate absent sentiment/fundamental/macro coverage or acquire execution authority. Combined synthetic committee calls existing optimizer/risk/execution. Genuine IBM committee underperformed its baseline; no all-agent genuine alpha claim or optimistic reclassification was introduced.

## 16. Independent risk enforcement results

VERIFIED M9 pre-trade, pending-order/fill-time and post-fill actual-holdings evaluations through existing M4 pipeline. Clean combined veto session pauses with insufficient tail data and no fills; normal session has five fills and reconciles. Undefined risk is not treated as zero; proposal weights are separate from holdings and rejected orders from fills. Tail estimates remain sample-limited; local enforcement correctness is not institutional risk calibration.

## 17. Paper-trading atomicity and recovery verification

VERIFIED real SQLite transactions and child processes, retaining existing lifecycle/concurrent-worker/fill uniqueness tests. New subprocess exits73 immediately after an actual fill is flushed (before commit), and separately after economic event/checkpoint commit but before confirmation. Before-commit case has no new durable fill; after-commit case has one. Same-command retry resumes frozen planned days; each yields exactly one new fill, identical cash/positions/equity on subsequent retry and equivalent replay. No distributed exactly-once or PostgreSQL certification. Fresh forward observations no longer expire merely because session start was over48h ago; genuinely stale inactivity still pauses.

## 18. Frontend functionality

VERIFIED 59 tests in8 files, strict TypeScript, ESLint/Prettier, production and standalone builds, clean npm install/build/types and38 actual transport checks. Eleven routes cover overview, security research, portfolio, committee, strategy lab, backtesting, sentiment, risk, ML, experiment history and paper. Existing simulation/synthetic labels, undefined numbers, cancellation/error/loading/empty states and source distinctions are preserved. Security Research is /research rather than a nonexistent extra route. New Permissions-Policy and bounded mutation stream add no decorative redesign.

## 19. Browser visual verification

BLOCKED. Fresh permitted CUA inventory was available, but selecting the in-app tab was rejected by URL security policy (requested protocol not allowed, despite listed allowed http/https). Exact tool diagnostic is archived. Policy expressly forbade alternate browser/raw-CDP workarounds; none was attempted. No current screenshot, responsive-layout, hydration/console or rendered chart claim. Historical M10 browser evidence remains historical. Affects visual/deployment assurance, not HTTP/core results. Next: use a genuinely permitted environment and run the supplied browser workflows after authorization/policy support.

## 20. Accessibility verification

PARTIALLY VERIFIED component semantics/tests only; rendered automated axe and manual keyboard/focus/screen-reader/contrast/reduced-motion/responsive review are BLOCKED with browser access. Do not call accessibility fully verified. Existing Playwright/axe setup remains provided; run on a permitted CI/local browser at desktop/laptop/tablet/mobile widths and inspect every major route. No fabricated screenshot or accessibility result is included.

## 21. Performance benchmarks

VERIFIED local synthetic measurements, not an SLA or market-data benchmark. macOS ARM64, Python3.12; other checks ran concurrently. Parent process peak RSS excludes child peak; SQL counts cover the instrumented pre-restart operation. One asset uses5 market events, larger runs3; do not compare as equivalent workloads.

| Assets | Events | Advance seconds | Replay seconds | Parent peak MiB | SQL statements | Fills |
|---|---|---|---|---|---|---|
| 1 | 5 | 0.346 | 0.086 | 241.50 | 300 | 2 |
| 5 | 3 | 0.439 | 0.097 | 251.92 | 313 | 5 |
| 20 | 3 | 1.788 | 0.654 | 373.91 | 737 | 12 |
| 50 | 3 | 6.021 | 2.741 | 873.14 | 1405 | 21 |

Each JSON includes ingestion, session creation, features/committee/risk/execution stage times, commit, API, separate-process recovery and full total. Risk/evidence persistence and replay dominate larger runs; no speculative optimization was applied. Full-stack HTTP timings are in http-verification.json and clean Next startup reported101ms; these are individual local observations, not browser rendering, p95 or a service guarantee. Separate cached FinBERT test2.46s includes test setup/inference and is not isolated inference latency. CPU utilization, startup distribution and browser responsiveness were not measured. Historical M6/M7 benchmarks remain workload-specific; no incompatible speedup claim.

## 22. Backend automated test results

VERIFIED Python3.12: **605 passed,1 optional skipped,+11 subtests**,86.50s. Python3.14: **605 passed,1 optional skipped,+11 subtests**,89.34s. Seven new M12 cases; original598 maintained. Cached real FinBERT optional smoke separately **1 passed,2.46s** on3.12 after certifi update. Ruff all checks passed,231 files formatted, mypy126 source modules clean; dependency consistency checks pass in both environments. Existing Starlette TestClient/httpx deprecation warning remains. Native PostgreSQL cases were not run locally.

## 23. Frontend automated test results

VERIFIED **59 passed in8 files**,1.11s final Vitest run; original58 tests preserved plus missing-length oversized-body adversary. Strict types, lint, format and production build pass; local standalone build/server syntax also pass. Fresh copied source with npm ci/build/type generation passes. Browser/axe runs are unexecuted due the stated policy blocker. Tests and builds do not replace rendered inspection.

## 24. Fresh installation results

VERIFIED new Python3.12 virtual environment: pinned runtime dependencies, normal build-isolated editable install, pip check, complete fresh migration/demo and real API startup. New frontend directory with no node_modules/.next: npm ci, production build and strict types passed, startup101ms. Initial --no-build-isolation trial failed missing setuptools; corrected tested quick-start omits that flag. No paid key/GPU/model download required. Python3.14 full regressions also pass, but this clean-install exercise used3.12. This host evidence is not Linux/Windows/container certification.

## 25. Reproducible demonstration results

VERIFIED one clean SQLite database containing actual synthetic M1/M2, M4–M9 research artifacts and two M11 sessions. Clean demo normal session:5 fills; veto session:0 fills/PAUSED; both replay equivalent. Saved IDs/provenance included in sanitized clean-demo.json. Actual38 Next/FastAPI checks retrieve them. API stopped → actual BFF503 backend_unavailable; online SQLite backup integrity_check ok → new API using restored database → identical portfolio and reconcile/replay pass. Frontend/API owned services stopped at end; closed ports confirmed. DEMO.md provides5–10 minute narrative, startup/restart and negative-results context. Dates/UUIDs vary; database bytes are not claimed reproducible.

## 26. Deployment readiness classification

**A Local Research Ready: VERIFIED** for documented core SQLite setup. **B Local Simulation Ready: VERIFIED** within tested single-user persistence/concurrency limits. **C Reproducible Demo Ready: VERIFIED** clean setup and actual combined workflow. **D Deployment Verified: NO/BLOCKED** native PostgreSQL, Docker runtime, remote CI and current rendered checks. **E Production Ready: NO/NOT IMPLEMENTED** required public identity/isolation, operational monitoring, backup policies and intended-environment validation. Optional NLP advisories additionally restrict that optional environment. Version0.12.0 is deliberately a local release, not institutional production certification.

## 27. Known unresolved issues

See prioritized M12_ISSUE_REGISTER.md. Native PG shmget restriction; unavailable Docker daemon; no authorized remote CI; browser URL policy; optional Transformers advisory records; untested OS disk-full/device-loss behavior and sustained availability; test-client deprecation; unhashed dependency artifacts/non-digest container tags. Exact diagnostics, attempts, affected scope and next steps are in sections6–10,19–20 and DEPLOYMENT/SECURITY. No arbitrary/public deployment can be approved on this evidence. No established genuine alpha or long forward track record exists; those are research limits rather than solved software defects.

## 28. Security restrictions

Local loopback single-user only. No tunnels/public reverse proxy; no wildcard Host/Origin; no real credentials/DB/model cache in source; no arbitrary uploaded strategy/model. Browser boundary is not authentication. Optional vulnerable NLP stack must not process untrusted model artifacts or be exposed publicly; default core/demo excludes it. Actual disk exhaustion, PostgreSQL backups and public operational controls are not certified. Source signature scan is a limited guard, not exhaustive secret discovery. Nothing was published, uploaded or deployed externally.

## 29. Source archive verification

VERIFIED by final packaging checks recorded in the external DELIVERY sidecar: per-source-path SHA256/size manifest (manifest excludes its own recursive hash), archive CRC test, exact archived hash comparison, protected baseline comparison and prohibited private-artifact/path checks. Source ZIP excludes databases, credentials/private .env, virtual environments, node_modules, .next, caches/model downloads, generated private research, temporary logs and compiled artifacts. Small sanitized verification evidence and deterministic fixture generators are included. RELEASE_MANIFEST.json lists all source changes; external archive SHA256/size/file count are in SentientAlpha-Milestone-12-DELIVERY.json. Previous milestone ZIPs remain preserved. No third-party raw corpus/license rights are implied.

## 30. Final recommendation for project presentation

Present as a rigorous local engineering portfolio: reproducible data lineage, temporal discipline, numeric references, independent governance, explicit abstention, durable economic effects and honest negative research. Demonstrate actual saved results and process recovery with synthetic provenance visible. Cite the negative IBM comparison and unresolved optional NLP/deployment/visual checks proactively. Do not advertise profitable alpha, institutional production readiness or live performance. The original twelve-milestone local software scope stops here; further deployment/research certification requires separately authorized work.
