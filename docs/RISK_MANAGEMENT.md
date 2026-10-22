# Independent risk management — Milestone 9

Version 0.9.0, methodology 9.0.0, schema 0011. This is a local, simulation-only equity risk system. Estimates and scenarios are not loss guarantees. There is no brokerage connection, short-sale engine, margin account, derivative pricing model or production risk certification.

## Architecture and authority

M8 evidence/abstention → committee → existing M5 allocation → independent M9 target validation → existing M4 order submission → M9 fresh pre-fill authorization → M4 execution/Decimal ledger → M9 actual post-open/post-close monitoring.

`risk/contracts.py` defines state and policies; `analytics.py` calculates measurements; `governance.py` applies one shared authority; `legacy.py` contains the original M8/M5 residual checks, imported by the old committee interface rather than copied into a competing controller. `controller.py` adapts actual M4 events without writing positions or cash. `storage.py` persists immutable policy versions and assessments. `validation.py` evaluates prior-issued one-session forecasts. M4 and M5 accounting/optimization remain authoritative.

M9 is explicitly enabled by `committee.requests.Request.risk_policy`. Omitting it preserves M8's original safeguards and behavior; it does not imply advanced risk controls were applied. No agent recommendation, consensus, confidence or past backtest score can override the numerical controller. The fill guard independently revalidates even a rejected proposal accidentally forwarded by an upstream component. Direct callers of M4 without a controller retain the pre-existing M4 safeguards; they are not represented as M9-controlled runs. This is an in-process trust boundary, not protection against arbitrary code modifying the Python process.

## Input and time contract

State includes portfolio ID, decision/valuation timestamps, USD cash/equity, nonnegative quantities, stable security IDs, raw prices with observation/availability clocks, actual equity history and pending orders. Equity reconciles to cash plus priced positions within USD 0.000001. A missing held quote produces an unavailable exposure rather than a fabricated price. Zero/negative equity, shorts, duplicate/conflicting IDs, future valuations/history, unsupported currency/security type and nonfinite fields are rejected.

A return observation has session date, availability, raw basis, nullable ticker values and source. Eligible observations satisfy session ≤ decision date and availability ≤ decision time. Complete-case M5 estimation never bridges missing M2 returns. Adjusted returns and adjusted/unknown trading quotes are incompatible with this raw M4 simulation. No corporate-action history is invented. Volume observations have their own dates and availability; unavailable values remain unverified.

The committee adapter freezes source references and M2 cells. Online mode respects ingestion and availability. Research reconstruction is explicitly retrospective: daily closes/volumes become eligible after modeled exchange close plus one second, and an opening quote is known only at its execution event. This is an event-model assumption, not verified historical provider publication timing. Sector/industry maps must be explicitly supplied as eligible policy information; current unversioned classifications are not backfilled into history. Unknown sectors remain `UNKNOWN`.

Default quote staleness is seven calendar days (configurable 1–30). Missing, future, suspended, incompatible or stale quotes needed for existing/proposed holdings veto trading, including sales: unavailable prices are not executable exits. Required missing covariance, tail, benchmark, classification, scenario or liquidity data fails closed. Optional unavailable measurements remain visible without silently becoming zero.

Historical scenario windows are bounded to1,827 calendar days; XNYS scenarios must fit the supported2000–2035 calendar.

Budgets: 50 assets, 1,260 return observations, 12 scenarios, 12,600 volume rows, 2,520 equity snapshots, 50 proposed orders and 100 pending orders. Standalone frozen inputs are capped at 64 MiB after validated parsing. API work uses a local semaphore; no distributed scheduler or hard process-memory isolation is claimed.

## Exposure and concentration

For quantity q, price P and equity E, value = qP and weight = qP/E. Long = sum(max(w,0)); short = sum(min(w,0)); gross = long − short; net = sum(w); cash = 1 − net. Borrowed exposure is max(net−1,0), but the accepted universe is long-only/unlevered. USD values and dimensionless fractions are explicit.

HHI = sum(w²), effective holdings = 1/HHI; invested-normalized HHI = sum(w²)/(sum(w))². Equity-weight effective holdings can exceed the security count when cash is large, so both conventions are returned. Cash-only effective holdings is undefined. Maximum/top-five weights, largest positions and sector/industry sums are reported. Unknown classifications are not imputed. Proposed analytics use post-cost hypothetical equity; actual analytics use M4 ledger equity. Exposure changes compare current and proposed weights.

