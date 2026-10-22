# Financial ML research engine — 6.0.0

This is bounded offline financial research. All forecasts come from fitted numerical models.
No price-prediction neural network, LLM forecast, brokerage connection, strategy discovery,
or Milestone 7 agent is implemented. A trained model is not evidence of alpha.

## Architecture and dependency

`ml/contracts.py` defines closed Pydantic requests; `dataset.py` adapts existing M2/M3 frozen
snapshots and M1 price IDs. `models.py` fits preprocessing and scikit-learn models and exports
numeric inference artifacts. `research.py` owns chronological eligibility, candidate selection,
separate calibration, held-out inference, explanations, ablations and monitoring.
`evaluation.py` computes metrics/calibration/uncertainty. `integration.py` supplies M4 targets
and M5 expected-return estimates. `storage.py` persists manifests, models and forecasts.
Migration 0008 adds three tables; no old migration or test is rewritten.

scikit-learn 1.9.1 is pinned; CPU fits use one native thread and forest `n_jobs=1`. SciPy,
NumPy and existing infrastructure are reused. No MLflow, GPU, broker, distributed service or
untrusted estimator plugin is required. API startup imports sklearn but not FinBERT/torch.

## Targets and clocks

A row has asset UUID/ticker, observation session, decision, next eligible execution,
ordered feature values, missing reasons, source feature clocks, future target window,
label availability and exact source price IDs. Definitions, source/definition hashes,
provider and snapshot IDs are retained in dataset metadata. Dataset snapshots are immutable
at the application layer and frozen into experiments; privileged DB alteration is outside
append-only application guarantees, but replay checks detect changed frozen/result hashes.

The decision is scheduled close + one second. For each input, its required clock must be
no later than that decision; late cells remain missing. Signals are not shifted twice.
`online` takes the existing feature online clock, including source ingestion/materialization.
`research_replay` uses M2/M3 decision readiness, preserving provider availability but ignoring
later computation/ingestion. Neither makes genuinely late market acquisition timely.

`retrospective` explicitly reconstructs **price** feature availability at historical close +
one second and label availability after its final close. Original provider availability is
still in lineage and prices. This mode is reconstruction, not verified PIT or live history.
Observed sentiment clocks are never backdated by this option. Observed, security-scoped,
calendar-compatible M3 sentiment requires complete coverage; partial/unknown coverage becomes
missing. Synthetic news provenance cannot be relabeled as genuine history.

For horizons h in {1,5,10}, let e be the first calendar opening strictly after decision and
f the close of its h-th session. Missing required sessions produce an unavailable target:

- **Return:** simple decimal horizon return `close(f)/open(e)-1`.
- **Direction:** `1(return > 0)`, otherwise 0, including exactly zero.
- **Volatility:** future-only intraday log-return RMS,
  `sqrt(252/h * sum(log(close_i/open_i)^2))`. This includes h future intraday returns,
  omits overnight returns, is annualized, and is RMS rather than demeaned sample SD.
  h=1 is consequently an absolute intraday return scaled by sqrt(252).
- **Close-to-close research:** separate explicit convention using the last observed close
  before decision as return entry and the same future exit. The entry predates the decision;
  the economic adapter refuses it. Volatility retains its documented future intraday formula.

Label readiness takes all required source-bar availability, and ingestion in online mode;
retrospective labels use the explicit modeled close clock. Price revisions other than 1,
flagged prices and sources beyond source cutoff are refused. Current adjusted history is
not substituted. XNYS handles holidays/early closes/DST; `weekday` is a synthetic schedule.
Raw returns omit unprovided distributions/actions and are not total returns.

## Chronological research protocol

Each declared fold has four strictly disjoint date windows: **train → validation → calibration
→ test**. They apply globally to all pooled assets, never random panel rows. Single assets
use the same machinery. Rolling requests declare advancing starts; expanding requests retain
the original start. Test windows cannot overlap and training ends must advance. The supplied
windows define retraining schedules; there is no automatic future-data retraining.

