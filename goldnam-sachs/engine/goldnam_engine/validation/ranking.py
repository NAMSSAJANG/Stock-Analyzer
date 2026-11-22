"""Monthly next-open cross-sectional validation, HAC inference and date-block CI."""

from math import ceil
from typing import Any

import numpy as np
import pandas as pd


def newey_west_t(values: pd.Series, lag: int = 2) -> float | None:
    x = values.dropna().to_numpy(dtype=float)
    if len(x) < 6:
        return None
    centered = x - x.mean()
    variance = float(centered @ centered / len(x))
    for k in range(1, min(lag + 1, len(x))):
        variance += 2 * (1 - k / (lag + 1)) * float(centered[k:] @ centered[:-k] / len(x))
    return float(x.mean() / np.sqrt(variance / len(x))) if variance > 1e-15 else None


def block_interval(
    values: pd.Series, block: int = 3, iterations: int = 2000, seed: int = 20261123
) -> tuple[float | None, float | None]:
    x = values.dropna().to_numpy(dtype=float)
    if len(x) < 6:
        return None, None
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, len(x), size=(iterations, ceil(len(x) / block)))
    indices = (starts[:, :, None] + np.arange(block)) % len(x)
    samples = x[indices.reshape(iterations, -1)[:, : len(x)]].mean(axis=1)
    low, high = np.quantile(samples, [0.025, 0.975])
    return float(low), float(high)


def evidence(t_stat: float | None, oos_net: float | None, ic: float | None) -> str:
    if t_stat is None or oos_net is None or ic is None:
        return "미검증"
    if ic <= 0 or oos_net <= 0:
        return "근거 없음"
    return "근거 있음" if t_stat >= 2 else "근거 약함"


def summarize(months: pd.DataFrame, horizon: int) -> dict[str, Any]:
    if months.empty:
        return {"months": 0, "evidence": "미검증"}
    ic = months.ic.dropna()
    lag = max(1, ceil(horizon / 21) - 1)
    t_stat = newey_west_t(ic, lag)
    oos = months.loc[months.index >= "2020-01-01", "net_spread"].dropna()
    mean_ic = float(ic.mean()) if len(ic) else None
    return {
        "months": len(months),
        "ic_mean": mean_ic,
        "ic_t": t_stat,
        "ic_positive_fraction": float((ic > 0).mean()) if len(ic) else None,
        "spread": float(months.spread.mean()),
        "net_spread": float(months.net_spread.mean()),
        "spread_ci95": block_interval(months.spread, max(3, ceil(horizon / 21))),
        "net_spread_ci95": block_interval(months.net_spread, max(3, ceil(horizon / 21))),
        "oos_net_spread": float(oos.mean()) if len(oos) else None,
        "turnover_top": float(months.turnover_top.mean()),
        "quintiles": {
            str(q): {
                "mean": float(months[f"q{q}"].mean()),
                "excess": float((months[f"q{q}"] - months.universe).mean()),
                "excess_ci95": block_interval(months[f"q{q}"] - months.universe),
            }
            for q in range(1, 6)
        },
        "evidence": evidence(t_stat, float(oos.mean()) if len(oos) else None, mean_ic),
    }


def rank_study(
    scores: pd.DataFrame,
    opens: pd.DataFrame,
    horizon: int = 21,
    round_trip_cost: float = 0.002,
    regimes: pd.Series | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if horizon not in {21, 63} or not 0 <= round_trip_cost < 1:
        raise ValueError("검증 기간/비용 오류")
    if opens.index.has_duplicates or not opens.index.is_monotonic_increasing:
        raise ValueError("가격 날짜 순서 오류")
    scores = scores.reindex(index=opens.index, columns=opens.columns).replace(
        [np.inf, -np.inf], np.nan
    )
    returns = opens.shift(-horizon - 1) / opens.shift(-1) - 1
    monthends = opens.groupby(pd.DatetimeIndex(opens.index).to_period("M")).tail(1).index
    records = []
    previous_top: set[str] = set()
    previous_bottom: set[str] = set()
    for day in monthends:
        score = scores.loc[day].dropna()
        # Formation uses all known scores, never future return availability.
        if len(score) < 10 or score.nunique() < 5:
            continue
        quantiles = np.ceil(score.rank(pct=True) * 5).clip(1, 5).astype(int)
        top, bottom = set(score.index[quantiles == 5]), set(score.index[quantiles == 1])
        turnover_top = 1 - len(top & previous_top) / len(previous_top) if previous_top else 1.0
        turnover_bottom = (
            1 - len(bottom & previous_bottom) / len(previous_bottom) if previous_bottom else 1.0
        )
        previous_top, previous_bottom = top, bottom
        forward = returns.loc[day].reindex(score.index)
        valid = forward.notna()
        if valid.sum() < 10:
            continue
        ranked_s = score[valid].rank()
        ranked_r = forward[valid].rank()
        ic = ranked_s.corr(ranked_r) if ranked_r.nunique() > 1 else np.nan
        row = {
            "date": day,
            "ic": ic,
            "universe": forward.mean(),
            "n": int(valid.sum()),
            "coverage": float(valid.mean()),
            "turnover_top": turnover_top,
            "regime": regimes.get(day, "미확인") if regimes is not None else "미확인",
        }
        for q in range(1, 6):
            row[f"q{q}"] = forward[quantiles == q].mean()
        row["spread"] = row["q5"] - row["q1"]
        row["net_spread"] = row["spread"] - round_trip_cost * (turnover_top + turnover_bottom)
        records.append(row)
    detail = pd.DataFrame(records)
    if detail.empty:
        return detail, {"months": 0, "evidence": "미검증"}
    detail = detail.set_index("date")
    summary = summarize(detail, horizon)
    summary["horizon"] = horizon
    summary["round_trip_cost"] = round_trip_cost
    summary["periods"] = {
        "2015-2019": summarize(detail.loc[detail.index < "2020-01-01"], horizon),
        "2020-present": summarize(detail.loc[detail.index >= "2020-01-01"], horizon),
    }
    summary["regimes"] = {
        str(label): summarize(group, horizon) for label, group in detail.groupby("regime")
    }
    summary["caveat"] = (
        "현재 구성 생존 편향; 미래 수익 결측은 coverage로 공시. 거래세·체결비용 가정은 고정 시나리오. 공매도 대차비용 제외."
    )
    return detail, summary
