"""Read model assembly. Failed sources remain explicit, never fabricated demo data."""

from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, cast

import pandas as pd
from goldnam_engine.data.contracts import DataResult
from goldnam_engine.data.fundamentals import DartFundamentals, SecFundamentals
from goldnam_engine.data.market_data import CurrentFundamentals, Fx, Prices, YahooCalendar
from goldnam_engine.data.quality import market_for
from goldnam_engine.data.store import Store
from goldnam_engine.data.universe import Universes, serialize
from goldnam_engine.factors.cross_section import financial_features, price_features
from goldnam_engine.factors.technical_engine import build_technical_snapshot
from goldnam_engine.regime.current import build_regime
from goldnam_engine.risk.current import build_risk_snapshot
from goldnam_engine.scoring.cross_section import rank_snapshot
from goldnam_engine.scoring.lenses import consensus
from goldnam_engine.timing.current import build_setups, structural_zones
from goldnam_engine.timing.sr_engine import build_zones

from .schemas import Analysis, Envelope, Meta, PriceBar, PriceData, ScoreModel, SearchHit, Source


class SourceFailure(Exception):
    def __init__(self, source: str, message: str) -> None:
        self.source, self.message = source, message
        super().__init__(message)


def source_of(result: DataResult[Any]) -> Source:
    return Source(
        name=result.source,
        fetched_at=result.fetched_at.isoformat(),
        as_of=str(result.as_of) if result.as_of else None,
        status=result.status,
        message=result.message,
    )


