"""A/B/C next-open execution with complete-window and non-overlap guards."""

from decimal import Decimal
from typing import Any, Literal, cast

import numpy as np
import pandas as pd

from goldnam_engine.strategy import STRATEGY
from goldnam_engine.trade.trade_core import Costs

ExitMode = Literal["A", "B", "C"]


def run_exits(
    frame: pd.DataFrame, signals: pd.DataFrame, mode: ExitMode = "A", costs: Costs | None = None
) -> pd.DataFrame:
    if mode not in {"A", "B", "C"}:
        raise ValueError("청산 방식은 A/B/C")
    required = ["Open", "High", "Low", "Close"]
    if not set(required).issubset(frame) or not {"date", "stop", "target"}.issubset(signals):
        raise ValueError("OHLC와 신호일·손절·목표 필요")
    d = frame[required].astype(float).copy()
    d.index = pd.DatetimeIndex(d.index).tz_localize(None).normalize()
    if (
        d.index.has_duplicates
        or not d.index.is_monotonic_increasing
        or not np.isfinite(d.to_numpy()).all()
        or (d <= 0).any().any()
    ):
        raise ValueError("가격 날짜/결측 오류")
    if (d.High < d[["Open", "Close", "Low"]].max(axis=1)).any() or (
        d.Low > d[["Open", "Close", "High"]].min(axis=1)
    ).any():
        raise ValueError("OHLC 범위 오류")
    s = signals.copy()
    s.index = pd.DatetimeIndex(pd.to_datetime(s.date)).tz_localize(None).normalize()
    if (
        s.index.has_duplicates
        or not s.index.is_monotonic_increasing
        or not s.index.isin(d.index).all()
    ):
        raise ValueError("신호 날짜 오류")
    cost = costs or Costs()
    holding = STRATEGY.holding_a if mode == "A" else STRATEGY.holding_bc
    prior = d.Close.shift(1)
    atr = (
        pd.concat([d.High - d.Low, (d.High - prior).abs(), (d.Low - prior).abs()], axis=1)
        .max(axis=1)
        .ewm(alpha=1 / 14, adjust=False)
        .mean()
    )
    ma20 = d.Close.rolling(20).mean()
    positions = {day: i for i, day in enumerate(d.index)}
    records = []
    last_exit = -1
    for label, signal in s.iterrows():
        day = cast(pd.Timestamp, label)
        i = positions[day]
        entry_pos, deadline = i + 1, i + holding
        row: dict[str, Any] = {"date": day.isoformat(), "mode": mode, "status": "excluded"}
        if entry_pos <= last_exit:
            row["reason"] = "기존 포지션 보유 중"
        elif deadline >= len(d):
            row["reason"] = "최대 보유기간 데이터 부족"
        else:
            entry, stop, target = (
                float(d.Open.iloc[entry_pos]),
                float(signal.stop),
                float(signal.target),
            )
            if not np.isfinite([stop, target]).all() or not 0 < stop < entry < target:
                row["reason"] = "다음 시가가 계획 범위 밖"
            else:
                original_stop = stop
                remaining, proceeds = Decimal(1), Decimal(0)
                highest = float(d.High.iloc[i])
                partial = False
                pending_close_exit = False
                exit_pos, reason = deadline, "기간 종료"
                fills = []
                for j in range(entry_pos, deadline + 1):
                    bar = d.iloc[j]
                    fill: float | None = None
                    # Known opening gaps take precedence; within a bar stop wins.
                    if bar.Open <= stop:
                        fill, reason = float(bar.Open), "손절 갭"
                    elif pending_close_exit:
                        fill, reason = float(bar.Open), "전일 종가 20일선 이탈"
                    elif mode == "A" and bar.Open >= target:
                        fill, reason = target, "목표 갭 (목표가 체결)"
                    elif bar.Low <= stop:
                        fill, reason = stop, "손절 우선"
                    elif mode == "A" and bar.High >= target:
                        fill, reason = target, "목표"
                    if fill is not None:
                        proceeds += remaining * cost.sell_unit(fill)
                        fills.append(
                            {
                                "date": d.index[j].isoformat(),
                                "fraction": float(remaining),
                                "price": fill,
                            }
                        )
                        exit_pos = j
                        remaining = Decimal(0)
                        break
                    if mode == "B" and not partial and bar.High >= target:
                        proceeds += Decimal(".5") * cost.sell_unit(target)
                        remaining = Decimal(".5")
                        fills.append(
                            {"date": d.index[j].isoformat(), "fraction": 0.5, "price": target}
                        )
                        partial = True
                        stop = max(stop, entry)  # effective next bar; no intra-bar lookahead
                    if mode == "C" or (mode == "B" and partial):
                        highest = max(highest, float(bar.High))
                        stop = max(stop, highest - STRATEGY.trail_atr * float(atr.iloc[j]))
                        pending_close_exit = bool(
                            pd.notna(ma20.iloc[j]) and bar.Close < ma20.iloc[j]
                        )
                if remaining:
                    proceeds += remaining * cost.sell_unit(float(d.Close.iloc[deadline]))
                    fills.append(
                        {
                            "date": d.index[deadline].isoformat(),
                            "fraction": float(remaining),
                            "price": float(d.Close.iloc[deadline]),
                        }
                    )
                unit = cost.buy_unit(entry)
                risk = unit - cost.sell_unit(original_stop)
                pnl = proceeds - unit
                row.update(
                    status="filled",
                    reason=reason,
                    entry_date=d.index[entry_pos].isoformat(),
                    exit_date=d.index[exit_pos].isoformat(),
                    entry=entry,
                    stop=original_stop,
                    target=target,
                    holding_days=exit_pos - entry_pos + 1,
                    net_return=float(pnl / unit),
                    r=float(pnl / risk),
                    unit_cost=float(unit),
                    proceeds=float(proceeds),
                    fills=fills,
                )
                last_exit = exit_pos
        records.append(row)
    return pd.DataFrame(records)
