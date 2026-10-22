# Financial sentiment engineering — Milestone 3

Package 0.3.0, sentiment subsystem 3.0.2. This subsystem ingests versioned financial news,
resolves relevance, runs pinned CPU FinBERT, and produces source-linked quantitative features
using the M2 snapshot and matrix contracts. It does not train a predictive model, optimize a
portfolio, run a backtest or claim sentiment alpha. See [actual verification](MILESTONE3_REPORT.md).

## Architecture

`sentiment/contracts.py` defines immutable news, coverage and probability contracts.
`providers.py` supplies public Federal Reserve RSS and Alpha Vantage news adapters.
`entities.py` resolves provider tags, canonical asset/company names and isolated company sentences.
`ingestion.py` retains versions, links syndicated stories and records atomic pipeline audits.
`model.py` initializes FinBERT explicitly; `inference.py` processes bounded incremental batches.
`registry.py` extends the existing Definition/Resolved/Registry schemas; `aggregation.py` supplies
causal trailing calculations; `datasets.py` persists their results in existing M2 feature tables.
`sentiment/matrices.py` extends the existing matrix assembler with immutable snapshot joins.
Typed news/sentiment endpoints live in `api/sentiment.py`; original M1/M2 endpoints remain.

Heavy libraries import only during explicit model initialization. Normal startup, migrations and
core tests require no transformer, weights, model download, GPU or live provider. No LLM, task
queue, alternate database or remote classifier was introduced. The source archive excludes weights,
provider raw responses, environments and local databases. Model artifact hashes are recorded in
[M3_MODEL_ARTIFACTS.json](M3_MODEL_ARTIFACTS.json).

## Sources, access, retained content and actual coverage

