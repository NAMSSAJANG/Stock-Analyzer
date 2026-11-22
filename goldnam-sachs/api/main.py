"""Same-origin API and static export host. No user state on local disk in production."""

import math
import os
import re
from datetime import date
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from goldnam_engine._version import APP_VERSION
from goldnam_engine.data.store import Store
from goldnam_engine.data.universe import serialize
from goldnam_engine.risk.portfolio import Holding, size_portfolio
from goldnam_engine.strategy import STRATEGY
from goldnam_engine.trade.trade_core import Costs, plan_ladder, simulate, target_average
from goldnam_engine.validation.events import event_summary, study_symbol
from goldnam_engine.validation.series import setup_history
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .auth import COOKIE, SESSION_SECONDS, Auth
from .schemas import (
    Analysis,
    Backup,
    Envelope,
    ExecutionInput,
    JournalInput,
    JournalRecord,
    Login,
    Meta,
    PlanInput,
    PriceData,
    ScoreRow,
    Screener,
    SearchHit,
    Settings,
    SimulationInput,
    WatchItem,
)
from .service import AnalysisService, SourceFailure


def problem(status: int, title: str, detail: str, source: str | None = None) -> JSONResponse:
    return JSONResponse(
        {
            "type": "about:blank",
            "title": title,
            "status": status,
            "detail": detail,
            "source": source,
        },
        status_code=status,
        media_type="application/problem+json",
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
    )


