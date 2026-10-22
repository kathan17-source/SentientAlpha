# Milestone 4: chronological portfolio research engine

Implementation: engine 4.0.0, package 0.4.0, migration `0006_backtesting`.
Simulation only. No broker, frontend, portfolio optimizer, model training or strategy search.
The numerical ledger is tested; the daily execution assumptions remain a research approximation.
See [executed evidence and completion report](MILESTONE4_REPORT.md).

## Architecture and boundaries

`backtesting/contracts.py` defines bounded frozen requests, raw bars, feature clocks and immutable
snapshots. `storage.py` selects retained market-price versions at a declared acquisition cutoff,
reuses M2 feature snapshots and their exact source IDs, freezes input values, orchestrates comparisons,
and persists results. It does not calculate replacement indicators or duplicate news infrastructure.
`strategies.py` defines a typed strategy protocol and frozen current context; `engine.py` schedules
chronological events, translates target weights into quantities, and owns the event loop.
`execution.py` applies opening prices, costs, liquidity and cash/position constraints.
`ledger.py` owns Decimal cash, quantities and weighted-average cost. `analytics.py` derives statistics
from those ledgers. `evaluation.py` defines chronological splits and walk-forward boundaries.
`api/backtesting.py` exposes the bounded simulation jobs and paginated artifacts.

Future internal strategies can implement `targets(Context) -> dict[str, Decimal]`. Context contains
only a UTC decision instant, observation date, already published prices/features, current quantities
and cash, all as immutable tuples. There is no database, feed, dataframe or future table. This is an
interface boundary, not a sandbox for malicious Python. Public requests select three allowlisted
strategies and cannot submit code, callbacks, labels, external signals or arbitrary feature columns.
Target quantities and predictive/sentiment strategies remain future extensions.

## Event sequencing and information clocks

Each session has an opening event and a closing valuation event from the existing calendar.
Corporate actions run before opening fills; simultaneous splits run before dividend cash credits.
At an opening, previously submitted eligible orders execute, sells before buys, then ticker/order ID.
At a close, exact current raw closes value holdings. A missing close for any held security fails the
run; stale marks, liquidation proceeds and delisting recovery values are never invented.
A decision event occurs after its completed observation close and required input readiness:

- Price readiness: max(scheduled close + 1 second, recorded provider availability).
- Online policy adds actual ingestion; an SMA additionally requires M2 `online_ready_at`, including
  its calculation/materialization and all dependency ingestion clocks.
- Explicit `research_replay` retains provider availability and M2 `decision_ready_at`, but ignores
  later ingestion and materialization. This makes historical synthetic replay possible. It does
  **not** assert that today's calculated feature existed online in the past.
- For each observation date, the decision waits for all eligible selected inputs. This conservative
  shared decision clock may delay other assets when one input arrives late.
- Each order's earliest execution is the existing `next_open(calendar, decision)` strictly after
  readiness. Features are not shifted again. Data published before next morning's open can trade
  that open; data published at/after that open waits for a later open.
- Old delayed observations cannot replace newer already-published observations for a ticker.

Orders record observation day, provider availability, input ingestion, optional feature readiness,
signal/submission instant, earliest execution, actual execution, strategy and feature snapshot.
Close valuations have separate timestamps. Execution cannot precede submission or readiness.

Neither policy overrides real provider acquisition with guessed historical publication times.
The retained public IBM sample acquired after its period correctly yields `insufficient_data` and
no fills. An online historical run can be all cash because its features were created later.
Requests return status separately from cash-portfolio statistics; no eligible decisions means
`insufficient_data`, whereas a valid deliberate zero allocation is a completed cash experiment.

## Raw prices, calendars, actions and unresolved market knowledge

The only accepted convention is `raw_daily_research_approximation`. Raw open and close come from
retained provider OHLCV; adjusted close and total-return series never become executable prices.
Daily bars were captured after their historical opening/closing events. The engine retrospectively
uses their raw open/close as event observations for fills/valuation, while shielding strategies
from the day's later prices and volume. This is not independent opening auction timestamp evidence.
Every manifest has `execution_certified: false`; there is no API switch that can claim certification.
Only original revision-1 prices are executable. Later retained revisions are refused in both modes
because a revised daily bar does not establish the original opening print. Replay continues to use
its copied original snapshot after later provider revisions or feature invalidation.

