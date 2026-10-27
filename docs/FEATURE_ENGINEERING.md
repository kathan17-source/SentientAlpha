# Financial feature engineering — Milestone 2

Version 0.2.0; calculation engine 2.0.0. This is a daily USD research foundation. It computes
38 registered feature templates (44 default numeric outputs), preserves input provenance,
and integrates with the existing ingestion, SQLAlchemy/Alembic and FastAPI application.
No models, prediction labels, sentiment, optimization, execution engine or backtest are implemented.

## Architecture and reproducibility

`features/contracts.py` validates bounded requests and immutable source observations.
`frames.py` sorts, verifies asset/calendar identity, rejects duplicates and aligns actual sessions.
`trend.py`, `momentum.py`, `volatility.py`, `volume.py` and `statistics.py` contain pure kernels.
`registry.py` exposes descriptions, inputs, defaults, versions, output names, minimum history,
missing policy and availability conventions. `calculator.py` memoizes shared returns, sample
volatility and moving averages per asset. `engine.py` combines values with causal input clocks.
`storage.py` resolves database revisions, fingerprints the source snapshot, calculates and stores
immutable datasets. `invalidation.py` integrates with ingestion; `matrices.py` supplies ordered
numeric input matrices and explicit availability filtering. API responses have Pydantic schemas.

NumPy and pandas are the only newly declared direct calculation dependencies; both already
existed in the hardened runtime lock. NumPy supplies float64 arrays; pandas supplies tested
trailing rolling statistics. Exact versions are pinned in both supplied lock files (NumPy 2.5.4,
pandas 3.0.6). No GPU, queue or distributed service was added. Unconstrained installation from
`pyproject.toml` alone is not an exact reproduction; use the lock and recorded library versions.
Prices remain exact decimal values in storage and are converted to float64 for features;
results have numerical floating-point tolerances and are not exact-decimal accounting values.

## Parameters and mathematical definitions

All windows count **declared trading sessions**, not calendar days. Integer session parameters
are bounded to 1–504; statistical minima are enforced: sample SD/covariance/correlation/beta
require at least 2 returns, skewness 3, kurtosis 4. Fast windows must be smaller than slow windows.
Annualization defaults to 252 and accepts integers 1–365. Bollinger width defaults to 2 and
must be in (0,10]. Booleans, strings, nonfinite parameters, unknown parameters and duplicate
outputs are rejected. Select the same template repeatedly with distinct windows for multi-horizon
features, including 5, 10, 20, 50, 100 and 200. Explicit features and groups are mutually exclusive.
Without either, generation selects the full catalog.

Let C,H,L,V be raw close, high, low and volume; B is benchmark raw close; r_t=C_t/C_(t-1)-1.
For n observations, μ is their arithmetic mean, s=sqrt(Σ(x−μ)²/(n−1)) is sample SD, and σ uses
divisor n. Arithmetic comparisons and units below refer to unscaled values: returns/volatilities
are decimals, RSI is 0–100, price indicators are USD, volume indicators are shares.
“History” means consecutive valid prices from the beginning of the source segment.