**Federal Reserve Board:** the adapter requests the [official press-release RSS feed](https://www.federalreserve.gov/feeds/feeds.htm)
with a fixed URL. It retains attributed headline metadata only, not linked full pages. Board
website information is generally public domain unless identified otherwise; third-party materials
and marks are excluded from this implementation. See the [Board disclaimer](https://www.federalreserve.gov/disclaimer.htm).
The feed is a source-specific broad-market/regulatory news sample, not complete financial news or
company coverage. Its snapshot yielded 20 actual headlines dated September 10–October 13, 2026,
collected October 14. It is not an archive of 2018–2026 news. Ticker-filtered Fed requests fail clearly;
use an empty ticker filter and broad-market sentiment scope.

**Alpha Vantage:** `NEWS_SENTIMENT` uses the existing `ALPHA_VANTAGE_API_KEY` configuration.
Official public `demo` access was actually verified for AAPL, yielding 50 articles dated October
13–14, 2026. It accepts the exact documented URL with `function`, `tickers`, then `apikey`; adding
historical query parameters or changing canonical ordering failed the public demo during verification.
The adapter handles this explicitly: public AAPL demo returns a current snapshot and applies request
bounds locally. It rejects other public-demo ticker scopes rather than pretending access exists.
No private credential was requested, printed, stored or used during verification.

Authenticated access supports bounded backward time partitions, up to five pages of at most 100
articles. It is implemented and tested with controlled transport, not certified against a private
subscription. There is no API cursor; minute-level boundaries can miss articles in saturated minutes,
so pagination remains partial coverage. No complete historical entitlement is inferred from access.
Quota, personal/noncommercial restrictions and publisher rights depend on the user's agreement;
review [official API documentation](https://www.alphavantage.co/documentation/) and [terms](https://www.alphavantage.co/terms_of_service/).
The adapter retains headlines internally for private research and omits provider summaries/full text;
public API responses omit Alpha Vantage headline text and all article descriptions. Provider-supplied
sentiment scores and relevance scores are not used as FinBERT outputs.

Both adapters use three bounded attempts, 15-second socket timeouts, a 2 MB response cap and
sanitized errors. Numeric/HTTP-date Retry-After is honored; long or unrecognized delays fail closed
for a later explicit retry. Permanent HTTP failures do not retry. XML entities/DTDs are refused.
Requested ingestion is at most one year, 50 tickers and 1,000 articles. There is no provider-failure
fallback to synthetic news. Synthetic fixtures and throughput data are separately labeled.

## News schema, revisions, deduplication and rights

Migration 0005 adds eight tables alongside the existing seven application tables:

| Entity | Purpose and retained evidence |
|---|---|
| `news_stories` | Stable story identity for exact syndication links |
| `news_articles` | Provider/external identity, story FK, original/canonical URL, dedup reason |
| `news_versions` | Immutable article revision, headline/permitted description, publisher, hashes, publication/update/event/first-seen/observation/ingestion clocks, language, scope, synthetic/rights/quality metadata |
| `article_associations` | Version/asset FKs, resolved/unresolved status, heuristic relevance weight/reason, exact company context |
| `sentiment_inferences` | Version/context/model/attempt identity, input hash, model/tokenizer/preprocessing metadata, inference time/status, three probabilities, score, token count/truncation |
| `sentiment_runs` | Ingestion/inference audit, safe configuration, timing, counters, diagnostics and failures |
| `news_coverage` | Requested interval, tickers, provider, knowledge time and complete/snapshot/partial state |
| `sentiment_inputs` | Existing feature-dataset FK to exact version/inference evidence |

Existing M2 `feature_datasets`, `feature_source_assets` and `feature_rows` store sentiment outputs;
there is no second incompatible feature-value schema. Existing real asset IDs are reused. Virtual
`SENT.MKT`, `SENT.UNIV` and sector aggregate symbols identify nontradable research entities. Foreign
keys retain evidence; unique identities and probability/clock constraints reject invalid storage.
Original migrations 0001–0004 are preserved. The new migration supports downgrade of its own tables;
M1's existing precision-loss downgrade safeguards remain.

Exact provider identity and normalized economic/text metadata reuse an unchanged current version.
Corrections and reversions append revisions; they do not overwrite earlier text. Canonical URLs remove
tracking parameters but original URLs are retained. Same canonical URL links stories across feeds.
Exact normalized content within 48 hours also links syndication; the stored reason identifies the match.
Headline hashes are retained, but similar headlines alone never discard distinct follow-up stories.
Cross-feed copies remain auditable article records while features count one unique story. At each decision
boundary aggregation chooses only a visible version and deduplicates only eligible copies.

News quality flags are retained and rejected by default during generation; `allow_flagged` is an explicit override. Changes to first-seen/event/publisher/quality metadata append revisions too.

Descriptions may be retained only with explicit `public_domain_feed`, `licensed_excerpt` or `synthetic`
rights. The production providers deliberately supply no full-page article body. Analysis is headline-only
unless an explicitly permitted description was supplied internally; it must never be called full-article
analysis. Public APIs do not expose descriptions, context text or arbitrary source metadata. Synthetic
and permitted Board headline text can be returned; restricted-source headline text is null.

## Temporal integrity and daily decision convention

An article distinguishes event time (nullable), original publication, update/revision, provider first-seen
(nullable), actual acquisition/observation and ingestion. Source queries require observed and ingested
clocks at/before the explicit cutoff. Inference evidence must also have completed by that cutoff.
Neither a publication timestamp nor an API retrieval request proves instantaneous historical delivery.

For required text version v, let P=publication, U=update or P, F=provider first-seen or P,
O=actual observation, d=configured delivery delay:

- `observed` availability = max(P,U,F,O)+d. This is the conservative default.
- `research_assumed` availability = max(P,U,F)+d, explicitly labeled **assumed**, not verified delivery.
  This mode requires at least 60 seconds of explicit delay; default d=300 seconds. Its convenience
  assumption is not a validated feed latency estimate or historical coverage claim.

Revisions without a distinct update timestamp additionally require their actual observation/ingestion time, even under research assumptions.
Revised contents become eligible only from that revision's availability; a future correction cannot
replace an original version in an earlier session. First-seen/event fields stay null when unavailable.
Delayed/backfilled articles in observed mode enter according to acquisition, not their old publication date.

Aggregates use completed-session boundaries: trading-session lookbacks include releases after the
preceding close and at/before the labeled close. After-hours news enters the next eligible daily session;
weekend news enters Monday/next trading session, never the previous Friday. XNYS calendar alignment
includes holidays, DST and scheduled early closes. Synthetic `weekday` scheduling remains explicitly
modeled. Calendar lookbacks use elapsed days, which differ across weekends; no dates/text are filled.

Feature timing reuses M2 fields. `decision_ready_at` is max(required article/coverage availability,
label's scheduled close + processing delay). `inputs_ingested_at` additionally includes required
inference completion; `online_ready_at` is max(theoretical readiness, pipeline completion and feature
materialization). `earliest_execution_at` is the next session open strictly after online readiness.
This is a **daily closing snapshot** convention, not an intraday news strategy. A weekend release in a
Monday closing snapshot is eligible for the subsequent open; there is no same-close fill or double shift.

A requested current/future daily session can contain a frozen partial snapshot, but it is not usable
before its closing readiness. `unclosed_sessions_at_cutoff` identifies those rows. Snapshot coverage
never means a finished full-day news census. Matrices mask cells before readiness and retain the explicit
online/research availability mode. Research matrix mode ignores later computation/ingestion clocks for
replay, but observed news policy still respects acquisition. Explicit assumed news policy and research
matrix mode together are an experiment assumption, not evidence that those signals existed historically.

Coverage knowledge participates in readiness when a complete interval is asserted. Real providers
return snapshots/partial coverage, **never fabricated completeness**. Recorded timestamps are sampled
before transaction commit, as in M2; they do not prove submillisecond database commit visibility.

## Pinned FinBERT and inference

Model: `ProsusAI/finbert`; model/tokenizer revision
`0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`. Pinned artifact hashes include 437,965,908-byte
safetensors weights. CPU Torch 2.14.1 and transformers 4.57.6 were actually used, with two CPU threads,
seed 0, deterministic algorithms, evaluation/dropout-disabled mode and inference-mode execution.
The token maximum is configurable 8–512 (default 512). Overlength inputs truncate explicitly and log
token counts, never raw article text. Empty/unsupported-language text skips classification with a status.
The English model relies on provider/record language metadata; language detection accuracy is not certified.

Preprocessing `nfkc-whitespace-v1` normalizes Unicode NFKC and collapses whitespace. All class probabilities
are retained from the actual softmax logits: positive, negative, neutral. Each lies in [0,1], sums to one
within 1e-5 and the score is **s=P(positive)−P(negative)** in [-1,1]. Model probabilities are not calibrated
confidence. No licensed independent gold-label corpus was available for calibration or predictive validation;
no accuracy, ECE, Brier or trading improvement is claimed. The opt-in model check verifies distribution,
batch/single consistency, positive/negative example ordering, metadata and long-text truncation only.

The [model card](https://huggingface.co/ProsusAI/finbert) specifies CC-BY-NC-SA-4.0 model-weight terms and
third-party training-data restrictions. This delivery verifies local noncommercial research use and does
not grant commercial model/data rights. Review the pinned card and obtain suitable rights or a separately
validated equivalent before commercial deployment. Code and caches do not redistribute model weights.

Install optional dependencies only when needed:

```sh
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m pip install -r requirements-nlp.lock
# Optional NLP lock was verified on Python 3.12/macOS ARM64, not every platform.
# For Linux, install the matching Torch CPU wheel from the official CPU index first.
```

Explicit one-time acquisition and local initialization:

```python
from sentientalpha.sentiment.model import FinBERT

model = FinBERT("/absolute/path/model-cache", local_only=False)  # explicit download
```

Later API initialization is **local-only** using exported `FINBERT_CACHE_DIR`; read endpoints never load or
download a model. A model instance is reused for batches. Missing weights/dependencies return a clear 503
and never invoke a fake classifier. Batch sizes are 1–32, default 16; up to 1,000 targets per run and a
1–300-second between-batch budget. A CPU call is not forcibly interrupted mid-batch. Work persists in
bounded transactions. Interrupted/error runs retain audits and completed batches.

Caching uses model/runtime/tokenizer/preprocessing/device/token settings and preprocessed input hash;
unchanged inputs reuse all probabilities. Duplicate texts within a batch are evaluated once. A new model
key processes missing targets incrementally. Inference failures retain a failed attempt; explicit subsequent
inference appends another attempt rather than mutating failed evidence. Empty/unsupported text stays a
terminal status until its input version/model changes. No overwrite of historical inference evidence occurs.

## Entity relevance and aggregation composition

The entity layer uses existing canonical asset IDs/names and derived company aliases, provider ticker tags
and `$TICKER` notation. A bare ordinary English ticker such as IT is not a match. Explicit ambiguous aliases
such as Apple/Meta/Block/Target/Gap require provider support or financial context. Alias matching and weights
are transparent heuristics, not empirically calibrated relevance confidence.

A single provider tag uses weight 0.8; a company alias uses 1.0. Multi-company text is split into sentences,
protecting common company abbreviations. A sentence uniquely associated with one company uses weight 0.9
and is classified separately. A comparative/mixed sentence referring to several entities remains unresolved;
its full sentiment is not copied to all companies. Unknown relevance is retained and excluded from level
calculations, with a distinct missing reason. Advanced relation extraction/NER is deferred, not disguised
as a reliable solution to every financial comparison.

Security features use their own eligible associations. Sector scope selects only requested assets whose
current stored sector exactly matches the requested sector. Unknown/empty sector selection fails rather
than guessing from headlines. Universe scope uses the fixed selected cohort; source/entity composition is
recorded. Sector/universe pooling counts unique stories, not repeated ticker mentions. For one story with
multiple resolved company contexts, probabilities are relevance-weighted within that story and every
context contributor ID is retained. Across stories the aggregation is pooled; it is not equal-company
weighting or a survivorship-free index. High-news companies can dominate, which must be assessed later.

Broad-market scope accepts explicitly broad-market source articles, currently Board press-release coverage.
It is a **source-specific news sentiment series**, not a comprehensive market index or an arbitrary mixture
of company headlines. Provider composition, missing intervals, requested entities and current sector/name
mapping are recorded. Historical universe/sector vintages and calibrated relevance quality remain future work.

## The 28 registered quantitative features

All names begin `sent_`; parameters are encoded canonically, including `window` and `min_articles`.
Default window w=5 and minimum scored unique stories m=3; choose windows 1/3/5/10/20 explicitly. The initial
sentiment window/baseline cap is 60; default baseline b=20 and minimum valid historical values h=5.
`long_window` defaults to 20 and must exceed w. h cannot exceed b. All are bounded integer parameters.
Session mode uses trailing w session intervals; calendar mode uses w elapsed days, with a conservative
w-session warmup gate. There is no backward/forward fill of sentiment or coverage.

Let G_t be eligible successful unique-story contexts in the window; n=|G_t|; s_i=p_i+−p_i−;
q_i=heuristic relevance; μ_t=mean(s_i). Labels use argmax of the full probability vector; tie order is
positive, negative, neutral. Baselines use only the previous b window observations, **excluding current**,
and need h valid values. Overlapping windows are intentional; these features are descriptive correlated
inputs, not independent statistical hypothesis tests.

| Name | Equation / meaning |
|---|---|
| `sent_mean` | mean(s_i) |
| `sent_weighted_mean` | Σq_i s_i / Σq_i |
| `sent_positive_probability` | mean(p_i+) |
| `sent_negative_probability` | mean(p_i−) |
| `sent_neutral_probability` | mean(p_i0) |
| `sent_positive_fraction` | Positive argmax-label count / n |
| `sent_negative_fraction` | Negative argmax-label count / n |
| `sent_neutral_fraction` | Neutral argmax-label count / n |
| `sent_momentum` | μ_t−μ_(t−w) |
| `sent_change` | μ_t−μ_(t−1) |
| `sent_acceleration` | μ_t−2μ_(t−1)+μ_(t−2) |
| `sent_short_long_difference` | Current w-window mean minus long-window mean |
| `sent_reversal` | sign(μ_t) if μ_t×μ_(t−1)<0; otherwise 0 when both defined |
| `sent_dispersion` | Sample variance of scores, divisor n−1 |
| `sent_std` | Sample score SD, sqrt(sample variance) |
| `sent_disagreement` | 4×positive fraction×negative fraction |
| `sent_strong_fraction` | Fraction abs(s_i)≥0.5; fixed documented uncalibrated threshold |
| `sent_article_count` | Observed article identities before cross-feed syndication collapse |
| `sent_unique_story_count` | Unique eligible observed stories including inference-failure/uncertain cases |
| `sent_unique_publisher_count` | Distinct observed publishers |
| `sent_news_volume` | Unique-story count over the lookback; duplicates never inflate this volume |
| `sent_abnormal_volume` | Current unique-story count minus prior baseline mean window count |
| `sent_volume_zscore` | (Current count−baseline mean)/baseline sample SD |
| `sent_surprise` | μ_t−mean(valid prior b window means) |
| `sent_zscore` | (μ_t−baseline mean)/baseline sample SD |
| `sent_abnormal_positive` | max(0, sentiment surprise) |
| `sent_abnormal_negative` | min(0, sentiment surprise), retaining negative sign |
| `sent_intensity_adjusted` | μ_t×min(3, log(1+current unique-story count)/log(1+baseline mean count)) |

Levels/fractions/distributions require at least m successful scored stories; SD/variance require at least
2 even when m=1 is explicitly requested. Coverage counts describe observed records and do not require
successful NLP. Momentum needs w extra sessions; change/reversal one extra; acceleration two; baseline
features w+b; short/long uses the maximum window. Missing prior means prevent differences; no-news is
never automatically a mean of zero. Zero baseline SD or zero baseline news volume yields null ratios.
Intensity scaling is a transparent capped heuristic, not a validated predictor.

Missing states are distinct: `no_news_observed` for a known complete empty interval;
`missing_provider_coverage` for an empty unverified interval; `insufficient_history`;
`insufficient_articles`; `insufficient_sentiment_history`; `insufficient_baseline_coverage`;
`inference_failure_or_unsupported_text`; `unresolved_entity_relevance`; and
`zero_baseline_variance_or_volume`. Count=0 is valid only with complete coverage evidence. Real-feed
nonempty counts/means are partial observed statistics and their coverage state stays explicit.
Actual neutral stories can produce zero mean and positive neutral fraction; absent news stays null.

## Storage, versioning, invalidation and mixed matrices

Generation is bounded to 50 selected assets, one year of output dates, 5,000 source versions, at most
1,000,000 output cells and the existing 128-column limit. CPU inference and feature generation are explicit
operations; a per-application semaphore permits one sentiment operation at a time (429 otherwise).
This is a local research API, not a multi-worker coordinated production queue. Several workers multiply
model memory. Requests are bounded but not forcibly canceled mid-model/batch/database call.

Snapshots fingerprint versions, associations, inference attempts/probabilities/clocks, coverage and fixed
asset/sector metadata. Configuration includes scope, model key, source policy, delays, windows and cutoff.
Matching effective inputs reuse the snapshot and its initial cutoff. Changed article/inference/complete
coverage evidence conservatively marks linked sentiment snapshots stale. Calculation/library/subsystem
version changes invalidate compatibility on read; unchanged prices and M2 definitions retain their names.
New generation creates another immutable snapshot. Sorted/shared sentiment writer locks and a final
source check coordinate commits with ingestion/inference. Per-cell contributor sets are interned to avoid
repeating large ID lists. Source linkage and all old evidence remain available.

Registered metadata uses the same M2 schema, with sentiment inputs, calculation version, warmup, availability,
missing policy and non-price basis. Historical cells additionally expose their `coverage_state`. `/api/features/definitions` retains its original 38-definition contract;
`/api/features/all-definitions` lists all 66 templates, and `/api/sentiment/definitions` lists 28.
M2 read endpoints can retrieve sentiment-only snapshots directly. Large internal coverage/contributor maps
are excluded from public dataset manifests; bounded contributor queries expose exact model evidence.

Existing `/api/features/matrix` accepts optional `sentiment_dataset_id` alongside its price `dataset_id`.
The assembler requires matching calendars and security-level sentiment, joins by actual asset/ticker/session,
keeps canonical column ordering and never fills an absent sentiment row. Per-cell clocks remain attached to
its original snapshot; combined row readiness is their maximum, not the older price timestamp. No targets
or labels can enter. Two immutable dataset IDs identify the reproducible mixed matrix. Sector/broad indices
are retrievable separately; there is no automatic broadcast of them as company-specific signals.

## API examples

From an installed repository with migrated DB and running loopback application:

```sh
# Real public Board feed; no ticker-filter assumption.
curl -X POST http://127.0.0.1:8000/api/news/ingest -H 'Content-Type: application/json' \
  -d '{"provider":"federal_reserve","start":"2026-09-01T00:00:00Z","end":"2026-10-14T00:00:00Z","tickers":[],"max_articles":100}'

# First export FINBERT_CACHE_DIR with already acquired pinned files; no API download occurs.
curl -X POST http://127.0.0.1:8000/api/sentiment/model/initialize -H 'Content-Type: application/json' -d '{}'
curl -X POST http://127.0.0.1:8000/api/sentiment/infer -H 'Content-Type: application/json' \
  -d '{"provider":"federal_reserve","max_items":100,"batch_size":16,"seconds":120}'

# Use the returned MODEL_KEY. SPY is a requested reference; broad output is a nontradable SENT.MKT entity.
curl -X POST http://127.0.0.1:8000/api/sentiment/generate -H 'Content-Type: application/json' \
  -d '{"tickers":["SPY"],"news_provider":"federal_reserve","model_key":"MODEL_KEY","start":"2026-09-10","end":"2026-10-13","scope":"broad_market","calendar":"XNYS","availability_policy":"observed","features":[{"name":"sent_mean","parameters":{"window":5}},{"name":"sent_news_volume","parameters":{"window":5}}]}'
```

Substitute actual UUIDs/model keys from responses, not the placeholders. Dates must fit actual source
coverage; rerunning a current feed later may yield different/empty data. An observed historical backfill
will correctly have no past eligible cells. Use explicit research assumptions only when justified/labeled.

| Method | Route | Use |
|---|---|---|
| POST | `/api/news/ingest` | Bounded explicit acquisition and audit |
| GET | `/api/news/{ticker}` | Source/version metadata, cutoff and bounded pagination; SENT.MKT for broad news |
| GET | `/api/sentiment/runs/{uuid}` | Audits, counters and sanitized errors |
| POST | `/api/sentiment/model/initialize` | Explicit reusable local-only CPU model |
| POST | `/api/sentiment/infer` | Incremental bounded scoring/retry |
| GET | `/api/sentiment/articles/{version_uuid}` | Full probabilities/status/model metadata for article/context attempts |
| GET | `/api/sentiment/definitions` | 28 structured definitions |
| GET | `/api/features/all-definitions` | Unified price/sentiment catalog |
| POST | `/api/sentiment/generate` | Security/sector/universe/broad snapshot generation |
| GET | `/api/features/{ticker}` | Existing typed historical sentiment analytics by dataset ID |
| GET | `/api/feature-datasets/{uuid}` | Reproducibility manifest and stale status |
| GET | `/api/sentiment/{uuid}/contributors` | Exact contributing inference IDs/probabilities; resolve article version via news metadata |
| POST | `/api/features/matrix` | Existing matrix schema plus optional sentiment snapshot ID |

Contributor query takes `ticker`, ISO `session_date`, canonical `feature`; max 500 contributors per cell.
News retrieval max 500 records, inference retrieval max 500, matrix limits remain 2,000 rows/100,000 cells.
Missing weights =503, stale snapshots =409, invalid requests =422, busy operation =429. Errors retain the
existing sanitized envelope and never echo credentials/full text. News history lists retained versions,
not a silently overwritten “current” article. Original URL and version IDs connect public permissible
headlines with exact contributor evidence; restricted headlines remain internal.

## Executed tests, performance and remaining gates

See [MILESTONE3_REPORT.md](MILESTONE3_REPORT.md), [real Board pipeline](M3_REAL_NEWS.json),
real public AAPL pipeline (`M3_ALPHA_REAL_PIPELINE.json`, intentionally omitted; see PUBLICATION_SELECTION.md), [synthetic real-model benchmark](M3_SENTIMENT_BENCHMARK.json),
[actual mixed HTTP matrix](M3_API_SMOKE.json) and [M2 allocation profile](M3_M2_MEMORY_PROFILE.json).

Core deterministic tests run offline on Python 3.12/3.14 with explicitly labeled controlled model outputs.
A separate local-weight opt-in test actually runs FinBERT; skipped model tests are not passed tests:

```sh
pytest -q
RUN_FINBERT=1 FINBERT_CACHE_DIR=/absolute/path/model-cache HF_HUB_OFFLINE=1 \
  pytest -q backend/tests/test_finbert_optional.py
python scripts/verify_sentiment_pipeline.py --model-cache /absolute/path/model-cache \
  --database /tmp/empty-real-news.db --output /tmp/real-news.json
# Add --alpha-demo for the public company sample or --synthetic for the 1000-article workload.
```

The verifier refuses existing database tables, uses real CPU model outputs in every mode and clearly labels
synthetic headlines. No arbitrary expected sentiment labels enter production. Baseline M2 profiling found
per-cell timing lists/integers and full wide snapshot values dominate tracked Python memory; a major M2
rewrite was not justified. M3 reuses one model, bounded text batches, persisted intermediate attempts,
shared contribution sets and paginated matrix joins. Its full-process RSS remains substantial because
FinBERT weights/runtime are not free; keep one model worker and reduce tokens/batches on small machines.

Native PostgreSQL/Docker execution remain blocked as previously documented; PostgreSQL 0005 SQL emission
is only structural evidence. Prior WASM failures remain unresolved. Current provider samples cannot
establish broad historic news completeness, prediction accuracy, calibrated confidence or strategy alpha.
Historical company/sector membership, advanced relevance quality, full-article rights, distributed job
recovery/cancellation, commercial licensing and later corporate-action/backtesting gates remain open.
Milestone 4 has not started.
