# Exact implementation roadmap

Milestones 1 (market data), 2 (financial features), 3 (sentiment intelligence), 4 (portfolio backtesting) 5 (quantitative optimization), 6 (financial ML research), and 7 (bounded strategy discovery) are implemented locally.
See [M2 verification](MILESTONE2_REPORT.md) and [feature contracts](FEATURE_ENGINEERING.md).
Native PostgreSQL/Docker execution and prior WASM failures remain open gates. Proceed in order;
Milestone 4 is implemented and locally verified for synthetic research simulation; real execution assumptions and native deployment remain partially verified/blocked. See [M3 verification](MILESTONE3_REPORT.md). Each later milestone preserves regression checks and immutable
research evidence. No investment performance is inferred from synthetic fixtures.

| # | Deliverable and files | Acceptance gate |
|---|---|---|
| 1 | `data/`, `database/`, `services/`, `api/`, CLI, migrations, config, Docker and CI | Synthetic offline seed; provider parsing; invalid prices rejected; atomic/idempotent ingestion; snapshot revisions/as-of filtering; typed read API; SQLite + PostgreSQL migration and API integration tests |
| 2 — locally verified | `features/` registry, five kernel modules, frames, calculator, engine, timing, storage, invalidation and matrices; feature API/schema; migration 0004 | Independent mathematical references; every-template prefix invariance; source/ingestion/online clocks; same-close exclusion; revision lineage/invalidation/cache; missing/benchmark policies; SQLite integration and 20/50-asset measurements. Native PostgreSQL gate remains open. Regime inference is deferred to later research. |
| 3 — locally verified | Modular news/contracts/entities, CPU model/inference, aggregation/registry/datasets/matrices, typed sentiment API and migration 0005 | Actual pinned FinBERT and public Board/AAPL providers; 28 quantitative definitions; every-definition prefix invariance, causal revisions/coverage, exact contributor evidence and mixed matrices. Calibration, comprehensive historical coverage, commercial licensing and native PostgreSQL/Docker remain gates. |
| 4 — locally verified research approximation | `backtesting/` contracts/engine/ledger/execution/strategies/analytics/evaluation/storage; API; migration 0006 | Golden Decimal ledger; causal next-open decisions; costs/prior-volume constraints; explicit action fixtures and missing/delisting refusal; frozen-input replay; chronological split/purge interfaces; independent OOS folds; bounded artifacts. Real execution certification, action/membership completeness and native deployment remain open. |
| 5 — locally verified research | `optimization/` contracts/inputs/estimation/solver/sentiment/research/storage; API; migration 0007 | Independent analytical portfolios; explicit PSD/cost/risk constraints and failure diagnostics; past-only M2/M3 inputs; training-only signed sentiment fit; M4 execution/ledger integration; solved frontier and disjoint OOS folds. Genuine sentiment alpha/history and native deployment remain open. |
| 6 — locally verified research | `ml/` contracts/dataset/models/research/evaluation/integration/storage, typed ML API, migration0008 | 1/5/10-session targets; seven actual estimator families; train-only preprocessing; purged four-window folds; separate calibration; safe numeric artifacts; immutable forecasts; M4/M5 adapters; exact refit/ledger replay. Genuine alpha and native deployment unverified; local gate rather than distributed worker. |
| 7 — locally verified research | `strategies/` contracts/grammar/search/inputs/evaluation/research/storage/allocation; typed API; migration0009 | Seeded random/small-grid search; no executable rules; M4-only evaluation; validation fitness and closed-sale-lot/complexity/turnover guards; immutable pre-test selection; local holdout-use tracking; failure history; disjoint independent folds; selected ledger replay; no alpha claim. |
| 8 — locally verified engineering | `committee/`, typed API, migration0010, M6/M7 sources, M5/M4 integration | Durable decisions/replay; fixed dependency-aware priors; original forecasts/locked rules; M5 veto and M4 ledger; genuine ablations and measured workloads. Adaptive weights withheld; coverage/alpha/deployment limitations explicit. |
| 9 — locally verified engineering | `risk/` contracts/analytics/governance/controller/storage/validation, typed API, migration0011 | Independent target and fill veto; full simultaneous revalidation; actual ledger monitoring; immutable replay; measured risk math and empirical limits. Infeasible cash reductions remain rejected. |
| 10 — locally verified engineering | `frontend/app/`, components/hooks/lib/types; OpenAPI-generated types | Ten routes; real persisted results; universe/date/risk controls; discovery submission and progress; benchmark/equity/drawdown/rolling/monthly charts, frontier and correlation; responsive/accessibility checks and screenshots |
| 11 — locally implemented simulation | `paper/` contracts/storage/worker; operational models/API; migration0012; `/paper` workstation | Existing M8/M5/M9/M4 reused; explicit start/pause/resume/stop; forward receipt clocks; atomic keyed events/fills/checkpoints; nonzero-ledger restart/replay; 1/5/20/50-asset synthetic measurements. Browser visual QA and deployment gates remain open. |
| 12 | Integration/property tests, docs, CI deployment checks | Clean-install walkthrough, immutable dependency lock, full PostgreSQL suite, end-to-end demo, threat review/auth gate, backup restore, reproducibility report and known limitations |

