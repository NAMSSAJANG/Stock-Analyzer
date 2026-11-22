"""Matched random-entry controls and account-level cap simulation."""

from collections import defaultdict
from typing import Any, cast

import numpy as np
import pandas as pd

from goldnam_engine.risk.portfolio import Holding, size_portfolio
from goldnam_engine.trade.exits import ExitMode, run_exits
from goldnam_engine.trade.trade_core import Costs
from goldnam_engine.validation.ranking import block_interval


def trade_statistics(ledger: pd.DataFrame) -> dict[str, Any]:
    if ledger.empty or "status" not in ledger:
        return {"n": 0, "expected_r": None}
    filled = ledger[ledger.status == "filled"].sort_values("entry_date")
    if filled.empty:
        return {"n": 0, "expected_r": None}
    r = filled.r.astype(float)
    returns = filled.net_return.astype(float)
    winners, losers = r[r > 0], r[r < 0]
    streak = maximum = 0
    for value in r:
        streak = streak + 1 if value < 0 else 0
        maximum = max(maximum, streak)
    return {
        "n": len(r),
        "expected_r": float(r.mean()),
        "expected_return": float(returns.mean()),
        "win_fraction": float((r > 0).mean()),
        "payoff_ratio": float(winners.mean() / -losers.mean())
        if len(winners) and len(losers)
        else None,
        "profit_factor": float(winners.sum() / -losers.sum()) if len(losers) else None,
        "max_loss_streak": maximum,
        "average_holding_days": float(filled.holding_days.mean()),
    }


def study_symbol(
    frame: pd.DataFrame,
    history: pd.DataFrame,
    setup: str,
    mode: ExitMode,
    costs: Costs,
    seed: int = 20261123,
) -> tuple[pd.DataFrame, list[pd.DataFrame]]:
    if setup not in {"pullback", "momentum"}:
        raise ValueError("Setup 오류")
    if history.empty:
        return pd.DataFrame(), []
    plans = history[["date", f"{setup}_stop_loss", f"{setup}_target1"]].rename(
        columns={f"{setup}_stop_loss": "stop", f"{setup}_target1": "target"}
    )
    signal_mask = history[f"{setup}_signal"]
    actual = run_exits(frame, plans.loc[signal_mask], mode, costs)
    rng = np.random.default_rng(seed)
    months = pd.DatetimeIndex(history.date).to_period("M")
    counts = pd.Series(months[signal_mask.to_numpy()]).value_counts()
    baselines = []
    for _ in range(20):
        chosen = []
        for month, count in counts.items():
            candidates = np.flatnonzero(months == month)
            chosen.extend(rng.choice(candidates, size=int(count), replace=False).tolist())
        baselines.append(run_exits(frame, plans.iloc[sorted(chosen)], mode, costs))
    return actual, baselines


def event_summary(actual: pd.DataFrame, baselines: list[pd.DataFrame]) -> dict[str, Any]:
    summary = trade_statistics(actual)
    base = [trade_statistics(b) for b in baselines]
    values = [b["expected_r"] for b in base if b["expected_r"] is not None]
    summary["random_repetitions"] = len(baselines)
    summary["random_expected_r"] = float(np.mean(values)) if values else None
    summary["excess_expected_r"] = (
        summary["expected_r"] - summary["random_expected_r"]
        if summary["expected_r"] is not None and values
        else None
    )
    if actual.empty or "status" not in actual:
        summary["excess_ci95"] = (None, None)
        return summary
    filled = actual[actual.status == "filled"].copy()
    if filled.empty:
        summary["excess_ci95"] = (None, None)
        return summary
    filled["month"] = pd.to_datetime(filled.entry_date).dt.to_period("M")
    means = filled.groupby("month").r.mean()
    random_months = []
    for baseline in baselines:
        if baseline.empty or "r" not in baseline:
            continue
        b = baseline[baseline.status == "filled"].copy()
        b["month"] = pd.to_datetime(b.entry_date).dt.to_period("M")
        random_months.append(b.groupby("month").r.mean())
    control = (
        pd.concat(random_months, axis=1).mean(axis=1) if random_months else pd.Series(dtype=float)
    )
    paired = (means - control).dropna()
    summary["monthly_excess_expected_r"] = float(paired.mean()) if len(paired) else None
    summary["excess_ci95"] = block_interval(paired, block=3)
    summary["ci_definition"] = (
        "동일 종목·동일 달 20회 무작위 진입 대비 월별 평균 기대값 차이; 3개월 날짜 블록 부트스트랩"
    )
    return summary


