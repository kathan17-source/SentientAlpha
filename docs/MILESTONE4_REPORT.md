# SentientAlpha — Milestone 4 completion report

Delivered 2026-10-14: package 0.4.0, backtesting engine 4.0.0, migration 0006.
**Working simulation and research evaluation are delivered. Daily execution remains a labeled research
approximation; real-market execution, native PostgreSQL and Docker are not certified. M5 is not implemented.**

| Component | Classification | Evidence / boundary |
|---|---|---|
| Decimal ledger, costs and constraint kernels | VERIFIED | Independent golden ledger, partial-sale/action/constraint tests |
| Chronological synthetic portfolio simulation | VERIFIED | Whole-system future-price/volume/late-feature tests and frozen replay |
| Existing M2 feature integration | VERIFIED | Registered SMA, exact original source-version matching, current/readiness clocks |
| Analytics and benchmark machinery | VERIFIED | Independent return/volatility/drawdown/VaR/CVaR/regression references; actual ledgers |
| SQLite migration/persistence/API/replay | VERIFIED | Full migration/model tests, retained-data hash comparison, TestClient and actual loopback HTTP |
| Baseline walk-forward / split interfaces | VERIFIED | Disjoint OOS folds, explicit purge/guard indices, frozen parameters, independent capital |
| Realistic execution and real corporate-action histories | PARTIALLY VERIFIED | Raw retrospective daily events, explicit synthetic action records; no certified auctions or complete action feed |
| Genuine market benchmark / historical universe | PARTIALLY VERIFIED | Stored genuine SPY supported when available; demo SPY insufficient; fixed current universe |
| Sentiment-to-trade / ML retraining integration | BLOCKED | Sufficient historical sentiment coverage absent; strategy types refuse unsupported sentiment/targets |
| Native PostgreSQL / Docker runtime | BLOCKED | Shared-memory permission / absent daemon; CI prepared, unexecuted |
| Full-chain offline PostgreSQL SQL emission | FAILED | Existing 0002 data-query migration cannot run on offline MockConnection; scoped M4 SQL emission passes |

## 1. Implementation summary

A deterministic multi-asset daily event simulator now turns already eligible information into targets,
orders, constrained raw-opening fills, reconciled cash/positions/equity and actual computed statistics.
Immutable inputs, configurations and application/library builds are recorded and checked on replay.
There is no optimizer, strategy search, investment committee, broker or decorative frontend.

## 2. Architecture decisions

Contracts/feed snapshots, existing calendar, M2 clock provider, frozen current-only strategy context,
order generation, execution constraints, Decimal ledger, statistics, chronological evaluation and
persistence are separate modules. Source observation, availability, ingestion, feature readiness,
decision, earliest execution, fill and closing valuation are distinct. Retrospective raw daily event
prices are explicitly approximations. Online mode honors all actual clocks; research replay ignores
later ingestion/materialization but retains provider availability. No guessed historical publication
policy is introduced. Orders make one IOC opening attempt; no double lag or closing fill.

## 3. New and modified files

New `backtesting/` package: contracts, strategies, engine, execution, ledger, analytics, evaluation,
storage and version module. New API router, two ORM models, migration 0006, domain/integration tests,
reproducible demo and allocation profiler, engine guide, report and measured JSON evidence.
Modified app routing/exception handling, expected schema revision/model registration, package metadata,
README/architecture/roadmap, PostgreSQL CI and one obsolete old endpoint-absence assertion.
[Exact changeset](CHANGESET_M4.json) and [source hashes](SOURCE_SHA256_M4.json) enumerate delivery files.
Original migrations 0001–0005 and all other original tests remain byte-identical to the pre-M4 baseline.

## 4. Execution models implemented

Long-only unlevered market orders use raw next eligible opens; fixed/per-share/percentage commissions,
fixed bp adverse slippage, previous-session available volume, participation/minimum-volume/quantity,
unknown-volume policy, cash and post-cost position constraints. Sells precede buys deterministically.
Partial remainders cancel; missing/suspended opens reject; missing held closes fail valuation.
This is not a calibrated impact model. Costs do not use future same-day realized volume.

## 5. Portfolio accounting verification

Weighted-average acquisition basis includes buy fees; partial sales remove proportional basis and
record realized P&L net of sell fees. Every close checks equity=cash+holdings and total-profit
reconciliation within 1e-8 dollars. Cash, positions, basis, realized/unrealized P&L, dividends,
commissions, slippage, exposures, weights and residual are persisted. No external capital flows,
shorts or leverage. Whole-share target rounding can leave cash and action-created fractions.

## 6. Corporate-action handling status

VERIFIED synthetic split/dividend math and event ordering. Splits preserve total basis, alter quantities
and reference marks, cancel pending stale-unit orders and do not rewrite old fills. Dividends are
explicit opening cash credits; same-day amounts must use post-split units. Real feed completeness,
ex/record/payment-date entitlement, cash-in-lieu and delisting recoveries remain PARTIALLY VERIFIED or
unimplemented. Missing held prices fail rather than invent recovery or stale valuations.

