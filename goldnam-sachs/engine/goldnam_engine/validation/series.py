"""One-pass technical history; bounded-window structural zones and state transitions."""

from typing import cast

import numpy as np
import pandas as pd

from goldnam_engine.factors.technical_engine import _adx, _rsi
from goldnam_engine.models import MarketRegimeSnapshot, PriceZone, TechnicalSnapshot
from goldnam_engine.risk.current import build_risk_snapshot
from goldnam_engine.timing.current import build_setups
from goldnam_engine.timing.sr_engine import ZoneSet


def scaled(s: pd.Series, low: float, high: float) -> pd.Series:
    return ((s - low) / (high - low) * 100).clip(0, 100)


def technical_series(d: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    c, v = d.Close.astype(float), d.Volume.astype(float)
    e20, e50, e200 = (c.ewm(span=n, adjust=False).mean() for n in (20, 50, 200))
    rsi = _rsi(c)
    adx, atr = _adx(d)
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    histogram = macd - macd.ewm(span=9, adjust=False).mean()
    ret = {n: c.pct_change(n, fill_method=None) * 100 for n in (22, 66, 126, 252)}
    vol_ratio = v / v.rolling(20).mean().clip(lower=1)
    obv = (cast(pd.Series, np.sign(c.diff())).fillna(0) * v).cumsum()
    obv_slope = (obv - obv.shift(19)) / v.rolling(20).sum().clip(lower=1)
    up = v.where(c.diff() > 0, 0).rolling(20).sum()
    down = v.where(c.diff() < 0, 0).rolling(20).sum()
    trend = (
        scaled(c / e200 - 1, -0.15, 0.25) * 0.22
        + scaled(e20 / e50 - 1, -0.08, 0.10) * 0.18
        + scaled(e50 / e200 - 1, -0.12, 0.18) * 0.18
        + scaled(e50.pct_change(20) * 100, -6, 10) * 0.14
        + scaled(e200.pct_change(20) * 100, -4, 7) * 0.08
        + scaled(ret[126], -25, 50) * 0.10
        + scaled(ret[252], -35, 80) * 0.10
    )
    momentum = (
        scaled(rsi, 38, 78) * 0.23
        + scaled(ret[22], -12, 22) * 0.22
        + scaled(ret[66], -20, 40) * 0.25
        + scaled(histogram / c * 100, -1.5, 1.5) * 0.18
        + scaled(adx, 12, 42) * 0.12
    )
    demand = (
        scaled(vol_ratio, 0.55, 2) * 0.30
        + scaled(obv_slope, -0.25, 0.35) * 0.35
        + scaled(up / down.clip(lower=1), 0.6, 1.8) * 0.35
    )
    b = benchmark.Close.reindex(d.index)
    rs = (
        scaled(ret[66] - b.pct_change(66, fill_method=None) * 100, -15, 25) * 0.6
        + scaled(ret[126] - b.pct_change(126, fill_method=None) * 100, -25, 40) * 0.4
    )
    recent = c.rolling(60).max()
    return pd.DataFrame(
        {
            "trend": trend.round(1),
            "momentum": momentum.round(1),
            "demand": demand.round(1),
            "relative_strength": rs.round(1),
            "rsi": rsi.round(1),
            "adx": adx.round(1),
            "atr": atr,
            "atr_pct": (atr / c * 100).round(2),
            "volume_ratio": vol_ratio.round(2),
            "dollar_volume": (c * v).rolling(20).mean(),
            "ret_1m": ret[22].round(2),
            "ret_3m": ret[66].round(2),
            "ret_6m": ret[126].round(2),
            "ret_12m": ret[252].round(2),
            "ema20": e20,
            "ema50": e50,
            "ema200": e200,
            "dist_ema20_atr": ((c - e20) / atr).round(2),
            "dist_ema50_atr": ((c - e50) / atr).round(2),
            "z60": ((c - c.rolling(60).mean()) / c.rolling(60).std().clip(lower=1e-9)).round(2),
            "prior_high20": c.shift().rolling(20).max(),
            "prior_high60": c.shift().rolling(60).max(),
            "recent_high60": recent,
            "drawdown_from_high60": ((c / recent - 1) * 100).round(2),
            "last_day_return": c.pct_change(fill_method=None).mul(100).round(2),
            "last_day_range_pct": ((d.High - d.Low) / c * 100).round(2),
            "obv_slope": obv_slope.round(3),
        }
    )


class StructuralHistory:
    """Same zone inputs as v6, numpy windows instead of rebuilding DataFrames."""

    def __init__(self, frame: pd.DataFrame) -> None:
        self.close, self.high, self.low, self.volume = (
            frame[c].to_numpy(dtype=float) for c in ("Close", "High", "Low", "Volume")
        )
        highs = frame.High
        lows = frame.Low
        ph = highs.eq(highs.rolling(7, center=True).max()).to_numpy()
        pl = lows.eq(lows.rolling(7, center=True).min()).to_numpy()
        self.pivots = [(i, float(self.high[i]), "Swing High") for i in np.flatnonzero(ph)] + [
            (i, float(self.low[i]), "Swing Low") for i in np.flatnonzero(pl)
        ]
        self.pivots.sort(key=lambda p: (p[0], 0 if p[2] == "Swing High" else 1))

    def zones(self, i: int, t: TechnicalSnapshot) -> ZoneSet:
        now = self.close[i]
        tol = max(t.atr * 0.65, now * 0.008)
        candidates = [(p, s, 1.0) for j, p, s in self.pivots if max(3, i - 176) <= j <= i - 3][-24:]
        start = max(0, i - 119)
        lo = float(self.low[start : i + 1].min())
        hi = float(self.high[start : i + 1].max())
        if hi > lo:
            edges = np.linspace(lo, hi, 19)
            centers = (edges[:-1] + edges[1:]) / 2
            indices = np.clip(np.digitize(self.close[start : i + 1], edges) - 1, 0, 17)
            vol = np.bincount(
                indices, weights=np.maximum(self.volume[start : i + 1], 0), minlength=18
            )
            if vol.max() > 0:
                candidates.extend(
                    (float(centers[k]), "Volume Node", 1.15) for k in np.argsort(vol)[-3:]
                )
        candidates.extend(
            [
                (t.ema20, "EMA20", 1.1),
                (t.ema50, "EMA50", 1.2),
                (t.ema200, "EMA200", 1.0),
                (t.prior_high20, "20D Breakout", 1.1),
                (t.prior_high60, "60D Breakout", 1.25),
                (float(self.low[max(0, i - 19) : i + 1].min()), "20D Low", 1.0),
                (float(self.low[max(0, i - 49) : i + 1].min()), "50D Low", 1.0),
                (float(self.high[max(0, i - 251) : i + 1].max()), "52W High", 1.15),
            ]
        )
        clusters: list[list[tuple[float, str, float]]] = []
        for candidate in sorted(candidates, key=lambda item: item[0]):
            if not np.isfinite(candidate[0]) or candidate[0] <= 0:
                continue
            if not clusters or abs(candidate[0] - np.mean([x[0] for x in clusters[-1]])) > tol:
                clusters.append([candidate])
            else:
                clusters[-1].append(candidate)
        supports: list[PriceZone] = []
        resistances: list[PriceZone] = []
        for cluster in clusters:
            sources = tuple(dict.fromkeys(x[1] for x in cluster))
            weights = [x[2] for x in cluster]
            center = float(np.average([x[0] for x in cluster], weights=weights))
            strength = float(
                np.clip(34 + 13 * len(sources) + 8 * sum(w - 1 for w in weights), 0, 100)
            )
            kind = "support" if center <= now else "resistance"
            zone = PriceZone(
                kind,
                round(center - tol * 0.42, 4),
                round(center + tol * 0.42, 4),
                round(center, 4),
                round(strength, 1),
                "Strong" if strength >= 75 else "Medium" if strength >= 55 else "Weak",
                sources,
            )
            (supports if kind == "support" else resistances).append(zone)
        return ZoneSet(
            tuple(sorted(supports, key=lambda z: z.center, reverse=True)[:5]),
            tuple(sorted(resistances, key=lambda z: z.center)[:5]),
        )


def regime_series(benchmark: pd.DataFrame) -> pd.DataFrame:
    close = benchmark.Close
    ma = close.rolling(200).mean()
    score = (
        (
            (close > ma).astype(float)
            + (close.rolling(50).mean() > ma).astype(float)
            + (ma > ma.shift(20)).astype(float)
        )
        * 100
        / 3
    )
    score = score.where(ma.shift(20).notna())
    label = pd.Series(
        np.where(score >= 65, "우호", np.where(score < 40, "비우호", "중립")), index=close.index
    ).where(score.notna(), "미확인")
    return pd.DataFrame({"score": score, "label": label})


def setup_history(frame: pd.DataFrame, benchmark: pd.DataFrame, market: str) -> pd.DataFrame:
    features = technical_series(frame, benchmark)
    regimes = regime_series(benchmark).reindex(frame.index)
    zones = StructuralHistory(frame)
    rows = []
    for i in range(252, len(frame)):
        if features.iloc[i].drop(labels="relative_strength").isna().any() or pd.isna(
            regimes.score.iloc[i]
        ):
            continue
        t = TechnicalSnapshot(**{str(k): float(v) for k, v in features.iloc[i].items()})
        m = MarketRegimeSnapshot(
            market.upper(),
            float(regimes.score.iloc[i]),
            str(regimes.label.iloc[i]),
            {},
            {},
            1.0,
            "가격 PIT",
        )
        risk = build_risk_snapshot(t, m)
        setups = build_setups(float(frame.Close.iloc[i]), t, m, zones.zones(i, t), risk)
        rows.append(
            {
                "date": frame.index[i],
                "regime": m.label,
                **{
                    f"{name}_{key}": getattr(setup, key)
                    for name, setup in (
                        ("pullback", setups.pullback),
                        ("momentum", setups.momentum),
                    )
                    for key in ("status", "stop_loss", "target1")
                },
            }
        )
    result = pd.DataFrame(rows)
    if not result.empty:
        for name, status in (("pullback", "READY"), ("momentum", "CONFIRMED")):
            active = result[f"{name}_status"].eq(status)
            result[f"{name}_signal"] = active & ~active.shift(fill_value=False)
    return result
