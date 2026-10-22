"""Atomic local event processor; existing M2/M5/M8/M9/M4 remain authoritative.

A feature snapshot can be prepared outside the economic transaction. Its creation has no
portfolio effect. Decisions, risk records, order transitions, fills and checkpoint commit together.
"""

from collections.abc import Callable
from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal
from time import perf_counter
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from sentientalpha.backtesting.analytics import analytics
from sentientalpha.backtesting.execution import execute as fill_order
from sentientalpha.backtesting.ledger import Ledger
from sentientalpha.backtesting.storage import build_id, digest
from sentientalpha.backtesting.strategies import Context
from sentientalpha.committee.engine import CommitteeStrategy
from sentientalpha.committee.requests import Request as CommitteeRequest
from sentientalpha.committee.sources import load_sources
from sentientalpha.committee.storage import equivalent
from sentientalpha.data.calendar import session_close, sessions_in_range
from sentientalpha.database.backtest_models import BacktestArtifact, BacktestRun
from sentientalpha.database.base import new_id, now
from sentientalpha.database.committee_models import CommitteeDecision, CommitteeRun
from sentientalpha.database.models import Asset, MarketPrice
from sentientalpha.database.paper_models import (
    PaperEvent,
    PaperFillReceipt,
    PaperOrder,
    PaperSession,
)
from sentientalpha.database.risk_models import RiskAssessment
from sentientalpha.database.session import serialize_writer
from sentientalpha.features.contracts import FeatureError, FeatureSpec, GenerationRequest
from sentientalpha.features.storage import generate
from sentientalpha.optimization.estimation import OptimizationError
from sentientalpha.paper.contracts import Advance, Command, Create
from sentientalpha.risk.contracts import (
    Equity,
    EvaluationRequest,
    Order,
    PortfolioState,
    Price,
    ReturnObservation,
    VolumeObservation,
)
from sentientalpha.risk.governance import evaluate
from sentientalpha.risk.storage import write as write_risk
from sentientalpha.strategies.inputs import freeze, thaw

ZERO = Decimal(0)
PENDING = {"QUEUED", "APPROVED", "PENDING_RISK", "CREATED"}


def error(message: str, code: str = "paper_conflict", status: int = 409) -> OptimizationError:
    return OptimizationError(message, code, status)


def get(s: Session, id: str) -> PaperSession:
    row = s.get(PaperSession, id)
    if row is None:
        raise error("Paper session not found", "not_found", 404)
    if (
        row.mode != row.configuration.get("mode")
        or digest(row.configuration) != row.configuration_hash
    ):
        raise error("Immutable paper configuration differs", "paper_integrity")
    return row


def events(s: Session, id: str) -> list[PaperEvent]:
    return list(
        s.scalars(
            select(PaperEvent).where(PaperEvent.session_id == id).order_by(PaperEvent.sequence)
        )
    )


def append(
    s: Session,
    row: PaperSession,
    key: str,
    kind: str,
    payload: dict[str, Any],
    day: date | None = None,
) -> PaperEvent:
    payload = {**payload, "orders_hash": digest([a.payload for a in artifacts(s, row, "orders")])}
    last = s.scalar(
        select(PaperEvent)
        .where(PaperEvent.session_id == row.id)
        .order_by(PaperEvent.sequence.desc())
        .limit(1)
    )
    sequence = last.sequence + 1 if last else 0
    previous = last.hash if last else row.configuration_hash
    processed = now()
    body = {
        "key": key,
        "kind": kind,
        "day": str(day) if day else None,
        "processed_at": processed.isoformat(),
        "payload": payload,
        "sequence": sequence,
    }
    item = PaperEvent(
        session_id=row.id,
        key=key,
        sequence=sequence,
        kind=kind,
        market_day=day,
        processed_at=processed,
        payload=payload,
        previous_hash=previous,
        hash=digest([previous, body]),
    )
    s.add(item)
    s.flush()
    return item


def existing(s: Session, id: str, key: str, request: Any) -> PaperEvent | None:
    event = s.scalar(select(PaperEvent).where(PaperEvent.session_id == id, PaperEvent.key == key))
    if event and event.payload.get("request_hash") != digest(request):
        raise error("Command key reused with different input", "idempotency_conflict")
    return event


def artifacts(s: Session, row: PaperSession, kind: str) -> list[BacktestArtifact]:
    return list(
        s.scalars(
            select(BacktestArtifact)
            .where(BacktestArtifact.run_id == row.ledger_id, BacktestArtifact.kind == kind)
            .order_by(BacktestArtifact.sequence)
        )
    )


def artifact(s: Session, row: PaperSession, kind: str, payload: dict[str, Any]) -> BacktestArtifact:
    n = s.scalar(
        select(func.max(BacktestArtifact.sequence)).where(
            BacktestArtifact.run_id == row.ledger_id, BacktestArtifact.kind == kind
        )
    )
    a = BacktestArtifact(
        run_id=row.ledger_id, kind=kind, sequence=0 if n is None else n + 1, payload=payload
    )
    s.add(a)
    s.flush()
    return a


def restore_ledger(s: Session, row: PaperSession) -> Ledger:
    ledger = Ledger(Decimal(row.configuration["capital"]))
    for a in artifacts(s, row, "fills"):
        f = a.payload
        receipt = s.get(PaperFillReceipt, f["order_id"])
        if receipt is None or receipt.artifact_id != a.id:
            raise error("Fill receipt is inconsistent", "paper_integrity")
        ledger.fill(
            f["ticker"],
            f["side"],
            Decimal(f["quantity"]),
            Decimal(f["price"]),
            Decimal(f["commission"]),
            Decimal(f["slippage"]),
        )
    return ledger


