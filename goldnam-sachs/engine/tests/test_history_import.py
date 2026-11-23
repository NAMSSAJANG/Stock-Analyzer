import hashlib
import json

import pytest
from goldnam_engine.data.history_store import SQLiteHistoryStore
from goldnam_engine.data.store import Store

from jobs.import_v6_history import normalize, read_legacy, save


def test_read_only_legacy_sqlite_json_idempotent_and_isolated(tmp_path):
    path = tmp_path / "v6.sqlite"
    legacy = SQLiteHistoryStore(path)
    legacy.record("AAPL", {"opportunity": 73}, metadata={"source": "original"})
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    rows = read_legacy(path)
    assert rows == normalize(json.loads(legacy.export_json()))
    store = Store("sqlite://")
    store.put("scores", "us:2026-01-01:AAPL", {"score_version": "score-v0.1"})
    assert save(rows, store) == save(rows, store) == 1
    assert len(store.list("legacy_history")) == 1
    assert store.list("legacy_history")[0]["score_version"] == "v6"
    assert store.list("scores")[0]["score_version"] == "score-v0.1"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    with pytest.raises(ValueError):
        normalize([{"symbol": "AAPL", "date": "2026-01-01", "risk": float("nan")}])
    with pytest.raises(ValueError):
        normalize([{"symbol": "AAPL", "date": "not-a-date"}])


def test_loss_simulation_reproducible_and_boundary_cases():
    from goldnam_engine.trade.lab import loss_simulation

    assert loss_simulation(0.4, 2, 0.01) == loss_simulation(0.4, 2, 0.01)
    loss = loss_simulation(0, 2, 0.01)
    assert loss["loss_streak"]["0.5"] == 100
    assert loss["max_drawdown"]["0.5"] == pytest.approx(0.99**100 - 1)
    win = loss_simulation(1, 2, 0.01)
    assert win["loss_streak"]["0.95"] == 0
    assert win["max_drawdown"]["0.05"] == 0


def test_portfolio_cap_updates_all_money_and_gap_risk():
    from goldnam_engine.risk.portfolio import Holding, size_portfolio
    from goldnam_engine.trade.trade_core import Costs

    costs = Costs(buy_fee=0, sell_fee=0, sell_tax=0, slippage=0)
    holding = Holding("OLD", "tech", 290, 100, 99)
    sized = size_portfolio(100000, 71000, 100, 95, 110, "tech", [holding], costs=costs)
    assert sized["수량"] == 10  # remaining sector capacity
    assert sized["매수 투입액"] == 1000
    assert sized["남은 현금"] == 70000
    assert sized["손절 예상손실"] == 50
    assert sized["목표 예상순이익"] == 100
    gap = size_portfolio(100000, 100000, 100, 95, 110, "tech", [], costs=costs, gap_pct=10)
    assert gap["손절 예상손실"] <= 1000
    assert gap["주당 손실"] == 14.5
    assert gap["projected_heat_pct"] == pytest.approx(gap["손절 예상손실"] / 1000)


def test_daily_timing_missing_benchmark_fails_closed():
    from goldnam_engine.scoring.snapshot import timing_snapshot

    from engine.tests.smoke_test import make_momentum

    frame, benchmark = make_momentum()
    missing = timing_snapshot(frame, None, "us")
    assert missing["risk"] is None and not missing["actionable"]
    actual = timing_snapshot(frame, benchmark, "us")
    assert actual["risk"]["earnings"] == "발표일 미확인"
    assert (
        actual["timing"]["preferred"] != "Momentum"
        or actual["timing"]["momentum"]["status"] != "EXTENDED"
    )
    kr_missing_fx = timing_snapshot(frame, benchmark, "kr")
    assert kr_missing_fx["risk"]["score"] is None
    assert kr_missing_fx["risk"]["position_size_multiplier"] == 0
