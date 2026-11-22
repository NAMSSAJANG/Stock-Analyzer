"""Universe validation runner. Partial runs cannot be promoted to headline evidence."""

import argparse
import json
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, cast
from uuid import uuid4

import pandas as pd
from goldnam_engine._version import APP_VERSION, SCORE_VERSION
from goldnam_engine.data.market_data import Prices
from goldnam_engine.data.store import Store
from goldnam_engine.data.universe import Universes, serialize
from goldnam_engine.factors.cross_section import price_features
from goldnam_engine.trade.cost_defaults import default_costs
from goldnam_engine.validation.events import event_summary, portfolio_simulation, study_symbol
from goldnam_engine.validation.ranking import rank_study
from goldnam_engine.validation.series import regime_series, setup_history


def symbol_events(
    symbol: str, frame: pd.DataFrame, bench: pd.DataFrame, market: str, start: date
) -> tuple[str, dict[str, Any]]:
    history = setup_history(frame, bench, market)
    if not history.empty:
        history = history.loc[pd.to_datetime(history.date) >= pd.Timestamp(start)].reset_index(
            drop=True
        )
    results: dict[str, Any] = {"history": history}
    for setup in ("pullback", "momentum"):
        for mode in ("A", "B", "C"):
            actual, baselines = study_symbol(frame, history, setup, mode, default_costs(market))
            actual["symbol"] = symbol
            for i, b in enumerate(baselines):
                if not b.empty and "r" in b:
                    b = b.loc[
                        b.status == "filled",
                        ["status", "entry_date", "r", "net_return", "holding_days"],
                    ].copy()
                b["symbol"] = symbol
                baselines[i] = b
            results[f"{setup}-{mode}"] = (actual, baselines)
    return symbol, results