## M1 implementation sequence

1. Write architecture, relational design, quantitative methodology and this roadmap.
2. Add package metadata, deterministic settings and explicit simulation-only configuration.
3. Define validated price/asset contracts, provider interface and deterministic synthetic source.
4. Add an Alpha Vantage compact daily adapter with timeouts, bounded retries and honest availability.
5. Add SQLAlchemy models and Alembic revision for assets, ingestion runs and versioned prices.
6. Implement atomic ingestion and as-of querying; reject conflicting duplicates in one batch.
7. Add CLI, FastAPI request/response validation, health checks and bounded result pagination.
8. Add configurable 24-symbol universe, Docker Compose and CI with PostgreSQL.
9. Exercise domain, provider, repository, migration and API failure paths; document what ran.

## Full-demo gate

The requested 2018–2026 experiment is blocked on sufficient licensed historical coverage,
publication-time news, fundamental filings, macro vintages and historical universe membership.
Only data available by the actual experiment cutoff may be included; future 2026 sessions must
not be invented. The offline synthetic workflow verifies software, not investment validity.
If a source lacks PIT history, label reconstruction and quantify resulting limitations.
Do not advertise a profitable trading system based on this project.


## M4 delivery checkpoint (historical)

Implemented: typed frozen snapshots/current-only strategy contexts, raw daily next-open execution,
transaction costs and prior-session volume limits, reconciled Decimal multi-asset ledger, explicit
split/dividend fixtures, three baselines, actual ledger metrics/comparisons, chronological split/purge
interfaces, independent walk-forward folds, frozen-input replay, bounded API and migration 0006.
Verification: [MILESTONE4_REPORT.md](MILESTONE4_REPORT.md).

Open before portfolio optimization: licensed PIT raw prices/actions/membership/delistings, genuine
benchmark coverage, realistic opening capacity and calibrated costs, native PostgreSQL CI/runtime,
optimizer objective/constraint/infeasibility policy and target-weight integration tests. M5 is now implemented as described below. Sentiment trading awaits genuinely sufficient historical news coverage.


## M5 delivered boundary (historical)

Five allocation methods, three mean/covariance choices, explicit constraints/turnover/costs, numerical
risk attribution, a training-only one-feature sentiment adjustment with honest unavailability,
frontier points, M4 comparative rebalancing/folds and frozen experiment replay are implemented.
See [MILESTONE5_REPORT.md](MILESTONE5_REPORT.md). Current genuine IBM sample supports a current
single-asset estimate, not historical trades before acquisition. Synthetic sentiment fixtures validate
statistics/ablation machinery only. Native PostgreSQL/Docker and complete historical news remain gates.

M6 preparation: obtain licensed PIT prices/actions/news/membership and untouched holdouts, define
forecast/label horizons, train-only preprocessing, calibration, evaluation/selection policies and native
service verification. Integrate future annual estimates through the existing validated numerical
boundary. No general ML predictor existed at that delivery boundary; M6 is now implemented below.


