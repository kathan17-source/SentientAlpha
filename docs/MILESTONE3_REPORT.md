# Milestone 3 delivery and actual verification

Verified October 14, 2026, America/Chicago. Package 0.3.0; sentiment calculation subsystem 3.0.2.
Milestones 1–3 are implemented locally. **Milestone 4 has not started.** Production-quality is an
engineering objective; native PostgreSQL/container certification, commercial rights and complete
historical coverage remain separate gates.

## 1. Implementation summary and component status

The news -> retained version -> relevance -> actual FinBERT -> quantitative sentiment -> feature
snapshot -> mixed matrix pipeline is implemented. All existing 174 M1/M2 tests are preserved.
The subsystem adds 28 sentiment templates, eight evidence tables and typed bounded API operations.
It supplies transparent research inputs rather than hand-authored production labels or trading claims.

| Major component | Classification | Executed evidence / boundary |
|---|---|---|
| Core news contracts, atomic ingestion, retained revisions, dedup | VERIFIED | Actual SQLite migrations, rollback/idempotency/version/source tests |
| Federal Reserve public RSS adapter | VERIFIED | Actual 20-headline fetch -> database -> real model -> aggregates |
| Alpha Vantage public AAPL news demo | VERIFIED | Actual 50-headline fetch -> database -> real model -> security aggregates |
| Authenticated Alpha Vantage pagination/quotas/history | PARTIALLY VERIFIED | Controlled transport tests; no private subscription/coverage certification |
| Pinned FinBERT CPU inference | VERIFIED | Real probabilities, cached artifact hashes, optional batch/single/truncation test; Python 3.12 |
| Transformer inference on Python 3.14 / other hardware | PARTIALLY VERIFIED | Core compatibility passes; heavyweight path not executed there |
| Probability calibration and relevance accuracy | PARTIALLY VERIFIED | Mechanisms validated; no independent labeled benchmark/calibration study |
| 28 sentiment calculations and prefix invariance | VERIFIED | Independent arithmetic, temporal/missing/zero-variance/coverage tests |
| Price+sentiment matrices and typed HTTP API | VERIFIED | Actual loopback HTTP with real FinBERT and clearly synthetic source data |
| Exact historical provider first-seen/complete news archive | BLOCKED | Public snapshots do not provide certified historical delivery/completeness |
| Native PostgreSQL and Docker runtime | BLOCKED | Inherited environment limits; SQL emission/Compose config are not execution proof |
| Previous PostgreSQL WASM fallback | FAILED (prior, unresolved) | Prior 3 failures + 2 setup errors remain; not reclassified as M3 success |

No currently executed M3 check remains failing. The classifications separate software verification
from data entitlement, model evaluation, deployment and historical delivery assumptions.

## 2. Architecture

Small modules implement immutable contracts, two provider adapters, interpretable entity relevance,
audited ingestion, explicit optional CPU model initialization, incremental inference, aggregation,
registry metadata, snapshot generation and matrix joins. SQLAlchemy/Alembic/FastAPI and existing asset
IDs are reused. Sentiment values use the M2 feature tables and read APIs; article/model evidence uses
new relational FKs. There is no transformer import at normal startup, model per article, LLM classifier,
alternative persistence layer, GPU requirement or premature distributed queue.

See [SENTIMENT_ENGINEERING.md](SENTIMENT_ENGINEERING.md) for all formulas, policies and API examples.

## 3. Added and modified files

[CHANGESET_M3.json](CHANGESET_M3.json) enumerates exact additions/modifications against the captured
M2 source baseline and verifies original migration hashes. Principal additions: `sentiment/`
contracts/providers/entities/ingestion/model/inference/registry/aggregation/datasets/matrices;
`database/sentiment_models.py`; migration 0005; typed `api/sentiment.py`; synthetic news/model-test
fixtures, domain/integration/optional-real-model tests; profiling/provider/model benchmark scripts;
optional NLP lock, engineering documentation and machine-readable execution evidence.