Source currency must be USD; known calendar must match; quality flags are rejected. A raw bar can
have optional missing fields in the internal feed contract; the current M1 provider/database normally
requires complete OHLCV. Missing opens/suspended sessions reject an opening attempt. Missing assets
at ingestion fail clearly. Missing held closes fail valuation. No delisting cash assumption exists.
The weekday synthetic calendar includes exchange holidays; real XNYS uses the existing holiday,
early-close and DST calendar. It is not reasonable to describe synthetic weekdays as actual exchange
sessions. A fixed requested universe is recorded; membership changes/delisted constituents are not
implemented, and unknown strategy members are refused. No survivorship-free claim is supported.

Explicit bounded action records include ticker, session, type, amount/ratio, known_at and source.
They must have been known by their effective open and snapshot cutoff. Splits multiply holdings,
preserve total cost basis and divide prior reference marks; they never rewrite old bars/fills.
Pending orders for that security cancel because their units are invalidated. Fractions created by
splits remain Decimal positions; there is no guessed cash-in-lieu payment. Minimum order size can
leave an untradeable fractional residual. Dividends credit holdings times the declared cash per
share at the session open. This is an explicit cash-payment event, **not** a full ex-date/record-date/
payment-date entitlement model. On a split/payment shared session, the declared dividend amount
must be in post-split units. Real provider action completeness, delisting events and historical
membership are unavailable. Actions in tests are explicitly synthetic; real actions are not guessed.
Raw M2 SMA can be discontinuous around a split; no future-adjusted signal history is created.

## Orders and execution constraints

Market orders have deterministic sequence IDs scoped by run ID; every successful fill has an ID.
Each gets one opening attempt (IOC), with statuses submitted, filled, partial_canceled, rejected,
canceled, or expired. Partial remainders do not retry; a future rebalance can submit a new target.
New unexecuted targets supersede older ones for the same security. An end-of-run order with no
remaining execution event expires. Rejected orders do not change cash, fees or positions.
Sells execute first so proceeds are available for deterministic subsequent buys; alphabetical buy
priority can leave later securities underallocated. This is disclosed, not proportional optimization.

For raw opening price P, quantity q, slippage b basis points and side sign s (+1 buy / −1 sell):
`fill_price = P × (1 + s × b/10000)`.
`commission = fixed + per_share × q + percentage × q × fill_price`.
`slippage_cost = q × abs(fill_price − P)` is attribution already included in cash prices; it is
not subtracted twice. Defaults are $1 fixed fee, 5 bp slippage and 1% participation. Explicit all-zero
costs are allowed and warned as a zero-cost experiment. This is not a calibrated impact model.
Volatility-sensitive slippage, auctions, spreads, intraday capacity and stochastic execution are absent.

Capacity uses the **immediately previous session's** volume, only if that volume was available under
the chosen information policy by the current open. It does not use full current-day realized volume.
Capacity is floor(previous volume × participation), shared by that ticker's opening attempts.
Zero/thin volume rejects or partially fills. Unknown prior volume rejects by default; the explicitly
named `unlimited_approximation` opt-in removes that constraint. Reported volume is not evidence of
opening auction capacity. Costs cap fills by available cash and post-cost raw marked position weight;
no borrowing, negative cash, short sales or leverage. Sells cannot exceed holdings and proceeds
must cover fees. Target quantities floor to whole shares; action-created fractions can remain.
No cash is reserved because there is a single deterministic event loop and one attempt per order.

## Decimal accounting and reconciliation

Provider prices retain M1's eight-place normalization. The ledger uses Decimal arithmetic (default
28 significant digits), stores numerical accounting as decimal strings in JSON on both SQL dialects,
and never routes money through SQLite floating NUMERIC. Float conversion is confined to analytics.
Acquisition cost includes buy fees. Weighted-average cost basis, rather than FIFO, allocates cost to
partial sales; sale P&L is proceeds less sale fees less removed acquisition basis.

