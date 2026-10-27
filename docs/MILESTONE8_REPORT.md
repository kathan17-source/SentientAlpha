> Dated research record. Original findings and numerical values are preserved. For current test/CI status see [verification](VERIFICATION.md); supporting exports are [retained locally](EVIDENCE.md).

# SentientAlpha — Milestone 8 completion report

**COMPLETE for local simulation-only engineering integration**, version0.8.0, schema0010_investment_committee.
This replaces the earlier incomplete foundation report. Native PostgreSQL/Docker/remote CI verification remains blocked or unexecuted. No genuine all-agent PIT deployment or investment alpha is claimed. Milestone9 has not started.

## 1. Summary and component status

| Component | Status | Evidence / limit |
|---|---|---|
| Quant Agent | VERIFIED | Original M6 forecast/model/feature/calibration integrity and timing checks; genuine IBM participation |
| Strategy Agent | VERIFIED | Original M7 canonical version, validation lock and stateful rule; no implicit search |
| SQLite durable persistence and typed API | VERIFIED | Migration preservation, idempotency, restart retrieval, real HTTP and rollback tests |
| M5 allocation / independent risk / M4 ledger | VERIFIED | Actual constrained solves, veto-to-no-orders tests, next-open fills and reconciled ledger |
| Frozen historical replay | VERIFIED | All saved configurations, artifact checks and cross-Python replay |
| Genuine ablation execution | VERIFIED | All feasible fixed configurations and matched baselines executed |
| Comparative full-committee outperformance | FAILED | Full committee -8.6995%; buy-hold -4.6899% |
| Statistical alpha | PARTIALLY VERIFIED | Negative descriptive evidence only; no significance or fresh holdout |
| Genuine fundamental/macro/sentiment coverage | BLOCKED | No adequate eligible histories in retained sources; honest abstentions |
| 1/5/20/50 workloads | VERIFIED | Actual timings/RSS below; analysis workloads, not live SLA |
| Native PostgreSQL / Docker | BLOCKED | Shared-memory permission denial / absent Docker daemon |
| Remote GitHub Actions | PARTIALLY VERIFIED | Existing workflow extended; **UPDATED BUT UNVERIFIED**, no Git remote |

## 2. Architecture

Continues the existing foundation. `sources` reuses M7's audited M2/M3/M6 resolver; `adapters` verifies original forecasts and locked candidates; `engine` implements trusted targets for M4. M5 estimation/solve/residuals and M4 accounting remain authoritative. No duplicate feature, optimizer, ML, search or ledger engine.

## 3. Files added and modified

New `committee/requests.py`, `sources.py`, `adapters.py`, `engine.py`, `storage.py`; `api/committee.py`; `database/committee_models.py`; migration0010; integration tests; verification/replay scripts. Existing foundation contracts/aggregation/risk are extended. M4 persist gains an optional shared transaction, with default behavior preserved, plus a parent replay guard. API/schema/version/CI and documentation are updated. CHANGESET_M8.json (historical evidence archived locally) lists exact files. All previous test files (covering499 cases) and migrations0001–0009 remain byte-identical.

## 4. Agents

Six analyst identities, plus actual aggregation, portfolio projection and independent risk roles. Technical uses existing return or price/SMA; sentiment requires eligible cached complete coverage; Quant uses original forecasts; Strategy uses original locked rules. Fundamental and Macro have PIT release/vintage interfaces and abstain without genuine configured sources. No analyst dialogue or LLM role-play.

## 5. Maturity

Local engine/service/SQLite/API/replay integration is VERIFIED. Native deployment, future performance, all-agent genuine coverage and contemporaneous historical deployment are not verified. Passing tests is engineering evidence, not proof of economic usefulness.

## 6. Real versus fixture coverage

