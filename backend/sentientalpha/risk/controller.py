"""M4 event adapter: no ledger writes, no synthetic fills, non-bypassable order authorization."""

from datetime import datetime, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any, Literal, cast

from sentientalpha.backtesting.strategies import Context
from sentientalpha.data.calendar import session_close, session_open
from sentientalpha.risk.contracts import (
    Equity,
    EvaluationRequest,
    Order,
    Policy,
    PortfolioState,
    Price,
    ReturnObservation,
    VolumeObservation,
)
from sentientalpha.risk.governance import evaluate, merged
from sentientalpha.strategies.inputs import Inputs


class RiskController:
    def __init__(self, request: Any, inputs: Inputs, metadata: dict[str, Any], owner: Any):
        self.request, self.inputs, self.metadata, self.owner = request, inputs, metadata, owner
        policy = request.risk_policy
        assert policy is not None
        from sentientalpha.backtesting.storage import digest

        self.policy = Policy.model_validate(
            {
                **policy.model_dump(),
                "version": policy.version[:40]
                + "-m5-"
                + digest(request.constraints.model_dump(mode="json"))[:16],
                "parent_definition_hash": digest(policy.model_dump(mode="json")),
                "constraints": merged(request.constraints, policy.constraints).model_dump(),
            }
        )
        self.events: list[dict[str, Any]] = []
        self.history: list[Equity] = []
        self.timings: dict[str, float] = {}
        self.price_map = {(b.day, b.ticker): b for b in inputs.prices.bars}
        # Frozen derived returns are shared by every assessment; not copied into event records.
        self.returns = []
        by_day: dict[Any, dict[str, Any]] = {}
        for (day, ticker), cells in inputs.signals.items():
            item = cells.get("return")
            if item and item.ready is not None:
                group = by_day.setdefault(day, {"values": {}, "ready": item.ready})
                group["values"][ticker] = item.value
                group["ready"] = max(group["ready"], item.ready)
        self.returns = [
            ReturnObservation(
                day=d, available_at=v["ready"], values=v["values"], source=request.dataset_id
            )
            for d, v in sorted(by_day.items())
        ]
        self.volumes = []
        for b in inputs.prices.bars:
            ready = (
                max(b.available, b.ingested)
                if request.information_policy == "online"
                else b.available
            )
            if request.information_policy == "retrospective":
                ready = session_close(inputs.calendar, b.day) + timedelta(seconds=1)
            if b.close is not None:
                self.volumes.append(
                    VolumeObservation(
                        ticker=b.ticker,
                        day=b.day,
                        available_at=ready,
                        volume=b.volume,
                        close=float(b.close),
                        source=b.source_id,
                    )
                )
        self.last_approved: dict[str, float] | None = None
        self.corrective_needed = False

    def state(
        self,
        at: datetime,
        quantities: dict[str, Decimal],
        cash: Decimal,
        marks: dict[str, Decimal],
        kind: str,
    ) -> PortfolioState:
        prices = []
        for ticker in self.request.tickers:
            eligible = [
                b for b in self.inputs.prices.bars if b.ticker == ticker and b.day <= at.date()
            ]
            last = max(eligible, key=lambda b: b.day) if eligible else None
            if kind == "decision":
                eligible = [
                    b
                    for b in eligible
                    if (
                        session_close(self.inputs.calendar, b.day) + timedelta(seconds=1)
                        if self.request.information_policy == "retrospective"
                        else max(b.available, b.ingested)
                        if self.request.information_policy == "online"
                        else b.available
                    )
                    <= at
                ]
                last = max(eligible, key=lambda b: b.day) if eligible else None
            observed = (
                (
                    session_open(self.inputs.calendar, last.day)
                    if kind == "open" and last.day == at.date()
                    else session_close(self.inputs.calendar, last.day)
                )
                if last
                else at
            )
            available = (
                at if kind in {"open", "close"} else max(observed, last.available) if last else at
            )
            if self.request.information_policy == "retrospective" and kind == "decision" and last:
                available = session_close(self.inputs.calendar, last.day) + timedelta(seconds=1)
            asset = self.metadata.get("risk_assets", {}).get(ticker, {})
            prices.append(
                Price(
                    ticker=ticker,
                    asset_id=asset.get("id", ticker),
                    value=marks.get(ticker),
                    observed_at=min(observed, at),
                    available_at=available,
                    suspended=kind == "open"
                    and (last is None or last.day != at.date() or last.opening is None),
                    currency=asset.get("currency", "USD"),
                    source=(last.source_id if last else "missing") + ":" + kind,
                )
            )
        equity = cash + sum(v * marks.get(t, Decimal(0)) for t, v in quantities.items())
        history = list(self.history)
        if not history:
            history = [
                Equity(at=at - timedelta(microseconds=1), value=Decimal(str(self.request.capital)))
            ]
        return PortfolioState(
            portfolio_id=self.request.idempotency_key,
            at=at,
            valuation_at=at,
            cash=cash,
            equity=equity,
            quantities=quantities,
            prices=prices,
            equity_history=history,
            calendar=cast(Literal["weekday", "XNYS"], self.inputs.calendar),
            provenance=self.request.information_policy,
        )

    def assess(
        self,
        state: PortfolioState,
        phase: str,
        targets: dict[str, float] | None = None,
        orders: list[Order] | None = None,
        order_id: str | None = None,
    ) -> dict[str, Any]:
        if len(self.events) >= 25000:
            raise ValueError("Risk event budget exceeded")
        started = perf_counter()
        request = EvaluationRequest(
            state=state,
            policy=self.policy,
            targets=targets,
            orders=orders or [],
            returns=[
                r for r in self.returns if r.day <= state.at.date() and r.available_at <= state.at
            ][-1260:],
            volumes=[
                v
                for t in self.request.tickers
                for v in [
                    o
                    for o in self.volumes
                    if o.ticker == t and o.available_at <= state.at and o.day <= state.at.date()
                ][-self.policy.volume_lookback :]
            ],
            costs=self.request.costs,
            idempotency_key="risk-controller-event",
        )
        result = evaluate(request, self.timings)
        self.timings["total"] = self.timings.get("total", 0.0) + perf_counter() - started
        from sentientalpha.backtesting.storage import digest

        result["decision_id"] = digest([self.request.idempotency_key, phase, result["decision_id"]])
        if any(e["result"]["decision_id"] == result["decision_id"] for e in self.events):
            return result
        event = {
            "phase": phase,
            "at": state.at.isoformat(),
            "state_hash": digest(state.model_dump(mode="json")),
            "sequence": len(self.events),
            "order_id": order_id,
            "result": result,
        }
        self.events.append(event)
        return result

    def approve_targets(
        self,
        context: Context,
        targets: dict[str, Decimal],
        pending_orders: list[dict[str, Any]] | None = None,
    ) -> dict[str, Decimal]:
        state = self.state(
            context.at, dict(context.quantities), context.cash, dict(context.prices), "decision"
        )
        state = state.model_copy(
            update={
                "pending_orders": [
                    Order(
                        ticker=o["ticker"],
                        side=o["side"],
                        quantity=Decimal(o["requested_quantity"]),
                    )
                    for o in pending_orders or []
                    if o["status"] == "submitted"
                ]
            }
        )
        if not targets:
            if not self.corrective_needed:
                self.assess(state, "no_trade", {})
                return {}
            targets = {t: Decimal(0) for t in self.request.tickers}
        result = self.assess(state, "pre_trade", {t: float(v) for t, v in targets.items()})
        approved = result["approved_targets"] if result["executable"] else None
        self.last_approved = approved
        if self.owner.trace and self.owner.trace[-1]["decision_at"] == context.at.isoformat():
            trace = self.owner.trace[-1]
            trace["m9_risk"] = {
                k: result[k]
                for k in [
                    "decision_id",
                    "status",
                    "violations",
                    "executable",
                    "policy_id",
                    "policy_version",
                    "control",
                ]
            }
            trace["allocation"]["m5_approved_before_M9"] = trace["allocation"]["final_allocation"]
            trace["allocation"]["final_allocation"] = approved
            trace["final_action"] = (
                "risk_reduction"
                if result["status"] == "APPROVED_WITH_REDUCTION"
                else "reject"
                if not result["executable"]
                else trace["final_action"]
            )
        return {t: Decimal(str(v)) for t, v in approved.items()} if approved is not None else {}

    def before_fill(
        self,
        at: datetime,
        order: dict[str, Any],
        quantities: dict[str, Decimal],
        cash: Decimal,
        marks: dict[str, Decimal],
        pending_orders: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        state = self.state(at, quantities, cash, marks, "open")
        state = state.model_copy(
            update={
                "pending_orders": [
                    Order(
                        ticker=o["ticker"],
                        side=o["side"],
                        quantity=Decimal(o["requested_quantity"]),
                    )
                    for o in pending_orders or []
                    if o["status"] == "submitted" and o["id"] != order["id"]
                ]
            }
        )
        result = self.assess(
            state,
            "pre_fill",
            orders=[
                Order(
                    ticker=order["ticker"],
                    side=order["side"],
                    quantity=Decimal(order["requested_quantity"]),
                )
            ],
            order_id=order["id"],
        )
        delta = (
            result["approved_plan"]["deltas"].get(order["ticker"], "0")
            if result["executable"]
            else "0"
        )
        return {
            "executable": result["executable"]
            and abs(Decimal(delta)) >= self.request.costs.minimum_quantity,
            "quantity": str(abs(Decimal(delta))),
            "decision_id": result["decision_id"],
            "status": result["status"],
        }

    def observe(
        self,
        at: datetime,
        quantities: dict[str, Decimal],
        cash: Decimal,
        marks: dict[str, Decimal],
        kind: str,
        had_fills: bool = False,
    ) -> None:
        state = self.state(at, quantities, cash, marks, kind)
        if not self.history:
            self.history = list(state.equity_history)
        if self.history[-1].at < at:
            self.history.append(
                Equity(at=at, value=state.equity, kind="closing" if kind == "close" else "opening")
            )
        state = state.model_copy(update={"equity_history": list(self.history)})
        result = self.assess(state, "post_" + kind)
        self.events[-1]["violation_origin"] = (
            "data_unavailable"
            if result["current"].get("quality_violations")
            else "execution_mismatch"
            if had_fills
            else "market_movement"
        )
        self.corrective_needed = not result["executable"] or (
            result["control"]["state"] == "HALTED" and self.policy.drawdown_mode == "cash"
        )
        self.events[-1]["corrective_targets"] = (
            {t: 0.0 for t in self.request.tickers} if not result["executable"] else None
        )
        self.events[-1]["corrective_execution"] = (
            "Next permitted M4 decision/open only; no immediate ledger mutation"
        )
