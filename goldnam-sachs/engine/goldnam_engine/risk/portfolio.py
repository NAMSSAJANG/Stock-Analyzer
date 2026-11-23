from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from goldnam_engine.strategy import STRATEGY, Strategy
from goldnam_engine.trade.trade_core import Costs, dec, position_size


@dataclass(frozen=True)
class Holding:
    symbol: str
    sector: str
    quantity: int
    price: float
    stop: float


def size_portfolio(
    account: float,
    cash: float,
    entry: float,
    stop: float,
    target: float,
    sector: str,
    holdings: list[Holding],
    risk_pct: float = 1.0,
    max_position_pct: float = 20.0,
    multiplier: float = 1.0,
    costs: Costs | None = None,
    config: Strategy = STRATEGY,
    gap_pct: float = 0,
) -> dict[str, Any]:
    costs = costs or Costs()
    for h in holdings:
        if h.quantity < 0 or h.quantity != int(h.quantity) or not 0 < h.stop <= h.price:
            raise ValueError("보유 수량·현재가·손절가 확인 필요")
    base = position_size(
        account, cash, entry, stop, target, risk_pct, max_position_pct, costs, multiplier, gap_pct
    )
    heat = sum(
        (
            max(Decimal(0), costs.buy_unit(h.price) - costs.sell_unit(h.stop)) * h.quantity
            for h in holdings
        ),
        Decimal(0),
    )
    same = [h for h in holdings if h.sector == sector and h.quantity > 0]
    exposure = sum((costs.buy_unit(h.price) * h.quantity for h in same), Decimal(0))
    unit_risk = costs.buy_unit(entry) - costs.sell_unit(dec(stop) * (1 - dec(gap_pct) / 100))
    cap_heat = max(Decimal(0), dec(account) * dec(config.heat_pct) / 100 - heat)
    cap_sector = max(Decimal(0), dec(account) * dec(config.sector_weight_pct) / 100 - exposure)
    caps = {
        "기존 단일 종목 한도": int(base["수량"]),
        "포트폴리오 히트": int(cap_heat // unit_risk),
        "업종 비중": int(cap_sector // costs.buy_unit(entry)),
    }
    if len([h for h in holdings if h.quantity > 0]) >= config.max_positions:
        caps["최대 보유 종목"] = 0
    if len(same) >= config.sector_positions:
        caps["업종 종목 수"] = 0
    quantity = min(caps.values())
    return {
        **base,
        "수량": quantity,
        "제한 요인": " · ".join(k for k, v in caps.items() if v == quantity),
        "매수 투입액": float(costs.buy_unit(entry) * quantity),
        "남은 현금": float(dec(cash) - costs.buy_unit(entry) * quantity),
        "손절 예상손실": float(unit_risk * quantity),
        "목표 예상순이익": float((costs.sell_unit(target) - costs.buy_unit(entry)) * quantity),
        "계좌 손실률(%)": float(unit_risk * quantity / dec(account) * 100),
        "투입 비중(%)": float(costs.buy_unit(entry) * quantity / dec(account) * 100),
        "portfolio_heat_pct": float(heat / dec(account) * 100),
        "projected_heat_pct": float((heat + unit_risk * quantity) / dec(account) * 100),
        "caps": caps,
        "warnings": [k for k, v in caps.items() if v == quantity and k != "기존 단일 종목 한도"],
        "gap_loss_1_5r": float(unit_risk * quantity * Decimal("1.5")),
    }
