# Evidence-based investment committee

Milestone 8 engineering is implemented locally in version **0.8.0**, schema **0010_investment_committee**. This is simulation-only research. Native PostgreSQL, Docker runtime and remote CI remain unverified or blocked. Engineering completion does not establish investment alpha or contemporaneous historical deployment.

## Services and authoritative engines

`committee.requests` bounds configuration; `sources` resolves existing M2/M3 data, original M6 forecasts and a caller-selected M7 registry version; `adapters` verifies forecast/selection eligibility; `engine` runs the analyst/committee/portfolio loop; `risk` uses the existing M5 solver and independently rechecks its output; `storage` persists ordered decisions and links the existing M4 ledger. The foundation contracts, vintages, feature resolver and past-outcome evaluator remain available.

The flow is source evidence → typed analyst recommendations → dependency-aware committee → M5 constrained allocation → independent risk veto → M4 target orders, fills and ledger. There is no second execution engine, optimizer, feature implementation, model trainer or strategy search in ordinary analysis. M7's stateful `RuleStrategy` evaluates its existing rule, including holding periods, exits and schedule; actual M4 holdings determine held state.

## Analyst contracts and coverage

Every recommendation carries an agent/version, ticker, exact decision/data cutoff, distinct status, bounded signal and strength, coverage, source/version references, dependencies, limitations, reasoning and optional forecast with horizon and units. Strength is heuristic magnitude, not confidence. Missing evidence is null and abstaining. Confidence and expected return remain null-only; no empirical mapping justifies broader support here.

| Analyst | Implemented evidence and eligibility |
|---|---|
| Technical | Existing M2 simple daily return or price-to-SMA deviation. Declared clip(value/scale,-1,1) transform and neutral region; source cell must be ready at decision. No indicator recalculation. |
| Sentiment | Existing M3 security-scoped cached mean with complete eligible coverage and retained news clocks. No implicit inference or transformer download. Missing coverage abstains. |
| Quant | Original M6 predictions with parent result/input integrity, full model/artifact hashes and original OOS membership. Verify effective/training cutoff, model/forecast cutoff agreement, horizon, type, feature-set hash, units, calibration, creation and generation clocks. Probability is a forecast, never expected return. |
| Strategy | Explicit existing candidate ID. Verify parent input/prepared hashes, canonical rule identity, immutable selection lock, selected/eligible status, prior validation cutoff, complexity and turnover. Inspect validation fragility; later holdout metrics never select the rule. No automatic latest/best lookup or search. |
| Fundamental | Release/filing/revision interfaces with original/amendment/restatement clocks. Abstains in current services because no genuine statement feed is configured. |
| Macro | Vintage/release/revision interfaces with broad-series semantics. Abstains in current services because no genuine vintage feed is configured. |

The original M6/M7 source build is retained as evidence; importing an old, internally consistent forecast does not require rerunning its training using current source. Replay of that original experiment itself still requires its original build. Numeric artifacts are not unpickled or evaluated as executable code.

Quant diagnostics report training count, calibration, physically generated/model-created times, and only prior matured OOS accuracy/Brier against a training-prevalence baseline. Outcome maturity comes from the original M6 frozen label lineage. Future/current-unmatured outcomes are excluded. Small samples are insufficient; larger samples remain descriptive, without significance or learned weights. Cross-asset/overlapping outcomes are not independent. Volatility forecasts abstain from directional voting.

## Information policies

- **online** requires M2/M3 online readiness and actual model creation/forecast generation by the decision. Later-materialized research forecasts cannot be relabeled live.
- **research_replay** uses the existing observed-availability feature contract and historical walk-forward model effective dates. It is research reconstruction, not evidence that the system was deployed then.
- **retrospective** explicitly uses M7's existing daily raw-price research clock adapter and modeled price-derived feature readiness. News clocks are never backdated. Original forecast creation and selection-freeze times remain in the source manifest; model training and validation boundaries must still precede each decision. No genuine PIT or live issuance claim follows from this mode.

For the IBM experiment, prices were acquired after the evaluation period and models/strategy searches were physically produced later. Results are genuine market observations in a **retrospective, previously inspected** research exercise. The stored M7 selection lock was frozen before its research test execution; modeling its historical validation eligibility is not contemporaneous selection attestation.

Policies are configured and snapshotted before each evaluation. A supplied historical `effective_at` is a declared research assumption, not independent proof of historical commitment. No configuration is chosen using the newly evaluated holdout results.

## Dependencies, aggregation and experimental influence

The default fixed nonnegative normalized priors are preferences, not learned skill. Shared dependencies form connected components; each component is capped at its largest constituent prior. Technical, price-derived ML and strategies conservatively share `market_prices:TICKER`. News has a separate dependency family. This avoids treating three momentum-derived votes as three independent confirmations. It is declared grouping, not a fitted correlation matrix.

Default policy requires two evidence families. The demonstration predeclares one family to exercise otherwise sparse single-stock coverage; this does not assert independence. Conflicting eligible signs withhold additions. Forecasts do not vote by default. Explicit `experimental_quant` permits a directional forecast vote capped at 0.1 prior weight. Quant-only proposals additionally cap invested exposure at 10%; this keeps normalized single-agent voting from silently producing full exposure. No probability-to-return conversion occurs.

Eligible active sets are projected by the existing M5 equal-weight optimizer using actual past-available M2 return means/covariance. All configured M5 constraints apply. A fixed M5 equal-weight baseline mode activates the declared universe through the same optimizer/risk/ledger path. Baseline and committee modes are explicit in the immutable request.

Missing/contradictory evidence uses the declared cash-active-set policy; it can lead to reduced exposure. Persisted final actions distinguish approve, maintain, reduce, more_cash, reject and abstain. Orders and realized holdings are not inferred from those labels.

