"""Deterministic exposure, empirical tails and linear equity scenarios; no loss guarantees."""

from datetime import timedelta
from math import ceil, floor, sqrt
from time import perf_counter
from typing import Any

import numpy as np
from numpy.typing import NDArray

from sentientalpha.data.calendar import sessions_in_range
from sentientalpha.optimization.estimation import OptimizationError, Panel, ReturnRow, estimate
from sentientalpha.risk.contracts import (
    EvaluationRequest,
    Policy,
    PortfolioState,
)


def exposure(
    state: PortfolioState,
    policy: Policy,
    weights: dict[str, float] | None = None,
    equity_override: float | None = None,
) -> dict[str, Any]:
    prices = {p.ticker: p for p in state.prices}
    if weights is None:
        if any(q and prices[t].value is None for t, q in state.quantities.items()):
            return {"status": "UNAVAILABLE", "reason": "Missing price for a held security"}
        values = {t: float(q * (prices[t].value or 0)) for t, q in state.quantities.items()}
        weights = {t: v / float(state.equity) for t, v in values.items()}
    else:
        values = {
            t: v * (float(state.equity) if equity_override is None else equity_override)
            for t, v in weights.items()
        }
    w = np.array(list(weights.values()), dtype=float)
    if not np.all(np.isfinite(w)):
        raise OptimizationError("Nonfinite exposure")
    long = float(np.maximum(w, 0).sum())
    short = float(np.minimum(w, 0).sum())
    hhi = float(w @ w)
    invested = float(w.sum())
    sectors: dict[str, float] = {}
    industries: dict[str, float] = {}
    for t, v in weights.items():
        sector = policy.constraints.sectors.get(t, "UNKNOWN")
        industry = policy.industries.get(t, "UNKNOWN")
        sectors[sector] = sectors.get(sector, 0) + v
        industries[industry] = industries.get(industry, 0) + v
    ordered = sorted(weights.items(), key=lambda x: (-abs(x[1]), x[0]))
    return {
        "status": "CALCULATED",
        "units": "fractions of current portfolio equity / USD market values",
        "market_values": values,
        "weights": weights,
        "cash_weight": 1 - invested,
        "long": long,
        "short": short,
        "gross": long - short,
        "net": invested,
        "borrowed_exposure": max(0.0, invested - 1),
        "short_margin_supported": False,
        "hhi_equity_weights": hhi,
        "effective_holdings_equity": 1 / hhi if hhi else None,
        "hhi_invested_normalized": hhi / invested**2 if invested > 0 else None,
        "effective_holdings_invested": invested**2 / hhi if hhi else None,
        "maximum_weight": max(weights.values(), default=0),
        "top_five": sum(v for _, v in ordered[:5]),
        "sectors": sectors,
        "industries": industries,
        "largest_positions": [list(v) for v in ordered[:5]],
    }


def tails(
    returns: NDArray[np.float64], confidence: float, equity: float, minimum_tail_mass: float
) -> dict[str, Any]:
    if returns.ndim != 1 or not len(returns) or not np.all(np.isfinite(returns)):
        return {
            "status": "UNAVAILABLE",
            "var_loss_fraction": None,
            "cvar_loss_fraction": None,
            "samples": 0,
        }
    losses = np.sort(-returns)
    n = len(losses)
    # Empirical inverse CDF and exactly (1-alpha) tail mass, including its boundary.
    index = max(0, min(n - 1, ceil(n * confidence) - 1))
    var = float(losses[index])
    mass = n * (1 - confidence)
    whole = floor(mass + 1e-12)
    fraction = max(0.0, mass - whole)
    top = losses[::-1]
    total = float(top[:whole].sum())
    if fraction and whole < n:
        total += fraction * float(top[whole])
    es = total / mass
    return {
        "status": "CALCULATED" if mass + 1e-10 >= minimum_tail_mass else "INSUFFICIENT_TAIL_DATA",
        "method": "empirical_inverse_CDF_and_fractional_tail_mass_ES",
        "confidence": confidence,
        "horizon_sessions": 1,
        "samples": n,
        "effective_tail_observations": mass,
        "strictly_above_var": int(np.sum(losses > var)),
        "var_loss_fraction": var,
        "cvar_loss_fraction": es,
        "var_currency": var * equity,
        "cvar_currency": es * equity,
        "loss_convention": "loss=-simple_return; negative quantile is gain, never a guarantee",
        "warnings": ["Empirical finite-sample losses are not worst-case guarantees"]
        + (
            ["Too few effective tail observations for the required reliability"]
            if mass < minimum_tail_mass - 1e-10
            else []
        ),
    }