Train labels must finish and become known before validation opening. Validation labels must
finish/become known before calibration opening; calibration labels must finish/become known
before test opening. Unmatured labels and cross-boundary windows are purged even if feature
dates are old. Optional embargo removes the last N sessions of each preceding window as an
additional conservative gap. In forward-only validation no future-side training exists;
this is not a random-fold CV with decorative post-test embargo. Audit counts/cutoffs retain
what was excluded. Test predictions need no realized labels; scoring includes only targets
matured by source cutoff. Every model is frozen before its OOS decisions.

Fit preprocessing and candidates **only on training**. Score all declared candidates on the
validation window. Do not refit on validation. Prefer lower configured complexity when loss
is within the explicit tolerance (default .001) of best validation loss. Tree complexity
uses trees × 2^depth; logistic uses C, with stronger regularization preferred. Other exact
ties retain declared ordering. This is a heuristic, not a statistical significance test.
Selection uses log loss for direction and RMSE otherwise. Preserve every candidate score
and failure. No test, calibration label, economic return or permutation score selects models.

Only after selection, fit optional calibration on the separate calibration window; never
use the test set to calibrate or choose whether calibration looks better. Persist both raw
and calibrated test metrics. The model is effective immediately before test opening, with
separate actual creation/generation timestamps in storage. Historical as-of inference refuses
an effective date after the requested decision. Retrospective models are never live-issued
forecasts merely because their effective research cutoffs are in the past.

## Preprocessing

Reject infinity. Default missing policy drops incomplete rows; comparisons share identical
eligible observations. Explicit `median_indicator` uses training medians and always appends
missing indicators, including sentiment. It does not label missing sentiment neutral or
complete. All-missing rows remain ineligible. Training constant/all-null and exact duplicate
features are removed. Clipping bounds (default 1st/99th percentiles), means and population SD
are fitted only on training. All models receive standardized inputs. Scaling is mathematically
unnecessary for trees but safe and keeps exported inference uniform. Constant SD uses 1.
Optional top-K absolute train correlation selects inputs inside training; this is simple
association selection and can be unstable. No PCA/category encoding is needed because only
numeric registered features are accepted. Sparse matrix/categorical APIs are not supported.

Persist feature ordering, removed/kept columns, medians, clipping/scaling, indicators,
selection and names with the estimator. Inference checks exact order and dimension. It cannot
silently reorder another feature schema, load a later model, or fit a new scaler.

## Models and baselines

Classification: regularized logistic regression, random forest classifier, conventional
scikit-learn gradient boosting classifier. Regression: Ridge, Elastic Net (l1_ratio=.5),
random forest regressor, gradient boosting regressor. Gradient boosting was chosen over
histogram boosting for transparent, independently checked JSON tree export. The RF/boost
bounds are 5–150 trees, depth 1–6, minimum leaf 2–100; seed is explicit.

Classification baselines: hard majority, training prevalence probability, prior daily-return
sign momentum (requires `return`). Regression: zero and train mean. Volatility: train target
mean plus historical daily close-return RMS ×sqrt(252), explicitly a different historical
proxy from future intraday RMS. Negative volatility model outputs are floored at zero and
this is tested against the corresponding clipped sklearn prediction.

All baselines use the same training eligibility and exact same OOS scoring rows as candidates.
Baseline preprocessing uses training only as well. One-class classifiers fail visibly;
constant/prevalence baselines can still function. Entirely constant usable feature sets are
reported insufficient rather than manufacturing informative features.

## Calibration and metrics

Sigmoid calibration fits regularized logistic regression on logit(clipped raw probability),
C=1, at least 40 calibration observations and 10 of each class. Isotonic requires at least
1,000 and 10 of each class. Insufficient calibration retains raw probabilities with an
explicit insufficient status; it does not certify raw calibration. Thresholds are practical
guards, not proofs of statistical adequacy. Curve bins are ten equal-width probability
intervals [i/10,(i+1)/10), after clipping p to [1e-15,1-1e-15]; ECE is count-weighted absolute
mean probability minus frequency. Classifier decision metrics use .5; the separate trading
threshold is predeclared and never tuned on test returns.

Classification: accuracy, balanced accuracy, precision/recall/F1, ROC-AUC, average precision
(PR summary, not trapezoidal PR area), log loss, Brier, confusion matrix, prevalence, reliability
and ECE. Undefined class metrics are null. Regression: MAE/RMSE/R², signed bias, Pearson IC,
Spearman rank IC; constant/near-constant correlations return null. Cross-sectional per-session
rank IC needs at least three assets and variation. Pooled IC is distinct and not independence
of pooled observations.

