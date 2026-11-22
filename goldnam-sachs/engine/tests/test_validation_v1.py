import numpy as np
import pandas as pd
import pytest
from goldnam_engine.validation.ranking import block_interval, evidence, newey_west_t, rank_study


def synthetic(seed=20261123):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2015-01-01", periods=2800)
    prices = pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0, 0.01, (2800, 160)), axis=0)), index=dates
    )
    scores = pd.DataFrame(rng.normal(size=prices.shape), index=dates)
    return prices, scores


def test_random_walk_no_predictive_signal():
    prices, scores = synthetic()
    _, result = rank_study(scores, prices, 63, round_trip_cost=0)
    assert abs(result["ic_mean"]) < 0.03
    assert result["spread_ci95"][0] <= 0 <= result["spread_ci95"][1]
    assert result["evidence"] != "근거 있음"


def test_planted_signal_detected_and_held_out():
    prices, scores = synthetic()
    # Intentionally future-informed synthetic oracle tests the validator, not a tradable feature.
    planted = prices.shift(-64) / prices.shift(-1) - 1
    _, result = rank_study(planted, prices, 63)
    assert result["ic_mean"] > 0.99 and result["oos_net_spread"] > 0
    assert result["spread_ci95"][0] > 0


def test_next_open_contract_no_zero_fills_or_tail_selection():
    dates = pd.bdate_range("2020-01-01", periods=120)
    opens = pd.DataFrame({str(i): 100 + np.arange(120) * i for i in range(1, 21)}, index=dates)
    scores = pd.DataFrame({str(i): float(i) for i in range(1, 21)}, index=dates)
    detail, _ = rank_study(scores, opens, 21, round_trip_cost=0)
    day = detail.index[0]
    pos = opens.index.get_loc(day)
    expected = (opens.iloc[pos + 22] / opens.iloc[pos + 1] - 1).mean()
    assert detail.iloc[0].universe == pytest.approx(expected)
    assert detail.index[-1] < dates[-21]
    assert block_interval(pd.Series([1, 2])) == (None, None)
    assert newey_west_t(pd.Series([1, 2])) is None
    assert evidence(None, 1, 1) == "미검증"
    assert evidence(3, -0.1, 0.1) == "근거 없음"
    assert evidence(1, 0.1, 0.1) == "근거 약함"
    with pytest.raises(ValueError):
        rank_study(scores, opens, 5)
    with pytest.raises(ValueError):
        rank_study(scores, opens.iloc[::-1])


def test_vectorized_technicals_zones_and_prefix_causality():
    from dataclasses import asdict

    from goldnam_engine.factors.technical_engine import build_technical_snapshot
    from goldnam_engine.timing.sr_engine import build_zones
    from goldnam_engine.validation.series import StructuralHistory, setup_history, technical_series

    from engine.tests.smoke_test import make_momentum

    frame, bench = make_momentum()
    features = technical_series(frame, bench)
    history = StructuralHistory(frame)
    for i in (260, 310, 359):
        snapshot = build_technical_snapshot(frame.iloc[: i + 1], bench.iloc[: i + 1])
        for key, value in asdict(snapshot).items():
            assert features.iloc[i][key] == pytest.approx(value, abs=1e-9), key
        assert history.zones(i, snapshot) == build_zones(frame.iloc[: i + 1], snapshot)
    full = setup_history(frame, bench, "us")
    prefix = setup_history(frame.iloc[:310], bench.iloc[:310], "us")
    pd.testing.assert_frame_equal(full.iloc[: len(prefix)], prefix)
    assert (
        full.momentum_signal
        == (
            full.momentum_status.eq("CONFIRMED")
            & ~full.momentum_status.eq("CONFIRMED").shift(fill_value=False)
        )
    ).all()


def test_event_controls_reproducible_and_portfolio_limits():
    from goldnam_engine.trade.trade_core import Costs
    from goldnam_engine.validation.events import (
        event_summary,
        portfolio_simulation,
        study_symbol,
        trade_statistics,
    )

    from engine.tests.test_strategy_v1 import bars

    d = bars(400)
    d.loc[d.index[5], ["High", "Close"]] = [112, 110]
    dates = d.index[1:240]
    history = pd.DataFrame(
        {
            "date": dates,
            "pullback_stop_loss": 95.0,
            "pullback_target1": 110.0,
            "pullback_signal": False,
        }
    )
    history.loc[history.index[::25], "pullback_signal"] = True
    a, b = study_symbol(d, history, "pullback", "A", Costs())
    a2, b2 = study_symbol(d, history, "pullback", "A", Costs())
    pd.testing.assert_frame_equal(a, a2)
    assert len(b) == 20
    for x, y in zip(b, b2, strict=True):
        pd.testing.assert_frame_equal(x, y)
    summary = event_summary(a, b)
    assert summary["n"] > 0 and summary["random_repetitions"] == 20
    assert trade_statistics(pd.DataFrame())["expected_r"] is None
    a["symbol"] = "A"
    portfolio = portfolio_simulation(a, {"A": d}, {"A": "tech"}, Costs())
    assert portfolio["entries"] > 0 and max(r["positions"] for r in portfolio["curve"]) == 1
    assert portfolio["max_drawdown"] <= 0
    assert portfolio_simulation(pd.DataFrame(), {}, {}, Costs())["entries"] == 0