def portfolio_simulation(
    ledger: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    sectors: dict[str, str],
    costs: Costs,
    account: float = 100_000.0,
) -> dict[str, Any]:
    if ledger.empty or "status" not in ledger:
        return {"entries": 0, "return": 0.0, "max_drawdown": 0.0, "curve": [], "rejected": 0}
    trades = ledger[ledger.status == "filled"].copy()
    entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trades.to_dict("records"):
        entries[str(row["entry_date"])[:10]].append(cast(dict[str, Any], row))
    dates = sorted({pd.Timestamp(d).strftime("%Y-%m-%d") for f in frames.values() for d in f.index})
    cash = account
    positions: dict[str, dict[str, Any]] = {}
    curve = []
    accepted = rejected = 0
    for day in dates:
        # Fill exits during the day only after entry sizing based on prior close.
        marks = {
            symbol: float(frame.loc[frame.index < pd.Timestamp(day), "Close"].iloc[-1])
            for symbol, frame in frames.items()
            if symbol in positions and (frame.index < pd.Timestamp(day)).any()
        }
        equity = cash + sum(p["remaining"] * marks.get(s, p["entry"]) for s, p in positions.items())
        for trade in sorted(entries.get(day, []), key=lambda r: str(r["symbol"])):
            symbol = str(trade["symbol"])
            if symbol in positions:
                rejected += 1
                continue
            holdings = [
                Holding(
                    s,
                    sectors.get(s, "미확인"),
                    p["remaining"],
                    marks.get(s, p["entry"]),
                    min(p["stop"], marks.get(s, p["entry"])),
                )
                for s, p in positions.items()
            ]
            plan = size_portfolio(
                equity,
                min(cash, equity),
                float(trade["entry"]),
                float(trade["stop"]),
                float(trade["target"]),
                sectors.get(symbol, "미확인"),
                holdings,
                costs=costs,
            )
            q = int(plan["수량"])
            if q <= 0:
                rejected += 1
                continue
            cash -= q * float(costs.buy_unit(trade["entry"]))
            positions[symbol] = {**trade, "quantity": q, "remaining": q}
            accepted += 1
        for symbol, p in list(positions.items()):
            for index, fill in enumerate(p["fills"]):
                if str(fill["date"])[:10] != day:
                    continue
                q = p["remaining"] if index == len(p["fills"]) - 1 else p["quantity"] // 2
                cash += q * float(costs.sell_unit(fill["price"]))
                p["remaining"] -= q
            if p["remaining"] == 0:
                del positions[symbol]
        value = cash
        for symbol, p in positions.items():
            frame = frames[symbol]
            available = frame.loc[frame.index <= pd.Timestamp(day), "Close"]
            value += p["remaining"] * float(available.iloc[-1])
        curve.append({"date": day, "equity": value, "positions": len(positions)})
    values = np.array([account, *[r["equity"] for r in curve]])
    return {
        "entries": accepted,
        "rejected": rejected,
        "return": float(values[-1] / account - 1),
        "max_drawdown": float((values / np.maximum.accumulate(values) - 1).min()),
        "curve": curve,
        "caveat": "정수 수량; 알 수 없는 업종은 하나의 미확인 그룹으로 제한. 기존 포지션의 최초 손절 기준 보수적 히트. 동일 날짜는 티커 순서, 미래 성과로 선택하지 않음.",
    }
