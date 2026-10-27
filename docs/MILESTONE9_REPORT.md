> Dated research record. Original findings and numerical values are preserved. For current test/CI status see [verification](VERIFICATION.md); supporting exports are [retained locally](EVIDENCE.md).

# Milestone 9 — independent portfolio risk governance

Release0.9.0 · schema0011_risk_management · methodology9.0.0 · verified2026-10-20. Build `c741bc3be50677368dfddf52e193770d83deef0f252d32314396e9dc91711454`.

## 1. Overall completion status

**COMPLETE for local simulation engineering.** Numerical analytics, enforceable M8/M4 integration, SQLite persistence/API/replay, migration preservation and quality gates are VERIFIED. Empirical tail-model validation and institutional production readiness are PARTIALLY VERIFIED. Native PostgreSQL/Docker are BLOCKED; remote CI execution is BLOCKED by absent repository/remote. No component failure is hidden as a pass. Milestone10 has not started.

## 2. Architecture decisions

One deterministic authority consolidates original M8/M5 residual checks with M9 limits. Existing M5 estimation/optimization and M4 ledger/execution are reused. Typed state separates current, hypothetical proposal, actual execution and scenario risk. A target check and independent fresh fill check enforce policy; no LLM calculates or overrides risk. M9 is explicit opt-in so original M8 functionality remains intact.

## 3. Files added and modified

Added risk contracts/analytics/governance/legacy/controller/storage/validation, API router, ORM models, migration0011, two risk test modules, four reproduction scripts, methodology/report/evidence. Modified M4 engine hooks; M8 request/source/engine/risk/storage adapters; app/router/schema registration; package version; existing PostgreSQL CI list; current docs/OpenAPI. Exact added/modified/deleted files are in CHANGESET_M9.json. All34 protected pre-existing test/migration files are byte-identical; no old migration or test was weakened. Original releases remain preserved.

## 4. Risk measurements implemented

VERIFIED: USD/fraction exposure, long/net/gross/cash, HHI under two conventions, effective holdings, top-five/sector/industry concentration; annual covariance/volatility, downside/loss frequency, correlations, beta/active weights/tracking error when an actual basket exists; component/marginal/percentage volatility; empirical one-session VaR/ES; actual past drawdown and explicit latch/recovery; liquidity/cost proxies; historical/hypothetical linear stress. Unsupported short/margin/derivative models are rejected, not implied by formulas.

## 5. Mathematical validation evidence

Independent synthetic references verify exposures/reconciliation, analytic covariance and contribution sum, beta/TE, signed/discrete/tied tails, fractional ES boundaries, scenario contributions and past-only drawdown. Adversarial cases cover all30 requested categories; mapping is in M9_ADVERSARIAL_TESTS.md. Parametrization yields41 new cases in addition to513 preserved cases. Synthetic math verification is distinct from genuine empirical model validation.

## 6. VaR and CVaR methodology

Loss=−simple return, empirical inverse-CDF VaR, exact upper-tail mass ES with fractional boundary allocation; one session, no Gaussian/time-scaling claim. Confidence/sample/tail mass and USD/fraction units are recorded. Default minimum five effective tail observations; required unreliable estimates fail closed. Cash-only is exact zero exposure, not evidence of calibrated market risk. Full formula and hand references are in RISK_MANAGEMENT.md.

## 7. Concentration monitoring

VERIFIED: current/proposed/actual weights, post-cost normalization, security/sector/industry limits and complete combined checks. Unknown historical classifications stay unknown; required sector/industry caps fail closed. A reduced proposal cannot bypass cash, group, turnover or other limits. Finite bounded uniform scaling is conservative and may miss another feasible solution; it is not a replacement optimizer.

## 8. Liquidity controls

VERIFIED engineering / PARTIALLY VERIFIED economic realism: eligible20-observation ADV/dollar-volume proxies (minimum5), freshness, order-plus-pending-buy participation, M5 turnover and M4 cost assumptions. Missing required proxies veto; pending sales do not fund new buys. Existing M4 capacity still applies. No depth, market-impact calibration or fictional liquidation duration is claimed.

## 9. Stress-test implementation

