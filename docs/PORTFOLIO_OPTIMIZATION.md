# Portfolio optimization — Milestone 5

Package 0.5.0; optimization subsystem 5.0.0; migration `0007_optimization`.
This is numerical portfolio research using the existing M2/M3 snapshots and M4 execution/ledger.
It is not investment advice, a broker, a validated sentiment-alpha model, or Milestone 6.
Executed results and unresolved gates are in [MILESTONE5_REPORT.md](MILESTONE5_REPORT.md).

## Components and contracts

| Module | Responsibility |
|---|---|
| `optimization/contracts.py` | Strict frozen estimator/objective/constraint/sentiment/static/frontier/research/walk requests |
| `inputs.py` | Existing M2 return and M3 security-feature adapters; copied immutable clocks/values/source identities |
| `estimation.py` | Complete past-available return panels, mean/covariance estimators, explicit PSD validation |
| `sentiment.py` | Training-only one-feature normalization and signed pooled coefficient; current-cell availability checks |
| `solver.py` | HiGHS feasibility, SLSQP objectives/gradients, independent constraint validation and expected risk attribution |
| `research.py` | Rebalance callback, method/ablation comparisons and M4 chronological fold evaluation |
| `storage.py` | Running/completed/failed experiment audit, frozen inputs/configuration/build/dependencies, linked M4 ledgers/replay |
| `api/portfolio.py` | Bounded typed requests/responses, one optimization job per app process and paginated outputs |

The reusable numerical boundary is `Estimates(tickers, mean, covariance, metadata, units="annual")`
plus `Constraints`, `Objective` and current weights. Daily estimates are rejected at that boundary.
The caller cannot submit arbitrary Python, executable objective expressions, labels or LLM allocations.
Future predictors can supply validated annual estimates internally; no general predictive model or
investment committee has been implemented. Public routes load retained dataset IDs, not client-supplied
historical return tables or sentiment scores.

## Universe, raw prices and point-in-time input selection

Universe members are canonical existing asset symbols, sorted once with duplicate/unknown mapping
rejection. Requested lower/upper bounds, restrictions, costs, groups, sectors and holdings must refer
to that same order. Unknown or unavailable members are rejected; there is no silent survivorship-based
dropping of inconvenient assets. Restrictions set maximum weight to zero. A restricted asset's missing
history can still cause complete-case estimation to be insufficient; no artificial covariance is filled.
Declared sector maps are fixed research inputs, not verified historical classifications.

An existing **M2 `return` feature** is required. It is the registered one-session raw simple return,
not a newly implemented return pipeline, adjusted-close execution price or forward label. Source
price versions come from the dataset's exact `FeatureInput` IDs. Original revision-1, USD, unflagged,
calendar-compatible raw bars are retained. Revised/unknown-quality versions are rejected. Optional
genuine SPY raw observations at the same source cutoff can be frozen separately for a benchmark;
synthetic SPY is never represented as the market. M2 warmup/gap rules remain authoritative.

For a decision T, each estimation row must satisfy:

1. Observation date lies inside configured start/end and is no later than T's UTC date.
2. Every selected return is finite and nonmissing, with its own required readiness ≤ T.
3. Under `online`, readiness is M2 `online_ready_at`, including ingestion and materialization.
4. Explicit `research_replay` uses M2 `decision_ready_at`, retaining provider availability while
   ignoring later ingestion/calculation. This is an assumption, not proof of online historical use.

Rows use common actual dates and listwise deletion; there is no forward fill, missing-to-zero return,
pairwise covariance from inconsistent samples or bridging of M2 gaps. The whole frozen dataset may
contain later evaluation dates, but the estimator only selects the eligible prefix. Tests change later
prices/returns and verify prior covariance/means/weights are unchanged. Raw returns lack unprovided
dividends/actions and can jump at splits. The existing research execution limitations remain in force.

## Expected-return and covariance estimation

All expected returns are **annual arithmetic estimates** (252 times a daily estimate), and covariance
is annual (252 times a daily covariance). Expected volatility is sqrt(annual variance). These differ
from M4 realized compounded annual return/CAGR; expected values are never called realized results.

