"""score-v0.1 features. Price features are vectorized across dates and securities."""

from typing import Any

import numpy as np
import pandas as pd

FACTOR_COLUMNS = {
    "momentum": ("momentum_12_1", "momentum_6_1"),
    "trend": ("price_ma200", "ma50_ma200", "slope_ma200", "distance_high252"),
    "quality": ("roe", "gross_assets", "operating_margin", "inverse_leverage", "income_stability"),
    "value": ("earnings_yield", "fcf_yield", "book_yield"),
    "growth": ("revenue_growth", "eps_growth"),
}


def price_features(close: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Never forward-fill prices: missing bars leave affected windows unavailable."""
    close = close.where(close > 0)
    ma50, ma200 = close.rolling(50).mean(), close.rolling(200).mean()
    return {
        "momentum_12_1": close.shift(21) / close.shift(252) - 1,
        "momentum_6_1": close.shift(21) / close.shift(126) - 1,
        "price_ma200": close / ma200 - 1,
        "ma50_ma200": ma50 / ma200 - 1,
        "slope_ma200": ma200 / ma200.shift(20) - 1,
        "distance_high252": close / close.rolling(252).max() - 1,
    }


def financial_features(
    facts: dict[str, Any] | None, market_cap: float | None
) -> dict[str, float | None]:
    result: dict[str, float | None] = {
        col: None for name in ("quality", "value", "growth") for col in FACTOR_COLUMNS[name]
    }
    if not facts:
        return result

    def number(name: str) -> float | None:
        value = facts.get(name)
        if value is None:
            return None
        try:
            value = float(value)
            return value if np.isfinite(value) else None
        except (TypeError, ValueError):
            return None

    def ratio(numerator: str, denominator: str, positive: bool = False) -> float | None:
        n, d = number(numerator), number(denominator)
        if n is None or d is None or d <= 0 or (positive and n <= 0):
            return None
        return n / d

    result.update(
        roe=ratio("net_income", "equity"),
        gross_assets=ratio("gross_profit", "assets"),
        operating_margin=ratio("operating_income", "revenue"),
    )
    leverage = ratio("liabilities", "equity")
    result["inverse_leverage"] = -leverage if leverage is not None else None
    income = np.asarray(facts.get("quarterly_income", []), dtype=float)
    income = income[np.isfinite(income)]
    if len(income) >= 4 and abs(float(income.mean())) > 0:
        result["income_stability"] = -float(income.std(ddof=1) / abs(income.mean()))
    if market_cap is not None and np.isfinite(market_cap) and market_cap > 0:
        for target, source in (("earnings_yield", "net_income"), ("book_yield", "equity")):
            value = number(source)
            if value is not None and value > 0:
                result[target] = value / market_cap
        operating, capex = number("operating_cashflow"), number("capex")
        if operating is not None and capex is not None and operating - abs(capex) > 0:
            result["fcf_yield"] = (operating - abs(capex)) / market_cap
    for name in FACTOR_COLUMNS["growth"]:
        result[name] = number(name)
    return result