Principal modifications: existing model metadata registration/schema readiness, API router/configuration,
M2 registry metadata/compatibility and matrix/cell schemas, shared matrix assembler, package version,
README/architecture/roadmap/database documentation and native PostgreSQL CI target list. All M1/M2
original tests and migrations 0001–0004 remain intact; no test was weakened to obtain passing results.
The historical M1/M2 reports/source packages remain historical evidence, not rewritten M3 claims.

## 4. Providers implemented and actually tested

Federal Reserve Board press-release RSS: fixed official feed, real HTTP transport, permitted attributed
headline metadata, actual ingestion and inference on 20 headlines dated **September 10–October 13,
2026**, collected October 14. Feed contents are a snapshot of one publisher's broad/regulatory coverage.
They are not full-market company news, complete historical coverage or 2018–2026 archive evidence.
[Real Board pipeline](M3_REAL_NEWS.json) records collection, probabilities, permitted headline examples
and aggregation. Board website content is generally public domain unless stated otherwise; no external
full-page content, marks or third-party images were scraped.

Alpha Vantage NEWS_SENTIMENT: real official public AAPL demo yielded **50 headlines dated October
13–14, 2026**. The initial adapter attempt with different query ordering returned an entitlement notice;
the canonical documented URL worked. Explicit public-demo handling and a regression test now preserve
that canonical path and local date filtering. It does not invent historical access. This sample was
actually ingested and scored: 50 global article targets plus 20 resolved company contexts, with model
probabilities and 28-output snapshots. Uncertain company relevance was not copied across all tickers.
Real company pipeline (`M3_ALPHA_REAL_PIPELINE.json`, intentionally omitted; see PUBLICATION_SELECTION.md) records the outcome. Restricted summaries/full text
are not retained or exposed; no private API key was used or stored. Authenticated paging (five pages,
100/page), missing schemas, retries and rate limits use controlled transports and remain subscription-
dependent. [Access probe](M3_ALPHA_NEWS_ACCESS.json) records successful public demo availability.

No provider failure ever triggers fabricated news. API/direct-provider failures create sanitized audit
records; post-insert failure testing proves rollback after an actual SQL insert. RSS malformed items have
rejection diagnostics; unsupported language/empty text and classifier failures remain explicit statuses.

## 5. FinBERT and inference verification

Actual model: `ProsusAI/finbert`, exact model/tokenizer commit
`0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`; Torch 2.14.1, transformers 4.57.6, CPU, two threads,
deterministic/evaluation/inference mode. Full positive/negative/neutral softmax probabilities persist;
score is positive minus negative. Probability and SQL constraints reject malformed distributions.
[Artifact hashes](M3_MODEL_ARTIFACTS.json) include the 437,965,908-byte safetensors weights; weights are
kept outside the source archive. No fallback labels are presented as real inference.

The opt-in actual cached model test **passed**: valid distributions, batch/single consistency within
1e-6, positive/negative financial examples, model metadata and overlength truncation. Default suites
skip this heavyweight check explicitly; the skip is not counted as a pass. Core tests use labeled TEST
DOUBLE metadata and never establish transformer semantic accuracy. API initialization loads local cached
weights explicitly and reuses one instance; it never downloads on reads. Duplicate input hashes/model
signatures reuse probabilities, including within-batch duplicates. Retry appends a new failed/successful
attempt rather than overwriting earlier model evidence. Intermediate batches and errors are audited.

The current pinned model card states noncommercial CC-BY-NC-SA-4.0 weight terms and training-data
restrictions. This is local research verification, not a commercial licensing grant. Probabilities are
**uncalibrated**; no empirical confidence calibration, predictive accuracy, alpha or trading gain is claimed.
A licensed independent gold-label set was not available for such evaluation.

## 6. Feature count and names

**28 sentiment templates**, each with structured parameters, inputs, output names, versions, warmup,
availability, missing policy and dtype. The unified registry lists 66 templates (38 price + 28 sentiment),
while the original price definitions endpoint retains its 38-template contract.