def create_app(
    store: Store | None = None,
    service: AnalysisService | None = None,
    passcode_hash: str | None = None,
    session_secret: str | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    application = FastAPI(title="Goldnam Sachs", version=APP_VERSION, docs_url=None, redoc_url=None)
    if store is None and os.getenv("DATABASE_URL"):
        store = Store()
    auth = Auth(store, passcode_hash, session_secret)
    source_service = service or (AnalysisService(store) if store else None)
    static = (static_dir or Path(os.getenv("WEB_STATIC_DIR", "web/out"))).resolve()
    application.state.store = store
    application.state.auth = auth
    application.state.service = source_service

    def db() -> Store:
        if store is None:
            raise HTTPException(503, "DATABASE_URL 미설정 · 저장소 준비 필요")
        return store

    def data_service() -> AnalysisService:
        if source_service is None:
            raise HTTPException(503, "데이터 서비스 준비 필요")
        return source_service

    def symbol_checked(symbol: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9^][A-Za-z0-9.^=\-]{0,19}", symbol):
            raise HTTPException(422, "종목 코드를 확인하세요")
        return symbol.upper()

    @application.middleware("http")
    async def guard(request: Request, call_next: Any) -> Response:
        path = request.url.path
        if ".." in path.split("/"):
            return problem(404, "화면 없음", "허용하지 않는 경로")
        public = path in {
            "/health",
            "/api/v1/health",
            "/api/v1/auth/login",
            "/login",
            "/login/",
            "/offline.html",
            "/manifest.webmanifest",
            "/service-worker.js",
            "/robots.txt",
        } or (
            path.startswith(("/_next/", "/icons/", "/brand/"))
            and Path(path).suffix.lower()
            in {".js", ".css", ".woff2", ".woff", ".png", ".svg", ".ico", ".jpg"}
        )
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            expected = os.getenv("PUBLIC_BASE_URL", str(request.base_url).rstrip("/")).rstrip("/")
            if origin and origin.rstrip("/") != expected:
                return problem(403, "요청 차단", "허용하지 않은 출처")
            if request.headers.get("sec-fetch-site") == "cross-site":
                return problem(403, "요청 차단", "다른 사이트에서의 변경 요청")
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return problem(400, "요청 형식 오류", "Content-Length 오류")
            if length > 2_000_000:
                return problem(413, "요청 크기 초과", "2MB 이하로 가져오세요")
        try:
            authenticated = public or auth.authenticated(request)
        except SQLAlchemyError:
            return problem(503, "저장소 연결 실패", "잠시 후 다시 시도하세요", "Postgres")
        if not authenticated:
            response: Response = (
                problem(401, "로그인 필요", "비밀번호로 로그인하세요")
                if path.startswith("/api/") or path == "/openapi.json"
                else RedirectResponse("/login/", status_code=303)
            )
        else:
            response = await call_next(request)
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response

    @application.exception_handler(SourceFailure)
    async def source_error(request: Request, exc: SourceFailure) -> JSONResponse:
        return problem(503, "데이터 조회 실패", exc.message, exc.source)

    @application.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(exc.status_code, "요청을 처리할 수 없음", str(exc.detail))

    @application.exception_handler(RequestValidationError)
    async def input_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Do not echo input, especially passcodes, in validation errors.
        fields = ", ".join(".".join(str(p) for p in error["loc"]) for error in exc.errors())
        return problem(422, "입력값 확인", fields)

    @application.exception_handler(ValueError)
    async def value_error(request: Request, exc: ValueError) -> JSONResponse:
        return problem(422, "계산 입력값 확인", "가격·수량·비용·계좌 한도를 확인하세요")

    @application.get("/health", include_in_schema=False)
    def legacy_health() -> dict[str, str]:
        return {"status": "scaffold", "version": APP_VERSION}

    @application.get("/api/v1/health", response_model=Envelope[dict[str, Any]])
    def health() -> Envelope[dict[str, Any]]:
        batches = {m: store.get("batch", m) for m in ("us", "kr")} if store else {}
        return Envelope(
            data={
                "status": "ready" if auth.configured else "configuration_required",
                "database_configured": store is not None,
                "auth_configured": auth.configured,
                "last_success": {m: b.get("as_of") if b else None for m, b in batches.items()},
            }
        )

    @application.post("/api/v1/auth/login", response_model=Envelope[dict[str, bool]])
    def login(body: Login, request: Request, response: Response) -> Envelope[dict[str, bool]]:
        if not auth.configured:
            raise HTTPException(503, "로그인 해시·세션 시크릿·DB 설정 필요")
        ip = request.client.host if request.client else "unknown"
        if not auth.allowed(ip):
            raise HTTPException(429, "로그인 시도 제한 · 1분 뒤 다시 시도하세요")
        token = auth.login(body.passcode)
        if token is None:
            raise HTTPException(401, "비밀번호를 확인하세요")
        response.set_cookie(
            COOKIE,
            token,
            max_age=SESSION_SECONDS,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )
        return Envelope(data={"authenticated": True})

    @application.get("/api/v1/auth/session", response_model=Envelope[dict[str, bool]])
    def session() -> Envelope[dict[str, bool]]:
        return Envelope(data={"authenticated": True})

    @application.post("/api/v1/auth/logout", response_model=Envelope[dict[str, bool]])
    def logout(request: Request, response: Response) -> Envelope[dict[str, bool]]:
        auth.logout(request)
        response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="lax")
        return Envelope(data={"authenticated": False})

    @application.get("/api/v1/search", response_model=Envelope[list[SearchHit]])
    def search(q: str = Query(min_length=1, max_length=60)) -> Envelope[list[SearchHit]]:
        return Envelope(data=data_service().search(q))

    @application.get("/api/v1/stocks/{symbol}/analysis", response_model=Envelope[Analysis])
    def analysis(symbol: str, include_options: bool = False) -> Envelope[Analysis]:
        return data_service().analysis(symbol_checked(symbol), include_options)

    @application.get("/api/v1/stocks/{symbol}/prices", response_model=Envelope[PriceData])
    def prices(symbol: str, range: str = "1y") -> Envelope[PriceData]:
        ranges = {"1m": 35, "3m": 100, "1y": 400, "5y": 1900, "10y": 3700}
        if range not in ranges:
            raise HTTPException(422, "기간은 1m/3m/1y/5y/10y")
        return data_service().price_data(symbol_checked(symbol), ranges[range])

    @application.get("/api/v1/universe/{market}/scores", response_model=Envelope[Screener])
    def scores(
        market: str,
        as_of: date | None = None,
        sort: str = "score",
        minimum: int = Query(default=0, ge=0, le=100),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=30, ge=1, le=100),
    ) -> Envelope[Screener]:
        if market not in {"us", "kr"}:
            raise HTTPException(422, "시장 오류")
        batch = db().get("batch", market)
        day = str(as_of) if as_of else str(batch["as_of"]) if batch else ""
        records = db().list("scores", f"{market}:{day}:") if day else []
        if sort not in {"score", "momentum", "trend", "quality", "value", "growth", "symbol"}:
            raise HTTPException(422, "정렬 기준 오류")

        def value(row: dict[str, Any]) -> float:
            v = (
                row["score"].get("value")
                if sort == "score"
                else row.get("factors", {}).get(sort, {}).get("value")
            )
            return float(v) if v is not None else -1

        rows = [
            r
            for r in records
            if minimum == 0
            or (r["score"].get("value") is not None and r["score"]["value"] >= minimum)
        ]
        rows.sort(key=lambda r: str(r["symbol"]))
        if sort != "symbol":
            rows.sort(key=value, reverse=True)
        total = len(rows)
        return Envelope(
            data=Screener(
                items=[
                    ScoreRow.model_validate(r)
                    for r in rows[(page - 1) * page_size : page * page_size]
                ],
                total=total,
                page=page,
                pages=math.ceil(total / page_size),
            ),
            meta=Meta(as_of=day or None),
            warnings=[] if batch else ["일일 배치 데이터 없음"],
        )

    @application.get("/api/v1/market/{market}/regime", response_model=Envelope[dict[str, Any]])
    def market_regime(market: str) -> Envelope[dict[str, Any]]:
        if market not in {"us", "kr"}:
            raise HTTPException(422, "시장 오류")
        return Envelope(data=data_service().regime(market))

    @application.get(
        "/api/v1/validation/{market}/latest", response_model=Envelope[dict[str, Any] | None]
    )
    def validation(market: str) -> Envelope[dict[str, Any] | None]:
        if market not in {"us", "kr"}:
            raise HTTPException(422, "시장 오류")
        result = db().get("validation", market)
        return Envelope(data=result, warnings=[] if result else ["미검증 · 검증 배치 실행 필요"])

    @application.get("/api/v1/watchlist", response_model=Envelope[list[WatchItem]])
    def watchlist() -> Envelope[list[WatchItem]]:
        return Envelope(data=[WatchItem(symbol=r["symbol"]) for r in db().list("watchlist")])

    @application.post("/api/v1/watchlist", response_model=Envelope[WatchItem])
    def add_watch(body: WatchItem) -> Envelope[WatchItem]:
        symbol = symbol_checked(body.symbol)
        db().put("watchlist", symbol, {"symbol": symbol})
        return Envelope(data=WatchItem(symbol=symbol))

    @application.delete("/api/v1/watchlist/{symbol}", response_model=Envelope[dict[str, bool]])
    def delete_watch(symbol: str) -> Envelope[dict[str, bool]]:
        db().remove("watchlist", symbol_checked(symbol))
        return Envelope(data={"deleted": True})

    @application.get("/api/v1/journal", response_model=Envelope[list[JournalRecord]])
    def journal() -> Envelope[list[JournalRecord]]:
        return Envelope(data=[JournalRecord.model_validate(r) for r in db().list("journal")])

    @application.post("/api/v1/journal", response_model=Envelope[JournalRecord])
    def add_journal(body: JournalInput) -> Envelope[JournalRecord]:
        from goldnam_engine.data.quality import market_for

        symbol = symbol_checked(body.symbol)
        identifier = str(uuid4())
        # Snapshot only a score known for the user's trade date; never backdate today's analysis.
        snapshot = db().get("scores", f"{market_for(symbol)}:{body.date}:{symbol}") or {}
        record = JournalRecord(
            **body.model_dump(exclude={"symbol"}),
            symbol=symbol,
            id=identifier,
            snapshot=snapshot,
            score_version="score-v0.1",
        )
        db().put("journal", identifier, record.model_dump(mode="json"))
        return Envelope(data=record, warnings=[] if snapshot else ["거래일 점수 스냅샷 없음"])

    @application.delete("/api/v1/journal/{identifier}", response_model=Envelope[dict[str, bool]])
    def delete_journal(identifier: str) -> Envelope[dict[str, bool]]:
        db().remove("journal", identifier)
        return Envelope(data={"deleted": True})

    @application.get("/api/v1/settings", response_model=Envelope[Settings])
    def settings() -> Envelope[Settings]:
        return Envelope(data=Settings.model_validate(db().get("settings", "user") or {}))

    @application.post("/api/v1/settings", response_model=Envelope[Settings])
    def save_settings(body: Settings) -> Envelope[Settings]:
        db().put("settings", "user", body.model_dump(mode="json"))
        return Envelope(data=body)

    @application.get("/api/v1/strategy", response_model=Envelope[dict[str, Any]])
    def strategy() -> Envelope[dict[str, Any]]:
        from dataclasses import asdict

        return Envelope(data=asdict(STRATEGY), warnings=["검증 전 임계값 변경 금지"])

    @application.get("/api/v1/export", response_model=Envelope[Backup])
    def export() -> Envelope[Backup]:
        return Envelope(
            data=Backup(
                watchlist=watchlist().data, journal=journal().data, settings=settings().data
            )
        )

    @application.post("/api/v1/import", response_model=Envelope[dict[str, int]])
    def import_backup(body: Backup) -> Envelope[dict[str, int]]:
        # Merge, do not delete existing records. Validation completes before any write.
        db().put_many("watchlist", [(r.symbol, r.model_dump()) for r in body.watchlist])
        db().put_many("journal", [(r.id, r.model_dump(mode="json")) for r in body.journal])
        db().put("settings", "user", body.settings.model_dump(mode="json"))
        return Envelope(data={"watchlist": len(body.watchlist), "journal": len(body.journal)})

    @application.post(
        "/api/v1/trade-lab/plan", response_model=Envelope[dict[str, Any] | list[dict[str, Any]]]
    )
    def plan(body: PlanInput) -> Envelope[Any]:
        cost = Costs(**body.costs.model_dump())
        if body.kind == "ladder":
            result: Any = plan_ladder(body.cash, body.prices, body.weights, cost, body.reserve_pct)
        elif body.kind == "target_average":
            quantity, amount = target_average(
                body.shares, body.average, body.entry, body.target, cost
            )
            result = {"quantity": quantity, "amount": amount}
        else:
            result = size_portfolio(
                body.account,
                body.cash,
                body.entry,
                body.stop,
                body.target,
                body.sector,
                [Holding(**h) for h in body.holdings],
                body.risk_pct,
                body.max_position_pct,
                body.multiplier,
                cost,
            )
        return Envelope(data=serialize(result))

    @application.post("/api/v1/trade-lab/simulate", response_model=Envelope[dict[str, Any]])
    def simulation(body: SimulationInput) -> Envelope[dict[str, Any]]:
        if body.kind == "loss_streak":
            from goldnam_engine.trade.lab import loss_simulation

            return Envelope(
                data=loss_simulation(
                    body.win_fraction, body.payoff_ratio, body.risk_fraction, body.seed
                )
            )
        rows, log = simulate(
            body.shares,
            body.average,
            body.cash,
            body.path,
            body.rules,
            Costs(**body.costs.model_dump()),
        )
        return Envelope(data={"rows": serialize(rows), "journal": serialize(log)})

    @application.post("/api/v1/execution-study", response_model=Envelope[dict[str, Any]])
    def execution(body: ExecutionInput) -> Envelope[dict[str, Any]]:
        from goldnam_engine.data.quality import market_for

        service = data_service()
        symbol = symbol_checked(body.symbol)
        frame = service.prices.prices(symbol, body.start, date.today())
        bench = service.prices.prices(
            "SPY" if market_for(symbol) == "us" else "^KS11", body.start, date.today()
        )
        if frame.data is None or bench.data is None:
            raise SourceFailure("prices", "체결 검증 시세 없음")
        history = setup_history(frame.data, bench.data, market_for(symbol))
        actual, random = study_symbol(
            frame.data, history, body.setup, body.mode, Costs(**body.costs.model_dump())
        )
        return Envelope(
            data=cast(
                dict[str, Any],
                serialize(
                    {"summary": event_summary(actual, random), "ledger": actual.to_dict("records")}
                ),
            )
        )

    @application.get("/{path:path}", include_in_schema=False)
    def static_file(path: str) -> Response:
        if path == "robots.txt":
            return Response("User-agent: *\nDisallow: /\n", media_type="text/plain")
        requested = (static / path).resolve()
        if not requested.is_relative_to(static):
            raise HTTPException(404, "화면 없음")
        candidates = [requested, requested / "index.html", requested.with_suffix(".html")]
        for candidate in candidates:
            if candidate.is_file() and candidate.is_relative_to(static):
                return FileResponse(candidate)
        raise HTTPException(404, "정적 화면 빌드가 필요합니다")

    return application


app = create_app()
