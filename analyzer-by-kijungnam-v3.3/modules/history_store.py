from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "score_history.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=5)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS score_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        captured_at TEXT NOT NULL,
        score INTEGER NOT NULL,
        fundamental INTEGER NOT NULL,
        technical INTEGER NOT NULL,
        market INTEGER NOT NULL,
        news INTEGER NOT NULL,
        reasons TEXT NOT NULL
        )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_score_ticker_time ON score_history(ticker, captured_at DESC)"
    )
    return connection


def save_snapshot(ticker: str, scores: dict, reasons: dict) -> tuple[dict | None, dict]:
    """Save once per UTC day; return the prior and current snapshots."""
    ticker = ticker.upper().strip()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as conn:
        rows = conn.execute(
            "SELECT captured_at, score, fundamental, technical, market, news, reasons "
            "FROM score_history WHERE ticker=? ORDER BY captured_at DESC LIMIT 2",
            (ticker,),
        ).fetchall()
        latest = _row(rows[0]) if rows else None
        today = now[:10]
        values = (
            int(scores["overall"]), int(scores["fundamental"]),
            int(scores["technical"]), int(scores["market"]), int(scores["news"]),
            json.dumps(reasons, ensure_ascii=False),
        )
        if latest and latest["captured_at"][:10] == today:
            conn.execute(
                "UPDATE score_history SET score=?, fundamental=?, technical=?, market=?, news=?, reasons=? "
                "WHERE ticker=? AND captured_at=?",
                (*values, ticker, latest["captured_at"]),
            )
            current = {"captured_at": latest["captured_at"], **dict(zip(
                ["score", "fundamental", "technical", "market", "news"], values[:5]
            )), "reasons": reasons}
            previous = _row(rows[1]) if len(rows) > 1 else None
        else:
            conn.execute(
                "INSERT INTO score_history(ticker,captured_at,score,fundamental,technical,market,news,reasons) "
                "VALUES(?,?,?,?,?,?,?,?)", (ticker, now, *values),
            )
            current = {"captured_at": now, **dict(zip(
                ["score", "fundamental", "technical", "market", "news"], values[:5]
            )), "reasons": reasons}
            previous = latest
    return previous, current


def list_history(ticker: str, limit: int = 30) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT captured_at, score, fundamental, technical, market, news, reasons "
            "FROM score_history WHERE ticker=? ORDER BY captured_at DESC LIMIT ?",
            (ticker.upper().strip(), limit),
        ).fetchall()
    return [_row(row) for row in rows]


def _row(row) -> dict:
    return {
        "captured_at": row[0], "score": row[1], "fundamental": row[2],
        "technical": row[3], "market": row[4], "news": row[5],
        "reasons": json.loads(row[6] or "{}"),
    }
