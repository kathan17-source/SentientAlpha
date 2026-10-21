# SentientAlpha — Milestone 11 delivery report

Version0.11.0 · schema0012_paper_operations · local verification2026-10-20 America/Chicago (UTC logs extend into2026-10-21).

## 1. Overall milestone completion status

**COMPLETE for local simulation engineering, with browser and deployment verification limitations.** Persistent sessions, explicit controls, forward clocks, M8/M5/M9/M4 reuse, atomic economic effects, restart recovery, typed APIs and the connected Paper Trading page are implemented. Engine/API/recovery tests are VERIFIED. Frontend visual end-to-end QA is PARTIALLY VERIFIED/BLOCKED as described below. No genuine forward-fill track record, production reliability or alpha is claimed. Milestone12 is not started.

## 2. Architecture decisions

VERIFIED. Existing M4 execute/Ledger remain the only financial engine. Existing M2 snapshots, M8 CommitteeStrategy, M5 solver and M9 governance/storage are called directly. Paper tables add operational identities, immutable configuration, command plans, event chain and unique fill receipts. Computation is local and bounded, with an optional standalone polling process; no Redis/Celery/Kafka or distributed exactly-once promise. [Operating design](PAPER_TRADING.md).

## 3. Files added and modified

VERIFIED. Added `paper/contracts.py`, `paper/storage.py`, `paper/worker.py`, operational ORM models, migration0012, typed API router and42 paper tests. Added `/paper` route/view, mode/lifecycle helpers, component/proxy tests and3 browser cases. Added demo/reconciliation scripts. App router/schema registration, research catalog exclusions, shell/proxy/contracts/version/CI and documentation updated. [Exact changes](CHANGESET_M11.json), [source hashes](SOURCE_SHA256_M11.json). All original backend/frontend test and migration files remain byte-identical to M10.

## 4. Simulation modes

VERIFIED. Forward mode uses actual processing/receipt clocks; synthetic mode uses explicit virtual-clock observations with actual processing timestamps separately retained; historical replay is a non-running reference to existing M4 research. Mode/provider are immutable and validated. Paper financial carriers and committee parents are excluded from historical catalogs to prevent curve/result mixing. No historical backfill is claimed as a past forward decision.

## 5. Session lifecycle implementation

VERIFIED. CREATED→READY→RUNNING, explicit pause/resume and terminal STOPPED, with FAILED for processing integrity errors. Creation does not start processing. Resume validates frozen history and projections; stopped sessions cannot restart. Paused ingestion can retain data but changes no holdings/checkpoint. Stop cancels outstanding orders through audit, without changing fills. Administrative keys are idempotent; differing reuse conflicts.

## 6. Market-data processing rules

VERIFIED for supported daily sources. Existing M1 bounded explicit updates retain provenance, availability/ingestion clocks and failures. Forward selects newly received complete sessions after start; pre-start/delayed bars become catch-up without trades. Missing/flagged/revised/current-valuation data fail closed. Missed active-portfolio windows pause and require pending-order cancellation before explicit recovery. Historical data never fills earlier orders at a previously observed open. Source/quality/revision limitations are documented rather than repaired silently.

## 7. Order lifecycle implementation

VERIFIED. Stable order IDs, M4 order artifacts and unique IOC fill receipts. Created/pending-risk/approved/queued transitions are retained; queued is distinct from filled. Fresh risk veto produces REJECTED. Actual partial fills record PARTIALLY_FILLED then CANCELLED remainder. Cancellation/expiry reasons and exact shares/costs/times/risk references are durable. Only one allocation batch remains outstanding; pending commitments enter M9, and M4 cash sufficiency is authoritative. No separate reservation account is claimed.

## 8. M8 Investment Committee integration

VERIFIED for technical/available evidence, with explicit missing-agent abstention. Actual M8 recommendations, aggregation/dependencies, M5 allocation and evidence clocks are persisted per paper decision. Current quantities/cash come from M4. NO_TRADE/maintain/reject are allowed; no training or discovery job is triggered. Optional M3/M6 eligibility is inherited from audited source adapters. Genuine forward sentiment/ML skill remains unverified.

## 9. M5 optimization integration

VERIFIED. The existing committee adapter invokes the existing M5 numerical estimation/solver and residual constraint review. Past source data and feature versions are frozen. Proposed targets remain separate from M9 approval and actual filled weights in the workstation. Existing optimizer failures/insufficient estimates do not become fabricated allocations.

## 10. M9 risk veto integration

VERIFIED. Independent M9 checks before queuing, fresh checks before each M4 fill with pending commitments, and post-fill actual-state monitoring. Hard limits cannot be bypassed by UI/committee. Actual fresh-fill vetoes were retained. A configured VaR-limit demonstration paused on INSUFFICIENT_RISK_DATA with zero fills. Tail estimates/ratios remain unavailable with insufficient history. Policy versions and durable M9 audit are replay-checked.

## 11. M4 execution and ledger integration

