"""User-assumption FCFF model; no network, recommendations or consensus estimates.

Amounts and shares must use the same scale (UI: millions). Exit EV/EBITDA
values operating assets. Current net debt bridges EV to equity; the entire
equity PV is divided by end-horizon diluted shares, ignoring issuance proceeds.
This deliberately simple dilution convention matches the Ideas Lab prototype.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from copy import deepcopy
from datetime import datetime, timezone
import math
from uuid import uuid4

import numpy as np

MODEL_VERSION = "FCFF-EXIT-EBITDA-1"


@dataclass(frozen=True)
class ScenarioInputs:
    revenue: float
    shares: float
    net_debt: float
    price: float
    growth: float = .15
    margin: float = .20
    capex: float = .10
    dilution: float = .01
    multiple: float = 12.
    years: int = 3
    discount: float = .10
    tax: float = .25
    depreciation: float = .05
    working_capital: float = .02

    def validate(self):
        for key, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{key}: 유한한 숫자를 입력하세요.")
        if not isinstance(self.years, int) or not 1 <= self.years <= 10:
            raise ValueError("기간은 1~10년의 정수여야 합니다.")
        if min(self.revenue, self.shares, self.price) <= 0:
            raise ValueError("기준 매출·주식 수·비교 가격은 0보다 커야 합니다.")
        bounds = {"growth": (-.8, 1.), "margin": (-1., 1.), "capex": (0., 1.),
                  "dilution": (0., .5), "multiple": (.1, 60.), "discount": (.01, .5),
                  "tax": (0., .6), "depreciation": (0., 1.), "working_capital": (0., 1.)}
        for key, (low, high) in bounds.items():
            if not low <= getattr(self, key) <= high:
                raise ValueError(f"{key}: 허용 범위 {low}~{high}를 확인하세요.")
        if self.margin + self.depreciation <= 0:
            raise ValueError("말기 EBITDA가 0 이하이면 EV/EBITDA 모형을 사용할 수 없습니다.")


def evaluate(inputs: ScenarioInputs) -> dict:
    inputs.validate()
    rows, revenue, pv = [], inputs.revenue, 0.
    for year in range(1, inputs.years + 1):
        previous = revenue
        revenue *= 1 + inputs.growth
        ebit = revenue * inputs.margin
        taxes = max(ebit, 0.) * inputs.tax  # No invented refund on operating losses.
        depreciation = revenue * inputs.depreciation
        capex = revenue * inputs.capex
        working = (revenue - previous) * inputs.working_capital
        fcff = ebit - taxes + depreciation - capex - working
        discounted = fcff / (1 + inputs.discount) ** year
        pv += discounted
        rows.append(dict(year=year, revenue=revenue, ebit=ebit, taxes=taxes,
                         depreciation=depreciation, capex=capex,
                         working_capital_change=working, fcff=fcff, pv_fcff=discounted))
    terminal = revenue * (inputs.margin + inputs.depreciation) * inputs.multiple
    terminal_pv = terminal / (1 + inputs.discount) ** inputs.years
    enterprise = pv + terminal_pv
    equity = enterprise - inputs.net_debt
    diluted_shares = inputs.shares * (1 + inputs.dilution) ** inputs.years
    value = equity / diluted_shares
    result = dict(value=value, gap_pct=(value / inputs.price - 1) * 100,
                  enterprise=enterprise, equity=equity, diluted_shares=diluted_shares,
                  pv_fcff=pv, terminal=terminal, terminal_pv=terminal_pv, flows=rows)
    if not all(math.isfinite(v) for k, v in result.items() if k != "flows"):
        raise ValueError("입력 규모가 너무 커 계산할 수 없습니다.")
    return result


def implied_growth(inputs: ScenarioInputs, low: float = -.6, high: float = 1.) -> dict:
    """Solve the FCFF polynomial for all real growth roots in a bounded interval.

    Negative interim cash flows can make value non-monotonic. Do not blindly
    bisect endpoints or report one arbitrarily selected 'market expectation'.
    """
    inputs.validate()
    if not (-.8 <= low < high <= 1.):
        raise ValueError("역산 범위를 확인하세요.")
    n, d, w = inputs.years, 1 + inputs.discount, inputs.working_capital
    a = inputs.margin - max(inputs.margin, 0.) * inputs.tax + inputs.depreciation - inputs.capex - w
    coefficients = np.zeros(n + 1)
    for year in range(1, n + 1):
        coefficients[year] += inputs.revenue * a / d ** year
        coefficients[year - 1] += inputs.revenue * w / d ** year
    coefficients[n] += inputs.revenue * (inputs.margin + inputs.depreciation) * inputs.multiple / d ** n
    coefficients[0] -= inputs.net_debt + inputs.price * inputs.shares * (1 + inputs.dilution) ** n
    scale = float(np.max(np.abs(coefficients)))
    if scale == 0:
        return dict(status="indeterminate", roots=[], low=low, high=high)
    roots = []
    for root in np.polynomial.polynomial.polyroots(coefficients / scale):
        growth = float(root.real) - 1
        if abs(root.imag) <= 1e-7 and low - 1e-8 <= growth <= high + 1e-8:
            growth = min(high, max(low, growth))
            actual = evaluate(replace(inputs, growth=growth))["value"]
            if math.isclose(actual, inputs.price, rel_tol=1e-6, abs_tol=1e-7):
                if not any(abs(growth - other) < 1e-7 for other in roots):
                    roots.append(growth)
    roots.sort()
    return dict(status="unique" if len(roots) == 1 else "multiple" if roots else "outside_range",
                roots=roots, low=low, high=high)


def source_defaults(info: dict) -> dict:
    """Missing provider values stay missing. Never silently mix currencies."""
    def number(key, positive=False):
        value = info.get(key)
        if isinstance(value, bool):
            return None
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value if math.isfinite(value) and (not positive or value > 0) else None
    currency, financial = info.get("currency"), info.get("financialCurrency")
    compatible = bool(currency and financial and currency == financial)
    debt, cash = number("totalDebt"), number("totalCash")
    revenue, shares = number("totalRevenue", True), number("sharesOutstanding", True)
    price = number("currentPrice", True) or number("regularMarketPrice", True)
    return dict(revenue=revenue / 1e6 if revenue is not None else None,
                shares=shares / 1e6 if shares is not None else None,
                net_debt=(debt - cash) / 1e6 if debt is not None and cash is not None else None,
                price=price if compatible else None,
                currency=financial or "", quote_currency=currency or "",
                currency_compatible=compatible,
                financial_as_of=info.get("mostRecentQuarter"), quote_as_of=info.get("regularMarketTime"))


def make_snapshot(inputs: ScenarioInputs, symbol: str, currency: str, source: dict, note: str = "") -> dict:
    return dict(id=str(uuid4()), created_at=datetime.now(timezone.utc).isoformat(),
                model_version=MODEL_VERSION, symbol=symbol, currency=currency,
                inputs=asdict(inputs), result=evaluate(inputs), implied=implied_growth(inputs),
                source=deepcopy(source), note=note[:4000])