Genuine IBM:100 acquired raw daily bars, May21–October13,2026, previously retained in M6/M7. Evaluation uses September9–October12,2026 and 23 eligible decision callbacks. Acquisition, model generation and strategy research occurred after the historical period: explicitly retrospective. Synthetic prices power integration tests and infrastructure benchmarks; release/vintage fixtures are independently labeled synthetic. Real cached FinBERT inference passes separately, without claiming genuine news alpha.

## 7. Shared schema and persistence

Recommendations retain unique analyst/version/ticker clocks, status, null-vs-neutral semantics, source versions/dependencies, diagnostics, coverage, signal strength, horizon/units and limitations. Confidence and expected return remain null-only. Two new relational tables store immutable idempotent parents and ordered decisions, with foreign-key M4 child links. Selected derived cells and numeric model/selection evidence are frozen; raw prices are ID/hash references. Complete market/news datasets and M4 ledgers are not duplicated.

A running parent precedes computation. Decisions and child ledger/artifacts share one transaction. Injecting failure after M4 ledger flush rolls both back and leaves a failed audit. Same-key same-config calls return original runs; changed config returns409. No silent history overwrite. Read APIs survive an application restart and use the saved database.

## 8. Fundamental Agent

PIT statement interface distinguishes fiscal period, release, ingestion, availability, original/amendment/restatement and revision lineage. Fixture tests prove late filings and amendments cannot rewrite earlier knowledge. No statement source or fundamentals inferred from prices. Genuine fundamental agent validation remains BLOCKED by coverage, not by an unimplemented execution integration.

## 9. Technical Agent

Existing M2 calculations only. The genuine run validates the original compatible100-row M2 generation/cache path and resolves existing cells; no second indicator implementation. Fixed scale/neutral region precede evaluation. Online mode requires actual readiness; retrospective price-derived clocks are explicit. Technical-only returns -11.0327% here.

## 10. Sentiment Agent

Existing cached M3 security means, complete observed coverage and original clocks only. No implicit downloads/inference and no probability-to-return mapping. Genuine compatible historical sentiment is absent, so participation is0. Injection text remains passive data. Separate real FinBERT: 1 passed in 3.23s; this is inference verification, not a news-return finding.

## 11. Macro Agent

Release/vintage interfaces reject latest-revision leakage and issuer valuation claims from macro series. No acquired genuine vintage panel exists, so Macro abstains. Synthetic vintage fixtures test revision eligibility. No future-fit regime or fabricated macro history.

## 12. Quant Agent

Actual original M6 model/forecast registry, safe numeric artifact hash, full version, parent input/result hash, original OOS membership, feature-set hash, horizon/type/units, model/forecast training cutoff agreement, effective time and calibration are checked. Online mode also requires actual creation/generation by the decision. Incompatible/nonfinite/future models are refused or abstain. Supporting predictions, calibration, training count and prior matured OOS accuracy/Brier versus training prevalence are recorded; future outcomes never enter those diagnostics or weights.

Genuine choice is predeclared logistic, the simplest nonbaseline family, not chosen by M8 test returns. It participates in 23 callbacks. M6's prior failure to beat prevalence remains unchanged. Forecast voting is opt-in experimental, prior capped0.1, with quant-only exposure capped10%. No calibrated confidence, automatic skill promotion or probability-to-expected-return conversion. Quant-only return: -0.6522%, at different intentionally conservative exposure.

## 13. Strategy Agent

Explicit existing candidate ID, canonical rule identity, locked validation selection, historical validation boundary, status/complexity/turnover and validation fragility. Current signals use M7's stateful RuleStrategy and actual M4 holdings. No search or holdout-based selection is run by ordinary analysis. Later holdout robustness is not used to choose historical rules. Original selection freeze and modeled retrospective eligibility remain distinct. Genuine participation: 23 callbacks; the original approximately−2.90% M7 evaluation is still a losing exploratory result. M8 sizing/dates differ, so strategy-only -3.9657% is not a replacement for the M7 experiment.

## 14. Portfolio Manager