VERIFIED. Existing Decimal Ledger reconstructs and values cash/positions/basis/realized/unrealized/fees/slippage; existing M4 execute handles all fills. The declared convention is **next_observed_close_ioc**, because a daily bar's open predates a close-based decision. A subsequent supplied close must occur strictly after submission; price/source/convention and actual processing time are retained. It is a daily execution approximation, not a real exchange fill. Independent1000USD/5-share reference and real partial-fill accounting reconcile exactly.

## 12. Database and transaction design

VERIFIED on SQLite. Migration0012 is additive; fresh initialization/models check and upgrade of a copied M10 database pass. BEGIN IMMEDIATE reserves the writer before economic reads. Decisions, risk rows, orders/fills, equity artifact, event and checkpoint commit atomically. Unique session/key, session/day, order identity and IOC receipt prevent duplicated effects. Feature preparation occurs outside economic transactions and can leave an unused snapshot only. PostgreSQL schema/advisory-lock path exists but runtime is UNVERIFIED.

## 13. Idempotency verification

VERIFIED. Duplicate create/advance/admin requests, conflicting keys, concurrent workers, unique order/fill constraints and partial-batch retry are tested. The command freezes intended dates before processing; retry cannot advance newer observations. Each economic event is serialized and atomic. Same-key retries after committed events return durable results, including interrupted batches. This establishes exactly-once economic effects within the supported local persistence boundary, not network delivery or distributed exactly-once.

## 14. Crash recovery and restart verification

VERIFIED. Injected interruption after decision, risk approval, fill flush and before checkpoint leaves no partial economic event. Fresh engine/connections recover positions; an actual separate Python process reconstructed/replayed each benchmark session. Three actual CLI processes verified processing, pause without economic change, resume and next-day progression. Reconciliation verifies event chain, order projection, fill receipts, checkpoint, durable committee/risk records, valuations and re-executed M4/M8/M9 outputs. Nonzero holdings survived separate-process recovery.

## 15. Forward availability safeguards

VERIFIED in controlled-clock fixtures, not mislabeled genuine market experiments. Actual forward decision clocks equal processing times; source closes must follow start and precede processing. Execution closes must follow order creation. Source availability and ingestion, model training/effective/creation/generated clocks and locked strategy selection remain checked. Future news/model/selection guards are also covered by preserved M3/M6/M7/M8 regressions. Revised external data is a new input vintage; immutable replay never reacquires it.

## 16. Paper portfolio monitoring

VERIFIED through typed APIs and component/HTTP integration. Current cash/equity, actual positions/basis/weights, realized/unrealized P&L, exposure, fees/slippage, cumulative return/drawdown, source/processing times, pending/rejected/partial orders, latest committee/M9 decision, provider update and event/error history are available. Performance is per immutable session mode; short ratios/tails are withheld below60 observations. No fabricated aligned benchmark or smoothed missing marks. UI uses explicit refresh; no always-live claim.

## 17. FastAPI endpoints

VERIFIED. Create/list/detail; ready/start/pause/resume/stop; bounded advance/update; pending-order cancellation; portfolio/orders/fills/decisions/risk/performance/events; reconcile and optional backtest comparison. Typed OpenAPI-generated client contracts reproduce byte-identically. Named mutations are admitted by the existing same-origin proxy; arbitrary order submissions and foreign-origin mutations were actually rejected. Single-user loopback authorization model is retained. [API schemas](openapi.json).

## 18. Frontend Paper Trading workstation

PARTIALLY VERIFIED. Reuses M10 shell, financial formatting, charts/tables, exact JSON provenance, Radix confirmation and error/empty states. Session creation and lifecycle controls, inspection/paging/cancellation, latest agent participation, M5/M9/filled targets, actual equity/holdings and operational records are wired to actual API paths. Component/proxy tests, types/lint/format, production build and actual proxy/API checks pass. Browser visual QA was blocked by tool URL policy, so no M11 screenshot, keyboard-browser or axe pass is claimed.

## 19. Actual end-to-end workflows

VERIFIED for HTTP/API/worker, BLOCKED for visual browser interaction. The latest production Next proxy passed21 checks including real creation, lifecycle, five-observation advance/retry, all record endpoints, immutable replay, stopped-state rejection, foreign-origin and arbitrary-order rejection. Additional actual demonstrations cover partial IOC, fresh fill-risk veto, insufficient-risk pause and three separate CLI worker processes. The `/paper` route served successfully. These checks are not presented as browser clicks.

## 20. Synthetic versus genuine demonstrations

VERIFIED and isolated. Offline demos generate actual modeled prices and M2/M8/M5/M9/M4 outputs. All resulting performance is labeled synthetic. The retained genuine IBM copy migrated from M10 and produced historical catch-up with zero paper orders/fills; original source database was untouched. No genuine forward-fill track record is claimed. The original IBM committee loss−8.70%, unverified sentiment/multi-agent alpha and tail-history limits remain unchanged.

