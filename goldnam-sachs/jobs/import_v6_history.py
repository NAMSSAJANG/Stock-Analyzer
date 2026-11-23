"""Read-only legacy import, isolated from current score records."""

import argparse
import hashlib
import json
import math
import re
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from goldnam_engine.data.store import Store

SCORES = (
    "opportunity",
    "company",
    "trend",
    "momentum",
    "relative_strength",
    "pullback",
    "momentum_entry",
    "market",
    "risk",
)


def normalize(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError("History JSON은 최대 10000개 행의 배열이어야 합니다")
    result = []
    for row in rows:
        if not isinstance(row, dict) or not re.fullmatch(
            r"[A-Za-z0-9^][A-Za-z0-9.^=\-]{0,19}", str(row.get("symbol", ""))
        ):
            raise ValueError("History 종목 코드 오류")
        day = date.fromisoformat(str(row.get("date", ""))).isoformat()
        scores = {}
        for name in SCORES:
            value = row.get(name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (float, int))
                or not math.isfinite(value)
                or not 0 <= value <= 100
            ):
                raise ValueError("History 점수는 0~100 유한수 또는 null")
            scores[name] = value
        metadata = row.get("metadata") or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        if not isinstance(metadata, dict):
            raise ValueError("History metadata 오류")
        symbol = row["symbol"].upper()
        identifier = hashlib.sha256(f"v6:{symbol}:{day}".encode()).hexdigest()[:32]
        result.append(
            {
                "id": identifier,
                "symbol": symbol,
                "date": day,
                "scores": scores,
                "preferred_setup": str(row.get("preferred_setup", ""))[:200],
                "metadata": metadata,
                "score_version": "v6",
            }
        )
    return result


def read_legacy(path: Path) -> list[dict[str, Any]]:
    if path.stat().st_size > 100_000_000:
        raise ValueError("가져오기 파일 100MB 제한")
    if path.suffix.lower() in {".sqlite", ".sqlite3", ".db"}:
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as connection:
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.row_factory = sqlite3.Row
            table = connection.execute(
                "SELECT type FROM sqlite_master WHERE name='score_history'"
            ).fetchone()
            if not table or table[0] != "table":
                raise ValueError("v6 score_history 테이블 없음")
            rows = [dict(r) for r in connection.execute("SELECT * FROM score_history LIMIT 10001")]
    else:
        rows = json.loads(path.read_text(encoding="utf-8"))
    return normalize(rows)


def save(rows: list[dict[str, Any]], store: Store) -> int:
    store.put_many("legacy_history", [(row["id"], row) for row in rows])
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    rows = read_legacy(args.path)
    if not args.dry_run:
        save(rows, Store())
    print(json.dumps({"rows": len(rows), "score_version": "v6", "written": not args.dry_run}))


if __name__ == "__main__":
    main()
