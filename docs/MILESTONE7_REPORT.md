# SentientAlpha — Milestone 7 delivery report

Version0.7.0; discovery engine7.0.0; migration0009_strategy_discovery. Implemented as bounded,
simulation-only quantitative research. **No robust genuine strategy/alpha established.**
Milestone8 was not started. Full artifacts stay in local research databases; the source archive
contains code, tests, guides and compact verification documentation, not large raw search dumps.

## 1. Summary and component status

| Component | Status | Actual evidence / limitation |
|---|---|---|
| Safe typed grammar and seeded random/small-grid search | VERIFIED | Golden logic, injection, dedup and budget tests |
| M4 execution/accounting integration | VERIFIED | All candidate scores use M4; selected order/fill/equity/action replay |
| Selection freeze and local holdout tracking | VERIFIED | Persisted pre-test lock, overlapping reservations, idempotency and failure tests |
| Untouched status outside this local registry | PARTIALLY VERIFIED | Cannot attest to external databases, private inspection or prior unrecorded searches |
| SQLite registry, leaderboard, API and replay | VERIFIED | Actual HTTP plus database/integration tests |
| ML and sentiment-capable strategy interfaces | VERIFIED | Actual M6 sklearn OOS forecasts; synthetic sentiment-variable run; real M3 clock/coverage integration tests |
| Genuine sentiment alpha | BLOCKED / UNVERIFIED | Insufficient complete compatible genuine news history |
| Genuine IBM strategy advantage | FAILED | Selected historical rule lost money and lagged cash/buy-hold |
| Robustness and regime diagnostics | PARTIALLY VERIFIED | Fixed historical stresses and lagged descriptive proxies, not calibrated execution or causal regimes |
| Native PostgreSQL / Docker | BLOCKED | Shared-memory denial / no daemon |
| GitHub Actions service integration | PARTIALLY VERIFIED | Existing workflow extended; UPDATED BUT UNVERIFIED, no configured Git remote |

## 2. Architecture and grammar

Nine-module `strategies/` subsystem, typed API and three relational registries. Existing M2/M3
cell clocks, M6 forecasts, M4 simulator/ledger and M5 solver are reused. `compare` leaves plus
AND/OR trees, finite numeric thresholds/feature comparisons, explicit exit/hold/schedule/cash
policies. No executable expressions or alternate accounting engine. Exact behavior is in
[STRATEGY_DISCOVERY.md](STRATEGY_DISCOVERY.md).

## 3. Files added and modified

New grammar/contracts/search/resolver/fitness/research/storage/allocation modules, API router,
ORM models, migration0009, two test files and four discovery/replay/context verification scripts.
Version/schema/API wiring and existing CI workflow updated. [Complete changes](CHANGESET_M7.json)
are audited; every prior test and migration0001–0008 is byte-identical.

## 4. Search algorithms

Deterministic random sampling (`seed+fold`, canonical dedup, bounded20×attempts) and exhaustively
bounded small Cartesian grid. Every evaluated unique candidate and rejection/failure is retained.
Duplicate attempts are counted and reproducible, not repeatedly evaluated. Grid refuses oversized
whole spaces. No evolutionary/Bayesian algorithm, arbitrary code or unbounded feature search.

## 5. Strategy families

Persisted SMA/EMA/RSI/MACD/bands/ATR/momentum/volatility/volume/relative strength/mean-reversion
columns are available when present. Demonstrations enumerate return, price/SMA5, RSI14, volatility20
and close>SMA5 comparisons with1/3/5/10-session holding/schedule choices. Existing trend/context
features and M6 probability/return/volatility aliases are supported under actual availability.
No invented macro history, intraday stops, shorts/leverage or broker orders.

## 6. Rule safety

Closed Pydantic schemas; validated identifier/operator/threshold/type/depth/condition limits;
actual feature-schema validation; three-valued missing semantics; no eval/exec/pickle loading.
Late news/ML/price sources cannot become historical known facts. A late cross-security observation
cannot rewind holding state. Strategy traces record calculated values and source clocks, not
LLM explanations. M4 independently checks target positions/cash and accounting.

## 7. Fitness and complexity

