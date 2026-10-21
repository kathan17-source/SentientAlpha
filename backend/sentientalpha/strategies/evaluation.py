"""Current-only rule adapter and dimensionless validation fitness on M4 accounting."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from math import isfinite, tanh
from typing import Any, Literal, cast

import numpy as np

from sentientalpha.backtesting.contracts import Request as BacktestRequest
from sentientalpha.backtesting.contracts import Snapshot, StrategySpec
from sentientalpha.backtesting.engine import simulate
from sentientalpha.backtesting.strategies import Context
from sentientalpha.data.calendar import session_close
from sentientalpha.strategies.contracts import Definition, Fitness, Request
from sentientalpha.strategies.grammar import compare, complexity, validate
from sentientalpha.strategies.inputs import Inputs


class RuleStrategy:
    def __init__(self, definition: Definition, inputs: Inputs, tickers: list[str], delay: int = 0):
        validate(definition, set(inputs.available))
        self.definition, self.inputs, self.tickers, self.delay = definition, inputs, tickers, delay
        self.trace: list[dict[str, Any]] = []
        self.since: dict[str, date] = {}
        self.previous: date | None = None
        self.last_observation: date | None = None
        self.complete = self.considered = 0
        days = sorted({d for d, _ in inputs.signals})
        self.days = days
        self.positions = {d: i for i, d in enumerate(days)}

    def targets(self, context: Context) -> dict[str, Decimal]:
        s, day = self.definition, context.day
        # A late publication from another security must not rewind the portfolio rule state.
        if self.last_observation is not None and day < self.last_observation:
            return {}
        self.last_observation = day
        previous = self.previous
        due = (
            previous is None
            or s.rebalance == "daily"
            or (s.rebalance == "weekly" and day.isocalendar()[:2] != previous.isocalendar()[:2])
            or (
                s.rebalance == "monthly"
                and (day.year, day.month) != (previous.year, previous.month)
            )
        )
        if due:
            self.previous = day
        holdings, prices = dict(context.quantities), dict(context.prices)
        weights = {}
        for ticker in self.tickers:
            if ticker not in prices:
                continue
            held = holdings.get(ticker, Decimal(0)) > 0
            if held:
                self.since.setdefault(ticker, day)
            else:
                self.since.pop(ticker, None)
            idx = self.positions.get(day, -1) - self.delay
            source_day = self.days[idx] if idx >= 0 else None
            cells = self.inputs.signals.get((source_day, ticker), {}) if source_day else {}
            used: dict[str, Any] = {}

            def resolver(
                name: str, cells: dict[str, Any] = cells, used: dict[str, Any] = used
            ) -> float | None:
                item = cells.get(name)
                ready = item is not None and item.ready is not None and item.ready <= context.at
                value = item.value if ready and item is not None else None
                used[name] = {
                    "value": value,
                    "available_at": item.ready.isoformat() if item and item.ready else None,
                    "source": item.source if item else None,
                    "reason": item.reason if item else "missing_observation",
                }
                return value

            entry, e = compare(s.entry, resolver)
            exit_value, x = compare(s.exit, resolver) if s.exit else (False, None)
            self.considered += 1
            self.complete += int(entry is not None and exit_value is not None)
            age = self.positions[day] - self.positions[self.since[ticker]] + 1 if held else 0
            expired = held and s.holding_sessions is not None and age >= s.holding_sessions
            # Actual fills determine held state, not prior target requests. Exits take precedence.
            long = held
            action = "hold"
            if (
                expired
                or exit_value is True
                or (s.missing_policy == "cash" and (entry is None or exit_value is None))
            ):
                long, action = False, "exit_or_cash"
            elif not held and due and entry is True:
                long, action = True, "enter"
            if due or long != held:
                weights[ticker] = (
                    Decimal(str(s.exposure)) / Decimal(len(self.tickers)) if long else Decimal(0)
                )
            if len(self.trace) < 20000:
                self.trace.append(
                    {
                        "at": context.at.isoformat(),
                        "day": str(day),
                        "ticker": ticker,
                        "source_day": str(source_day) if source_day else None,
                        "features": used,
                        "entry": e,
                        "exit": x,
                        "holding_age_decision_sessions": age,
                        "holding_limit_exit": expired,
                        "action": action,
                        "held_quantity": str(holdings.get(ticker, 0)),
                        "cash_before": str(context.cash),
                        "target_weight": str(weights[ticker]) if ticker in weights else None,
                    }
                )
        return weights


def config(request: Request, inputs: Inputs, start: date, end: date) -> BacktestRequest:
    return BacktestRequest(
        tickers=request.tickers,
        provider=cast(Literal["synthetic", "alphavantage"], inputs.metadata["provider"]),
        start=start,
        end=end,
        source_as_of=request.source_as_of,
        capital=Decimal(str(request.capital)),
        calendar=cast(Literal["weekday", "XNYS"], inputs.calendar),
        information_policy="research_replay"
        if request.information_policy == "retrospective"
        else request.information_policy,
        costs=request.costs,
        seconds=min(request.seconds, 300),
        strategy=StrategySpec(name="equal_weight", rebalance="daily"),
    )


def snapshot(request: Request, inputs: Inputs, start: date, end: date) -> Snapshot:
    bars = tuple(
        replace(b, available=session_close(inputs.calendar, b.day) + timedelta(seconds=1))
        if request.information_policy == "retrospective"
        else b
        for b in inputs.prices.bars
        if start <= b.day <= end
    )
    return Snapshot(bars)


def evaluate(
    request: Request,
    inputs: Inputs,
    definition: Definition,
    start: date,
    end: date,
    delay: int = 0,
    audit: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    adapter = RuleStrategy(definition, inputs, request.tickers, delay)
    result = simulate(
        config(request, inputs, start, end), snapshot(request, inputs, start, end), adapter
    )
    diagnostics = {
        "signal_coverage": adapter.complete / adapter.considered if adapter.considered else 0,
        "decisions": adapter.considered,
        "trace": adapter.trace if audit else [],
        "trace_truncated": adapter.considered > 20000,
    }
    return result, diagnostics


def summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        k: v
        for k, v in result["metrics"].items()
        if k not in {"daily_returns", "monthly_returns", "drawdown", "rolling"}
    }


def fitness(
    result: dict[str, Any], diagnostics: dict[str, Any], definition: Definition, f: Fitness
) -> dict[str, Any]:
    m = result["metrics"]
    reasons = []
    if result["status"] != "completed" or m.get("status") != "computed":
        reasons.append("execution_failed")
    if len(result.get("equity", [])) < f.minimum_sessions:
        reasons.append("insufficient_observations")
    if m.get("closed_lot_count", 0) < f.minimum_closed_lots:
        reasons.append("too_few_completed_lots")
    if diagnostics["signal_coverage"] < f.minimum_signal_coverage:
        reasons.append("insufficient_data_coverage")
    if m.get("turnover", 0) > f.maximum_turnover:
        reasons.append("excessive_turnover")
    if any(
        abs(Decimal(r["reconciliation_residual"])) > Decimal("1e-8")
        for r in result.get("equity", [])
    ):
        reasons.append("invalid_accounting")
    required = [m.get(k) for k in ("sharpe", "maximum_drawdown", "turnover")]
    if any(v is None or not isfinite(v) for v in required):
        reasons.append("undefined_required_metrics")
    if reasons:
        return {"eligible": False, "score": None, "reasons": reasons, "components": {}}
    rolling = [r["sharpe"] for r in m.get("rolling", []) if r["sharpe"] is not None]
    instability = float(np.std(np.tanh(np.array(rolling) / 3))) if rolling else 1.0
    parts = {
        "risk_adjusted": tanh(m["sharpe"] / 3),
        "drawdown_penalty": f.drawdown_weight * m["maximum_drawdown"],
        "turnover_penalty": f.turnover_weight * tanh(m["turnover"] / f.turnover_scale),
        "complexity_penalty": f.complexity_weight * float(complexity(definition)["normalized"]),
        "instability_penalty": f.instability_weight * instability,
    }
    score = parts["risk_adjusted"] - sum(v for k, v in parts.items() if k != "risk_adjusted")
    return {"eligible": True, "score": score, "reasons": [], "components": parts}


def fragility(result: dict[str, Any]) -> dict[str, Any]:
    profits = [f for f in result.get("fills", []) if float(f["realized_pnl"]) > 0]
    by_asset: dict[str, float] = {}
    for f in result.get("fills", []):
        by_asset[f["ticker"]] = by_asset.get(f["ticker"], 0) + float(f["realized_pnl"])
    positive = sum(float(f["realized_pnl"]) for f in profits)
    positive_by_asset: dict[str, float] = {}
    for f in profits:
        positive_by_asset[f["ticker"]] = positive_by_asset.get(f["ticker"], 0) + float(
            f["realized_pnl"]
        )
    largest = max(positive_by_asset.values(), default=0) / positive if positive else None
    largest_two = (
        sum(sorted((float(f["realized_pnl"]) for f in profits), reverse=True)[:2]) / positive
        if positive
        else None
    )
    return {
        "realized_sale_pnl_by_asset": by_asset,
        "positive_sale_lots": len(profits),
        "largest_asset_positive_pnl_share": largest,
        "top_two_positive_lots_share": largest_two,
        "single_asset_dependence_warning": largest is not None and largest > 0.8,
        "few_trades_profit_concentration_warning": largest_two is not None and largest_two > 0.8,
        "scope": "Realized sale PNL only; excludes unrealized attribution and dividends",
        "monthly_returns": result["metrics"].get("monthly_returns", []),
    }
