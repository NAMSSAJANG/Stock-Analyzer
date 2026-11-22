import math
import os
from datetime import date, timedelta
from functools import partial
from pathlib import Path
from typing import Any, cast

import pandas as pd

from .contracts import CalendarProvider, DataResult, FxProvider, PriceProvider
from .parquet_cache import ParquetCache
from .quality import market_for, now_utc, price_ttl, validate_prices
from .resilience import ResilientCache


class YahooPrices(PriceProvider):
    def prices(self, symbol: str, start: date, end: date) -> DataResult[pd.DataFrame]:
        import yfinance as yf

        raw = yf.download(
            symbol,
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            auto_adjust=True,
            progress=False,
            threads=False,
            timeout=12,
            multi_level_index=False,
        )
        if raw is None:
            return DataResult(None, "yfinance", status="failed", message="시세 조회 실패")
        return validate_prices(raw, "yfinance", market_for(symbol), end)


class FdrPrices(PriceProvider):
    def prices(self, symbol: str, start: date, end: date) -> DataResult[pd.DataFrame]:
        import FinanceDataReader as fdr

        code = symbol.split(".")[0] if market_for(symbol) == "kr" else symbol
        raw = fdr.DataReader(code, start.isoformat(), end.isoformat())
        return validate_prices(raw, "FinanceDataReader", market_for(symbol), end)


class Prices(PriceProvider):
    def __init__(self, cache_dir: Path | None = None) -> None:
        self.disk = ParquetCache(cache_dir or Path(os.getenv("GOLDNAM_CACHE_DIR", ".data/cache")))
        self.cache: ResilientCache[pd.DataFrame] = ResilientCache()
        self.yahoo = YahooPrices()
        self.fdr = FdrPrices()

    def prices(self, symbol: str, start: date, end: date) -> DataResult[pd.DataFrame]:
        market = market_for(symbol)
        ordered = [("FinanceDataReader", self.fdr), ("yfinance", self.yahoo)]
        if market == "us":
            ordered.reverse()
        providers = [(name, partial(p.prices, symbol, start, end)) for name, p in ordered]
        ttl = price_ttl(market, now_utc())
        key = f"{symbol}:{start}:{end}"
        if key not in self.cache.success:
            saved = self.disk.read(key)
            if saved:
                self.cache.success[key] = saved
        result = self.cache.get(key, providers, ttl)
        if result.status in {"ok", "partial"} and key in self.cache.success:
            self.disk.write(key, self.cache.success[key][0], result)
        return result


class YahooCalendar(CalendarProvider):
    def earnings(self, symbol: str) -> DataResult[date]:
        if market_for(symbol) == "kr":
            return DataResult(
                None, "calendar", status="failed", message="발표일 미확인 · 한국 공급자 미확보"
            )
        import yfinance as yf

        try:
            values = yf.Ticker(symbol).calendar.get("Earnings Date", [])
            future = sorted(
                pd.Timestamp(x).date() for x in values if pd.Timestamp(x).date() >= date.today()
            )
            if future:
                return DataResult(future[0], "yfinance", as_of=date.today())
        except Exception:
            pass
        return DataResult(None, "yfinance", status="failed", message="발표일 미확인")


class Fx(FxProvider):
    def __init__(self) -> None:
        self.cache: ResilientCache[float] = ResilientCache()

    def _fetch(self, provider: str) -> DataResult[float]:
        if provider == "yfinance":
            result = YahooPrices().prices("KRW=X", date.today() - timedelta(days=20), date.today())
            if result.usable:
                value = float(cast(pd.DataFrame, result.data).Close.iloc[-1])
                return DataResult(
                    value, provider, result.fetched_at, result.as_of, result.status, result.message
                )
            return DataResult(None, provider, status="failed", message="환율 없음")
        import FinanceDataReader as fdr

        frame = fdr.DataReader("USD/KRW", (date.today() - timedelta(days=20)).isoformat())
        if frame.empty:
            return DataResult(None, provider, status="failed", message="환율 없음")
        value = float(frame.Close.dropna().iloc[-1])
        if not math.isfinite(value) or value <= 0:
            return DataResult(None, provider, status="failed", message="환율 오류")
        as_of = pd.Timestamp(frame.index[-1]).date()
        stale = (date.today() - as_of).days > 5
        return DataResult(
            value,
            provider,
            as_of=as_of,
            status="stale" if stale else "ok",
            message="환율 최근값" if stale else "",
        )

    def usd_krw(self) -> DataResult[float]:
        return self.cache.get(
            "USD/KRW",
            [(p, partial(self._fetch, p)) for p in ("yfinance", "FinanceDataReader")],
            timedelta(hours=1),
        )


class CurrentFundamentals:
    """Current screen only. Explicitly prohibited as historical PIT input."""

    def __init__(self) -> None:
        self.cache: ResilientCache[dict[str, Any]] = ResilientCache()

    def get(self, symbol: str) -> DataResult[dict[str, Any]]:
        def fetch() -> DataResult[dict[str, Any]]:
            import yfinance as yf

            info = yf.Ticker(symbol).info
            if not info or not any(
                info.get(k) is not None for k in ("marketCap", "totalRevenue", "returnOnEquity")
            ):
                return DataResult(None, "yfinance", status="failed", message="재무 조회 실패")
            return DataResult(
                dict(info),
                "yfinance",
                as_of=date.today(),
                status="partial",
                message="현재 스냅샷 · 과거 검증 사용 금지",
            )

        return self.cache.get(symbol, [("yfinance", fetch)], timedelta(hours=24))
