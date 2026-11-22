"""Offline regression coverage for modules outside the original 49 tests."""

from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from goldnam_engine.data.history_store import SQLiteHistoryStore
from goldnam_engine.data.korean_stock_search import (
    contains_hangul,
    load_krx_listing,
    search_krx_listing,
)
from goldnam_engine.factors.company_engine import build_company_snapshot
from goldnam_engine.factors.options_analyzer import (
    calculate_max_pain,
    option_bias,
    option_entry_readiness,
    price_confluence,
    summarize_options,
)
from goldnam_engine.factors.technical_engine import build_technical_snapshot
from goldnam_engine.models import MarketRegimeSnapshot
from goldnam_engine.regime.market_regime import build_market_regime
from goldnam_engine.risk.risk_engine import build_risk_snapshot
from goldnam_engine.scoring.consensus_engine import build_consensus_v2
from goldnam_engine.scoring.quant_engine import financial_rows
from goldnam_engine.scoring.scoring_utils import percentile_score
from goldnam_engine.timing.setup_engine import build_setups
from goldnam_engine.timing.sr_engine import build_zones
from goldnam_engine.trade.trade_core import Costs, affordable_shares
from hypothesis import given
from hypothesis import strategies as st

from engine.tests.smoke_test import make_momentum


def chain():
    return pd.DataFrame(
        {
            "strike": [90.0, 100.0, 110.0],
            "openInterest": [10, 100, 20],
            "volume": [5, 50, 10],
            "impliedVolatility": [0.3, 0.4, 0.5],
            "bid": [2.0, 3.0, 4.0],
            "ask": [2.2, 3.2, 4.2],
            "lastPrice": [2.1, 3.1, 4.1],
        }
    )


def test_option_calculation_separated_from_ui():
    calls = chain()
    puts = chain()
    today = date(2026, 1, 1)
    summary = summarize_options(calls, puts, 100, "2026-02-01", today)
    assert summary.call_wall == summary.put_wall == summary.max_pain == 100
    assert summary.volume_ratio == summary.oi_ratio == 1
    assert summary.expected_move == pytest.approx(6.2)
    assert summary.expected_low == pytest.approx(93.8)
    assert summary.expected_high == pytest.approx(106.2)
    assert summary.data_quality == 1
    assert option_bias(summary) == "Neutral"
    assert price_confluence(summary, 100, 100, 100)[0] == "HIGH CONFLUENCE"
    assert price_confluence(summary, 100, None, 100)[0] == "PARTIAL CONFLUENCE"
    assert price_confluence(summary, 80, 120, 100)[0] == "DIVERGENCE"


@pytest.mark.parametrize(
    "ratio,label",
    [
        (0.3, "Bullish"),
        (0.8, "Mild Bullish"),
        (1, "Neutral"),
        (1.3, "Mild Bearish"),
        (2, "Bearish"),
    ],
)
def test_option_bias_and_readiness_branches(ratio, label):
    calls, puts = chain(), chain()
    puts[["volume", "openInterest"]] = puts[["volume", "openInterest"]] * ratio
    expiry = (date.today() + timedelta(days=40)).isoformat()
    summary = summarize_options(calls, puts, 100, expiry)
    assert option_bias(summary) == label
    entry = option_entry_readiness(summary, calls, puts, 100, expiry)
    assert 0 <= entry.score <= 100
    assert set(entry.factors) == set(entry.details)


def test_missing_option_chain_stays_low_quality():
    empty = pd.DataFrame()
    summary = summarize_options(empty, empty, 100, "2026-02-01", date(2026, 1, 1))
    assert summary.data_quality == 0
    assert summary.call_wall is None and summary.put_wall is None
    assert calculate_max_pain(empty, empty) is None
    assert option_bias(summary) == "Neutral"
    sparse = chain().assign(openInterest=0, volume=0, bid=0, ask=0, lastPrice=0)
    fallback = summarize_options(sparse, sparse, 100, "2026-02-01", date(2026, 1, 1))
    assert fallback.max_pain is None
    assert fallback.expected_move > 0  # Existing IV fallback, preserved.


@pytest.mark.parametrize(
    "symbol,sector,region", [("AAPL", "technology", "US"), ("005930.KS", "semiconductors", "KR")]
)
def test_market_regime_uses_only_as_of_prices(symbol, sector, region):
    index = pd.bdate_range("2025-01-01", periods=100)
    frame = pd.DataFrame({"Close": np.linspace(100, 130, 100)}, index=index)
    calls = []

    def loader(ticker, period):
        calls.append(ticker)
        return frame.copy()

    cutoff = index[70]
    before = build_market_regime(symbol, sector, loader, cutoff)
    frame.loc[index[71] :, "Close"] = 1_000_000
    after = build_market_regime(symbol, sector, loader, cutoff)
    assert before == after
    assert before.market == region and before.components
    assert calls and 0 <= before.score <= 100
    assert before.data_quality > 0


