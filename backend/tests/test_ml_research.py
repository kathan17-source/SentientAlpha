"""Independent numeric references and adversarial chronological ML checks."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest
from pydantic import ValidationError
from sentientalpha.backtesting.contracts import Bar, Snapshot
from sentientalpha.backtesting.storage import digest
from sentientalpha.data.calendar import session_close, sessions_in_range
from sentientalpha.features.timing import next_open
from sentientalpha.ml.contracts import Candidate, MLException, ResearchRequest, Target, Window
from sentientalpha.ml.dataset import Dataset, Observation, freeze, label, thaw
from sentientalpha.ml.evaluation import calibrate, fit_calibration, metrics
from sentientalpha.ml.integration import economic, forecast_estimates
from sentientalpha.ml.models import infer, train, transform
from sentientalpha.ml.research import ablations, evaluate, inference_guard, matrix, partition
from sentientalpha.optimization.estimation import Estimates


def fixture(task="direction", horizon=1):
    days = sessions_in_range("weekday", date(2022, 1, 3), date(2024, 6, 28))
    w = Window(
        train_start=days[0],
        train_end=days[199],
        validation_start=days[200],
        validation_end=days[279],
        calibration_start=days[280],
        calibration_end=days[359],
        test_start=days[360],
        test_end=days[459],
    )
    cfg = ResearchRequest(
        dataset_id="00000000-0000-0000-0000-000000000001",
        tickers=["AAA", "BBB"],
        columns=["return", "sma__window_5", "sent_mean", "sent_momentum", "sent_surprise"],
        source_as_of=datetime(2026, 10, 15, tzinfo=UTC),
        target=Target(task=task, horizon=horizon),
        windows=[w],
        information_policy="research_replay",
        calibration="sigmoid" if task == "direction" else "none",
        minimum_train=40,
        minimum_evaluation=10,
        candidates=[Candidate(model="logistic" if task == "direction" else "ridge")],
        sentiment_provenance="synthetic_fixture",
    )
    rng = np.random.default_rng(43)
    rows, bars = [], []
    previous = {"AAA": 100.0, "BBB": 80.0}
    for day in days:
        for t in cfg.tickers:
            values = rng.normal(0, 1, 5)
            opening = previous[t]
            closing = opening * np.exp(float(rng.normal(0, 0.01)))
            previous[t] = closing
            ready = session_close("weekday", day) + timedelta(seconds=1)
            bars.append(
                Bar(
                    t,
                    day,
                    Decimal(str(opening)),
                    Decimal(str(closing)),
                    1000000,
                    ready,
                    ready,
                    str(day) + t,
                )
            )
            rows.append(
                Observation(
                    t,
                    t,
                    day,
                    ready,
                    next_open("weekday", ready),
                    tuple(values),
                    None,
                    None,
                    None,
                    None,
                    {},
                )
            )
    snap = Snapshot(tuple(bars))
    rows = [
        replace(
            r,
            target=outcome[0],
            target_start=outcome[1],
            target_end=outcome[2],
            target_available=outcome[3],
        )
        for r in rows
        for outcome in [label(r.ticker, r.decision, cfg, snap, "weekday")]
    ]
    return cfg, Dataset(
        tuple(cfg.columns),
        tuple(rows),
        snap,
        "weekday",
        {"datasets": [{"provider": "synthetic"}], "provenance": "explicit synthetic fixture"},
    )


@pytest.mark.parametrize("h", [1, 5, 10])
def test_target_independent_open_close_and_future_rms(h):
    cfg, ds = fixture(horizon=h)
    r = ds.rows[0]
    bars = [b for b in ds.prices.bars if b.ticker == r.ticker and b.day > r.day][:h]
    got = label(
        r.ticker,
        r.decision,
        cfg.model_copy(update={"target": Target(task="return", horizon=h)}),
        ds.prices,
        "weekday",
    )
    assert got[0] == pytest.approx(float(bars[-1].close) / float(bars[0].opening) - 1)
    assert got[1] > r.decision and got[2] == session_close("weekday", bars[-1].day)
    vol = label(
        r.ticker,
        r.decision,
        cfg.model_copy(update={"target": Target(task="volatility", horizon=h)}),
        ds.prices,
        "weekday",
    )
    expected = np.sqrt(sum(np.log(float(b.close) / float(b.opening)) ** 2 for b in bars) / h * 252)
    assert vol[0] == pytest.approx(expected)


def test_holiday_target_skips_market_holiday():
    cfg, _ = fixture()
    at = datetime(2024, 7, 3, 17, 0, 1, tzinfo=UTC)
    ready = datetime(2024, 7, 5, 20, 0, 1, tzinfo=UTC)
    b = Bar("AAA", date(2024, 7, 5), Decimal(100), Decimal(105), 100, ready, ready, "holiday")
    result = label("AAA", at, cfg, Snapshot((b,)), "XNYS")
    assert result[0] == 1 and result[1] == datetime(2024, 7, 5, 13, 30, tzinfo=UTC)


def test_metric_golden_and_undefined():
    y, p = np.array([0.0, 1.0, 1.0, 0.0]), np.array([0.1, 0.8, 0.4, 0.7])
    m = metrics(y, p, "direction")
    assert m["accuracy"] == 0.5
    assert m["brier"] == pytest.approx((0.01 + 0.04 + 0.36 + 0.49) / 4)
    assert m["confusion_matrix"] == [[1, 1], [1, 1]]
    assert m["log_loss"] == pytest.approx(-np.log([0.9, 0.8, 0.4, 0.3]).mean())
    r = metrics(np.array([1.0, 2.0, 3.0]), np.array([2.0, 2.0, 2.0]), "return")
    assert r["mae"] == pytest.approx(2 / 3) and r["rmse"] == pytest.approx(np.sqrt(2 / 3))
    assert r["correlation"] is None
    assert metrics(np.ones(5), np.full(5, 0.6), "direction")["roc_auc"] is None


@pytest.mark.parametrize(
    "name,task",
    [
        ("logistic", "direction"),
        ("forest_classifier", "direction"),
        ("boost_classifier", "direction"),
        ("ridge", "return"),
        ("elastic_net", "return"),
        ("forest_regressor", "return"),
        ("boost_regressor", "return"),
    ],
)
def test_actual_estimators_json_save_load_determinism(name, task):
    cfg, ds = fixture(task)
    rows = list(ds.rows[:200])
    x, y = matrix(rows), np.array([r.target for r in rows])
    c = Candidate(model=name, trees=5)
    a = train(c, x, y, cfg)
    p = infer(a, x[:10], cfg.columns)
    assert digest(a) == digest(train(c, x, y, cfg))
    assert np.array_equal(p, infer(a, x[:10], cfg.columns))
    if task == "direction":
        assert ((p >= 0) & (p <= 1)).all()
    with pytest.raises(MLException):
        infer(a, x, list(reversed(cfg.columns)))


def test_training_only_scaler_imputation_selection_constant_and_infinite():
    cfg, ds = fixture()
    cfg = cfg.model_copy(update={"missing": "median_indicator", "select_features": 2})
    x = matrix(list(ds.rows[:200]))
    x[0, 0] = np.nan
    x[:, 1] = 5
    x[:, 2] = x[:, 3]
    y = np.array([r.target for r in ds.rows[:200]])
    a = train(Candidate(), x, y, cfg)
    state = a["preprocessing"]
    assert 1 not in state["keep"] and len(state["names"]) == 2
    assert state["median"][0] == pytest.approx(np.nanmedian(x[:, 0]))
    saved = digest(state)
    transform(state, np.full((20, 5), 1e9), cfg.columns)
    assert digest(state) == saved
    with pytest.raises(MLException):
        train(Candidate(), np.full((200, 5), np.inf), y, cfg)


def test_purged_matured_labels_and_embargo_multiasset():
    cfg, ds = fixture(horizon=10)
    parts, audit = partition(ds, cfg, cfg.windows[0])
    cutoff = datetime.fromisoformat(audit["train"]["cutoff"])
    assert all(r.target_available <= cutoff and r.target_end < cutoff for r in parts["train"])
    assert audit["train"]["purged_or_missing"] >= 18
    contaminated = replace(ds.rows[0], target_available=cutoff + timedelta(days=1))
    groups, _ = partition(replace(ds, rows=(contaminated, *ds.rows[1:])), cfg, cfg.windows[0])
    assert contaminated not in groups["train"]
    groups2, _ = partition(ds, cfg.model_copy(update={"embargo_sessions": 15}), cfg.windows[0])
    assert len(groups2["train"]) < len(parts["train"])


def test_future_price_sentiment_test_labels_distribution_do_not_change_prior_models():
    cfg, ds = fixture()
    cfg = cfg.model_copy(update={"candidates": [Candidate(strength=0.1), Candidate(strength=2)]})
    original = evaluate(cfg, ds)
    w = cfg.windows[0]
    changed = replace(
        ds,
        rows=tuple(
            replace(r, values=tuple(v + 100000 for v in r.values), target=1 - r.target)
            if r.day >= w.test_start and r.target is not None
            else r
            for r in ds.rows
        ),
        prices=Snapshot(
            tuple(
                replace(b, close=b.close * 2) if b.day > w.test_end else b for b in ds.prices.bars
            )
        ),
    )
    later = evaluate(cfg, changed)
    assert original["models"] == later["models"]
    assert original["folds"][0]["candidates"] == later["folds"][0]["candidates"]
    # Immutable snapshot survives external mutation; early predictions are byte-identical.
    frozen = freeze(ds)
    assert evaluate(cfg, thaw(frozen))["predictions"] == original["predictions"]
    m = original["models"][0]
    with pytest.raises(MLException):
        inference_guard(m, datetime(2020, 1, 1, tzinfo=UTC), cfg.columns)
    assert {p["origin"] for p in original["predictions"]} == {"historical_walk_forward"}


def test_calibration_separate_small_sample_and_actual_sigmoid_isotonic():
    p = np.linspace(0.05, 0.95, 1200)
    y = (np.arange(1200) % 3 == 0).astype(float)
    assert fit_calibration(p[:20], y[:20], "sigmoid")["status"] == "insufficient_data"
    assert fit_calibration(p[:200], y[:200], "isotonic")["status"] == "insufficient_data"
    for method in ("sigmoid", "isotonic"):
        state = fit_calibration(p, y, method)
        assert state["status"] == "completed"
        out = calibrate(state, np.array([0.1, 0.9]))
        assert ((out >= 0) & (out <= 1)).all()
    cfg, ds = fixture()
    r = evaluate(cfg, ds)
    assert r["models"][0]["calibration"]["n"] == 158
    assert r["models"][0]["training_cutoff"] < r["models"][0]["effective_at"]


def test_backtest_orders_cannot_precede_forecasts_and_reconcile():
    cfg, ds = fixture()
    result = evaluate(cfg, ds)
    experiments = economic(cfg, ds, result["predictions"])
    net = experiments[0]["net"]
    assert net["fills"]
    orders = {o["id"]: o for o in net["orders"]}
    assert all(f["at"] > orders[f["order_id"]]["submitted_at"] for f in net["fills"])
    assert all(
        abs(Decimal(row["reconciliation_residual"])) < Decimal("1e-8") for row in net["equity"]
    )


def test_optimizer_rejects_probability_horizon_stale_double_sentiment():
    cfg, ds = fixture("return")
    output = evaluate(cfg, ds)
    p = output["predictions"][:2]
    at = datetime.fromisoformat(p[0]["decision_at"])
    e = Estimates(tuple(cfg.tickers), np.zeros(2), np.eye(2) * 0.01, {})
    got = forecast_estimates(e, p, at, 1)
    assert got.mean == pytest.approx([v["value"] * 252 for v in p])
    for pp, aa, hh, sentiment in [
        ([{**v, "prediction_type": "direction"} for v in p], at, 1, False),
        (p, at, 5, False),
        (p, at + timedelta(days=10), 1, False),
        (p, at, 1, True),
    ]:
        with pytest.raises(MLException):
            forecast_estimates(e, pp, aa, hh, sentiment_adjustment=sentiment)


def test_sentiment_ablation_matched_common_rows_and_insufficient():
    cfg, ds = fixture()
    cfg = cfg.model_copy(update={"candidates": [Candidate(model="prevalence")]})
    result = ablations(cfg, ds)
    assert result["sentiment_alpha"] == "UNVERIFIED"
    counts = [len(v["predictions"]) for v in result["variants"].values()]
    assert len(set(counts)) == 1
    empty = replace(
        ds, rows=tuple(replace(r, values=(*r.values[:2], None, None, None)) for r in ds.rows)
    )
    assert all(
        v["status"] == "insufficient_data" for v in ablations(cfg, empty)["variants"].values()
    )


def test_request_bounds_no_arbitrary_models_or_overlapping_test():
    cfg, _ = fixture()
    payload = cfg.model_dump(mode="json")
    payload["candidates"] = [{"model": "eval(user_code)"}]
    with pytest.raises(ValidationError):
        ResearchRequest.model_validate(payload)
    payload = cfg.model_dump(mode="json")
    payload["windows"] *= 2
    with pytest.raises(ValidationError):
        ResearchRequest.model_validate(payload)


@pytest.mark.parametrize("task", ["return", "volatility"])
@pytest.mark.parametrize("h", [1, 5, 10])
def test_regression_and_volatility_lifecycle(task, h):
    cfg, ds = fixture(task, h)
    result = evaluate(cfg, ds)
    assert result["status"] == "completed"
    assert result["folds"][0]["metrics"]["rmse"] >= 0
    if task == "volatility":
        assert all(p["value"] >= 0 for p in result["predictions"])


def test_missing_target_session_is_not_bridged():
    cfg, ds = fixture(horizon=5)
    r = ds.rows[0]
    missing = replace(ds.prices, bars=tuple(b for b in ds.prices.bars if b.day != ds.rows[6].day))
    assert label(r.ticker, r.decision, cfg, missing, ds.calendar)[0] is None


def test_preprocessing_fit_never_sees_validation_calibration_or_test(monkeypatch):
    import sentientalpha.ml.models as module

    cfg, ds = fixture()
    original = module.preprocess
    expected_rows = partition(ds, cfg, cfg.windows[0])[0]["train"]
    expected = matrix(expected_rows)
    calls = []

    def spy(x, y, request):
        assert np.array_equal(x, expected)
        calls.append(len(x))
        return original(x, y, request)

    monkeypatch.setattr(module, "preprocess", spy)
    evaluate(cfg, ds)
    assert calls and set(calls) == {len(expected)}


def test_calibration_labels_cannot_select_hyperparameters():
    cfg, ds = fixture()
    cfg = cfg.model_copy(update={"candidates": [Candidate(strength=0.1), Candidate(strength=2)]})
    original = evaluate(cfg, ds)
    w = cfg.windows[0]
    changed = replace(
        ds,
        rows=tuple(
            replace(r, target=1 - r.target)
            if w.calibration_start <= r.day <= w.calibration_end and r.target is not None
            else r
            for r in ds.rows
        ),
    )
    later = evaluate(cfg, changed)
    assert original["models"][0]["artifact"] == later["models"][0]["artifact"]
    assert original["folds"][0]["selected_candidate"] == later["folds"][0]["selected_candidate"]


def test_invalid_numeric_artifact_tree_cycles_refused():
    from sentientalpha.ml.models import tree_predict

    t = {"left": [0], "right": [0], "feature": [0], "threshold": [1.0], "value": [0.5]}
    with pytest.raises(MLException, match="Cyclic"):
        tree_predict(t, np.array([[0.0]]))


def test_close_to_close_is_separate_research_convention():
    cfg, ds = fixture("return")
    cfg = cfg.model_copy(
        update={"target": Target(task="return", convention="close_to_close_research")}
    )
    r = ds.rows[0]
    outcome = label(r.ticker, r.decision, cfg, ds.prices, ds.calendar)
    assert outcome[1] < r.decision
    with pytest.raises(MLException):
        economic(cfg, ds, [])