Fixed dependency-aware active set → actual past M2 return-panel mean/covariance → M5 equal-weight constrained projection. Every configured constraint and execution position cap applies. No invented expected returns. M5 results are embedded and referenced by their decision allocation/proposal; source dates and diagnostics are retained. Approved targets, actual quantities/weights/cash before the decision and M4 realized ledger remain separate.

## 15. Investment Committee and API

Actual typed GET agent/list/performance and POST analysis/backtest; run listing/retrieval, paginated decisions/recommendations/evidence/allocation/risk/execution; POST replay. Real services/SQL, not hardcoded portfolios. Full paths/schemas in [MULTI_AGENT_SYSTEM.md](MULTI_AGENT_SYSTEM.md) and [openapi.json](openapi.json). Actual uvicorn loopback HTTP verifies saved genuine decisions, POST analysis, idempotency/conflict409 and malformed-input422 validation and replay; server terminated after smoke.

Workloads: ≤50 assets, six analysts, one explicit model/strategy, ten-year history/one-year evaluation, bounded pages/cells/source bytes and cooperative runtime; local semaphore. No acquisition, fitting or strategy search from reads or analysis.

## 16. Disagreement and dependency handling

Connected dependency groups cap shared market-price evidence; agreement is not independent confidence. Conflicting signs withhold additions. Default requires two families; the sparse genuine/demo configuration explicitly predeclares one to exercise the workflow, without asserting independence. No fitted correlation/causal independence claim. Full genuine run records 7 disagreeing decisions and 69 individual abstentions.

## 17. Past performance and weighting

Foundation matured-outcome evaluator preserves OOS/maturity/version/horizon filtering. Quant diagnostics use original source-authenticated target-availability clocks, with baseline comparisons only from prior matured forecasts. No future outcome changes weights. Fixed priors are preferences, not learned skill. Agent performance API exposes real recommendations and truthfully withholds unverified standalone agent P&L attribution. Adaptive/regime weights, statistical significance, calibrated confidence and fitted agent correlation remain withheld for insufficient evidence.

## 18. Non-overridable risk review

Independent M5 residual recheck retains original proposal/slacks/violations. Rejects invalid weights/universe/covariance, future or >7-day-old risk inputs, live mode, and existing bound/concentration/cash/group/sector/volatility/variance/turnover/tracking-error violations. Veto means no approved target and no M4 orders for that decision. Prior holdings remain real holdings; rejection does not fabricate liquidation. Final actions record approve/maintain/reduce/more_cash/reject/abstain. Full genuine risk veto count: 0 (zero is an observed result, not a missing veto interface).

## 19. Point-in-time integrity

Online is actual readiness/issuance; research replay is historical reconstruction; retrospective explicitly models price-derived readiness, never future news eligibility. Model training and validation must precede decisions in every mode. Source physical creation and selection-freeze clocks are retained. Backdating a policy's declared effective time is not proof of historical commitment. The IBM exercise cannot establish genuine contemporaneous PIT availability and is labeled accordingly.

## 20. Authoritative M4/M5 integration

Every proposed allocation comes from M5; every trade/equity result from M4. Next allowed open and exchange sessions, cash, participation, costs/slippage, IOC/partial fills, raw daily limitations and M4 corporate-action scope are preserved. No invented fills or alternate ledger. Veto-to-zero-orders tests exercise both injected vetoes and an actually invalid M5 proposal through the real risk check. All ledger reconciliation residuals stay inside existing M4 tolerance1e−8.

## 21. Genuine results

