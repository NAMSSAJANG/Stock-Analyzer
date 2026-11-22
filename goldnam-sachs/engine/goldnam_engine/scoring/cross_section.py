"""Cross-sectional percentile scores with explicit coverage and peer provenance."""

from dataclasses import asdict, dataclass, field
from datetime import date
from math import ceil
from typing import Any

import numpy as np
import pandas as pd

from goldnam_engine.factors.cross_section import FACTOR_COLUMNS


@dataclass(frozen=True)
class Score:
    value: int | None
    percentile: int | None
    coverage: float
    as_of: str
    sources: list[dict[str, Any]]
    evidence: str = "미검증"
    raw_value: float | None = None
    badges: list[str] = field(default_factory=list)


def percentile(value: float, peers: pd.Series) -> float | None:
    clean = pd.to_numeric(peers, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 2 or not np.isfinite(value):
        return None
    low, high = clean.quantile([0.01, 0.99])
    clean = clean.clip(low, high)
    value = float(np.clip(value, low, high))
    less, equal = int((clean < value).sum()), int((clean == value).sum())
    # Matches average rank / N for members; ECDF for an out-of-universe observation.
    return 100.0 * (less + (equal + 1) / 2 if equal else less) / len(clean)


def rank_snapshot(
    reference: pd.DataFrame,
    as_of: date,
    sources: list[dict[str, Any]],
    targets: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Reference contains one market/date only; targets are never added to its ranks."""
    if "market" in reference and reference.market.nunique() > 1:
        raise ValueError("시장별로 따로 순위를 계산해야 합니다")
    selected = reference if targets is None else targets
    if selected.index.has_duplicates or reference.index.has_duplicates:
        raise ValueError("중복 종목")
    rows = []
    for symbol, row in selected.iterrows():
        factors: dict[str, Any] = {}
        indicator_details: dict[str, Any] = {}
        for name, columns in FACTOR_COLUMNS.items():
            values = []
            for column in columns:
                scope = "market"
                peers = reference
                if name in {"quality", "value", "growth"}:
                    for category in ("industry", "sector"):
                        label = row.get(category)
                        if pd.notna(label) and category in reference:
                            group = reference[reference[category] == label]
                            if column in group and group[column].notna().sum() >= 10:
                                peers, scope = group, category
                                break
                raw = row.get(column)
                rank = (
                    percentile(float(raw), peers[column])
                    if pd.notna(raw) and column in peers
                    else None
                )
                indicator_details[column] = {
                    "value": float(raw) if pd.notna(raw) else None,
                    "percentile": round(rank) if rank is not None else None,
                    "scope": scope,
                    "peer_count": int(peers[column].notna().sum()) if column in peers else 0,
                }
                if rank is not None:
                    values.append(rank)
            coverage = len(values) / len(columns)
            raw_score = float(np.mean(values)) if len(values) >= ceil(len(columns) / 2) else None
            shown = round(raw_score) if raw_score is not None else None
            factors[name] = asdict(
                Score(shown, shown, coverage, as_of.isoformat(), sources, raw_value=raw_score)
            )
        available = [f["raw_value"] for f in factors.values() if f["raw_value"] is not None]
        badges = []
        if any(factors[k]["value"] is None for k in ("quality", "value", "growth")):
            badges.append("가격 기반 부분 점수 · 재무 일부 또는 전체 제외")
        if symbol not in reference.index:
            badges.append("유니버스 밖")
        composite = float(np.mean(available)) if len(available) >= 3 else None
        shown = round(composite) if composite is not None else None
        score = Score(
            shown,
            shown,
            len(available) / 5,
            as_of.isoformat(),
            sources,
            raw_value=composite,
            badges=badges,
        )
        rows.append(
            {
                "symbol": str(symbol),
                "name": row.get("name", str(symbol)),
                "market": row.get("market"),
                "sector": row.get("sector"),
                "score": asdict(score),
                "factors": factors,
                "indicators": indicator_details,
                "grade": grade(shown),
            }
        )
    return rows


def grade(value: int | None) -> str:
    if value is None:
        return "산출 불가"
    return (
        "상위 10%"
        if value >= 90
        else "상위 30%"
        if value >= 70
        else "하위 10%"
        if value <= 10
        else "하위 30%"
        if value <= 30
        else "중간"
    )
