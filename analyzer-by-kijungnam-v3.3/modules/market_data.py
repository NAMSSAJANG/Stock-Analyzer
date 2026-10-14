from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import yfinance as yf


MARKET_ASSETS = [
    ("S&P 500", "^GSPC", "index"), ("Nasdaq 100", "^NDX", "index"),
    ("SOX", "^SOX", "index"), ("VIX", "^VIX", "index"),
    ("Gold", "GC=F", "commodity"), ("Silver", "SI=F", "commodity"),
    ("WTI", "CL=F", "commodity"), ("Copper", "HG=F", "commodity"),
    ("USD/KRW", "KRW=X", "fx"), ("DXY", "DX-Y.NYB", "fx"),
    ("Bitcoin", "BTC-USD", "crypto"), ("Ethereum", "ETH-USD", "crypto"),
]


@dataclass
class MarketAsset:
    name: str
    symbol: str
    kind: str
    value: float | None
    change: float | None
    spark: list[float]
    error: str | None = None


def load_market_assets() -> list[MarketAsset]:
    assets = []
    for name, symbol, kind in MARKET_ASSETS:
        try:
            daily = yf.download(symbol, period="5d", interval="1d", auto_adjust=False, progress=False)
            intraday = yf.download(symbol, period="1d", interval="5m", auto_adjust=False, progress=False)
            daily_close = _series(daily, "Close").dropna()
            live = _series(intraday, "Close").dropna()
            if daily_close.empty:
                raise ValueError("가격 없음")
            value = float(live.iloc[-1] if not live.empty else daily_close.iloc[-1])
            previous = float(daily_close.iloc[-2] if len(daily_close) >= 2 else daily_close.iloc[-1])
            spark = ((live / previous - 1) * 100).astype(float).tolist() if not live.empty else [0, (value / previous - 1) * 100]
            assets.append(MarketAsset(name, symbol, kind, value, (value / previous - 1) * 100, spark))
        except Exception as exc:
            assets.append(MarketAsset(name, symbol, kind, None, None, [], str(exc)))
    return assets


def _series(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=float)
    data = frame[column]
    return data.iloc[:, 0] if isinstance(data, pd.DataFrame) else data


def auxiliary_market() -> dict[str, tuple[float | None, float | None]]:
    symbols = {"US 2Y": "^IRX", "US 10Y": "^TNX", "US 30Y": "^TYX", "HYG": "HYG", "LQD": "LQD"}
    result = {}
    for label, symbol in symbols.items():
        try:
            data = yf.download(symbol, period="5d", interval="1d", auto_adjust=False, progress=False)
            close = _series(data, "Close").dropna()
            value = float(close.iloc[-1])
            change = float((value / close.iloc[-2] - 1) * 100) if len(close) > 1 else 0
            result[label] = (value, change)
        except Exception:
            result[label] = (None, None)
    two, ten = result["US 2Y"][0], result["US 10Y"][0]
    result["10Y-2Y"] = ((ten - two) if ten is not None and two is not None else None, None)
    hyg, lqd = result["HYG"][1], result["LQD"][1]
    result["Credit Spread"] = ((lqd - hyg) if hyg is not None and lqd is not None else None, None)
    return result


def market_health(assets: list[MarketAsset], aux: dict) -> tuple[int, int, str, list[str]]:
    by_name = {asset.name: asset for asset in assets}
    def change(name):
        return by_name.get(name).change if by_name.get(name) and by_name[name].change is not None else 0
    score = 50
    contributions = []
    equity = np.mean([change("S&P 500"), change("Nasdaq 100"), change("SOX")])
    vix = change("VIX")
    score += np.clip(equity * 7, -18, 18)
    score += np.clip(-vix * 2, -12, 12)
    score += np.clip(change("Bitcoin") * 1.2, -7, 7)
    score += np.clip((aux.get("HYG", (0, 0))[1] or 0) * 4, -6, 6)
    score = int(round(np.clip(score, 0, 100)))
    coverage = sum(asset.value is not None for asset in assets) / len(assets)
    confidence = int(round(55 + coverage * 35))
    if equity > .25: contributions.append("주요 주가지수가 동반 강세로 위험선호에 기여합니다.")
    elif equity < -.25: contributions.append("주요 주가지수 약세가 시장 체력을 낮추고 있습니다.")
    if vix < -1: contributions.append("VIX 하락은 단기 위험심리 안정 신호입니다.")
    elif vix > 1: contributions.append("VIX 상승으로 변동성 경계가 필요합니다.")
    if change("SOX") > change("S&P 500") + .3: contributions.append("반도체가 시장 대비 강해 성장주 수급이 우호적입니다.")
    if not contributions: contributions.append("지수와 변동성 신호가 혼재해 중립적인 접근이 적절합니다.")
    posture = "Risk On" if score >= 70 else ("Risk Off" if score < 40 else "Balanced")
    brief = f"현재 시장은 {posture} 구간입니다. " + " ".join(contributions[:2])
    return score, confidence, brief, contributions
