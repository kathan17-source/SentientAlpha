"""Independent finite-sample references and adversarial risk inputs, explicitly synthetic."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest
from pydantic import ValidationError
from sentientalpha.data.calendar import sessions_in_range
from sentientalpha.optimization.contracts import Constraints, Estimator
from sentientalpha.risk.analytics import analyse, tails
from sentientalpha.risk.contracts import (
    Equity,
    EvaluationRequest,
    Order,
    Policy,
    PortfolioState,
    Price,
    ReturnObservation,
    Scenario,
    VolumeObservation,
)
from sentientalpha.risk.governance import control, evaluate

AT = datetime(2025, 1, 1, 0, 0, 1, tzinfo=UTC)


def fixture(**policy_updates):
    days = sessions_in_range("weekday", date(2024, 1, 2), date(2024, 12, 31))
    rng = np.random.default_rng(97)
    x = rng.normal([0.0002, 0.0001], [0.012, 0.017], (len(days), 2))
    rows = [
        ReturnObservation(
            day=d,
            available_at=datetime.combine(d, datetime.min.time(), tzinfo=UTC) + timedelta(hours=23),
            values={"AAA": float(a), "BBB": float(b)},
            source="synthetic-return-fixture",
        )
        for d, (a, b) in zip(days, x, strict=True)
    ]
    state = PortfolioState(
        portfolio_id="fixture",
        at=AT,
        valuation_at=AT,
        cash=Decimal(80000),
        equity=Decimal(100000),
        quantities={"AAA": Decimal(1000), "BBB": Decimal(500)},
        calendar="weekday",
        provenance="synthetic_fixture",
        prices=[
            Price(
                ticker=t,
                asset_id=t,
                value=Decimal(v),
                observed_at=AT,
                available_at=AT,
                source="synthetic-quote",
            )
            for t, v in [("AAA", 10), ("BBB", 20)]
        ],
        equity_history=[Equity(at=AT - timedelta(days=10), value=Decimal(100000))],
    )
    policy = Policy.model_validate(
        {
            "effective_at": datetime(2023, 1, 1, tzinfo=UTC),
            "estimator": Estimator(covariance="sample", lookback=252, minimum_observations=60),
            **policy_updates,
        }
    )
    volumes = [
        VolumeObservation(
            ticker=t,
            day=d,
            available_at=r.available_at,
            volume=100000,
            close=p,
            source="synthetic-volume",
        )
        for d, r in zip(days[-20:], rows[-20:], strict=True)
        for t, p in [("AAA", 10), ("BBB", 20)]
    ]
    return EvaluationRequest(
        state=state,
        policy=policy,
        returns=rows,
        volumes=volumes,
        targets={"AAA": 0.2, "BBB": 0.2},
        idempotency_key="risk-math-fixture",
    )


@pytest.mark.parametrize(
    "confidence,expected_var,expected_es",
    [(0.5, 0.02, 0.035), (0.75, 0.03, 0.04), (0.625, 0.03, 0.055 / 1.5)],
)
def test_fractional_tail_mass_against_hand_calculation(confidence, expected_var, expected_es):
    result = tails(np.array([-0.01, -0.02, -0.03, -0.04]), confidence, 100000, 1)
    assert result["var_loss_fraction"] == pytest.approx(expected_var)
    assert result["cvar_loss_fraction"] == pytest.approx(expected_es)
    assert result["cvar_currency"] == pytest.approx(100000 * expected_es)


def test_ties_constant_and_negative_loss_convention():
    assert tails(np.zeros(100), 0.95, 100000, 5)["cvar_loss_fraction"] == 0
    result = tails(np.full(100, 0.01), 0.95, 100000, 5)
    assert result["var_loss_fraction"] == -0.01 and result["cvar_loss_fraction"] == pytest.approx(
        -0.01
    )
    assert tails(np.array([-0.1] * 5 + [0] * 95), 0.95, 100000, 5)[
        "cvar_loss_fraction"
    ] == pytest.approx(0.1)


def test_covariance_exposure_and_risk_attribution_independent_reference():
    req = fixture()
    report = analyse(req)
    exp = report["exposure"]
    v = report["volatility"]
    assert exp["market_values"] == {"AAA": 10000, "BBB": 10000}
    assert exp["cash_weight"] == pytest.approx(0.8)
    assert exp["hhi_equity_weights"] == pytest.approx(0.02)
    assert exp["effective_holdings_invested"] == pytest.approx(2)
    x = np.array([[r.values["AAA"], r.values["BBB"]] for r in req.returns[-252:]])
    cov = np.cov(x, rowvar=False, ddof=1) * 252
    w = np.array([0.1, 0.1])
    vol = np.sqrt(w @ cov @ w)
    assert v["estimated_annual"] == pytest.approx(vol)
    assert sum(v["component_volatility"].values()) == pytest.approx(vol)
    assert sum(v["percentage_volatility"].values()) == pytest.approx(1)
    assert v["historical_annual"] == pytest.approx(np.std(x @ w, ddof=1) * np.sqrt(252))


@pytest.mark.parametrize(
    "policy",
    [
        {"constraints": Constraints(cash_maximum=1, concentration=0.1)},
        {
            "constraints": Constraints(
                cash_maximum=1, sectors={"AAA": "tech", "BBB": "tech"}, sector_maximum={"tech": 0.3}
            )
        },
        {"constraints": Constraints(cash_maximum=1, volatility_maximum=0.001)},
        {"var_maximum": 0.0001},
        {"cvar_maximum": 0.0001},
        {"participation_maximum": 0.000001},
        {"minimum_dollar_volume": 1e9},
        {"cost_fraction_maximum": 0.0},
    ],
)
def test_hard_limits_never_fail_open(policy):
    result = evaluate(fixture(**policy))
    assert not result["executable"] and result["approved_targets"] is None
    assert result["violations"] and result["override_permitted"] is False


def test_missing_tail_history_rejects_required_risk():
    req = fixture(var_maximum=0.05)
    req = req.model_copy(update={"returns": req.returns[-60:]})
    result = evaluate(req)
    assert result["status"] == "INSUFFICIENT_RISK_DATA"
    assert result["proposed"]["tail"]["status"] == "INSUFFICIENT_TAIL_DATA"


def test_scaled_allocation_passes_complete_policy_not_individual_clipping():
    req = fixture(var_maximum=0.001, adjustment="scale_to_cash")
    result = evaluate(req)
    assert result["status"] == "APPROVED_WITH_REDUCTION" and result["executable"]
    final = req.model_copy(
        update={
            "targets": result["approved_targets"],
            "policy": req.policy.model_copy(update={"adjustment": "reject"}),
        }
    )
    assert evaluate(final)["status"] == "APPROVED"
    impossible = fixture(
        constraints=Constraints(cash_maximum=0.1, concentration=0.4), adjustment="scale_to_cash"
    )
    assert not evaluate(impossible)["executable"]


@pytest.mark.parametrize("change", ["stale", "future", "missing", "adjusted", "suspended"])
def test_missing_stale_or_incompatible_quotes_reject(change):
    req = fixture()
    prices = list(req.state.prices)
    updates = (
        {"observed_at": AT - timedelta(days=8)}
        if change == "stale"
        else {"available_at": AT + timedelta(days=1)}
        if change == "future"
        else {"value": None}
        if change == "missing"
        else {"basis": "adjusted"}
        if change == "adjusted"
        else {"suspended": True}
    )
    prices[0] = prices[0].model_copy(update=updates)
    req = req.model_copy(update={"state": req.state.model_copy(update={"prices": prices})})
    assert not evaluate(req)["executable"]


def test_singular_covariance_and_perfect_correlation_are_not_hidden_by_regularization():
    req = fixture(constraints=Constraints(cash_maximum=1, volatility_maximum=1))
    rows = [
        r.model_copy(update={"values": {"AAA": r.values["AAA"], "BBB": r.values["AAA"]}})
        for r in req.returns
    ]
    result = evaluate(req.model_copy(update={"returns": rows}))
    assert not result["executable"]
    assert not result["proposed"]["volatility"]["raw_covariance_reliable"]
    assert result["proposed"]["volatility"]["raw_correlation"][0][1] == pytest.approx(1)


def test_cash_only_is_exact_zero_risk_without_fabricated_covariance():
    req = fixture()
    state = req.state.model_copy(update={"quantities": {}, "cash": Decimal(100000)})
    req = req.model_copy(update={"state": state, "returns": [], "targets": {"AAA": 0, "BBB": 0}})
    result = evaluate(req)
    assert result["current"]["tail"]["status"] == "EXACT_ZERO_EXPOSURE"
    assert result["current"]["tail"]["var_loss_fraction"] == 0
    assert result["current"]["volatility"]["estimated_annual"] == 0
    assert result["executable"]


def test_future_returns_never_change_prior_var():
    req = fixture()
    before = analyse(req)
    future = ReturnObservation(
        day=date(2025, 1, 2),
        available_at=AT + timedelta(days=2),
        values={"AAA": -0.99, "BBB": -0.99},
        source="future-fixture",
    )
    after = analyse(req.model_copy(update={"returns": [*req.returns, future]}))
    assert after["tail"] == before["tail"]


def test_drawdown_is_past_realized_path_and_latches_until_explicit_recovery():
    req = fixture(drawdown_maximum=0.05)
    history = [
        Equity(at=AT - timedelta(days=3), value=Decimal(100000)),
        Equity(at=AT - timedelta(days=2), value=Decimal(90000)),
        Equity(at=AT - timedelta(days=1), value=Decimal(100000)),
    ]
    req = req.model_copy(update={"state": req.state.model_copy(update={"equity_history": history})})
    assert control(req)["state"] == "HALTED"
    recovering = req.model_copy(
        update={
            "policy": req.policy.model_copy(
                update={"recovery_observations": 2, "recovery_drawdown": 0.01}
            )
        }
    )
    assert control(recovering)["state"] == "ACTIVE"
    with pytest.raises(ValidationError, match="Future equity"):
        EvaluationRequest.model_validate(
            {
                **req.model_dump(),
                "state": {
                    **req.state.model_dump(),
                    "equity_history": [Equity(at=AT + timedelta(days=1), value=Decimal(1000000))],
                },
            }
        )


def test_explicit_orders_check_cash_and_negative_holdings():
    req = fixture()
    req = req.model_copy(
        update={
            "targets": None,
            "orders": [Order(ticker="AAA", side="buy", quantity=Decimal(100000))],
        }
    )
    result = evaluate(req)
    assert not result["executable"] and any(v["metric"] == "cash" for v in result["violations"])
    assert not evaluate(
        req.model_copy(
            update={"orders": [Order(ticker="AAA", side="sell", quantity=Decimal(2000))]}
        )
    )["executable"]


def test_stress_uses_declared_shocks_and_contributions_not_predictions():
    scenario = Scenario(
        id="shock",
        version="1",
        effective_at=datetime(2023, 1, 1, tzinfo=UTC),
        broad_shock=-0.05,
        assets={"BBB": -0.1},
    )
    req = fixture(scenarios=[scenario])
    report = analyse(req)
    shock = report["stress"][0]
    assert shock["loss_currency"] == pytest.approx(1500)
    assert sum(shock["asset_loss_contributions"].values()) == pytest.approx(1500)
    with pytest.raises(ValidationError):
        Scenario(id="bad", version="1", effective_at=AT, broad_shock=float("inf"))


def test_policy_code_nan_future_versions_and_unsupported_units_rejected():
    req = fixture()
    with pytest.raises(ValidationError, match="Conflicting explicit asset bounds"):
        Policy(effective_at=AT, constraints=Constraints(minimum={"AAA": 0.8}, maximum={"AAA": 0.2}))
    huge = Scenario(
        id="unbounded",
        version="1",
        effective_at=req.policy.effective_at,
        kind="historical",
        start=date(1, 1, 1),
        end=date(2024, 12, 31),
    )
    with pytest.raises(ValidationError, match="budget"):
        EvaluationRequest.model_validate(
            {
                **req.model_dump(),
                "policy": {**req.policy.model_dump(), "scenarios": [huge.model_dump()]},
            }
        )
    with pytest.raises(ValidationError):
        Policy.model_validate({**req.policy.model_dump(), "execute": '__import__("os")'})
    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate({**req.model_dump(), "targets": {"AAA": float("nan")}})
    with pytest.raises(ValidationError):
        EvaluationRequest.model_validate(
            {
                **req.model_dump(),
                "policy": {**req.policy.model_dump(), "effective_at": AT + timedelta(days=1)},
            }
        )
    with pytest.raises(ValidationError):
        Price.model_validate({**req.state.prices[0].model_dump(), "asset_type": "option"})


def test_reduction_or_fees_cannot_create_another_concentration_breach():
    req = fixture(constraints=Constraints(cash_maximum=1, maximum={"BBB": 0.1}))
    req = req.model_copy(update={"targets": {"AAA": 0, "BBB": 0.1}})
    result = evaluate(req)
    assert not result["executable"]
    assert any(v["metric"] == "M5:maximum_asset_weight" for v in result["violations"])


def test_nearly_correlated_and_zero_volatility_inputs_have_explicit_outcomes():
    req = fixture(correlation_maximum=0.9)
    rows = [
        r.model_copy(
            update={
                "values": {
                    "AAA": r.values["AAA"],
                    "BBB": float(r.values["AAA"]) + 0.00000001 * (i % 2),
                }
            }
        )
        for i, r in enumerate(req.returns)
    ]
    assert not evaluate(req.model_copy(update={"returns": rows}))["executable"]
    zero = [r.model_copy(update={"values": {"AAA": 0.0, "BBB": 0.0}}) for r in req.returns]
    result = analyse(req.model_copy(update={"returns": zero}))
    assert result["volatility"]["estimated_annual"] < 0.0001
    assert result["volatility"]["raw_covariance_reliable"] is False
    assert result["tail"]["cvar_loss_fraction"] == 0


def test_historical_scenarios_require_exact_eligible_coverage():
    req = fixture()
    days = [r.day for r in req.returns]
    s = Scenario(
        id="past",
        version="1",
        effective_at=req.policy.effective_at,
        kind="historical",
        start=days[-5],
        end=days[-1],
    )
    req = req.model_copy(update={"policy": req.policy.model_copy(update={"scenarios": [s]})})
    report = analyse(req)
    scenario = report["stress"][0]
    assert scenario["status"] == "CALCULATED" and scenario["sessions"] == 5
    expected = sum(
        -10000 * (np.prod([1 + r.values[t] for r in req.returns[-5:]]) - 1) for t in ["AAA", "BBB"]
    )
    assert scenario["loss_currency"] == pytest.approx(expected)
    late = req.returns[-1].model_copy(update={"available_at": AT + timedelta(days=1)})
    future = req.model_copy(update={"returns": [*req.returns[:-1], late]})
    assert analyse(future)["stress"][0]["status"] == "UNAVAILABLE"


def test_benchmark_relative_beta_and_tracking_error_use_actual_return_panel():
    req = fixture(
        constraints=Constraints(cash_maximum=1, benchmark_weights={"AAA": 0.5, "BBB": 0.5})
    )
    report = analyse(req)["volatility"]
    assert report["benchmark_beta"] == pytest.approx(0.2)
    assert report["active_weights"] == {"AAA": -0.4, "BBB": -0.4}
    assert report["tracking_error_annual"] > report["estimated_annual"]


def test_exception_diagnostics_cannot_use_future_or_tiny_samples_as_validation():
    from sentientalpha.risk.validation import ForecastOutcome, exception_diagnostics

    rows = [
        ForecastOutcome(
            portfolio_id="test",
            policy_version="1",
            forecast_at=AT - timedelta(days=300 - i),
            outcome_at=AT - timedelta(days=299 - i),
            available_at=AT - timedelta(days=299 - i),
            confidence=0.95,
            var_loss_fraction=0.02,
            realized_loss_fraction=0.03 if i % 20 == 0 else 0.01,
            reliable_sample=True,
        )
        for i in range(250)
    ]
    result = exception_diagnostics(rows, AT)
    assert result["status"] == "DESCRIPTIVE_BINOMIAL_DIAGNOSTIC"
    assert result["qualified_exceptions"] == 13
    assert 0 <= result["binomial_pvalue"] <= 1
    small = exception_diagnostics(rows[:5], AT)
    assert small["status"] == "INSUFFICIENT_VALIDATION_SAMPLE" and small["binomial_pvalue"] is None
    assert exception_diagnostics(rows, AT - timedelta(days=301))["matured"] == 0


def test_adjusted_returns_and_missing_sector_classifications_fail_closed():
    req = fixture(
        constraints=Constraints(
            cash_maximum=1, sectors={"AAA": "tech"}, sector_maximum={"tech": 0.8}
        )
    )
    assert not evaluate(req)["executable"]
    with pytest.raises(ValidationError, match="Adjusted returns"):
        EvaluationRequest.model_validate(
            {
                **req.model_dump(),
                "returns": [req.returns[0].model_copy(update={"basis": "adjusted"})],
            }
        )


def test_pending_buys_are_counted_and_pending_sales_do_not_create_cash():
    req = fixture()
    state = req.state.model_copy(
        update={"pending_orders": [Order(ticker="AAA", side="buy", quantity=Decimal(9000))]}
    )
    result = evaluate(req.model_copy(update={"state": state, "targets": None}))
    assert not result["executable"]
    assert any(v["metric"] == "cash" for v in result["violations"])
    state = req.state.model_copy(
        update={"pending_orders": [Order(ticker="BBB", side="sell", quantity=Decimal(500))]}
    )
    result = evaluate(
        req.model_copy(
            update={
                "state": state,
                "targets": None,
                "orders": [Order(ticker="AAA", side="buy", quantity=Decimal(8500))],
            }
        )
    )
    assert not result["executable"]


def test_later_policy_effective_time_cannot_govern_earlier_state():
    req = fixture()
    with pytest.raises(ValidationError, match="Future policy"):
        EvaluationRequest.model_validate(
            {
                **req.model_dump(),
                "policy": {**req.policy.model_dump(), "effective_at": AT + timedelta(days=1)},
            }
        )