- Levels: `sent_mean`, `sent_weighted_mean`, `sent_positive_probability`, `sent_negative_probability`,
  `sent_neutral_probability`, `sent_positive_fraction`, `sent_negative_fraction`, `sent_neutral_fraction`.
- Dynamics: `sent_momentum`, `sent_change`, `sent_acceleration`, `sent_short_long_difference`, `sent_reversal`.
- Distribution: `sent_dispersion`, `sent_std`, `sent_disagreement`, `sent_strong_fraction`.
- Coverage: `sent_article_count`, `sent_unique_story_count`, `sent_unique_publisher_count`, `sent_news_volume`,
  `sent_abnormal_volume`, `sent_volume_zscore`.
- Surprise/intensity: `sent_surprise`, `sent_zscore`, `sent_abnormal_positive`, `sent_abnormal_negative`,
  `sent_intensity_adjusted`.

Default w=5/m=3; configurable 1/3/5/10/20-session or elapsed-calendar lookbacks. Baseline b=20, minimum
history h=5. Thresholds, sample ddof and formulas are documented precisely. Future-only baseline data,
zero news, missing coverage, true neutral observations, insufficient samples, uncertain relevance and
inference failures cannot silently collapse to the same score. Exact constant-series variance is forced
to mathematical zero: a discovered floating-point residual could otherwise create a false z-score. The
fix has a dedicated independent regression test and increments the subsystem calculation signature to 3.0.2.

## 7. Point-in-time safety

Publication, update, event, provider first-seen, actual observation, ingestion, inference, feature creation,
theoretical readiness and online readiness remain distinct. Observed policy uses actual acquisition;
research_assumed policy requires explicit nonzero delivery delay and is labeled unverified. Source/inference
cutoffs exclude later evidence. Revision selection occurs at each closing boundary, not globally by a future
latest article. A revised version without a distinct update timestamp cannot reuse original publication
availability, even in research mode: it requires its actual observation/ingestion clock. A dedicated
regression verifies that undisclosed corrections preserve earlier historical values. After-hours/weekend alignment follows the same declared calendars as M2; no Friday signal
from weekend text and no same-close fill. Inference/materialization clocks participate in online readiness.

Every one of the 28 sentiment definitions passes prefix invariance with unchanged earlier source, scope,
coverage and definitions. Tests also cover corrected/reverted versions, missing publication, delayed/backfilled
news, company isolation, unsupported/empty text, no-news versus neutral, duplicate volume, complete-coverage
knowledge, calendar versus session windows and missing prior means. Timestamp assertions verify actual data
and model results cannot be used before they exist. No future-return labels enter the matrix.

Observed real-feed snapshots have **zero nonnull prior-session cells**: their actual acquisition was October
14, not at old publication times. Explicit assumed research policy produced descriptive historical inputs
instead. Current-day partial snapshots are not automatically completed closing data; closing readiness and
`unclosed_sessions_at_cutoff` prevent early decisions. Publication time is not delivery proof.

## 8. Database and migration verification

Migration `0005_sentiment` adds stories, articles, versions, associations, inference attempts, runs,
coverage and feature-evidence FKs: **15 application tables** overall. Existing M2 feature-value tables
are reused. Unique source/revision/model/context/attempt relationships and clock/probability constraints
are exercised with actual SQLite writes. Atomic news rollback, append-only versions/attempts, idempotent
inference, cache reuse, stale invalidation and explicit historical inspection pass.

The working M2 DB was backed up before upgrade. At 0005 it retains all **3,220 price revisions and 230
prior feature rows**. SQLite integrity is `ok`, foreign-key violations are zero and `alembic check` reports
no upgrade operations. Fresh schema/model drift and cleanup/downgrade execute in the suite. PostgreSQL
0005 SQL was emitted successfully, which is structural evidence only, not native execution certification.

News/association/inference/coverage/model changes conservatively invalidate linked sentiment datasets.
Source/model/calculation hashes create immutable new snapshots on regeneration. Changed first-seen,
quality/publisher/event/URL metadata is part of revision identity; source content is never retroactively
rewritten. Exact per-cell contributor sets resolve to retained version/inference records. Public manifests
exclude large internal maps and historical cells expose bounded coverage-state information.