## 7. Performance metrics implemented

Daily/monthly/total/cumulative/session-annualized returns and calendar CAGR; sample annual volatility,
population downside deviation, drawdown/duration, historical 95% VaR/CVaR; zero-RF Sharpe/Sortino,
Calmar; aligned alpha/beta/tracking-error/IR/excess return; actual fill count, closed-sale-lot win rate,
profit factor/mean P&L, turnover, exposure and costs. Rolling 20-session Sharpe/volatility/beta and
zero-cost counterfactual return are computed. Undefined denominators/short samples are null. Closed
sales use weighted-average lot accounting, not positive daily-return frequency. Formula conventions,
annualization, overflow, cash/no-trade and missing-data rules are in [the engine guide](BACKTESTING_ENGINE.md).

## 8. Strategies available

Buy-and-hold, equal-weight and close-versus-existing-M2-SMA trend. Allocation and once/daily/weekly/
monthly/signal schedules are configurable. Unsupported strategy code, target labels and sentiment
columns are refused. These are engineering baselines, not validated profitable investment rules.
Genuine sufficiently complete sentiment trading remains absent; no synthetic news history is sold as
historical market sentiment. Existing M3 controlled classifiers remain clearly labeled test doubles.

## 9. Chronological validation capabilities

Disjoint ordered train/validation/test dates; session-index forward-label overlap purge and optional
explicit pre-boundary guard. No random splitting, fitted scaling, parameter selection or training.
Embargo without label-overlap rationale is rejected. Frozen baseline policy cannot select parameters
from validation/test outcomes. Full-table callbacks and unknown universe/feature members are refused.

## 10. Walk-forward capabilities

Rolling or expanding train history, declared validation/test/step lengths, complete-fold requirement,
nonoverlapping OOS evaluation and maximum-fold bounds. Each child starts with independent initial cash;
OOS return factors are linked without duplicate dates. Aggregate index is labeled separately from
actual fold cash/position ledgers; continuity/optimizer retraining is not pretended. Each measured
five-year demonstration ran seven folds and persisted their split/configuration/child IDs.

## 11. Data/API/database integration

Reuses existing retained prices and M2 feature values/clocks/source IDs. Adds `backtest_runs` plus
uniquely ordered `backtest_artifacts`; position/cash histories nest in equity records. Atomic bounded
batches persist orders/fills/actions/curves/metrics/benchmark/fold summaries. Request limits include
50 assets, ten years, four benchmarks, fifty folds, event/artifact/snapshot budgets and cooperative
time limits. One job per app process; pages at most 2,000 rows. No OS memory ceiling or distributed
worker recovery is claimed. The read-only-original migration-copy check preserved **3,220 raw price
revisions and 230 old feature rows**, plus hashes/counts for every old table. Actual HTTP checks use
the current loopback API at `http://127.0.0.1:8014` in addition to migrated SQLite TestClient tests.
[Migration evidence](M4_MIGRATION_CHECK.json); [HTTP evidence](M4_HTTP_SMOKE.json).

## 12. Exact automated verification

- Python 3.12.15: **309 passed, 1 skipped, 11 subtests passed**.
- Python 3.14.5: **309 passed, 1 skipped, 11 subtests passed**.
- 67 M4 cases added to 242 existing cases. One old assertion that a future endpoint is absent now
  asserts its implemented presence; its restart and price-preservation assertions are unchanged.
- Core skipped test is the opt-in real FinBERT test, not a pass. Separately on Python 3.12 with actual
  pinned locally cached CPU weights: **1 passed**, 3.19 seconds; no classifier double in that run.
- Ruff lint and formatting pass; mypy passes all **62 application modules**; compile and dependency
  consistency checks pass on both environments. SQLite upgrade/downgrade/model checks execute in tests.
- One existing Starlette/httpx deprecation warning appears in each core run; no test was weakened to
  suppress it. Native PG/Docker checks and prior WASM failure remain separate from SQLite results.

Full captured outputs: VERIFICATION_M4.json (`VERIFICATION_M4.json`, intentionally omitted; see PUBLICATION_SELECTION.md).

## 13. Golden-ledger results

VERIFIED independently specified cash1000 → buy50@10.10+$1 → sell27@11.88−$1 → sell23@13.86−$1.
Equity sequence: **1000, 1044, 1112.76, 1131.54**. Final cash/equity **$1,131.54**; profit **$131.54**;
fees **$3**; attributed slippage **$11.46**; realized sale lots **$46.52 and $85.02**; return **13.154%**.
Manual expected quantities/prices/cash/equity are in tests, with independent return/volatility/Sharpe
calculations. Further references verify splits, fractional basis, dividends, commissions, drawdown,
tail risk and benchmark regression. These are synthetic financial identities, not real market profit.

## 14. Adversarial time-safety results