VERIFIED: explicit broad/sector/asset shock precedence, portfolio/equity and asset/sector contributions, nonfinite rejection and historical exact-session eligibility. Genuine IBM August3–31 has21 complete retained sessions; its constant-quantity shock is +4.57%, giving a gain rather than inventing a crisis. The hypothetical−10% shock on the actual late held portfolio produces USD9,126.20 loss (9.99% equity). Neither is an executed/future outcome. Nonlinear/volatility/correlation-shock revaluation is unsupported.

## 10. Risk policy system

VERIFIED: strict declarative immutable `(id,version)`, effective time, portfolio scope, inherited tighter M5 limits/hash, opt-in additional limits, missing-required reject, bounded simultaneous reductions. Default template permits cash and long-only exposure with default data/estimator rules; it does not enable every optional limit. Future/malformed/unsafe/contradictory definitions fail validation. There is no mutable policy API or suitability claim.

## 11. Independent veto enforcement

VERIFIED: hard vetoes yield no executable plan. The fill guard checks actual cash/marks/holdings/pending orders and can only reduce quantity. A maliciously bypassed target check was forwarded into M4 in an adversarial test and still produced no fills. Altered caller order IDs do not manufacture approval or duplicate alerts. In-process code integrity remains assumed; this is not an adversarial runtime sandbox.

## 12. Pre-trade integration

VERIFIED: M8 recommendation → existing M5 target → M9 current/proposed analytics → full policy check/reduction → approved target. Pre-fill validation rechecks opening-event risk rather than trusting an earlier close. All applicable constraints rerun after each simultaneous adjustment, including costs and rounding. A missing required metric cannot pass. Original proposal and violations remain in the audit even when a reduced target passes.

## 13. Post-trade integration

VERIFIED: actual M4 quantities/cash determine exposure after every open/close. Tests reconcile risk weights to persisted M4 equity snapshots and distinguish partial fills from targets. Alerts identify unavailable data, execution mismatch or market movement. Corrective zero targets go through future normal M4 events. Turnover/lower bounds/stale prices may prevent immediate cash conversion; the controller never mutates the ledger directly. Multi-leg sequential enforcement is intentionally conservative.

## 14. M8 committee integration

VERIFIED: evidence/abstention/dependency traces remain, M5-approved proposal is retained before M9, final risk decision and allocations are linked. OriginalM8 baseline reproduces exactly−8.69952944%. Optional risk-policy absence preserves previous behavior and does not claim M9 coverage. No new fundamental/macro/sentiment data or adaptive-agent alpha was invented.

## 15. M4 execution integration

VERIFIED: authoritative existing engine/ledger handles fees, slippage, capacity, partial fills and positions. All genuine M9 fills were checked against persisted executable pre-fill assessments. Vetoed proposals do not become fills. No parallel accounting system, forced immediate liquidation, shorting, margin or live execution was added.

## 16. Risk event persistence

VERIFIED on actual SQLite: three source-linked tables, immutable policy hashes, unique parent sequence, request idempotency and deduplicated alert identities. M8 parent/M4 children/risk rows share a transaction. Injected post-flush risk-storage failure rolls back child ledger/policy/alerts/decisions. Restart/API retrieval and duplicate processing pass. Old26 tables and original DB retain identical row hashes through upgrade. Native PostgreSQL transaction behavior remains BLOCKED.

## 17. API functionality

VERIFIED with TestClient and actual uvicorn HTTP: summary, evaluate, stress-test, policies, decisions/replay, alerts/history and portfolio exposure/tail/drawdown/concentration/volatility/stress routes. Typed requests/responses, pagination, as-of selection, exact assessment ownership, local compute gate and structured errors are implemented. Earlier absent snapshots return404; unsafe extra configuration422; immutable version conflicts409. Standalone input is caller-supplied, not a verified custodian feed. OpenAPI was exported from the running app.

## 18. Historical replay

VERIFIED: all eight fixed genuine comparison parents replay decision/ledger/metric equivalence; enabled profiles replay risk events too. Standalone and committee-linked risk replay verify build/dependencies/source/input/policy/result hashes with float rtol/atol1e−9 and exact Decimal strings. Later policy/data inputs do not replace past snapshots; tampering fails. Retained-source reconstruction is not proof of genuine PIT availability. Old M8 code fingerprints are preserved, not silently accepted as current-build replays.

## 19. Genuine-data risk evaluation results

