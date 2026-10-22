# SentientAlpha — Milestone 5 completion report

Verified 2026-10-14 America/Chicago (some UTC evidence timestamps are October 15).
**Package 0.5.0; optimization 5.0.0; migration 0007. Milestone 6 was not started.**
Working numerical allocation research is integrated with the existing feature pipeline, execution
simulator and Decimal ledger. This delivery does **not** establish genuine sentiment alpha or certify
realistic market execution/native deployment.

| Major component | Classification | Scope |
|---|---|---|
| Five optimization methods / independent references | VERIFIED | Analytical two-asset solutions, constraints, residuals, failure handling |
| Past-only means/covariance / PSD audit | VERIFIED | M2 return adapter, independent formulas, later-data invariance |
| Sentiment normalization/signed fit/ablation machinery | VERIFIED | Explicit synthetic statistical fixtures; partial/missing M3 coverage refusal |
| Genuine historical sentiment coefficient / alpha | BLOCKED | Complete compatible genuine history absent; no empirical alpha claimed |
| M4 targets/orders/ledger / chronological folds / replay | VERIFIED | Actual linked M4 artifacts, delays/costs/rounding and independent-capital OOS folds |
| SQLite/schema/API/current genuine IBM estimation | VERIFIED | Real migrations, preservation hashes, TestClient and actual loopback HTTP |
| Nonconvex global optimality / actual target compliance | PARTIALLY VERIFIED | Local Sharpe/ERC candidates; actual holdings can diverge from continuous targets |
| Real historical multi-asset trading / action completeness | PARTIALLY VERIFIED | Daily raw research approximation, fixed current universe, incomplete raw/action knowledge |
| Native PostgreSQL / Docker | BLOCKED | Shared-memory denial / absent daemon; SQL/config/CI preparation are not runtime certification |
| Required local checks | VERIFIED | No remaining failed local gate; injected failures and infeasible cases are rejected, not hidden |

## 1. Implementation summary

A modular portfolio constructor now estimates interpretable annual returns/covariance, validates
constraints, solves five allocation methods, attributes expected risk and passes targets into actual
M4 execution/accounting. It persists numerical research, solved frontier points, every predeclared
comparison/ablation, chronological folds and immutable replay inputs. No replacement ledger,
LLM-computed weight, broker, frontend, general ML predictor or strategy-search engine was introduced.

## 2. Architecture decisions

Separate contracts, input adapters, estimation, sentiment statistics, numerical objectives/constraints,
feasibility checks, risk attribution, rebalance research and storage/API modules. The numerical boundary
accepts structured annual `Estimates`, constraints/objective and current weights. M2 `return` and M3
registered security-level features retain their own source and availability clocks. Source observation,
provider readiness, pipeline readiness, estimator decision and next-open execution are not conflated.
See [PORTFOLIO_OPTIMIZATION.md](PORTFOLIO_OPTIMIZATION.md) for formulas and the exact boundary policies.

## 3. Files added and modified

New `optimization/` package (contracts, inputs, estimation, sentiment, solver, research, storage/version),
portfolio API router, optimization ORM model, migration 0007, three new test files, four executable
verification/replay scripts, optimization guide/report and measured evidence. Updated schema registration,
app routing/error handler, version metadata, SciPy runtime pin, existing PostgreSQL CI and architecture/
roadmap/README/OpenAPI. M4 storage only adds a guard directing optimizer-ledger replay to its parent
experiment. **All original 309 tests and migrations 0001–0006 are byte-identical to the M5 starting
baseline.** [Changeset](CHANGESET_M5.json); [source hashes](SOURCE_SHA256_M5.json).

## 4. Methods implemented