`equity = cash + Σ(quantity × current raw close)`.
`unrealized = market value − remaining acquisition cost basis`.
`equity − initial capital = realized P&L + unrealized P&L + dividend cash`.
Every valuation checks the last identity within 1e-8 dollars. Fees are already embedded in basis or
realized P&L. Split-adjusted quantities preserve aggregate basis. Gross/net exposure coincide in the
long-only implementation. Snapshots retain cash, market value, equity, realized/unrealized P&L,
dividends, fees, slippage, exposure, quantity, basis, weights and reconciliation residual.
External deposits/withdrawals are not accepted; no capital-flow-adjusted TWR is claimed.

The independent four-session golden scenario buys 50 shares at 10.10 plus $1, sells 27 at 11.88
less $1, then sells 23 at 13.86 less $1. Equity is 1000, 1044, 1112.76, 1131.54; final cash and equity
are $1,131.54, total realized profit $131.54, commissions $3 and slippage $11.46. Expected figures
are manually written in tests, not obtained from another invocation of the ledger.

## Strategies and comparisons

Buy-and-hold allocates on its first eligible decision; default once, with configurable later rebalance.
Equal-weight divides among the fixed requested universe; daily, weekly (ISO week), monthly, once and
signal-change schedules are available. Moving-average trend uses an **existing registered M2 SMA**
column: close > SMA holds its allocation, otherwise cash. Missing SMA prevents that asset's decision;
there is no imputation or target injection. Its natural default in the demo is signal-change rebalance.
A strategy change or target flip uses the same normal order/cost machinery.

Requested buy-hold, monthly equal-weight and signal-change SMA baselines use the same capital,
calendar, dates, source versions, costs, timing and valuation policy. Benchmark initialization also
waits for its first eligible close; there is no privileged purchase at the start's already-known close.
A moving-average benchmark requires a matching SMA dataset. Genuine SPY can be evaluated when
Alpha Vantage SPY observations are already stored at the same cutoff/calendar; synthetic SPY is
never represented as a real market benchmark. Missing reference data has explicit insufficient status.
The first completed comparison is the documented relative benchmark. Curves join on identical dates
and capital before relative statistics are available. Comparisons are engineering tools, not evidence
of alpha, parameter selection or future profitability.

## Metric definitions

Let E0 be initial capital, Et daily closing equity, rt=Et/E(t−1)−1, N the recorded sessions.
The initial recorded session return is relative to initial cash. Annual convention is 252 sessions;
the synthetic weekday grid does not have precisely 252 observations a year. Risk-free and target
return are explicitly zero. Calendar CAGR and 252-session annualized return are separate measures.

| Output | Formula / convention |
|---|---|
| Total/cumulative return | EN/E0 − 1 |
| Daily return | rt; no external capital flows |
| Monthly return | product(1+rt) within month − 1; partial months retained |
| Annualized return | (EN/E0)^(252/N) − 1, requires ≥2 observations |
| CAGR | (EN/E0)^(365.25/elapsed calendar days first-to-last valuation) − 1; positive elapsed required |
| Annual volatility | sample SD(rt) × sqrt(252), requires ≥2 |
| Downside deviation | sqrt(mean(min(rt,0)^2)) × sqrt(252) |
| Sharpe / Sortino | mean(rt) × 252 / volatility or downside deviation |
| Drawdown | Et/max(E0,E1,…,Et) − 1 |
| Maximum drawdown | negative minimum drawdown; nonnegative loss fraction |
| Duration | longest consecutive underwater recorded-session count; recovery resets |
| Historical VaR/CVaR 95 | −5th percentile rt / −mean(rt ≤ that percentile); ≥20 observations, unclipped signed loss convention |
| Calmar | annualized compounded return / maximum drawdown |
| Beta | sample covariance(strategy, benchmark)/sample variance(benchmark) |
| Alpha | (mean(strategy) − beta × mean(benchmark)) × 252; arithmetic zero-RF regression intercept |
| Tracking error / IR | sample SD(active returns)×sqrt252; annual arithmetic mean active / tracking error |
| Excess return | strategy cumulative return minus benchmark cumulative return |
| Turnover | Σ absolute filled notional / (2 × mean daily equity), whole-period two-way convention |
| Trade count | successful fill count; not number of daily signals |
| Closed-lot count | each weighted-average partial or complete sale is one realized lot |
| Win rate / average P&L | fraction strictly positive realized sales / mean realized sale P&L; buy/sell fees included |
| Profit factor | positive realized sale P&L sum / absolute negative realized sale P&L sum |
| Exposure / costs | mean daily raw marked holdings/equity; sum actual commissions and slippage attribution |
| Gross counterfactual | rerun same frozen strategy with zero commissions/slippage; quantities may differ because capital differs |

