from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import yfinance as yf

from .models import Analysis


def _num(value, default=0.0) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _clip(value: float) -> int:
    return int(round(max(0, min(100, value))))


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def _returns(close: pd.Series) -> dict[str, float | None]:
    periods = {"7일": 5, "1개월": 21, "3개월": 63, "1년": 252}
    result = {}
    for label, days in periods.items():
        result[label] = ((close.iloc[-1] / close.iloc[-days - 1] - 1) * 100) if len(close) > days else None
    return result


def analyze_stock(ticker_text: str, market_score: int = 50) -> Analysis:
    ticker = ticker_text.upper().strip()
    if not ticker:
        raise ValueError("티커를 입력해 주세요.")
    obj = yf.Ticker(ticker)
    history = obj.history(period="2y", interval="1d", auto_adjust=True)
    if history.empty or len(history) < 30:
        raise ValueError(f"{ticker}의 분석 가능한 가격 데이터가 부족합니다.")
    history = history.dropna(subset=["Close"]).copy()
    close, volume = history["Close"], history["Volume"]
    for window in (20, 50, 200):
        history[f"MA{window}"] = close.rolling(window).mean()
    history["RSI"] = _rsi(close)
    tr = pd.concat([
        history["High"] - history["Low"],
        (history["High"] - close.shift()).abs(),
        (history["Low"] - close.shift()).abs(),
    ], axis=1).max(axis=1)
    history["ATR"] = tr.rolling(14).mean()

    try:
        info = obj.info or {}
    except Exception:
        info = {}
    price = _num(close.iloc[-1])
    ma20, ma50, ma200 = (_num(history[f"MA{w}"].iloc[-1], price) for w in (20, 50, 200))
    rsi = _num(history["RSI"].iloc[-1], 50)
    atr = _num(history["ATR"].iloc[-1], price * .025)
    vol_ratio = _num(volume.tail(5).mean() / max(volume.tail(20).mean(), 1), 1)
    high52 = _num(close.tail(252).max(), price)
    low52 = _num(close.tail(252).min(), price)

    technical = 50
    technical += 10 if price > ma20 else -8
    technical += 10 if ma20 > ma50 else -8
    technical += 12 if ma50 > ma200 else -10
    technical += 6 if 42 <= rsi <= 65 else (-6 if rsi > 75 or rsi < 30 else 0)
    technical += 4 if vol_ratio > 1.15 and close.pct_change(5).iloc[-1] > 0 else 0
    technical = _clip(technical)

    fundamental = 50
    roe = _num(info.get("returnOnEquity"))
    margin = _num(info.get("profitMargins"))
    growth = _num(info.get("revenueGrowth"))
    debt = _num(info.get("debtToEquity"), 100)
    forward_pe = _num(info.get("forwardPE"), 0)
    fundamental += 12 if roe > .15 else (-6 if roe < 0 else 0)
    fundamental += 10 if margin > .12 else (-8 if margin < 0 else 0)
    fundamental += 10 if growth > .10 else (-5 if growth < 0 else 0)
    fundamental += 8 if debt < 80 else (-8 if debt > 200 else 0)
    fundamental += 5 if 0 < forward_pe < 30 else (-3 if forward_pe > 60 else 0)
    fundamental = _clip(fundamental)

    news_items = []
    try:
        for item in (obj.news or [])[:5]:
            content = item.get("content", item)
            news_items.append({
                "title": content.get("title", "제목 없음"),
                "publisher": content.get("provider", {}).get("displayName", item.get("publisher", "")),
                "url": content.get("canonicalUrl", {}).get("url", item.get("link", "")),
            })
    except Exception:
        pass
    momentum = _num(close.pct_change(5).iloc[-1])
    news_score = _clip(50 + np.sign(momentum) * min(abs(momentum) * 300, 12)) if news_items else 50
    overall = _clip(fundamental * .30 + technical * .40 + market_score * .20 + news_score * .10)

    swing_low = history["Low"].tail(60).rolling(5, center=True).min()
    swing_high = history["High"].tail(60).rolling(5, center=True).max()
    lows = history.loc[history["Low"].eq(swing_low), "Low"].tail(3).tolist()
    highs = history.loc[history["High"].eq(swing_high), "High"].tail(3).tolist()
    supports_raw = [v for v in [ma20, ma50, ma200, *lows] if v < price]
    resist_raw = [v for v in [high52, *highs] if v > price]
    supports_raw = sorted(set(round(v, 4) for v in supports_raw), reverse=True)[:3]
    resist_raw = sorted(set(round(v, 4) for v in resist_raw))[:3]
    supports = [(v, "이동평균/최근 저점 기반") for v in supports_raw] or [(price - atr * 1.5, "ATR 기반")]
    resistances = [(v, "최근 고점/52주 고점 기반") for v in resist_raw] or [(price + atr * 2, "ATR 기반")]
    entry_high = min(price, supports[0][0] + atr * .45)
    entry_low = max(supports[0][0] - atr * .45, 0.01)
    invalidation = max(min(v for v, _ in supports) - atr * .6, 0.01)
    target = resistances[0][0]

    positives, cautions = [], []
    if price > ma200: positives.append("현재가가 200일 이동평균선 위로 장기 상승 구조입니다.")
    else: cautions.append("현재가가 200일 이동평균선 아래로 장기 추세 확인이 필요합니다.")
    if ma20 > ma50: positives.append("20일선이 50일선 위에 있어 중단기 모멘텀이 우호적입니다.")
    else: cautions.append("20일선이 50일선 아래로 단기 반등의 지속성을 확인해야 합니다.")
    if rsi > 72: cautions.append(f"RSI {rsi:.1f}로 단기 과열 부담이 있습니다.")
    elif rsi < 35: cautions.append(f"RSI {rsi:.1f}로 약세 모멘텀이 이어질 수 있습니다.")
    else: positives.append(f"RSI {rsi:.1f}로 극단적인 과열·침체 구간은 아닙니다.")
    if growth > .10: positives.append(f"최근 매출 성장률이 {growth*100:.1f}%로 양호합니다.")
    if debt > 200: cautions.append("부채비율이 높아 금리와 현금흐름 변화에 민감할 수 있습니다.")
    if not positives: positives.append("뚜렷한 강점보다 가격 확인이 우선인 중립 구간입니다.")
    if not cautions: cautions.append("공개 데이터의 시차와 장중 변동성을 함께 고려해야 합니다.")

    score_reasons = {
        "fundamental": [f"ROE {roe*100:.1f}%", f"영업/순이익률 참고 {margin*100:.1f}%", f"매출 성장률 {growth*100:.1f}%"],
        "technical": [f"현재가/MA20 {price:.2f}/{ma20:.2f}", f"MA50/MA200 {ma50:.2f}/{ma200:.2f}", f"RSI {rsi:.1f}, 거래량비 {vol_ratio:.2f}x"],
        "market": ["12개 Market Pulse와 변동성·채권·신용 환경을 합산한 점수"],
        "news": [f"수집된 최신 뉴스 {len(news_items)}건과 단기 가격 반응을 제한적으로 반영"],
    }
    return Analysis(
        ticker=ticker, name=info.get("longName") or info.get("shortName") or ticker,
        currency=info.get("currency", "USD"), price=price, history=history, info=info,
        scores={"overall": overall, "fundamental": fundamental, "technical": technical,
                "market": _clip(market_score), "news": news_score,
                "long": _clip(50 + (12 if price > ma200 else -12) + (8 if ma50 > ma200 else -8)),
                "short": _clip(50 + (12 if price > ma20 else -10) + (8 if ma20 > ma50 else -8)),
                "pullback": _clip(65 + (10 if ma20 > ma50 else -10) - min(abs(price/ma20-1)*300, 25) - max(rsi-68, 0))},
        score_reasons=score_reasons, positives=positives, cautions=cautions,
        metrics={"ma20": ma20, "ma50": ma50, "ma200": ma200, "rsi": rsi, "atr": atr,
                 "volume_ratio": vol_ratio, "high52": high52, "low52": low52},
        supports=supports, resistances=resistances, entry_low=entry_low, entry_high=entry_high,
        invalidation=invalidation, target=target, returns=_returns(close), news=news_items,
    )