Equal-weight projection; minimum variance; mean variance with explicit gamma; maximum estimated Sharpe
with annual risk-free/cost units; constrained percentage-risk-contribution parity. Cash/exposure modes
are explicit. Sharpe/ERC require fixed invested exposure and refuse undefined zero empirical risk;
they are not advertised as globally solved. Equal-weight under constraints/cost penalties can be a
projection with residual cash. Optional target-volatility optimization is not implemented; maximum
volatility/variance constraints are. Unsupported fields/method combinations reject clearly.

## 5. Mathematical verification results

Independent two-asset reference: annual mu=[0.10,0.20], Sigma=diag(0.04,0.09), gamma 5, fully invested,
rf 0, zero optimization penalties. AAA weights: equal weight 0.5; minimum variance 9/13; mean variance 8/13;
tangency 9/17; equal-risk 0.6. BBB is the remainder. Closed-form tests pass within stated numerical
tolerances. ERC variance is 0.0288, with equal percentage risk shares. Contribution sums, covariance/
EW/shrinkage formulas, PSD regularization, group/sector/turnover/risk caps, tiny variance capacity,
zero-risk objectives, cash return targets, solver failures, explicit fallback and asset ordering are
independently tested. Expected values are not generated by another call to the optimizer itself.

## 6. Expected-return estimation

Historical mean, normalized exponentially weighted mean and configured conservative shrinkage toward
an explicit annual prior (default zero). Arithmetic daily means scale by252; estimates never use future
realized returns. Included dates/count, raw sample-mean uncertainty diagnostic, effective EW count,
window/start/end/readiness, missing policy, units/configuration and source identities are retained.
No unsupported factor estimate or calibrated predictive confidence is implied.

## 7. Covariance estimation

Sample covariance; unbiased normalized exponentially weighted covariance; fixed-intensity shrinkage
of off-diagonal sample covariance toward its diagonal. The latter is **not Ledoit-Wolf**. Common
past-available complete rows preserve asset/date ordering; no missing returns are zero-filled.
Symmetry, nonfinite values and material indefiniteness reject; eigenvalue floor/adjustment/condition
and zero-variance counts are explicit. Singular positive-variance correlations can be processed;
ill-conditioned or infeasible risk problems are not forced into successful allocations.

## 8. Sentiment methodology

One registered level/momentum/surprise at a time. Training-only pooled normalization, clipping and
centered OLS estimate a signed next-session intraday drift coefficient. Signal readiness must precede
its label's open; completed label knowledge must precede fitting; labels crossing train_end are purged.
Annual adjustment is252 × lambda_daily*z, added transparently to the historical daily-return proxy.
Coverage/inference/history/neutral states remain distinct. Current missing/late/partial signals refuse
adjustment or invoke an explicit labeled price-only fallback. Exact per-asset adjustments and training
lineage are retained. Broad news is not broadcast to individual securities.

## 9. Empirical lambda status

**BLOCKED on genuine compatible history.** No arbitrary positive coefficient or manual lambda override
exists. The synthetic statistical demonstration learns a negative level coefficient
**-0.0009240324 daily per standardized signal unit**; momentum/surprise
also fit their own training-only coefficients. These signals are generated mathematical variables,
**not observed news or FinBERT outputs**, and cannot establish investment predictability. IID standard
errors are descriptive; no calibrated significance, causal sentiment effect or genuine alpha is claimed.

## 10. Constraints implemented

Long-only minima/maxima, restrictions, concentration, full-investment/cash bounds, invested exposure,
group minima/maxima, declared sector maxima, annual volatility/variance and compatible tracking-error
caps, target expected return including cash, current holdings, one-way turnover including cash,
rebalance thresholds and asset-specific ex-ante cost penalties. Unknown members/constraints reject.
Independent postchecks include normalized relative risk-cap slack rather than permissive absolute
variance error. Actual execution lot/gap/partial-fill effects can violate theoretical target bounds;
subsequent actual weights and slacks are preserved rather than claiming continuous-target compliance.

## 11. Solver diagnostics and failures

