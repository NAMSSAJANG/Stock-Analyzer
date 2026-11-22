"""Public contracts drive both OpenAPI and generated TypeScript types."""

from datetime import date
from typing import Any, Generic, Literal, TypeVar

from goldnam_engine.models import MarketRegimeSnapshot, SetupSnapshot, TechnicalSnapshot
from goldnam_engine.risk.current import RiskState
from goldnam_engine.timing.sr_engine import ZoneSet
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Source(BaseModel):
    name: str
    fetched_at: str | None = None
    as_of: str | None = None
    status: Literal["ok", "partial", "stale", "failed"] = "ok"
    message: str = ""


class Meta(BaseModel):
    as_of: str | None = None
    app_version: str = "0.0.0-a.1"
    score_version: str = "score-v0.1"
    coverage: float = 0
    sources: list[Source] = Field(default_factory=list)


class Envelope(BaseModel, Generic[T]):
    data: T
    meta: Meta = Field(default_factory=Meta)
    warnings: list[str] = Field(default_factory=list)


class ScoreModel(BaseModel):
    value: int | None = None
    percentile: int | None = None
    coverage: float = 0
    as_of: str
    sources: list[Source] = Field(default_factory=list)
    evidence: str = "미검증"
    raw_value: float | None = None
    badges: list[str] = Field(default_factory=list)


class ScoreRow(BaseModel):
    symbol: str
    name: str | None = None
    market: str | None = None
    sector: str | None = None
    score: ScoreModel
    factors: dict[str, ScoreModel] = Field(default_factory=dict)
    indicators: dict[str, Any] = Field(default_factory=dict)
    grade: str = "산출 불가"


class Analysis(ScoreRow):
    last_price: float | None = None
    change_pct: float | None = None
    timing: SetupSnapshot | None = None
    risk: RiskState | None = None
    zones: ZoneSet | None = None
    technical: TechnicalSnapshot | None = None
    regime: MarketRegimeSnapshot | None = None
    fundamentals: dict[str, Any] | None = None
    consensus: dict[str, Any] | None = None
    evidence_detail: dict[str, Any] | None = None
    options: dict[str, Any] | None = None
    can_slim: dict[str, Any] | None = None


class PriceBar(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class PriceData(BaseModel):
    symbol: str
    bars: list[PriceBar]


class SearchHit(BaseModel):
    symbol: str
    name: str
    market: str


class Screener(BaseModel):
    items: list[ScoreRow]
    total: int
    page: int
    pages: int


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Login(StrictModel):
    passcode: str = Field(min_length=1, max_length=1024, repr=False)


class WatchItem(StrictModel):
    symbol: str = Field(pattern=r"^[A-Za-z0-9^][A-Za-z0-9.^=\-]{0,19}$")


class JournalInput(WatchItem):
    date: date
    side: Literal["buy", "sell"]
    quantity: int = Field(gt=0, le=1_000_000_000)
    price: float = Field(gt=0, le=1_000_000_000)
    notes: str = Field(default="", max_length=4000)


class JournalRecord(JournalInput):
    id: str
    snapshot: dict[str, Any] = Field(default_factory=dict)
    score_version: str


class CostInput(StrictModel):
    buy_fee: float = Field(default=0.001, ge=0, lt=0.5)
    sell_fee: float = Field(default=0.001, ge=0, lt=0.5)
    sell_tax: float = Field(default=0, ge=0, lt=0.5)
    slippage: float = Field(default=0.0005, ge=0, lt=0.5)


class Settings(StrictModel):
    theme: Literal["personal", "goldnam"] = "personal"
    colors: Literal["kr", "international"] = "kr"
    currency: Literal["KRW", "USD"] = "KRW"
    account: float = Field(default=10_000_000, gt=0, le=1e15)
    risk_pct: float = Field(default=1, ge=0, le=6)
    max_position_pct: float = Field(default=20, ge=0, le=100)
    costs: CostInput = Field(default_factory=CostInput)
    exit_mode: Literal["A", "B", "C"] | None = None
    saved_filters: list[dict[str, str]] = Field(default_factory=list, max_length=20)


class PlanInput(StrictModel):
    kind: Literal["position", "ladder", "target_average"] = "position"
    account: float = Field(default=100000, gt=0)
    cash: float = Field(default=100000, ge=0)
    entry: float = Field(default=100, gt=0)
    stop: float = Field(default=95, gt=0)
    target: float = Field(default=110, gt=0)
    risk_pct: float = Field(default=1, ge=0, le=6)
    max_position_pct: float = Field(default=20, ge=0, le=100)
    multiplier: float = Field(default=1, ge=0, le=1)
    gap_pct: float = Field(default=0, ge=0, lt=100)
    prices: list[float] = Field(default_factory=list, max_length=100)
    weights: list[float] = Field(default_factory=list, max_length=100)
    reserve_pct: float = Field(default=0, ge=0, le=100)
    shares: int = Field(default=0, ge=0)
    average: float = Field(default=100, ge=0)
    costs: CostInput = Field(default_factory=CostInput)
    sector: str = "미확인"
    holdings: list[dict[str, Any]] = Field(default_factory=list, max_length=100)


class SimulationInput(StrictModel):
    kind: Literal["path", "loss_streak"] = "path"
    shares: int = Field(default=0, ge=0)
    average: float = Field(default=100, ge=0)
    cash: float = Field(default=10000, ge=0)
    path: list[float] = Field(default_factory=list, max_length=2000)
    rules: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    costs: CostInput = Field(default_factory=CostInput)
    win_fraction: float = Field(default=0.5, ge=0, le=1)
    payoff_ratio: float = Field(default=2, ge=0, le=100)
    risk_fraction: float = Field(default=0.01, ge=0, lt=1)
    seed: int = Field(default=20261123, ge=0, le=2**32 - 1)


class ExecutionInput(WatchItem):
    mode: Literal["A", "B", "C"] = "A"
    start: date = date(2020, 1, 1)
    setup: Literal["pullback", "momentum"] = "pullback"
    costs: CostInput = Field(default_factory=CostInput)


class Backup(StrictModel):
    schema_version: Literal[1] = 1
    watchlist: list[WatchItem] = Field(default_factory=list, max_length=1000)
    journal: list[JournalRecord] = Field(default_factory=list, max_length=10000)
    settings: Settings = Field(default_factory=Settings)
