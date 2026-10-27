> Dated research record. Original findings and numerical values are preserved. For current test/CI status see [verification](VERIFICATION.md); supporting exports are [retained locally](EVIDENCE.md).

# SentientAlpha — Milestone 6 delivery and verification report

Milestone 6 is implemented as version 0.6.0 / ML engine 6.0.0 / schema 0008_machine_learning.
Milestone 7 was not started. Local research engineering is verified; predictive alpha is
**not established**, and native deployment is not certified. Evidence uses actual CPU
estimators, frozen input snapshots and existing M4/M5 engines, never invented predictions.

## 1. Implementation summary and status

| Component | Status | Evidence / limit |
|---|---|---|
| Numeric ML training, JSON inference, temporal validation | VERIFIED | Actual sklearn fits and independent golden/adversarial tests |
| SQLite models/forecasts/experiments and replay | VERIFIED | Migration, API, frozen refit and linked ledger comparisons |
| Probability calibration framework | VERIFIED | Separate-window sigmoid/isotonic tests, raw/calibrated metrics |
| Genuine IBM calibration | BLOCKED | Only 14 eligible calibration observations; refusal retained |
| Historical ML economic performance | PARTIALLY VERIFIED | Ledger works; tiny retrospective raw-data experiment, no execution certification |
| Genuine point-in-time market forecasting | BLOCKED | Historical bars were acquired after the historical decisions |
| Sentiment ablation framework | VERIFIED | Four synthetic variants on identical common observations |
| Genuine sentiment alpha | BLOCKED / UNVERIFIED | Insufficient complete compatible historical news |
| M5 expected-return adapter | VERIFIED | Units/horizon/freshness gates and actual Ridge→M5 solve |
| Offline drift and regime diagnostics | PARTIALLY VERIFIED | Simple daily proxies and descriptive fold/month diagnostics; no advanced regime model |
| Native PostgreSQL / Docker runtime | BLOCKED | Shared-memory denial / absent daemon |
| ML improvement over prevalence on retained IBM | FAILED | All three ML families had worse OOS log loss/Brier than prevalence |

## 2. Architecture decisions

Reuse persisted M2/M3 features and M1 source IDs, one small `ml/` package, sklearn1.9.1 and
numeric JSON artifacts, existing SQLAlchemy/Alembic and bounded per-process API gate. Four
chronological windows distinguish candidate selection from calibration and final evaluation.
Use ordinary gradient boosting to make tree export transparent. No model pickles, MLflow,
neural-price models, distributed workers, live broker or strategy discovery were introduced.
See [exact contracts](ML_RESEARCH_ENGINE.md).

## 3. Files added and modified

Eight ML modules, one API router, three ORM tables and migration0008, two ML test modules,
four executable verifiers/replay/profiling helpers, API wiring/version/dependency/schema updates,
and M4 parent-replay routing. Existing tests and migrations0001–0007 are byte-identical.
Complete file list (historical evidence archived locally) gives the audited changes.

## 4. Forecasting targets

Direction, simple decimal return and future-only annualized intraday log-return RMS volatility,
for 1/5/10 sessions. Entry is strictly next eligible open; exit is h-th session close.
Close-to-close research is separate and refused by the economic adapter. Volatility RMS is
not close-close volatility or sample SD; h=1 remains a defined absolute-return proxy.

## 5. Models

Logistic/RF/gradient-boosting classifiers; Ridge/Elastic Net/RF/gradient-boosting regressors.
Every estimator family executes in tests, checks finite outputs and matches its exported
numeric representation to sklearn. Seeds and complexity/regularization are bounded.

## 6. Baselines

Majority, training prevalence, prior-return sign momentum; zero/train-mean returns; train-mean
volatility and historical daily-return RMS. Candidate and baseline scores use identical OOS
observations. Constant probability and a hard majority are distinct, especially under log loss.

## 7. Point-in-time safeguards

Exact feature clocks/order/definitions/source IDs, no target input columns, no random pooled
splits or future cross-asset dates, no sentiment forward-fill or fake complete coverage.
Strict online historical reconstruction correctly yields insufficient data when features were
computed afterward. Explicit retrospective price reconstruction is labeled and retains source
acquisition lineage; it never backdates observed sentiment.

## 8. Temporal methodology

Declared rolling/expanding fold windows globally separate train, validation, calibration and
test. Models are frozen before each test opening. Held-out target changes do not change
preprocessing, candidate selection or previous models. Stored forecasts carry actual generation
time and historical-walk-forward/retrospective origin, never live-issued labels.

## 9. Purging and embargo

Labels must end and mature before the next window's opening; old feature dates alone do not
make labels eligible. Label overlap is removed at every boundary. Optional extra gap excludes
last N sessions of the preceding window. This is forward-only purged chronological validation,
not random folds plus a decorative gap. Audit counts and label maturity cutoffs are retained.

## 10. Hyperparameter selection

