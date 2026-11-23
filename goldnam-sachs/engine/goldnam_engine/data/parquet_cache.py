"""Disposable, atomic OHLCV disk cache; durable application state belongs in SQL."""

from datetime import date, datetime
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import cast

import pandas as pd

from .contracts import DataResult, Status


class ParquetCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path(self, key: str) -> Path:
        return self.directory / (sha256(key.encode()).hexdigest() + ".parquet")

    def read(self, key: str) -> tuple[datetime, DataResult[pd.DataFrame]] | None:
        try:
            frame = pd.read_parquet(self.path(key))
            meta = frame.attrs.pop("goldnam")
            if meta["status"] not in {"ok", "partial"}:
                return None
            return datetime.fromisoformat(meta["expires"]), DataResult(
                frame,
                meta["source"],
                datetime.fromisoformat(meta["fetched_at"]),
                date.fromisoformat(meta["as_of"]) if meta["as_of"] else None,
                cast(Status, meta["status"]),
                meta["message"],
            )
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def write(self, key: str, expires: datetime, result: DataResult[pd.DataFrame]) -> None:
        if result.data is None or result.status not in {"ok", "partial"}:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        frame = result.data.copy()
        frame.attrs["goldnam"] = {
            "expires": expires.isoformat(),
            "source": result.source,
            "fetched_at": result.fetched_at.isoformat(),
            "as_of": result.as_of.isoformat() if result.as_of else None,
            "status": result.status,
            "message": result.message,
        }
        with NamedTemporaryFile(dir=self.directory, suffix=".parquet", delete=False) as file:
            temp = Path(file.name)
        try:
            frame.to_parquet(temp)
            temp.replace(self.path(key))
        finally:
            temp.unlink(missing_ok=True)
