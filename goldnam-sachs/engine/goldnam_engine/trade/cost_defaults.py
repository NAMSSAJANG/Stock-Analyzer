"""2026-11-23 cost scenario; current tax is not a claim about historical tax rates."""

from goldnam_engine.trade.trade_core import Costs


def default_costs(market: str) -> Costs:
    # KOSPI .05% transaction + .15% rural tax; KOSDAQ .20% transaction.
    # Commissions and slippage are editable research assumptions, not broker quotes.
    return Costs(
        buy_fee=0.00015 if market == "kr" else 0.001,
        sell_fee=0.00015 if market == "kr" else 0.001,
        sell_tax=0.002 if market == "kr" else 0.0,
        slippage=0.0005,
    )
