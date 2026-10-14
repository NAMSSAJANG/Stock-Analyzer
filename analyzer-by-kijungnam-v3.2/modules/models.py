from dataclasses import dataclass, field
from typing import Any


@dataclass
class Analysis:
    ticker: str
    name: str
    currency: str
    price: float
    history: Any
    info: dict[str, Any]
    scores: dict[str, int]
    score_reasons: dict[str, list[str]]
    positives: list[str]
    cautions: list[str]
    metrics: dict[str, float]
    supports: list[tuple[float, str]]
    resistances: list[tuple[float, str]]
    entry_low: float
    entry_high: float
    invalidation: float
    target: float
    returns: dict[str, float | None]
    news: list[dict[str, Any]] = field(default_factory=list)