## 21. Performance and memory benchmarks

VERIFIED for short local scope.

| Assets | Events | Batch advance s | New-process recovery/replay s | API s | Parent peak MiB | SQL statements before restart | Fills |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 5 | 0.2933 | 0.6107 | 0.0112 | 239.34 | 300 | 2 |
| 5 | 3 | 0.4097 | 0.6547 | 0.0118 | 252.53 | 313 | 5 |
| 20 | 3 | 1.7482 | 1.1988 | 0.0142 | 371.72 | 737 | 12 |
| 50 | 3 | 6.3726 | 4.0493 | 0.0240 | 872.53 | 1405 | 21 |

Measured stages include market update, creation, committee/M5, M9/persistence, order generation, M4 fills, ledger restore/valuation, a real audit commit, API retrieval and both fresh-connection and new-process recovery. Full values/throughput are in [benchmark evidence](verification/milestone11/benchmarks.json). Other verification also ran on this machine. Parent RSS is not combined service memory. The50-security fixture's97MiB working DB and~873MiB parent peak reflect verbose frozen audit inputs; databases are excluded from the source ZIP. No p95, long-duration reliability or production capacity claim.

## 22. Backend test results

VERIFIED. **598 passed +11 subtests on Python3.12 (82.27s) and3.14 (82.84s)**; one optional FinBERT skip each. Optional actual cached FinBERT passed separately:1 test,3.29s. Original556 tests preserved;42 new paper cases added. Ruff224 formatted files, mypy125 modules, compileall and pip checks pass. Initial full runs hit a sandbox socket permission failure in an unchanged test; network permission was granted and full unmodified suites then passed. One existing Starlette/httpx deprecation warning remains.

## 23. Frontend test results

VERIFIED. **58 tests in7 files pass**, preserving the previous51 tests byte-for-byte and adding mode/lifecycle, empty-data/review/confirmation and paper-proxy checks. Strict TypeScript, ESLint and Prettier pass. npm audit reports0 vulnerabilities. Fresh npm ci installed372 packages, types and clean build passed; final source changes were copied into the clean installation and rebuilt. Generated API types are byte-identical on regeneration.

## 24. Production build and browser verification

Production build/server and HTTP integration are VERIFIED: eleven research/paper routes plus dynamic proxy; production startup135ms reported by Next in the first verified run. Final build also succeeds. Browser verification is **BLOCKED**: the browser tool rejected the existing localhost tab lookup under its URL policy and explicitly prohibited alternate surfaces/workarounds. No bypass, alternate launcher or new screenshot was attempted. Three paper Playwright tests are provided but unexecuted; automated axe remains unexecuted. This is separate from M10's earlier actual-browser evidence and native Chromium blocker.

## 25. CI/PostgreSQL/Docker status

UNVERIFIED runtime/remote gates. No Git repository/remote is configured; none was created or pushed. Existing PostgreSQL CI test selection now includes paper operations; full backend tests and migration/model checks remain. Frontend CI adds a synthetic paper seed, separate local services and paper browser suite after the existing offline suite. Workflow configuration is not CI execution. PostgreSQL/Docker are not on the current PATH and no real runtime/service was certified; earlier shared-memory/daemon limitations remain. Do not infer PostgreSQL correctness from SQLite or emitted schema.

## 26. Security findings

VERIFIED within local review/test scope. No broker adapter, brokerage credentials, deposits/withdrawals, borrowing, production routing or arbitrary strategy code was added. Server-only market-data key names remain environment-only. Fixed upstream, explicit origin/path/method allowlist and sanitized failures are retained; no arbitrary paper-order endpoint exists. No real-money controls exist to enable. npm audit0 is not a complete security certification. Services remain unauthenticated loopback single-user software and require later auth/operational hardening before public exposure. Archive excludes private environments, databases, model caches, dependencies and restricted source content.

## 27. Research and operational limitations

Daily-close execution and prior-volume capacity remain approximations. Raw corporate-action/membership/PIT news limits, insufficient tails, absence of alpha and the negative IBM baseline remain. SQLite serializes writers; use one polling worker to avoid redundant quota consumption. Synchronous bounded events can outlast a client response; same-key retry/reconciliation is required. Evidence volume makes larger universes heavier. Optional eligible M7 paper execution is supported only for return/close rules and lacks a genuine forward selected-rule track record. Browser visual/accessibility, native PostgreSQL/Docker, remote CI, hosted security and long-duration availability are open. No empirical short local run establishes institutional production reliability.

## 28. Readiness for Milestone 12

Local simulation operations provide the intended foundation: durable state, evidence/risk authority, real M4 accounting, restart/replay and connected controls. Before deployment, resolve browser/accessibility QA, native PostgreSQL/Docker/CI, auth/authorization, backup/restore and longer-running operational/load tests, and validate any genuine forward source/execution assumptions. **Milestone12 is NOT STARTED.** This delivery stops at Milestone11.
