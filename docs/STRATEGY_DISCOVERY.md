# Strategy discovery — engine 7.0.0

Package0.7.0, schema0009_strategy_discovery. This is offline simulation research, not automated
real-money trading or an investment committee. No Milestone8 module is implemented.
Every candidate is evaluated by the existing M4 engine. No screening PNL simulator, new ledger,
new indicator formula, executable expression or LLM-generated prediction is used.

## Architecture

`strategies/contracts.py`: closed requests and recursive grammar; `grammar.py`: canonical
identity, three-valued predicates and numeric complexity; `search.py`: seeded random and bounded
grid generation; `inputs.py`: existing M2/M3 cells, M1 source versions and M6 registered forecasts;
`evaluation.py`: current-only M4 strategy adapter and dimensionless fitness; `research.py`:
train/validation search, frozen selection, final tests and stresses; `storage.py`: audit states,
reservations, registry and exact replay; `allocation.py`: optional M5 constrained active-set
proposal. API routes live in `api/strategies.py`. There are no added runtime dependencies.

## Restricted rule grammar

A comparison has `kind=compare`, an existing feature, operator `lt|le|gt|ge|eq`, and exactly one
numeric threshold or `other_feature`. Boolean `all` and `any` have2–4 children and no leaf fields.
Maximum expression depth3;6 leaves per expression and8 entry+exit leaves overall. Feature names
have a restricted lowercase identifier pattern and are checked against the **actual compatible
snapshot columns** before simulation. Unknown names, future targets, function calls, strings as
operators, nonfinite values and extra executable parameters are rejected.

```json
{
  "entry": {"kind":"all","children":[
    {"feature":"rsi__window_14","operator":"lt","threshold":40},
    {"feature":"close","operator":"gt","other_feature":"sma__window_5"}
  ]},
  "exit": {"feature":"close","operator":"le","other_feature":"sma__window_5"},
  "holding_sessions":10,"rebalance":"daily","exposure":0.8,"missing_policy":"cash"
}
```

Thresholds above are illustrative, not winning recommendations. Lookbacks are encoded in
persisted registered feature names; discovery never recalculates an unpersisted window.
Any of the existing technical/benchmark/trend/rank inputs can be used when actually present.
Market context is a numeric comparison against a retained feature, not an invented macro history.
No shorting, leverage, intraday stops, arbitrary NOT/script, conditional exchange order, or
continuous threshold interval optimizer is supported.

Canonical identity sorts Boolean children, removes repeated children and normalizes association
within the grammar, so reordered/repeated AND/OR conditions deduplicate. It is structural Boolean
canonicalization, not an exhaustive equivalence theorem prover for all real-valued inequalities.
Numeric Pydantic parameters normalize integer/float inputs. Canonical rule hash is the definition
version; each discovery/fold has its own immutable candidate UUID and provenance.

## Missing values and signal timing

Comparisons with unavailable inputs yield **unknown**, never false-neutral zero. AND(false,
unknown)=false; OR(true,unknown)=true; otherwise unknown propagates. Coverage means the entry/exit
truth is determinable, not that every raw feature exists. An OR rule may legitimately be decided
by a known technical condition without using its unknown sentiment branch.

`cash` missing policy sends zero targets when entry/exit is unknown. `hold` preserves existing
holdings on unknown signals, but never creates an entry from missing data. An absent exit rule
is false, not missing. Exit and holding expiry take precedence over entry; simultaneous entry
and exit do not open a position. A false entry alone does **not** close an existing position:
provide an exit condition or maximum holding period if desired.

Each decision reads only cells for its exact observation date, and each cell must have its own
ready timestamp≤actual decision. No signal forward-fill, price-history table or future labels
are handed to the strategy. Late cross-asset observations cannot rewind the portfolio's last
observation/holding state. The M4 simulator provides only known current prices, cash and actual
quantities. Actual fills, rather than intended orders, determine whether a security is held.

Daily/weekly/monthly entry/rebalance schedules are supported. Exits/holding limits are checked
on every eligible decision. Holding age counts observed session decisions from the first
observed filled holding; that first close counts1. It is not an intraday stop or guaranteed
fill date. Orders go to M4's first eligible opening after decision. Liquidity, missing bars,
rejections, partial IOC fills, fees and share rounding can alter holdings or leave a position
open after a requested exit. M4 refuses invalid valuation or target constraints.