| Configuration | Return | Sharpe | Max drawdown | Volatility | Turnover | Fees / slippage | Fills |
|---|---:|---:|---:|---:|---:|---:|---:|
| technical | -11.0327% | -6.4840 | 11.4337% | 18.6242% | 6.5675 | $14.00 / $605.96 | 14 |
| quant | -0.6522% | -3.3779 | 0.9663% | 2.0278% | 0.4443 | $12.00 / $44.16 | 12 |
| strategy | -3.9657% | -3.1020 | 4.7757% | 13.4039% | 3.0119 | $6.00 / $291.35 | 6 |
| technical_quant | -8.6995% | -6.3210 | 9.1120% | 14.9190% | 5.5416 | $12.00 / $520.79 | 12 |
| technical_strategy | -8.6995% | -6.3210 | 9.1120% | 14.9190% | 5.5416 | $12.00 / $520.79 | 12 |
| full | -8.6995% | -6.3210 | 9.1120% | 14.9190% | 5.5416 | $12.00 / $520.79 | 12 |
| m5_equal_weight_baseline | -4.7207% | -1.5289 | 11.6889% | 30.2948% | 0.5172 | $2.00 / $49.90 | 2 |
| buy_hold | -4.6899% | -1.5282 | 11.6095% | 30.1209% | 0.5170 | $2.00 / $49.88 | see M4 ledger |
| equal_weight | -4.7207% | -1.5289 | 11.6889% | 30.2948% | 0.5172 | $2.00 / $49.90 | see M4 ledger |


These are observed small-sample research results. Annualized returns, exposure and full metrics are retained in VERIFICATION_M8.json; annualization and Sharpe from this short sample are unstable. Every configuration lost money. Quant-only lower losses occur under its explicit10% exposure cap and cannot establish superior forecasting skill. Full committee underperforms buy-hold and cash. No significance, reliable agent P&L attribution or investment recommendation.

## 22. Ablation design

Technical, Quant, Strategy, Technical+Quant, Technical+Strategy, full eligible set, M5 equal-weight projection, buy-hold and M4 equal-weight. Same IBM dates, capital, provider/calendar, fixed cost/slippage contract and hard constraints. Configuration set and priors frozen before execution; no ranking or winner selected from new outcomes. Quant experimental sizing differs by declared policy and is disclosed. Fundamental/Macro/Sentiment abstain, rather than fabricate coverage. This previously inspected holdout is an integration comparison, **comparative alpha UNVERIFIED**.

## 23. Tests and quality gates

- Python3.12: **513 passed, 1 skipped, 1 warning, 11 subtests passed in 54.11s**.
- Python3.14: **513 passed, 1 skipped, 1 warning, 11 subtests passed in 55.92s**.
- Prior499 tests and11 subtests preserved;14 new integration/adversarial cases.
- Separate actual FinBERT: **1 passed in 3.23s**.
- Ruff lint/format, compileall, dependency checks pass; mypy108 application modules passes.
- One normal skip is the opt-in FinBERT test (run separately); one upstream Starlette/httpx deprecation warning.

Adversarial coverage spans contradictory and overlapping momentum votes; future features/articles/filings/vintages/models/selections; missing/mostly abstaining agents; NaN; unjustified confidence; tiny samples and future outcomes; concentration and veto override; same-close execution; incompatible horizons/units; duplicate recommendations/orders; malicious text; stale/missing persisted evidence; future price changes outside the frozen range; actual future retraining; changed risk configs; rollback and immutable child replay routing. See the new integration tests plus preserved foundation/M4–M7 suites. No previous test was weakened or removed.

## 24. Performance and memory

| Assets | Source retrieval | Agents | Aggregation | M5 solve | Risk check | DB persistence | End-to-end | Replay | Peak RSS |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.0202s | 0.0001s | 0.0001s | 0.0014s | 0.000053s | 0.0048s | 0.0795s | 0.0335s | 236.0 MiB |
| 5 | 0.1089s | 0.0002s | 0.0002s | 0.0015s | 0.000060s | 0.0132s | 0.2344s | 0.1187s | 250.7 MiB |
| 20 | 0.5109s | 0.0005s | 0.0007s | 0.0027s | 0.000106s | 0.0414s | 0.9038s | 0.5666s | 328.7 MiB |
| 50 | 1.4156s | 0.0012s | 0.0018s | 0.0087s | 0.000275s | 0.1111s | 2.4114s | 1.6404s | 548.8 MiB |