No completed sells, zero risk denominator, zero benchmark variance, incompatible benchmark, short
sample or numerical overflow yields null where undefined. A cash curve legitimately has zero return,
volatility and drawdown, but undefined Sharpe/Sortino/Calmar/profit factor. Missing held valuations
produce a failed run rather than incomplete-return statistics. Very short CAGR/annualized figures are
mathematically computable but statistically uninformative. Rolling 20-session volatility/Sharpe/beta
remain null until a complete window. The backend retains calculated arrays, never decorative constants.

## Chronological evaluation and walk-forward

`Split` requires nonoverlapping train → validation → held-out test dates. `indices(days)` can purge
observations whose declared forward label horizon reaches the next segment. Optional embargo is an
explicit extra **pre-boundary guard** in session positions, not a generic post-test embargo operation.
An embargo without label horizon is rejected. No arbitrary number of days is automatically added.
These are interfaces for future labels; this milestone does not generate labels or fit anything.

Walk-forward accepts rolling/expanding history and bounded train/validation/test/step lengths.
Step must be ≥ test length; overlapping OOS windows are rejected, and incomplete trailing folds drop.
Every fold runs a frozen baseline on its test dates with independent initial cash and positions.
Past-only precomputed SMA warmup is allowed. No model training, scaler fitting, parameter selection
or test-driven ranking happens. Fold manifests retain split, frozen selection policy and child run IDs.
Actions are restricted to effective events inside that fold's test interval.

Aggregate OOS return index multiplies independent fold daily return factors, in date order without
counting any session twice. It is **not a carried portfolio**. Gap periods are omitted; annualization
uses represented sessions, and CAGR uses represented first/last calendar dates (including gaps).
Aggregate equity endpoints are labeled `linked_oos_return_index`, with no fake cash/position fields.
Aggregate trade count sums fold fills; exposure, turnover, commissions, slippage and realized-trade
ratios are null on the linked index; actual fold values are in child runs. Portfolio continuity,
retraining and parameter-selection protocols remain future work.

## Database, immutable manifests and replay

Migration 0006 adds `backtest_runs` and `backtest_artifacts`; existing market/feature/news tables and
migrations are reused. Runs contain status, timestamp, manifest, frozen input JSON, metrics and
sanitized diagnostics. Artifact rows have run FK, kind, nonnegative sequence, unique run/kind/sequence
and payload: orders, fills, equity/positions/cash, actions, benchmark curves/summaries, fold summaries.
Position/cash records are nested inside equity records; separate duplicate tables are unnecessary.
Snapshots retain original price IDs/revisions/clocks/raw values and eligible feature values/clocks,
SMA definitions and dataset ID. Persisted decimal strings preserve financial arithmetic on SQLite/PG.

Manifests include canonical configuration/hash, exact snapshot hash, complete application-source build
hash, engine/strategy/library/calendar versions, source cutoff/provider, fixed universe/dates/capital,
price/cost/information policy, definitions, seed=null (no simulation randomness), warnings and status.
Source IDs/copies identify frozen prices even when the live provider changes. This guarantee applies
to copied local inputs, not the provider's unrecorded historical versions or delivery timestamps.
Replay refuses a changed snapshot, configuration, application build or numerical dependency version.
It compares metrics **and** persisted orders/fills/equity/actions. Aggregate walk-forward replay uses
its saved child fold IDs; direct aggregate replay is refused rather than creating a fictional portfolio.
Later source revisions do not mutate copied inputs. Saved failed simulations retain error codes;
preflight invalid input/source failures have no successful run artifact and return a typed error.
Transactions atomically save run and artifacts in 1,000-row batches. There is no worker lease/recovery,
WAL job queue, or immutability enforced against a privileged database administrator.