The target is exposure divided by the **declared full universe** per active asset; inactive
weights remain cash. Active assets are not automatically levered/reweighted to full exposure.
Long-only targets and per-position limits are validated before search and by M4 at execution.

## Data modes, revisions and provenance

Read immutable current-compatible feature snapshots through existing `get_dataset`/`cell`.
Source revision1 raw USD/calendar-compatible prices must be unflagged and known by source cutoff.
Revised/unsupported prices are refused. Features retain source IDs, definition/source hashes,
calculation and availability provenance; no price or news acquisition is triggered by discovery.

`online` respects feature computation/source-ingestion clocks. `research_replay` uses existing
source readiness and ignores later materialization, as explicitly labeled research.
`retrospective` additionally models price readiness at close+1second, retaining original source
clocks in frozen prices. It does not backdate news. Retrospective IBM is reconstruction from a
later download, not verified PIT or live-issued trading history. Existing raw-price/corporate-
action/universe/delisting limitations remain; no total-return adjusted history is fabricated.

Sentiment must be observed-policy, security-scoped and calendar-compatible. Synthetic provider
identity requires `synthetic_fixture`; it cannot be relabeled genuine. Non-complete coverage
is missing. Even complete coverage metadata does not make a cell usable before its knowledge/
source clock. Tests exercise this distinction using actual M3 persisted test-double inference;
a late numerical sentiment value never enters the historical decision.

ML aliases `ml_probability`, `ml_return`, `ml_volatility` require exact registered M6 model IDs
and declared1/5/10-session horizon. Verify full model/JSON-artifact hashes, parent source/result
hashes and original OOS prediction membership. Model effective/training cutoffs must precede
prediction decisions. Overlapping model versions for the same asset/date/type are refused.
Research forecasts are allowed only as historical research; online additionally requires model
creation and actual prediction generation before decision. Retrospective predictions require
explicit retrospective mode. Later ad-hoc `/ml/predict` records not in the original frozen OOS
experiment are not accepted. Source build/version is retained; reading validated earlier
forecasts does not refit an old model under the new application build.

M6's genuine IBM experiment did not beat the prevalence baseline. M7 does not reverse that
finding or assume ML/sentiment adds value. Genuine comprehensive news alpha remains unverified.

## Search spaces and algorithms

Each axis enumerates thresholds or compatible other-feature comparisons;24 axes,120 unique
atomic comparisons, up to3 chosen entry conditions, predeclared joins/holding periods/schedules.
Random search uses Python `Random(seed+fold)`, bounded20×requested attempts, canonical dedup,
and up to30% randomly chosen exit predicates when enabled. Exhaustion/requested/attempt/unique/
duplicate counts and seeds are stored. Generation reads declared configuration, not price data.

Grid search enumerates **the whole** small entry-combination ×holding×schedule grid. It refuses
an entire grid exceeding the candidate budget rather than silently returning its first winners.
Random optional exits are not a separate exhaustive grid dimension. Both retain every unique
evaluated candidate, including no-trade, undefined, failed and validation-weak candidates.
Duplicates are not evaluated; aggregate attempts and deterministic generator replay explain them.
No evolutionary/Bayesian search, automatic feature discovery, threshold fitting or unlimited
parameter search is implemented. More attempts are not assumed to improve real performance.

## Fitness: exact units, penalties and eligibility

All analytics come from M4's exact Decimal ledger. Required finite Sharpe, drawdown and turnover
must exist. Default minimum40 ledger sessions,5 closed sale lots,70% determinable signals,
maximum turnover20. Invalid execution/accounting, inadequate observations/trades/coverage or
undefined required ratios is ineligible. Closed sale lots are M4 accounting dispositions, not
independent statistical samples or necessarily full entry→flat round trips. Two sale lots fail
the default guard. A configurable smaller demonstration threshold is explicitly not credibility.

Let S be annual M4 Sharpe, D maximum drawdown fraction, T M4 one-way turnover, C normalized
complexity and I=populationSD(tanh(rolling20Sharpe/3)); missing rolling history usesI=1:

`F = tanh(S/3) - .2D - .1tanh(T/5) - .1C - .1I`.

The weights/turnover scale/minima are declared configuration. There is no addition of raw dollars
to Sharpe. Tanh bounds the risk-adjusted and turnover components; costs already reduce net ledger
returns and are not deducted twice. Ratios with no denominator remain null. Profit factor/win
rate are reported but not required fitness components; an all-winning sample is not assigned
an invented infinite profit factor. Defaults do not establish significance.

