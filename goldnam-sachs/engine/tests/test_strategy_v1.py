from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from goldnam_engine.data.contracts import DataResult
from goldnam_engine.factors.technical_engine import build_technical_snapshot
from goldnam_engine.models import MarketRegimeSnapshot, PriceZone
from goldnam_engine.regime.current import build_regime, regime_multiplier
from goldnam_engine.risk.current import build_risk_snapshot
from goldnam_engine.risk.portfolio import Holding, size_portfolio
from goldnam_engine.timing.current import actionable, build_setups, structural_zones
from goldnam_engine.timing.setup_engine import build_setups as legacy_setups
from goldnam_engine.timing.sr_engine import ZoneSet
from goldnam_engine.trade.execution_engine import run_execution_study
from goldnam_engine.trade.exits import run_exits
from goldnam_engine.trade.trade_core import Costs

from engine.tests.smoke_test import make_momentum


def context():
    frame, _ = make_momentum()
    tech = build_technical_snapshot(frame)
    market = MarketRegimeSnapshot("KR", 70, "우호", {}, {}, 1, "")
    return tech, market


def test_four_upgrade_regressions():
    tech, market = context()
    tech = replace(
        tech,
        dollar_volume=9_000_000_000,
        dist_ema20_atr=4,
        rsi=90,
        trend=95,
        momentum=95,
        demand=95,
        relative_strength=95,
        volume_ratio=2,
        prior_high20=120,
        prior_high60=110,
    )
    risk = build_risk_snapshot(tech, market, fx=DataResult(2000.0, "fixture"))
    setup = build_setups(130, tech, market, ZoneSet((), ()), risk, expected_r={"momentum": 3})
    assert risk.earnings == "발표일 미확인" and risk.components["earnings"] == 50
    assert risk.liquidity == "Weak"
    assert setup.momentum.trigger == 110
    assert setup.momentum.status == "EXTENDED" and not actionable(setup.momentum)
    assert setup.preferred == "비교 근거 없음"
    assert "ATR 기준" in setup.momentum.details["Target source"]
    unknown_fx = build_risk_snapshot(tech, market)
    assert unknown_fx.score is None and unknown_fx.position_size_multiplier == 0
    assert unknown_fx.components["liquidity"] is None
    stale = build_risk_snapshot(tech, market, fx=DataResult(2000.0, "fixture", status="stale"))
    assert "stale" in " ".join(stale.badges)


def test_ema20_solo_excluded_and_six_protected_rules():
    t, m = context()
    m = replace(m, market="US")
    t = replace(
        t,
        ema200=80,
        ema50=98,
        ema20=99,
        atr=2,
        trend=90,
        drawdown_from_high60=-5.5,
        rsi=52,
        volume_ratio=0.6,
        dist_ema20_atr=0.5,
        last_day_return=-1,
    )
    zone = PriceZone("support", 97, 99, 98, 85, "Strong", ("EMA20",))
    assert not structural_zones(ZoneSet((zone,), ())).supports
    zone = replace(zone, sources=("EMA20", "Swing Low"))
    zones = ZoneSet((zone,), ())
    risk = build_risk_snapshot(t, m, 30)
    new = build_setups(100, t, m, zones, risk)
    old = legacy_setups(100, t, m, zones, risk)
    for key in ["Pullback Depth", "Momentum Stabilization", "Volume Pattern"]:
        assert new.pullback.factors[key] == old.pullback.factors[key]
    assert new.pullback.stop_loss == 97 - 2 * 0.55
    for depth in [-0.5, -18]:
        other = build_setups(100, replace(t, drawdown_from_high60=depth), m, zones, risk)
        assert other.pullback.factors["Pullback Depth"] < new.pullback.factors["Pullback Depth"]
    low_rsi = build_setups(100, replace(t, rsi=25), m, zones, risk)
    assert (
        low_rsi.pullback.factors["Momentum Stabilization"]
        < new.pullback.factors["Momentum Stabilization"]
    )
    assert (
        build_setups(100, replace(t, ema200=110), m, zones, risk).pullback.status == "INVALIDATED"
    )
    assert build_setups(100, replace(t, trend=30), m, zones, risk).pullback.status == "INVALIDATED"
    near = build_risk_snapshot(t, m, 1)
    assert near.score > risk.score and near.position_size_multiplier < risk.position_size_multiplier
    selected = build_setups(100, t, m, zones, risk, {"pullback": 0.3})
    assert selected.preferred == "pullback"


@pytest.mark.parametrize(
    "days,expected", [(None, 50), (-1, 50), (1, 95), (7, 78), (21, 45), (30, 20)]
)
def test_earnings_components(days, expected):
    t, m = context()
    assert build_risk_snapshot(t, replace(m, market="US"), days).components["earnings"] == expected