class AnalysisService:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.prices = Prices()
        self.us = SecFundamentals()
        self.kr = DartFundamentals()
        self.current = CurrentFundamentals()
        self.fx = Fx()
        self.calendar = YahooCalendar()
        self.universe = Universes(Path(".data/universe"))

    def search(self, query: str) -> list[SearchHit]:
        q = query.strip().casefold()
        if not q:
            return []
        hits = []
        # Prefer already-observed membership; no need to refetch two markets per keystroke.
        for market in ("us", "kr"):
            paths = sorted(Path(".data/universe").glob(f"{market}-*.parquet"))
            if paths:
                frame = pd.read_parquet(paths[-1])
                for row in frame.to_dict("records"):
                    if (
                        q in str(row.get("name", "")).casefold()
                        or q in str(row["symbol"]).casefold()
                    ):
                        hits.append(
                            SearchHit(
                                symbol=str(row["symbol"]),
                                name=str(row.get("name", row["symbol"])),
                                market=market,
                            )
                        )
        # Korean name lookup uses the preserved listing adapter; only on demand.
        if not hits and any("가" <= c <= "힣" for c in q):
            from goldnam_engine.data.korean_stock_search import load_krx_listing, search_krx_listing

            result = search_krx_listing(query, load_krx_listing(), limit=20)
            for hit in result:
                hits.append(
                    SearchHit(
                        symbol=str(hit.get("symbol", "")),
                        name=str(hit.get("name", "")),
                        market="kr",
                    )
                )
        if not hits and query.replace(".", "").replace("-", "").isalnum() and query.isascii():
            symbol = query.upper()
            if symbol.isdigit() and len(symbol) == 6:
                symbol += ".KS"
            hits.append(
                SearchHit(symbol=symbol, name=f"{symbol} · 직접 조회", market=market_for(symbol))
            )
        return hits[:20]

    def price_data(self, symbol: str, days: int) -> Envelope[PriceData]:
        result = self.prices.prices(symbol, date.today() - timedelta(days=days), date.today())
        if result.data is None:
            raise SourceFailure(result.source, result.message)
        bars = [
            PriceBar(
                time=cast(pd.Timestamp, day).date().isoformat(),
                open=float(r.Open),
                high=float(r.High),
                low=float(r.Low),
                close=float(r.Close),
                volume=float(r.Volume) if pd.notna(r.Volume) else None,
            )
            for day, r in result.data.iterrows()
        ]
        return Envelope(
            data=PriceData(symbol=symbol, bars=bars),
            meta=Meta(as_of=str(result.as_of), coverage=1, sources=[source_of(result)]),
            warnings=[result.message] if result.message else [],
        )

    def regime(self, market: str) -> dict[str, Any]:
        result = self.prices.prices(
            "SPY" if market == "us" else "^KS11", date.today() - timedelta(days=550), date.today()
        )
        regime = build_regime(result.data, market) if result.data is not None else None
        fx = self.fx.usd_krw()
        return {
            "regime": asdict(regime) if regime else None,
            "source": source_of(result).model_dump(),
            "fx": serialize(fx),
            "as_of": str(result.as_of),
        }

    def overview(self, market: str) -> dict[str, Any]:
        from math import sqrt

        macro = []
        for symbol, label, unit in (
            ("^TNX", "미국 10년 국채 수익률", "%"),
            ("^VIX", "미국 VIX", "pt"),
        ):
            result = self.prices.prices(symbol, date.today() - timedelta(days=35), date.today())
            macro.append(
                {
                    "symbol": symbol,
                    "label": label,
                    "unit": unit,
                    "value": float(result.data.Close.iloc[-1]) if result.data is not None else None,
                    "source": source_of(result).model_dump(),
                }
            )
        batch = self.store.get("batch", market)
        rows = self.store.list("scores", f"{market}:{batch['as_of']}:") if batch else []
        tiles = [
            {
                "symbol": r["symbol"],
                "name": r.get("name"),
                "sector": r.get("sector"),
                "weight": sqrt(r["market_cap"]),
                "market_cap": r["market_cap"],
                "change_pct": r.get("change_pct"),
            }
            for r in rows
            if (r.get("market_cap") or 0) > 0
        ]
        return {
            "macro": macro,
            "heatmap": tiles,
            "as_of": batch.get("as_of") if batch else None,
            "note": "히트맵 면적은 시가총액 제곱근. 재무/시가총액 결측 종목 제외. 미국 금리·변동성은 양 시장의 공통 참고 지표.",
        }

    def analysis(self, symbol: str, include_options: bool = False) -> Envelope[Analysis]:
        market = market_for(symbol)
        result = self.prices.prices(symbol, date.today() - timedelta(days=550), date.today())
        if result.data is None:
            raise SourceFailure(result.source, result.message)
        d = result.data
        as_of = result.as_of or date.today()
        benchmark = self.prices.prices(
            "SPY" if market == "us" else "^KS11", date.today() - timedelta(days=550), as_of
        )
        regime = build_regime(benchmark.data, market) if benchmark.data is not None else None
        financial = (self.kr if market == "kr" else self.us).fundamentals(symbol, as_of)
        sources = [source_of(result), source_of(financial), source_of(benchmark)]
        warnings = [r.message for r in (result, financial, benchmark) if r.message]
        facts = financial.data
        current_only = False
        if facts is None:
            fallback = self.current.get(symbol)
            sources.append(source_of(fallback))
            facts = fallback.data
            current_only = True
            warnings.append("현재 재무 스냅샷 · 과거 검증 사용 금지")
        batch = self.store.get("batch", market)
        score_date = str(batch["as_of"]) if batch else str(as_of)
        saved = self.store.get("scores", f"{market}:{score_date}:{symbol}")
        if saved is None and batch:
            peers = self.store.list("scores", f"{market}:{score_date}:")
            reference = pd.DataFrame(
                [
                    {
                        **{k: v.get("value") for k, v in r.get("indicators", {}).items()},
                        "symbol": r["symbol"],
                        "name": r.get("name"),
                        "market": market,
                        "sector": r.get("sector"),
                    }
                    for r in peers
                ]
            )
            if not reference.empty:
                hist = d.loc[d.index <= pd.Timestamp(score_date)]
                if not hist.empty:
                    raw = {
                        k: v.iloc[-1, 0]
                        for k, v in price_features(
                            hist[["Close"]].rename(columns={"Close": symbol})
                        ).items()
                    }
                    pit = (self.kr if market == "kr" else self.us).fundamentals(
                        symbol, date.fromisoformat(score_date)
                    )
                    shares = pit.data.get("shares") if pit.data else None
                    cap = float(shares * hist.Close.iloc[-1]) if shares is not None else None
                    raw.update(financial_features(pit.data, cap))
                    target = pd.DataFrame([{**raw, "symbol": symbol, "market": market}]).set_index(
                        "symbol"
                    )
                    saved = rank_snapshot(
                        reference.set_index("symbol"),
                        date.fromisoformat(score_date),
                        [source.model_dump() for source in sources],
                        target,
                    )[0]
        base = saved or {
            "symbol": symbol,
            "name": symbol,
            "market": market,
            "score": ScoreModel(
                as_of=score_date, badges=["가격 기반 부분 점수 · 재무 또는 유니버스 분포 없음"]
            ).model_dump(),
            "factors": {},
            "grade": "산출 불가",
        }
        if score_date < str(as_of):
            warnings.append(f"순위는 {score_date} 배치 기준 · 최신 배치 대기")
        technical = (
            build_technical_snapshot(d, benchmark.data)
            if len(d) >= 252 and benchmark.data is not None
            else None
        )
        zones = structural_zones(build_zones(d, technical)) if technical else None
        earnings = self.calendar.earnings(symbol)
        fx = self.fx.usd_krw() if market == "kr" else None
        sources.append(source_of(earnings))
        if fx:
            sources.append(source_of(fx))
        risk = (
            build_risk_snapshot(
                technical, regime, (earnings.data - as_of).days if earnings.data else None, fx
            )
            if technical and regime
            else None
        )
        setup = (
            build_setups(float(d.Close.iloc[-1]), technical, regime, zones, risk)
            if technical and regime and zones and risk
            else None
        )
        validation = self.store.get("validation", market)
        options = None
        if include_options and market == "us":
            try:
                import yfinance as yf
                from goldnam_engine.factors.options_analyzer import summarize_options

                ticker = yf.Ticker(symbol)
                expiry = ticker.options[0]
                chain = ticker.option_chain(expiry)
                options = serialize(
                    summarize_options(chain.calls, chain.puts, float(d.Close.iloc[-1]), expiry)
                )
            except Exception:
                warnings.append("옵션 공급자 조회 실패")
        payload = {
            **base,
            "last_price": float(d.Close.iloc[-1]),
            "change_pct": float((d.Close.iloc[-1] / d.Close.iloc[-2] - 1) * 100)
            if len(d) > 1
            else None,
            "technical": technical,
            "regime": regime,
            "zones": zones,
            "risk": risk,
            "timing": setup,
            "fundamentals": {"data": serialize(facts), "current_only": current_only},
            "options": options,
            "evidence_detail": validation,
            "consensus": consensus(base.get("factors", {}), setup, regime, market=market),
            "can_slim": {
                "note": "참고 뷰 · 별도 점수 없음",
                "rsi": technical.rsi if technical else None,
                "volume_ratio": technical.volume_ratio if technical else None,
            },
        }
        clean = cast(dict[str, Any], serialize(payload))
        analysis = Analysis.model_validate(clean)
        self.store.put(
            "analysis_history",
            f"{as_of}:{symbol}",
            {
                "symbol": symbol,
                "date": str(as_of),
                "score_version": "score-v0.1",
                "snapshot": analysis.model_dump(mode="json"),
            },
        )
        return Envelope(
            data=analysis,
            meta=Meta(as_of=str(as_of), coverage=base["score"]["coverage"], sources=sources),
            warnings=warnings,
        )