| Feature | Exact calculation | Required history |
|---|---|---|
| `sma` | Mean of last w closes | w |
| `ema` | First value = SMA of first w closes; then E_t=α C_t+(1−α)E_(t−1), α=2/(w+1) | w; all segment history influences later values |
| `macd` | EMA_fast−EMA_slow; signal=SMA-seeded EMA_signal of valid MACD; histogram=line−signal | line: slow; signal/histogram: slow+signal−1 |
| `price_to_sma`, `price_to_ema` | C/average−1 | w; EMA recursive |
| `ma_crossover` | +1 when fast−slow becomes positive from ≤0; −1 when negative from ≥0; otherwise 0 | slow+1 |
| `trend_direction` | sign(SMA_fast−SMA_slow), −1/0/+1 | slow |
| `trend_strength` | abs(SMA_fast−SMA_slow)/C | slow |
| `rsi` | Δ=C_t−C_(t−1); gains=max(Δ,0), losses=max(−Δ,0); separately SMA-seed w changes then Wilder α=1/w; 100−100/(1+average_gain/average_loss) | w+1; recursive |
| `roc`, `trailing_return` | C_t/C_(t−w)−1 | w+1 |
| `momentum` | log(C_t/C_(t−w)) | w+1 |
| `relative_strength` | (C_t/C_(t−w))/(B_t/B_(t−w))−1 | w+1 in both aligned series |
| `realized_volatility` | Sample SD of last w simple daily returns × sqrt(annualization) | w+1 |
| `atr` | TR=max(H−L, abs(H−previous C), abs(L−previous C)); at segment start TR=H−L; SMA-seed w TRs then Wilder α=1/w | w; recursive |
| `bollinger` | middle=μ(C), upper/lower=μ±width×σ(C); bandwidth=(upper−lower)/middle; percent_b=(C−lower)/(upper−lower) | w for all 5 outputs |
| `downside_volatility` | sqrt(mean(min(r,0)²)) × sqrt(annualization), zero target and all w returns in denominator | w+1 |
| `vol_normalized_momentum` | Trailing w-session simple return / (sample daily-return SD × sqrt(w)); no additional annualization | w+1 |
| `volume_sma` | Mean of last w volumes, including zeros | w |
| `relative_volume` | Current V / mean(V) | w |
| `volume_zscore` | (V−mean(V))/sample SD(V) | w |
| `obv` | Segment starts at 0; add sign(C_t−C_(t−1))×V_t thereafter; unchanged close adds 0 | 1; recursive |
| `return` | C_t/C_(t−1)−1 | 2 |
| `log_return` | log(C_t/C_(t−1)) | 2 |
| `lagged_return` | r_(t−lag); explicit positive past lag | lag+2 |
| `rolling_return_mean` | Mean of last w daily simple returns | w+1 |
| `rolling_return_std` | Sample SD of last w daily simple returns, ddof=1 | w+1 |
| `rolling_skewness` | Adjusted Fisher-Pearson: n/((n−1)(n−2)) × Σ((r−μ)/s)^3 | w+1, w≥3 |
| `rolling_kurtosis` | Unbiased excess: n(n+1)/((n−1)(n−2)(n−3)) × Σ((r−μ)/s)^4 − 3(n−1)²/((n−2)(n−3)) | w+1, w≥4 |
| `rolling_zscore` | (C−mean(C))/sample SD(C) | w |
| `rolling_covariance` | Σ((r−mean(r))(benchmark_r−mean(benchmark_r)))/(w−1) | w+1 in both series |
| `rolling_correlation` | Sample covariance / (sample SD(r) × sample SD(benchmark_r)) | w+1 in both series |
| `rolling_beta` | Sample covariance / sample variance(benchmark_r) | w+1 in both series |
| `cross_sectional_momentum_rank` | Same-session trailing returns; average ascending tie ranks; (rank−1)/(N−1) | w+1 for every selected asset; N≥2 |
| `vol_adjusted_return` | Current daily return / sample SD of last w daily returns | w+1 |
| `rolling_max_drawdown` | Within last w closes, min_j(C_j / max_(k≤j) C_k −1); negative or zero | w |
| `distance_from_high`, `distance_from_low` | C/max(last w closes)−1; C/min(last w closes)−1 | w |

Defaults are 20 where a single window applies, except RSI/ATR=14; MACD=12/26/9; SMA trend
pairs=10/50; lagged return lag=1. The live definitions endpoint is the authoritative structured
catalog and provides default parameters and per-output warmup counts. Output names encode
sorted parameters, e.g. `sma__window_200`, `macd__fast_12__signal_9__slow_26.histogram`.
Each template begins at calculation version 1.0.0. Formula changes must bump its version or
ENGINE_VERSION; dependency version changes also change the dataset definition hash.

