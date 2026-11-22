from __future__ import annotations

from typing import Any, Mapping, Sequence, cast

from goldnam_engine.models import CompanySnapshot
from goldnam_engine.scoring.scoring_utils import finite, percentile_score, scale, weighted


def _pct(info: Mapping[str, Any], key: str) -> float | None:
    value = info.get(key)
    if not finite(value):
        return None
    return float(cast(float, value)) * 100


def _num(info: Mapping[str, Any], key: str) -> float | None:
    value = info.get(key)
    return float(cast(float, value)) if finite(value) else None


def _positive_multiple(value: float | None) -> float | None:
    """PER/PBR류 valuation multiple 전용 가드. 적자기업의 음수 PER(예: -20)이나
    자본잠식으로 인한 음수 PBR은 '매우 저평가'가 아니라 '이 지표로 평가 불가' 상태이므로,
    reverse-scale에 흘려보내면 안 됩니다(음수일수록 score가 100에 가까워지는 착시가 생김)."""
    return value if value is not None and value > 0 else None


def extract_company_raw(info: Mapping[str, Any]) -> dict[str, float | None]:
    revenue = _num(info, "totalRevenue")
    free_cash_flow = _num(info, "freeCashflow")
    fcf_margin = None if not revenue or not free_cash_flow else free_cash_flow / revenue * 100
    return {
        "revenue_growth": _pct(info, "revenueGrowth"),
        "earnings_growth": _pct(info, "earningsGrowth"),
        "operating_margin": _pct(info, "operatingMargins"),
        "profit_margin": _pct(info, "profitMargins"),
        "roe": _pct(info, "returnOnEquity"),
        "debt_to_equity": _num(info, "debtToEquity"),
        "current_ratio": _num(info, "currentRatio"),
        "trailing_pe": _num(info, "trailingPE"),
        "forward_pe": _num(info, "forwardPE"),
        "price_to_book": _num(info, "priceToBook"),
        "fcf_margin": fcf_margin,
    }


def _absolute_scores(raw: Mapping[str, float | None]) -> dict[str, float | None]:
    return {
        "Growth": weighted(
            [
                (
                    scale(raw.get("revenue_growth"), -5, 30)
                    if finite(raw.get("revenue_growth"))
                    else None,
                    0.50,
                ),
                (
                    scale(raw.get("earnings_growth"), -10, 35)
                    if finite(raw.get("earnings_growth"))
                    else None,
                    0.50,
                ),
            ]
        )
        if any(finite(raw.get(k)) for k in ("revenue_growth", "earnings_growth"))
        else None,
        "Profitability": weighted(
            [
                (
                    scale(raw.get("operating_margin"), 0, 30)
                    if finite(raw.get("operating_margin"))
                    else None,
                    0.35,
                ),
                (
                    scale(raw.get("profit_margin"), 0, 25)
                    if finite(raw.get("profit_margin"))
                    else None,
                    0.25,
                ),
                (scale(raw.get("roe"), 0, 30) if finite(raw.get("roe")) else None, 0.40),
            ]
        )
        if any(finite(raw.get(k)) for k in ("operating_margin", "profit_margin", "roe"))
        else None,
        "Balance Sheet": weighted(
            [
                (
                    scale(raw.get("debt_to_equity"), 0, 220, reverse=True)
                    if finite(raw.get("debt_to_equity"))
                    else None,
                    0.65,
                ),
                (
                    scale(raw.get("current_ratio"), 0.6, 2.2)
                    if finite(raw.get("current_ratio"))
                    else None,
                    0.35,
                ),
            ]
        )
        if any(finite(raw.get(k)) for k in ("debt_to_equity", "current_ratio"))
        else None,
        "Cash Flow": scale(raw.get("fcf_margin"), -5, 22)
        if finite(raw.get("fcf_margin"))
        else None,
        "Valuation": weighted(
            [
                (
                    scale(_positive_multiple(raw.get("forward_pe")), 8, 45, reverse=True)
                    if _positive_multiple(raw.get("forward_pe"))
                    else None,
                    0.45,
                ),
                (
                    scale(_positive_multiple(raw.get("trailing_pe")), 8, 50, reverse=True)
                    if _positive_multiple(raw.get("trailing_pe"))
                    else None,
                    0.35,
                ),
                (
                    scale(_positive_multiple(raw.get("price_to_book")), 1, 12, reverse=True)
                    if _positive_multiple(raw.get("price_to_book"))
                    else None,
                    0.20,
                ),
            ]
        )
        if any(
            _positive_multiple(raw.get(k)) for k in ("forward_pe", "trailing_pe", "price_to_book")
        )
        else None,
    }