Per-ticker, month and simple regime slices retain counts. Regimes use decision-available daily
return sign and absolute magnitude versus a training-only median. These are interpretable
one-session proxies, **not** a fitted latent regime or full trailing volatility/trend model.
Sector performance is unavailable without declared trustworthy historical sectors. No sector
history is fabricated. Small cells do not establish regime superiority.

A 300-replicate moving-block bootstrap estimates descriptive mean loss difference versus
prevalence/mean. First average across each date to keep cross-sectional dependence together;
block length=max(10,h) sessions, minimum four blocks, seed recorded. It is conditional on this
model/holdout and omits selection uncertainty/structural breaks. No naïve independent daily
significance, family-wise multiple-search correction or guaranteed alpha claim is supplied.

## Explanations and monitoring

Linear standardized coefficients show direction conditional on correlated inputs; tree
impurity importance has no causal sign. Held-out raw-column permutation measures change in
loss on identical scored rows, after selected preprocessing/calibration. It is a single seeded
row permutation, descriptive only, disrupts temporal dependence and supplies no significance
claim. It never selects features/models. Each fold records model version and sample count;
fold coefficient/importance differences can be inspected without hindsight decisions.

Offline monitoring compares train/OOS standardized feature means, missing rates, prediction
mean/SD, class prevalence and monthly error/calibration. Fold metrics support deterioration
and importance stability comparisons. This does not establish a regime change, trigger an
automatic retrain, or provide a cloud monitor. Individual prediction intervals, SHAP, sparse
models and advanced regime inference are not implemented.

## Economic integration

The trusted `ForecastStrategy` converts direction into predeclared equal long/cash weights
using eligible current-session predictions. Absent assets get zero targets at a decision;
no future signal is exposed and no stale forecast is carried into a new target decision.
No signal decision leaves existing holdings under M4's ordinary no-order semantics. Execution
is strictly next eligible open via the existing M4 simulator, with cash, lots, liquidity,
slippage, commissions and exact Decimal reconciliation. There is no second ledger.

The adapter performs daily long/cash updates. A multi-session label describes predictive
quality, not a separate portfolio of overlapping h-session round trips. Holdings may survive
between updates; forecast accuracy cannot be read as trade profit. Gross uses a separate
zero-fee/zero-slippage simulation with the same liquidity constraints; its path can differ
because available cash differs. It is not a fabricated net-plus-cost scalar.

Persist net, gross, buy-and-hold and monthly equal-weight child M4 ledgers. Each fold starts
fresh cash; folds are not falsely merged into carried positions. Ledger replay checks every
order/fill/equity/action payload. Standalone child replay directs to the parent ML experiment.
This remains a raw daily research execution approximation, including unverified opening
liquidity and incomplete historical actions/universe. No execution certification is implied.

`forecast_estimates` replaces M5 mean estimates with compatible **return** forecasts while
retaining historical covariance. It refuses direction probabilities, wrong horizons/units,
stale observations, missing assets, invalid magnitudes, future fit cutoffs and additional
sentiment adjustment. Simple h-session returns become an explicit arithmetic annual proxy
`252/h * forecast`. This is neither compounding nor a probability-to-return conversion.
Next-open drift versus close-close covariance is explicitly an approximation; scale validity
is tested, reliability of estimated magnitude remains unestablished. Historical/shrinkage/
sentiment M5 estimators remain available. This is a typed internal adapter, not an automatic
live-allocation API or a ranking/strategy search engine.

## Persistence, loading and replay

`ml_experiments`: running/completed/partial/insufficient/failed state, config/source/input/
result/build/dependency hashes and frozen source/result JSON. `ml_models`: experiment FK,
actual creation time, full model payload version digest, numeric artifact hash, schema,
training/validation/test windows via parent, parameters/seed, calibration and effective cutoff.
`ml_predictions`: version FK, ticker, decision, actual generation time, model/feature versions,
execution eligibility, target/horizon/units, quality/origin/status and snapshot references.
Unique(model,ticker,decision) prevents overwrite; new models get new records. No update/delete
forecast endpoint exists. Inference of an already recorded model/decision returns the record.