def drawdown(state: PortfolioState) -> dict[str, Any]:
    history = [(e.at, float(e.value)) for e in state.equity_history]
    if not history or history[-1][0] < state.at:
        history.append((state.at, float(state.equity)))
    elif history[-1][0] == state.at and abs(history[-1][1] - float(state.equity)) > 1e-6:
        raise OptimizationError("Equity history conflicts with current ledger state")
    peak = history[0][1]
    peak_at = history[0][0]
    maximum = 0.0
    duration = 0
    worst_duration = 0
    for at, value in history:
        if value >= peak:
            peak = value
            peak_at = at
            duration = 0
        else:
            duration += 1
        maximum = max(maximum, 1 - value / peak)
        worst_duration = max(worst_duration, duration)
    closes = [float(e.value) for e in state.equity_history if e.kind == "closing"]
    realized = np.array([b / a - 1 for a, b in zip(closes, closes[1:], strict=False)], dtype=float)
    return {
        "realized_close_return_samples": len(realized),
        "realized_annual_volatility": float(np.std(realized, ddof=1) * sqrt(252))
        if len(realized) >= 2
        else None,
        "realized_downside_annual": float(np.sqrt(np.mean(np.minimum(realized, 0) ** 2) * 252))
        if len(realized)
        else None,
        "realized_loss_frequency": float(np.mean(realized < 0)) if len(realized) else None,
        "equity_change_since_first_observation": float(state.equity) - history[0][1],
        "realized_volatility_scope": (
            "Actual explicitly marked closing equity snapshots; "
            "undefined for unlabeled/intraday-only history"
        ),
        "status": "CALCULATED",
        "current": 1 - float(state.equity) / peak,
        "maximum_observed": maximum,
        "peak_equity": peak,
        "peak_at": peak_at.isoformat(),
        "duration_valuation_observations": duration,
        "maximum_duration_observations": worst_duration,
        "calendar_days_since_peak": (state.at - peak_at).total_seconds() / 86400,
        "samples": len(history),
        "scope": "Realized eligible equity path only; no future trough or peak",
    }


def matrix(request: EvaluationRequest) -> tuple[Panel, NDArray[np.float64], dict[str, Any]]:
    names = tuple(sorted(p.ticker for p in request.state.prices))
    rows = tuple(
        ReturnRow(
            r.day, tuple(r.values.get(t) for t in names), tuple(r.available_at for _ in names)
        )
        for r in sorted(request.returns, key=lambda r: r.day)
    )
    panel = Panel(names, rows, request.state.calendar)
    start = min((r.day for r in request.returns), default=request.state.at.date())
    x, meta = panel.eligible(
        request.state.at, start, request.state.at.date(), request.policy.estimator
    )
    return panel, x, meta


def stress(
    request: EvaluationRequest, weights: dict[str, float], equity_override: float | None = None
) -> list[dict[str, Any]]:
    results = []
    at = request.state.at
    policy = request.policy
    equity = float(request.state.equity) if equity_override is None else equity_override
    for scenario in policy.scenarios:
        item: dict[str, Any] = {
            "id": scenario.id,
            "version": scenario.version,
            "kind": scenario.kind,
            "status": "CALCULATED",
            "assumption": "Linear equity, constant quantities; no trading or nonlinear pricing",
        }
        shocks = {}
        if scenario.effective_at > at:
            item.update(status="UNAVAILABLE", reason="Future scenario")
        elif scenario.kind == "hypothetical":
            if set(scenario.assets) - set(weights):
                item.update(
                    status="UNAVAILABLE", reason="Scenario assets outside portfolio universe"
                )
            elif scenario.sectors and any(
                weights[t] > 0 and t not in policy.constraints.sectors for t in weights
            ):
                item.update(status="UNAVAILABLE", reason="Missing historical sector classification")
            else:
                shocks = {
                    t: scenario.assets.get(
                        t,
                        scenario.sectors.get(
                            policy.constraints.sectors.get(t, ""), scenario.broad_shock
                        ),
                    )
                    for t in weights
                }
        else:
            assert scenario.start is not None and scenario.end is not None
            expected = sessions_in_range(request.state.calendar, scenario.start, scenario.end)
            actual = {
                r.day: r
                for r in request.returns
                if scenario.start <= r.day <= scenario.end and r.available_at <= at
            }
            if scenario.end > at.date() or not expected or any(d not in actual for d in expected):
                item.update(
                    status="UNAVAILABLE", reason="Historical scenario coverage/clocks incomplete"
                )
            elif any(
                actual[d].values.get(t) is None for d in expected for t, w in weights.items() if w
            ):
                item.update(status="UNAVAILABLE", reason="Missing actual historical asset returns")
            else:
                shocks = {
                    t: float(np.prod([1 + float(actual[d].values[t] or 0.0) for d in expected]) - 1)
                    if weights[t]
                    else 0.0
                    for t in weights
                }
                item.update(
                    start=str(scenario.start), end=str(scenario.end), sessions=len(expected)
                )
        if item["status"] == "CALCULATED":
            contributions = {t: -equity * weights[t] * r for t, r in shocks.items()}
            loss = sum(contributions.values())
            sectors: dict[str, float] = {}
            for t, v in contributions.items():
                s = policy.constraints.sectors.get(t, "UNKNOWN")
                sectors[s] = sectors.get(s, 0) + v
            item.update(
                shocks=shocks,
                loss_currency=loss,
                loss_fraction=loss / equity,
                equity_after=equity - loss,
                asset_loss_contributions=contributions,
                sector_loss_contributions=sectors,
            )
            if not np.isfinite(loss):
                raise OptimizationError("Nonfinite scenario result")
        results.append(item)
    return results