RSI conventions: gain=loss=0 yields 50; positive gain and zero loss yields 100; zero gain with
positive loss yields 0. Constant series have zero realized/downside volatility and zero
covariance where defined; z-scores, correlation, beta and volatility ratios remain null when
their denominator is zero. Bollinger bands can coincide; bandwidth is then 0 and percent B null.
OBV is a relative accumulator with no claim about absolute vendor OBV levels.

## Time semantics and leakage prevention

Each nonnull feature cell distinguishes:

1. `observation_at`: scheduled close of its labeled session.
2. `inputs_available_at`: maximum availability of the required source dependency span.
3. `inputs_ingested_at`: maximum recorded ingestion of that span.
4. `decision_ready_at`: theoretical source-time readiness, max(input availability, session close
   + processing delay); default delay 1 second, configurable 1–3600 seconds.
5. `calculated_at`: recorded materialization time, sampled after calculation and before commit.
6. `online_ready_at`: max(decision readiness, input ingestion, calculation time).
7. `earliest_execution_at`: first scheduled session open **strictly after online readiness**.

A source query requires both availability and ingestion ≤ the explicit `as_of` cutoff (or
captured current time). It chooses the latest visible revision by revision number, not UUID.
Historical corrections retain their later acquisition/ingestion clocks; they cannot silently
become information known on their original session date. A source downloaded today is not
verified historical PIT knowledge. Recorded ingestion/calculation times are not database
transaction-commit timestamps; submillisecond transaction visibility is outside this contract.

Finite features record a conservative trailing dependency span. Recursive EMA/MACD/RSI/ATR/OBV
track all observations from the contiguous segment start, including late revisions to earlier
seed inputs. Lagged returns conservatively include the labeled session's timing without shifting
other features. Benchmark clocks include the aligned benchmark window. Cross-sectional clocks
include every member; ranks require a complete, fixed requested cohort. There is no partial-cohort
ranking or implicit survivorship-free index membership. Dependency positions refer to the shared
session grid and can be resolved against dataset lineage; no future position is allowed.

Raw feature values stay on the session they describe. They are **not automatically shifted**.
Only `lagged_return` shifts a daily return. A future backtester must use readiness and execution
eligibility, not trade a close-derived value at that same close or apply another arbitrary lag.
The next-open schedule is eligibility only: it is not an order, fill simulation or price promise.
XNYS uses actual scheduled holidays/DST/early closes from exchange-calendars; supported calendar
range is 2000–2035. Synthetic weekday closes at 23:59:59 UTC and opens at 14:30 UTC are explicitly
modeled software conventions, including exchange holidays, never real exchange timing evidence.

Matrix `availability_mode="online"` (default) masks cells before online readiness.
`availability_mode="research"` explicitly models theoretical source-time readiness and ignores
later ingestion/calculation times for replay; it is not proof that the software existed then.
Even research mode respects original source availability, so it cannot move today's downloaded
real sample into a past decision. Both modes preserve availability metadata and the mode name.
Prefix-invariance is tested for every registered template by comparing 230-session prefixes
with histories extended to 340 sessions, including values, reasons and dependency clocks.

## Price basis, quality and missing observations

Only `price_basis="raw"` is accepted. Raw OHLC and benchmark close are used consistently;
`adjusted_close` is excluded even if supplied. There is no corporate-action ledger, total-return
reconstruction or delisting coverage. Raw returns around splits/dividends are not economically
adjusted investment returns. Default `quality_policy="reject_flagged"` rejects source quality
flags; explicit `allow_flagged` retains flag counts and does not repair them.

Sessions are aligned by date/calendar with no forward/backward fill, interpolation or fabricated
market observations. Duplicates are rejected after the storage layer resolves revisions. Asset
identity, calendar, finite positive OHLC and nonnegative volume are validated. Calendar mismatch
is an error. Zeros in volume remain observations, not missing rows. Leading pre-source/IPO dates
stay absent. Internal gaps reset recursive indicators and require full consecutive warmup for
finite indicators; endpoint-only momentum cannot bridge a missing session. `gap_policy="reject"`
rejects detected internal gaps. Output dates without bars retain null cells and missing reasons.
Missing benchmark sessions cannot be filled or bridged, and benchmark warmup is checked separately.

