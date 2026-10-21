"""Independent analytical portfolios and numerical/adversarial references."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from pydantic import ValidationError
from sentientalpha.optimization.contracts import (
    Constraints,
    Estimator,
    Group,
    Objective,
)
from sentientalpha.optimization.estimation import (
    Estimates,
    OptimizationError,
    Panel,
    ReturnRow,
    covariance_checked,
    estimate,
)
from sentientalpha.optimization.solver import risk, solve

CUTOFF = datetime(2024, 12, 31, tzinfo=UTC)


def inputs(cov=None, mean=None):
    return Estimates(
        ("AAA", "BBB"),
        np.array(mean or [0.1, 0.2]),
        np.diag([0.04, 0.09]) if cov is None else np.array(cov, dtype=float),
        {},
    )


@pytest.mark.parametrize(
    "method,expected",
    [
        ("equal_weight", 0.5),
        ("minimum_variance", 9 / 13),
        ("mean_variance", 8 / 13),
        ("maximum_sharpe", 9 / 17),
        ("risk_parity", 0.6),
    ],
)
def test_independently_solved_two_asset_portfolios(method, expected):
    # Diagonal covariance: MVP inverse variance; MVO derivative; tangency inverse Sigma mu;
    # ERC inverse volatility. Expected constants are independent closed-form references.
    result = solve(inputs(), Constraints(), Objective(method=method, risk_aversion=5), {})
    assert result["status"] == "completed", result
    assert result["weights"]["AAA"] == pytest.approx(expected, abs=2e-5)
    assert result["weights"]["BBB"] == pytest.approx(1 - expected, abs=2e-5)
    assert result["diagnostics"]["maximum_constraint_violation"] <= 2e-7
    if method == "risk_parity":
        assert list(result["risk"]["percentage_risk_contributions"].values()) == pytest.approx(
            [0.5, 0.5], abs=1e-5
        )


def test_risk_contributions_add_to_volatility_and_units():
    e = inputs()
    w = np.array([0.6, 0.4])
    r = risk(w, e, np.zeros(2), Objective(), Constraints())
    # .6²*.04 + .4²*.09 = .0288; each variance contribution=.0144.
    assert r["variance"] == pytest.approx(0.0288)
    assert sum(r["risk_contributions"].values()) == pytest.approx(np.sqrt(0.0288))
    assert r["expected_return"] == pytest.approx(0.14)
    with pytest.raises(OptimizationError, match="units"):
        solve(replace(e, units="daily"), Constraints(), Objective(), {})


@pytest.mark.parametrize(
    "c",
    [
        Constraints(concentration=0.4),
        Constraints(minimum={"AAA": 0.8, "BBB": 0.8}),
        Constraints(restricted=["AAA", "BBB"]),
        Constraints(groups={"both": Group(members=["AAA", "BBB"], maximum=0.2)}),
    ],
)
def test_conflicting_constraints_never_silently_return_weights(c):
    result = solve(inputs(), c, Objective(), {})
    assert result["status"] == "infeasible" and result["weights"] is None


@pytest.mark.parametrize(
    "c",
    [
        Constraints(maximum={"AAA": 0.4}),
        Constraints(groups={"group": Group(members=["AAA"], maximum=0.4)}),
        Constraints(sectors={"AAA": "tech", "BBB": "energy"}, sector_maximum={"tech": 0.4}),
    ],
)
def test_asset_group_sector_caps(c):
    result = solve(inputs(), c, Objective(), {})
    assert result["weights"]["AAA"] == pytest.approx(0.4, abs=1e-6)
    assert result["weights"]["BBB"] == pytest.approx(0.6, abs=1e-6)


def test_cash_and_restrictions_are_explicit():
    result = solve(inputs(), Constraints(cash_maximum=1), Objective(), {})
    assert result["cash_weight"] == pytest.approx(1, abs=1e-6)
    assert result["risk"]["sharpe"] is None
    result = solve(inputs(), Constraints(restricted=["AAA"]), Objective(), {})
    assert result["weights"] == pytest.approx({"AAA": 0, "BBB": 1}, abs=1e-6)
    with pytest.raises(OptimizationError, match="fixed invested"):
        solve(inputs(), Constraints(cash_maximum=1), Objective(method="risk_parity"), {})


def test_turnover_includes_cash_and_cost_penalties():
    e = inputs(mean=[0.01, 0.9])
    c = Constraints(turnover_maximum=0.05)
    result = solve(
        e, c, Objective(method="mean_variance", risk_aversion=0.1), {"AAA": 0.7, "BBB": 0.3}
    )
    assert result["weights"]["AAA"] == pytest.approx(0.65, abs=1e-5)
    assert result["risk"]["turnover"] <= 0.0500002
    # All-cash->fully invested is 100% one-way turnover, not 50%.
    bad = solve(e, Constraints(turnover_maximum=0.9), Objective(), {})
    assert bad["status"] == "infeasible"
    expensive = solve(
        e,
        Constraints(),
        Objective(
            method="mean_variance", risk_aversion=0.1, asset_cost_rates={"AAA": 0.1, "BBB": 0.1}
        ),
        {"AAA": 0.7, "BBB": 0.3},
    )
    assert expensive["risk"]["turnover"] < result["risk"]["turnover"] + 1e-4


def test_risk_tracking_and_target_return_constraints():
    e = inputs()
    result = solve(e, Constraints(volatility_maximum=0.19), Objective(), {})
    assert result["weights"] is not None and result["risk"]["volatility"] <= 0.1900002
    c = Constraints(benchmark_weights={"AAA": 0.5, "BBB": 0.5}, tracking_error_maximum=0.001)
    result = solve(e, c, Objective(), {})
    assert result["weights"] is not None and result["risk"]["tracking_error"] <= 0.00101
    impossible = solve(e, Constraints(), Objective(target_return_annual=0.3), {})
    assert impossible["status"] == "infeasible"
    result = solve(e, Constraints(), Objective(target_return_annual=0.18), {})
    assert result["risk"]["expected_return"] >= 0.18 - 2e-7


@pytest.mark.parametrize(
    "cov",
    [
        [[1, 1], [1, 1]],
        [[0.04, 0.059999999], [0.059999999, 0.09]],
        [[1e-12, 0], [0, 1]],
        [[0, 0], [0, 0]],
    ],
)
def test_singular_correlated_and_different_volatility(cov):
    matrix, audit = covariance_checked(np.array(cov, dtype=float), 1e-10)
    assert np.linalg.eigvalsh(matrix).min() >= -1e-12
    result = solve(inputs(cov=matrix), Constraints(), Objective(), {})
    assert result["weights"] is not None and np.isfinite(result["risk"]["variance"])
    assert audit["eigenvalue_adjustment_total"] >= 0


@pytest.mark.parametrize(
    "cov", [[[1, 2], [2, 1]], [[1, np.nan], [np.nan, 1]], [[1, 0.2], [0.3, 1]]]
)
def test_invalid_covariance_refused(cov):
    with pytest.raises(OptimizationError):
        covariance_checked(np.array(cov), 0)


@pytest.mark.parametrize("method", ["maximum_sharpe", "risk_parity"])
def test_zero_variance_risk_objective_is_not_fake_success(method):
    result = solve(inputs(cov=np.zeros((2, 2))), Constraints(), Objective(method=method), {})
    assert result["status"] == "insufficient_data" and result["weights"] is None


def test_constrained_risk_parity_reports_nonzero_residual():
    result = solve(inputs(), Constraints(maximum={"AAA": 0.2}), Objective(method="risk_parity"), {})
    assert result["weights"]["AAA"] <= 0.2000002
    assert result["risk"]["risk_parity_residual"] > 0.1


def test_solver_failure_and_invalid_output_are_not_success():
    fake = SimpleNamespace(
        x=np.r_[0.5, 0.5, 1, 1, 1], fun=0, status=9, success=False, message="iteration limit", nit=1
    )
    with patch("scipy.optimize.minimize", return_value=fake):
        result = solve(inputs(), Constraints(), Objective(), {})
    assert result["status"] == "solver_failed" and result["weights"] is None
    fake.success = True
    fake.x = np.array([np.nan] * 5)
    with patch("scipy.optimize.minimize", return_value=fake):
        result = solve(inputs(), Constraints(), Objective(), {})
    assert result["weights"] is None


def test_explicit_fallback_preserves_failed_method():
    from scipy.optimize import minimize as actual

    count = 0

    def fail_first(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 1:
            return SimpleNamespace(
                x=np.r_[0.5, 0.5, 1, 1, 1],
                fun=0,
                status=9,
                success=False,
                message="controlled failure",
                nit=1,
            )
        return actual(*args, **kwargs)

    with patch("scipy.optimize.minimize", side_effect=fail_first):
        result = solve(
            inputs(), Constraints(), Objective(method="mean_variance", fallback="equal_weight"), {}
        )
    assert result["status"] == "fallback" and result["requested_method"] == "mean_variance"
    assert result["weights"] == pytest.approx({"AAA": 0.5, "BBB": 0.5}, abs=1e-6)


def panel():
    start = date(2024, 1, 1)
    values = [
        (0.01, 0.02),
        (0.03, 0.01),
        (-0.01, 0.00),
        (0.02, -0.01),
        (0.00, 0.03),
        (0.04, 0.02),
        (-0.02, -0.02),
        (0.01, 0.01),
        (0.02, 0.01),
        (0.01, 0.00),
    ]
    return Panel(
        ("AAA", "BBB"),
        tuple(
            ReturnRow(
                start + timedelta(days=i),
                tuple(v),
                (datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=i + 1),) * 2,
            )
            for i, v in enumerate(values)
        ),
        "weekday",
    )


@pytest.mark.parametrize("mean", ["historical", "exponential", "shrinkage"])
@pytest.mark.parametrize("cov", ["sample", "exponential", "diagonal_shrinkage"])
def test_estimation_formulas_independent(mean, cov):
    p = panel()
    config = Estimator(
        mean=mean,
        covariance=cov,
        minimum_observations=5,
        lookback=10,
        decay=0.8,
        shrinkage=0.25,
        eigenvalue_floor=0,
    )
    e = estimate(p, CUTOFF, date(2024, 1, 1), date(2024, 1, 10), config)
    x = np.array([r.values for r in p.rows])
    w = 0.8 ** np.arange(9, -1, -1)
    w /= sum(w)
    expected = (
        x.mean(axis=0)
        if mean == "historical"
        else w @ x
        if mean == "exponential"
        else 0.75 * x.mean(axis=0)
    )
    assert e.mean == pytest.approx(expected * 252)
    if cov == "exponential":
        expected_cov = sum(
            wi * np.outer(xi - w @ x, xi - w @ x) for wi, xi in zip(w, x, strict=True)
        ) / (1 - sum(w * w))
    else:
        expected_cov = np.cov(x, rowvar=False, ddof=1)
        if cov == "diagonal_shrinkage":
            expected_cov = 0.75 * expected_cov + 0.25 * np.diag(np.diag(expected_cov))
    assert e.covariance == pytest.approx(expected_cov * 252)


def test_future_prices_covariance_and_ingestion_cannot_enter_estimate():
    p = panel()
    at = datetime(2024, 1, 8, tzinfo=UTC)
    config = Estimator(minimum_observations=5, lookback=10)
    original = estimate(p, at, date(2024, 1, 1), date(2024, 1, 10), config)
    altered = replace(
        p, rows=tuple(replace(r, values=(900.0, 800.0)) if r.ready[0] > at else r for r in p.rows)
    )
    changed = estimate(altered, at, date(2024, 1, 1), date(2024, 1, 10), config)
    assert np.array_equal(original.mean, changed.mean) and np.array_equal(
        original.covariance, changed.covariance
    )
    late = replace(
        p, rows=tuple(replace(r, ready=(CUTOFF + timedelta(days=1),) * 2) for r in p.rows)
    )
    with pytest.raises(OptimizationError, match="Insufficient"):
        estimate(late, at, date(2024, 1, 1), date(2024, 1, 10), config)


def test_missing_rows_not_imputed_and_repeatable_weights():
    p = panel()
    p = replace(p, rows=(replace(p.rows[0], values=(None, 0.02)),) + p.rows[1:])
    e = estimate(
        p,
        CUTOFF,
        date(2024, 1, 1),
        date(2024, 1, 10),
        Estimator(minimum_observations=5, lookback=10),
    )
    assert e.metadata["observations"] == 9
    one = solve(e, Constraints(), Objective(), {})
    two = solve(e, Constraints(), Objective(), {})
    assert one["weights"] == two["weights"]


@pytest.mark.parametrize(
    "bad",
    [
        {"concentration": -1},
        {"cash_minimum": 0.8, "cash_maximum": 0.2},
        {"tracking_error_maximum": 0.1},
        {"sector_maximum": {"unknown": 0.2}},
        {"arbitrary_risk_agent": "approve"},
    ],
)
def test_invalid_constraint_contracts(bad):
    with pytest.raises(ValidationError):
        Constraints(**bad)


def test_cash_risk_free_return_participates_in_frontier_target():
    result = solve(
        inputs(),
        Constraints(cash_maximum=1),
        Objective(target_return_annual=0.03, risk_free_annual=0.05),
        {},
    )
    assert result["weights"] is not None
    assert result["cash_weight"] == pytest.approx(1, abs=1e-6)
    assert result["risk"]["expected_return"] == pytest.approx(0.05, abs=1e-6)


def test_variance_limits_are_checked_relatively_at_tiny_scales():
    result = solve(
        inputs(cov=np.diag([1e-8, 2e-8])), Constraints(variance_maximum=1e-12), Objective(), {}
    )
    assert (
        result["weights"] is None
    )  # Impossible fully invested cap must not pass absolute 2e-7 slack.


def test_exposure_cash_conflict_is_explicit():
    result = solve(inputs(), Constraints(invested_maximum=0.5), Objective(), {})
    assert result["status"] == "infeasible" and result["weights"] is None


def test_equal_weight_cash_mode_does_not_allocate_cash_for_restricted_assets():
    result = solve(
        inputs(),
        Constraints(cash_maximum=1, restricted=["AAA"]),
        Objective(method="equal_weight"),
        {},
    )
    assert result["weights"] == pytest.approx({"AAA": 0, "BBB": 1}, abs=1e-6)
    assert result["cash_weight"] == pytest.approx(0, abs=1e-6)


@pytest.mark.parametrize("method", ["maximum_sharpe", "risk_parity"])
def test_cash_only_or_zero_variance_component_has_no_risk_objective(method):
    for e, c in (
        (inputs(), Constraints(cash_minimum=1, cash_maximum=1)),
        (inputs(cov=np.diag([0.0, 0.09])), Constraints()),
    ):
        result = solve(e, c, Objective(method=method), {})
        assert result["status"] == "insufficient_data" and result["weights"] is None