def create(sessions: sessionmaker[Session], q: Create) -> PaperSession:
    config = q.model_dump(mode="json")
    with sessions() as s:
        serialize_writer(s, "paper:create")
        old = s.scalar(select(PaperSession).where(PaperSession.key == q.key))
        if old:
            if old.configuration_hash != digest(config):
                raise error("Session key has a different configuration", "idempotency_conflict")
            return old
        if q.mode == "historical_replay" and s.get(BacktestRun, q.historical_run_id) is None:
            raise error("Historical research run not found", "not_found", 404)
        at = now()
        if q.history_start >= at.date() or (at.date() - q.history_start).days > 3660:
            raise error("History must be prior and within ten years", "invalid_request", 422)
        effective = (
            session_close("weekday", q.simulation_start) + timedelta(seconds=2)
            if q.simulation_start
            else at
        )
        if max(q.committee_policy.effective_at, q.risk_policy.effective_at) > effective:
            raise error("Future policy is not available", "invalid_request", 422)
        carrier = BacktestRun(
            id=new_id(),
            status="completed",
            manifest={
                "version": "11.0.0",
                "scope": "paper_operational_ledger",
                "mode": q.mode,
                "simulation_only": True,
            },
            snapshot={},
            metrics={},
            diagnostics={"not_a_historical_backtest": True},
        )
        s.add(carrier)
        s.flush()
        row = PaperSession(
            id=new_id(),
            key=q.key,
            mode=q.mode,
            status="CREATED",
            created_at=at,
            updated_at=at,
            configuration=config,
            configuration_hash=digest(config),
            ledger_id=carrier.id,
        )
        s.add(row)
        s.flush()
        carrier.manifest = {**carrier.manifest, "paper_session": row.id}
        append(
            s,
            row,
            "create-" + q.key[:72],
            "created",
            {
                "request_hash": digest(config),
                "mode": q.mode,
                "build_id": build_id(),
                "cash": str(q.capital),
            },
        )
        s.commit()
        return row


TRANSITIONS = {
    "ready": ({"CREATED"}, "READY"),
    "start": ({"READY"}, "RUNNING"),
    "pause": ({"RUNNING"}, "PAUSED"),
    "resume": ({"PAUSED"}, "RUNNING"),
    "stop": ({"CREATED", "READY", "RUNNING", "PAUSED", "FAILED"}, "STOPPED"),
}


def transition(sessions: sessionmaker[Session], id: str, action: str, q: Command) -> PaperSession:
    request = {"action": action, **q.model_dump(mode="json")}
    with sessions() as s:
        serialize_writer(s, "paper:" + id)
        row = get(s, id)
        if existing(s, id, q.key, request):
            return row
        allowed, target = TRANSITIONS[action]
        if row.status not in allowed:
            raise error("Invalid paper lifecycle transition")
        if action == "start" and row.mode == "historical_replay":
            raise error(
                "Historical research uses the existing M4 replay API; "
                "it cannot run as forward paper"
            )
        if action in {"ready", "resume"}:
            replay(s, row)
            if (
                row.warning
                and row.warning.startswith("missed_processing_window")
                and any(a.payload["status"] in PENDING for a in artifacts(s, row, "orders"))
            ):
                raise error("Cancel outstanding orders before resuming a missed window")
        skipped = None
        if (
            action == "resume"
            and row.warning
            and row.warning.startswith("missed_processing_window")
        ):
            available = market(s, Create.model_validate(row.configuration), now())
            skipped = str(max(available)) if available else None
            if available:
                row.last_day = max(available)
        row.status, row.updated_at = target, now()
        if action == "start":
            row.started_at = now()
        if action == "stop":
            for a in artifacts(s, row, "orders"):
                if a.payload["status"] in PENDING:
                    a.payload = {
                        **a.payload,
                        "status": "CANCELLED",
                        "cancellation_reason": "session_stopped",
                        "transitions": a.payload["transitions"] + ["CANCELLED"],
                    }
        append(
            s,
            row,
            q.key,
            action,
            {
                "request_hash": digest(request),
                "status": target,
                "outage_catchup_through": skipped,
                "no_backdated_economic_effect": True,
            },
        )
        s.commit()
        return row


