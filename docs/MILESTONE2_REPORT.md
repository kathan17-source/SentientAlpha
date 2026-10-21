# Milestone 2 completion and verification report

Verified October 13, 2026 America/Chicago (execution timestamps extend into October 14 UTC).
Milestone 2 is implemented as an integrated local research foundation. Milestone 3 has not begun.
The existing hardened M1 architecture, three migrations, exact price storage, provider contracts,
revision history and simulation/paper restrictions are preserved. Native PostgreSQL certification
remains outstanding; “institutional-grade” is an engineering objective, not a deployment claim.

## 1. Implementation summary

38 registry templates produce 44 default float64 outputs across trend, momentum, volatility,
volume, statistical and benchmark/cross-sectional features. Configurable windows include
5/10/20/50/100/200. Source chronology and per-asset isolation feed pure reusable kernels.
Recursive indicators use documented SMA seeding/Wilder conventions and full contiguous history.
A registry, source snapshot loader, causal dependency clocks, immutable storage, invalidation and
matrix assembly form one subsystem integrated with ingestion and the existing FastAPI application.
[FEATURE_ENGINEERING.md](FEATURE_ENGINEERING.md) documents every formula and warmup, all policies
and complete usage examples. [CHANGESET_M2.json](CHANGESET_M2.json) lists added/modified source files
against the captured hardened M1 baseline and confirms old migration hashes are unchanged.

## 2. Files and architecture

Added `features/` contracts, registry, trend, momentum, volatility, volume, statistics, frames,
calculator, timing, engine, storage, invalidation and matrices; typed feature API/router;
feature SQLAlchemy models; migration `0004_feature_engine`; extended synthetic fixtures and
three feature test modules; reproducible synthetic benchmark script; formulas/report/evidence.

Modified the existing API application to include feature routes/error handling; ingestion to
invalidate snapshots within its existing transaction; shared database writer locking and base/type
placement to prevent import cycles; metadata/schema readiness; package version/dependency declaration;
CI native PostgreSQL target coverage; README/architecture/roadmap/database documentation. The historical
M1 hardening report remains intact. M1 validation and handoff documents are labeled historical.

NumPy/pandas already existed in both locked environments; they are now justified direct dependencies.
No additional runtime package family, worker, microservice, GPU or alternative persistence system was
introduced. Versions remain pinned in supplied locks; editable package 0.2.0 installs and dependency
consistency checks execute in Python 3.12/3.14. An initial no-build-isolation install failed because
setuptools was absent from the venv; normal isolated builds then installed successfully. This did not
require changing runtime locks. Generated build metadata is excluded from the source archive.

## 3. Successfully implemented quantitative calculations

SMA, SMA-seeded EMA, MACD/signal/histogram, price-to-average ratios, SMA crossover events,
trend direction/strength; Wilder RSI, ROC, log momentum, configurable trailing returns and
benchmark relative strength; sample annualized realized volatility, Wilder ATR, five Bollinger
outputs, downside RMS volatility and volatility-normalized momentum; volume SMA, relative volume,
volume sample z-score and zero-seeded OBV; simple/log/lagged returns, rolling return mean/SD,
adjusted skewness and unbiased excess kurtosis, close z-score, sample covariance/correlation/beta,
complete-cohort momentum ranks, volatility-adjusted returns, ordered rolling maximum drawdown and
close distance from trailing high/low closes.

Independent arithmetic/reference tests verify SMA at all six requested windows, EMA recursion,
RSI upward/downward/flat and Wilder update cases, MACD seed ordering, ATR true ranges, population
Bollinger width, simple/log returns, sample annualization/downside RMS, covariance/beta, sample
skewness/kurtosis, tied ranks, zero-denominator policies, peak-before-trough drawdown, OBV and
crossovers. Zero variance does not silently become a ratio of zero. A first verification run found
pandas 3 read-only rolling output arrays in skew/kurtosis; explicit writable copies fixed both.

## 4. Time safety and leakage checks

Each feature cell exposes its labeled scheduled close, required source availability, input ingestion,
theoretical decision readiness, calculation time, actual online readiness and first eligible next open.
Strict generation cutoff filters both source availability and ingestion. Recursive input clocks include
earlier seed revisions. Benchmark windows and complete rank cohorts contribute their own clocks.
Values are not arbitrarily shifted; lagged return alone uses an explicit past lag. No same-close execution
eligibility is allowed. Null output plus reason preserves unavailable/undefined observations.

All **38 templates** pass prefix-invariance tests comparing 230-session histories with 340-session
extensions using the same definitions, identities, cohort and unchanged earlier data. Tests compare
historical values, missing reasons and dependency clocks. Additional tests exercise late-revised seeds,
rank-member availability, no cross-security contamination, benchmark misalignment/gaps, source cutoffs,
no future labels, raw versus adjusted-price separation, unknown/invalid parameters, missing sessions,
nonfinite/nonpositive prices and recursive warmup resets. Existing M1 provider/domain tests also validate
finite price/volume/calendar contracts. The supported ingestion path preserves synthetic/real provenance.