For complete return rows x1…xN:

- Historical mean: `mu = 252 * mean(x)`.
- Exponential mean: `a_i = decay^(N-i) / sum(decay^(N-j))`, `mu = 252 * sum(a_i*x_i)`.
- Conservative mean shrinkage: `mu = 252 * (1-s)*mean(x) + s*prior_annual_return`.
  The default prior is zero and s=0.25; these are declared research preferences, not fitted alpha.
- Sample covariance: `252 * centered.T @ centered / (N-1)`.
- Exponential covariance: `252 * sum(a_i * (x_i-mu_daily)(x_i-mu_daily).T) / (1-sum(a_i^2))`.
- Diagonal shrinkage covariance: `(1-s)*sample_cov + s*diag(diag(sample_cov))`.

Diagonal shrinkage is explicitly a configured fixed-intensity estimator; it is **not** advertised as
Ledoit-Wolf. No unsupported factor/benchmark-return estimator is implied. Rolling history uses the
last lookback complete observations; expanding history is bounded at 1,260 complete observations.
Minimum sample count is enforced, EW effective count `1/sum(a_i^2)` is reported, and degenerate effective
history is refused. Low effective count, limited observations relative to asset dimension and noisy
historical means are warned. The reported historical sample-mean standard error is a descriptive
IID diagnostic, not a calibrated forecast interval or autocorrelation-robust confidence claim.

Estimates record actual included dates/count, start/end, time all inputs were ready, lookback/config,
annualization/units, source snapshot identifiers, definition hash and missing policy. Symmetry is checked;
materially negative eigenvalues (<−1e−8) or nonfinite/misaligned matrices are refused. Numerical PSD
regularization floors eigenvalues at an explicit configurable annual-variance floor (default 1e−10).
Before/after minimum eigenvalue, adjustment sum, condition estimate and zero-variance count are audited.
The solver also records its covariance validation audit. No regularization is silently claimed to be
empirical risk. Sharpe/risk-parity refuse zero empirical variance components or zero invested exposure;
singular positive-variance correlation structures remain supported subject to diagnostics.

## Mathematical objectives and solver

Let w be risky weights, cash `c=1-sum(w)`, annual mu/Sigma, current weights p, horizon h in years
(`horizon_sessions/252`), annual risk-free rate rf, asset cost rates k_i, and eta turnover penalty.
The auxiliary variables u_i ≥ abs(w_i-p_i) and u_cash ≥ abs(c-c_previous) make L1 trading terms linear.
One-way turnover is `0.5 * (sum(abs(w-p)) + abs(c-c_previous))`; cash is included. Costs are
`sum(k_i*abs(w_i-p_i))`, an estimate of one rebalance as a fraction of equity.

| Method | Implemented objective / convention |
|---|---|
| Equal weight | Least-squares projection toward equal eligible risky weights at maximum permitted invested exposure; per-asset caps clip the target, leaving cash when allowed; fully invested constraints can force redistribution. Penalties can change the projection, so a constrained/cost-aware result need not be exactly equal. |
| Minimum variance | `w.T @ Sigma @ w + eta*turnover + estimated_cost`; the **entire** objective is scaled by max covariance diagonal for numerical conditioning, preserving its minimizer. |
| Mean variance | `h*(gamma*w.T@Sigma@w - mu@w - c*rf) + eta*turnover + estimated_cost`, gamma explicit. |
| Maximum Sharpe | `-(mu@w - sum(w)*rf - estimated_cost/h)/sqrt(w.T@Sigma@w) + eta*turnover`; fixed invested exposure required. |
| Risk parity | `sum((w_i*(Sigma@w)_i/(w.T@Sigma@w) - 1/N)^2) + eta*turnover + estimated_cost`; fixed invested exposure required. |