SciPy 1.18.1 HiGHS linear feasibility plus SLSQP with analytical objective gradients and deterministic
starts. Solver success, finite output and independent feasibility are all required. Reports preserve
status/message/iterations/objective/tolerances/starts/residuals/bindings/covariance audit. A local
nonlinear failure is not a global infeasibility certificate. Explicit equal-weight fallback retains
the original failed method and reason. Controlled failure/nonfinite-output tests use clearly labeled
solver injections; normal mathematical/integration/demonstration runs use the real SciPy solver.

## 12. Efficient frontier

A bounded gamma grid solves actual constrained mean-variance portfolios on identical frozen mu/Sigma
and sentiment adjustment. Failed points are labeled. No interpolated decorative curve or held-out
selection is generated. Six points per measured experiment completed; cost-aware grids need not be
a classical unrestricted smooth Markowitz frontier. Static nonzero-rf calculations are supported;
historical comparisons require zero-rf because M4 cash earns no interest.

## 13. Risk attribution and explanations

Expected return/variance/volatility/Sharpe, volatility and percentage-risk contributions, ERC residual,
cash/invested weights, turnover, estimated costs, HHI including cash, concentration, sectors,
correlation and compatible predicted tracking error are calculated. Binding constraints, numerical
weight changes, source window and exact sentiment deltas support explanations. Predicted risk is
separate from realized M4 statistics; no invented causal narrative accompanies a weight change.

## 14. Backtesting integration

The actual M4 `simulate`, execution constraints and Decimal ledger produce every order/fill/cash/
position/equity artifact. Monthly/quarterly/explicit observation schedules estimate only eligible past
moments. Orders trade after readiness at the next eligible open. Estimated optimization costs never
become ledger debits; M4 commissions/slippage are charged once. Rounding/liquidity/cash may prevent
exact targets. Theoretical and first post-eligible-execution closing weights/slacks are distinct.
A delayed-data test verifies this report does not accidentally read weights from before execution.
M5 optimized comparisons reject explicit action records; M4 standalone action support is preserved.

## 15. Walk-forward evaluation

Reuses M4 chronological window/split machinery, rolling or expanding moment history and disjoint OOS
steps. Settings are fixed before evaluation; no winner is selected using later test returns. Earlier
OOS observations may enter a subsequent decision only once available, as explicit online adaptation.
Sentiment fitting stays within its declared earlier training interval. Each measured workload ran
**two independent-capital folds**, 42 test sessions each, for all five methods. Child ledgers persist;
linked OOS return indices do not pretend to carry positions/capital. Aggregate ledger-dependent cost/
trade/exposure ratios are null; actual fold values remain available. Exact fold replay passes.

## 16. Ablation status

Price-only, level, momentum and surprise variants are predeclared and all retained in
[M5_SYNTHETIC_SENTIMENT.json](M5_SYNTHETIC_SENTIMENT.json), with saved fixture/config/hash and exact
M4 replay. Tiny synthetic OOS forecast errors/direction diagnostics are explicitly nonempirical.
No arbitrary feature combinations or multiple-testing-adjusted market significance is claimed.
Genuine ablations remain unavailable because source coverage is incomplete. A valid missing-coverage
result is preserved; no2018–2026 news history or neutral-zero replacement is fabricated.

## 17. Genuine market-data experiments

The retained public Alpha Vantage IBM sample has 100 original raw observations through2026-10-13.
At the actual current decision clock, **99 daily returns** support a genuine-data mean/covariance and
single-asset allocation of 100% IBM. That weight is an identity, not diversification/optimal-investment
or profitability evidence. Historical online estimation is **insufficient_data** and historical
optimized comparison has **zero fills**, because acquisition/materialization occurred later.
The original database remains read-only and unchanged; a migrated copy is used.
M5_REAL_IBM.json (`M5_REAL_IBM.json`, intentionally omitted; see PUBLICATION_SELECTION.md). Complete compatible IBM sentiment and genuine SPY coverage are
absent; no real historical alpha, long-term performance or licensed coverage is implied.

