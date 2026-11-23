from datetime import date

import numpy as np
import pandas as pd
import pytest
from goldnam_engine.data.store import Store
from goldnam_engine.factors.cross_section import FACTOR_COLUMNS, financial_features, price_features
from goldnam_engine.scoring.cross_section import grade, percentile, rank_snapshot


def test_momentum_excludes_last_month_and_uses_full_history():
    prices = pd.DataFrame({"A": np.arange(1.0, 301.0), "B": np.arange(301.0, 601.0)})
    factors = price_features(prices)
    assert factors["momentum_12_1"].iloc[-1, 0] == pytest.approx(279 / 48 - 1)
    changed = prices.copy()
    changed.iloc[-20:] *= 5
    assert (
        price_features(changed)["momentum_12_1"].iloc[-1, 0] == factors["momentum_12_1"].iloc[-1, 0]
    )
    assert factors["momentum_12_1"].iloc[:252].isna().all().all()
    assert factors["price_ma200"].iloc[-1, 0] == pytest.approx(
        300 / prices.A.iloc[-200:].mean() - 1
    )
    assert factors["distance_high252"].iloc[-1, 0] == 0
    before = price_features(prices.iloc[:280])["ma50_ma200"].iloc[-1]
    pd.testing.assert_series_equal(before, factors["ma50_ma200"].iloc[279])


def test_financial_guards_and_missing_values():
    assert all(v is None for v in financial_features(None, None).values())
    facts = {
        "equity": 100,
        "assets": 200,
        "net_income": 10,
        "gross_profit": 50,
        "operating_income": 20,
        "revenue": 100,
        "liabilities": 100,
        "operating_cashflow": 30,
        "capex": 5,
        "revenue_growth": 0.1,
        "eps_growth": 0.2,
        "quarterly_income": [1, 2, 3, 4],
    }
    f = financial_features(facts, 500)
    assert f["roe"] == 0.1 and f["fcf_yield"] == 0.05 and f["book_yield"] == 0.2
    assert f["income_stability"] < 0
    facts.update(net_income=-1, equity=-1, capex=100)
    f = financial_features(facts, 500)
    assert (
        f["roe"] is None
        and f["earnings_yield"] is None
        and f["book_yield"] is None
        and f["fcf_yield"] is None
    )
    assert financial_features({"assets": "bad", "gross_profit": np.inf}, 0)["gross_assets"] is None


def reference():
    df = pd.DataFrame(
        {column: np.arange(1.0, 31.0) for columns in FACTOR_COLUMNS.values() for column in columns},
        index=[f"S{i}" for i in range(30)],
    )
    df["market"] = "us"
    df["industry"] = ["small"] * 5 + ["large"] * 25
    df["sector"] = ["tech"] * 15 + ["other"] * 15
    return df


def test_coverage_threshold_peer_hierarchy_and_integer_metadata():
    peers = reference()
    rows = rank_snapshot(peers, date(2026, 1, 1), [{"name": "fixture"}])
    assert rows[0]["indicators"]["roe"]["scope"] == "sector"
    assert rows[10]["indicators"]["roe"]["scope"] == "industry"
    assert rows[-1]["score"]["value"] == 100
    assert rows[-1]["score"]["coverage"] == 1
    assert rows[-1]["score"]["evidence"] == "미검증"
    assert isinstance(rows[4]["score"]["value"], int)
    price_only = peers.drop(
        columns=[c for k in ["quality", "value", "growth"] for c in FACTOR_COLUMNS[k]]
    )
    result = rank_snapshot(price_only, date(2026, 1, 1), [])[0]
    assert result["score"]["value"] is None and result["score"]["coverage"] == 0.4
    assert "부분 점수" in result["score"]["badges"][0]
    # Exactly half of a two-indicator factor counts; 2/5 quality does not.
    peers.loc["S0", ["momentum_12_1", "roe", "gross_assets", "income_stability"]] = np.nan
    result = rank_snapshot(peers, date.today(), [])[0]
    assert result["factors"]["momentum"]["value"] is not None
    assert result["factors"]["quality"]["value"] is None
    assert result["score"]["value"] is not None and result["score"]["coverage"] == 0.8


def test_out_of_universe_uses_same_reference_and_market_not_mixed():
    peers = reference()
    target = peers.iloc[[0]].copy()
    target.index = ["OUT"]
    target[["industry", "sector"]] = None
    row = rank_snapshot(peers, date.today(), [], target)[0]
    assert "유니버스 밖" in row["score"]["badges"]
    assert row["indicators"]["roe"]["scope"] == "market"
    assert row["indicators"]["momentum_12_1"]["percentile"] == round(
        percentile(1, peers.momentum_12_1)
    )
    peers.loc["S0", "market"] = "kr"
    with pytest.raises(ValueError):
        rank_snapshot(peers, date.today(), [])
    with pytest.raises(ValueError):
        rank_snapshot(pd.concat([reference(), reference()]), date.today(), [])
    assert percentile(1, pd.Series([None])) is None
    assert percentile(np.nan, pd.Series([1, 2])) is None
    assert [grade(x) for x in [None, 95, 80, 50, 20, 5]] == [
        "산출 불가",
        "상위 10%",
        "상위 30%",
        "중간",
        "하위 30%",
        "하위 10%",
    ]


def test_sql_storage_upsert_transaction_namespaces_and_nulls(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError):
        Store()
    store = Store("sqlite://")
    store.put("scores", "us:2026-01-01:A", {"score": np.nan})
    assert store.get("scores", "us:2026-01-01:A")["score"] is None
    store.put("scores", "us:2026-01-01:A", {"score": 12})
    store.put_many("scores", [("kr:B", {"score": 22}), ("us:2026-01-01:C", {"score": 33})])
    assert len(store.list("scores", "us:")) == 2
    assert store.get("journal", "us:2026-01-01:A") is None
    store.remove("scores", "kr:B")
    assert len(store.list("scores")) == 2
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(ValueError):
        Store("sqlite://")