def test_regime_uses_prices_as_of_and_size_only():
    frame = pd.DataFrame({"Close": np.arange(1.0, 301.0)})
    favorable = build_regime(frame, "us")
    assert favorable.label == "우호" and regime_multiplier(favorable) == 1
    assert build_regime(frame.iloc[:100], "us") is None and regime_multiplier(None) == 0
    down = build_regime(pd.DataFrame({"Close": np.arange(300.0, 0.0, -1)}), "us")
    assert down.label == "비우호" and regime_multiplier(down) == 0.5
    assert regime_multiplier(replace(down, label="중립")) == 0.75


def bars(n=140):
    return pd.DataFrame(
        {"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0},
        index=pd.bdate_range("2025-01-01", periods=n),
    )


def signals(d, days=(0,), stop=95, target=110):
    return pd.DataFrame({"date": [d.index[i] for i in days], "stop": stop, "target": target})


def test_a_exact_legacy_cost_gap_and_overlap_parity():
    d = bars()
    d.iloc[2] = [94, 100, 93, 95]
    s = signals(d, (0, 1, 3))
    costs = Costs(0.001, 0.002, 0.003, 0.001)
    new = run_exits(d, s, "A", costs)
    old_signal = pd.DataFrame(
        {
            "date": s.date,
            "pullback": 100,
            "momentum": 0,
            "pullback_stop_loss": 95,
            "pullback_target1": 110,
            "momentum_stop_loss": 95,
            "momentum_target1": 110,
        }
    )
    old, _ = run_execution_study(d, old_signal, costs=costs)
    filled = old[old["상태"] == "체결"]
    assert new[new.status == "filled"].net_return.tolist() == pytest.approx(
        filled["순수익률(%)"] / 100
    )
    assert new.iloc[0].reason == "손절 갭" and new.iloc[1].status == "excluded"
    assert new.iloc[0].fills[0]["price"] == 94


@pytest.mark.parametrize("mode", ["A", "B", "C"])
def test_full_window_and_stop_priority(mode):
    d = bars()
    d.iloc[1] = [100, 115, 90, 105]
    result = run_exits(d, signals(d), mode)
    assert result.iloc[0].fills[0]["price"] == 95 and result.iloc[0].r == -1
    # Recent barrier hits still excluded without the complete 20/120-day horizon.
    recent = run_exits(d, signals(d, (130,)), mode)
    assert recent.iloc[0].status == "excluded"


def test_partial_target_trailing_no_intrabar_lookahead():
    d = bars()
    d.iloc[1] = [100, 112, 99, 111]
    d.iloc[2] = [109, 110, 108, 109]
    b = run_exits(d, signals(d), "B").iloc[0]
    assert b.fills[0]["fraction"] == 0.5 and b.fills[0]["price"] == 110
    assert len(b.fills) >= 2 and b.fills[1]["date"] != b.fills[0]["date"]
    c = run_exits(d, signals(d), "C").iloc[0]
    assert len(c.fills) == 1 and c.fills[0]["date"] != d.index[1].isoformat()
    assert run_exits(d, signals(d, stop=101), "A").iloc[0].status == "excluded"


def test_portfolio_caps_and_gap_stress():
    base = size_portfolio(10000, 10000, 100, 95, 110, "tech", [])
    assert base["수량"] == 20 and base["projected_heat_pct"] == 1
    held = [Holding("A", "tech", 15, 100, 90), Holding("B", "tech", 10, 100, 90)]
    limited = size_portfolio(10000, 7000, 100, 95, 110, "tech", held)
    assert limited["수량"] == 0 and "업종 종목 수" in limited["warnings"]
    heat = size_portfolio(10000, 7000, 100, 95, 110, "other", [Holding("A", "tech", 59, 100, 90)])
    assert heat["수량"] == 2 and heat["projected_heat_pct"] == 6
    assert heat["gap_loss_1_5r"] == 15
    with pytest.raises(ValueError):
        size_portfolio(10000, 10000, 100, 95, 110, "x", [Holding("x", "x", 1, 90, 100)])


def test_execution_rejects_malformed_inputs():
    d = bars()
    with pytest.raises(ValueError):
        run_exits(d, signals(d), "D")
    with pytest.raises(ValueError):
        run_exits(d.drop(columns="High"), signals(d))
    with pytest.raises(ValueError):
        run_exits(d.iloc[::-1], signals(d))
    d.iloc[0, 1] = 80
    with pytest.raises(ValueError):
        run_exits(d, signals(d))


def test_independent_lenses_exclude_extended_price_vote():
    from goldnam_engine.scoring.lenses import consensus

    t, m = context()
    t = replace(
        t,
        trend=95,
        momentum=95,
        demand=95,
        relative_strength=95,
        dist_ema20_atr=5,
        rsi=90,
        volume_ratio=2,
    )
    risk = build_risk_snapshot(t, replace(m, market="US"))
    setups = build_setups(100, t, m, ZoneSet((), ()), risk)
    factors = {k: {"value": 99} for k in ["momentum", "trend", "quality", "value", "growth"]}
    result = consensus(factors, setups, m, 90)
    assert len(result["lenses"]) == 4
    assert result["lenses"]["price"]["supportive"] is False
    assert result["supportive"] == 3
    assert consensus({}, None, None, 90, "kr")["available"] == 0