def present(s: Session, row: PaperSession) -> dict[str, Any]:
    snapshots = artifacts(s, row, "equity")
    ledger = restore_ledger(s, row)
    portfolio = snapshots[-1].payload if snapshots else ledger.value({})
    orders = [a.payload for a in artifacts(s, row, "orders")]
    last_decision = s.scalar(
        select(CommitteeDecision)
        .join(CommitteeRun, CommitteeRun.id == CommitteeDecision.run_id)
        .where(CommitteeRun.backtest_id == row.ledger_id)
        .order_by(CommitteeDecision.decision_at.desc())
        .limit(1)
    )
    latest = None
    if last_decision:
        approval = s.scalar(
            select(RiskAssessment)
            .where(
                RiskAssessment.backtest_id == row.ledger_id,
                RiskAssessment.phase == "paper_pre_trade",
                RiskAssessment.at == last_decision.decision_at,
            )
            .limit(1)
        )
        latest = {
            "id": last_decision.id,
            "committee_id": last_decision.run_id,
            "at": last_decision.decision_at.isoformat(),
            "payload": last_decision.payload,
            "m9": approval.payload if approval else None,
        }
    provider_event = s.scalar(
        select(PaperEvent)
        .where(PaperEvent.session_id == row.id, PaperEvent.kind == "provider_update")
        .order_by(PaperEvent.sequence.desc())
        .limit(1)
    )
    return {
        "id": row.id,
        "latest_decision": latest,
        "last_provider_update": provider_event.payload.get("result") if provider_event else None,
        "mode": row.mode,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "last_processed_observation": str(row.last_day) if row.last_day else None,
        "last_processing_at": row.last_processing_at.isoformat()
        if row.last_processing_at
        else None,
        "warning": row.warning,
        "configuration": row.configuration,
        "ledger_id": row.ledger_id,
        "portfolio": portfolio,
        "pending_orders": sum(o["status"] in PENDING for o in orders),
        "reserved_cash": "0",
        "reservation_policy": (
            "One outstanding allocation batch; no new target batch until all earlier "
            "orders terminate. M9 evaluates pending commitments; M4 cash is authoritative."
        ),
        "valuation_stale": not snapshots
        or row.status != "RUNNING"
        or (now() - datetime.fromisoformat(snapshots[-1].payload["processed_at"])).total_seconds()
        > row.configuration["stale_hours"] * 3600,
        "simulation_only": True,
        "synthetic": row.mode == "synthetic_demo",
        "continuous_availability": False,
    }


def market(s: Session, q: Create, cutoff: datetime) -> dict[date, dict[str, MarketPrice]]:
    rows = s.execute(
        select(MarketPrice, Asset.ticker)
        .join(Asset, Asset.id == MarketPrice.asset_id)
        .where(
            Asset.ticker.in_(q.tickers),
            MarketPrice.provider == q.provider,
            MarketPrice.session_date >= q.history_start,
            MarketPrice.available_at <= cutoff,
            MarketPrice.ingested_at <= cutoff,
        )
        .order_by(MarketPrice.session_date, MarketPrice.revision_no)
        .limit(140001)
    ).all()
    if len(rows) > 140000:
        raise error("Paper source budget exceeded", "resource_limit", 429)
    result: dict[date, dict[str, MarketPrice]] = {}
    for bar, ticker in rows:
        result.setdefault(bar.session_date, {})[ticker] = bar
    return result


def prepare(
    sessions: sessionmaker[Session], id: str, through: date | None
) -> tuple[date | None, str | None]:
    with sessions() as s:
        row = get(s, id)
        if row.status != "RUNNING":
            return None, None
        q = Create.model_validate(row.configuration)
        if row.mode != "synthetic_demo" and through is not None:
            raise error("Forward clock cannot be supplied by the caller", "invalid_request", 422)
        data = market(s, q, now())
        days = sorted(
            d
            for d in data
            if (row.last_day is None or d > row.last_day)
            and (not q.simulation_start or d >= q.simulation_start)
            and (through is None or d <= through)
        )
        if not days:
            return None, None
        day = days[0] if row.mode == "synthetic_demo" else days[-1]
    ds = generate(
        sessions,
        GenerationRequest(
            tickers=q.tickers,
            provider=q.provider,
            start=q.history_start,
            end=day,
            features=[FeatureSpec(name="return")],
        ),
    )
    return day, ds.dataset.id


def risk_request(
    q: Create,
    row: PaperSession,
    ledger: Ledger,
    at: datetime,
    day: date,
    data: dict[date, dict[str, MarketPrice]],
    marks: dict[str, Decimal],
    history: list[dict[str, Any]],
    *,
    targets: dict[str, float] | None = None,
    orders: list[Order] | None = None,
    pending: list[Order] | None = None,
) -> EvaluationRequest:
    values = ledger.value(marks)
    prices = [
        Price(
            ticker=t,
            asset_id=data[day][t].asset_id,
            value=marks[t],
            observed_at=data[day][t].session_close_at or at,
            available_at=min(at, data[day][t].available_at),
            source=data[day][t].id,
        )
        for t in q.tickers
    ]
    history_values = [
        Equity(at=datetime.fromisoformat(v["at"]), value=Decimal(v["equity"]), kind="closing")
        for v in history[-2519:]
        if datetime.fromisoformat(v["at"]) < at
    ]
    if not history_values:
        history_values = [Equity(at=at - timedelta(microseconds=1), value=q.capital)]
    state = PortfolioState(
        portfolio_id=row.id,
        at=at,
        valuation_at=at,
        cash=ledger.cash,
        equity=Decimal(values["equity"]),
        quantities={t: p.quantity for t, p in ledger.positions.items()},
        prices=prices,
        pending_orders=pending or [],
        equity_history=history_values,
        calendar="weekday" if q.mode == "synthetic_demo" else "XNYS",
        provenance="synthetic_fixture" if q.mode == "synthetic_demo" else "online",
    )
    returns: list[ReturnObservation] = []
    volumes: list[VolumeObservation] = []
    previous: dict[str, Decimal] = {}
    for d, bars in sorted(data.items()):
        if d > day:
            continue
        eligible = {
            t: b
            for t, b in bars.items()
            if b.session_close_at
            and b.session_close_at <= at
            and (q.mode == "synthetic_demo" or max(b.available_at, b.ingested_at) <= at)
        }
        if set(eligible) != set(q.tickers):
            previous = {}
            continue
        ready = (
            max(b.available_at for b in eligible.values())
            if q.mode == "synthetic_demo"
            else max(max(b.available_at, b.ingested_at) for b in eligible.values())
        )
        if ready > at:
            continue
        if previous:
            returns.append(
                ReturnObservation(
                    day=d,
                    available_at=ready,
                    values={t: float(b.close / previous[t] - 1) for t, b in eligible.items()},
                    source=digest([b.id for b in eligible.values()]),
                )
            )
        # Today's realized full-session volume cannot constrain a fill at today's close.
        if d < day:
            volumes.extend(
                VolumeObservation(
                    ticker=t,
                    day=d,
                    available_at=ready,
                    volume=b.volume,
                    close=float(b.close),
                    source=b.id,
                )
                for t, b in eligible.items()
            )
        previous = {t: b.close for t, b in eligible.items()}
    return EvaluationRequest(
        state=state,
        policy=q.risk_policy,
        targets=targets,
        orders=orders or [],
        returns=returns[-1260:],
        volumes=[
            v
            for t in q.tickers
            for v in [x for x in volumes if x.ticker == t][-q.risk_policy.volume_lookback :]
        ],
        costs=q.costs,
        idempotency_key="paper-"
        + digest(
            [row.id, at.isoformat(), targets, [o.model_dump(mode="json") for o in orders or []]]
        )[:64],
    )