At most12 candidates/12 folds/48 candidate-fold fits. All validation scores/failures retained;
log loss or RMSE selects within the declared search. A .001 default tolerance favors simpler
configured candidates absent a larger validation advantage. Calibration and final test do not
select candidate parameters. Demonstrations tune two predeclared candidates per ML family and
report every family, including failures/poor results; no best-test winner is selected.

## 11. Calibration results

Separate sigmoid and isotonic computations pass tests. Isotonic requires1,000 observations;
sigmoid40, plus10 of each class. All retained IBM families report **insufficient calibration**
with14 observations and preserve raw predictions. Synthetic pooled demonstrations provide
larger separate calibration windows; complete raw/calibrated scores/reliability curves/counts
are in benchmark evidence. Numeric bounds alone never establish calibration quality.

## 12. Out-of-sample genuine predictive results

Universe: retained IBM only, 100 genuine raw daily bars May21–October13,2026, XNYS calendar.
Acquisition was October14 after this historical interval. These are **retrospective research**,
not contemporaneously available historical forecasts. Features: return and SMA5. Chronological
train/validation/calibration/test have declared dates in each persisted fold. Held-out scoring
has24 observations. This holdout is now consumed and must not become an untouched future test.

| Family | N | Accuracy | Brier | Log loss | Net simulated return | Gross return |
|---|---:|---:|---:|---:|---:|---:|
| prevalence | 24 | 0.7917 | 0.236042 | 0.665208 | 0.0000% | 0.0000% |
| logistic | 24 | 0.2500 | 0.268841 | 0.730982 | -10.8753% | -10.5537% |
| forest_classifier | 24 | 0.5000 | 0.265206 | 0.724773 | -3.7599% | -3.0691% |
| boost_classifier | 24 | 0.5417 | 0.249765 | 0.693810 | -1.2730% | -0.5668% |

All ML families failed to beat prevalence on held-out log loss and Brier in this small sample.
High prevalence accuracy did not prove tradable forecasting: that baseline stayed in cash.
Buy-and-hold net return was −4.6931%; monthly equal-weight −4.6899%. Costs/turnover/exposure/
drawdown/Sharpe and every ledger are retained, not inferred from classification accuracy.
Negative results are research evidence, not recommendations or a universal finding that ML fails.

## 13. Feature importance

Each fitted fold records real standardized linear coefficients or impurity importance and
held-out seeded permutation loss changes with sample counts. No LLM explanation, causal effect
or SHAP claim. IBM logistic standardized coefficients are +0.215799 for return and −0.173948
for SMA5; corresponding permutation log-loss increases are0.003429 and0.004606 (N=24).
Forest impurity importance is0.55/0.45 and boosting0.568573/0.431427; these are not causal effects. Genuine IBM has only24 OOS observations and two correlated features; no robust
feature conclusion is warranted. Fold stability (historical evidence archived locally) records synthetic coefficient/
importance dispersion, signs, prediction means and changing class prevalence. Permutation
breaks temporal dependence and is descriptive; it is not a feature-selection score.

## 14. Price-only versus sentiment

Four fixed variants: price only, level, dynamics, training-selected sentiment. All use the
same common observations. Synthetic evidence (`M6_SYNTHETIC_SENTIMENT.json`, intentionally omitted; see PUBLICATION_SELECTION.md) is generated statistical
variables, not genuine historical news or FinBERT article scores. Missing genuine historical
coverage correctly prevents a real conclusion. **Genuine sentiment alpha remains UNVERIFIED.**
The fixture and all variants are retained; no synthetic financial metric is real-market evidence.
On200 shared synthetic OOS rows, log loss was0.689948 price-only,0.690822 level,0.691392
dynamics and0.692205 selected sentiment; adding generated sentiment did not improve this fixture.

## 15. ML-to-backtester

Direction→predeclared long/cash threshold→M4 next-open orders→existing costs/liquidity/lots→
Decimal ledger→analytics. Net, zero-cost/slippage gross, buy-hold and monthly equal-weight child
runs are saved separately for each fold. Every order/fill/equity/action payload replays.
Raw-price daily execution, openings/liquidity, actions and historical membership remain research
approximations; no broker/execution certification or carried cross-fold portfolio is claimed.

## 16. ML-to-optimizer

Actual Ridge forecasts supply horizon simple returns; M5 retains training-only historical
covariance and solves constrained mean variance. Probability inputs, wrong units/horizon,
stale/future/missing data and double sentiment adjustments are rejected. Arithmetic252/h
annualization is explicit and approximate. The single-IBM allocation is an identity constraint,
not a diversification achievement; forecasting magnitudes are not established as reliable.

## 17. Registry and artifacts

Schema0008 stores experiments, full versioned model payloads, actual creation timestamps,
preprocessing, calibration and immutable application forecast versions. Safe scalar/tree JSON,
no executable deserialization/upload. Build/dependency/input/config/result hashes and exact
same-environment numerical refit are checked. New training never overwrites older forecasts.
A replay regression fixed default1 versus1.0 serialization; packaged export replays on both
Python versions. No cross-hardware bitwise or administrator-proof security guarantee is made.