`F=tanh(Sharpe/3)-.2*drawdown-.1*tanh(turnover/5)-.1*complexity-.1*rolling_instability`.
All components are dimensionless and declared before test. Complexity reflects conditions,
unique features, depth and triggers. Defaults require40 sessions,5 closed sale lots,70%
decidable signals, finite required metrics, valid accounting and bounded turnover. These lots
are accounting dispositions, not independent samples. Validation floor0 rejects even the best
negative-fitness candidate. The tiny IBM demonstration explicitly uses20 sessions/2 lots to
exercise the pipeline; this is insufficient for credibility and does not relax production defaults.

## 8. Selection procedure

Generate from declared configuration only; simulate train and validation; require both eligibility;
rank by validation fitness; prefer simpler rules within declared .01 tolerance. Preserve every
score/status and freeze the selected hash, ranking, windows/config/source versions before test.
Final OOS results and stresses never select or reorder candidates. Unknown/failed candidates
remain inspectable; a no-selection run is a successful research outcome.

## 9. Multiple-testing safeguards

Complete evaluated history and attempted/duplicate counts, complexity/turnover regularization,
validation floor and historical selection, locked final evaluation, disjoint folds and explicit
holdout-reuse disclosure. No inappropriate DSR/PSR, p-value or significance claim is generated.
The local registry detects overlapping dates/assets/provider and prior M6 test windows; it cannot
attest to searches in another DB or private human inspection. More trials are not evidence of alpha.

## 10. Chronological/walk-forward method

Use existing M4 Split/WalkRequest semantics, advancing rolling/expanding history and disjoint tests.
Purged label-horizon/embargo indices are honored. ML uses only earlier-trained, matured-label M6
OOS models. Each fold starts independent cash; the linked OOS index is not a carried portfolio.
Selection frequency, rule versions, monthly outcomes and train/validation/test gaps are retained.

## 11. Backtester integration

All candidate and selected evaluations use the actual M4 order/execution/Decimal ledger, including
prior-volume capacity, next-open eligibility, fees/slippage/lots and missing valuation rejection.
Persist full selected train/validation/test/stress/benchmark ledgers; unselected candidates store
metrics/status and replayable inputs, avoiding thousands of duplicated order/equity histories.
Net and zero-cost gross are separate simulations. Fixed benchmarks are cash, buy-hold, monthly
equal weight and the existing M4 moving-average baseline. Raw daily execution remains approximate.

## 12. Sentiment/ML/optimizer integration

Observed security-level complete sentiment plus its clock, provenance/version checks and no
missing-to-neutral substitution. Complete coverage metadata learned later is still unavailable
historically. Actual persisted M3 test-double article/inference snapshots exercise this contract.
The standalone synthetic sentiment-variable experiment executes and replays without pretending
to be FinBERT/news. Actual M6 sklearn OOS forecasts on synthetic prices also execute/replay.
Online refuses research-issued forecasts; retrospective forecasts require that explicit mode;
future model cutoffs, wrong horizons and overlapping versions are refused. Genuine alpha remains
unverified. M5 active-set projection is tested as a separate typed optional boundary with real
supplied covariance/unit/timestamp constraints; discovery backtests use declared fixed weights.

## 13. Persistent leaderboard

UUID strategy/fold/run, canonical version, human/machine rule, requirements, complexity, train/
validation metrics/fitness and selected-only test results. Ranking is validation-only before and
after test; actual HTTP smoke confirms unchanged ordering. Failed/rejected and partial budget
history can be inspected. Trades join stored feature truth/clock/target with actual fills, fees,
slippage and prior cash/quantity; M4 equity routes expose real portfolio snapshots.

## 14. Genuine historical experiment

Retained100 genuine IBM raw bars,May21–October13,2026, acquired afterward; XNYS. Only one genuine
asset was available, not an invented5–20-asset adjusted PIT universe. Historical reconstruction
is explicit and this sample overlaps the previously inspected M6 holdout. It is **exploratory**,
not new untouched evidence. Search100 predefined candidates, retain every outcome.

Candidate states: `{'rejected': 82, 'eligible': 12, 'validation_weakness': 6}`; 12 eligible.

## 15. Train, validation and test performance

| Period | Net return | Sharpe | Maximum drawdown | Closed sale lots |
|---|---:|---:|---:|---:|
| Train | -0.1665% | 0.0429 | 5.9839% | 5 |
| Validation | 8.5899% | 4.3280 | -0.0000% | 2 |
| Exploratory test | -2.8966% | -2.2983 | 4.5032% | 2 |