## 9. Integration with M2 matrices and APIs

Existing generation/storage/read schemas and canonical columns remain compatible. Sentiment snapshots
reuse real asset IDs, source-linked definitions and existing feature rows. Existing `/api/features/matrix`
accepts an additional immutable sentiment dataset ID. Security-level joins require matching calendars and
selected assets, join exact dates without fills and take the maximum of source-specific readiness clocks.
The older price timestamp cannot backdate a sentiment feature. Matrix ordering/missing/decision policies,
labels exclusion and reproducible two-snapshot identity remain explicit.

Actual loopback HTTP smoke used **real CPU FinBERT and explicitly synthetic price/news inputs**: health,
readiness, original/unified/sentiment definitions, OpenAPI, local model initialization, zero-repeat inference,
feature generation/reuse, price generation, a 20-row mixed matrix, news metadata, article probabilities and
exact contributors all passed. [M3_API_SMOKE.json](M3_API_SMOKE.json) contains computed results. This is
separate from controlled-model TestClient coverage. Read APIs never calculate or download models. Sector,
selected-universe and publisher-specific broad series are supported; no automatic broad-score broadcasting
as company-specific sentiment is performed.

## 10. Exact test and quality-gate results

| Executed check | Result |
|---|---|
| M1/M2 baseline before work | 174 passed + 11 subtests |
| Full default suite, Python 3.12.15 | **242 passed, 1 skipped, 11 subtests passed** |
| Full default suite, Python 3.14.5 | **242 passed, 1 skipped, 11 subtests passed** |
| Preserved original M1/M2 tests | All 174 still pass; original files unchanged |
| New deterministic M3 cases | 68 passing cases, including all 28 per-template prefix comparisons |
| Separately invoked actual FinBERT test, Python 3.12 | **1 passed**; not the default skip |
| Ruff lint / formatting | Passed across the repository |
| Mypy | Passed for 51 application modules |
| Compilation / dependency consistency | Backend/migrations/scripts and pip checks passed in both environments |
| Installed editable package | 0.3.0 in Python 3.12 and 3.14 |
| Live SQLite upgrade/drift/integrity/FKs | Passed; prior evidence preserved |
| Actual provider/model/HTTP matrix verification | Passed, evidence linked above |
| Native PostgreSQL / Docker runtime | Not executed successfully; inherited blockers |
| PostgreSQL 0005 offline SQL / Compose CLI config | Passed structural/configuration checks only |
| Remote CI | Coverage updated, not dispatched/executed here |

There is one existing Starlette/httpx TestClient deprecation warning per default suite. Tests are not
weakened or skipped for that warning. The one explicit default skip is the heavyweight model test, which
was separately executed successfully. Real-provider checks are opt-in scripts; default deterministic tests
make no provider/model network requests. Controlled retries, quotas and injected failures are not proof
of private-subscription behavior. No failing executed final M3 test remains.

## 11. Performance and memory

Python 3.12/macOS ARM64, real resident FinBERT CPU model, batch 16; single recorded runs. Processes were
separate but some verification jobs overlapped, so these are measured local samples, not isolated-machine
latency distributions or production throughput guarantees. Model load is excluded from inference/generation
latency. RSS includes full process lifetime, native model/runtime, ingestion, source loading and output rows.

| Workload | Real Board | Real AAPL demo | Synthetic throughput |
|---|---:|---:|---:|
| Articles | 20 | 50 | 1,000 over 20 securities / 50 sessions |
| Inference pipeline | 0.132 s | 0.250 s | 2.987 s |
| Feature generation | 0.189 s | 0.177 s | 0.955 s |
| Identical feature request | 0.0031 s | 0.0036 s | 0.0464 s |
| Whole-process peak RSS | 844.7 MiB | 854.4 MiB | 942.2 MiB |
| Output rows / columns | 24 / 28 | 2 / 28 | 1,000 / 28 |