def analyse(
    request: EvaluationRequest,
    weights: dict[str, float] | None = None,
    cached: tuple[Any, ...] | None = None,
    timings: dict[str, float] | None = None,
    equity_override: float | None = None,
) -> dict[str, Any]:
    state, policy = request.state, request.policy
    began = perf_counter()
    exp = exposure(state, policy, weights, equity_override)
    dd = drawdown(state)
    if timings is not None:
        timings["exposure"] = timings.get("exposure", 0.0) + perf_counter() - began
    if exp["status"] != "CALCULATED":
        return {"exposure": exp, "drawdown": dd, "status": "UNAVAILABLE"}
    weights = exp["weights"]
    names = tuple(sorted(p.ticker for p in state.prices))
    w = np.array([weights.get(t, 0.0) for t in names])
    prices = {p.ticker: p for p in state.prices}
    quality = []
    for t, v in weights.items():
        if not v:
            continue
        price = prices[t]
        if price.value is None or price.suspended:
            quality.append("missing_or_suspended_price:" + t)
        if price.basis != "raw":
            quality.append("incompatible_price_basis:" + t)
        if price.available_at > state.at:
            quality.append("future_price:" + t)
        if state.at - price.observed_at > timedelta(days=policy.stale_days):
            quality.append("stale_price:" + t)
    estimated = None
    x = None
    history_meta: dict[str, Any] = {}
    error = None
    began = perf_counter()
    try:
        if cached is None:
            panel, x, history_meta = matrix(request)
            estimated = estimate(
                panel,
                state.at,
                min(r.day for r in request.returns),
                state.at.date(),
                policy.estimator,
            )
        else:
            estimated, x, history_meta = cached
    except OptimizationError as exc:
        error = str(exc)
    if timings is not None:
        timings["covariance"] = timings.get("covariance", 0.0) + perf_counter() - began
    volatility: dict[str, Any] = {
        "status": "UNAVAILABLE",
        "estimated_annual": None,
        "reason": error,
    }
    empirical: dict[str, Any] = {
        "status": "UNAVAILABLE",
        "var_loss_fraction": None,
        "cvar_loss_fraction": None,
        "samples": 0,
    }
    if estimated is not None and x is not None:
        cov = estimated.covariance
        variance = max(0.0, float(w @ cov @ w))
        vol = sqrt(variance)
        diagonal = np.sqrt(np.maximum(np.diag(cov), 0))
        denom = np.outer(diagonal, diagonal)
        corr = np.divide(cov, denom, out=np.zeros_like(cov), where=denom > 0)
        portfolio = x @ w
        actual_cov = np.atleast_2d(np.cov(x, rowvar=False, ddof=1))
        condition = float(np.linalg.cond(actual_cov)) if np.any(actual_cov) else None
        raw_den = np.outer(
            np.sqrt(np.maximum(np.diag(actual_cov), 0)), np.sqrt(np.maximum(np.diag(actual_cov), 0))
        )
        raw_corr = np.divide(actual_cov, raw_den, out=np.zeros_like(actual_cov), where=raw_den > 0)
        rank = int(np.linalg.matrix_rank(actual_cov))
        reliable = (
            rank == len(names)
            and condition is not None
            and np.isfinite(condition)
            and condition <= policy.covariance_condition_maximum
        )
        marginal = cov @ w / vol if vol > 1e-14 else None
        components = w * marginal if marginal is not None else None
        relative = components / vol if components is not None else None
        benchmark = policy.constraints.benchmark_weights
        beta = tracking = None
        active = None
        if benchmark is not None:
            b = np.array([benchmark.get(t, 0.0) for t in names])
            bvariance = float(b @ cov @ b)
            beta = float(w @ cov @ b / bvariance) if bvariance > 1e-14 else None
            tracking = sqrt(max(0.0, float((w - b) @ cov @ (w - b))))
            active = {t: weights.get(t, 0.0) - benchmark.get(t, 0.0) for t in names}
        volatility = {
            "status": "CALCULATED",
            "estimated_annual": vol,
            "estimated_variance_annual": variance,
            "historical_annual": float(np.std(portfolio, ddof=1) * sqrt(252)),
            "downside_annual": float(np.sqrt(np.mean(np.minimum(portfolio, 0) ** 2) * 252)),
            "loss_frequency": float(np.mean(portfolio < 0)),
            "rolling_downside_20": float(
                np.sqrt(np.mean(np.minimum(portfolio[-20:], 0) ** 2) * 252)
            ),
            "covariance": cov.tolist(),
            "correlation": corr.tolist(),
            "raw_correlation": raw_corr.tolist(),
            "asset_order": list(names),
            "marginal_volatility": dict(zip(names, marginal.tolist(), strict=True))
            if marginal is not None
            else None,
            "component_volatility": dict(zip(names, components.tolist(), strict=True))
            if components is not None
            else None,
            "percentage_volatility": dict(zip(names, relative.tolist(), strict=True))
            if relative is not None
            else None,
            "risk_hhi": float(relative @ relative) if relative is not None else None,
            "benchmark_beta": beta,
            "tracking_error_annual": tracking,
            "active_weights": active,
            "raw_covariance_rank": rank,
            "raw_condition_number": condition
            if condition is not None and np.isfinite(condition)
            else None,
            "raw_covariance_reliable": bool(reliable),
            "estimation": estimated.metadata,
            "warnings": (
                []
                if reliable
                else ["Raw covariance unreliable; regularization does not establish reliability"]
            ),
        }
        began = perf_counter()
        empirical = tails(
            portfolio,
            policy.confidence,
            float(state.equity) if equity_override is None else equity_override,
            policy.minimum_tail_mass,
        )
        if timings is not None:
            timings["tails"] = timings.get("tails", 0.0) + perf_counter() - began
    if not np.any(w):
        volatility = {
            **volatility,
            "status": "EXACT_ZERO_EXPOSURE",
            "estimated_annual": 0.0,
            "historical_annual": 0.0,
            "downside_annual": 0.0,
            "loss_frequency": 0.0,
        }
        empirical = {
            **empirical,
            "status": "EXACT_ZERO_EXPOSURE",
            "var_loss_fraction": 0.0,
            "cvar_loss_fraction": 0.0,
            "var_currency": 0.0,
            "cvar_currency": 0.0,
        }
    liquidity = {}
    for t in names:
        eligible = sorted(
            [
                v
                for v in request.volumes
                if v.ticker == t and v.day <= state.at.date() and v.available_at <= state.at
            ],
            key=lambda v: v.day,
        )[-policy.volume_lookback :]
        valid = [v for v in eligible if v.volume is not None and v.volume > 0]
        verified = (
            len(valid) >= policy.minimum_volume_observations
            and bool(valid)
            and (state.at.date() - valid[-1].day).days <= policy.stale_days
        )
        adv = float(np.mean([v.volume for v in valid])) if valid else None
        liquidity[t] = {
            "status": "DAILY_VOLUME_PROXY" if verified else "LIQUIDITY_UNVERIFIED",
            "observations": len(valid),
            "average_volume": adv,
            "average_dollar_volume": float(np.mean([v.close * float(v.volume or 0) for v in valid]))
            if valid
            else None,
            "position_shares_to_ADV": abs(weights.get(t, 0))
            * float(state.equity)
            / float(prices[t].value or 1)
            / adv
            if adv and prices[t].value
            else None,
            "latest_available_at": valid[-1].available_at.isoformat() if valid else None,
            "limitations": "Daily volume proxy; no depth, impact or liquidation forecast",
        }
    began = perf_counter()
    scenarios = stress(request, weights, equity_override)
    if timings is not None:
        timings["stress"] = timings.get("stress", 0.0) + perf_counter() - began
    return {
        "status": "CALCULATED" if not quality else "DATA_QUALITY_FAILURE",
        "exposure": exp,
        "drawdown": dd,
        "volatility": volatility,
        "tail": empirical,
        "liquidity": liquidity,
        "stress": scenarios,
        "quality_violations": quality,
        "sample": history_meta,
        "currency": "USD",
        "risk_kind": "estimated_weights_on_past_returns; realized_drawdown; scenario_shocks",
    }
