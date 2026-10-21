"""Operational adversaries against real SQLite transactions and existing quantitative engines."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sentientalpha.api.app import create_app
from sentientalpha.config import Settings
from sentientalpha.data.synthetic import SyntheticProvider
from sentientalpha.database.paper_models import PaperEvent
from sentientalpha.database.risk_models import RiskAssessment
from sentientalpha.database.session import make_engine, session_factory
from sentientalpha.paper import storage as paper
from sentientalpha.paper.contracts import Advance, Command, Create
from sentientalpha.services.ingestion import ingest
from sqlalchemy import select
from test_integration import database as database


def configuration(**changes):
    values = dict(
        key="paper-create-test",
        mode="synthetic_demo",
        tickers=["AAPL"],
        provider="synthetic",
        history_start="2024-01-02",
        simulation_start="2024-04-01",
        capital="10000",
        committee_policy={"effective_at": "2023-12-31T00:00:00Z", "minimum_independent_groups": 1},
        risk_policy={
            "id": "paper-test",
            "version": "1",
            "effective_at": "2023-12-31T00:00:00Z",
            "constraints": {"cash_maximum": 1, "concentration": 0.4},
            "estimator": {"minimum_observations": 20},
        },
    )
    return Create.model_validate({**values, **changes})


def initialize(sessions, **changes):
    q = configuration(**changes)
    for t in q.tickers:
        ingest(sessions, SyntheticProvider(), t, date(2024, 1, 2), date(2024, 4, 12))
    row = paper.create(sessions, q)
    paper.transition(sessions, row.id, "ready", Command(key="ready-command"))
    paper.transition(sessions, row.id, "start", Command(key="start-command"))
    return row


def test_end_to_end_m4_m5_m8_m9_and_immutable_replay(database):
    _, sessions, _ = database
    row = initialize(sessions)
    result = paper.advance(sessions, row.id, Advance(key="advance-all", maximum_events=10))
    assert result["processed"]
    with sessions() as s:
        row = paper.get(s, row.id)
        print(
            [
                (e.kind, (e.payload.get("decision") or {}).get("record", {}).get("final_action"))
                for e in paper.events(s, row.id)
            ]
        )
        assert paper.replay(s, row)["equivalent"]
        state = paper.present(s, row)
        assert state["mode"] == "synthetic_demo" and state["synthetic"]
        assert Decimal(state["portfolio"]["reconciliation_residual"]) == 0
        assert paper.artifacts(s, row, "fills")
        assert paper.performance(s, row)["metrics"]["sharpe"] is None


def test_api_lifecycle_idempotency_and_malformed_requests(database):
    url, sessions, _ = database
    for t in ["AAPL"]:
        ingest(sessions, SyntheticProvider(), t, date(2024, 1, 2), date(2024, 4, 5))
    with TestClient(create_app(Settings(database_url=url))) as c:
        payload = configuration().model_dump(mode="json")
        first = c.post("/api/paper/sessions", json=payload)
        assert first.status_code == 201, first.text
        id = first.json()["id"]
        assert first.json()["status"] == "CREATED"
        assert c.post("/api/paper/sessions", json=payload).json()["id"] == id
        assert (
            c.post(
                f"/api/paper/sessions/{id}/advance", json={"key": "premature-advance"}
            ).status_code
            == 409
        )
        for action in ["ready", "start", "pause", "resume"]:
            r = c.post(f"/api/paper/sessions/{id}/{action}", json={"key": action + "-command"})
            assert r.status_code == 200, r.text
            assert (
                c.post(
                    f"/api/paper/sessions/{id}/{action}", json={"key": action + "-command"}
                ).status_code
                == 200
            )
        r = c.post(
            f"/api/paper/sessions/{id}/advance", json={"key": "advance-api", "maximum_events": 3}
        )
        assert r.status_code == 200, r.text
        assert (
            c.post(
                f"/api/paper/sessions/{id}/advance",
                json={"key": "advance-api", "maximum_events": 3},
            ).json()
            == r.json()
        )
        for kind in ["orders", "fills", "decisions", "risk", "events", "portfolio", "performance"]:
            r = c.get(f"/api/paper/sessions/{id}/{kind}")
            assert r.status_code == 200, (kind, r.text)
        assert c.post(
            f"/api/paper/sessions/{id}/reconcile", json={"key": "reconcile-command"}
        ).json()["data"]["equivalent"]
        assert (
            c.post(f"/api/paper/sessions/{id}/stop", json={"key": "stop-command"}).status_code
            == 200
        )
        assert (
            c.post(f"/api/paper/sessions/{id}/resume", json={"key": "resume-stopped"}).status_code
            == 409
        )
        assert (
            c.post(f"/api/paper/sessions/{id}/advance", json={"key": "advance-stopped"}).status_code
            == 409
        )
        assert (
            c.post("/api/paper/sessions", json={**payload, "mode": "forward_paper"}).status_code
            == 422
        )
        assert (
            c.post(
                f"/api/paper/sessions/{id}/advance",
                json={"key": "invalid-budget", "maximum_events": 100000},
            ).status_code
            == 422
        )
        assert (
            c.post(
                "/api/paper/sessions", json={**payload, "strategy": '__import__("os")'}
            ).status_code
            == 422
        )


@pytest.mark.parametrize(
    "stage", ["after_decision", "after_risk", "after_execution", "before_checkpoint", "after_fill"]
)
def test_atomic_crash_restart_no_duplicate_economic_effect(database, stage):
    url, sessions, _ = database
    row = initialize(sessions)
    # Reach a day with a real pending order before testing fill-stage faults.
    if stage == "after_fill":
        for i in range(5):
            paper.advance(sessions, row.id, Advance(key=f"prepare-fill-{i}"))
            with sessions() as s:
                if any(
                    a.payload["status"] == "QUEUED"
                    for a in paper.artifacts(s, paper.get(s, row.id), "orders")
                ):
                    break
    with sessions() as s:
        before = {
            k: len(paper.artifacts(s, paper.get(s, row.id), k))
            for k in ["fills", "orders", "equity"]
        }
        checkpoint = paper.get(s, row.id).last_day

    def crash(where):
        if where == stage:
            raise RuntimeError("injected process interruption")

    with pytest.raises(RuntimeError):
        paper.advance(sessions, row.id, Advance(key="crash-command"), fault=crash)
    engine = make_engine(url)
    restarted = session_factory(engine)
    try:
        with restarted() as s:
            restored = paper.get(s, row.id)
            assert restored.last_day == checkpoint
            assert {k: len(paper.artifacts(s, restored, k)) for k in before} == before
        a = paper.advance(restarted, row.id, Advance(key="crash-command"))
        assert paper.advance(restarted, row.id, Advance(key="crash-command")) == a
        with restarted() as s:
            assert paper.replay(s, paper.get(s, row.id))["equivalent"]
    finally:
        engine.dispose()


def test_duplicate_event_competing_workers_and_pause(database):
    _, sessions, _ = database
    row = initialize(sessions)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(
            pool.map(
                lambda i: paper.advance(sessions, row.id, Advance(key="concurrent-same-command")),
                range(2),
            )
        )
    with sessions() as s:
        assert len([e for e in paper.events(s, row.id) if e.kind == "market"]) == 1
        assert paper.replay(s, paper.get(s, row.id))["equivalent"]
    paper.transition(sessions, row.id, "pause", Command(key="pause-command"))
    with pytest.raises(paper.OptimizationError):
        paper.advance(sessions, row.id, Advance(key="paused-command"))


def test_event_chain_tamper_and_configuration_tamper_fail_closed(database):
    _, sessions, _ = database
    row = initialize(sessions)
    paper.advance(sessions, row.id, Advance(key="one-command"))
    with sessions.begin() as s:
        e = s.scalar(
            select(PaperEvent).where(PaperEvent.session_id == row.id, PaperEvent.kind == "market")
        )
        e.payload = {**e.payload, "source_hash": "tampered"}
    with sessions() as s:
        with pytest.raises(Exception, match="chain"):
            paper.replay(s, paper.get(s, row.id))


def test_independent_decimal_reference_and_cancel_pending(database):
    from sentientalpha.backtesting.contracts import Costs
    from sentientalpha.backtesting.execution import execute
    from sentientalpha.backtesting.ledger import Ledger

    ledger = Ledger(Decimal("1000"))
    at = datetime(2024, 4, 3, tzinfo=UTC)
    o = {
        "id": "independent",
        "ticker": "AAPL",
        "side": "buy",
        "requested_quantity": "20",
        "submitted_at": (at - timedelta(days=1)).isoformat(),
        "earliest_execution_at": at.isoformat(),
    }
    f = execute(
        ledger,
        o,
        Decimal("100"),
        100,
        at,
        Costs(fixed=Decimal("1"), slippage_bps=Decimal("10"), participation=Decimal(".05")),
        {"AAPL": Decimal("100")},
    )
    assert f["quantity"] == "5" and f["price"] == "100.100"
    assert ledger.cash == Decimal("498.500") and ledger.positions["AAPL"].basis == Decimal(
        "501.500"
    )
    assert ledger.value({"AAPL": Decimal("100")})["equity"] == "998.500"
    _, sessions, _ = database
    row = initialize(sessions)
    for i in range(5):
        paper.advance(sessions, row.id, Advance(key=f"cancel-prepare-{i}"))
        with sessions() as s:
            orders = [
                a.payload
                for a in paper.artifacts(s, paper.get(s, row.id), "orders")
                if a.payload["status"] == "QUEUED"
            ]
        if orders:
            break
    assert orders
    paper.cancel(sessions, row.id, orders[0]["id"], Command(key="cancel-command"))
    assert paper.cancel(sessions, row.id, orders[0]["id"], Command(key="cancel-command"))[
        "cancelled"
    ]
    with pytest.raises(paper.OptimizationError):
        paper.cancel(sessions, row.id, orders[0]["id"], Command(key="cancel-again"))


@pytest.mark.parametrize(
    "changes",
    [
        {"mode": "forward_paper"},
        {"provider": "alphavantage"},
        {"capital": "NaN"},
        {"capital": "-1"},
        {"tickers": ["AAPL", "AAPL"]},
        {"tickers": ["__import__(x)"]},
        {"execution_convention": "same_close"},
        {"corporate_action_policy": "ignore"},
        {"simulation_start": "2020-01-01"},
        {"historical_run_id": "not-a-uuid"},
    ],
)
def test_unsafe_or_incompatible_session_configuration(changes):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        configuration(**changes)


@pytest.mark.parametrize("action", ["start", "pause", "resume"])
def test_created_session_cannot_skip_lifecycle(database, action):
    _, sessions, _ = database
    row = paper.create(sessions, configuration())
    with pytest.raises(paper.OptimizationError):
        paper.transition(sessions, row.id, action, Command(key="invalid-state-key"))


def test_command_key_conflict_and_partial_batch_retry_frozen_days(database):
    _, sessions, _ = database
    row = initialize(sessions)
    calls = 0

    def crash(stage):
        nonlocal calls
        if stage == "before_checkpoint":
            calls += 1
            if calls == 2:
                raise RuntimeError("interruption between batch events")

    with pytest.raises(RuntimeError):
        paper.advance(
            sessions, row.id, Advance(key="frozen-batch-key", maximum_events=3), fault=crash
        )
    with sessions() as s:
        assert len(paper.artifacts(s, paper.get(s, row.id), "equity")) == 1
    response = paper.advance(sessions, row.id, Advance(key="frozen-batch-key", maximum_events=3))
    assert len(response["processed"]) == 3
    assert (
        paper.advance(sessions, row.id, Advance(key="frozen-batch-key", maximum_events=3))
        == response
    )
    with pytest.raises(paper.OptimizationError, match="different input"):
        paper.advance(sessions, row.id, Advance(key="frozen-batch-key", maximum_events=4))


def test_missing_price_and_revision_fail_closed_and_do_not_revalue(database):
    from sentientalpha.database.models import MarketPrice

    _, sessions, _ = database
    row = initialize(sessions, tickers=["AAPL", "MSFT"])
    # Remove an asset's current observation in this disposable test database.
    with sessions.begin() as s:
        asset = s.scalar(select(paper.Asset).where(paper.Asset.ticker == "MSFT"))
        bar = s.scalar(
            select(MarketPrice).where(
                MarketPrice.asset_id == asset.id, MarketPrice.session_date == date(2024, 4, 1)
            )
        )
        bar.quality_flags = ["unexplained_jump"]
    result = paper.advance(sessions, row.id, Advance(key="quality-command"))
    assert result["status"] == "PAUSED"
    with sessions() as s:
        assert not paper.artifacts(s, paper.get(s, row.id), "fills")
        assert not paper.artifacts(s, paper.get(s, row.id), "equity")


def test_pending_order_revalidation_veto_with_insufficient_tail_history(database):
    _, sessions, _ = database
    q = configuration().model_dump(mode="json")
    q["risk_policy"]["var_maximum"] = 0.01
    row = initialize(sessions, **q)
    paper.advance(sessions, row.id, Advance(key="var-risk-command", maximum_events=5))
    with sessions() as s:
        r = paper.get(s, row.id)
        assert not paper.artifacts(s, r, "fills")
        assessments = list(
            s.scalars(select(RiskAssessment).where(RiskAssessment.backtest_id == r.ledger_id))
        )
        assert any(a.status in {"REJECTED", "INSUFFICIENT_RISK_DATA"} for a in assessments)
        assert paper.replay(s, r)["equivalent"]


def test_order_artifact_tamper_cannot_be_reconciled(database):
    _, sessions, _ = database
    row = initialize(sessions)
    paper.advance(sessions, row.id, Advance(key="tamper-orders", maximum_events=5))
    with sessions.begin() as s:
        a = paper.artifacts(s, paper.get(s, row.id), "orders")[0]
        a.payload = {**a.payload, "status": "FILLED", "filled_quantity": "99999999"}
    with sessions() as s:
        with pytest.raises(paper.OptimizationError, match="Order projection"):
            paper.replay(s, paper.get(s, row.id))


def test_provider_failure_audited_and_retry_uses_new_key(database, monkeypatch):
    from sentientalpha.paper.worker import update

    _, sessions, _ = database
    row = initialize(sessions)

    def unavailable(*args, **kwargs):
        raise RuntimeError("secret-bearing upstream text must not escape")

    monkeypatch.setattr("sentientalpha.paper.worker.ingest", unavailable)
    from sentientalpha.paper.contracts import Update

    q = Update(key="provider-update-failure", start=date(2024, 4, 1), end=date(2024, 4, 2))
    first = update(sessions, row.id, q, Settings())
    assert first["status"] == "provider_update_failed" and "secret" not in str(first)
    assert update(sessions, row.id, q, Settings()) == first
    with sessions() as s:
        assert paper.get(s, row.id).warning.startswith("provider_update_failed")


def test_historical_research_cannot_be_started_as_forward(database):
    _, sessions, _ = database
    from sentientalpha.database.backtest_models import BacktestRun

    with sessions.begin() as s:
        b = BacktestRun(
            status="completed",
            manifest={"scope": "test_fixture"},
            snapshot={},
            metrics={},
            diagnostics={},
        )
        s.add(b)
        s.flush()
        id = b.id
    row = paper.create(
        sessions,
        configuration(
            mode="historical_replay",
            provider="alphavantage",
            simulation_start=None,
            historical_run_id=id,
        ),
    )
    paper.transition(sessions, row.id, "ready", Command(key="historical-ready"))
    with pytest.raises(paper.OptimizationError, match="Historical research"):
        paper.transition(sessions, row.id, "start", Command(key="historical-start"))


def test_forward_clock_cannot_be_user_overridden_or_backfill_traded(database):
    _, sessions, _ = database
    row = paper.create(
        sessions,
        configuration(mode="forward_paper", provider="alphavantage", simulation_start=None),
    )
    paper.transition(sessions, row.id, "ready", Command(key="forward-ready"))
    paper.transition(sessions, row.id, "start", Command(key="forward-start"))
    with pytest.raises(paper.OptimizationError, match="clock"):
        paper.advance(sessions, row.id, Advance(key="forward-override", through=date(2024, 4, 1)))
    # No genuine forward data has arrived. A synthetic provider cannot silently supply it.
    ingest(sessions, SyntheticProvider(), "AAPL", date(2024, 1, 2), date(2024, 4, 2))
    assert paper.advance(sessions, row.id, Advance(key="forward-no-data"))["no_new_observations"]
    with sessions() as s:
        assert not paper.artifacts(s, paper.get(s, row.id), "orders")


@pytest.fixture
def forward_fixture(database, monkeypatch):
    """Clock-controlled provider fixture, NOT genuine market observations."""
    from dataclasses import replace

    from sentientalpha.data.calendar import session_close, sessions_in_range
    from sentientalpha.database.models import MarketPrice

    _, sessions, _ = database

    class ClockProvider:
        name = "alphavantage"
        parameters = {"fixture": "modeled prices for clock tests only"}

        def fetch(self, ticker, start, end):
            days = set(sessions_in_range("XNYS", start, end))
            return [
                replace(
                    b,
                    provider="alphavantage",
                    is_synthetic=False,
                    availability_kind="observed",
                    calendar="XNYS",
                    session_close_at=session_close("XNYS", b.session_date),
                    available_at=session_close("XNYS", b.session_date) + timedelta(minutes=1),
                )
                for b in SyntheticProvider().fetch(ticker, start, end)
                if b.session_date in days
            ]

    ingest(sessions, ClockProvider(), "AAPL", date(2024, 1, 2), date(2024, 4, 12))
    with sessions.begin() as s:
        for b in s.scalars(select(MarketPrice)):
            b.ingested_at = b.available_at + timedelta(seconds=1)
            b.observed_at = b.available_at
    clock = [datetime(2024, 4, 1, 12, tzinfo=UTC)]
    monkeypatch.setattr(paper, "now", lambda: clock[0])
    monkeypatch.setattr(
        "sentientalpha.features.storage.now", lambda: clock[0] - timedelta(seconds=1)
    )
    row = paper.create(
        sessions,
        configuration(mode="forward_paper", provider="alphavantage", simulation_start=None),
    )
    paper.transition(sessions, row.id, "ready", Command(key="clock-ready-key"))
    paper.transition(sessions, row.id, "start", Command(key="clock-start-key"))
    return sessions, row, clock


def test_forward_daily_clocks_decisions_fills_and_recovery(forward_fixture):
    from sentientalpha.data.calendar import session_close, sessions_in_range

    sessions, row, clock = forward_fixture
    for i, day in enumerate(sessions_in_range("XNYS", date(2024, 4, 1), date(2024, 4, 5))):
        clock[0] = session_close("XNYS", day) + timedelta(minutes=3)
        paper.advance(sessions, row.id, Advance(key=f"forward-event-{i}"))
    with sessions() as s:
        r = paper.get(s, row.id)
        ev = [e for e in paper.events(s, row.id) if e.kind == "market"]
        assert ev and all(
            e.payload["decision_clock"] == e.payload["actual_processing_at"] for e in ev
        )
        assert paper.artifacts(s, r, "fills")
        for a in paper.artifacts(s, r, "orders"):
            if a.payload.get("execution_at"):
                fillday = datetime.fromisoformat(a.payload["execution_at"]).date()
                assert session_close("XNYS", fillday) > datetime.fromisoformat(
                    a.payload["submitted_at"]
                )
        assert paper.replay(s, r)["equivalent"]
        assert paper.present(s, r)["mode"] == "forward_paper"


def test_prestart_backfill_is_only_catchup(forward_fixture):
    sessions, row, clock = forward_fixture
    clock[0] = datetime(2024, 4, 1, 12, tzinfo=UTC)
    result = paper.advance(sessions, row.id, Advance(key="catchup-only-key"))
    with sessions() as s:
        assert not paper.artifacts(s, paper.get(s, row.id), "fills")
        assert not paper.artifacts(s, paper.get(s, row.id), "orders")
        assert any(e.kind == "historical_catch_up" for e in paper.events(s, row.id))
    assert result["processed"][0]["kind"] == "historical_catch_up"


@pytest.mark.parametrize("condition", ["stale", "late", "revision", "incomplete", "nonfinite"])
def test_forward_unusable_market_data_never_generates_a_fill(forward_fixture, condition):
    from sentientalpha.data.calendar import session_close
    from sentientalpha.database.models import MarketPrice

    sessions, row, clock = forward_fixture
    clock[0] = session_close("XNYS", date(2024, 4, 1)) + timedelta(minutes=3)
    if condition == "stale":
        clock[0] = datetime(2024, 4, 20, tzinfo=UTC)
    with sessions.begin() as s:
        bar = s.scalar(select(MarketPrice).where(MarketPrice.session_date == date(2024, 4, 1)))
        if condition == "late":
            bar.ingested_at = datetime(2024, 4, 3, tzinfo=UTC)
            clock[0] = datetime(2024, 4, 3, 1, tzinfo=UTC)
        if condition == "revision":
            bar.revision_no = 2
        if condition == "incomplete":
            bar.session_close_at = clock[0] + timedelta(hours=1)
            bar.available_at = bar.session_close_at + timedelta(minutes=1)
            bar.ingested_at = bar.available_at + timedelta(seconds=1)
        if condition == "nonfinite":
            bar.quality_flags = ["invalid_valuation"]
    paper.advance(sessions, row.id, Advance(key="bad-forward-market"))
    with sessions() as s:
        assert not paper.artifacts(s, paper.get(s, row.id), "fills")


def test_unique_fill_receipt_and_order_identity_enforced_in_database(database):
    from sentientalpha.database.paper_models import PaperFillReceipt, PaperOrder
    from sqlalchemy.exc import IntegrityError

    _, sessions, _ = database
    row = initialize(sessions)
    paper.advance(sessions, row.id, Advance(key="db-unique-command", maximum_events=5))
    with sessions() as s:
        order = s.scalar(select(PaperOrder).where(PaperOrder.session_id == row.id))
        oid, aid, did = order.id, order.artifact_id, order.decision_id
        receipt = s.scalar(select(PaperFillReceipt))
        filled_order, fill_artifact = receipt.order_id, receipt.artifact_id
    with pytest.raises(IntegrityError):
        with sessions.begin() as s:
            s.add(PaperOrder(id=oid, session_id=row.id, artifact_id=aid, decision_id=did))
    with pytest.raises(IntegrityError):
        with sessions.begin() as s:
            s.add(PaperFillReceipt(order_id=filled_order, artifact_id=fill_artifact))
    with sessions() as s:
        assert paper.replay(s, paper.get(s, row.id))["equivalent"]


def test_paused_ingestion_preserves_positions_and_checkpoint(database):
    from sentientalpha.paper.contracts import Update
    from sentientalpha.paper.worker import update

    _, sessions, _ = database
    row = initialize(sessions)
    paper.advance(sessions, row.id, Advance(key="paused-data-initial", maximum_events=3))
    paper.transition(sessions, row.id, "pause", Command(key="paused-data-pause"))
    with sessions() as s:
        before = paper.present(s, paper.get(s, row.id))
    result = update(
        sessions,
        row.id,
        Update(key="paused-data-update", start=date(2024, 4, 1), end=date(2024, 4, 5)),
        Settings(),
    )
    assert result["status"] == "updated"
    with sessions() as s:
        after = paper.present(s, paper.get(s, row.id))
        assert after["status"] == "PAUSED"
        assert (
            after["portfolio"] == before["portfolio"]
            and after["last_processed_observation"] == before["last_processed_observation"]
        )
        assert paper.replay(s, paper.get(s, row.id))["equivalent"]


def test_checkpoint_corruption_cannot_skip_recovery_validation(database):
    _, sessions, _ = database
    row = initialize(sessions)
    paper.advance(sessions, row.id, Advance(key="checkpoint-one"))
    with sessions.begin() as s:
        paper.get(s, row.id).last_day = date(2024, 4, 12)
    with sessions() as s:
        with pytest.raises(paper.OptimizationError, match="Checkpoint"):
            paper.replay(s, paper.get(s, row.id))


def test_missing_security_observation_pauses_without_fake_valuation(database):
    from sentientalpha.database.models import Asset, MarketPrice
    from sqlalchemy import delete

    _, sessions, _ = database
    row = initialize(sessions, tickers=["AAPL", "MSFT"])
    with sessions.begin() as s:
        asset = s.scalar(select(Asset).where(Asset.ticker == "MSFT"))
        s.execute(
            delete(MarketPrice).where(
                MarketPrice.asset_id == asset.id, MarketPrice.session_date == date(2024, 4, 1)
            )
        )
    response = paper.advance(sessions, row.id, Advance(key="missing-security-key"))
    assert response["status"] == "PAUSED"
    with sessions() as s:
        r = paper.get(s, row.id)
        assert "missing_universe" in r.warning
        assert not paper.artifacts(s, r, "equity") and not paper.artifacts(s, r, "fills")


def test_paper_financial_carriers_are_not_historical_research_catalogs(database):
    url, sessions, _ = database
    row = initialize(sessions)
    paper.advance(sessions, row.id, Advance(key="catalog-separation"))
    with TestClient(create_app(Settings(database_url=url))) as c:
        for kind in ["backtest", "committee"]:
            assert c.get("/api/research/catalog?kind=" + kind).json()["items"] == []