Synthetic throughput is approximately 335 unique article texts/second for this short-headline workload;
2,000 article/context targets persist, with context outputs reused where inputs are unchanged. Longer
512-token inputs are not benchmarked as equivalent throughput. [Raw benchmark](M3_SENTIMENT_BENCHMARK.json)
records actual model/counter/configuration evidence; no hand-authored probabilities are used.

M2 allocation profiling on the existing 20-asset/five-year source found **302.3 MiB tracked peak** during
pure calculation, excluding already loaded source ORM and most native allocations. Leading live allocations
were timing lists (~129 MB), timing integers (~67 MB), feature values (~66 MB) and dependency positions
(~24 MB). Full snapshot materialization, not a speculative model cache, dominates that Python profile.
[M3_M2_MEMORY_PROFILE.json](M3_M2_MEMORY_PROFILE.json) records line-level allocations. M2's original whole-
process 50-asset benchmark of ~1.37 GiB remains historical; this tracked figure is not directly comparable.

A further **resident FinBERT + full five-year 50-asset price calculation** used **1,717 MiB peak RSS**, taking
4.326 s for pure price calculation, with feature persistence excluded. [Combined memory](M3_COMBINED_MEMORY.json)
shows that loading the transformer does increase shared-process memory; it is not hidden or claimed free.
M3 avoids duplicating full price matrices and uses bounded batches, immutable intermediate persistence,
shared contributor sets and page-level joins. No major M2 rewrite was justified. Keep lightweight core work
model-free where possible, use one model worker and narrower sets/ranges on constrained machines. Multiple
workers or simultaneous large generation can require more memory; no universal resource guarantee is made.

## 12. Remaining issues and research limits

Public feeds are short, incomplete snapshots. Historical first-seen/coverage, historical universe/sector
membership, calibration/gold-label accuracy and relevance quality have not been independently certified.
Multi-company relation extraction is conservative; ambiguous comparisons are excluded. Analysis is headline-
only for the implemented providers; full-article access/rights is not assumed. Provider language metadata
is trusted rather than certified by a multilingual language detector. Raw price/corporate-action/delisting
limits from M2 remain. Intensity adjustment is a transparent heuristic, not an established predictive factor.

NLP is optional and heavyweight, verified on Python 3.12/macOS CPU rather than all platforms. Local operations
are synchronous with bounded attempts/batches/rows; a model call is not forcibly interrupted mid-batch,
there is no distributed job recovery or remote authentication, and workers multiply memory. The service is
for local research. Recorded timestamps do not establish exact commit visibility. Administrative mutations
outside supported ingestion/inference paths bypass application invalidation. Commercial model/provider
rights need separate review. None of these limitations is disguised as successful alpha validation.

## 13. PostgreSQL/Docker boundaries

Native PostgreSQL 16.2 initialization remains blocked by sandbox `shmget` denial. Docker daemon/image
build/startup remain unavailable. Prior PostgreSQL 18.6/PGlite results remain **23 passed, 3 failed,
2 setup errors** with unresolved rollback/authentication issues; M3 did not reinterpret them as a pass.
PostgreSQL SQL emission and Compose configuration do not certify transaction/concurrency/runtime behavior.
The architecture stays SQLAlchemy/Alembic with SQLite locally and native PostgreSQL deployment intended.
CI now includes sentiment integration on native PostgreSQL16, but that workflow was not executed here.

## 14. Milestone 4 readiness

The software foundation is ready for a separately scoped backtesting milestone: immutable price/news/model
versions, explicit dataset clocks, chronological mixed inputs, missing/coverage policies, exact contributors
and executable leakage tests. Backtesting must consume actual readiness/next-open eligibility, avoid double
shifts, preserve locked datasets, apply corporate actions/costs/cash reconciliation and distinguish research
assumptions from verified historical delivery. Native PostgreSQL/Docker gates and entitled complete market/
news/universe data remain required before broad production claims. No predictive model, portfolio optimizer,
strategy search or backtesting engine was implemented in this milestone.