## 18. Exact automated tests and integration checks

- Python 3.12.15: **387 passed, 1 skipped, 11 subtests passed**.
- Python 3.14.5: **387 passed, 1 skipped, 11 subtests passed**.
- **78 new M5 cases**, preserving all 309 original cases and 11 subtests without changing their files.
- The core skip is the opt-in real FinBERT test. Separately on 3.12 with actual pinned local CPU
  weights: **1 passed in 2.55 seconds**; not a test double. No 3.14 real-model run is claimed.
- Ruff lint/format pass; mypy passes **72 application modules**; compilation and dependency checks
  pass in both environments. One existing Starlette/httpx deprecation warning remains.
- Actual SQLite upgrade/downgrade/schema checks pass. A migration copy preserved hashes of **17 old
  tables, 18 existing backtest runs and16,850 artifacts**. A separate genuine-data copy preserves all
  prior 3,220 prices/230 feature rows before adding the new return experiment.
- Actual loopback HTTP at `http://127.0.0.1:8015` creates optimization/frontier/comparison/walk runs,
  retrieves typed pages, reads existing M4 ledger routes and verifies numerical/execution replay.

Captured verification (`VERIFICATION_M5.json`, intentionally omitted; see PUBLICATION_SELECTION.md); [migration](M5_MIGRATION_CHECK.json);
[HTTP](M5_HTTP_SMOKE.json). Pure solver success tests are not substitutes for these integration checks.

## 19. Performance and memory

Sequential separate Python 3.12/macOS ARM64 processes: synthetic 2022–2024 source data, 126-return
estimation windows, 2024 evaluation, 12 monthly decisions per method and two OOS folds. All five methods
and every measured monthly decision completed. No FinBERT model/GPU is loaded in these processes.

| Assets | Estimate s | Min-var solve s | Mean-var solve s | Sharpe solve s | ERC solve s | Five-method compare/persist s | Walk/persist s | Whole-process peak MiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 0.0006 | 0.0009 | 0.0010 | 0.0012 | 0.0018 | 0.458 | 0.333 | 213.0 |
| 20 | 0.0027 | 0.0018 | 0.0028 | 0.0074 | 0.0099 | 1.613 | 1.173 | 363.1 |
| 50 | 0.0056 | 0.0101 | 0.0251 | 0.0808 | 0.0764 | 6.942 | 4.440 | 1004.6 |

Equal-weight is the first cold solver call and includes lazy SciPy/HiGHS initialization
(about 0.15 seconds); later method timings are warm, so this is **not an algorithm speed ranking**.
Comparison persistence flush/JSON-encoding/commit time was separately measured at
0.036/0.101/0.272
seconds for 5/20/50 assets; it excludes source loading, freeze construction/hash and pre-flush work.
The archive also includes a complete standalone synthetic input/manifest export and an executed
database-free replay helper. Full JSON reports static end-to-end/source/feature/frontier/API timings and scopes:
[5](M5_BENCHMARK_5.json), [20](M5_BENCHMARK_20.json), [50](M5_BENCHMARK_50.json).

Peak RSS includes ingestion, one M2 return output, sources, five objectives, frontier, comparative
ledgers, walk-forward, persistence, replay and API checks. It is not incremental kernel memory or a
like-for-like comparison to M2's 44-output/five-year 1.37GiB workload. Child ledgers retain their execution
range while parent inputs retain estimation history; full 44-feature matrices are not copied into the
optimizer. No unmeasured claim of fixing M2 memory, distributed worker, GPU or queue is made.

All measured synthetic outcomes are reported below, including less attractive methods. Costs are
actual M4 simulated commissions; slippage and remaining metrics are in the JSON. No market inference:

