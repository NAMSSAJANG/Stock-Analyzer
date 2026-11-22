import pandas as pd

from goldnam_engine.models import MarketRegimeSnapshot
from goldnam_engine.strategy import STRATEGY


def build_regime(frame: pd.DataFrame, market: str) -> MarketRegimeSnapshot | None:
    if "Close" not in frame or len(frame) < 220 or frame.Close.tail(220).isna().any():
        return None
    close = frame.Close.astype(float)
    ma200 = close.rolling(200).mean()
    components = {
        "above_ma200": 100.0 if close.iloc[-1] > ma200.iloc[-1] else 0.0,
        "ma50_above_ma200": 100.0 if close.tail(50).mean() > ma200.iloc[-1] else 0.0,
        "ma200_rising": 100.0 if ma200.iloc[-1] > ma200.iloc[-21] else 0.0,
    }
    score = sum(components.values()) / len(components)
    label = (
        "우호"
        if score >= STRATEGY.regime_favorable
        else "비우호"
        if score < STRATEGY.regime_unfavorable
        else "중립"
    )
    return MarketRegimeSnapshot(
        market.upper(), score, label, components, {}, 1.0, "지수 가격 기준 · 순위 점수에 미반영"
    )


def regime_multiplier(regime: MarketRegimeSnapshot | None) -> float:
    return (
        0.0
        if regime is None
        else 1.0
        if regime.label == "우호"
        else 0.75
        if regime.label == "중립"
        else 0.5
    )