Internal NaN becomes JSON/SQL null plus a reason (`insufficient_history`,
`insufficient_history_after_gap`, `missing_observation`, `missing_benchmark`,
`missing_benchmark_observation`, `insufficient_benchmark_history`, `incomplete_cross_section`,
`zero_variance`, `zero_volume_mean`, `undefined_ratio` or `not_available_at_decision`).
Neither zeros nor sentinel prices replace missing values. No label/target columns exist.

## Immutable storage, repeat generation and invalidation

Migration `0004_feature_engine` adds four tables without changing M1 price representation:

- `feature_datasets`: unique snapshot cache key, configuration/source/definition hashes, explicit
  source cutoff and calculation time, engine version, dates, provider, normalized configuration,
  definitions/column ordering, diagnostics and source-invalidation state.
- `feature_source_assets`: dataset/asset relation and selected/benchmark role.
- `feature_inputs`: exact retained price-revision foreign keys and shared-grid positions.
- `feature_rows`: one wide JSON values/reasons/timing row per dataset/asset/session, unique composite
  primary key, with date/asset lookup index. No millions of individual feature-cell SQL rows.

Generation loads all visible prior source history (from supported 2000 onward) for stable recursive
seeding; requested start bounds output only. Cache identity combines normalized effective configuration,
feature/code/library definition hash and all selected/benchmark source fingerprints. Fingerprints
include exact reconstructed bar content, IDs, revisions, clocks and quality flags. The cutoff is
recorded but excluded from cache identity when it resolves identical inputs; a reused manifest
retains its first captured cutoff. Different inputs cannot share a dataset simply because dates match.
An identical request fingerprints inputs with three SELECT executions and reuses persisted output;
read endpoints never compute features. There is no unsafe suffix-only update of recursive/ranked
features. Changed sources generate another immutable snapshot. Conservative whole-snapshot invalidation
is intentional: it favors research correctness over partial recomputation complexity.

Ingestion marks linked datasets stale within its price-write transaction when sessions at or before
a dataset end change, including a newly available previously missing benchmark. Future-only additions
beyond a fixed dataset end do not invalidate that snapshot. Deduplicated input does not invalidate it.
Old values and revision references remain inspectable. Reads/matrices reject stale snapshots by default
(409); `allow_stale=true` explicitly opts into historical inspection. Definition/hash compatibility is
checked at retrieval; changed/removed definitions block current reads even when the stored source-status
field still says current. Regeneration uses the new definition hash and produces a separate dataset.

Calculation runs outside the write lock, then sorted PostgreSQL per-ticker advisory locks or a SQLite
writer reservation coordinate its commit with ingestion. A second source check under those locks marks
historical/concurrently changed source snapshots stale. Persisting dataset/lineage/rows is one atomic
transaction with bounded bulk batches. Failed persistence leaves no partial dataset. Application price
writes must use ingestion; arbitrary administrator mutations are outside the supported invalidation
contract. An explicit generation still detects changed reconstructed source content through its hash.

## Matrices, chronology and API usage

`assemble(session, MatrixRequest(...))` yields columns sorted by canonical feature name and rows ordered
by session date then ticker. `Matrix.to_numpy()` returns float64 inputs only, preserving missing cells as
NaN. It never creates targets, scales features, learns parameters or shuffles rows. Future chronological
train/validation/test splits must freeze dataset ID, configuration, universe and column list; fit imputers
and scalers on training only and purge label boundaries when labels are introduced in a later milestone.

Select matrix tickers, columns and date bounds explicitly. Feature groups are selected at generation;
resulting columns may be subset at assembly. Missing policies: `preserve` returns null/reasons;
`drop_row` drops any incomplete/unavailable selected row; `raise` fails instead of silently dropping.
Pagination advances across **scanned** rows, including dropped rows, so follow `next_offset` even if a
page is empty. A matrix response's row decision-ready time follows its declared online/research mode.