Model artifacts contain only coefficients, scalars and bounded tree arrays. Loading never
uses pickle/joblib/cloudpickle or imports a supplied class; no artifact-upload endpoint exists.
Tree traversal/count bounds reject cycles/invalid features, output finite/probability checks
apply, and storage checks schema, version/build/dependencies and hashes before inference.
Export accuracy is checked against the real fitted sklearn estimator. JSON integrity hashes
are not cryptographic authorization against a privileged attacker rewriting all database
hashes. Read the official [persistence security guidance](https://scikit-learn.org/stable/model_persistence.html)
and [calibration guidance](https://scikit-learn.org/stable/modules/calibration.html).

Replay reconstructs typed configuration and frozen inputs, refits the actual estimator and
compares the exact numerical result digest. Saved source revisions cannot alter it. It checks
current build and dependency versions; old milestones require their preserved archives.
Same-environment determinism is tested; portable bitwise BLAS/hardware equivalence is not
promised. SQLite and both supported Python versions have executed tests; native PostgreSQL
runtime has not. Build hashes cover application Python, not documentation/verifier edits.

Running experiments are recorded before fitting; training exceptions retain sanitized failure
codes. Dataset/request validation may fail before a run is created. Model/prediction persistence
and final result commits are audited stages, not a distributed atomic transaction. A crash can
leave a running job requiring operator recovery. Economic child runs commit separately and
interruption recovery is not a lease/queue system.

## API and bounds

POST `/api/ml/train` or `/walk-forward` uses the same research request, one or more declared
windows. GET `/models`, `/models/{uuid}`, `/predictions/{ticker}`, `/experiments/{uuid}`,
`/experiments/{uuid}/metrics`, `/feature-importance`. POST `/predict` takes an existing model
UUID, exact decision timestamp and tickers; only retained frozen rows are supported, no
arbitrary feature vectors or live-provider download. POST experiment `/backtest` and `/replay`.
Model metadata endpoints omit artifact arrays and input training matrices. Forecast records
are paginated; model page≤100, forecasts≤500. Results expose research diagnostic summaries.

Limits: 50 assets, 48 features, 10 years, 12 folds, 12 candidates, ≤48 candidate-fold fits,
2 million feature cells, 140k price bars, 64MiB frozen input/result JSON, 300-second maximum
cooperative research budget. One training/replay/backtest API job per process; concurrent jobs
get429. Current native calls and data materialization are not forcibly killed; limits are not
an OS memory/RSS guarantee. Inference covers at most 50 requested assets at one timestamp.
Other subsystem gates are separate; multiple server workers multiply memory.

Example configuration can be copied from an executed export's `manifest.configuration`,
with real existing snapshot UUIDs. Four windows are mandatory even for uncalibrated models;
calibration may be `none` but remains an unused chronological gap. API validation rejects
unknown models/features/parameters, labels masquerading as inputs and incompatible tasks.
Failures use the existing sanitized error envelope; failed or insufficient runs are not fake
successful predictions. The service remains loopback research software without multi-user auth.

## Executable verification

Install `requirements.lock` and the project editable without dependency changes. Commands:

```sh
pytest -q
python scripts/verify_ml.py --assets 5 --source /path/to/retained-M5-5-assets.db \
  --database /tmp/new-ml5.db --output /tmp/ml5.json
# 20/50 use the matching retained M5 universe. Genuine IBM uses --assets 1.
python scripts/profile_ml_stages.py --database /tmp/new-ml5.db --output /tmp/stages.json
python scripts/verify_ml_sentiment.py --output /tmp/ablation.json --export /tmp/frozen.json
python scripts/replay_ml_export.py docs/M6_FROZEN_DEMO.json
```

The sentiment verifier imports the packaged **test fixture** (development requirements needed):
random synthetic statistical variables and market paths, not reconstructed articles or real
FinBERT probabilities. Four fixed ablations share common complete observations. Their purpose
is integration verification; genuine historical news coverage remains insufficient. Every
variant and negative result is retained. See `MILESTONE6_REPORT.md` and machine-readable evidence.
