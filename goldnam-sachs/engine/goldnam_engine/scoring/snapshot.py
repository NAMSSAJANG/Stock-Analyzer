"""Timing/risk alongside ranks; no opportunity-score blending."""

from dataclasses import asdict
from typing import Any

import pandas as pd

from goldnam_engine.data.contracts import DataResult
from goldnam_engine.factors.technical_engine import build_technical_snapshot
from goldnam_engine.regime.current import build_regime
from goldnam_engine.risk.current import build_risk_snapshot
from goldnam_engine.timing.current import build_setups, structural_zones
from goldnam_engine.timing.sr_engine import build_zones


def timing_snapshot(
    frame: pd.DataFrame | None,
    benchmark: pd.DataFrame | None,
    market: str,
    fx: DataResult[float] | None = None,
) -> dict[str, Any]:
    if frame is None or benchmark is None or len(frame) < 252:
        return {"timing": None, "risk": None, "actionable": False}
    tech = build_technical_snapshot(frame, benchmark)
    regime = build_regime(benchmark, market)
    if regime is None:
        return {"timing": None, "risk": None, "actionable": False}
    risk = build_risk_snapshot(tech, regime, None, fx)
    zones = structural_zones(build_zones(frame, tech))
    timing = build_setups(float(frame.Close.iloc[-1]), tech, regime, zones, risk)
    return {
        "timing": asdict(timing),
        "risk": asdict(risk),
        "actionable": timing.pullback.status == "READY" or timing.momentum.status == "CONFIRMED",
        "change_pct": float((frame.Close.iloc[-1] / frame.Close.iloc[-2] - 1) * 100),
        "timing_note": "배치 실적일 미조회 · 종목 분석에서 확인",
    }