Frozen definition: `{"entry":{"kind":"all","children":[{"kind":"compare","feature":"return","operator":"gt","threshold":0.003,"other_feature":null},{"kind":"compare","feature":"return","operator":"gt","threshold":0.0,"other_feature":null}]},"exit":null,"exposure":1.0,"holding_sessions":1,"rebalance":"weekly","missing_policy":"cash","version":"7.0.0"}`.

Test outcome: **no_out_of_sample_advantage**. Costs: commissions$4.00, slippage$194.9129; turnover1.9854; exposure6.8535%.

| Exploratory test benchmark | Net return | Sharpe |
|---|---:|---:|
| buy_hold | -1.5736% | -0.3089 |
| equal_weight | -1.5732% | -0.3087 |
| cash | 0.0000% | undefined |
| moving_average | -9.1319% | -5.0459 |

The selected rule lost money, lagged buy-hold/equal-weight/cash and had only two completed sale
lots. Positive earlier validation was not evidence of robust genuine predictability. M6's negative
ML finding remains intact; no profitable-strategy or deployability conclusion follows.

## 16. Robustness and sensitivity

Fixed validation threshold neighbors(up/down), higher fee/slippage, extra signal-session delay,
weekly schedule and reduced asset cohort. Final gross is a separate zero-cost/slippage test.
All results retained, including undefined/inactive neighbors; no retuning from stress/test.

| Check | Net return | Sharpe | Sale lots |
|---|---:|---:|---:|
| higher_cost_validation | 8.1575% | 4.2194 | 2 |
| nearby_threshold_validation | 8.5899% | 4.328 | 2 |
| lower_threshold_validation | 8.5899% | 4.328 | 2 |
| extra_session_delay_validation | 8.9918% | 4.1263 | 4 |
| weekly_validation | 8.5899% | 4.328 | 2 |
| reduced_universe_validation | 8.5899% | 4.328 | 2 |
| gross_test | -2.6977% | -2.156 | 2 |

Lagged regime-proxy counts/mean/SD and selection-switch diagnostics are in compact verification.
Concentration flags use actual realized-sale PNL, excluding unrealized attribution. These are
descriptive stress assumptions/proxies, not calibrated execution or causal market regimes.

## 17. Rejected and failed candidates

20- and50-asset100-candidate/fold searches selected no eligible strategies. Five-asset500- and
1000-candidate searches also selected none under the fixed criteria; their apparently attractive
training candidates are not promoted as final winners. Every benchmark includes an additional
predeclared impossible1000-closed-lot search that correctly returns no eligible strategy. No
fabricated leaderboard entries or synthetic success claims fill the empty results.

## 18. Adversarial checks

Golden numeric and missing Boolean rules; unsafe expression/operator/depth/feature refusal;
commutative duplicates; seed/grid/work budgets; excellent train/poor validation rejection;
two-lot filter; noisy complex rules; high-cost profit reversal; anomalous asset/two-lot PNL
concentration; future sentiment and actual M3 coverage clocks; future/mismatched M6 model
refusal; test changes cannot alter search; locked selection/config mutations refused; invalid
position targets; unstable thresholds/no-trade neighbors; no-signal search; next-open execution;
failed/consumed holdouts cannot reset; partial budget audit; cross-asset late-state regression;
real migration/API/persistence/ledger replay. Independent examples are used for logic/fitness.

## 19. Exact test/quality results

Python3.12.15: **463 passed,1 skipped,11 subtests passed**,44.92s.
Python3.14.5: **463 passed,1 skipped,11 subtests passed**,47.34s.
All423 prior tests/11 subtests are preserved;40 M7 tests added. Separate real cached CPU FinBERT:
**1 passed**,4.27s. Ruff check/format pass; mypy93 application modules passes; compileall and
pip checks pass on both versions. One upstream Starlette/httpx deprecation warning remains.
An initial sandbox socket-bind failure was resolved with loopback network permission, without
changing the legacy test. No tests were deleted or assertions weakened.

## 20. Measured resource benchmarks