## API and workload limits

| Method | Path | Output |
|---|---|---|
| POST | `/api/backtest` | typed run summary, 201, simulation only |
| POST | `/api/backtest/walk-forward` | independent folds + aggregate manifest |
| GET | `/api/backtest/{uuid}` | manifest/status/diagnostics |
| GET | `…/metrics` | computed return/risk/trade metrics and monthly/rolling arrays |
| GET | `…/equity?limit=500&offset=0` | paginated ledger snapshots |
| GET | `…/equity?benchmark=buy_hold` | identically evaluated paginated benchmark curve |
| GET | `…/trades?kind=fills` | fills; kind=orders or actions also supported |
| GET | `…/drawdown` | paginated drawdown curve |
| GET | `…/report` | summary metrics, benchmark/fold summaries and child IDs |
| POST | `…/replay` | bounded replay and numerical/artifact equivalence flags |

Limits: 1–50 assets, ≤10 calendar years (2000–2034), ≤4 benchmarks, ≤50 folds,
≤140,000 raw bar events and ≤300,000 persisted artifacts per run, ≤64 MiB serialized input snapshot,
1–300-second cooperative event/fold budget, result pages ≤2,000 rows with bounded offsets.
Metrics arrays are bounded by ≤10 years of sessions; comparison/fold summaries exclude duplicate
chart arrays. A per-app semaphore allows one backtest/walk/replay operation, others 429. Multiple
server workers multiply this limit; this is not a coordinated production queue. Source loading,
SQL/native calls and one currently executing fold are not forcibly canceled mid-call. Snapshot byte
budget is validated before persistence; it is not an operating-system RSS ceiling. Existing M2
feature generation retains its separate limits and documented memory cost.

Example, after ingesting actual source data or explicitly synthetic fixtures and generating an M2 SMA:

```json
{
  "tickers": ["SYN00"], "provider": "synthetic", "calendar": "weekday",
  "start": "2020-01-01", "end": "2024-12-31",
  "source_as_of": "2026-10-14T20:00:00Z", "capital": "100000",
  "information_policy": "research_replay",
  "price_convention": "raw_daily_research_approximation",
  "strategy": {"name": "moving_average", "rebalance": "signal",
    "feature_dataset_id": "REPLACE_WITH_ACTUAL_UUID", "feature_column": "sma__window_20"},
  "costs": {"fixed": "1", "slippage_bps": "5", "participation": "0.01"},
  "benchmarks": ["buy_hold", "equal_weight", "moving_average", "SPY"]
}
```

The UUID placeholder must be replaced; actual generated manifests are stored in the executed demo DBs.
The replay endpoint uses the saved manifest and snapshot rather than querying a changed live provider.
A fully executable demonstration creates an empty migrated database, synthetic raw prices and M2 SMA,
then runs signals/orders/fills/ledgers/metrics/three comparisons, independent walk-forward, persistence,
retrieval/replay and API verification:

```sh
python scripts/verify_backtesting.py --assets 1 \
  --database /tmp/new-backtest.db --output /tmp/backtest-evidence.json
# --assets 20 or 50 for five-year workloads; each DB must be empty.
# Optional --real-database /absolute/path/retained-m1-db separately verifies
# the genuine IBM sample's availability refusal; it never replaces real prices.
pytest -q
```

## Remaining integrity limits and next milestone prerequisites

Real raw opening prints/action delivery, historical membership and delistings are not independently
verified. Commercial data/news rights and FinBERT calibration remain unresolved. There is no historical
sentiment strategy; the API refuses sentiment/future-target inputs rather than pretending complete
news coverage. Existing M3 tests still protect article revisions, after-hours timing and observed versus
assumed policies, but M4 does not claim sentiment-to-trade validation. Native PostgreSQL and Docker
remain separate deployment gates. Daily fills cannot validate a spread/impact model, auction capacity,
short borrow, leverage or live trading. Synthetic profitability figures have no investment meaning.
Before M5 optimization, obtain licensed PIT prices/actions/membership, agree on realistic execution
capacity, validate genuine benchmarks, verify PostgreSQL CI, and connect a bounded optimizer through
the current target-weight contract. No optimizer has been implemented here.