Each synthetic workload is one historical multi-asset analysis over retained genuine-engine synthetic M2 data, plus persisted retrieval/API and replay. Price/feature preparation/cache validation and copied-database migration are separately measured; peak process RSS includes those operations and imported dependencies. Source retrieval excludes fitting/inference: existing forecasts are retrieved, no transformer loads. End-to-end includes serialization/hash/parent work and commits. Persistence covers initial parent commit plus primary decision/ledger transaction; supplementary timing-metadata commit is included in end-to-end. Timings overlap by stage and must not be summed as disjoint totals. Other verification ran on the host; these are measured examples, not isolated SLA claims. No unavailable workload or memory value was invented.

## 25. Replay and reproducibility

All seven genuine committee/M5 configurations and four synthetic workloads pass regenerated decision and M4 ledger/metric comparisons. Python3.14 additionally replays the Python3.12 genuine audit. Exact IDs/Decimal strings and nonnumeric content; float relative/absolute tolerance1e−9. Solver elapsed time excluded. Builds/config/source/result/decision/ledger/dependency changes are rejected; direct M4 child replay requires the committee parent. New external versions and out-of-range future prices cannot rewrite frozen decisions. Missing referenced raw prices prevents full replay and is reported as an error, not silently reacquired.

Scope: replay of frozen derived inputs, original numeric forecasts and locked strategy evidence, not a new raw-news ingestion/FinBERT inference/ML fit/search. Original upstream experiments require their original source archives. No historical build guard was relaxed. Detailed run IDs/database paths, replay flags and current build f48645cfc0cebfb8bf93be6ff8fd46faa095f6a82344a612f274466548fca98b are in VERIFICATION_M8.json. Source archives exclude large databases and weights.

## 26. PostgreSQL, Docker and CI

SQLite migration/model check passes. Copying the retained M7 database and upgrading preserves all24 previous application tables and every row/content hash, including31 M4 runs,120 forecasts and120 strategy candidates. Adds only committee_runs/committee_decisions. Original source database remains unchanged; prior migrations remain byte-identical.

Native initdb actually attempted: shared-memory shmget denied (Operation not permitted). Docker Compose version/config pass; runtime cannot connect to the absent daemon. PostgreSQL migration0010 offline DDL generation passes, **not native transaction verification**. Existing GitHub Actions PostgreSQL16 workflow now includes committee tests but is **UPDATED BUT UNVERIFIED**: no Git checkout/remote exists here. Next: provide native PostgreSQL or start Docker, run migration/check and full integration suite against a disposable empty PostgreSQL database, then push/dispatch existing CI. Prior environment failures are not relabeled successes.

## 27. Security and hygiene

No brokers, real-money orders, credentials, arbitrary code, eval, pickle execution, implicit training/search/download or generative analyst prompts. ORM-bound queries; unknown inputs rejected; local gate/pages/workloads bounded. Malicious article text is passive data; source/model/strategy integrity is checked. No private .env, database, cache or weights enters the source package. Historical audits/archives remain preserved. Administrative SQL writes can break provenance and are not an authenticated external trust source.

## 28. Limits and findings

Engineering integration is complete locally. Genuine coverage is one small, already-inspected, retrospectively acquired stock sample; no true all-agent PIT deployment, new holdout, benchmark SPY coverage, genuine statements/vintages or compatible news history. Correlation estimates/adaptive weights/confidence remain withheld; fixed conservative policies are explicit. M4 raw daily/open/volume/corporate-action limitations persist. Native PostgreSQL/Docker/remote CI remain blocked/unverified. Negative M6 and M7 results remain unchanged; all M8 configurations lose money. This is not investment advice or a production execution certification.

## 29. Milestone 9 readiness

M8 supplies durable, replayed, source-linked targets and non-overridable basic risk boundaries for later work. Ready for a separately authorized M9 engineering scope, subject to deployment blockers and independent research validation. **Milestone9 has not started.** No advanced risk/stress engine was added.
