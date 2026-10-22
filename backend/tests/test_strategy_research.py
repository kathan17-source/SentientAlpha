"""Independent rule/fitness references and adversarial strategy-discovery tests."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from math import tanh

import numpy as np
import pytest
from pydantic import ValidationError
from sentientalpha.backtesting.contracts import Bar, Snapshot
from sentientalpha.backtesting.evaluation import Split
from sentientalpha.backtesting.strategies import Context
from sentientalpha.data.calendar import session_close, sessions_in_range
from sentientalpha.strategies.contracts import (
    Axis,
    Definition,
    DiscoveryError,
    Fitness,
    Request,
    Rule,
    Space,
)
from sentientalpha.strategies.evaluation import RuleStrategy, evaluate, fitness
from sentientalpha.strategies.grammar import compare, identity, validate
from sentientalpha.strategies.inputs import Inputs, Signal, freeze, thaw
from sentientalpha.strategies.research import final_evaluation, prepare
from sentientalpha.strategies.search import generate


def fixture(assets=2, candidates=12):
    days = sessions_in_range("weekday", date(2023, 1, 2), date(2023, 12, 29))
    rng = np.random.default_rng(71)
    bars, signals = [], {}
    tickers = [f"TOY{i:02d}" for i in range(assets)]
    for ticker in tickers:
        past = [100.0]
        for day in days:
            opening = past[-1] * np.exp(rng.normal(0, 0.003))
            closing = opening * np.exp(rng.normal(0, 0.01))
            ready = session_close("weekday", day) + timedelta(seconds=1)
            bars.append(
                Bar(
                    ticker,
                    day,
                    Decimal(str(opening)),
                    Decimal(str(closing)),
                    10000000,
                    ready,
                    ready,
                    ticker + str(day),
                )
            )
            signals[(day, ticker)] = {
                "return": Signal(closing / past[-1] - 1, ready, "synthetic_price"),
                "close": Signal(closing, ready, "synthetic_price"),
                "sma__window_5": Signal(
                    sum((past + [closing])[-5:]) / 5 if len(past) >= 4 else None,
                    ready,
                    "synthetic_indicator_fixture",
                ),
            }
            past.append(closing)
    # Explicit permissive selection floor exercises ledger/lock paths on noise, not alpha.
    cfg = Request(
        dataset_id="00000000-0000-0000-0000-000000000001",
        tickers=tickers,
        source_as_of=datetime(2026, 10, 17, tzinfo=UTC),
        information_policy="research_replay",
        windows=[
            Split(
                train_start=days[0],
                train_end=days[79],
                validation_start=days[80],
                validation_end=days[149],
                test_start=days[150],
                test_end=days[209],
            )
        ],
        space=Space(
            axes=[
                Axis(feature="return", thresholds=[-0.003, 0, 0.003]),
                Axis(feature="close", other_features=["sma__window_5"]),
            ],
            holdings=[1, 3, 5],
            include_exit=True,
        ),
        fitness=Fitness(minimum_sessions=20, minimum_closed_lots=2, minimum_validation_score=-5),
        candidates=candidates,
        idempotency_key="fixture_discovery_71",
        seconds=120,
    )
    return cfg, Inputs(
        Snapshot(tuple(bars)),
        signals,
        "weekday",
        {"provider": "synthetic", "synthetic": True},
        frozenset(["return", "close", "sma__window_5"]),
    )


@pytest.mark.parametrize(
    "op,left,right,expected",
    [
        ("lt", 1, 2, True),
        ("le", 2, 2, True),
        ("gt", 1, 2, False),
        ("ge", 2, 2, True),
        ("eq", 1, 1, True),
    ],
)
def test_numeric_rule_golden(op, left, right, expected):
    rule = Rule(feature="return", operator=op, threshold=right)
    assert compare(rule, lambda _: left)[0] is expected


@pytest.mark.parametrize(
    "kind,a,b,out",
    [
        ("all", True, None, None),
        ("all", False, None, False),
        ("any", True, None, True),
        ("any", False, None, None),
    ],
)
def test_missing_strong_boolean_logic(kind, a, b, out):
    rule = Rule(
        kind=kind,
        children=[
            Rule(feature="a", operator="gt", threshold=0),
            Rule(feature="b", operator="gt", threshold=0),
        ],
    )
    values = {"a": 1 if a else -1, "b": None if b is None else int(b)}
    assert compare(rule, values.get)[0] is out


@pytest.mark.parametrize(
    "payload",
    [
        {"feature": "__import__('os').system('ls')", "operator": "gt", "threshold": 0},
        {"feature": "return", "operator": "execute", "threshold": 0},
        {"feature": "return", "operator": "gt", "threshold": float("nan")},
        {"feature": "return", "operator": "gt", "threshold": 0, "other_feature": "close"},
        {"kind": "all", "children": []},
    ],
)
def test_unsafe_and_invalid_grammar_refused(payload):
    with pytest.raises(ValidationError):
        Rule.model_validate(payload)


def test_expression_depth_and_complexity_limits_and_unknown_feature():
    r = Rule(feature="return", operator="gt", threshold=0)
    r = Rule(kind="all", children=[r, r])
    r = Rule(kind="any", children=[r, r])
    with pytest.raises(ValidationError):
        Rule(kind="all", children=[r, r])
    with pytest.raises(DiscoveryError):
        validate(
            Definition(entry=Rule(feature="future_return", operator="gt", threshold=0)), {"return"}
        )


def test_commutative_duplicates_canonical_identity():
    a, b = (
        Rule(feature="a", operator="gt", threshold=0),
        Rule(feature="b", operator="gt", threshold=1),
    )
    one = Definition(entry=Rule(kind="all", children=[a, b, a]))
    two = Definition(entry=Rule(kind="all", children=[b, a]))
    assert identity(one) == identity(two)
    assert identity(Definition.model_validate({**two.model_dump(), "exposure": 1})) == identity(two)


def test_random_reproducible_grid_exhaustion_and_budget():
    cfg, _ = fixture(candidates=20)
    a, h = generate(cfg)
    assert [identity(v) for v in a] == [identity(v) for v in generate(cfg)[0]]
    assert len(a) == 20 and len(set(identity(v) for v in a)) == 20
    small = cfg.model_copy(
        update={
            "space": Space(
                axes=[Axis(feature="return", thresholds=[0, 0.1])],
                maximum_conditions=1,
                holdings=[None],
                schedules=["daily"],
            ),
            "algorithm": "grid",
        }
    )
    generated, history = generate(small)
    assert len(generated) == 2 and history["exhausted"]
    with pytest.raises(DiscoveryError):
        generate(small.model_copy(update={"candidates": 1}))


def test_independent_fitness_dimensionless_calculation_and_two_lucky_trades():
    cfg, _ = fixture()
    definition = Definition(entry=Rule(feature="return", operator="gt", threshold=0))
    m = {
        "status": "computed",
        "sharpe": 1.5,
        "maximum_drawdown": 0.1,
        "turnover": 2.0,
        "closed_lot_count": 8,
        "rolling": [{"sharpe": 1.5}] * 30,
    }
    result = {
        "status": "completed",
        "metrics": m,
        "equity": [{"reconciliation_residual": "0"}] * 60,
    }
    f = Fitness()
    c = (1 / 8 + 1 / 16 + 0 + 1 / 3) / 4
    expected = tanh(0.5) - 0.2 * 0.1 - 0.1 * tanh(2 / 5) - 0.1 * c
    assert fitness(result, {"signal_coverage": 1}, definition, f)["score"] == pytest.approx(
        expected
    )
    m["closed_lot_count"] = 2
    assert (
        "too_few_completed_lots"
        in fitness(result, {"signal_coverage": 1}, definition, f)["reasons"]
    )


def test_actual_entry_exit_holding_and_next_open_accounting():
    cfg, inputs = fixture()
    d = Definition(entry=Rule(feature="return", operator="gt", threshold=-1), holding_sessions=1)
    w = cfg.windows[0]
    result, diagnostic = evaluate(cfg, inputs, d, w.train_start, w.train_end, audit=True)
    assert result["fills"] and any(t["holding_limit_exit"] for t in diagnostic["trace"])
    orders = {o["id"]: o for o in result["orders"]}
    assert all(f["at"] > orders[f["order_id"]]["submitted_at"] for f in result["fills"])
    assert all(
        abs(Decimal(r["reconciliation_residual"])) < Decimal("1e-8") for r in result["equity"]
    )
    assert any(t["features"] for t in diagnostic["trace"])


def test_future_sentiment_and_missing_do_not_create_entries():
    cfg, inputs = fixture()
    day = cfg.windows[0].train_start
    context = Context(
        session_close(inputs.calendar, day) + timedelta(seconds=1),
        day,
        tuple((t, Decimal(100)) for t in cfg.tickers),
        (),
        (),
        Decimal(100000),
    )
    late = Signal(1.0, context.at + timedelta(days=1), "explicit_future_sentiment")
    modified = replace(
        inputs,
        signals={(day, t): {"sent_mean": late} for t in cfg.tickers},
        available=frozenset(["sent_mean"]),
    )
    adapter = RuleStrategy(
        Definition(entry=Rule(feature="sent_mean", operator="gt", threshold=0)),
        modified,
        cfg.tickers,
    )
    assert all(v == 0 for v in adapter.targets(context).values())
    assert adapter.complete == 0
    timely = replace(
        modified,
        signals={(day, t): {"sent_mean": replace(late, ready=context.at)} for t in cfg.tickers},
    )
    positive = RuleStrategy(
        Definition(entry=Rule(feature="sent_mean", operator="gt", threshold=0)), timely, cfg.tickers
    )
    assert all(v == Decimal("0.5") for v in positive.targets(context).values())


def test_changing_future_test_cannot_change_search_or_prior_decisions():
    cfg, inputs = fixture(candidates=8)
    original = prepare(cfg, inputs)
    boundary = cfg.windows[0].test_start
    changed = replace(
        inputs,
        prices=Snapshot(
            tuple(
                replace(b, close=b.close * 3) if b.day >= boundary else b
                for b in inputs.prices.bars
            )
        ),
        signals={
            k: (
                {c: replace(v, value=999.0) for c, v in values.items()}
                if k[0] >= boundary
                else values
            )
            for k, values in inputs.signals.items()
        },
    )
    assert prepare(cfg, changed) == original
    assert prepare(cfg, thaw(freeze(inputs))) == original
    assert original["selection_lock"]["selection_uses"] == "validation_fitness_only"


def test_test_based_selection_and_locked_manifest_mutation_refused():
    cfg, inputs = fixture(candidates=8)
    prepared = prepare(cfg, inputs)
    assert any(f["selected"] for f in prepared["folds"])
    prepared["folds"][0]["selected"] = "a" * 64
    with pytest.raises(DiscoveryError, match="lock"):
        final_evaluation(cfg, inputs, prepared)


def test_complex_noise_strategy_penalty_cost_sensitivity_and_negative_search():
    cfg, inputs = fixture(candidates=8)
    p = prepare(cfg, inputs)
    evaluated = final_evaluation(cfg, inputs, p)
    assert evaluated["alpha_established"] is False
    assert any("robustness" in f for f in evaluated["folds"])
    negative = cfg.model_copy(
        update={"fitness": cfg.fitness.model_copy(update={"minimum_closed_lots": 1000})}
    )
    assert prepare(negative, inputs)["status"] == "no_eligible_strategy"


def test_training_good_validation_poor_and_anomalous_security_diagnostics():
    cfg, inputs = fixture(candidates=6)
    prepared = prepare(cfg, inputs)
    for fold in prepared["folds"]:
        for c in fold["candidates"]:
            if c["status"] != "failed":
                assert c["training_validation_gap"] == pytest.approx(
                    (c["train"]["metrics"]["sharpe"] or 0)
                    - (c["validation"]["metrics"]["sharpe"] or 0)
                )
    assert all(
        c["validation"]["fitness"]["score"] is not None
        for c in prepared["folds"][0]["candidates"]
        if c["status"] == "eligible"
    )


def test_constraints_and_search_budget_request_refusal():
    cfg, _ = fixture()
    payload = cfg.model_dump()
    payload["costs"]["position_limit"] = "0.1"
    with pytest.raises(ValidationError):
        Request.model_validate(payload)
    payload = cfg.model_dump()
    payload["candidates"] = 1000
    payload["maximum_simulations"] = 100
    with pytest.raises(ValidationError):
        Request.model_validate(payload)


def test_high_training_sharpe_cannot_rescue_negative_validation(monkeypatch):
    import sentientalpha.strategies.research as research

    cfg, inputs = fixture(candidates=3)
    cfg = cfg.model_copy(
        update={"fitness": cfg.fitness.model_copy(update={"minimum_validation_score": 0.0})}
    )

    def controlled(request, inputs, definition, first, last, **kwargs):
        sharpe = 3.0 if first == request.windows[0].train_start else -2.0
        m = {
            "status": "computed",
            "sharpe": sharpe,
            "maximum_drawdown": 0.01,
            "turnover": 1.0,
            "closed_lot_count": 20,
            "rolling": [{"sharpe": sharpe}] * 30,
            "monthly_returns": [],
        }
        return {
            "status": "completed",
            "metrics": m,
            "equity": [{"reconciliation_residual": "0"}] * 60,
            "events_processed": 60,
            "fills": [],
        }, {"signal_coverage": 1.0}

    monkeypatch.setattr(research, "evaluate", controlled)
    result = prepare(cfg, inputs)
    assert result["status"] == "no_eligible_strategy"
    assert {c["status"] for c in result["folds"][0]["candidates"]} == {"validation_weakness"}


def test_anomalous_security_and_two_lot_profit_concentration_warning():
    from sentientalpha.strategies.evaluation import fragility

    result = {
        "fills": [
            {"ticker": "ANOMALY", "realized_pnl": "99"},
            {"ticker": "ORDINARY", "realized_pnl": "1"},
        ],
        "metrics": {},
    }
    f = fragility(result)
    assert f["largest_asset_positive_pnl_share"] == 0.99
    assert f["single_asset_dependence_warning"]
    assert f["top_two_positive_lots_share"] == 1
    assert f["few_trades_profit_concentration_warning"]


def test_profitable_path_loses_under_high_commissions():
    cfg, inputs = fixture()
    from sentientalpha.backtesting.contracts import Costs

    days = sorted({b.day for b in inputs.prices.bars})
    lookup = {d: i for i, d in enumerate(days)}
    bars = tuple(
        replace(
            b,
            opening=Decimal("100") * Decimal("1.005") ** lookup[b.day],
            close=Decimal("100") * Decimal("1.005") ** (lookup[b.day] + 1),
        )
        for b in inputs.prices.bars
    )
    monotone = replace(inputs, prices=Snapshot(bars))
    definition = Definition(
        entry=Rule(feature="return", operator="gt", threshold=-1), holding_sessions=1
    )
    w = cfg.windows[0]
    low, _ = evaluate(
        cfg.model_copy(update={"costs": Costs(fixed=Decimal(0), slippage_bps=Decimal(0))}),
        monotone,
        definition,
        w.train_start,
        w.train_end,
    )
    high, _ = evaluate(
        cfg.model_copy(update={"costs": Costs(fixed=Decimal(1000), slippage_bps=Decimal(0))}),
        monotone,
        definition,
        w.train_start,
        w.train_end,
    )
    assert low["metrics"]["total_return"] > 0
    assert high["metrics"]["total_return"] < 0


def test_extreme_parameter_sensitivity_can_remove_all_trades():
    cfg, inputs = fixture()
    first, last = cfg.windows[0].validation_start, cfg.windows[0].validation_end
    definition = Definition(
        entry=Rule(feature="return", operator="gt", threshold=-0.001), holding_sessions=1
    )
    perturbed = definition.model_copy(
        update={"entry": Rule(feature="return", operator="gt", threshold=1)}
    )
    base, _ = evaluate(cfg, inputs, definition, first, last)
    alternative, _ = evaluate(cfg, inputs, perturbed, first, last)
    assert base["fills"] and alternative["fills"] == []
    assert alternative["metrics"]["sharpe"] is None


def test_purged_windows_and_independent_walk_forward_no_overlap():
    cfg, inputs = fixture(candidates=5)
    from sentientalpha.backtesting.evaluation import WalkRequest
    from sentientalpha.strategies.evaluation import config

    days = sorted({d for d, _ in inputs.signals})
    walk = WalkRequest(
        backtest=config(cfg, inputs, days[0], days[-1]),
        train_sessions=60,
        validation_sessions=40,
        test_sessions=30,
        step_sessions=30,
        maximum_folds=8,
    )
    windows = walk.folds(days)
    req = Request.model_validate({**cfg.model_dump(), "windows": windows})
    result = prepare(req, inputs)
    forward = final_evaluation(req, inputs, result)
    oos = [r["day"] for r in forward["oos_return_index"]]
    assert len(oos) == len(set(oos))
    assert forward["capital_policy"].startswith("Independent")
    assert all(
        f["selection_hash"] == result["selection_hash"]
        for f in forward["folds"]
        if "selection_hash" in f
    )


def test_m5_projection_respects_active_set_risk_inputs_and_timestamp():
    from sentientalpha.optimization.contracts import Constraints
    from sentientalpha.optimization.estimation import Estimates
    from sentientalpha.strategies.allocation import project_active

    at = datetime(2023, 1, 3, tzinfo=UTC)
    estimates = Estimates(
        ("AAA", "BBB"),
        np.zeros(2),
        np.eye(2) * 0.04,
        {"provenance": "synthetic covariance fixture"},
    )
    result = project_active(
        estimates,
        {"AAA": True, "BBB": False},
        Constraints(concentration=0.6, cash_maximum=1),
        at,
        at,
    )
    assert result["weights"]["AAA"] == pytest.approx(0.6, abs=2e-7)
    assert result["weights"]["BBB"] == pytest.approx(0, abs=2e-7)
    with pytest.raises(DiscoveryError):
        project_active(
            estimates, {"AAA": True, "BBB": False}, Constraints(), at, at + timedelta(days=1)
        )


def test_late_cross_asset_observation_cannot_rewind_holding_state():
    cfg, inputs = fixture()
    days = sorted({day for day, _ in inputs.signals})
    definition = Definition(
        entry=Rule(feature="return", operator="gt", threshold=-1), holding_sessions=5
    )
    adapter = RuleStrategy(definition, inputs, cfg.tickers)
    at = session_close(inputs.calendar, days[10]) + timedelta(seconds=1)
    current = Context(
        at,
        days[10],
        tuple((t, Decimal(100)) for t in cfg.tickers),
        (),
        tuple((t, Decimal(1)) for t in cfg.tickers),
        Decimal(1000),
    )
    adapter.targets(current)
    since = dict(adapter.since)
    assert adapter.targets(replace(current, day=days[2])) == {}
    assert adapter.since == since and adapter.last_observation == days[10]