VERIFIED past fills/orders unchanged after appended future observations or altered future closes;
current-day realized volume cannot constrain that earlier open; delayed features cannot fill before
ready; actual online acquisition prevents historical use; revisions refuse retrospective execution;
corporate actions cannot rewrite earlier fills; callbacks lack a future feed; labels/unsupported news
features reject; later-fold perturbations cannot change an earlier fold's orders/equity/parameters.
M3 article/after-hours/revision tests remain intact. A sentiment-to-trade implementation is not tested
or claimed because the strategy type is absent; its unsupported inputs are rejected at M4's boundary.
Passing indicator-prefix tests alone is not the evidence for these portfolio-level checks.

## 15. Measured runtime and memory

Separate sequential Python 3.12/macOS ARM64 processes, deterministic synthetic weekdays 2020–2024,
1,305 equity sessions, one M2 SMA output and the same cost/timing convention. No FinBERT model is
loaded into these processes. Timings exclude data seeding/SMA generation where separately indicated.

| Assets | Simulation s | Net+gross+3 baselines s | Persistence s | 7-fold run/persistence s | Whole-process peak MiB | Orders | Events |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.025 | 0.127 | 0.095 | 0.184 | 199.3 | 428 | 3,895 |
| 20 | 0.389 | 1.363 | 0.861 | 2.861 | 709.9 | 12,653 | 3,895 |
| 50 | 1.202 | 4.116 | 2.054 | 7.352 | 1373.1 | 25,767 | 3,895 |

Events count scheduled open/close/decision events, not per-asset price visits; orders are separately
counted. Peak RSS includes ingestion, SMA generation, loaded sources, retained strategy/comparison
results, persistence, replay, API checks and walk-forward. It is not the simulator's incremental RAM
or an apples-to-apples comparison to M2's 44-output workload. Full JSON includes source load, seed,
SMA, replay timings and database size: [1](M4_BENCHMARK_1.json), [20](M4_BENCHMARK_20.json),
[50 assets](M4_BENCHMARK_50.json). No claim that backtesting fixes M2's approximately 1.37 GiB peak.

Independent frozen-input allocation profile: source current **140.3 MiB**,
tracked simulation peak **233.8 MiB**, incremental peak
**93.6 MiB**. Major retained allocations are parsed frozen
JSON and ledger/order outputs; this excludes interpreter/native memory and is **not RSS**.
[Allocation profile](M4_MEMORY_PROFILE.json). Bounded outputs/pagination and one job per process are
used; no GPU, queue, distributed compute or unmeasured performance claim is introduced.

## 16. Executed demonstration / real-market status

All 14 requested demo stages execute via `scripts/verify_backtesting.py`: load explicit synthetic raw
observations, select universe, configure baseline, generate genuine M2 SMA calculations, make eligible
signals/orders/fills, record ledgers/equity/metrics/comparisons, evaluate seven chronological folds,
persist/retrieve and replay copied manifests. Metrics and **all orders/fills/equity/actions** match
replay. Actual API requests also create a run and walk-forward, retrieve every required endpoint and
verify both replay flags. Demo databases live under `work/milestone4/benchmark*-delivery.db`; the source
archive includes scripts/evidence, not hundreds of MB of databases or model weights.

Separately, existing **100 genuine public Alpha Vantage IBM observations** for May21–Oct13 2026 were
read without writing the original DB. Strict online run returned **insufficient_data, zero fills**
because acquisition followed the historical period. No missing availability/actions/real SPY history
was fabricated. This is verified honest refusal, not a successful real-market investment backtest.
Synthetic curves and their reported returns establish software behavior only.

## 17. Remaining limitations

Daily retrospective prices/opening liquidity are approximations. Real action/membership/delisting
coverage, historical publication evidence, comprehensive licensed news and calibrated sentiment are
absent. No historical sentiment/fundamental/predictive strategy, optimizer, shorts/leverage, external
cash flows, portfolio carry between folds, real auctions/spreads or calibrated impact model. Missing
held valuations fail, rather than inventing returns. Source loading/native calls are bounded by logical
workload limits but not forcibly canceled; all-worker job coordination/authentication/deployment remain
later gates. The existing M2 wide-feature memory cost is unchanged.

## 18. PostgreSQL/Docker verification

Compose version/configuration pass. Runtime cannot connect to an absent daemon. Native PostgreSQL
initdb was retried once and fails `shmget: Operation not permitted`. M4-only PostgreSQL SQL emission
passes structurally; full-chain offline emission fails the retained 0002 data-query precondition and
is not repaired by altering historical migrations. Existing PostgreSQL 16 CI service now includes M4
integration tests, **not dispatched or successfully run**. Prior WASM negative tests remain unresolved
and are not native certification. [Exact checks](M4_DEPLOYMENT_CHECKS.json).

## 19. Preparation for M5 — no M5 implementation

Obtain licensed PIT raw prices/actions/membership/delistings and genuine benchmark coverage; validate
execution capacity/cost assumptions and native PostgreSQL CI; agree on optimizer objectives, feasible
bounds, cash/turnover constraints and explicit infeasibility policy. Integrate future target weights
through the tested strategy/constraint boundary and preserve frozen OOS evaluation. Portfolio
optimization, ML selection and downstream committee/frontend work stop outside this milestone.
