"""Four independent views; correlated price metrics do not earn extra votes."""

from typing import Any

from goldnam_engine.models import MarketRegimeSnapshot, SetupSnapshot
from goldnam_engine.timing.current import actionable


def consensus(
    factors: dict[str, dict[str, Any]],
    setups: SetupSnapshot | None,
    regime: MarketRegimeSnapshot | None,
    option_bias: float | None = None,
    market: str = "us",
) -> dict[str, Any]:
    def average(names: tuple[str, ...]) -> float | None:
        values = [
            factors[n]["value"]
            for n in names
            if n in factors and factors[n].get("value") is not None
        ]
        return sum(values) / len(values) if values else None

    price = average(("momentum", "trend"))
    fundamental = average(("quality", "value", "growth"))
    price_actionable = setups is not None and (
        actionable(setups.pullback) or actionable(setups.momentum)
    )
    lenses = {
        "price": {
            "value": price,
            "supportive": price is not None and price >= 70 and price_actionable,
        },
        "fundamentals": {
            "value": fundamental,
            "supportive": fundamental is not None and fundamental >= 70,
        },
        "regime": {
            "value": regime.score if regime else None,
            "supportive": regime is not None and regime.label == "우호",
        },
        "options": {
            "value": option_bias if market == "us" else None,
            "supportive": market == "us" and option_bias is not None and option_bias >= 70,
        },
    }
    return {
        "lenses": lenses,
        "available": sum(v["value"] is not None for v in lenses.values()),
        "supportive": sum(bool(v["supportive"]) for v in lenses.values()),
        "interpretation": "독립 렌즈의 조건 일치 수 · 상승 확률이 아님",
    }
