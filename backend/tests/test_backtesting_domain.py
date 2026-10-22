"""Independent financial fixtures and adversarial full-simulator chronology tests."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D

import numpy as np
import pytest
from pydantic import ValidationError
from sentientalpha.backtesting.analytics import analytics
from sentientalpha.backtesting.contracts import (
    Action,
    BacktestError,
    Bar,
    Costs,
    Feature,
    Request,
    Snapshot,
    StrategySpec,
)
from sentientalpha.backtesting.engine import simulate
from sentientalpha.backtesting.evaluation import Split, WalkRequest
from sentientalpha.backtesting.execution import execute
from sentientalpha.backtesting.ledger import Ledger
from sentientalpha.backtesting.strategies import Baseline, Context
from sentientalpha.data.calendar import session_close, session_open, sessions_in_range

START = date(2024, 1, 2)
END = date(2024, 1, 5)
CUTOFF = datetime(2026, 10, 14, tzinfo=UTC)
ZERO = Costs(fixed=D(0), slippage_bps=D(0), participation=D(1))


def request(**kwargs):
    return Request(
        tickers=["AAA"],
        start=START,
        end=END,
        source_as_of=CUTOFF,
        information_policy="research_replay",
        costs=ZERO,
        **kwargs,
    )


def snapshot(prices=((10, 10), (10, 11), (12, 13), (14, 14)), ticker="AAA", volume=10000):
    days = sessions_in_range("weekday", START, END)
    return Snapshot(
        tuple(
            Bar(
                ticker,
                day,
                D(op),
                D(cl),
                volume,
                session_close("weekday", day) + timedelta(seconds=1),
                CUTOFF,
                f"{ticker}-{day}",
            )
            for day, (op, cl) in zip(days, prices, strict=True)
        )
    )


class Scripted:
    def __init__(self, weights):
        self.weights = weights
        self.contexts = []

    def targets(self, context):
        self.contexts.append(context)
        return self.weights.get(context.day, {})


def test_complete_independent_golden_ledger():
    # Manually: buy 50*10.10+1 => cash494, basis506; sell27*11.88-1
    # => cash813.76, remaining basis232.76, realized46.52; sell23*13.86-1
    # => final1131.54, cumulative realized131.54, fees3, slippage11.46.
    spec = Scripted(
        {
            START: {"AAA": D("0.5")},
            date(2024, 1, 3): {"AAA": D("0.25")},
            date(2024, 1, 4): {"AAA": D(0)},
        }
    )
    cfg = request(capital=D(1000)).model_copy(
        update={"costs": Costs(fixed=D(1), slippage_bps=D(100), participation=D(1))}
    )
    result = simulate(cfg, snapshot(), spec)
    assert [D(f["quantity"]) for f in result["fills"]] == [50, 27, 23]
    assert [D(f["price"]) for f in result["fills"]] == [D("10.10"), D("11.88"), D("13.86")]
    assert [D(r["equity"]) for r in result["equity"]] == [1000, 1044, D("1112.76"), D("1131.54")]
    assert [D(r["cash"]) for r in result["equity"]] == [1000, 494, D("813.76"), D("1131.54")]
    final = result["equity"][-1]
    assert D(final["realized_pnl"]) == D("131.54")
    assert D(final["fees"]) == 3 and D(final["slippage"]) == D("11.46")
    assert all(
        D(r["equity"]) == D(r["cash"]) + D(r["market_value"])
        and D(r["reconciliation_residual"]) == 0
        for r in result["equity"]
    )
    expected = np.array([0, 0.044, 1112.76 / 1044 - 1, 1131.54 / 1112.76 - 1])
    assert result["metrics"]["total_return"] == pytest.approx(0.13154)
    assert result["metrics"]["annualized_volatility"] == pytest.approx(
        expected.std(ddof=1) * np.sqrt(252)
    )
    assert result["metrics"]["sharpe"] == pytest.approx(
        expected.mean() * 252 / (expected.std(ddof=1) * np.sqrt(252))
    )
    assert result["metrics"]["win_rate"] == 1 and result["metrics"]["profit_factor"] is None
    assert result["closed_pnl"] == pytest.approx([46.52, 85.02])
    for order, fill in zip(result["orders"], result["fills"], strict=True):
        assert fill["at"] > order["submitted_at"] and fill["at"] >= order["earliest_execution_at"]


@pytest.mark.parametrize(
    "fixed,per_share,percentage,expected",
    [(1, 0, 0, "899"), (0, 1, 0, "890"), (0, 0, "0.01", "899")],
)
def test_commission_models(fixed, per_share, percentage, expected):
    ledger = Ledger(D(1000))
    from sentientalpha.backtesting.execution import commission

    costs = Costs(fixed=D(fixed), per_share=D(per_share), percentage=D(percentage))
    ledger.fill("AAA", "buy", D(10), D(10), commission(costs, D(10), D(10)))
    assert ledger.cash == D(expected)


@pytest.mark.parametrize(
    "quantity,price,fee,side",
    [
        (0, 10, 0, "buy"),
        (-1, 10, 0, "buy"),
        (1, 0, 0, "buy"),
        (1, 10, -1, "buy"),
        (200, 10, 0, "buy"),
        (1, 10, 0, "sell"),
        (1, 10, 0, "short"),
    ],
)
def test_invalid_fill_is_atomic(quantity, price, fee, side):
    ledger = Ledger(D(1000))
    with pytest.raises(BacktestError):
        ledger.fill("AAA", side, D(quantity), D(price), D(fee))
    assert ledger.cash == 1000 and not ledger.positions


def test_split_dividend_and_fractional_basis():
    ledger = Ledger(D(1000))
    ledger.fill("AAA", "buy", D(9), D(10), D(1))
    ledger.action("AAA", "split", D("1.5"))
    assert ledger.positions["AAA"].quantity == D("13.5")
    assert ledger.positions["AAA"].basis == 91
    ledger.action("AAA", "dividend", D(2))
    assert ledger.cash == 936 and ledger.dividends == 27
    ledger.fill("AAA", "sell", D("4.5"), D(8), D(1))
    view = ledger.value({"AAA": D(8)})
    assert D(view["equity"]) == 1043 and abs(D(view["reconciliation_residual"])) < D("1e-8")


def order(at, quantity=10):
    return {
        "id": "x",
        "ticker": "AAA",
        "side": "buy",
        "requested_quantity": str(quantity),
        "filled_quantity": "0",
        "remaining_quantity": str(quantity),
        "submitted_at": (at - timedelta(hours=1)).isoformat(),
        "earliest_execution_at": at.isoformat(),
        "status": "submitted",
    }


@pytest.mark.parametrize(
    "opening,volume,expected",
    [
        (None, 100, "rejected"),
        (10, None, "rejected"),
        (10, 0, "rejected"),
        (10, 20, "partial_canceled"),
        (1000, 10000, "rejected"),
    ],
)
def test_execution_constraints(opening, volume, expected):
    ledger = Ledger(D(100))
    at = session_open("weekday", date(2024, 1, 3))
    o = order(at)
    fill = execute(
        ledger,
        o,
        D(opening) if opening else None,
        volume,
        at,
        Costs(fixed=D(1), slippage_bps=D(0), participation=D("0.1")),
        {"AAA": D(10)},
    )
    assert o["status"] == expected
    if expected == "rejected":
        assert fill is None and ledger.cash == 100 and not ledger.positions
    else:
        assert D(fill["quantity"]) == 2 and ledger.cash == 79


def test_same_instant_submission_refused():
    at = session_open("weekday", date(2024, 1, 3))
    o = order(at)
    o["submitted_at"] = at.isoformat()
    ledger = Ledger(D(1000))
    assert execute(ledger, o, D(10), 1000, at, ZERO, {"AAA": D(10)}) is None
    assert o["reason"] == "information_not_ready"


def test_next_open_no_same_close_or_double_lag():
    result = simulate(request(capital=D(1000)), snapshot())
    assert result["fills"][0]["at"] == session_open("weekday", date(2024, 1, 3)).isoformat()
    assert result["orders"][0]["observation_day"] == str(START)


@pytest.mark.parametrize("change", ["append", "future_close", "future_volume"])
def test_future_changes_do_not_change_settled_trades(change):
    snap = snapshot()
    original = simulate(request(capital=D(1000)), snap)
    if change == "append":
        altered = Snapshot(
            snap.bars + (replace(snap.bars[-1], day=date(2024, 1, 8), close=D(999)),)
        )
    else:
        altered = Snapshot(
            snap.bars[:-1]
            + (
                replace(
                    snap.bars[-1],
                    **({"close": D(999)} if change == "future_close" else {"volume": 0}),
                ),
            )
        )
    changed = simulate(request(capital=D(1000)), altered)
    assert changed["orders"] == original["orders"] and changed["fills"] == original["fills"]


def test_realized_execution_day_volume_cannot_limit_earlier_open():
    snap = snapshot()
    changed = Snapshot(
        tuple(replace(b, volume=0) if b.day == date(2024, 1, 3) else b for b in snap.bars)
    )
    assert (
        simulate(request(capital=D(1000)), changed)["fills"]
        == simulate(request(capital=D(1000)), snap)["fills"]
    )


def test_online_ingestion_cannot_be_backdated_by_replay():
    cfg = request(capital=D(1000)).model_copy(update={"information_policy": "online"})
    result = simulate(cfg, snapshot())
    assert result["status"] == "insufficient_data" and not result["fills"]


@pytest.mark.parametrize("delay", [timedelta(days=1), timedelta(days=3)])
def test_late_feature_never_executes_before_ready(delay):
    snap = snapshot()
    features = tuple(
        Feature(b.ticker, b.day, D(5), b.available + delay, CUTOFF, "snapshot") for b in snap.bars
    )
    cfg = request(
        capital=D(1000),
        strategy=StrategySpec(
            name="moving_average",
            rebalance="signal",
            feature_dataset_id="a" * 36,
            feature_column="sma__window_5",
        ),
    )
    result = simulate(cfg, Snapshot(snap.bars, features))
    for o in result["orders"]:
        feat = next(f for f in features if str(f.day) == o["observation_day"])
        assert datetime.fromisoformat(o["submitted_at"]) >= feat.ready
    assert (
        not result["fills"]
        or result["fills"][0]["at"] >= session_open("weekday", date(2024, 1, 4)).isoformat()
    )


@pytest.mark.parametrize("column", ["future_return", "target", "sent_mean__window_5"])
def test_future_labels_and_unverified_sentiment_are_not_strategy_inputs(column):
    with pytest.raises(ValidationError):
        StrategySpec(name="moving_average", feature_dataset_id="a" * 36, feature_column=column)


def test_strategy_context_has_no_future_table_and_is_immutable():
    strategy = Scripted({})
    simulate(request(), snapshot(), strategy)
    ctx = strategy.contexts[0]
    assert not hasattr(ctx, "bars") and not hasattr(ctx, "session")
    assert dict(ctx.prices) == {"AAA": D(10)}
    with pytest.raises(FrozenInstanceError):
        ctx.cash = D(0)


@pytest.mark.parametrize("kind", ["opening", "close", "whole"])
def test_missing_price_behavior(kind):
    snap = snapshot()
    altered = (
        Snapshot(
            tuple(replace(b, **{kind: None}) if b.day == date(2024, 1, 4) else b for b in snap.bars)
        )
        if kind != "whole"
        else Snapshot(tuple(b for b in snap.bars if b.day != date(2024, 1, 4)))
    )
    if kind == "opening":
        assert simulate(request(), altered)["status"] == "completed"
    else:
        with pytest.raises(BacktestError, match="Held security"):
            simulate(request(), altered)


def test_revised_history_is_refused_and_actions_not_retroactive():
    snap = snapshot()
    with pytest.raises(BacktestError, match="revised"):
        simulate(request(), Snapshot((replace(snap.bars[0], revision=2),) + snap.bars[1:]))
    action = Action(
        ticker="AAA",
        day=START,
        kind="split",
        value=D(2),
        known_at=CUTOFF,
        source="explicit fixture",
    )
    with pytest.raises(BacktestError, match="unavailable"):
        simulate(request(actions=[action]), snap)


def test_corporate_actions_in_event_engine_and_pending_units():
    snap = snapshot(((10, 10), (10, 10), (5, 5), (5, 5)))
    actions = [
        Action(
            ticker="AAA",
            day=date(2024, 1, 4),
            kind="split",
            value=D(2),
            known_at=datetime(2024, 1, 1, tzinfo=UTC),
            source="synthetic fixture",
        ),
        Action(
            ticker="AAA",
            day=date(2024, 1, 5),
            kind="dividend",
            value=D(1),
            known_at=datetime(2024, 1, 1, tzinfo=UTC),
            source="synthetic fixture",
        ),
    ]
    result = simulate(request(capital=D(1000), actions=actions), snap)
    assert D(result["equity"][-1]["equity"]) == 1200
    assert D(result["equity"][-1]["positions"]["AAA"]["quantity"]) == 200
    assert D(result["equity"][-1]["dividends"]) == 200


@pytest.mark.parametrize("frequency", ["once", "daily", "weekly", "monthly", "signal"])
def test_rebalance_schedules(frequency):
    spec = Baseline(StrategySpec(name="equal_weight", rebalance=frequency), ["AAA"])

    def ctx(day):
        return Context(
            datetime.combine(day, datetime.min.time(), UTC), day, (("AAA", D(10)),), (), (), D(1000)
        )

    assert spec.targets(ctx(date(2024, 1, 2)))
    assert bool(spec.targets(ctx(date(2024, 1, 3)))) == (frequency == "daily")
    assert bool(spec.targets(ctx(date(2024, 2, 1)))) == (
        frequency in {"daily", "weekly", "monthly"}
    )


def test_simultaneous_sells_before_buys_and_universe_is_fixed():
    snap = snapshot()
    second = snapshot(ticker="BBB")
    cfg = request(capital=D(1000)).model_copy(update={"tickers": ["AAA", "BBB"]})
    script = Scripted(
        {START: {"AAA": D(1), "BBB": D(0)}, date(2024, 1, 3): {"AAA": D(0), "BBB": D(1)}}
    )
    result = simulate(cfg, Snapshot(snap.bars + second.bars), script)
    assert [(f["side"], f["ticker"]) for f in result["fills"]] == [
        ("buy", "AAA"),
        ("sell", "AAA"),
        ("buy", "BBB"),
    ]
    bad = Scripted({START: {"FUTURE_MEMBER": D(1)}})
    with pytest.raises(BacktestError, match="constraints"):
        simulate(cfg, snap, bad)


@pytest.mark.parametrize("reason", ["cash", "missing_features"])
def test_no_trades_and_undefined_statistics(reason):
    cfg = (
        request(strategy=StrategySpec(allocation={"AAA": D(0)}))
        if reason == "cash"
        else request(
            strategy=StrategySpec(
                name="moving_average", feature_dataset_id="a" * 36, feature_column="sma__window_5"
            )
        )
    )
    result = simulate(cfg, snapshot())
    assert not result["fills"]
    for key in ("sharpe", "sortino", "calmar", "win_rate", "profit_factor", "beta", "alpha"):
        assert result["metrics"][key] is None
    assert analytics([], 0, [], [])["status"] == "insufficient_data"


@pytest.mark.parametrize(
    "bad",
    [{"test_start": "2024-01-03"}, {"validation_start": "2024-01-01"}, {"embargo_sessions": 1}],
)
def test_chronological_split_rejects_overlap(bad):
    fields = dict(
        train_start="2024-01-01",
        train_end="2024-01-02",
        validation_start="2024-01-03",
        validation_end="2024-01-04",
        test_start="2024-01-05",
        test_end="2024-01-08",
    )
    with pytest.raises(ValidationError):
        Split(**(fields | bad))


def test_label_overlap_purge_and_explicit_embargo():
    days = sessions_in_range("weekday", date(2024, 1, 1), date(2024, 1, 31))
    split = Split(
        train_start=days[0],
        train_end=days[9],
        validation_start=days[10],
        validation_end=days[14],
        test_start=days[15],
        test_end=days[-1],
        label_horizon_sessions=2,
        embargo_sessions=1,
    )
    assert split.indices(days)["train"] == list(range(7))
    assert split.indices(days)["validation"] == [10, 11]


@pytest.mark.parametrize("mode", ["rolling", "expanding"])
def test_walk_forward_disjoint_oos_and_frozen_selection(mode):
    cfg = request().model_copy(update={"start": date(2024, 1, 1), "end": date(2024, 2, 29)})
    wr = WalkRequest(
        backtest=cfg,
        train_sessions=10,
        validation_sessions=5,
        test_sessions=5,
        step_sessions=5,
        mode=mode,
    )
    days = sessions_in_range("weekday", cfg.start, cfg.end)
    folds = wr.folds(days)
    assert all(a.test_end < b.test_start for a, b in zip(folds, folds[1:], strict=False))
    assert folds[1].train_start == (days[0] if mode == "expanding" else days[5])
    with pytest.raises(ValidationError):
        wr.model_validate(wr.model_dump() | {"step_sessions": 4})


def test_weekend_holiday_no_execution_event():
    days = sessions_in_range("XNYS", date(2024, 7, 3), date(2024, 7, 8))
    assert days == [date(2024, 7, 3), date(2024, 7, 5), date(2024, 7, 8)]
    from sentientalpha.features.timing import next_open

    assert next_open("XNYS", datetime(2024, 7, 3, 22, tzinfo=UTC)) == session_open(
        "XNYS", date(2024, 7, 5)
    )


def test_post_fee_position_limit_not_just_pre_fee_equity():
    ledger = Ledger(D(1000))
    at = session_open("weekday", date(2024, 1, 3))
    o = order(at, 100)
    costs = Costs(
        fixed=D(10),
        per_share=D("0.1"),
        percentage=D("0.01"),
        slippage_bps=D(100),
        position_limit=D("0.5"),
        participation=D(1),
    )
    execute(ledger, o, D(10), 10000, at, costs, {"AAA": D(10)})
    assert ledger.value({"AAA": D(10)})["positions"]["AAA"]["weight"] <= 0.5


def test_benchmark_alignment_zero_variance_and_short_sample():
    from sentientalpha.backtesting.analytics import annual_growth

    assert annual_growth(10**20, 126) is None
    cash = [
        {"day": str(START + timedelta(days=i)), "equity": "1000", "gross_exposure": 0}
        for i in range(25)
    ]
    metrics = analytics(cash, 1000, [], [], cash)
    assert metrics["historical_var_95"] == 0 and metrics["historical_cvar_95"] == 0
    assert metrics["beta"] is None and metrics["information_ratio"] is None
    assert analytics(cash, 1000, [], [], cash[:-1])["excess_return"] is None
    short = analytics(cash[:1], 1000, [], [])
    assert short["cagr"] is None and short["annualized_return"] is None


def test_unknown_volume_opt_in_approximation_and_suspension():
    at = session_open("weekday", date(2024, 1, 3))
    ledger = Ledger(D(1000))
    o = order(at)
    assert execute(
        ledger,
        o,
        D(10),
        None,
        at,
        ZERO.model_copy(update={"unknown_volume": "unlimited_approximation"}),
        {"AAA": D(10)},
    )
    snap = snapshot()
    suspended = Snapshot(
        tuple(replace(b, opening=None) if b.day == date(2024, 1, 3) else b for b in snap.bars)
    )
    result = simulate(request(), suspended)
    assert not result["fills"] and result["orders"][0]["reason"] == "missing_open_or_suspended"


def test_split_does_not_rewrite_past_fills_or_prices():
    snap = snapshot(((10, 10), (10, 10), (5, 5), (5, 5)))
    action = Action(
        ticker="AAA",
        day=date(2024, 1, 4),
        kind="split",
        value=D(2),
        known_at=datetime(2024, 1, 1, tzinfo=UTC),
        source="fixture",
    )
    original = simulate(request(capital=D(1000)), snap)
    adjusted = simulate(request(capital=D(1000), actions=[action]), snap)
    assert adjusted["fills"] == original["fills"]
    assert adjusted["equity"][:2] == original["equity"][:2]
    assert snap.bars[0].opening == 10


def test_other_position_limit_cannot_be_broken_by_new_buy_fees():
    ledger = Ledger(D(1000))
    ledger.fill("BBB", "buy", D(50), D(10), D(0))
    at = session_open("weekday", date(2024, 1, 3))
    o = order(at, 10)
    fill = execute(
        ledger,
        o,
        D(10),
        10000,
        at,
        Costs(fixed=D(10), slippage_bps=D(0), position_limit=D("0.5"), participation=D(1)),
        {"AAA": D(10), "BBB": D(10)},
    )
    assert fill is None and ledger.cash == 500
    assert o["reason"] == "other_position_post_cost_limit"


def test_same_day_split_precedes_post_split_dividend_credit():
    snap = snapshot(((10, 10), (10, 10), (5, 5), (5, 5)))
    kwargs = dict(
        ticker="AAA",
        day=date(2024, 1, 4),
        known_at=datetime(2024, 1, 1, tzinfo=UTC),
        source="synthetic fixture",
    )
    actions = [
        Action(**kwargs, kind="dividend", value=D(1)),
        Action(**kwargs, kind="split", value=D(2)),
    ]
    result = simulate(request(capital=D(1000), actions=actions), snap)
    assert [a["kind"] for a in result["actions"]] == ["split", "dividend"]
    assert D(result["equity"][-1]["equity"]) == 1200


def test_bar_clock_and_nan_input_contracts():
    bar = snapshot().bars[0]
    for changes in (
        {"close": D("NaN")},
        {"volume": -1},
        {"ingested": bar.available - timedelta(seconds=1)},
        {"available": datetime(2024, 1, 1)},
    ):
        with pytest.raises(ValueError):
            replace(bar, **changes)
    from sentientalpha.backtesting.analytics import annual_growth

    assert annual_growth(-1, 126) == -1


def test_independent_drawdown_tail_risk_closed_lots_and_regression():
    rows = [
        {
            "day": str(START + timedelta(days=i)),
            "equity": "1000" if i == 0 else "800",
            "gross_exposure": 0.5,
        }
        for i in range(20)
    ]
    benchmark = [{**r, "equity": "1000" if i == 0 else "900"} for i, r in enumerate(rows)]
    result = analytics(rows, 1000, [], [10, -5, 0], benchmark)
    # Twenty returns: one -20% and nineteen zeroes. Linear 5th percentile=-1%.
    assert result["maximum_drawdown"] == pytest.approx(0.2)
    assert result["drawdown_duration_sessions"] == 19
    assert result["historical_var_95"] == pytest.approx(0.01)
    assert result["historical_cvar_95"] == pytest.approx(0.2)
    assert result["downside_deviation"] == pytest.approx(np.sqrt(0.04 / 20 * 252))
    assert result["profit_factor"] == 2 and result["win_rate"] == pytest.approx(1 / 3)
    assert result["average_trade_pnl"] == pytest.approx(5 / 3)
    assert result["beta"] == pytest.approx(2) and result["alpha"] == pytest.approx(0, abs=1e-12)
    assert result["excess_return"] == pytest.approx(-0.1)
    assert result["monthly_returns"] == [{"month": "2024-01", "return": pytest.approx(-0.2)}]
