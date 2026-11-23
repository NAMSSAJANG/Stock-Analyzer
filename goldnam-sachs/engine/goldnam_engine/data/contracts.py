"""Provider contracts; missing data never masquerades as a successful value."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Generic, Literal, TypeVar

import pandas as pd

T = TypeVar("T")
Status = Literal["ok", "partial", "stale", "failed"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DataResult(Generic[T]):
    data: T | None
    source: str
    fetched_at: datetime = field(default_factory=utcnow)
    as_of: date | None = None
    status: Status = "ok"
    message: str = ""

    @property
    def usable(self) -> bool:
        return self.data is not None and self.status != "failed"


class PriceProvider(ABC):
    @abstractmethod
    def prices(self, symbol: str, start: date, end: date) -> DataResult[pd.DataFrame]: ...


class FundamentalsProvider(ABC):
    @abstractmethod
    def fundamentals(self, symbol: str, as_of: date) -> DataResult[dict[str, Any]]: ...


class CalendarProvider(ABC):
    @abstractmethod
    def earnings(self, symbol: str) -> DataResult[date]: ...


class FxProvider(ABC):
    @abstractmethod
    def usd_krw(self) -> DataResult[float]: ...


class UniverseProvider(ABC):
    @abstractmethod
    def constituents(self, market: str, as_of: date) -> DataResult[pd.DataFrame]: ...