Zero costs/penalties give the classical objectives. The Sharpe and ERC methods intentionally reject
variable cash ranges rather than adding an undisclosed exposure constraint to remove scale ambiguity.
Exact equal risk shares may be infeasible under bounds/groups; percentage-share residual is returned.
Risk contributions can be negative under hedging covariance; a risk-parity label does not assert
perfect balance. Zero-variance risky components require a defensible risk-free classification first.

SciPy 1.18.1 is the added numerical dependency. HiGHS linear programming checks the supported linear
feasible set; it does not certify the additional nonlinear risk caps. SLSQP then solves from deterministic
starts, using analytical objective gradients and explicit linear/convex-risk constraints. Sharpe/ERC
also try feasible equal and inverse-volatility starts. Lowest objective among converged, validated
candidates is chosen, never the best historical test return. See the official
[SLSQP documentation](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-slsqp.html) and
[HiGHS linear programming documentation](https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs.html).

Minimum variance and mean variance with PSD covariance have convex supported objectives/constraints;
Sharpe/ERC are handled as local numerical problems. No numerical run asserts a certified global optimum.
Diagnostics retain objective/configuration, solver/status/message, iterations, objective value, tolerances,
all starts, maximum constraint violation, binding constraints, covariance audit and runtime.

A candidate is accepted only when the solver reports success, every value is finite and an independent
post-solution check passes. Tiny negative weights are clipped and excess-budget rounding normalized,
then constraints are checked again. Default feasibility tolerance is 2e−7 in weight fractions and
**relative variance capacity** for risk caps, not a large absolute variance allowance. Solver ftol is
separate (default1e−9). Failure/nonconvergence never secretly becomes equal weight. Explicit fallback
may solve a constrained equal-weight projection and returns `fallback`, original method and failure
reason. Initial allocation bound contradictions are identified; HiGHS can certify linear infeasibility.
A nonlinear solve failure means no accepted solution was found, not a proof of nonlinear infeasibility.

## Constraint engine and unsupported cases

Supported: per-asset minima/maxima, restrictions, concentration, long-only, cash minimum/maximum,
maximum invested exposure, overlapping named group minima/maxima, declared sector maxima, annual
volatility/variance caps, maximum one-way turnover including cash, compatible same-universe benchmark
weights and annual tracking-error caps, expected-return targets and rebalance thresholds.
Risk-cap slacks are normalized `(cap_variance - actual_variance)/cap_variance`; volatility/TE inputs are
standard deviations, squared before this check. Minimum supported annual volatility/TE is 1e−6 and
variance1e−12. Return targets include forecast cash return. All constraints are retained and validated;
none is silently removed to reach a green result.

A turnover threshold holds current weights only if their independent feasibility check passes.
Asset-specific cost rates are configurable fractions of traded notional, not a hidden single constant.
Exact fixed-commission/cardinality optimization, integer lots, shorts/leverage, arbitrary agent veto code,
nonlinear user expressions, factor models and target-volatility objectives are not supported. Lot/cash/
actual commissions are handled later by M4; unsupported request fields/types return validation errors.
Static optimization supports nonzero rf. M4 cash pays zero interest and its realized Sharpe convention
uses zero rf, so historical optimized comparisons require rf=0 rather than silently crediting interest.

## Sentiment adjustment and missing-history policy

The only initial candidate inputs are a single registered M3 sentiment **level, momentum or surprise**
column, with security-level scope, the matching calendar and observed source availability. Broad/sector
news is not broadcast as company sentiment. Incompatible sources/policies are unavailable; explicit
synthetic fixtures must be labeled `synthetic_fixture` and cannot be relabeled as genuine provider data.
Research replay can still ignore later inference/materialization, so `verified_history` denotes the
requested observed source/coverage contract, not a claim of actual online pipeline operation.

The training interval must end before evaluation. For each training signal, construct a one-session
next-eligible-session **raw open-to-close** return label, requiring signal readiness strictly before
that open and the completed label's provider availability (plus ingestion online) before fit time.
The last training signal is purged if its next-session label would cross train_end. No held-out target
is used to normalize or fit lambda. The intraday label is an executable next-session drift component;
adding it to a historical close-to-close expected-return proxy is an explicit approximate additive
arithmetic model, not an exact total-return forecast or asserted alpha relationship.