Matrix online mode includes calculation/ingestion time; explicit research mode models theoretical source
readiness and labels that relaxation. Neither mode can use newly acquired real historical observations
before their original acquisition. A current-symbol cohort is not historical index-membership evidence.
Transaction timestamps are recorded precommit clocks, not submillisecond commit-visibility proof.

## 5. Storage and API integration

Four new tables retain dataset/configuration/definition/source hashes, normalized policies, exact source
price-revision FKs and wide per-session feature values/reasons/timing. Identical effective inputs reuse
an immutable dataset; definition changes create a distinct cache identity and block incompatible reads.
Ingestion marks affected datasets stale transactionally, including the creation of previously absent
benchmark data. Unchanged ingestion does not invalidate. Old evidence remains inspectable explicitly.
Calculations occur outside writer locks, with a coordinated locked source recheck and atomic bulk commit.
Tests demonstrate that a failed output write leaves no partial dataset/lineage/rows.

Pydantic generation/registry/retrieval/matrix/lineage responses are in OpenAPI. Explicit generation is
bounded (50 assets, 300k source rows, 5m output cells, 128 columns, 504-session windows) and serialized per
API process; a competing request gets 429. Read endpoints never initiate computation. Matrices sort
columns and session/ticker rows, reject targets and expose preserve/drop/raise policies. Pagination
advances through scanned rows including dropped rows. Dataset manifests expose normalized configuration.

Actual HTTP smoke testing used a running loopback server on the migrated SQLite database, separately
from TestClient tests: health/readiness/assets/definitions/OpenAPI, two-asset computed generation,
repeat reuse, ticker retrieval, multi-asset matrix and lineage all passed. The generated snapshot has
130 rows; retrieved values include a calculated SMA and return, not hardcoded response examples.
[API_SMOKE_M2.json](API_SMOKE_M2.json) records the result. IDs identify this local execution and are
not assumed to exist in a fresh installation. The source archive does not distribute local databases.

The existing working database was upgraded to 0004. A backup of its migrated, pre-feature-generation
state remains in scratch storage. Its 3,120 prior retained price revisions were preserved; later replay
added 100 real IBM source revisions. `alembic check` reports no new upgrade operations against the live DB.
Fresh migration/model checks and upgrade/downgrade/legacy preservation execute in the automated suite.

## 6. Actual executed results

| Check | Actual result |
|---|---|
| Full SQLite-backed suite, Python 3.12.15 | **174 passed, 11 subtests passed, zero failed/skipped** |
| Full SQLite-backed suite, Python 3.14.5 | **174 passed, 11 subtests passed, zero failed/skipped** |
| Existing M1 regression coverage | All 82 original tests preserved and passing in both full suites |
| Added M2 coverage | 92 tests, including all 38 per-template prefix comparisons |
| Ruff lint, complete repository | Passed |
| Ruff formatting, complete repository | Passed |
| Mypy | Passed, 38 application source modules |
| Source compilation | Backend, migrations and scripts passed |
| Editable package install / pip check | Version 0.2.0 installed; no broken requirements on both Python versions |
| SQLite schema drift/live migration | No new upgrade operations; revision 0004 |
| Actual loopback HTTP feature/API smoke | Passed; evidence linked above |
| Real IBM source -> storage -> calculation | 100 real bars; independent last SMA5 reference matched 226.41 |
| Synthetic five-year 20/50-asset workloads | Both generated/stored and reused; measured below |
| PostgreSQL 0004 offline migration SQL | Emitted successfully; **not runtime integration proof** |
| Compose CLI configuration | Passed again; no daemon/runtime assertion |
| SQLite integrity / FK consistency | `integrity_check=ok`; zero FK violations; 3,220 retained price rows and 230 feature rows |
| Native PostgreSQL/Docker/PGlite M2 execution | **Not executed/certified**; inherited environmental limits below |
| Remote CI workflow | Updated to include feature integration; not dispatched/executed here |

One dependency warning remains: Starlette's httpx TestClient adapter is deprecated. It does not skip or
fail tests; adding an unrelated compatibility package was not necessary. Provider fault cases use
controlled payloads as in M1; feature rollback/cache/concurrency tests use explicit fault injection,
while their migration/storage assertions execute against real SQLite. Those tests are not proof of
PostgreSQL behavior. The first M2 M1 run encountered a sandbox socket restriction; loopback network
permission was granted and the complete suites subsequently passed. No live provider access is needed
for deterministic automated tests.

## 7. Performance measurements

Isolated Python 3.12.15 processes, macOS 26.6.2 ARM64, SQLite, 2020-01-01 through 2024-12-31;
synthetic weekday history, one SPY benchmark in addition to selected assets, 44 default outputs.
Seeding is excluded from generation latency. Each size was measured once; no latency distribution or
production throughput claim is made. Memory is process lifetime maximum RSS, including native arrays,
source loading, ingestion and persistence, not an incremental feature-only allocation estimate.

