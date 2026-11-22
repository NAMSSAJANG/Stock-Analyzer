"""Bounded negative cache, stale fallback, retries and per-provider circuit breaker."""

from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import datetime, timedelta
from threading import RLock
from time import sleep
from typing import Generic, TypeVar

from .contracts import DataResult, utcnow

T = TypeVar("T")


class ResilientCache(Generic[T]):
    def __init__(
        self, clock: Callable[[], datetime] = utcnow, wait: Callable[[float], None] = sleep
    ) -> None:
        self.clock = clock
        self.wait = wait
        self.success: dict[str, tuple[datetime, DataResult[T]]] = {}
        self.negative: dict[str, tuple[datetime, DataResult[T]]] = {}
        self.breakers: dict[str, tuple[int, datetime]] = {}
        self.lock = RLock()

    def get(
        self, key: str, providers: Sequence[tuple[str, Callable[[], DataResult[T]]]], ttl: timedelta
    ) -> DataResult[T]:
        with self.lock:
            now = self.clock()
            previous = self.success.get(key)
            if previous and now < previous[0]:
                return previous[1]
            negative = self.negative.get(key)
            if negative and now < negative[0]:
                return self._fallback(previous, negative[1])
        failures: list[str] = []
        stale: DataResult[T] | None = None
        for name, call in providers:
            breaker_key = f"{name}:{key}"
            with self.lock:
                count, until = self.breakers.get(breaker_key, (0, now))
            if count >= 3 and now < until:
                failures.append(f"{name}: 일시 중단")
                continue
            for attempt in range(3):
                try:
                    result = call()
                except Exception as exc:
                    # Never include raw exceptions: provider URLs can contain API keys.
                    result = DataResult(None, name, status="failed", message=type(exc).__name__)
                if result.usable and result.status == "stale":
                    stale = result
                    break
                if result.usable:
                    with self.lock:
                        self.breakers[breaker_key] = (0, now)
                        self.negative.pop(key, None)
                        # Failed/stale values are never stored as fresh successes.
                        if result.status in {"ok", "partial"}:
                            self.success[key] = (self.clock() + ttl, result)
                    return result
                if attempt < 2:
                    self.wait(0.25 * 2**attempt)
            if result.usable and result.status == "stale":
                failures.append(f"{name}: 오래된 데이터")
                continue
            with self.lock:
                self.breakers[breaker_key] = (count + 3, self.clock() + timedelta(minutes=5))
            failures.append(f"{name}: {result.message or '조회 실패'}")
        failed: DataResult[T] = DataResult(
            None,
            ", ".join(n for n, _ in providers),
            fetched_at=self.clock(),
            status="failed",
            message="; ".join(failures),
        )
        with self.lock:
            self.negative[key] = (self.clock() + timedelta(minutes=5), stale or failed)
        return stale or self._fallback(previous, failed)

    @staticmethod
    def _fallback(
        previous: tuple[datetime, DataResult[T]] | None, failed: DataResult[T]
    ) -> DataResult[T]:
        if previous:
            return replace(previous[1], status="stale", message="마지막 성공값 · " + failed.message)
        return failed