Only complete eligible windows, finite nonmissing values and enough training pairs are fitted.
Normalize with the **training** pooled mean/sample SD, clip z to [−3,3], then fit centered pooled OLS:
`lambda_daily = sum((z-z_bar)*(y-y_bar))/sum((z-z_bar)^2)`.
`mu_adjusted_annual = mu_base_annual + 252*lambda_daily*z_current`.
The fitted intercept is retained diagnostically but is not added a second time to the base return.
The coefficient may be negative, negligible, uncertain, or unavailable. The API provides no manual
positive-lambda override. Pooling across securities assumes a common slope; IID standard errors are
explicitly descriptive because serial/cross-asset dependence and model uncertainty remain unresolved.

Every adjusted asset records its exact raw signal, z, annual adjustment, source dataset/column,
coverage and readiness. Model metadata records training bounds, sample count, normalization, slope,
intercept, descriptive uncertainty and exact training label lineage. A current signal must be for the
current decision observation date; there is no sentiment forward-fill. Training updates are confined
to the configured interval, never chosen from test performance. Genuine historical coefficient estimation
remains unavailable on the retained limited/partial real news samples.

`no_news_observed`, genuine neutral zero, missing provider coverage, insufficient history, unsupported
inference, unverified source policy and insufficient statistical evidence remain distinct. No missing
value is replaced with zero. Default unavailable policy refuses an adjusted allocation. Explicit
`price_only` fallback returns `price_only_fallback` and the reason, preserving the completed base result.
A fixed predeclared level/momentum/surprise ablation list is supported; there is no arbitrary combination
search, winning-test selection or claim of empirical significance from one strong backtest.

## Expected risk, explanations and implementation costs

For validated weights, output expected annual return including forecast cash, variance, volatility,
Sharpe, marginal volatility contributions `w_i*(Sigma@w)_i/sigma`, percentage variance contributions,
ERC residual, cash/invested weights, turnover, estimated costs, HHI including cash, largest position,
sector exposure, correlation matrix/weighted correlation and compatible predicted tracking error.
Undefined ratios are null; expected risk is never called realized risk. Contribution sums are tested
against portfolio volatility. Explanations identify actual binding constraints, calculated weight
changes, risk attributions and sentiment adjustments; they do not invent causal market narratives.

Ex-ante k_i estimates influence the objective only. They are **not ledger cash entries**. M4 charges
actual configured fixed/per-share/percentage commissions and raw-opening slippage once. Targets are
floored to 1e−12 weight precision before M4 whole-share conversion; actual lot rounding, available cash,
liquidity, price gaps and minimum orders can change achieved holdings. Proposed weights, first subsequent
closing weights and their constraint slacks under the decision's estimates are preserved separately.
Target constraints are not advertised as permanent realized-weight/risk guarantees after price moves
or partial fills. No future Risk Manager Agent is simulated.

## Rebalancing, comparisons and walk-forward

`OptimizedStrategy` is a trusted internal adapter that selects only the eligible frozen prefix at
M4's actual decision timestamp. Its only execution output is target weights. The original M4 simulator
submits orders and applies next-open timing, price gaps, cash, fees, liquidity and the exact Decimal
ledger. Public strategy callbacks never receive an arbitrary code/table API. Internally retained
future rows are filtered by date **and** readiness, with adversarial tests changing future values.
No second execution simulator, accounting ledger or realized performance implementation is introduced.

Monthly, quarterly and bounded explicit observation-date schedules are supported. Every rebalance
re-estimates past-available rolling/expanding moments; configured hyperparameters stay fixed. Source
cutoff, universe, costs, dates, calendars and price convention match across all predeclared methods.
No optimization uses the evaluation dataset all at once. Missing/failing methods and all predeclared
ablations remain in results. Available genuine SPY can use the same M4 convention; otherwise it has an
explicit insufficient status. Relative realized metrics use genuine SPY if completed, else completed
equal weight. M4 analytics supply CAGR/return/volatility/Sharpe/Sortino/drawdown/turnover/costs and relative
metrics. Actual concentration and time-varying exposures/holdings come from existing ledger snapshots.