PARTIALLY VERIFIED empirically. Retained public raw IBM data contains100 bars; dates are previously inspected and retrospective, acquired after the decisions. The selected late held state has98 eligible returns:95% VaR≈4.38%/USD3,997.79 and ES≈9.58%/USD8,749.81, explicitly INSUFFICIENT_TAIL_DATA (effective mass4.9). Estimated static-weight annual volatility≈59.43% is distinct from actual realized ledger volatility. A genuine90%-weight proposal under a10% cap was reduced and fully rechecked. Actual equity history drives drawdown. Historical/scenario/sensitivity evidence is in M9_RESEARCH_EVIDENCE.json.

Shadow forecasts have7 matured nonzero-exposure observations, zero raw exceptions, **zero qualified reliable forecasts**, no p-value and no coverage claim. Sensitivity fixes20/60/90 lookbacks × three covariance estimators ×95/99% confidence without choosing a winner. Two existing M4 independent-capital folds (test startsAug4 andSep1) returned−2.48% and−3.99%; they are previously inspected reconstruction, not new holdouts. Genuine all-agent PIT coverage/alpha remain unestablished.

## 20. Risk-policy backtesting results

Fixed strategy, universe, datesSep9–Oct12, capital/costs/model/rule and predeclared profiles; no threshold tuning after returns. Guard-only retains modest extra full-order/cost checks. Concentration cap50%; volatility cap25% annual; drawdown3% cash latch; VaR2.5%/ES3.5% one-session with minimum five tail observations; combined cap50%/vol30%/DD4%/turnover40%/participation1%/−10% shock with5% stress-loss cap. All are research configurations, not investor advice.

| Fixed profile | Return | Max DD | Annual vol | Mean exposure | Turnover | Costs USD | Fills |
|---|---:|---:|---:|---:|---:|---:|---:|
| m8_baseline | -8.70% | 9.11% | 14.92% | 33.26% | 5.542 | 532.79 | 12 |
| guard_only | -8.64% | 9.06% | 14.84% | 32.95% | 5.497 | 529.79 | 13 |
| concentration | -4.32% | 4.53% | 7.37% | 16.17% | 2.670 | 270.95 | 12 |
| volatility | -3.17% | 3.35% | 5.26% | 12.22% | 1.998 | 207.41 | 12 |
| drawdown | -4.69% | 4.69% | 12.00% | 12.34% | 2.036 | 200.57 | 5 |
| var | 0.00% | -0.00% | 0.00% | 0.00% | 0.000 | 0.00 | 0 |
| cvar | 0.00% | -0.00% | 0.00% | 0.00% | 0.000 | 0.00 | 0 |
| combined | -4.45% | 5.77% | 11.21% | 39.79% | 0.651 | 68.67 | 6 |

Buy-hold remains−4.69% under matched M8 assumptions. Lower losses often reflect lower exposure and costs, not added alpha. VaR/ES profiles are cash because nonzero proposals lack reliable tails, not because a tail model predicted no loss. Combined controls leave some exposure after a halt because other constraints can prevent immediate liquidation; its mean exposure is39.79% and max drawdown5.77%. All unsuccessful/outstanding states remain recorded. Exact Sharpe/cash/risk-event/order statuses and timings are in VERIFICATION_M9.json; short-sample annual statistics are descriptive only.

## 21. Exact test counts for both Python versions

- Python3.12: **554 passed, 1 skipped, 1 warning, 11 subtests passed in 62.70s (0:01:02)**
- Python3.14: **554 passed, 1 skipped, 1 warning, 11 subtests passed in 65.41s (0:01:05)**
- Separate optional actual cached CPU FinBERT: **1 passed in 2.88s** (Python3.12, offline model cache; not a stub).

The default skip is optional real FinBERT; one upstream Starlette/httpx deprecation warning remains. All original513 tests and11 subtests remain. New41 cases include exact math, actual SQL/API/M8/M4 integration, injection/rollback/partial-fill/replay adversaries. Ruff check/format, mypy118 modules, compilation and dependency consistency on both runtimes pass. No GPU was introduced.

## 22. Performance and memory measurements

VERIFIED measured synthetic workloads; one-process sequential warm samples, no throughput guarantee. Nonzero constructed holdings use retained M5 synthetic returns and an actual broad shock. Exposure/covariance/tail/stress/policy timings include current and proposed checks; phases overlap and do not sum to wall time. VaR/ES share one sorted array, so their joint time is reported honestly. SQL commit is measured using an already-calculated new assessment; replay includes calculation/hash verification.

