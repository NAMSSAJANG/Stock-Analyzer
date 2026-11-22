"""Pre-registered score-v0.1 strategy thresholds. Changes require new validation runs."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Strategy:
    pull_ready: float = 78
    pull_developing: float = 62
    pull_invalid_trend: float = 40
    pull_warning_trend: float = 55
    support_ready_atr: float = 1.25
    support_outside_atr: float = 2.5
    extension_outside_atr: float = 1.5
    momentum_confirmed: float = 80
    momentum_early: float = 68
    momentum_extended: float = 65
    momentum_failed: float = 45
    early_breakout: float = 60
    confirmed_volume: float = 1.1
    stop_buffer_atr: float = 0.55  # protected structure rule
    trail_atr: float = 3
    holding_a: int = 20
    holding_bc: int = 120
    max_positions: int = 8
    sector_positions: int = 2
    sector_weight_pct: float = 30
    heat_pct: float = 6
    regime_favorable: float = 65
    regime_unfavorable: float = 40


STRATEGY = Strategy()
