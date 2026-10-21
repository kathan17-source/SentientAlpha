"""Ledger-derived statistics; undefined ratios remain null."""

from collections import defaultdict
from datetime import date
from math import expm1, log, sqrt
from typing import Any

import numpy as np


def annual_growth(total: float, exponent: float) -> float | None:
    if total <= -1:
        return -1.0
    power = log(1 + total) * exponent
    return expm1(power) if power < 709 else None


def ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator > 1e-14 else None


def analytics(
    equity: list[dict[str, Any]],
    initial: float,
    fills: list[dict[str, Any]],
    closed: list[float],
    benchmark: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if initial <= 0 or not equity:
        return {"status": "insufficient_data"}
    values = np.array([float(r["equity"]) for r in equity])
    if np.any(values <= 0) or not np.all(np.isfinite(values)):
        return {"status": "invalid_equity"}
    returns = values / np.r_[initial, values[:-1]] - 1
    total = float(values[-1] / initial - 1)
    n = len(returns)
    vol = float(np.std(returns, ddof=1) * sqrt(252)) if n > 1 else None
    downside = float(np.sqrt(np.mean(np.minimum(returns, 0) ** 2)) * sqrt(252)) if n > 1 else None
    annual = annual_growth(total, 252 / n) if n > 1 else None
    elapsed = (date.fromisoformat(equity[-1]["day"]) - date.fromisoformat(equity[0]["day"])).days
    cagr = annual_growth(total, 365.25 / elapsed) if elapsed > 0 else None
    highs = np.maximum.accumulate(np.r_[initial, values])[1:]
    drawdowns = values / highs - 1
    duration = maximum_duration = 0
    for d in drawdowns:
        duration = duration + 1 if d < -1e-14 else 0
        maximum_duration = max(maximum_duration, duration)
    maximum = float(-np.min(drawdowns))
    threshold = float(np.quantile(returns, 0.05)) if n >= 20 else None
    monthly: dict[str, list[float]] = defaultdict(list)
    for row, r in zip(equity, returns, strict=True):
        monthly[row["day"][:7]].append(float(r))
    gains, losses = sum(x for x in closed if x > 0), -sum(x for x in closed if x < 0)
    rolling = []
    bench_returns = None
    if benchmark is not None and [r["day"] for r in benchmark] == [r["day"] for r in equity]:
        bv = np.array([float(r["equity"]) for r in benchmark])
        if np.all(bv > 0):
            bench_returns = bv / np.r_[initial, bv[:-1]] - 1
    for i, row in enumerate(equity):
        window = returns[max(0, i - 19) : i + 1]
        sd = float(np.std(window, ddof=1) * sqrt(252)) if len(window) == 20 else None
        beta = None
        if bench_returns is not None and len(window) == 20:
            bw = bench_returns[i - 19 : i + 1]
            variance = float(np.var(bw, ddof=1))
            beta = float(np.cov(window, bw, ddof=1)[0, 1] / variance) if variance > 1e-14 else None
        rolling.append(
            {
                "day": row["day"],
                "volatility": sd,
                "sharpe": ratio(float(np.mean(window) * 252), sd) if sd is not None else None,
                "beta": beta,
            }
        )
    result: dict[str, Any] = {
        "status": "computed",
        "total_return": total,
        "cumulative_return": total,
        "annualized_return": annual,
        "cagr": cagr,
        "annualized_volatility": vol,
        "downside_deviation": downside,
        "maximum_drawdown": maximum,
        "drawdown_duration_sessions": maximum_duration,
        "historical_var_95": -threshold if threshold is not None else None,
        "historical_cvar_95": -float(np.mean(returns[returns <= threshold]))
        if threshold is not None
        else None,
        "sharpe": ratio(float(np.mean(returns) * 252), vol) if vol is not None else None,
        "sortino": ratio(float(np.mean(returns) * 252), downside) if downside is not None else None,
        "calmar": ratio(annual, maximum) if annual is not None else None,
        "alpha": None,
        "beta": None,
        "tracking_error": None,
        "information_ratio": None,
        "excess_return": None,
        "trade_count": len(fills),
        "closed_lot_count": len(closed),
        "win_rate": sum(x > 0 for x in closed) / len(closed) if closed else None,
        "profit_factor": ratio(gains, losses) if closed else None,
        "average_trade_pnl": sum(closed) / len(closed) if closed else None,
        "turnover": sum(float(f["quantity"]) * float(f["price"]) for f in fills)
        / (2 * float(np.mean(values))),
        "commissions": sum(float(f["commission"]) for f in fills),
        "slippage": sum(float(f["slippage"]) for f in fills),
        "average_exposure": float(np.mean([r["gross_exposure"] for r in equity])),
        "daily_returns": [
            {"day": row["day"], "return": float(r)} for row, r in zip(equity, returns, strict=True)
        ],
        "monthly_returns": [
            {"month": m, "return": float(np.prod(1 + np.array(rs)) - 1)}
            for m, rs in sorted(monthly.items())
        ],
        "drawdown": [
            {"day": row["day"], "drawdown": float(d)}
            for row, d in zip(equity, drawdowns, strict=True)
        ],
        "rolling": rolling,
    }
    if bench_returns is not None and n > 1:
        variance = float(np.var(bench_returns, ddof=1))
        beta = (
            float(np.cov(returns, bench_returns, ddof=1)[0, 1] / variance)
            if variance > 1e-14
            else None
        )
        active = returns - bench_returns
        tracking = float(np.std(active, ddof=1) * sqrt(252))
        result.update(
            beta=beta,
            alpha=float((np.mean(returns) - beta * np.mean(bench_returns)) * 252)
            if beta is not None
            else None,
            tracking_error=tracking,
            information_ratio=ratio(float(np.mean(active) * 252), tracking),
            excess_return=total - float(np.prod(1 + bench_returns) - 1),
        )
    return result