def test_market_missing_loader_preserves_legacy_behavior():
    def unavailable(*args):
        raise ConnectionError("offline fixture")

    result = build_market_regime("AAPL", None, unavailable)
    assert result.data_quality == 0 and not result.components
    # This neutral fallback is a documented Phase 1/3 change, not changed here.
    assert result.score == 50


def test_krx_fallback_order_and_name_search():
    calls = []

    def listing(market):
        calls.append(market)
        if market == "KOSDAQ-DESC":
            return pd.DataFrame({"Symbol": [660, 660], "Company": ["테스트", "테스트"]})
        raise ConnectionError("offline fixture")

    frame = load_krx_listing(listing)
    assert calls == ["KRX", "KOSPI", "KOSDAQ", "KOSPI-DESC", "KOSDAQ-DESC"]
    assert len(frame) == 1
    assert search_krx_listing("테스트", frame)[0]["symbol"] == "000660.KQ"
    assert search_krx_listing("660", frame)[0]["symbol"] == "000660.KQ"
    assert search_krx_listing("", frame) == []
    assert contains_hangul("삼성") and not contains_hangul("AAPL")


def test_history_roundtrip_upsert_and_metadata(tmp_path):
    first = SQLiteHistoryStore(tmp_path / "first.sqlite")
    first.record("TEST", {"trend": 10}, date(2026, 1, 1), {"score_version": "v6"})
    first.record("TEST", {"trend": 15}, date(2026, 1, 1), {"score_version": "v6"})
    first.record("TEST", {"trend": 20}, date(2026, 1, 2))
    second = SQLiteHistoryStore(tmp_path / "second.sqlite")
    assert second.import_json(first.export_json().encode()) == 2
    assert second.rows("TEST") == first.rows("TEST")
    trend = second.recent("TEST", "trend")
    assert trend.change == 5 and trend.label == "Improving"
    with pytest.raises(ValueError):
        second.import_json("{}")


def test_negative_valuation_multiples_excluded_with_peers():
    info = {
        "returnOnEquity": 0.2,
        "revenueGrowth": 0.1,
        "trailingPE": -10,
        "forwardPE": -8,
        "priceToBook": -2,
    }
    peers = [
        {**info, "trailingPE": n, "forwardPE": n, "priceToBook": n / 10} for n in (10, 20, 30, 40)
    ]
    result = build_company_snapshot(info, peers)
    assert result.factors["Valuation"] is None
    assert result.relative["Trailing PE"] is None
    assert result.relative["Price / Book"] is None
    assert financial_rows(result, {})


@pytest.mark.parametrize("earnings", [None, 1, 5, 15, 30])
def test_risk_event_and_consensus_remain_compatible(earnings):
    frame, bench = make_momentum()
    tech = build_technical_snapshot(frame, bench)
    market = MarketRegimeSnapshot("KR", 72, "Risk-On", {}, {}, 1.0, "")
    risk = build_risk_snapshot(tech, market, earnings)
    zones = build_zones(frame, tech)
    setups = build_setups(float(frame.Close.iloc[-1]), tech, market, zones, risk)
    company = build_company_snapshot({"revenueGrowth": 0.3})
    result = build_consensus_v2(company, tech, setups, market, "Bullish", 0.8)
    assert result.available == 5
    assert 0 <= result.signal_agreement <= 100
    assert 0 <= risk.position_size_multiplier <= 1
    assert "원" in risk.details["Liquidity"]
    if earnings == 1:
        assert "Event Risk" in risk.earnings
    bad = build_consensus_v2(
        replace(company, score=10),
        replace(tech, trend=10),
        replace(setups, preferred="No Clear Setup"),
        replace(market, score=10),
        "Bearish",
        0.5,
    )
    assert bad.supportive == 0


@given(st.integers(0, 1_000_000), st.integers(1, 100_000))
def test_affordable_shares_never_exceed_cash(cash, price):
    costs = Costs(0.001, 0.002, 0.003, 0.005)
    quantity = affordable_shares(cash, price, costs)
    assert costs.buy_unit(price) * quantity <= cash
    assert costs.buy_unit(price) * (quantity + 1) > cash


@given(
    st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False),
    st.lists(st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False), min_size=3, max_size=30),
)
def test_existing_percentile_bounds(value, peers):
    result = percentile_score(value, peers)
    assert result is not None and 0 <= result <= 100