def _peer_relative(
    raw: Mapping[str, float | None], peer_raw: Sequence[Mapping[str, float | None]]
) -> dict[str, float | None]:
    higher_better = {
        "revenue_growth": "Revenue Growth",
        "earnings_growth": "Earnings Growth",
        "operating_margin": "Operating Margin",
        "profit_margin": "Profit Margin",
        "roe": "ROE",
        "fcf_margin": "FCF Margin",
        "current_ratio": "Current Ratio",
    }
    lower_better = {
        "debt_to_equity": "Debt / Equity",
        "forward_pe": "Forward PE",
        "trailing_pe": "Trailing PE",
        "price_to_book": "Price / Book",
    }
    valuation_keys = {"forward_pe", "trailing_pe", "price_to_book"}
    out: dict[str, float | None] = {}
    for key, label in higher_better.items():
        vals = [x.get(key) for x in peer_raw if finite(x.get(key))]
        out[label] = percentile_score(raw.get(key), vals)
    for key, label in lower_better.items():
        is_valuation = key in valuation_keys
        target = _positive_multiple(raw.get(key)) if is_valuation else raw.get(key)
        vals = [(_positive_multiple(x.get(key)) if is_valuation else x.get(key)) for x in peer_raw]
        vals = [v for v in vals if finite(v)]
        pct = percentile_score(target, vals)
        out[label] = None if pct is None else 100 - pct
    return out


def build_company_snapshot(
    info: Mapping[str, Any], peer_infos: Sequence[Mapping[str, Any]] | None = None
) -> CompanySnapshot:
    raw = extract_company_raw(info)
    absolute = _absolute_scores(raw)
    peer_raw = [extract_company_raw(x) for x in (peer_infos or [])]
    relative = _peer_relative(raw, peer_raw) if peer_raw else {}

    def rel_weight(parts: list[tuple[float | None, float]]) -> float | None:
        return weighted(parts) if any(finite(v) for v, _ in parts) else None

    rel_groups = {
        "Growth": rel_weight(
            [(relative.get("Revenue Growth"), 0.5), (relative.get("Earnings Growth"), 0.5)]
        )
        if relative
        else None,
        "Profitability": rel_weight(
            [
                (relative.get("Operating Margin"), 0.35),
                (relative.get("Profit Margin"), 0.25),
                (relative.get("ROE"), 0.4),
            ]
        )
        if relative
        else None,
        "Balance Sheet": rel_weight(
            [(relative.get("Debt / Equity"), 0.65), (relative.get("Current Ratio"), 0.35)]
        )
        if relative
        else None,
        "Cash Flow": relative.get("FCF Margin") if relative else None,
        "Valuation": rel_weight(
            [
                (relative.get("Forward PE"), 0.45),
                (relative.get("Trailing PE"), 0.35),
                (relative.get("Price / Book"), 0.2),
            ]
        )
        if relative
        else None,
    }
    factors: dict[str, float | None] = {}
    for name in absolute:
        abs_score = absolute[name]
        rel_score = rel_groups.get(name)
        if finite(abs_score) and finite(rel_score):
            factors[name] = weighted([(abs_score, 0.55), (rel_score, 0.45)])
        elif finite(abs_score):
            factors[name] = float(cast(float, abs_score))
        elif finite(rel_score):
            factors[name] = float(cast(float, rel_score))
        else:
            factors[name] = None

    factor_weights = {
        "Growth": 0.30,
        "Profitability": 0.30,
        "Balance Sheet": 0.15,
        "Cash Flow": 0.10,
        "Valuation": 0.15,
    }
    valid = [(factors[k], w) for k, w in factor_weights.items() if finite(factors[k])]
    score = weighted(valid) if valid else None

    raw_fields = list(raw.values())
    raw_coverage = sum(finite(v) for v in raw_fields) / max(len(raw_fields), 1)
    relative_available = [v for v in relative.values() if finite(v)]
    relative_coverage = len(relative_available) / max(len(relative), 1) if relative else 0.0
    coverage = min(1.0, 0.80 * raw_coverage + 0.20 * relative_coverage)
    confidence = "High" if coverage >= 0.78 else "Medium" if coverage >= 0.55 else "Low"

    notes = []
    if raw_coverage < 0.65:
        notes.append(
            "공개 재무 데이터 일부가 제공되지 않아 해당 항목은 점수 계산에서 제외했습니다."
        )
    if peer_infos and relative_coverage >= 0.35:
        notes.append("동일/유사 업종 후보군의 상대 순위를 절대평가와 함께 반영했습니다.")
    elif not peer_infos:
        notes.append("업종 상대평가 자료가 없어 절대평가 중심으로 계산했습니다.")
    return CompanySnapshot(
        None if score is None else round(float(score), 1),
        round(coverage, 3),
        confidence,
        {k: None if v is None or not finite(v) else round(float(v), 1) for k, v in factors.items()},
        raw,
        {
            k: None if v is None or not finite(v) else round(float(v), 1)
            for k, v in relative.items()
        },
        tuple(notes),
    )
