"""Current membership snapshots, with explicit survivorship-bias disclosure."""

from datetime import date
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from .contracts import DataResult, UniverseProvider
from .transport import bound_provider

BIAS = "현재 지수 구성으로 과거 검증 · 상장폐지/편출 종목 누락에 따른 생존 편향"


class Universes(UniverseProvider):
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _fetch(self, market: str) -> pd.DataFrame:
        if market == "us":
            tables = []
            for url in (
                "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                "https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies",
            ):
                response = requests.get(
                    url, headers={"User-Agent": "GoldnamSachs/0.1 (personal research)"}, timeout=20
                )
                response.raise_for_status()
                candidates = pd.read_html(StringIO(response.text), flavor="lxml")
                selected = next(
                    t
                    for t in candidates
                    if {"Symbol", "Security"}.issubset(t.columns)
                    or {"Ticker", "Company"}.issubset(t.columns)
                )
                selected = selected.rename(
                    columns={
                        "Symbol": "symbol",
                        "Ticker": "symbol",
                        "Security": "name",
                        "Company": "name",
                        "GICS Sector": "sector",
                        "GICS Sub-Industry": "industry",
                    }
                )
                tables.append(
                    selected[[c for c in ["symbol", "name", "sector", "industry"] if c in selected]]
                )
            out = pd.concat(tables, ignore_index=True).drop_duplicates("symbol")
            out["symbol"] = out.symbol.str.replace(".", "-", regex=False)
            return out
        if market == "kr":
            from pykrx import stock

            bound_provider("pykrx")

            rows = []
            for market_name, index_name, suffix in (
                ("KOSPI", "코스피 200", ".KS"),
                ("KOSDAQ", "코스닥 150", ".KQ"),
            ):
                index_ids = stock.get_index_ticker_list(market=market_name)
                index_id = next(
                    i
                    for i in index_ids
                    if stock.get_index_ticker_name(i).replace(" ", "")
                    == index_name.replace(" ", "")
                )
                for code in stock.get_index_portfolio_deposit_file(index_id):
                    rows.append(
                        {
                            "symbol": code + suffix,
                            "name": stock.get_market_ticker_name(code),
                            "sector": None,
                            "industry": None,
                        }
                    )
            return pd.DataFrame(rows).drop_duplicates("symbol")
        raise ValueError("시장 오류")

    def constituents(self, market: str, as_of: date) -> DataResult[pd.DataFrame]:
        if market not in {"us", "kr"}:
            raise ValueError("시장은 us 또는 kr이어야 합니다.")
        self.directory.mkdir(parents=True, exist_ok=True)
        today = date.today()
        stored = sorted(self.directory.glob(f"{market}-*.parquet"))
        if as_of == today and stored and stored[-1].stem.endswith(today.isoformat()):
            return DataResult(
                pd.read_parquet(stored[-1]), "universe-snapshot", as_of=today, message=BIAS
            )
        try:
            frame = self._fetch(market)
            if frame.empty:
                raise ValueError("empty universe")
            for col in ("sector", "industry"):
                if col not in frame:
                    frame[col] = None
            frame["market"] = market
            frame["membership_as_of"] = today.isoformat()
            frame.to_parquet(self.directory / f"{market}-{today.isoformat()}.parquet", index=False)
            return DataResult(
                frame, "Wikipedia" if market == "us" else "pykrx", as_of=today, message=BIAS
            )
        except Exception as exc:
            if stored:
                latest = stored[-1]
                return DataResult(
                    pd.read_parquet(latest),
                    "universe-snapshot",
                    as_of=date.fromisoformat(latest.stem[3:]),
                    status="stale",
                    message="마지막 구성 · " + BIAS,
                )
            return DataResult(
                None, "universe", status="failed", message="구성 조회 실패: " + type(exc).__name__
            )


def serialize(value: Any) -> Any:
    """JSON-safe boundary: missing values remain null, never zero."""
    import math
    from dataclasses import asdict, is_dataclass
    from datetime import datetime

    import numpy as np

    if is_dataclass(value) and not isinstance(value, type):
        return serialize(asdict(value))
    if isinstance(value, dict):
        return {str(k): serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(v) for v in value]
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return serialize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
