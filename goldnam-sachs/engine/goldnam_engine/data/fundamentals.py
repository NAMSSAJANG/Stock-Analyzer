"""Disclosure-date PIT selection. Current Yahoo info is never accepted here."""

import os
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from threading import Lock
from time import monotonic, sleep
from typing import Any

import requests

from .contracts import DataResult, FundamentalsProvider
from .resilience import ResilientCache

CONCEPTS: dict[str, tuple[str, ...]] = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "Revenue",
    ),
    "gross_profit": ("GrossProfit",),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "operating_income": ("OperatingIncomeLoss", "ProfitLossFromOperatingActivities"),
    "assets": ("Assets",),
    "equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "Equity",
    ),
    "liabilities": ("Liabilities",),
    "operating_cashflow": (
        "NetCashProvidedByUsedInOperatingActivities",
        "CashFlowsFromUsedInOperatingActivities",
    ),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment", "PurchaseOfPropertyPlantAndEquipment"),
    "eps": ("EarningsPerShareDiluted", "DilutedEarningsLossPerShare"),
    "shares": (
        "CommonStockSharesOutstanding",
        "EntityCommonStockSharesOutstanding",
        "NumberOfSharesOutstanding",
    ),
}


@dataclass(frozen=True)
class Fact:
    metric: str
    value: float
    end: date
    filed: date
    start: date | None
    unit: str
    accession: str


def parse_sec_facts(payload: dict[str, Any]) -> list[Fact]:
    result = []
    for taxonomy in payload.get("facts", {}).values():
        for metric, names in CONCEPTS.items():
            for name in names:
                concept = taxonomy.get(name, {})
                for unit, records in concept.get("units", {}).items():
                    if unit not in {"USD", "USD/shares", "shares"}:
                        continue
                    for item in records:
                        try:
                            result.append(
                                Fact(
                                    metric,
                                    float(item["val"]),
                                    date.fromisoformat(item["end"]),
                                    date.fromisoformat(item["filed"]),
                                    date.fromisoformat(item["start"])
                                    if item.get("start")
                                    else None,
                                    unit,
                                    str(item.get("accn", "")),
                                )
                            )
                        except (KeyError, TypeError, ValueError):
                            continue
    return result


def select_pit(facts: list[Fact], as_of: date) -> dict[str, Any]:
    available = [f for f in facts if f.filed <= as_of and f.end <= as_of]
    selected: dict[str, Any] = {}
    provenance: dict[str, Any] = {}
    for metric in CONCEPTS:
        candidates = [f for f in available if f.metric == metric]
        if metric in {"assets", "equity", "liabilities", "shares"}:
            candidates = [f for f in candidates if f.start is None]
        else:
            # Annual amounts give consistent denominators for quality/value.
            candidates = [f for f in candidates if f.start and 330 <= (f.end - f.start).days <= 400]
        if candidates:
            fact = max(candidates, key=lambda f: (f.end, f.filed))
            selected[metric] = fact.value
            provenance[metric] = asdict(fact)
    for metric in ("revenue", "eps"):
        quarters = [
            f
            for f in available
            if f.metric == metric and f.start and 60 <= (f.end - f.start).days <= 120
        ]
        if not quarters:
            continue
        latest = max(quarters, key=lambda f: (f.end, f.filed))
        prior = [f for f in quarters if 330 <= (latest.end - f.end).days <= 400]
        if prior:
            previous = max(prior, key=lambda f: (f.end, f.filed))
            # Negative base EPS cannot produce a meaningful growth ratio.
            if previous.value > 0:
                selected[metric + "_growth"] = latest.value / previous.value - 1
                provenance[metric + "_growth"] = {
                    "current": asdict(latest),
                    "previous": asdict(previous),
                }
    incomes: dict[date, Fact] = {}
    for fact in available:
        if fact.metric == "net_income" and fact.start and 60 <= (fact.end - fact.start).days <= 120:
            if fact.end not in incomes or fact.filed > incomes[fact.end].filed:
                incomes[fact.end] = fact
    selected["quarterly_income"] = [incomes[d].value for d in sorted(incomes)[-8:]]
    selected["provenance"] = provenance
    selected["pit"] = True
    selected["as_of"] = as_of.isoformat()
    return selected


class SecFundamentals(FundamentalsProvider):
    _lock = Lock()
    _last_request = 0.0

    def __init__(self, user_agent: str | None = None) -> None:
        self.user_agent = user_agent if user_agent is not None else os.getenv("SEC_USER_AGENT", "")
        self.cache: ResilientCache[dict[str, Any]] = ResilientCache()
        self._tickers: dict[str, str] = {}

    def _json(self, url: str) -> dict[str, Any]:
        with self._lock:
            delay = 0.15 - (monotonic() - type(self)._last_request)
            if delay > 0:
                sleep(delay)
            response = requests.get(
                url,
                headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"},
                timeout=20,
            )
            type(self)._last_request = monotonic()
        response.raise_for_status()
        return dict(response.json())

    def raw(self, symbol: str) -> DataResult[dict[str, Any]]:
        if "@" not in self.user_agent:
            return DataResult(
                None, "SEC", status="failed", message="SEC_USER_AGENT 미설정 · 연락처 필요"
            )

        def fetch() -> DataResult[dict[str, Any]]:
            if not self._tickers:
                entries = self._json("https://www.sec.gov/files/company_tickers.json")
                self._tickers = {
                    str(v["ticker"]).upper(): str(v["cik_str"]).zfill(10) for v in entries.values()
                }
            cik = self._tickers.get(symbol.upper().replace(".", "-"))
            if cik is None:
                return DataResult(None, "SEC", status="failed", message="CIK 매핑 없음")
            payload = self._json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
            return DataResult(payload, "SEC", as_of=date.today())

        return self.cache.get(symbol, [("SEC", fetch)], timedelta(hours=24))

    def fundamentals(self, symbol: str, as_of: date) -> DataResult[dict[str, Any]]:
        raw = self.raw(symbol)
        if not raw.usable or raw.data is None:
            return raw
        selected = select_pit(parse_sec_facts(raw.data), as_of)
        if not selected["provenance"]:
            return DataResult(
                None, "SEC", as_of=as_of, status="failed", message="해당 날짜에 알려진 재무 없음"
            )
        return DataResult(selected, "SEC", raw.fetched_at, as_of, raw.status)


class DartFundamentals(FundamentalsProvider):
    def __init__(self, api_key: str | None = None) -> None:
        from .dart import DartClient

        self.api_key = api_key if api_key is not None else os.getenv("OPENDART_API_KEY", "")
        self.client = DartClient(self.api_key)

    def fundamentals(self, symbol: str, as_of: date) -> DataResult[dict[str, Any]]:
        if not self.api_key:
            return DataResult(
                None, "OpenDART", as_of=as_of, status="failed", message="OPENDART_API_KEY 미설정"
            )
        return self.client.fundamentals(symbol, as_of)
