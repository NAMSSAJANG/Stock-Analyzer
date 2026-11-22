from datetime import date, datetime, timedelta, timezone
from threading import Lock
from typing import Any, cast

import exchange_calendars as xcals
import numpy as np
import pandas as pd

from .contracts import DataResult

_calendar_lock = Lock()
_calendars: dict[str, Any] = {}


def calendar(market: str) -> Any:
    if market not in {"us", "kr"}:
        raise ValueError("시장은 us 또는 kr이어야 합니다.")
    with _calendar_lock:
        if market not in _calendars:
            _calendars[market] = xcals.get_calendar(
                "XNYS" if market == "us" else "XKRX", start="2010-01-01", end="2035-12-31"
            )
        return _calendars[market]


def price_ttl(market: str, now: datetime) -> timedelta:
    cal = calendar(market)
    sessions = cal.sessions_in_range(now.date(), now.date() + timedelta(days=12))
    for session in sessions:
        close = cal.session_close(session).to_pydatetime()
        if close > now:
            return cast(timedelta, close - now + timedelta(minutes=15))
    return timedelta(hours=1)


def validate_prices(
    frame: pd.DataFrame, source: str, market: str, as_of: date
) -> DataResult[pd.DataFrame]:
    required = ["Open", "High", "Low", "Close", "Volume"]
    if frame.empty or not set(required).issubset(frame.columns):
        return DataResult(None, source, status="failed", message="OHLCV 데이터 없음")
    d = frame[required].copy().apply(pd.to_numeric, errors="coerce")
    d.index = pd.DatetimeIndex(pd.to_datetime(d.index)).tz_localize(None).normalize()
    d = d.loc[d.index.date <= as_of]
    if d.empty or d.index.has_duplicates or not d.index.is_monotonic_increasing:
        return DataResult(None, source, status="failed", message="날짜 순서·중복 오류")
    price = d[required[:4]]
    if (
        (price <= 0).any().any()
        or not np.isfinite(price.to_numpy()).all()
        or (d.High < d[["Open", "Close", "Low"]].max(axis=1)).any()
        or (d.Low > d[["Open", "Close", "High"]].min(axis=1)).any()
    ):
        return DataResult(None, source, status="failed", message="가격 결측·OHLC 범위 오류")
    last = d.index[-1].date()
    cal = calendar(market)
    expected = cal.sessions_in_range(d.index[0].date(), last)
    gaps = len(expected.difference(d.index))
    warnings = []
    if gaps:
        warnings.append(f"거래일 누락 {gaps}일")
    if d.Volume.isna().any() or (d.Volume <= 0).any():
        warnings.append("거래량 누락 또는 0")
    if (d.Close.pct_change().abs() > 0.45).any():
        warnings.append("급변 감지 · 분할/병합 확인 필요")
    sessions_after = cal.sessions_in_range(last, as_of)
    if len(sessions_after) - 1 > 3:
        return DataResult(
            d,
            source,
            as_of=last,
            status="stale",
            message="마지막 봉이 3거래일 초과 · " + "; ".join(warnings),
        )
    return DataResult(
        d, source, as_of=last, status="partial" if warnings else "ok", message="; ".join(warnings)
    )


def market_for(symbol: str) -> str:
    return (
        "kr"
        if symbol.upper().endswith((".KS", ".KQ"))
        or symbol.isdigit()
        or symbol.upper() in {"^KS11", "^KQ11", "KS11", "KQ11"}
        else "us"
    )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