## 18. Genuine market-data experiments

IBM report (`M6_REAL_IBM.json`, intentionally omitted; see PUBLICATION_SELECTION.md) records all four directional families plus Ridge and M5 handoff,
actual calibration refusal, M4 comparisons, API retrieval and replay. Strict online genuine
historical training remains unavailable; retrospective price reconstruction is explicit.
No SPY/multiasset genuine history, delistings, full corporate actions, licensed complete news,
or original historical universe was invented. Old milestone DBs/archives were preserved;
new demos use migrated copies.

## 19. Automated checks

Python3.12.15: **423 passed,1 skipped,11 subtests passed**,40.36s.
Python3.14.5: **423 passed,1 skipped,11 subtests passed**,41.26s.
All387 earlier tests and11 subtests remain;36 ML tests were added. One harmless upstream
Starlette/httpx deprecation warning remains. Optional actual pinned CPU FinBERT: **1 passed**,
3.59s, separately from the core skip. Lint/format, mypy82 app modules, compilation and pip
checks pass. SQLite migration/model check and old-table hash preservation pass. Actual loopback
HTTP exercises train/walk/predict/model/forecast/metric/explanation/backtest/replay routes.
Mandatory adversarial scenarios are covered across ML and existing M2/M3/M4 prefix/timing tests:
future snapshots, future sentiment/test distributions, train-only scaler/imputation/selection,
unmatured/overlapping labels, future model refusal, forbidden targets, origin labeling, delayed
orders and probability/return unit rejection. The export bug has its own regression test.

## 20. Training/inference measurements

Synthetic seed51,5/20/50 retained assets,2022–2024 daily prices; M2 return/SMA5/volatility20;
two expanding folds, two candidate configurations per ML family, training-only fitting,
separate calibration, all-family persistence and ledger replay. These are measured local CPU
runs, with other verification processes active; no unbiased algorithm-speed comparison is
claimed. Wall times below include training, selection, OOS diagnostics and experiment writes,
not separate ledger/replay time. RSS is the peak **whole process**, including M2/database/saved
results/replay, not an estimator-only or OS memory guarantee. Timings are not extrapolated.

| Assets | Build dataset s | Logistic workflow s | Forest workflow s | Boost workflow s | 100-row Ridge inference ms | Peak RSS MiB | Cumulative commit s |
|---|---:|---:|---:|---:|---:|---:|---:|
| 5 | 0.232 | 0.473 | 0.841 | 0.802 | 0.063 | 414.6 | 0.428 |
| 20 | 0.879 | 1.690 | 2.881 | 3.175 | 0.106 | 806.8 | 1.604 |
| 50 | 2.380 | 4.686 | 7.896 | 8.052 | 0.086 | 1626.2 | 4.938 |

`M6_STAGES_{5,20,50}.json` separately measures first-fold train+preprocess and validation
inference/scoring, with candidate counts and total selection workload. `M6_BENCHMARK_*.json`
includes actual artifact bytes, feature construction, fold scores, full calibration, costs,
ledger IDs and API checks. Measured50-asset memory is substantial; parallel server workers
multiply it. Benchmarking only one feature shape does not prove a48-feature worst-case bound.

## 21. Known limitations

No reliable predictive alpha, calibrated real-market advantage or sentiment improvement is
established. Tiny/noisy/dependent IBM holdout; multiple tried families, one current survivor,
retrospective acquisition and consumed holdout preclude broad inference. Raw actions/dividends/
delistings/universe limitations, no complete genuine news rights/history, simple regime proxies,
row permutation dependence disruption and conditional bootstrap uncertainty remain. JSON logical
budgets/cooperative timers are not hard process limits. Interrupted jobs need operator recovery;
child persistence is staged. Live-data arbitrary inference, individual prediction intervals,
sector history, neural/ranking models and strategy discovery are not delivered or claimed.

## 22. PostgreSQL and Docker

Rechecked: Compose version/config pass, daemon unavailable; native initdb fails shmget with
Operation not permitted. M6 structural PostgreSQL SQL emission passes but is not runtime proof.
Prepared PostgreSQL16 CI now includes ML integration tests and has not been dispatched.
Earlier WASM transaction failures remain unresolved. Full-chain offline SQL remains blocked by
old0002's data queries; immutable prior migrations were not altered.

## 23. Readiness for Milestone 7

The typed frozen forecast, numerical artifacts, baseline comparisons, M4 ledger and M5 adapter
are ready as **research interfaces** for a separately authorized milestone. Predictive evidence
and deployment are not production-ready. Obtain licensed PIT market/actions/universe/news,
reserve a new untouched holdout, verify native PostgreSQL/containers and agree bounded strategy
search/multiple-trial controls before evaluating discovered strategies. Milestone7 was not begun.