| Measurement | 20 selected assets | 50 selected assets |
|---|---:|---:|
| Visible input bars including SPY | 27,405 | 66,555 |
| Persisted output rows | 26,100 | 65,250 |
| Output cells | 1,148,400 | 2,871,000 |
| End-to-end generation/materialization | 4.267 s | 11.198 s |
| Pre-persistence elapsed (loading/hash/calculation) | 3.294 s | 8.643 s |
| Identical repeated request | 0.758 s | 1.815 s |
| Fresh SQL executions | 6 SELECT + 1 BEGIN + 57 bulk INSERT | 6 SELECT + 1 BEGIN + 135 bulk INSERT |
| Repeat SQL executions | 3 SELECT, no INSERT/calculation | 3 SELECT, no INSERT/calculation |
| Whole-process peak RSS | 645.5 MiB | 1,403.5 MiB |
| SQLite file size | 192,364,544 bytes | 478,720,000 bytes |

[20-asset raw metrics](BENCHMARK_20.json); [50-asset raw metrics](BENCHMARK_50.json).
Timing metadata and wide JSON consume meaningful memory/storage; full snapshots remain in memory
until bulk persistence. The bounds control workload size but are not a universal memory guarantee.
Use narrowed feature sets/ranges and one API worker on constrained machines. Multiple workers multiply
memory; repeated requests still load/hash source rows, O(input rows), but execute no indicator kernels
or duplicate output writes. Conservative recomputation on changes is safer than an unverified incremental
recursive updater. A future chunked/columnar artifact path may be justified if measured workload grows.

## 8. Real observations and unresolved limits

The M1 public compact response was saved with its original acquisition time
2026-10-14T00:35:31.660411Z. M2 replayed its **100 actual IBM daily observations** from May 21–October 13,
2026 through the existing adapter and ingestion service, preserving XNYS/raw/real provenance. No missing
market bars were manufactured and no new live download occurred. Last SMA5 = 226.41 (independent mean
matched), daily price return ≈0.0165624 and Wilder RSI14 ≈52.9707. SMA200 stayed null; no SPY real history
was available, so beta stayed null. A before-acquisition research matrix masked every value. Earliest
online next-open eligibility for its last SMA was October 14, 2026 at 13:30 UTC, after acquisition,
ingestion and calculation. Real check evidence (`REAL_IBM_FEATURE_CHECK.json`, intentionally omitted; see PUBLICATION_SELECTION.md) records clocks and nulls.
Raw bulk provider data is not redistributed in the source package.

Remaining limits: raw-only calculations; no split/dividend/total-return ledger; no point-in-time
historical index membership or delisting data; limited real compact sample; fixed calendars; substantial
wide-snapshot memory; synchronous bounded local generation and no cancellation/job leasing; transaction
clocks do not establish exact commit visibility; administrator price mutations bypass application
invalidation. There are no failing executed M2 checks. These declared scope/verification limits remain.

## 9. PostgreSQL and Docker verification boundaries

Carried forward accurately from M1: Docker Compose configuration passed using CLI v2.39.4; no Docker
daemon was available for image build/startup. Native PostgreSQL 16.2 initdb was blocked by sandbox
shared-memory (`shmget`) denial. PostgreSQL 18.6/PGlite fallback had **23 passed, 3 failed, 2 setup errors**;
its rollback/authentication protocol issues are unresolved and do not certify native concurrency.
Those fallback results were not reclassified or rerun as M2 success. Architecture remains SQLAlchemy,
Alembic, SQLite locally and native PostgreSQL deployment; no substitute database was added.

M2 emits PostgreSQL 0004 migration SQL and uses UTC timestamp/FK/JSON/bulk SQLAlchemy definitions.
Emission is only structural compatibility evidence. A native empty PostgreSQL16 deployment must still
run the original and new feature integration tests without fallback client alterations. CI now includes
that path but has not been run here. Container image startup/build and migration under Docker likewise
remain gates. See the preserved [M1 hardening report](HARDENING_REPORT.md) for exact prior failures.

## 10. Readiness for Milestone 3 — Sentiment Intelligence

The local quantitative foundation is ready: stable feature names/definitions, explicit input availability,
immutable source-linked datasets, ordered numeric matrices and typed APIs provide compatible boundaries
for later sentiment features. M3 should preserve article publication/acquisition times, pinned model
versions, cached probabilities and chronological aggregation, then extend this registry/timing/lineage
contract with independently tested text inputs. No sentiment implementation or model download has begun.

Before broad research or deployment, complete native PostgreSQL/Docker gates and acquire entitled,
corporate-action-aware historical data and historical universe membership. Do not interpret this
software completion or synthetic benchmarks as profitable strategy evidence.