With L leaves, U unique features, H=max expression depth and G=entry+explicit exit+holding
triggers, `C=(L/8 + U/16 + (H-1)/2 + G/3)/4`. Leaf thresholds/operators carry parameters; the
reported parameter count is L+G+1. This fixed complexity proxy favors simpler configurations.
At most8 leaves,16 references,depth3,3 triggers keep its scale bounded.

Training and validation must both pass eligibility. Default validation score floor0 rejects
negative fitness even when it is the best of bad candidates. Rank strictly by validation fitness;
within the predeclared .01 tolerance prefer lower C, then better score, then canonical hash.
Test returns, stresses and human inspection never reorder this leaderboard. A complete search
with no eligible strategy is a successful `no_eligible_strategy` outcome.

## Chronological windows and multiple-trial safeguards

Reuse M4 `Split.indices` for train/validation/test and optional declared label-horizon purging/
embargo. M6 ML label maturity is already enforced in original OOS forecasts. Global asset
windows avoid random panel splits. Explicit rolling/expanding windows advance training and
have disjoint tests. The verifier constructs them using existing M4 `WalkRequest` duration/
step controls. Indicators can use prior warmup history, but no future-ready value can enter.

Discovery stores all training/validation candidates and selection before final-test access.
A hashed lock contains ranked/selected definitions, windows and configuration. The frozen input
hash covers the exact retained data. The registry commits `selection_frozen_at` before consuming
a holdout. Each test is evaluated only for the frozen selected rule, never every candidate.

Holdout reservations are serialized using existing SQLite writer locks/PostgreSQL advisory
locks. Overlapping provider/date/asset reservations and prior M6 test windows in the same DB
require explicit `previously_inspected`. New source versions/configurations cannot silently
reset a reservation. Idempotency keys cannot change configuration. Evaluations mark holdouts
consumed **before** computation, so errors cannot reset them. Repeated evaluations return the
saved result; there is no test-reset or candidate-edit route. Failed evaluation requires operator
review, not a silent fresh-holdout retry. Search failure retains partial completed history.

The local registry cannot attest to private human inspection, another copied database, an
external search or earlier unrecorded M4/M5 research. `new_reservation` means a new local
reservation, not a global untouched guarantee. The genuine IBM demo declares known prior use.
Complete trial counts, complexity/turnover regularization, historical validation, fixed test
selection and fold dispersion address data-snooping risk; **no DSR/PSR, family-wise significance,
bootstrap p-value or statistical confidence is claimed**. Winning among1000 attempts does not
mean it was the only trial. Consumed tests must not be relabeled untouched in later research.

## Walk-forward, robustness and negative diagnostics

Each fold regenerates from seed+fold, evaluates earlier history, freezes its own rule and tests
forward. Capital/positions start independently per fold. A linked OOS return index is provided;
it is not a continuously carried portfolio. Selected hashes/frequencies, monthly returns,
train→validation and validation→test Sharpe gaps expose selection drift/deterioration.

Only selected rules get full M4 ledgers for train, validation, test and fixed benchmarks:
buy-hold, monthly equal-weight, cash and the existing M4 moving-average strategy when a retained
SMA exists. Other candidates retain metrics/status and are reproducible from frozen inputs;
unselected full order/equity ledgers are intentionally not duplicated thousands of times.

Predeclared validation stresses: thresholds up/down10% (minimum .001), doubled commissions+1,
doubled slippage+5bp (bounded by M4 limits), extra observation-session signal delay, weekly
schedule and removing the last declared asset. These are assumptions, not fitted execution
latencies. Comparisons retain Sharpe/return/drawdown/trade-count/turnover/profitability. Undefined
neighbor metrics and range>1 Sharpe produce a sensitivity warning; positive validation profit
turning nonpositive under high costs is flagged. No stress result changes selection.

Gross final test reruns the **same** rule with fee/slippage rates0, retaining liquidity limits.
Its holdings may differ because available cash changes, so it is a separate ledger rather than
net-plus-cost arithmetic. Final results separately label lack of advantage over cash/equal
weight and insufficient test evidence. None establishes alpha or deployability.