def run(
    market: str,
    start: date,
    output: Path,
    symbols: list[str] | None = None,
    skip_events: bool = False,
    workers: int = 4,
) -> dict[str, Any]:
    began = perf_counter()
    run_id = str(uuid4())
    output.mkdir(parents=True, exist_ok=True)
    universe = Universes(Path(".data/universe")).constituents(market, date.today())
    partial = bool(symbols)
    if universe.data is None and not symbols:
        raise RuntimeError(universe.message)
    members = universe.data.set_index("symbol") if universe.data is not None else pd.DataFrame()
    selected = symbols or list(members.index)
    provider = Prices(Path(".data/prices"))
    fetch_start = start - timedelta(days=550)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda s: provider.prices(s, fetch_start, date.today()), selected))
    frames = {
        s: r.data
        for s, r in zip(selected, results, strict=True)
        if r.data is not None and len(r.data) >= 330
    }
    if not frames:
        raise RuntimeError("검증할 시세 없음")
    benchmark = provider.prices("SPY" if market == "us" else "^KS11", fetch_start, date.today())
    if benchmark.data is None:
        raise RuntimeError("실제 지수 시세 없음")
    bench = benchmark.data
    close = pd.DataFrame({s: f.Close for s, f in frames.items()}).sort_index()
    opens = pd.DataFrame({s: f.Open for s, f in frames.items()}).reindex(close.index)
    feature = price_features(close)
    # Per-date winsorization and percentile ranks are vectorized over the universe.
    percentiles = {
        name: values.clip(
            values.quantile(0.01, axis=1), values.quantile(0.99, axis=1), axis=0
        ).rank(axis=1, pct=True)
        * 100
        for name, values in feature.items()
    }
    momentum = (percentiles["momentum_12_1"] + percentiles["momentum_6_1"]) / 2
    trend = (
        pd.concat(
            {
                name: p
                for name, p in percentiles.items()
                if name not in {"momentum_12_1", "momentum_6_1"}
            },
            axis=0,
        )
        .groupby(level=1)
        .mean()
        .reindex(close.index)
    )
    regimes = regime_series(bench).label.reindex(close.index)
    cost = default_costs(market)
    round_trip = float(cost.buy_unit(1) - cost.sell_unit(1))
    report: dict[str, Any] = {
        "run_id": run_id,
        "app_version": APP_VERSION,
        "score_version": SCORE_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "market": market,
        "start": str(start),
        "end": str(close.index[-1].date()),
        "universe_count": len(selected),
        "prices_available": len(frames),
        "universe_as_of": str(universe.as_of),
        "bias": universe.message,
        "scope": "selected-symbol smoke" if partial else "current-universe",
        "variants_tried": 1,
        "parameters_fit": False,
        "costs": asdict(cost),
        "cost_caveat": "현재 세율을 전체 기간에 고정 적용한 비용 시나리오; 과거 세율 복원이 아님",
        "composite_evidence": "미검증",
        "fundamentals": "PIT 재무 미포함; 가격 팩터만 검증, 종합 점수 근거로 전용 금지",
        "rankings": {},
        "events": {},
        "portfolios": {},
        "default_exit": None,
        "default_exit_reason": "검증 근거를 확인하기 전 자동 선택하지 않음",
    }
    try:
        report["commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        report["commit"] = "unknown"
    for name, scores in (("momentum", momentum), ("trend", trend)):
        for horizon in (21, 63):
            detail, summary = rank_study(
                scores.loc[str(start) :], opens.loc[str(start) :], horizon, round_trip, regimes
            )
            if partial:
                summary["evidence"] = "미검증"
            report["rankings"][f"{name}-{horizon}"] = summary
            detail.to_parquet(output / f"{name}-{horizon}.parquet")
    report["price_factor_correlation"] = float(momentum.corrwith(trend, axis=1).mean())
    if not skip_events:
        grouped: dict[str, list[tuple[pd.DataFrame, list[pd.DataFrame]]]] = {}
        with ProcessPoolExecutor(max_workers=workers) as pool:
            tasks = [
                pool.submit(symbol_events, s, f, bench, market, start) for s, f in frames.items()
            ]
            for count, future in enumerate(as_completed(tasks), 1):
                symbol, data = future.result()
                data.pop("history").to_parquet(output / f"signals-{symbol}.parquet")
                for key, pair in data.items():
                    grouped.setdefault(key, []).append(pair)
                if count % 10 == 0 or count == len(tasks):
                    print(f"events {count}/{len(tasks)}", flush=True)
        for key, pairs in grouped.items():
            actual = pd.concat([p[0] for p in pairs], ignore_index=True)
            baseline = [
                pd.concat([p[1][i] for p in pairs if len(p[1]) > i], ignore_index=True)
                for i in range(20)
            ]
            # Nested fills remain in JSON; flat detail is a portable Parquet artifact.
            flat = actual.copy()
            if "fills" in flat:
                flat["fills"] = flat.fills.map(lambda x: json.dumps(serialize(x)))
            flat.to_parquet(output / f"events-{key}.parquet", index=False)
            report["events"][key] = event_summary(actual, baseline)
            sector_map = {
                s: str(members.loc[s].get("sector") or "미확인")
                for s in frames
                if s in members.index
            }
            report["portfolios"][key] = portfolio_simulation(actual, frames, sector_map, cost)
    report["events_skipped"] = skip_events
    report["elapsed_seconds"] = perf_counter() - began
    clean = cast(dict[str, Any], serialize(report))
    (output / "summary.json").write_text(
        json.dumps(clean, ensure_ascii=False, allow_nan=False, indent=2)
    )
    return clean


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=["us", "kr"], required=True)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2015, 1, 1))
    parser.add_argument(
        "--symbols", help="명시적인 부분 스모크 실행: 쉼표 구분, 헤드라인 근거 승격 금지"
    )
    parser.add_argument("--output", type=Path, default=Path(".data/validation"))
    parser.add_argument("--skip-events", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--save-db", action="store_true")
    args = parser.parse_args()
    if args.save_db and not os.getenv("DATABASE_URL"):
        raise SystemExit("DATABASE_URL 미설정")
    if not 1 <= args.workers <= 8:
        raise SystemExit("workers는 1~8")
    result = run(
        args.market,
        args.start,
        args.output,
        args.symbols.split(",") if args.symbols else None,
        args.skip_events,
        args.workers,
    )
    if args.save_db:
        Store().put("validation", args.market, result)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "run_id",
                    "market",
                    "scope",
                    "prices_available",
                    "elapsed_seconds",
                    "composite_evidence",
                )
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
