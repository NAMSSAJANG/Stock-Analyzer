from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, cast

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class OptionSummary:
    call_volume: int
    put_volume: int
    call_oi: int
    put_oi: int
    volume_ratio: float
    oi_ratio: float
    call_iv: float
    put_iv: float
    atm_iv: float
    call_wall: float | None
    put_wall: float | None
    max_pain: float | None
    expected_move: float
    expected_low: float
    expected_high: float
    confirmation: str
    interpretation: str
    data_quality: float


@dataclass(frozen=True)
class OptionEntry:
    score: float
    factors: dict[str, float]
    interpretation: str
    details: dict[str, str]


def _number(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
        return cast(float, value) if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _total(frame: pd.DataFrame, column: str) -> int:
    if column not in frame:
        return 0
    return int(pd.to_numeric(frame[column], errors="coerce").fillna(0).clip(lower=0).sum())


def _weighted_iv(frame: pd.DataFrame) -> float:
    if frame.empty or "impliedVolatility" not in frame:
        return float("nan")
    iv = pd.to_numeric(frame["impliedVolatility"], errors="coerce")
    weights = (
        cast(pd.Series, pd.to_numeric(frame.get("openInterest", 1), errors="coerce"))
        .fillna(0)
        .clip(lower=0)
    )
    valid = iv.between(0.001, 10) & iv.notna()
    if not valid.any():
        return float("nan")
    weights = weights[valid]
    return (
        float(np.average(iv[valid], weights=weights))
        if weights.sum()
        else float(iv[valid].median())
    )


def _oi_wall(frame: pd.DataFrame) -> float | None:
    if frame.empty or not {"strike", "openInterest"}.issubset(frame.columns):
        return None
    oi = pd.to_numeric(frame["openInterest"], errors="coerce").fillna(0)
    if oi.max() <= 0:
        return None
    return float(pd.to_numeric(frame.loc[cast(Any, oi.idxmax()), "strike"], errors="coerce"))


def _atm_row(frame: pd.DataFrame, spot: float) -> pd.Series | None:
    if frame.empty or "strike" not in frame:
        return None
    strikes = pd.to_numeric(frame["strike"], errors="coerce")
    valid = strikes.notna()
    return frame.loc[cast(Any, (strikes[valid] - spot).abs().idxmin())] if valid.any() else None


def calculate_max_pain(calls: pd.DataFrame, puts: pd.DataFrame) -> float | None:
    """Settlement strike that minimizes aggregate intrinsic payout."""
    if calls.empty and puts.empty:
        return None

    def normalized(frame: pd.DataFrame) -> pd.DataFrame:
        strikes = (
            pd.to_numeric(frame["strike"], errors="coerce")
            if "strike" in frame
            else pd.Series(index=frame.index, dtype=float)
        )
        oi = (
            pd.to_numeric(frame["openInterest"], errors="coerce").fillna(0)
            if "openInterest" in frame
            else pd.Series(0.0, index=frame.index)
        )
        return frame.assign(strike=strikes, oi=oi).dropna(subset=["strike"])

    c, p = normalized(calls), normalized(puts)
    strikes = sorted(set(c.strike) | set(p.strike))
    if not strikes or c.oi.sum() + p.oi.sum() <= 0:
        return None
    payouts = {
        s: ((s - c.strike).clip(lower=0) * c.oi).sum() + ((p.strike - s).clip(lower=0) * p.oi).sum()
        for s in strikes
    }
    return float(min(payouts, key=cast(Callable[[Any], float], payouts.get)))


def summarize_options(
    calls: pd.DataFrame, puts: pd.DataFrame, spot: float, expiry: str, today: date | None = None
) -> OptionSummary:
    call_volume, put_volume = _total(calls, "volume"), _total(puts, "volume")
    call_oi, put_oi = _total(calls, "openInterest"), _total(puts, "openInterest")
    volume_ratio = put_volume / call_volume if call_volume else float("nan")
    oi_ratio = put_oi / call_oi if call_oi else float("nan")
    call_iv, put_iv = _weighted_iv(calls), _weighted_iv(puts)
    call_atm, put_atm = _atm_row(calls, spot), _atm_row(puts, spot)
    atm_ivs = [
        _number(row.get("impliedVolatility"), float("nan"))
        for row in (call_atm, put_atm)
        if row is not None
    ]
    atm_ivs = [x for x in atm_ivs if math.isfinite(x) and x > 0]
    fallback_ivs = [x for x in (call_iv, put_iv) if math.isfinite(x)]
    atm_iv = (
        float(np.mean(atm_ivs))
        if atm_ivs
        else (float(np.mean(fallback_ivs)) if fallback_ivs else float("nan"))
    )
    today = today or datetime.now().date()
    days = max((datetime.strptime(expiry, "%Y-%m-%d").date() - today).days, 1)
    # ATM straddle is the most intuitive expiry move; IV is a robust fallback for sparse quotes.
    premiums = []
    for row in (call_atm, put_atm):
        if row is None:
            continue
        mid = (_number(row.get("bid")) + _number(row.get("ask"))) / 2
        premiums.append(mid if mid > 0 else _number(row.get("lastPrice")))
    straddle_move = sum(premiums) if len(premiums) == 2 and all(x > 0 for x in premiums) else 0
    iv_move = spot * atm_iv * math.sqrt(days / 365) if math.isfinite(atm_iv) else 0
    expected_move = straddle_move or iv_move
    ratios = [x for x in (volume_ratio, oi_ratio) if math.isfinite(x)]
    blended = float(np.mean(ratios)) if ratios else 1.0
    if blended <= 0.75:
        confirmation = "Bullish confirmation"
        direction = "콜 활동이 상대적으로 우세합니다."
    elif blended >= 1.25:
        confirmation = "Bearish / hedge-heavy"
        direction = "풋 활동이 상대적으로 높아 하방 경계 또는 헤지 수요가 관찰됩니다."
    else:
        confirmation = "Neutral confirmation"
        direction = "콜과 풋 활동이 대체로 균형적입니다."
    volatility = (
        "내재변동성이 높아 가격 변동 폭이 클 수 있습니다."
        if math.isfinite(atm_iv) and atm_iv >= 0.50
        else "내재변동성은 극단적으로 높지 않습니다."
    )
    interpretation = f"{direction} {volatility} 옵션은 헤지·스프레드 거래도 포함하므로 방향을 단정하는 신호가 아니라 현물 분석의 보조 확인값으로 해석하세요."
    available_fields = sum(
        x > 0 for x in (call_volume + put_volume, call_oi + put_oi, expected_move)
    ) + int(math.isfinite(atm_iv))
    quality = available_fields / 4
    return OptionSummary(
        call_volume,
        put_volume,
        call_oi,
        put_oi,
        volume_ratio,
        oi_ratio,
        call_iv,
        put_iv,
        atm_iv,
        _oi_wall(calls),
        _oi_wall(puts),
        calculate_max_pain(calls, puts),
        expected_move,
        max(0, spot - expected_move),
        spot + expected_move,
        confirmation,
        interpretation,
        quality,
    )


def option_bias(summary: OptionSummary) -> str:
    ratios = [value for value in (summary.volume_ratio, summary.oi_ratio) if math.isfinite(value)]
    if not ratios:
        return "Neutral"
    blended = float(np.mean(ratios))
    if blended <= 0.65:
        return "Bullish"
    if blended <= 0.90:
        return "Mild Bullish"
    if blended < 1.10:
        return "Neutral"
    if blended < 1.50:
        return "Mild Bearish"
    return "Bearish"


def option_entry_readiness(
    summary: OptionSummary, calls: pd.DataFrame, puts: pd.DataFrame, spot: float, expiry: str
) -> OptionEntry:
    bias = option_bias(summary)
    direction = {
        "Bullish": 88,
        "Mild Bullish": 72,
        "Neutral": 50,
        "Mild Bearish": 68,
        "Bearish": 82,
    }[bias]
    total_oi, total_volume = (
        summary.call_oi + summary.put_oi,
        summary.call_volume + summary.put_volume,
    )
    activity = min(100, 18 * math.log10(max(total_oi, 1)) + 12 * math.log10(max(total_volume, 1)))
    spreads = []
    for frame in (calls, puts):
        if not {"strike", "bid", "ask"}.issubset(frame.columns):
            continue
        nearby = frame.loc[
            (pd.to_numeric(frame["strike"], errors="coerce") - spot).abs().nsmallest(5).index
        ]
        for _, row in nearby.iterrows():
            bid, ask = _number(row.get("bid")), _number(row.get("ask"))
            mid = (bid + ask) / 2
            if mid > 0 and ask >= bid:
                spreads.append((ask - bid) / mid)
    median_spread = float(np.median(spreads)) if spreads else 0.5
    spread_score = max(0, 100 - median_spread * 180)
    liquidity = 0.6 * activity + 0.4 * spread_score
    iv_efficiency = (
        50 if not math.isfinite(summary.atm_iv) else max(0, min(100, 100 - summary.atm_iv * 100))
    )
    if bias in ("Bullish", "Mild Bullish"):
        reward = (
            summary.call_wall - spot
            if summary.call_wall and summary.call_wall > spot
            else summary.expected_move
        )
        risk = (
            spot - summary.put_wall
            if summary.put_wall and summary.put_wall < spot
            else summary.expected_move
        )
    elif bias in ("Bearish", "Mild Bearish"):
        reward = (
            spot - summary.put_wall
            if summary.put_wall and summary.put_wall < spot
            else summary.expected_move
        )
        risk = (
            summary.call_wall - spot
            if summary.call_wall and summary.call_wall > spot
            else summary.expected_move
        )
    else:
        reward = risk = summary.expected_move
    rr = reward / max(risk, 1e-9) if reward > 0 else 0
    risk_reward = max(0, min(100, 35 + rr * 30))
    days = max((datetime.strptime(expiry, "%Y-%m-%d").date() - datetime.now().date()).days, 1)
    time_decay = max(0, min(100, (days - 5) / 40 * 100))
    factors = {
        "Direction": direction,
        "IV Efficiency": iv_efficiency,
        "Liquidity": liquidity,
        "Risk / Reward": risk_reward,
        "Time / DTE": time_decay,
    }
    details = {
        "Direction": f"Option Bias {bias}를 진입 방향 확인도로 변환했습니다.",
        "IV Efficiency": f"ATM IV {_fmt_iv(summary.atm_iv)}입니다. IV가 높을수록 매수 프리미엄 부담을 크게 봅니다.",
        "Liquidity": f"총 OI {total_oi:,}, 거래량 {total_volume:,}, 근접 행사가 중간 호가 스프레드 {median_spread * 100:.1f}%를 반영합니다.",
        "Risk / Reward": f"주요 OI Wall과 예상 변동범위의 보상/위험 비율 {rr:.2f}배를 반영합니다.",
        "Time / DTE": f"선택 만기까지 {days}일입니다. 5일 이하는 시간가치 감소 위험을 가장 높게 봅니다.",
    }
    weights = {
        "Direction": 0.30,
        "IV Efficiency": 0.15,
        "Liquidity": 0.25,
        "Risk / Reward": 0.20,
        "Time / DTE": 0.10,
    }
    score = round(sum(factors[k] * weights[k] for k in factors), 1)
    if liquidity < 45:
        note = "방향성보다 유동성 부족과 넓은 호가가 우선 위험요인입니다."
    elif iv_efficiency < 45 and bias in ("Bullish", "Mild Bullish"):
        note = "상승 방향성은 있지만 IV와 프리미엄 부담이 높아 단순 Call보다 손익이 제한된 스프레드 구조를 함께 비교할 환경입니다."
    elif time_decay < 40:
        note = (
            "만기가 짧아 시간가치 감소 민감도가 높으므로 포지션 유지기간을 보수적으로 봐야 합니다."
        )
    else:
        note = "방향성·유동성·만기 구조가 대체로 균형적이지만 최대손실과 손익분기점을 별도로 확인해야 합니다."
    return OptionEntry(score, {k: round(v, 1) for k, v in factors.items()}, note, details)


def price_confluence(
    summary: OptionSummary, support: float | None, resistance: float | None, spot: float
) -> tuple[str, str]:
    tolerance = max(abs(spot) * 0.025, 1e-9)
    support_match = (
        support is not None
        and summary.put_wall is not None
        and abs(support - summary.put_wall) <= tolerance
    )
    resistance_match = (
        resistance is not None
        and summary.call_wall is not None
        and abs(resistance - summary.call_wall) <= tolerance
    )
    if support_match and resistance_match:
        return "HIGH CONFLUENCE", "기술적 지지·저항과 옵션 주요 Strike가 모두 근접합니다."
    if support_match or resistance_match:
        return (
            "PARTIAL CONFLUENCE",
            "한쪽 주요 가격대가 일치하며 다른 구간은 추가 확인이 필요합니다.",
        )
    return (
        "DIVERGENCE",
        "기술적 가격대와 옵션 OI 집중 구간이 달라 단기 반응을 확인할 필요가 있습니다.",
    )


def _fmt_ratio(value: float) -> str:
    return "—" if not math.isfinite(value) else f"{value:.2f}"


def _fmt_iv(value: float) -> str:
    return "—" if not math.isfinite(value) else f"{value * 100:.1f}%"
