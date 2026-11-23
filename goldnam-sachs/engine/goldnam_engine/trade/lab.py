"""Seeded research simulation, not an estimated probability of future profits."""

from typing import Any

import numpy as np


def loss_simulation(
    win_fraction: float, payoff_ratio: float, risk_fraction: float, seed: int = 20261123
) -> dict[str, Any]:
    if (
        not np.isfinite([win_fraction, payoff_ratio, risk_fraction]).all()
        or not 0 <= win_fraction <= 1
        or payoff_ratio < 0
        or not 0 <= risk_fraction < 1
    ):
        raise ValueError("승률/손익비/위험 비율 오류")
    rng = np.random.default_rng(seed)
    wins = rng.random((10000, 100)) < win_fraction
    changes = np.where(wins, payoff_ratio, -1) * risk_fraction
    equity = np.concatenate([np.ones((10000, 1)), np.cumprod(1 + changes, axis=1)], axis=1)
    drawdown = (equity / np.maximum.accumulate(equity, axis=1) - 1).min(axis=1)
    streak = np.zeros(10000, dtype=int)
    maximum = streak.copy()
    for column in wins.T:
        streak = np.where(column, 0, streak + 1)
        maximum = np.maximum(maximum, streak)

    def distribution(values: np.ndarray) -> dict[str, float]:
        return {str(q): float(np.quantile(values, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)}

    return {
        "expected_r": win_fraction * payoff_ratio - (1 - win_fraction),
        "break_even_win_fraction": 1 / (1 + payoff_ratio),
        "seed": seed,
        "simulations": 10000,
        "trades": 100,
        "loss_streak": distribution(maximum),
        "max_drawdown": distribution(drawdown),
        "final_equity_multiple": distribution(equity[:, -1]),
        "note": "입력 승률·손익비가 고정되고 거래가 독립이라는 가정 · 실제 성과 예측이 아님",
    }
