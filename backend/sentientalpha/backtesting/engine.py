"""Chronological events: actions/open fills/close valuations/published decisions."""

from collections import defaultdict
from datetime import timedelta
from decimal import ROUND_FLOOR, Decimal
from time import monotonic
from typing import Any

from sentientalpha.backtesting.analytics import analytics
from sentientalpha.backtesting.contracts import BacktestError, Bar, Request, Snapshot
from sentientalpha.backtesting.execution import execute
from sentientalpha.backtesting.ledger import ZERO, Ledger
from sentientalpha.backtesting.strategies import Baseline, Context, Strategy
from sentientalpha.data.calendar import session_close, session_open, sessions_in_range
from sentientalpha.features.timing import next_open


def simulate(
    request: Request,
    snapshot: Snapshot,
    strategy: Strategy | None = None,
    risk_control: Any | None = None,
) -> dict[str, Any]:
    started = monotonic()
    days = sessions_in_range(request.calendar, request.start, request.end)
    if not days:
        raise BacktestError("No sessions in requested range", "insufficient_data")
    bars = {
        (b.day, b.ticker): b
        for b in snapshot.bars
        if b.ticker in request.tickers and request.start <= b.day <= request.end
    }
    if len(bars) > 140000 or len(bars) != len(
        [
            b
            for b in snapshot.bars
            if b.ticker in request.tickers and request.start <= b.day <= request.end
        ]
    ):
        raise BacktestError("Duplicate bars or event budget exceeded")
    session_set = set(days)
    if any(day not in session_set for day, _ in bars):
        raise BacktestError("Source calendar does not match execution calendar")
    if any(b.available < session_close(request.calendar, b.day) for b in bars.values()):
        raise BacktestError("Completed daily bar is available before its observation close")
    if any(b.revision != 1 for b in bars.values()):
        raise BacktestError(
            "Research replay refuses revised price snapshots; use original "
            "versions or online clocks",
            "revised_history",
        )
    features = {(f.day, f.ticker): f for f in snapshot.features}
    strategy = strategy or Baseline(request.strategy, request.tickers)
    ledger = Ledger(request.capital)
    events: list[tuple[Any, int, str, Any]] = []
    last_close = session_close(request.calendar, days[-1])
    first_open = session_open(request.calendar, days[0])
    bar: Bar | None
    for day in days:
        events.append((session_open(request.calendar, day), 1, "open", day))
        events.append((session_close(request.calendar, day), 2, "close", day))
        current = [bars[(day, t)] for t in request.tickers if (day, t) in bars]
        eligible = []
        for bar in current:
            if bar.close is None:
                continue
            ready = max(session_close(request.calendar, day) + timedelta(seconds=1), bar.available)
            if request.information_policy == "online":
                ready = max(ready, bar.ingested)
            if request.strategy.name == "moving_average":
                feature = features.get((day, bar.ticker))
                if feature is None or feature.value is None:
                    continue
                ready = max(
                    ready,
                    feature.online if request.information_policy == "online" else feature.ready,
                )
            eligible.append((bar, ready))
        if eligible:
            decision = max(r for _, r in eligible)
            if first_open <= decision <= last_close:
                events.append((decision, 3, "decision", (day, tuple(b for b, _ in eligible))))
    for action in request.actions:
        if action.day not in days:
            raise BacktestError("Corporate action must fall on a requested trading session")
        at = session_open(request.calendar, action.day)
        if action.known_at > at or action.known_at > request.source_as_of:
            raise BacktestError(
                "Corporate action was unavailable at effective event", "unavailable_action"
            )
        events.append((at, 0, "action", action))
    events.sort(
        key=lambda e: (
            e[0],
            e[1],
            (e[3].kind != "split", e[3].ticker) if e[2] == "action" else (False, ""),
        )
    )
    pending: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    fills: list[dict[str, Any]] = []
    equity: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    marks: dict[str, Decimal] = {}
    known_prices: dict[str, Decimal] = {}
    previous_volume: dict[str, int | None] = {}
    prior_day = {day: days[i - 1] if i else None for i, day in enumerate(days)}
    last_observation: dict[str, Any] = {}
    warnings = [
        "Raw daily retrospective opening/closing events are a research "
        "approximation, not execution-certified.",
        "Corporate-action completeness and historical universe membership are not verified.",
        "Liquidity uses prior session volume; participation is an uncalibrated "
        "capacity approximation.",
    ]
    if request.information_policy == "research_replay":
        warnings.append(
            "Research replay ignores feature materialization and ingestion clocks; "
            "provider availability is retained."
        )
    if (
        request.costs.fixed
        == request.costs.per_share
        == request.costs.percentage
        == request.costs.slippage_bps
        == 0
    ):
        warnings.append("Explicit zero-cost experiment.")
    decisions = 0
    for at, _, kind, payload in events:
        if monotonic() - started > request.seconds:
            raise BacktestError(
                "Simulation exceeded cooperative event time budget", "time_budget", 429
            )
        if kind == "action":
            action = payload
            payment = ledger.action(action.ticker, action.kind, action.value)
            if action.kind == "split":
                if action.ticker in marks:
                    marks[action.ticker] /= action.value
                if action.ticker in known_prices:
                    known_prices[action.ticker] /= action.value
                for order in pending:
                    if order["ticker"] == action.ticker:
                        order.update(status="canceled", reason="split_invalidated_pending_units")
                pending = [o for o in pending if o["status"] == "submitted"]
            actions.append(
                {
                    **action.model_dump(mode="json"),
                    "cash_payment": str(payment),
                    "at": at.isoformat(),
                }
            )
        elif kind == "open":
            day = payload
            opening_marks = marks.copy()
            for ticker in request.tickers:
                bar = bars.get((day, ticker))
                if bar and bar.opening is not None:
                    opening_marks[ticker] = bar.opening
            due = [o for o in pending if o["earliest_execution_at"] <= at.isoformat()]
            due.sort(key=lambda o: (o["side"] != "sell", o["ticker"], o["id"]))
            used: dict[str, Decimal] = defaultdict(lambda: ZERO)
            for order in due:
                bar = bars.get((day, order["ticker"]))
                prior = prior_day[day]
                previous_bar = bars.get((prior, order["ticker"])) if prior is not None else None
                eligible_volume = None
                if previous_bar is not None:
                    volume_ready = (
                        max(previous_bar.available, previous_bar.ingested)
                        if request.information_policy == "online"
                        else previous_bar.available
                    )
                    if volume_ready <= at:
                        eligible_volume = previous_volume.get(order["ticker"])
                if risk_control is not None:
                    authorization = risk_control.before_fill(
                        at,
                        order,
                        {t: p.quantity for t, p in ledger.positions.items()},
                        ledger.cash,
                        opening_marks,
                        pending_orders=pending,
                    )
                    order["risk_decision_id"] = authorization["decision_id"]
                    quantity = Decimal(authorization["quantity"])
                    if (
                        not authorization["executable"]
                        or quantity <= 0
                        or quantity > Decimal(order["requested_quantity"])
                    ):
                        order.update(status="rejected", reason="independent_risk_veto")
                        continue
                    if quantity < Decimal(order["requested_quantity"]):
                        order["risk_original_requested_quantity"] = order["requested_quantity"]
                        order["requested_quantity"] = str(quantity)
                fill = execute(
                    ledger,
                    order,
                    bar.opening if bar else None,
                    eligible_volume,
                    at,
                    request.costs,
                    opening_marks,
                    used[order["ticker"]],
                )
                if fill:
                    fills.append(fill)
                    used[order["ticker"]] += Decimal(fill["quantity"])
            pending = [o for o in pending if o["status"] == "submitted"]
            if risk_control is not None:
                risk_control.observe(
                    at,
                    {t: p.quantity for t, p in ledger.positions.items()},
                    ledger.cash,
                    opening_marks,
                    "open",
                    any(
                        o["status"] != "filled" or "risk_original_requested_quantity" in o
                        for o in due
                    ),
                )
        elif kind == "close":
            day = payload
            for ticker in request.tickers:
                bar = bars.get((day, ticker))
                held = ledger.positions.get(ticker)
                if (bar is None or bar.close is None) and held and held.quantity:
                    raise BacktestError(
                        "Held security has no current raw close; no stale valuation or "
                        "invented delisting proceeds",
                        "incomplete_valuation",
                    )
                if bar and bar.close is not None:
                    marks[ticker] = bar.close
                previous_volume[ticker] = bar.volume if bar else None
            equity.append({"day": str(day), "at": at.isoformat(), **ledger.value(marks)})
            if risk_control is not None:
                risk_control.observe(
                    at,
                    {t: p.quantity for t, p in ledger.positions.items()},
                    ledger.cash,
                    marks,
                    "close",
                )
        else:
            day, current = payload
            latest = []
            for bar in current:
                if bar.ticker not in last_observation or day >= last_observation[bar.ticker]:
                    assert bar.close is not None
                    known_prices[bar.ticker] = bar.close
                    last_observation[bar.ticker] = day
                    latest.append(bar)
            if not latest:
                continue
            context = Context(
                at,
                day,
                tuple(sorted(known_prices.items())),
                tuple(
                    (
                        b.ticker,
                        features[(day, b.ticker)].value if (day, b.ticker) in features else None,
                    )
                    for b in latest
                ),
                tuple((t, p.quantity) for t, p in sorted(ledger.positions.items())),
                ledger.cash,
            )
            targets = strategy.targets(context)
            if risk_control is not None:
                targets = risk_control.approve_targets(context, targets, pending_orders=pending)
            if (
                set(targets) - set(request.tickers)
                or any(
                    not w.is_finite() or w < 0 or w > request.costs.position_limit
                    for w in targets.values()
                )
                or sum(targets.values()) > Decimal("1.000000000000000000000000001")
            ):
                raise BacktestError("Strategy violated target weight constraints")
            if not targets:
                continue
            decisions += 1
            valuation = ledger.value(known_prices)
            capital = Decimal(valuation["equity"])
            for ticker, weight in sorted(targets.items()):
                if ticker not in known_prices:
                    raise BacktestError("Strategy targeted unavailable price")
                target = (capital * weight / known_prices[ticker]).to_integral_value(
                    rounding=ROUND_FLOOR
                )
                held = ledger.positions.get(ticker)
                difference = target - (held.quantity if held else ZERO)
                if abs(difference) < request.costs.minimum_quantity:
                    continue
                # A new target cancels earlier unexecuted instructions for the same asset.
                for old in pending:
                    if old["ticker"] == ticker:
                        old.update(status="canceled", reason="superseded_target")
                pending = [o for o in pending if o["status"] == "submitted"]
                order = {
                    "id": f"order-{len(orders) + 1:08d}",
                    "ticker": ticker,
                    "side": "buy" if difference > 0 else "sell",
                    "requested_quantity": str(abs(difference)),
                    "filled_quantity": "0",
                    "remaining_quantity": str(abs(difference)),
                    "submitted_at": at.isoformat(),
                    "signal_at": at.isoformat(),
                    "data_available_at": bars[
                        (last_observation[ticker], ticker)
                    ].available.isoformat(),
                    "input_ingested_at": bars[
                        (last_observation[ticker], ticker)
                    ].ingested.isoformat(),
                    "feature_ready_at": features[(day, ticker)].ready.isoformat()
                    if (day, ticker) in features
                    else None,
                    "observation_day": str(day),
                    "earliest_execution_at": next_open(request.calendar, at).isoformat(),
                    "status": "submitted",
                    "execution_at": None,
                    "execution_price": None,
                    "commission": "0",
                    "slippage": "0",
                    "reason": None,
                    "strategy": request.strategy.name,
                    "feature_snapshot": request.strategy.feature_dataset_id,
                }
                orders.append(order)
                pending.append(order)
    for order in pending:
        order.update(status="expired", reason="no_execution_event_within_run")
    metrics = analytics(equity, float(request.capital), fills, [float(x) for x in ledger.closed])
    return {
        "status": "completed" if decisions else "insufficient_data",
        "orders": orders,
        "fills": fills,
        "equity": equity,
        "actions": actions,
        "metrics": metrics,
        "warnings": warnings,
        "events_processed": len(events),
        "decisions": decisions,
        "closed_pnl": [float(x) for x in ledger.closed],
    }