Synthetic retained seed51 prices,2022–2024 source; features generated once per job; bounded
M4 expanding folds.100-candidate5/20/50 jobs use2folds;500/1000 five-asset jobs use1fold.
The training/validation windows/fixed search/cost config are retained in local raw reports.
These local CPU measurements ran with other verification activity, not isolated speed contests.
Peak RSS is the whole process (including source copy, feature generation, SQL persistence and
replay), not just a candidate kernel. Total DB bytes include earlier retained M6 experiments;
incremental bytes also include new M2 snapshots/migration/stresses, not just candidate rows.

| Assets | Requested candidates/fold | Folds | Generation s | Search s | Selected/stress/write s | Replay s | Peak MiB | Commit s | Search events/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 100 | 2 | 0.0032 | 4.354 | 0.417 | 4.164 | 498.3 | 0.045 | 34636 |
| 20 | 100 | 2 | 0.0032 | 16.363 | 0.000 | 15.736 | 1041.5 | 0.106 | 9216 |
| 50 | 100 | 2 | 0.0033 | 42.161 | 0.000 | 38.439 | 2217.9 | 0.077 | 3577 |
| 5 | 500 | 1 | 0.0157 | 7.699 | 0.000 | 7.241 | 490.5 | 0.062 | 36695 |
| 5 | 1000 | 1 | 0.0340 | 15.326 | 0.000 | 14.823 | 499.4 | 0.089 | 36867 |

Events are actual M4 calendar-event counts, not per-asset ticks. Duplicate rates, source/build
times, total/incremental DB size and detailed state counts are in VERIFICATION_M7.json (`VERIFICATION_M7.json`, intentionally omitted; see PUBLICATION_SELECTION.md).
No1000×50-asset runtime is extrapolated or claimed. Logical workload/JSON bounds are not OS RSS
limits; multiple processes can multiply memory. A process-local gate is not a distributed queue.

## 21. Replay verification

Every completed demonstration regenerates seeded candidates, selection and metrics from frozen
inputs; selected M4 order/fill/equity/action payloads match. All release DBs match the final build.
The selected five-asset run additionally replays on Python3.14. There is no executable model or
strategy deserialization. Failed/incomplete runs are refused. Full hashes/result data remain in
local DBs; public source includes replay scripts, not raw generated experiment databases.

## 22. PostgreSQL / Docker / CI debt

M6→M7 SQLite upgrade/model check preserves all21 earlier application tables and every content
hash, including ML forecasts and M4 ledgers. Original source DB unchanged. New tables3.
Native initdb still fails shmget(Operation not permitted); Docker daemon absent. Compose config
and M7-only PostgreSQL structural SQL emission pass; neither proves service integration.
Existing PostgreSQL16 ephemeral Actions workflow now explicitly runs M7 persistence/replay tests:
**UPDATED BUT UNVERIFIED**. This folder has no Git checkout/remote, so no CI run was dispatched.
Concrete next gate: publish/reconnect source to its intended repository, run the push/PR service
job, inspect fresh migrations and replay test logs, then update verification status. No production
DB/credentials are needed. Prior WASM failures remain unresolved; no weakened SQLite-only tests.

## 23. Known limitations

One genuinely observed survivor, tiny already-consumed retrospective sample, raw prices without
complete actions/dividends/delistings/universe, insufficient genuine news/rights, uncalibrated
opening liquidity and execution, low trade power, dependent observations and many tested rules.
Closed lots are not independent round trips; metrics and proxy regimes have no causal/significance
claim. Local holdout history is not global attestation. Logical byte/cooperative limits do not
hard-kill native code; crash recovery needs an operator and child persistence is staged, not an
atomic distributed transaction. Traces cap20000 records; unselected full ledgers are replayed
rather than stored redundantly. M5 projection is optional and does not secretly alter backtest
weights. Commercial deployment, auth, native services and robust predictive evidence remain gates.

## 24. Readiness for Milestone 8

The safe strategy definitions, persistent evidence, abstention/no-selection outcomes, M4 ledger,
M5 boundary and M6 forecast integration provide research interfaces for a separately authorized
multi-agent milestone. They do not establish deployability or profitable alpha. Obtain licensed
PIT actions/universe/market/news, reserve new holdouts, verify actual native CI and define typed
agent evidence/risk constraints first. **Milestone8 has not been started.**