```sh
# First ingest enough completed source history via the existing market ingestion endpoint.
curl -X POST http://127.0.0.1:8000/api/market/ingest -H 'Content-Type: application/json' \
  -d '{"ticker":"AAPL","provider":"synthetic","start":"2020-01-01","end":"2024-12-31"}'

curl http://127.0.0.1:8000/api/features/definitions
curl -X POST http://127.0.0.1:8000/api/features/generate -H 'Content-Type: application/json' \
  -d '{"tickers":["AAPL"],"provider":"synthetic","start":"2024-01-01","end":"2024-12-31","features":[{"name":"sma","parameters":{"window":200}},{"name":"rsi"},{"name":"trailing_return","parameters":{"window":5}},{"name":"trailing_return","parameters":{"window":20}}]}'

# Substitute the actual returned dataset.id; no static dataset ID is assumed.
curl 'http://127.0.0.1:8000/api/features/AAPL?dataset_id=DATASET_UUID&start=2024-12-02&end=2024-12-31&limit=20'
curl 'http://127.0.0.1:8000/api/feature-datasets/DATASET_UUID/lineage?limit=20'
curl -X POST http://127.0.0.1:8000/api/features/matrix -H 'Content-Type: application/json' \
  -d '{"dataset_id":"DATASET_UUID","start":"2024-12-02","end":"2024-12-31","missing_policy":"preserve","availability_mode":"online","limit":100}'
```

Generation returns HTTP 201 with dataset metadata, reuse flag and elapsed seconds. `/api/feature-datasets/{id}`
provides stored configuration/definitions/hashes and source invalidation metadata, including stale evidence.
Ticker retrieval and lineage are paginated; matrix supplies practical multi-asset retrieval. Existing error
format remains `{detail:{code,message,run_id}}`; unsupported input is 422, unknown data 404, stale data 409,
busy generation 429, unavailable storage 503. Pydantic/OpenAPI schemas describe all feature responses.

Bounds: 50 selected assets, 64 feature specifications, 128 output columns, 300,000 loaded input rows,
5,000,000 output cells, windows ≤504, 2,000 returned rows and 100,000 response cells, offset ≤1,000,000.
Requests span at most 30 years from 2000 onward. One generation runs per API application process;
concurrent generation receives 429 and callers retry explicitly. This is a local research service.
Multiple server workers multiply memory use and are not coordinated by the in-process semaphore.
No synchronous timeout/cancellation or job scheduler is implemented; use narrower sets/ranges on small machines.

## Verification, performance and limits

See Milestone 2 report (historical evidence archived locally), measured 20-asset (historical evidence archived locally) and
50-asset (historical evidence archived locally) runs, real IBM check (`REAL_IBM_FEATURE_CHECK.json`, intentionally omitted; see PUBLICATION_SELECTION.md) and
actual HTTP smoke evidence (historical evidence archived locally). Reproduce the synthetic workload in an empty SQLite DB:

```sh
python scripts/benchmark_features.py --assets 20 --database /tmp/empty-benchmark20.db --output /tmp/result20.json
```

The extended test fixtures contain 320–340 deterministic **synthetic** sessions. Mathematical tests
use independent Python/arithmetic reference values; no live network is needed for the automated suite.
The IBM check replays the saved real public response from M1 with original acquisition time, not a new
provider call or synthetic extension. Its 100 actual bars cannot produce a 200-session SMA. Benchmark
absence produces null beta. Raw licensed data is not redistributed in this source delivery.

SQLite migrations, persistence and API behavior are executed. PostgreSQL types/migration definitions
remain compatible by design and integration tests can target an empty native database; native PostgreSQL
and Docker execution remain blocked locally, and prior PostgreSQL WASM failures remain unresolved.
No mocked persistence result or emitted SQL is proof of PostgreSQL runtime integration. This milestone
is ready as the software foundation for M3; it is not a production certification or evidence of alpha.