| Assets | Risk calc ms | Exposure ms | Covariance ms | VaR+ES ms | Stress ms | Policy ms | SQL commit ms | Replay ms | Risk RSS MiB | Committee M9 s / RSS MiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4.008 | 0.041 | 1.202 | 0.046 | 0.010 | 0.207 | 11.194 | 15.667 | 113.12 | 0.093 / 238.42 |
| 5 | 6.624 | 0.046 | 1.700 | 0.047 | 0.012 | 0.302 | 13.572 | 19.843 | 127.00 | 0.260 / 258.50 |
| 20 | 15.640 | 0.058 | 3.166 | 0.048 | 0.019 | 0.698 | 23.088 | 36.659 | 187.53 | 1.021 / 351.72 |
| 50 | 34.988 | 0.091 | 6.284 | 0.047 | 0.028 | 2.131 | 44.735 | 75.362 | 316.52 | 2.638 / 657.17 |

Paired committee baselines for1/5/20/50 assets were 0.053s, 0.207s, 0.877s, 2.258s; increments with M9 were 0.040s, 0.052s, 0.144s, 0.380s. M8's historical50-asset2.411s/~549MiB is contextual: current source/snapshot/API preparation and risk audit differ, and current committee process peaked657.17MiB. No direct speedup claim. RSS is macOS whole-process high-water bytes/2²⁰; source loading/dependencies/API/replay are included, model fitting/transformer inference excluded. Frozen return matrices are reused per assessment and shared between candidate checks; event records reference source/ledger state rather than duplicating every return matrix.

## 23. PostgreSQL/Docker/CI status

SQLite fresh initialization/integration and preserved26-table M8 upgrade: VERIFIED. PostgreSQL0010→head offline DDL and schema/model comparison: VERIFIED as SQL generation only. Native initdb retry with mmap/shared-memory settings: BLOCKED, `shmget(..., size=56)` Operation not permitted. Docker Compose2.39.4/configuration: VERIFIED; runtime: BLOCKED, daemon socket unavailable. Existing GitHub Actions PostgreSQL16 service now includes risk math/integration along with market/feature/sentiment/backtest/model/strategy/committee persistence, transaction, startup/API and replay tests. No Git checkout/remote is configured here, so CI has not run and is BLOCKED/UNVERIFIED. No remote was created, pushed or published.

To reproduce on an authorized host: install requirements.lock and editable package, start empty disposable PostgreSQL16, set TEST_DATABASE_URL, execute the second pytest step in `.github/workflows/test.yml`, then run the complete suite and Compose checks. The database fixture upgrades head against the disposable service. This debt remains an explicit final-deployment gate.

## 24. Security findings

VERIFIED within local scope: strict finite/extra-forbid Pydantic input, safe declarative policy/scenario data, bound histories/assets/work, ORM parameterization, hash/source checks, immutable version conflicts, mathematical alert identities and transaction rollback. No executable configuration, model unpickling, credentials, private env, DBs, weights or caches enter the source archive. No live broker/real-money path. Local APIs lack production authentication/authorization/TLS/process isolation; no penetration-test or production security certification is claimed. A host/process administrator can modify storage/code; hashes detect ordinary replay drift, not a fully malicious administrator rewriting all manifests.

## 25. Known limitations

Thin noisy single-asset empirical evidence; no untouched holdout or reliable tail calibration; historical raw-price action/universe limitations; incomplete genuine news/fundamental/macro histories; volume/open-fill assumptions; conservative finite reduction search and sequential multi-leg enforcement; missing quotes can prevent exits; simultaneous turnover/lower bounds can prevent cash correction; valuations are not a continuous market feed. Default optional M9 coverage must be explicitly enabled. Native PostgreSQL/Docker and remote CI remain unresolved. No risk guarantee, established alpha, suitability recommendation or institutional production readiness is implied.

## 26. Readiness for Milestone 10 — Institutional-Grade Frontend

Backend local risk engineering and typed persisted API are ready for a separately authorized frontend milestone. Frontend must display current/proposed/actual differences, reliability/status/units, vetoes, cash/no-new-risk latches and missing data honestly. Native deployment, authentication and genuine-data research gaps remain gates. **Milestone10 has not started.** Fresh source archive, per-file SHA256 manifest, changeset and machine evidence accompany this report.