## Veto and execution

Independent M5 residual checks reject nonfinite/negative/overleveraged weights, incompatible universes or covariance, future or older-than-seven-day risk inputs, and violations of existing cash, position/concentration, group, sector, volatility/variance, turnover and tracking-error limits. Live execution is unsupported. Original proposals, slacks and violations are retained. A veto returns no approved target and the M4 adapter emits **no orders for that decision**. Existing holdings are not magically liquidated by a rejected proposal; they remain visible in the authoritative ledger.

M4 enforces next-permitted open, exchange sessions, cash, transaction costs, slippage, participation limits, partial fills and its existing corporate-action/raw-daily-data limitations. The source snapshot and cost contract are reused. No synthetic fill is manufactured. Decisions store intended approved weights and actual quantities/weights/cash before the decision. M4 artifacts separately record requested orders, status/rejections, fills, actual portfolio cash/holdings/equity and reconciliation.

## Durable audit and replay

Migration 0010 adds only `committee_runs` and `committee_decisions`. Parent IDs and unique idempotency keys identify immutable configuration/source manifests. Ordered decisions are unique by parent/sequence and hold recommendations, clocks, dependencies, policy/aggregation, M5 proposal/diagnostics, risk veto, approved weights, execution eligibility and actual pre-decision positions. M5 results are referenced through the decision's allocation/proposal; M4 execution remains a foreign-key child, with orders/fills retrievable from that ledger.

Selected derived cells and numeric model/selection evidence are frozen. Raw prices remain referenced by immutable IDs plus a content hash; entire market/news datasets and M4 ledgers are not copied into committee tables. Replay resolves those original price IDs, verifies their exact content, and ignores later source revisions/models/selections. Missing/altered referenced prices produce a replay error; replay cannot reacquire unavailable originals.

A durable running parent is saved before computation. Decisions and M4 child/artifacts commit in one transaction; injected failure after ledger flush rolls both back and leaves a sanitized failed parent. Running duplicate keys conflict; identical finished requests return their original parent, and changed configurations return 409. Failed runs are not silently retried or overwritten. Timing metadata is supplementary; a failure updating it cannot relabel an already committed complete ledger as a rolled-back failure.

Replay verifies current executable build, library versions, request/input/result hashes, saved decision integrity and authoritative ledger hashes. It regenerates recommendations/abstentions, grouping, M5 proposals/vetoes, M4 orders/fills/equity and analytics. Decimal strings, IDs and nonnumeric content compare exactly; floating values use relative/absolute tolerance 1e-9. Solver elapsed time is excluded. Numeric risk decisions still use M5's own feasibility tolerance. A direct M4 child replay is refused with a parent-replay instruction.

This is deterministic replay of frozen derived evidence and versioned decisions, **not** a full re-ingestion/retraining/search experiment. Original M2/M3/M6/M7 reruns require their own frozen inputs and source builds. Administrative database writes can invalidate the hashes; they are not an authenticated external provenance authority.

## API and bounds

GET `/api/agents`, `/{agent_id}`, `/{agent_id}/performance`; POST `/api/agents/analyze`; POST `/api/investment-committee/analyze` and `/backtest`; GET `/api/investment-committee` and `/{run_id}`; paginated `/{run_id}/decisions`, `/agents`, `/evidence`, `/allocation`, `/risk-review`, `/execution`; POST `/{run_id}/replay`.

Requests reject unknown fields and arbitrary code. At most 50 assets, six analyst identities, one explicit model and one explicit strategy; up to ten years of input history and one evaluation year; M7 cell/row limits, 64-MiB frozen-source cap and M4 cooperative time bounds apply. Expensive committee operations share a local semaphore. Pagination is bounded. Existing local API safety restrictions remain. Reads trigger no acquisition, training, discovery or inference.

The performance endpoint exposes real persisted recommendations and explicitly reports insufficient source-authenticated standalone agent P&L attribution. It does not invent an agent return series. Quant diagnostics and the separate foundation matured-outcome evaluator provide descriptive historical measures; adaptive weighting remains deliberately withheld.

## Reproduction

Run the actual integration fixture suite without downloads:

```sh
pytest -q backend/tests/test_committee_integration.py
```

With the retained original M7 IBM database, run all fixed ablations, M4 baselines, API checks and replay into a new database:

```sh
python scripts/verify_committee.py --source /path/to/real-IBM-release.db \
  --database /tmp/new-committee.db --report /tmp/committee.json --genuine
python scripts/replay_committee.py --database-url sqlite:////tmp/new-committee.db \
  --run-id UUID_FROM_REPORT
```

Synthetic 1/5/20/50-asset benchmark mode accepts the corresponding retained M5 source database and `--assets N`. It measures one historical multi-asset analysis with source retrieval, agent/grouping, M5/risk, persistence and replay, including dependency memory. Preparation is reported separately. Original forecasts are retrieved, not refit/inferred; no transformer load is included. Raw databases/model caches are deliberately excluded from the source archive. See the delivery report and `VERIFICATION_M8.json` for measured results, exact retained audit paths and limitations.


## Milestone 9 authority hierarchy

Research agents provide evidence and may abstain. The committee proposes; M5 allocates; the deterministic M9 Risk Manager may reject or reduce; M4 executes authorized quantities and alone updates the ledger. Consensus cannot override a hard veto. A second risk check at the actual opening fill prevents accidental forwarding from bypassing the target check. Post-event monitoring distinguishes unavailable data, execution mismatch and market movement and proposes future M4 corrections. `risk_policy=None` retains the prior M8 safeguards without implying M9 coverage. See [risk contracts](RISK_MANAGEMENT.md), immutable policy/replay rules and the [M9 report](MILESTONE9_REPORT.md). No LLM calculates or overrides risk.