## M6 delivered; stop before M7

Financial ML research is implemented and locally verified:423 tests plus11 subtests on both
Python versions, optional actual FinBERT separately. The retained real IBM demonstration gives
negative ML-versus-prevalence results and refuses calibration for insufficient samples; no
sentiment alpha or production execution is established. Synthetic5/20/50-asset and ablation
results test the plumbing, not market profitability. Native PostgreSQL/Docker remain blocked.
See [complete M6 report](MILESTONE6_REPORT.md). Reserve new holdouts and obtain licensed PIT
history before strategy discovery. Milestone7 has not been started.


## Historical M7 delivery

463 tests plus11 subtests on Python3.12/3.14, optional actual FinBERT separately. Local SQLite,
public API lifecycle, M4 ledger replay, M3 clocks and real M6 sklearn forecasts are verified.
Actual100/500/1000-candidate workloads include no-eligible outcomes. The small, previously
inspected retrospective IBM rule lost2.90% and did not beat cash/buy-hold. Genuine sentiment
alpha and global holdout independence remain unverified. Native PostgreSQL/Docker remain
blocked; existing PostgreSQL16 service CI is extended but has not run from this source folder.
See [full M7 report](MILESTONE7_REPORT.md). Its original delivery preceded M8. Licensed PIT histories, new holdouts and native CI remain outstanding research/deployment requirements.

## Milestone 8 delivered; stop before Milestone 9

Local engineering integration is complete: source-verified Quant/Strategy adapters, durable transaction-safe audits,
typed API, M5/risk/M4 execution, immutable replay, genuine IBM ablations and 1/5/20/50-asset benchmarks.
The full committee lost money and underperformed its simple baseline. No statistical alpha or genuine all-agent
coverage is claimed. Native PostgreSQL/Docker remain blocked; remote CI is extended but unverified.
See [M8 evidence and limits](MILESTONE8_REPORT.md). This is the historical M8 delivery boundary; M9 is now delivered below.


## Milestone 9 delivered; stop before Milestone 10

Local simulation engineering is complete with554 passing tests plus11 subtests on both supported Python versions. Independent numerical risk gates are enforced at target and fill stages; actual-ledger risk history persists/replays. Fixed genuine IBM policy comparisons, two independent M4 folds and1/5/20/50-asset workloads ran. Tail reliability/alpha are not established. Native PostgreSQL and Docker remain blocked; configured remote CI is unexecuted. See [26-section report](MILESTONE9_REPORT.md). Frontend work is the next milestone and has **not started**.


## M10 delivery checkpoint

Local full-stack engineering is complete with explicit verification limitations: ten real-API routes, bounded research submissions, evidence/risk/ledger inspectors, responsive charts/tables and saved manifests. 556 backend tests plus11 subtests on both Python versions;51 frontend tests; production and clean builds pass. Actual connected-browser checks passed; native Chromium/axe, PostgreSQL/Docker and remote CI remain blocked/unverified. See [M10 report](MILESTONE10_REPORT.md). Milestone11 is not started; no paper-execution service or live broker was introduced.


## M11 delivery checkpoint

Persistent sessions, forward source gates, M8/M5/M9/M4 reuse, atomic order/fill/checkpoint effects, immutable replay, explicit local worker and Paper Trading UI are implemented. 598 backend tests plus11 subtests on both Python versions and58 frontend tests pass. Actual API/proxy and separate-process recovery are verified. Browser visual QA was blocked by tool policy; native PostgreSQL/Docker and remote CI remain unverified. No genuine forward-fill track record, continuous operation or production reliability is claimed. [M11 report](MILESTONE11_REPORT.md). Milestone12 is not started.


## M12 final local release checkpoint

Milestones 1–11 above are historical checkpoints, including their then-current “not started” statements. M12 now adds final local security/recovery/integration verification and reproducible combined demo. See [final report](MILESTONE12_REPORT.md). No external publication or production certification.
