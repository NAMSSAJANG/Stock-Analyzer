"""Daily snapshot job. No fake scores when fundamentals or providers are missing."""

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd
from goldnam_engine._version import APP_VERSION, SCORE_VERSION
from goldnam_engine.data.fundamentals import DartFundamentals, SecFundamentals
from goldnam_engine.data.market_data import Fx, Prices
from goldnam_engine.data.quality import calendar
from goldnam_engine.data.store import Store
from goldnam_engine.data.universe import Universes, serialize
from goldnam_engine.factors.cross_section import financial_features, price_features
from goldnam_engine.scoring.cross_section import rank_snapshot
from goldnam_engine.scoring.snapshot import timing_snapshot


def calculate(market: str, as_of: date, cache_dir: Path) -> dict[str, Any]:
    started = perf_counter()
    universe = Universes(cache_dir / "universe").constituents(market, as_of)
    if universe.data is None:
        raise RuntimeError(universe.message)
    members = universe.data.set_index("symbol")
    prices = Prices(cache_dir / "prices")
    fundamentals = DartFundamentals() if market == "kr" else SecFundamentals()
    symbols = list(members.index)
    # Download is I/O-bound; bounded concurrency avoids unbounded provider bursts.
    with ThreadPoolExecutor(max_workers=4) as pool:
        price_results = list(
            pool.map(
                lambda symbol: prices.prices(symbol, as_of - timedelta(days=550), as_of), symbols
            )
        )
    close = pd.DataFrame(
        {s: r.data.Close for s, r in zip(symbols, price_results, strict=True) if r.data is not None}
    )
    close = close.reindex(calendar(market).sessions_in_range(as_of - timedelta(days=550), as_of))
    features = price_features(close)
    snapshot = members.copy()
    for name, values in features.items():
        snapshot[name] = values.iloc[-1].reindex(snapshot.index)
    source_rows = []
    for symbol, price in zip(symbols, price_results, strict=True):
        financial = fundamentals.fundamentals(symbol, as_of)
        fact = financial.data
        shares = fact.get("shares") if fact else None
        last = close[symbol].iloc[-1] if symbol in close and not close.empty else None
        cap = float(shares * last) if shares is not None and last is not None else None
        snapshot.loc[symbol, "market_cap"] = cap
        for column, value in financial_features(fact, cap).items():
            snapshot.loc[symbol, column] = value
        source_rows.append(
            {
                "symbol": symbol,
                "price": {
                    "name": price.source,
                    "fetched_at": price.fetched_at.isoformat(),
                    "as_of": str(price.as_of),
                    "status": price.status,
                    "message": price.message,
                },
                "fundamentals": {
                    "name": financial.source,
                    "fetched_at": financial.fetched_at.isoformat(),
                    "as_of": str(financial.as_of),
                    "status": financial.status,
                    "message": financial.message,
                },
            }
        )
    benchmark = prices.prices(
        "SPY" if market == "us" else "^KS11", as_of - timedelta(days=550), as_of
    )
    fx = Fx().usd_krw() if market == "kr" else None
    ranking_start = perf_counter()
    scores = rank_snapshot(snapshot, as_of, [])
    for row, sources, price in zip(scores, source_rows, price_results, strict=True):
        row.update(timing_snapshot(price.data, benchmark.data, market, fx))
        row["market_cap"] = snapshot.loc[row["symbol"], "market_cap"]
        row["score"]["sources"] = [sources["price"], sources["fundamentals"]]
        for factor in row["factors"].values():
            factor["sources"] = row["score"]["sources"]
    report = {
        "market": market,
        "as_of": as_of.isoformat(),
        "app_version": APP_VERSION,
        "score_version": SCORE_VERSION,
        "universe_as_of": str(universe.as_of),
        "bias": universe.message,
        "count": len(scores),
        "prices_usable": sum(r.usable for r in price_results),
        "composites_available": sum(r["score"]["value"] is not None for r in scores),
        "ranking_seconds": perf_counter() - ranking_start,
        "total_seconds": perf_counter() - started,
        "scores": scores,
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    snapshot.to_parquet(cache_dir / f"features-{market}-{as_of}.parquet")
    return serialize(report)  # type: ignore[no-any-return]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=["us", "kr"], required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--output", type=Path, default=Path(".data/daily.json"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".data"))
    parser.add_argument("--no-db", action="store_true")
    parser.add_argument("--scheduled", action="store_true")
    args = parser.parse_args()
    cal = calendar(args.market)
    if not cal.is_session(args.as_of):
        print(json.dumps({"status": "skipped", "reason": "휴장일"}, ensure_ascii=False))
        return
    if args.scheduled and cal.session_close(
        pd.Timestamp(args.as_of)
    ).to_pydatetime() > datetime.now(timezone.utc):
        raise SystemExit("장 마감 전 실행 거부")
    if not args.no_db and not os.getenv("DATABASE_URL"):
        raise SystemExit("DATABASE_URL 미설정: 로컬 측정은 --no-db")
    report = calculate(args.market, args.as_of, args.cache_dir)
    if not args.no_db:
        store = Store()
        store.put_many(
            "scores", [(f"{args.market}:{args.as_of}:{r['symbol']}", r) for r in report["scores"]]
        )
        store.put("batch", args.market, {k: v for k, v in report.items() if k != "scores"})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "scores"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