def assess(
    s: Session,
    row: PaperSession,
    request: EvaluationRequest,
    phase: str,
    saved: list[dict[str, Any]],
) -> dict[str, Any]:
    risk_started = perf_counter()
    result = evaluate(request)
    write_risk(
        s,
        result,
        request.policy,
        request.model_dump(mode="json"),
        phase,
        request.idempotency_key,
        backtest_id=row.ledger_id,
    )
    saved.append(
        {
            "phase": phase,
            "request": request.model_dump(mode="json"),
            "result": result,
            "elapsed_seconds": perf_counter() - risk_started,
        }
    )
    return result


def process_one(
    sessions: sessionmaker[Session],
    id: str,
    day: date,
    ds: str,
    fault: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    started = perf_counter()
    fault = fault or (lambda _: None)
    with sessions() as s:
        serialize_writer(s, "paper:" + id)
        row = get(s, id)
        if row.status != "RUNNING" or (row.last_day and day <= row.last_day):
            return {"status": "already_processed_or_inactive"}
        q = Create.model_validate(row.configuration)
        actual = now()
        data = market(s, q, actual)
        bars = data.get(day, {})

        def safety(reason: str) -> dict[str, Any]:
            row.status, row.warning, row.updated_at = "PAUSED", reason, actual
            append(s, row, "safety-" + new_id(), "safety_pause", {"reason": reason})
            s.commit()
            return {"status": "PAUSED", "reason": reason}

        if len(artifacts(s, row, "equity")) >= 2500:
            return safety("session_event_budget_exhausted; export_and_create_new_session")
        if set(bars) != set(q.tickers):
            return safety(
                "missing_universe_observation; holdings unchanged; stale valuation retained"
            )
        if any(
            b.calendar != ("weekday" if q.mode == "synthetic_demo" else "XNYS")
            or b.session_close_at is None
            or b.quality_flags
            or b.revision_no != 1
            for b in bars.values()
        ):
            return safety("revision_quality_or_corporate_action_review_required")
        if any(b.is_synthetic != (q.mode == "synthetic_demo") for b in bars.values()):
            return safety("provider_provenance_mismatch")
        closed = max(cast(datetime, b.session_close_at) for b in bars.values())
        received = max(max(b.available_at, b.ingested_at) for b in bars.values())
        at = (
            max(b.available_at for b in bars.values()) + timedelta(seconds=2)
            if q.mode == "synthetic_demo"
            else actual
        )
        if q.mode != "synthetic_demo":
            if closed > actual:
                return safety("incomplete_session")
            if (
                row.started_at is None
                or closed <= row.started_at
                or (received - closed).total_seconds() > q.maximum_reception_delay_hours * 3600
            ):
                append(
                    s,
                    row,
                    "catchup-" + str(day),
                    "historical_catch_up",
                    {
                        "source_ids": [b.id for b in bars.values()],
                        "no_economic_effect": True,
                        "reason": "bar_closed_before_start_or_delayed_reception",
                    },
                    day,
                )
                row.last_day, row.last_processing_at = day, actual
                s.commit()
                return {"status": "historical_catch_up", "no_economic_effect": True}
            if (actual - closed).total_seconds() > q.stale_hours * 3600:
                return safety("stale_market_data; catch_up_is_not_forward_trading")
        restore_started = perf_counter()
        ledger = restore_ledger(s, row)
        restore_seconds = perf_counter() - restore_started
        marks = {t: b.close for t, b in bars.items()}
        snapshots = [a.payload for a in artifacts(s, row, "equity")]
        if snapshots:
            last_day = row.last_day or date.fromisoformat(snapshots[-1]["day"])
            missing = sessions_in_range(
                "weekday" if q.mode == "synthetic_demo" else "XNYS", last_day, day
            )[1:-1]
            if missing:
                return safety(
                    "missed_processing_window; no_backdated_fills; cancel_pending_before_resume"
                )
        risk_records: list[dict[str, Any]] = []
        operations: list[dict[str, Any]] = []
        committee_seconds = 0.0
        order_seconds = 0.0
        open_orders = [a for a in artifacts(s, row, "orders") if a.payload["status"] in PENDING]
        for a in sorted(
            open_orders,
            key=lambda a: (a.payload["side"] != "sell", a.payload["ticker"], a.payload["id"]),
        ):
            if perf_counter() - started > 45:
                raise error("Atomic event time budget exceeded", "time_budget", 429)
            o = deepcopy(a.payload)
            submitted = datetime.fromisoformat(o["submitted_at"])
            if closed <= submitted:
                continue
            if (at - submitted).total_seconds() > q.stale_hours * 3600:
                o.update(status="EXPIRED", reason="missed_execution_window")
                o["transitions"].append("EXPIRED")
                a.payload = o
                continue
            pending = [
                Order(
                    ticker=x.payload["ticker"],
                    side=x.payload["side"],
                    quantity=Decimal(x.payload["remaining_quantity"]),
                )
                for x in open_orders
                if x.id != a.id and x.payload["status"] in PENDING
            ]
            request = risk_request(
                q,
                row,
                ledger,
                at,
                day,
                data,
                marks,
                snapshots,
                orders=[
                    Order(
                        ticker=o["ticker"],
                        side=o["side"],
                        quantity=Decimal(o["requested_quantity"]),
                    )
                ],
                pending=pending,
            )
            risk = assess(s, row, request, "paper_pre_fill", risk_records)
            o["fill_risk_id"] = risk["decision_id"]
            delta = (
                abs(Decimal(risk["approved_plan"]["deltas"].get(o["ticker"], "0")))
                if risk["executable"]
                else ZERO
            )
            if (
                not risk["executable"]
                or delta < q.costs.minimum_quantity
                or delta > Decimal(o["requested_quantity"])
            ):
                o.update(status="REJECTED", reason="independent_fill_risk_veto")
                o["transitions"].append("REJECTED")
                a.payload = o
                continue
            approved = {**o, "requested_quantity": str(delta), "status": "submitted"}
            prior = [
                b[o["ticker"]]
                for d, b in sorted(data.items())
                if d < day and o["ticker"] in b and b[o["ticker"]].available_at <= at
            ]
            volume = prior[-1].volume if prior else None
            execution_input = {
                "order": deepcopy(approved),
                "price": str(marks[o["ticker"]]),
                "previous_volume": volume,
                "at": at.isoformat(),
                "marks": {t: str(v) for t, v in marks.items()},
            }
            fill_started = perf_counter()
            fill = fill_order(ledger, approved, marks[o["ticker"]], volume, at, q.costs, marks)
            if fill:
                fill["price_convention"] = "next_observed_close_ioc"
                fill["source_id"] = bars[o["ticker"]].id
                f = artifact(s, row, "fills", fill)
                s.add(PaperFillReceipt(order_id=o["id"], artifact_id=f.id))
                fault("after_fill")
                o.update(
                    {k: v for k, v in approved.items() if k not in {"requested_quantity", "status"}}
                )
                o["approved_quantity"] = str(delta)
                o["remaining_quantity"] = str(
                    Decimal(o["requested_quantity"]) - Decimal(fill["quantity"])
                )
                o["status"] = (
                    "FILLED" if Decimal(o["remaining_quantity"]) == 0 else "PARTIALLY_FILLED"
                )
                o["transitions"].append(o["status"])
                if o["status"] == "PARTIALLY_FILLED":
                    o["status"] = "CANCELLED"
                    o["transitions"].append("CANCELLED")
                    o["cancellation_reason"] = "ioc_unfilled_remainder"
            else:
                o.update(status="REJECTED", reason=approved.get("reason"))
                o["transitions"].append("REJECTED")
            operations.append(
                {
                    "input": execution_input,
                    "fill": fill,
                    "elapsed_seconds": perf_counter() - fill_started,
                }
            )
            a.payload = o
        ledger.value(marks)
        fault("after_execution")
        # An outstanding allocation batch blocks another; no invented cash reservation ledger.
        outstanding = [a for a in artifacts(s, row, "orders") if a.payload["status"] in PENDING]
        decision_record = None
        insufficient_pre_trade = False
        if not outstanding:
            cq = CommitteeRequest(
                dataset_id=ds,
                tickers=q.tickers,
                history_start=q.history_start,
                start=day,
                end=day,
                source_as_of=actual,
                information_policy="research_replay" if q.mode == "synthetic_demo" else "online",
                policy=q.committee_policy,
                estimator=q.estimator,
                constraints=q.risk_policy.constraints,
                costs=q.costs,
                capital=float(q.capital),
                model_id=q.model_id,
                sentiment_dataset_id=q.sentiment_dataset_id,
                sentiment_column=q.sentiment_column,
                idempotency_key="paper-" + digest([id, str(day)])[:64],
            )
            inputs, meta = load_sources(s, cq)
            if q.strategy_id:
                from sentientalpha.database.strategy_models import DiscoveryRun, StrategyCandidate
                from sentientalpha.strategies.contracts import Definition
                from sentientalpha.strategies.grammar import requirements

                candidate = s.get(StrategyCandidate, q.strategy_id)
                parent = s.get(DiscoveryRun, candidate.discovery_id) if candidate else None
                if parent is None or candidate is None:
                    raise error("Configured locked strategy not found", "not_found", 404)
                if requirements(Definition.model_validate(candidate.payload["definition"])) - {
                    "return",
                    "close",
                }:
                    raise error(
                        "Paper adapter supports return/close locked rules only",
                        "unsupported_strategy",
                        422,
                    )
                source_request = cq.model_copy(
                    update={
                        "dataset_id": parent.manifest["configuration"]["dataset_id"],
                        "strategy_id": q.strategy_id,
                    }
                )
                _, selected_meta = load_sources(s, source_request)
                meta["strategy"] = selected_meta["strategy"]
            adapter = CommitteeStrategy(cq, inputs, meta)
            context = Context(
                at,
                day,
                tuple(sorted(marks.items())),
                (),
                tuple((t, p.quantity) for t, p in sorted(ledger.positions.items())),
                ledger.cash,
            )
            committee_started = perf_counter()
            targets = adapter.targets(context)
            committee_seconds = perf_counter() - committee_started
            record = adapter.trace[0]
            cr = CommitteeRun(
                id=new_id(),
                idempotency_key=cq.idempotency_key,
                status="analyzed",
                backtest_id=row.ledger_id,
                manifest={
                    "configuration": cq.model_dump(mode="json"),
                    "scope": "paper_event_decision",
                    "mode": q.mode,
                    "build_id": build_id(),
                    "paper_session": id,
                    "simulation_only": True,
                },
                inputs={},
                result={"decision_count": 1, "orders": 0, "fills": 0},
            )
            s.add(cr)
            s.flush()
            decision = CommitteeDecision(
                id=new_id(), run_id=cr.id, sequence=0, decision_at=at, payload=record
            )
            s.add(decision)
            s.flush()
            fault("after_decision")
            decision_record = {
                "request": cq.model_dump(mode="json"),
                "inputs": freeze(inputs),
                "metadata": meta,
                "context_at": at.isoformat(),
                "record": record,
                "committee_id": cr.id,
                "decision_id": decision.id,
            }
            risk = assess(
                s,
                row,
                risk_request(
                    q,
                    row,
                    ledger,
                    at,
                    day,
                    data,
                    marks,
                    snapshots,
                    targets={t: float(v) for t, v in targets.items()} if targets else {},
                ),
                "paper_pre_trade",
                risk_records,
            )
            insufficient_pre_trade = risk["status"] == "INSUFFICIENT_RISK_DATA"
            fault("after_risk")
            approved = risk["approved_plan"]["deltas"] if risk["executable"] else {}
            proposed = risk.get("proposal") or {}
            deltas = approved or proposed.get("deltas", {})
            orders_started = perf_counter()
            for t, delta_value in sorted(deltas.items()):
                delta = Decimal(str(delta_value))
                if abs(delta) < q.costs.minimum_quantity:
                    continue
                oid = digest([row.id, decision.id, t])
                o = {
                    "id": oid,
                    "session_id": id,
                    "committee_id": cr.id,
                    "decision_id": decision.id,
                    "ticker": t,
                    "side": "buy" if delta > 0 else "sell",
                    "requested_quantity": str(abs(delta)),
                    "approved_quantity": str(abs(delta)) if risk["executable"] else "0",
                    "filled_quantity": "0",
                    "remaining_quantity": str(abs(delta)),
                    "submitted_at": at.isoformat(),
                    "processed_at": actual.isoformat(),
                    "earliest_execution_at": (at + timedelta(microseconds=1)).isoformat(),
                    "risk_decision_id": risk["decision_id"],
                    "status": "QUEUED" if risk["executable"] else "REJECTED",
                    "reason": None if risk["executable"] else "independent_pre_trade_risk_veto",
                    "transitions": ["CREATED", "PENDING_RISK"]
                    + (["APPROVED", "QUEUED"] if risk["executable"] else ["REJECTED"]),
                }
                a = artifact(s, row, "orders", o)
                s.add(PaperOrder(id=oid, session_id=id, artifact_id=a.id, decision_id=decision.id))
            order_seconds = perf_counter() - orders_started
        post = assess(
            s,
            row,
            risk_request(
                q, row, ledger, at + timedelta(microseconds=1), day, data, marks, snapshots
            ),
            "paper_post_trade",
            risk_records,
        )
        ledger_started = perf_counter()
        valuation = {
            **ledger.value(marks),
            "day": str(day),
            "at": at.isoformat(),
            "processed_at": actual.isoformat(),
            "marks": {t: str(v) for t, v in marks.items()},
            "mode": q.mode,
            "source_ids": {t: b.id for t, b in bars.items()},
            "stale": False,
            "market_observed_at": closed.isoformat(),
        }
        artifact(s, row, "equity", valuation)
        fault("before_checkpoint")
        payload = {
            "mode": q.mode,
            "actual_processing_at": actual.isoformat(),
            "decision_clock": at.isoformat(),
            "source_ids": {t: b.id for t, b in bars.items()},
            "source_hash": digest({t: [b.id, b.checksum] for t, b in bars.items()}),
            "operations": operations,
            "decision": decision_record,
            "risks": risk_records,
            "valuation": valuation,
            "build_id": build_id(),
            "timings": {
                "ledger_restore": restore_seconds,
                "committee_m5": committee_seconds,
                "order_generation": order_seconds,
                "risk_evaluation_and_persistence": sum(r["elapsed_seconds"] for r in risk_records),
                "fill_execution": sum(o["elapsed_seconds"] for o in operations),
                "ledger_valuation": perf_counter() - ledger_started,
            },
            "elapsed_seconds": perf_counter() - started,
        }
        append(s, row, "market-" + str(day), "market", payload, day)
        row.last_day, row.last_processing_at, row.updated_at = day, actual, actual
        row.warning = None
        if insufficient_pre_trade:
            row.status, row.warning = (
                "PAUSED",
                "insufficient_pre_trade_risk_data; no unapproved order can fill",
            )
        if not post["executable"]:
            row.status, row.warning = (
                "PAUSED",
                "post_trade_risk_requires_review; no direct position mutation",
            )
        s.commit()
        fault("after_commit")
        return {
            "status": row.status,
            "day": str(day),
            "elapsed_seconds": perf_counter() - started,
            "fills": len([o for o in operations if o["fill"]]),
            "committee_id": decision_record["committee_id"] if decision_record else None,
            "risk_status": post["status"],
        }


def advance(
    sessions: sessionmaker[Session],
    id: str,
    q: Advance,
    fault: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    request = q.model_dump(mode="json")
    done_key = "done-" + digest(q.key)[:64]
    with sessions() as s:
        serialize_writer(s, "paper:" + id)
        row = get(s, id)
        done = existing(s, id, done_key, request)
        if done:
            return done.payload["response"]
        claim = existing(s, id, q.key, request)
        if not claim:
            if row.status != "RUNNING":
                raise error("Only RUNNING paper sessions can advance")
            if row.mode != "synthetic_demo" and q.through is not None:
                raise error(
                    "Forward clock cannot be supplied by the caller", "invalid_request", 422
                )
            config = Create.model_validate(row.configuration)
            data = market(s, config, now())
            days = sorted(
                d
                for d in data
                if (row.last_day is None or d > row.last_day)
                and (config.simulation_start is None or d >= config.simulation_start)
                and (q.through is None or d <= q.through)
            )
            days = days[: q.maximum_events] if row.mode == "synthetic_demo" else days[-1:]
            if not days and row.mode == "forward_paper":
                row.warning = "awaiting_new_eligible_observation; no economic effect"
                last_observation = row.last_processing_at or row.started_at
                if (
                    last_observation
                    and (now() - last_observation).total_seconds() > config.stale_hours * 3600
                ):
                    row.status = "PAUSED"
                    row.warning = "stale_or_missing_essential_market_data"
            claim = append(
                s,
                row,
                q.key,
                "advance_started",
                {
                    "request_hash": digest(request),
                    "planned_days": [str(d) for d in days],
                    "retry_policy": "Resume frozen days only; a retry cannot select newer days.",
                },
            )
            s.commit()
        planned = list(claim.payload["planned_days"])
    for day_text in planned:
        day = date.fromisoformat(day_text)
        with sessions() as s:
            row = get(s, id)
            if row.status != "RUNNING":
                break
            if row.last_day and row.last_day >= day:
                continue
            config = Create.model_validate(row.configuration)
        try:
            ds = generate(
                sessions,
                GenerationRequest(
                    tickers=config.tickers,
                    provider=config.provider,
                    start=config.history_start,
                    end=day,
                    features=[FeatureSpec(name="return")],
                ),
            )
            result = process_one(sessions, id, day, ds.dataset.id, fault)
            if result["status"] not in {"RUNNING", "already_processed_or_inactive"}:
                break
        except (ValueError, OptimizationError, FeatureError) as exc:
            if fault is not None:
                raise
            with sessions() as s:
                serialize_writer(s, "paper:" + id)
                row = get(s, id)
                row.status = "FAILED" if getattr(exc, "code", "") == "paper_integrity" else "PAUSED"
                row.warning = "processing_integrity_or_source_failure; reconcile before resume"
                append(
                    s,
                    row,
                    "processing-error-" + new_id(),
                    "processing_failure",
                    {"reason": row.warning, "code": getattr(exc, "code", "invalid_source")},
                )
                s.commit()
            break
    with sessions() as s:
        serialize_writer(s, "paper:" + id)
        row = get(s, id)
        old = existing(s, id, done_key, request)
        if old:
            return old.payload["response"]
        completed = [
            e for e in events(s, id) if e.market_day is not None and str(e.market_day) in planned
        ]
        response = {
            "session_id": id,
            "processed": [
                {
                    "day": str(e.market_day),
                    "kind": e.kind,
                    "event_id": e.id,
                    "fills": sum(bool(o["fill"]) for o in e.payload.get("operations", [])),
                }
                for e in completed
            ],
            "status": row.status,
            "no_new_observations": not planned,
        }
        append(s, row, done_key, "advance", {"request_hash": digest(request), "response": response})
        s.commit()
        return response


def cancel(sessions: sessionmaker[Session], id: str, order_id: str, q: Command) -> dict[str, Any]:
    request = {"order_id": order_id, **q.model_dump(mode="json")}
    with sessions() as s:
        serialize_writer(s, "paper:" + id)
        row = get(s, id)
        if existing(s, id, q.key, request):
            return {"cancelled": order_id}
        o = s.get(PaperOrder, order_id)
        if o is None or o.session_id != id:
            raise error("Paper order not found", "not_found", 404)
        a = s.get(BacktestArtifact, o.artifact_id)
        assert a is not None
        if a.payload["status"] not in PENDING:
            raise error("Only outstanding unfilled orders can be cancelled")
        a.payload = {
            **a.payload,
            "status": "CANCELLED",
            "cancellation_reason": "explicit_local_user",
            "transitions": a.payload["transitions"] + ["CANCELLED"],
        }
        append(s, row, q.key, "cancel", {"request_hash": digest(request), "order_id": order_id})
        s.commit()
        return {"cancelled": order_id}


def performance(s: Session, row: PaperSession) -> dict[str, Any]:
    snapshots = [a.payload for a in artifacts(s, row, "equity")]
    fills = [a.payload for a in artifacts(s, row, "fills")]
    ledger = restore_ledger(s, row)
    result = analytics(
        snapshots, float(row.configuration["capital"]), fills, [float(v) for v in ledger.closed]
    )
    if len(snapshots) < 60:
        for name in [
            "sharpe",
            "sortino",
            "calmar",
            "annualized_return",
            "cagr",
            "historical_var_95",
            "historical_cvar_95",
        ]:
            result[name] = None
        result["statistical_status"] = "insufficient_history_under_60_observations"
    return {
        "mode": row.mode,
        "synthetic": row.mode == "synthetic_demo",
        "metrics": result,
        "benchmark": None,
        "benchmark_reason": "No independently received aligned forward benchmark configured",
        "equity": snapshots,
    }


def replay(s: Session, row: PaperSession) -> dict[str, Any]:
    """Re-execute persisted M4 fills/M8 decisions/M9 assessments, not reacquired prices."""
    q = Create.model_validate(row.configuration)
    ledger = Ledger(q.capital)
    previous = row.configuration_hash
    count = 0
    for e in events(s, row.id):
        body = {
            "key": e.key,
            "kind": e.kind,
            "day": str(e.market_day) if e.market_day else None,
            "processed_at": e.processed_at.isoformat(),
            "payload": e.payload,
            "sequence": e.sequence,
        }
        if e.previous_hash != previous or e.hash != digest([previous, body]):
            raise error("Paper event chain differs", "replay_mismatch")
        previous = e.hash
        if e.kind != "market":
            continue
        p = e.payload
        if p["build_id"] != build_id():
            raise error("Paper replay requires original code build", "replay_mismatch")
        for op in p["operations"]:
            x = op["input"]
            o = deepcopy(x["order"])
            fill = fill_order(
                ledger,
                o,
                Decimal(x["price"]),
                x["previous_volume"],
                datetime.fromisoformat(x["at"]),
                q.costs,
                {t: Decimal(v) for t, v in x["marks"].items()},
            )
            expected = op["fill"]
            if fill:
                fill = {
                    **fill,
                    "price_convention": "next_observed_close_ioc",
                    "source_id": p["source_ids"][fill["ticker"]],
                }
            if not equivalent(fill, expected):
                raise error("Paper fill replay differs", "replay_mismatch")
            count += bool(fill)
        d = p["decision"]
        marks = {t: Decimal(v) for t, v in p["valuation"]["marks"].items()}
        if d:
            durable_decision = s.get(CommitteeDecision, d["decision_id"])
            if durable_decision is None or not equivalent(durable_decision.payload, d["record"]):
                raise error("Durable committee audit differs", "paper_integrity")
            adapter = CommitteeStrategy(
                CommitteeRequest.model_validate(d["request"]), thaw(d["inputs"]), d["metadata"]
            )
            context = Context(
                datetime.fromisoformat(d["context_at"]),
                cast(date, e.market_day),
                tuple(sorted(marks.items())),
                (),
                tuple((t, v.quantity) for t, v in sorted(ledger.positions.items())),
                ledger.cash,
            )
            adapter.targets(context)
            if not equivalent(adapter.trace[0], d["record"]):
                raise error("Committee replay differs", "replay_mismatch")
        for r in p["risks"]:
            from sentientalpha.database.risk_models import RiskPolicyVersion
            from sentientalpha.risk.storage import compact

            durable_risk = s.get(RiskAssessment, r["result"]["decision_id"])
            version = s.get(RiskPolicyVersion, durable_risk.policy_key) if durable_risk else None
            if (
                durable_risk is None
                or version is None
                or digest(version.definition) != r["result"]["policy_hash"]
                or not equivalent(durable_risk.payload, compact(r["result"]))
                or digest(durable_risk.inputs) != durable_risk.manifest["input_hash"]
            ):
                raise error("Durable risk audit differs", "paper_integrity")
            if not equivalent(
                evaluate(EvaluationRequest.model_validate(r["request"])), r["result"]
            ):
                raise error("Paper risk replay differs", "replay_mismatch")
        value = ledger.value(marks)
        if any(value[k] != p["valuation"][k] for k in value):
            raise error("Paper ledger replay differs", "replay_mismatch")
    saved_events = events(s, row.id)
    if saved_events and saved_events[-1].payload["orders_hash"] != digest(
        [a.payload for a in artifacts(s, row, "orders")]
    ):
        raise error("Order projection differs from audit", "paper_integrity")
    expected_equity = [e.payload["valuation"] for e in saved_events if e.kind == "market"]
    if not equivalent(expected_equity, [a.payload for a in artifacts(s, row, "equity")]):
        raise error("Valuation artifacts differ from event history", "paper_integrity")
    expected_day = None
    for event in saved_events:
        if event.market_day is not None:
            expected_day = event.market_day
        if event.payload.get("outage_catchup_through"):
            expected_day = date.fromisoformat(event.payload["outage_catchup_through"])
    if row.last_day != expected_day:
        raise error("Checkpoint differs from committed event history", "paper_integrity")
    durable = restore_ledger(s, row)
    if (
        ledger.cash != durable.cash
        or ledger.positions != durable.positions
        or count != len(artifacts(s, row, "fills"))
    ):
        raise error("Ledger artifacts differ from immutable events", "paper_integrity")
    return {
        "session_id": row.id,
        "equivalent": True,
        "fills": count,
        "events": len(events(s, row.id)),
        "mode": row.mode,
        "scope": (
            "Frozen event chain; M4 execution/accounting, M8 decisions and M9 assessments "
            "re-executed. No external reacquisition."
        ),
    }