Walk-forward reuses M4 `WalkRequest`/chronological `Split`: rolling/expanding training, validation and
disjoint test/step windows. Fixed estimation settings are declared before OOS. Prior-only moments can
update after an OOS observation has actually become available; this is online adaptation, not selection
using a later test outcome. Sentiment labels remain in the declared pre-evaluation training interval.
There is no general model/scaler training or strategy search. The supervised sentiment label is one
session and purged at its training boundary; M4's optional forward-label guard interface remains intact.

Every fold starts with independent cash/positions and stores separate linked M4 ledgers. OOS return
factors are linked without duplicate sessions; the aggregate is a **return index**, not fictitious
carried holdings. Aggregate trade/cost/exposure ratios without a consistent single cash ledger are
null; fold values remain available. Parameter selection and retraining infrastructure beyond this
one-signal M5 fit are Milestone 6 or later work, not silently implemented here.

## Efficient frontier

A declared bounded gamma grid produces independently solved constrained mean-variance portfolios from
the same frozen expected returns/covariance/sentiment adjustment. Every point records weights, expected
risk/return/Sharpe, solver status and constraint slacks. No decorative interpolation is generated.
Failed points remain labeled. With costs or nonstandard constraints this is a cost-aware utility grid;
it is not necessarily a classical smooth, unrestricted Markowitz frontier. It does not tune gamma on
held-out performance or choose an investment winner.

## Persistence, failure audit and replay

Migration0007 adds one `optimization_runs` table rather than redundant copies of existing feature or
ledger tables. Typed configurations, kind/status, manifest, frozen source inputs and structured results
cover estimates, covariance, constraints, solver attempts, proposed allocations, forecasts, risk,
explanations, ablations, folds and M4 run links. Running is saved before expensive execution; failures
retain a sanitized error code and any committed child links. Child M4 ledgers commit in their own
transactions; this is an audited multi-stage workflow, **not** an all-or-nothing distributed transaction.
Interrupted running jobs require operator recovery; no lease/job queue is claimed.

Each child ledger stores only its relevant execution price range; the parent experiment retains the
full frozen estimation/sentiment history. Full source snapshot IDs/hashes and definitions, availability
clocks, source cutoff, solver/runtime/dependency versions, configuration/build/input/result hashes and
warnings are recorded. Current provider revisions or source invalidation cannot rewrite a saved run.
Replay refuses changed inputs/config/build/dependencies and compares numerical results plus every
linked M4 order/fill/equity/action artifact, excluding elapsed timings and random DB link IDs.
Optimized M4 ledgers direct replay to their parent optimizer experiment, avoiding an incorrect
buy-and-hold replay of optimizer-driven targets. Older manifests require their original source build;
prior milestone archives/data are preserved. Cross-platform exact floating-point equivalence is not
certified; numerical solver feasibility has its separate documented tolerance.

## API and workload limits

| Method | Route |
|---|---|
| POST | `/api/portfolio/optimize` |
| GET | `/api/portfolio/optimization/{uuid}` |
| GET | `…/{uuid}/weights`, `/risk`, `/explanation` |
| GET | `…/{uuid}/result?section=summary|points|methods|folds|aggregate` |
| GET | `…/{uuid}/training-lineage?limit=100&offset=0` |
| POST | `…/{uuid}/replay` |
| POST | `/api/portfolio/efficient-frontier` |
| POST | `/api/portfolio/compare` |
| POST | `/api/portfolio/walk-forward` |

Requests are extra-field-forbidden, finite, bounded and simulation-only. Limits include 50 assets,
1,260 estimation rows, ten-year requested estimation-date span (source snapshots may also contain bounded later evaluation rows), 140,000 input cells/bars, three extra sentiment
ablations, five classical methods, 25 frontier points, 60 rebalance decisions per strategy, 20 OOS folds,
64MiB frozen input/result budgets and a 2MiB general result page budget. Top-level pages ≤100 items;
method decisions have separate bounded limit/offset; training lineage ≤500 rows. Full training lineage
is removed from ordinary responses and retrieved through its dedicated page. Input and result byte
budgets are logical bounds, not an OS RSS ceiling.