Realized-sale PNL by asset, largest positive-PNL asset share and top-two lot contribution flag
concentration above80%; they exclude unrealized PNL/dividends and do not imply independence.
`analyze_discovery.py` adds descriptive conditional results using prior-session fixed-universe
return sign and existing volatility versus a train-only median. Counts/mean/SD are reported;
these are observable proxies, not a fitted regime agent or causal explanation.

## Registry, replay and API

Migration0009 adds `strategy_discoveries`, `strategy_candidates`, `strategy_holdouts`. IDs,
per-run/fold/rule uniqueness, idempotency uniqueness, FKs, typed JSON and state transitions
retain version/source/search/cost/window/selection evidence. M4 runs/artifacts are reused for
all persisted trades and equity. No API updates/deletes an earlier strategy definition.

Build/dependency/config/input/prepared/result hashes are verified before evaluation/replay.
Replay regenerates the exact seeded search, selection, metrics and every selected M4 order,
fill, equity and action. Reading source-revised market data cannot alter a frozen experiment.
Old builds require their preserved milestone source. Failed/incomplete jobs are not replay
certified; no cross-hardware bitwise guarantee or protection against a privileged administrator
rewriting every hash is claimed. Safe JSON, no executable artifact upload/deserialization.

POST `/api/strategies/discover`; GET `/api/strategies`, `/leaderboard?run_id=UUID`,
`/discovery/{uuid}`, `/discovery/{uuid}/history` (including partial failure history).
GET `/{strategy_uuid}`, `/rules`, `/performance`, `/trades`, `/robustness`.
POST `/{strategy_uuid}/evaluate` only for the frozen selected rule, or discovery `/evaluate`;
POST discovery `/replay`. The multi-fold evaluation consumes that discovery's locked selections.
Leaderboard orders by fold then validation rank; OOS metrics are shown separately.
Trade inspection joins actual order/fill records to stored decision features, ready clocks,
truth values, target, actual quantity, fees/slippage and prior cash/quantity. Equity snapshots
are linked through the existing M4 route; no immediate post-fill portfolio state is fabricated.

Limits:50 assets,1000 candidates/fold,8 folds,≤5000 declared simulations,10 years,1million
signal cells,140k bars,64MiB frozen/result JSON. One process-local training/evaluation/replay
job; competing submissions429. Search budget up to600seconds is cooperative between simulator
calls; each M4 call has its own bound. Readers use separate FastAPI worker threads; there is no
unlimited synchronous job or distributed queue. Different subsystem gates/processes can multiply
memory. Candidate pages≤100, history≤500, fills≤500; traces capped20k records and labeled when
truncated. Logical JSON bounds are not OS memory/RSS limits. Auth is required before any remote
multiuser deployment; the research service remains loopback-only and simulation-only.

## Reproduction and infrastructure debt

```sh
pytest -q
python scripts/verify_discovery.py --source /path/to/retained-M6-5-asset.db \
  --database /tmp/new-discovery.db --assets 5 --candidates 100 --folds 2 --output /tmp/discovery.json
python scripts/verify_discovery_signals.py --database /tmp/new-signal-demo.db --output /tmp/signals.json
python scripts/replay_discovery.py --database /tmp/new-discovery.db --run-id UUID_FROM_REPORT
python scripts/analyze_discovery.py --database /tmp/new-discovery.db --output /tmp/contexts.json
```

Verifiers refuse existing DB destinations and migrate copies, preserving earlier observations.
The signal verifier uses packaged explicit test fixtures (development requirements needed):
generated sentiment variables, not reconstructed news/FinBERT scores; actual M6 sklearn training
and saved OOS forecasts on synthetic prices, not fabricated probability values. Complete M3
coverage/clock enforcement is independently tested with persisted synthetic article fixtures.
No private provider credentials/network data are required. Raw generated search histories and
large DBs stay outside source/package. See `MILESTONE7_REPORT.md` and compact verification summary.

Native PostgreSQL initdb and Docker runtime are still blocked locally. The existing ephemeral
PostgreSQL16 GitHub Actions workflow was inspected and extended with M7 persistence/replay tests.
It is **UPDATED BUT UNVERIFIED** because this source folder has no Git repository/remote to run it
against. Actual service CI, complete licensed PIT prices/actions/news/universe and new untouched
holdouts remain concrete gates before deployment or stronger empirical claims. Prior WASM
transaction failures remain unresolved; structural PostgreSQL SQL emission is not runtime proof.