## Covariance, volatility and attribution

Existing M5 supports sample, exponential and diagonal-shrinkage covariance, bounded rolling/expanding history and annualization by 252. The engine records asset order, sample dates, units, PSD/symmetry checks, eigenvalue regularization and raw conditioning/rank. Regularization is not evidence that an unidentified/singular risk model is reliable. Configured volatility limits require reliable unregularized support (default condition ceiling 1e12).

Estimated annual volatility = sqrt(w'Σw). Marginal contribution = Σw/vol; component contribution = w × marginal; percentage = component/vol. Components sum to estimated volatility. Near-zero volatility has undefined marginal/percentage attribution, not a division by zero. Historical static-weight volatility, downside deviation sqrt(252 mean(min(r,0)²)), loss frequency and last-20-observation downside are separate from actual ledger return statistics. Risk HHI uses percentage contributions and is a descriptive concentration measure, not a number of independent bets.

A configured benchmark basket uses real eligible panel returns: beta = w'Σb/(b'Σb), tracking error = sqrt((w−b)'Σ(w−b)), and active weights = w−b. A zero-variance/missing benchmark does not produce a fictional beta. There is no default fabricated market index.

## Historical one-session VaR and Expected Shortfall

Simple portfolio return is r = Xw using fixed current/proposed weights and past eligible returns. Loss L = −r: positive is loss; a negative VaR describes a historical gain quantile. There is no square-root-of-time extrapolation or parametric distribution assumption.

For n sorted losses ascending, confidence α, VaR = L[ceil(nα)−1], the empirical inverse CDF (NumPy's `inverted_cdf` convention). Let m=n(1−α), k=floor(m), f=m−k. ES = (sum of k largest losses + f × next-largest loss)/m. This integrates exactly the requested upper-tail mass, including discrete ties/boundaries; it does not average only strict exceedances. Floating boundary rounding has a 1e−12 guard. USD VaR/ES = fraction × the relevant equity.

Hand reference: losses [.01,.02,.03,.04], α=.625 → VaR .03, tail mass1.5, ES (.04+.5×.03)/1.5 = .0366666667. At .75, VaR .03 and ES .04. Constant returns/ties, signed gains, confidence changes and portfolio scaling have independent tests. Cash-only risk is exactly zero exposure; it does not validate a market-tail model.

The default minimum effective tail mass is five observations. A numerical estimate can still be displayed with `INSUFFICIENT_TAIL_DATA`; required VaR/ES limits cannot use it as a pass. Five tail observations is only an engineering minimum, not an empirical validation standard. See [NumPy quantile methods](https://numpy.org/doc/stable/reference/generated/numpy.quantile.html).

## Realized drawdown and state

Past eligible equity alone determines running peak, current/max-observed drawdown and duration. Duration is explicitly valuation-observation count and calendar time, not falsely labeled sessions when opens/closes coexist. Actual realized annual/downside volatility and loss frequency use only explicitly marked closing equity snapshots; unlabeled/intraday-only input does not receive daily annualization.

A threshold breach latches `HALTED`; mode is `no_new_risk` (no increase in quantities) or `cash` (zero-risk target). Default recovery count zero means no automatic reset. Explicit recovery requires a configured number of consecutive eligible valuations at or below a stricter recovery drawdown threshold. No future peak/trough enters earlier decisions. A state can be halted while a no-trade assessment is approved: approval covers that assessment only, not permission to buy. Alerts preserve the latch.

## Liquidity, turnover and costs

ADV and average dollar volume use eligible daily observations (default20, minimum5), with freshness checks. Position shares/ADV and proposed-plus-pending buy participation are proxies. Required participation/minimum dollar volume fails closed on `LIQUIDITY_UNVERIFIED`. Actual M4 participation checks remain in force. No order book, intraday depth, calibrated impact or liquidation-time forecast is inferred.

Plans use M4 minimum share quantity, whole-share flooring, fixed/per-share/percentage commission and slippage assumptions. Pending buys consume hypothetical cash and add exposure/participation; pending sells do not create spendable cash. A replacement target supersedes an old pending order only for a ticker whose target produces a new order, consistent with M4. Turnover is the existing M5 one-way allocation-change convention; costs are estimates until M4 fills. Daily OHLCV/open execution is an approximation.

## Stress scenarios

Hypothetical linear equity shocks use explicit asset override, then sector override, then broad shock; asset/sector USD loss contributions reconcile to portfolio loss and shocked equity. These are scenario inputs, not predictions. Historical scenarios compound actual returns per asset across every required calendar session, with coverage and availability checks; missing securities/sessions do not receive invented returns. Constant quantities are assumed; no rebalancing or executed fills occur. Nonfinite results raise an error. Volatility/correlation shocks and nonlinear instruments are unsupported because no justified revaluation model is available.

## Versioned policy and complete validation

Default `Policy(effective_at=...)` is a simulation template: cash allowed0–100%, concentration/invested maximum100%, M5 estimator lookback252/minimum60, confidence95%, minimum tail mass5, raw quote staleness7days, default reject adjustment, missing-required reject. Additional volatility, VaR/ES, drawdown, turnover, classification, participation, cost, stress and correlation limits are opt-in. No investor-suitability profiles are marketed.

Example (all fractions, not percent points):

```python
Policy(
    id="fixed-research",
    version="1",
    effective_at=earlier_aware_timestamp,
    constraints=Constraints(cash_maximum=1, concentration=0.5),
    drawdown_maximum=0.03,
    drawdown_mode="cash",
    adjustment="scale_to_cash",
)
```

M8 and M9 constraints merge by taking tighter maxima/higher minima, unioning restrictions and rejecting conflicting benchmark/group/classification definitions. The effective policy version includes the inherited M5-constraint hash and original definition hash. Policy `(id,version)` is immutable through the API; changing its content produces409. Future/wrong-portfolio policies are rejected. Frozen Pydantic contracts forbid extra fields and nonfinite values; no expression evaluation, YAML object construction or executable configuration is used.

Validation covers whole portfolio, incremental orders, actual cash, post-cost weights, all M5 residuals, data reliability and optional M9 limits together. Optional `scale_to_cash` evaluates up to20 (bounded40) simultaneous uniform reductions and fully rechecks each candidate. It is a conservative bounded search, not a claim to solve every feasible allocation. It may reject even when another feasible allocation exists. Lower bounds, turnover and costs can prevent a move to cash; cash is never automatically declared feasible.

| Decision | Permission |
|---|---|
| APPROVED | Only the assessed proposal may proceed to fresh M4 fill authorization. |
| APPROVED_WITH_REDUCTION | Only explicit approved targets/quantities may proceed; original proposal violations remain recorded. |
| REJECTED | No executable proposal. |
| NO_NEW_RISK | Restricted-state veto; no executable proposal from this assessment. |
| INSUFFICIENT_RISK_DATA | A required input/measurement is unavailable; no executable proposal. |

`executable` and `approved_plan` govern execution; a displayed numerical metric or proposal is not approval. Order-request assessments return hypothetical post-order weights plus quantity deltas, not a second order ledger.

## Execution, monitoring and alerts

Pre-target validation uses actual state and pending orders. Every M4 fill attempt then rechecks actual quantities/cash, fresh event marks and other pending buys. It may only reduce requested quantity; it cannot increase authorization. M4 alone handles partial fills, rounding, capacity, rejection and ledger conservation. The no-controller branch preserves original behavior.

Post-open/post-close assessments use actual ledger quantities and cash. Events distinguish unavailable data, execution mismatch and market movement. Proposed weight and actual weight are never substituted for one another. Corrective zero-target proposals are submitted at a future permitted strategy/M4 event and fully validated. Missing prices, turnover limits or other simultaneous constraints can prevent liquidation; alerts persist rather than fabricating an immediate exit. Sequential multi-asset fill validation is conservative and can block intermediate legs if existing holdings already violate policy.

## Persistence and replay

Migration0011 adds `risk_policy_versions`, `risk_assessments`, `risk_alerts`; no duplicate order/position tables. Committee events store state hashes and M8/M4 references, while standalone assessments freeze supplied inputs. Matrices common to proposed/approved reports reference current volatility to reduce storage. Alert identity is assessment+metric; mathematical decision identity excludes caller-supplied order identifiers, preventing duplicate rejected-order alerts. Committee event identities additionally include portfolio request namespace and phase.

M8 parent, M4 child ledger, decisions, effective policy and all risk events commit in one transaction. Failure rolls back all children, leaving the existing failed-parent audit. Repeated request keys with different inputs fail409. Repeated identical mathematical rejected assessments use the existing ID. SQLite restart/API retrieval was exercised.

Replay verifies code fingerprint, dependency versions, input/result/policy hashes and original referenced price hashes. Linked assessments reconstruct the whole frozen M8→M4 event chronology; standalone assessments use their frozen request. Numerical tolerance is rtol1e−9/atol1e−9; IDs/orderings/Decimal strings remain exact. Later policy versions or source revisions cannot silently replace old inputs. Missing or altered referenced data fails replay. This is retained-source reproducibility, not proof that retrospective data was historically published then. Replaying pre-M9 build audits with changed code correctly fails; old releases and databases remain preserved.

## API and reproduction

`GET /api/risk`, `/policies`, `/policies/{id}?version=...`, `/decisions/{id}`, `/alerts`, `/history`; `POST /evaluate`, `/stress-test`, `/decisions/{id}/replay`. Portfolio routes expose full assessment or `/exposure`, `/var`, `/cvar`, `/drawdown`, `/concentration`, `/volatility`, `/stress`. Supply `snapshot=current|proposed|approved`, exact `assessment_id` or aware `as_of`. An unavailable earlier snapshot returns404; latest state is not substituted. Pages are bounded with offsets. The API trusts validated caller-supplied standalone state; it is not an authenticated custodian feed. Exact schemas are in [OpenAPI](openapi.json).

From the repository with dependencies installed and retained source DB available:

```sh
PYTHONPATH=backend python scripts/verify_risk.py --source SOURCE_M8.db --database NEW_M9.db --report comparison.json --genuine
PYTHONPATH=backend python scripts/validate_risk_research.py --database NEW_M9.db --comparison comparison.json --report research.json
PYTHONPATH=backend python scripts/replay_risk.py --database-url sqlite:///NEW_M9.db --assessment-id STORED_ID
pytest -q backend/tests/test_risk_math.py backend/tests/test_risk_integration.py
```

For synthetic workloads run `verify_risk.py` with `--assets 1|5|20|50` and retained M5 source, then `benchmark_risk.py --database NEW.db --comparison comparison.json --report benchmark.json`. No script downloads data, overwrites existing audit DBs or selects a profile after observing returns. Private DBs/model weights are excluded from source packaging; offline integration tests generate small fixtures and verify the complete flow without retained research databases.

## Empirical validation and limitations

Shadow forecasts use prior eligible current weights and subsequent close-to-close market returns, distinct from dynamic trading P&L. Future outcomes are excluded until maturity. Diagnostic records must share portfolio/policy/confidence, have unique forecast times and forecast < outcome ≤ availability. Tiny/unreliable samples receive no p-value. With at least250 qualified forecasts and expected tail count≥5, the standard exact binomial diagnostic/95% interval is descriptive, explicitly assuming unverified IID exceptions; it does not validate clustering or model stability. See [SciPy binomtest](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binomtest.html).

The retained IBM experiment is a short, previously inspected retrospective raw-price sample. M8 lost8.70% against buy-hold loss4.69%; this negative finding remains. Fixed M9 policies change exposure/costs and can reduce profits as well as losses. Tail history is insufficient; seven matured nonzero-exposure shadow forecasts validate nothing statistically. Sensitivity covers fixed20/60/90-session lookbacks, all three covariance choices and95/99% confidence without choosing a winner. Two independent-capital M4 folds use fixed policy, not holdout tuning.

Measured benchmarks and exact gates are in [MILESTONE9_REPORT.md](MILESTONE9_REPORT.md) and VERIFICATION_M9.json (`VERIFICATION_M9.json`, intentionally omitted; see PUBLICATION_SELECTION.md). Native PostgreSQL and Docker remain blocked; CI is configured but has not executed here. Genuine PIT news/fundamental/macro coverage, universe survivorship, corporate actions, calibrated execution, multi-asset empirical tail validation, authentication and operational controls remain unresolved. No established research alpha or institutional production readiness is claimed.
