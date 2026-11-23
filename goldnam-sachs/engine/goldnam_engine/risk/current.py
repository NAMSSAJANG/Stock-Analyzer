"""Live FX and explicit unknown-event risk; no invented liquidity fallback."""

from dataclasses import dataclass, field
from typing import Any

from goldnam_engine.data.contracts import DataResult
from goldnam_engine.models import MarketRegimeSnapshot, TechnicalSnapshot
from goldnam_engine.scoring.scoring_utils import scale


@dataclass(frozen=True)
class RiskState:
    score: float | None
    level: str
    extension: str
    earnings: str
    liquidity: str
    position_size_multiplier: float
    components: dict[str, float | None]
    coverage: float
    badges: list[str] = field(default_factory=list)
    fx: dict[str, Any] | None = None


def build_risk_snapshot(
    tech: TechnicalSnapshot,
    market: MarketRegimeSnapshot,
    earnings_days: int | None = None,
    fx: DataResult[float] | None = None,
) -> RiskState:
    extension_score = scale(max(tech.dist_ema20_atr, 0) + max(tech.rsi - 70, 0) / 8, 0.5, 3.5)
    extension = (
        "Normal"
        if extension_score < 35
        else "Elevated"
        if extension_score < 65
        else "High"
        if extension_score < 85
        else "Extreme"
    )
    volatility = scale(tech.atr_pct, 1.3, 7.0)
    badges = []
    if earnings_days is None or earnings_days < 0:
        event, earnings = 50.0, "발표일 미확인"
        badges.append(earnings)
    elif earnings_days <= 2:
        event, earnings = 95.0, f"실적 임박 D-{earnings_days}"
    elif earnings_days <= 7:
        event, earnings = 78.0, f"실적 예정 D-{earnings_days}"
    elif earnings_days <= 21:
        event, earnings = 45.0, f"실적 예정 D-{earnings_days}"
    else:
        event, earnings = 20.0, f"실적 예정 D-{earnings_days}"
    dollars: float | None = tech.dollar_volume
    fx_meta = None
    if market.market.upper() == "KR":
        if fx and fx.usable and fx.data and fx.data > 0:
            dollars = tech.dollar_volume / fx.data
            fx_meta = {
                "value": fx.data,
                "as_of": str(fx.as_of),
                "status": fx.status,
                "source": fx.source,
            }
            if fx.status == "stale":
                badges.append("환율 최근 성공값 · stale")
        else:
            dollars = None
            badges.append("환율 없음 · 유동성/수량 산출 불가")
    liquidity_score: float | None
    if dollars is None:
        liquidity_score, liquidity = None, "미확인"
    elif dollars >= 100_000_000:
        liquidity_score, liquidity = 10.0, "High"
    elif dollars >= 20_000_000:
        liquidity_score, liquidity = 25.0, "Normal"
    elif dollars >= 5_000_000:
        liquidity_score, liquidity = 50.0, "Thin"
    else:
        liquidity_score, liquidity = 78.0, "Weak"
    components = {
        "extension": extension_score,
        "volatility": volatility,
        "earnings": event,
        "liquidity": liquidity_score,
        "market": 100 - market.score if market.data_quality > 0 else None,
    }
    weights = {
        "extension": 0.34,
        "volatility": 0.22,
        "earnings": 0.20,
        "liquidity": 0.10,
        "market": 0.14,
    }
    coverage = sum(weights[k] for k, v in components.items() if v is not None)
    score = (
        sum(v * weights[k] for k, v in components.items() if v is not None)
        if all(v is not None for v in components.values())
        else None
    )
    level = (
        "미확인"
        if score is None
        else "LOW"
        if score < 30
        else "MODERATE"
        if score < 55
        else "HIGH"
        if score < 75
        else "EXTREME"
    )
    multiplier = (
        0.0
        if score is None
        else 1.0
        if score < 30
        else 0.75
        if score < 55
        else 0.5
        if score < 75
        else 0.25
    )
    # Event proximity always limits size, even if other components dilute the total.
    if earnings_days is not None and 0 <= earnings_days <= 7:
        multiplier = min(multiplier, 0.25 if earnings_days <= 2 else 0.5)
    return RiskState(
        round(score) if score is not None else None,
        level,
        extension,
        earnings,
        liquidity,
        multiplier,
        components,
        coverage,
        badges,
        fx_meta,
    )