| Assets | Method | Annualized return | Annualized volatility | Sharpe | Max drawdown | Whole-period turnover | Commissions USD |
|---|---|---:|---:|---:|---:|---:|---:|
| 5 | equal_weight | -3.27% | 15.04% | -0.146 | 11.62% | 0.592 | 56.00 |
| 5 | minimum_variance | -3.30% | 15.35% | -0.142 | 11.64% | 0.913 | 60.00 |
| 5 | mean_variance | -3.42% | 15.32% | -0.151 | 11.68% | 1.224 | 57.00 |
| 5 | maximum_sharpe | -3.77% | 15.60% | -0.169 | 11.90% | 1.888 | 58.00 |
| 5 | risk_parity | -3.28% | 15.17% | -0.144 | 11.63% | 0.717 | 59.00 |
| 20 | equal_weight | -2.76% | 7.61% | -0.330 | 10.21% | 0.590 | 139.00 |
| 20 | minimum_variance | -3.34% | 7.85% | -0.393 | 10.31% | 1.480 | 232.00 |
| 20 | mean_variance | -3.62% | 8.85% | -0.372 | 10.55% | 3.662 | 232.00 |
| 20 | maximum_sharpe | -3.38% | 9.39% | -0.319 | 10.45% | 3.865 | 219.00 |
| 20 | risk_parity | -3.03% | 7.55% | -0.370 | 10.21% | 0.938 | 210.00 |
| 50 | equal_weight | -3.03% | 5.29% | -0.556 | 9.76% | 0.676 | 316.00 |
| 50 | minimum_variance | -3.24% | 5.87% | -0.532 | 9.82% | 2.063 | 539.00 |
| 50 | mean_variance | -3.20% | 7.29% | -0.410 | 10.33% | 6.523 | 485.00 |
| 50 | maximum_sharpe | -3.18% | 6.50% | -0.466 | 10.13% | 4.692 | 535.00 |
| 50 | risk_parity | -3.16% | 5.38% | -0.569 | 9.79% | 1.128 | 475.00 |

## 20. Known limitations

No genuine historical sentiment lambda/alpha/calibration; incomplete market actions/delistings/
historical universe/sectors; raw daily execution approximation; local nonconvex solutions; finite-sample
moment sensitivity; uncalibrated cost rates/liquidity; configured diagonal rather than Ledoit-Wolf
shrinkage; no explicit action events in M5 comparisons; no short/leverage/cardinality/integer-lot
optimization or exact fixed-commission objective. Actual holdings can drift from target constraints.
Cooperative bounds do not forcibly cancel native calls, enforce an OS RSS ceiling or coordinate all
server workers. Database privilege/auth/worker recovery remain deployment work. M2 memory cost and
commercial news/model-rights questions remain unchanged. Old manifests need their matching source
build, not an unreported replay across application changes.

## 21. PostgreSQL/Docker verification

Compose version/configuration succeed. Runtime cannot connect to the absent Docker daemon. Native
PostgreSQL initdb was retried once and still fails `shmget: Operation not permitted`. M5-only PostgreSQL
migration SQL emits successfully; this is structural evidence, **not native execution**. The existing
PostgreSQL 16 CI service now includes M5 integration tests but was **not dispatched/executed**. Prior
WASM negative-test failures remain unresolved; the old 0002 data-query migration remains unsuitable
for full-chain offline SQL. Original migrations were not altered to hide this.
[M5_DEPLOYMENT_CHECKS.json](M5_DEPLOYMENT_CHECKS.json).

## 22. Readiness for M6 — stop here

The annual-estimate/constraint boundary, source manifests, honest missing-history policy, validated
targets, M4 ledger links and chronological evaluation are ready for a future predictor adapter.
Before M6: obtain licensed PIT prices/actions/news/membership, define forecast horizons/labels and
untouched holdouts, implement train-only preprocessing/calibration/selection policies, validate native
service CI and benchmark genuine out-of-sample forecasts. No general ML predictor, automated discovery,
investment committee, Risk Manager personality, broker or frontend was implemented in this milestone.