One optimizer job per app process is permitted; concurrent submissions get429. M4's other subsystem
semaphores are separate. Solver iterations/time, HiGHS feasibility time, event-loop budget and method/
fold checkpoints are bounded. Source loading, JSON/native calls and the currently executing stage are
not forcibly interrupted; this is a cooperative local research service, not a distributed job system.
Validation errors422, missing run404, mismatched replay409, busy/time429 and missing solver503 retain
the existing sanitized error envelope. There is no provider-key input or brokerage connection.

Example after creating an actual M2 return snapshot (replace UUID and timestamps):

```json
{
  "price_dataset_id":"REPLACE_WITH_EXISTING_UUID",
  "tickers":["AAA","BBB"],"history_start":"2023-01-02",
  "estimation_end":"2023-12-29","decision_at":"2023-12-30T00:00:00Z",
  "source_as_of":"2026-10-15T00:00:00Z","information_policy":"research_replay",
  "estimator":{"mean":"shrinkage","covariance":"diagonal_shrinkage",
    "lookback":126,"minimum_observations":60,"shrinkage":0.25},
  "objective":{"method":"mean_variance","risk_aversion":5},
  "constraints":{"concentration":0.7,"cash_minimum":0,"cash_maximum":0}
}
```

## Executable demonstrations

```sh
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python scripts/verify_optimization.py --assets 5 \
  --database /tmp/new-optimization.db --output /tmp/optimization-evidence.json
# Repeat with --assets 20 or --assets 50, each on an empty DB.
python scripts/verify_sentiment_allocation.py \
  --inputs /tmp/toy-inputs.json --output /tmp/toy-sentiment-evidence.json
python scripts/verify_real_optimization.py --source /absolute/path/retained-data.db \
  --database /tmp/new-genuine-copy.db --output /tmp/genuine-estimation-evidence.json
python scripts/replay_optimization_export.py docs/M5_FROZEN_DEMO.json
pytest -q
```

The packaged `M5_FROZEN_DEMO.json` is a complete synthetic standalone allocation export. The replay
helper verifies inputs/configuration/build/dependencies and the saved numerical hash without database
or provider access. Linked comparative ledgers replay through their optimizer database/API manifest.

The first script executes the 18-stage price-only research demonstration, all five objectives, actual
frontier solves, monthly M4 trading, all-method comparisons, independent folds, database persistence,
retrieval and exact frozen-input/ledger replay. The second uses **explicitly generated statistical
signals, not observed news or FinBERT scores**, to test normalization, signed lambda, level/momentum/
surprise ablations, OOS forecast diagnostics and ledger replay. It saves all predeclared variants and
its complete fixture manifest, never an alleged genuine sentiment history. The third reads the
existing genuine IBM sample, migrates a copy, checks preservation hashes, estimates currently known
returns/risk and correctly refuses historical decisions before acquisition. One asset is an identity
allocation, not meaningful diversification or investment validation.

## Remaining gates

Genuine complete compatible historical news is insufficient; no empirical lambda, out-of-sample
sentiment advantage, calibrated probabilities or alpha is claimed. News/model commercial rights remain
unresolved. Historical universe/sector membership, raw-price/actions/dividends/delistings and daily
opening liquidity are still imperfect. M5 optimized comparisons currently reject explicit corporate
action records; M4's standalone action tests remain intact. Native PostgreSQL and Docker runtime are
blocked; prepared CI/offline SQL emission are not successful native execution. M2's separate 44-output
memory cost is unchanged. Before M6, obtain licensed PIT data and holdouts, define forecast horizons,
train-only preprocessing and calibration, verify native service CI and use this tested structured
estimate/target interface. No Milestone6 predictor or search engine exists in this delivery.
