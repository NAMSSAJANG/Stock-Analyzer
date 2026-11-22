from unittest.mock import Mock

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from goldnam_engine.data.contracts import DataResult
from goldnam_engine.data.store import Store

from api.main import create_app
from api.schemas import SearchHit
from api.service import AnalysisService, SourceFailure
from engine.tests.smoke_test import make_momentum

PASSWORD = "test-fixture-only"
SECRET = "test-fixture-session-secret-at-least-32-chars"


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    store = Store("sqlite://")
    service = AnalysisService(store)
    frame, benchmark = make_momentum()
    as_of = frame.index[-1].date()
    service.prices.prices = Mock(
        side_effect=lambda symbol, start, end: DataResult(
            benchmark if symbol == "SPY" else frame, "fixture", as_of=as_of
        )
    )
    service.us.fundamentals = Mock(
        return_value=DataResult(None, "SEC", status="failed", message="키 미설정")
    )
    service.kr.fundamentals = Mock(
        return_value=DataResult(None, "DART", status="failed", message="키 미설정")
    )
    service.current.get = Mock(
        return_value=DataResult({"marketCap": 100}, "fixture", status="partial")
    )
    service.calendar.earnings = Mock(return_value=DataResult(None, "calendar", status="failed"))
    service.fx.usd_krw = Mock(return_value=DataResult(1400.0, "fixture"))
    service.search = Mock(return_value=[SearchHit(symbol="AAPL", name="Apple", market="us")])
    (tmp_path / "index.html").write_text("private shell")
    (tmp_path / "login.html").write_text("login")
    app = create_app(store, service, PasswordHasher().hash(PASSWORD), SECRET, tmp_path)
    with TestClient(app, base_url="https://testserver") as client:
        yield client, store, service, app


def login(client):
    response = client.post("/api/v1/auth/login", json={"passcode": PASSWORD})
    assert response.status_code == 200
    return response


def test_public_health_and_all_other_routes_protected(bundle):
    client, _, _, app = bundle
    assert client.get("/api/v1/health").json()["data"]["auth_configured"]
    assert client.get("/", follow_redirects=False).status_code == 303
    assert client.get("/login/").status_code == 200
    assert client.get("/openapi.json").status_code == 401
    for path in app.openapi()["paths"]:
        if path in {"/api/v1/health", "/api/v1/auth/login"}:
            continue
        url = (
            path.replace("{symbol}", "AAPL").replace("{market}", "us").replace("{identifier}", "x")
        )
        method = next(iter(app.openapi()["paths"][path]))
        assert client.request(method, url).status_code == 401, (method, url)


def test_auth_cookie_csrf_revocation_and_rate_limit(bundle):
    client, store, _, app = bundle
    response = login(client)
    cookie = response.headers["set-cookie"]
    assert all(part in cookie for part in ["HttpOnly", "Secure", "SameSite=lax", "Max-Age=2592000"])
    token = client.cookies.get("goldnam_session")
    assert client.get("/api/v1/auth/session").status_code == 200
    assert client.get("/").headers["x-robots-tag"].startswith("noindex")
    assert (
        client.post(
            "/api/v1/watchlist", json={"symbol": "AAPL"}, headers={"origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert client.post("/api/v1/auth/logout").status_code == 200
    client.cookies.set("goldnam_session", token)
    assert client.get("/api/v1/auth/session").status_code == 401
    app.state.auth.attempts.clear()
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json={"passcode": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"passcode": PASSWORD}).status_code == 429
    assert store.list("session") == []


def test_search_analysis_prices_market_and_validation(bundle):
    client, store, service, _ = bundle
    login(client)
    assert client.get("/api/v1/search?q=애플").json()["data"][0]["symbol"] == "AAPL"
    analysis = client.get("/api/v1/stocks/AAPL/analysis")
    assert analysis.status_code == 200, analysis.text
    payload = analysis.json()
    assert payload["data"]["score"]["value"] is None
    assert "부분 점수" in payload["data"]["score"]["badges"][0]
    assert payload["data"]["fundamentals"]["current_only"]
    assert payload["data"]["risk"]["earnings"] == "발표일 미확인"
    assert client.get("/api/v1/stocks/AAPL/prices?range=1y").json()["data"]["bars"]
    assert client.get("/api/v1/stocks/AAPL/prices?range=bad").status_code == 422
    assert client.get("/api/v1/market/us/regime").json()["data"]["regime"]
    assert len(client.get("/api/v1/market/us/overview").json()["data"]["macro"]) == 2
    assert client.get("/api/v1/market/other/regime").status_code == 422
    assert client.get("/api/v1/validation/us/latest").json()["data"] is None
    store.put("validation", "us", {"composite_evidence": "미검증"})
    assert (
        client.get("/api/v1/validation/us/latest").json()["data"]["composite_evidence"] == "미검증"
    )
    service.analysis = Mock(side_effect=SourceFailure("fixture", "소스 실패"))
    error = client.get("/api/v1/stocks/AAPL/analysis")
    assert error.status_code == 503 and error.headers["content-type"] == "application/problem+json"
    assert error.json()["source"] == "fixture"


def test_screener_sort_filter_and_pagination(bundle):
    client, store, _, _ = bundle
    login(client)
    assert client.get("/api/v1/universe/us/scores").json()["data"]["total"] == 0
    store.put("batch", "us", {"as_of": "2026-01-01"})
    for symbol, value in [("A", 1), ("B", 90), ("C", None)]:
        store.put(
            "scores",
            f"us:2026-01-01:{symbol}",
            {"symbol": symbol, "score": {"value": value, "as_of": "2026-01-01"}},
        )
    result = client.get("/api/v1/universe/us/scores?page_size=1").json()
    assert result["data"]["items"][0]["symbol"] == "B" and result["data"]["pages"] == 3
    assert client.get("/api/v1/universe/us/scores?minimum=50").json()["data"]["total"] == 1
    assert client.get("/api/v1/universe/us/scores?sort=bad").status_code == 422
    assert client.get("/api/v1/universe/other/scores").status_code == 422


def test_watch_journal_settings_backup_roundtrip(bundle):
    client, store, _, _ = bundle
    login(client)
    assert (
        client.post("/api/v1/watchlist", json={"symbol": "aapl"}).json()["data"]["symbol"] == "AAPL"
    )
    assert len(client.get("/api/v1/watchlist").json()["data"]) == 1
    trade = {
        "symbol": "AAPL",
        "date": "2020-01-01",
        "side": "buy",
        "quantity": 2,
        "price": 100,
        "notes": "진입",
    }
    response = client.post("/api/v1/journal", json=trade)
    assert response.status_code == 200, response.text
    row = response.json()["data"]
    assert row["snapshot"] == {} and row["score_version"] == "score-v0.1"
    assert client.get("/api/v1/journal").json()["data"][0]["id"] == row["id"]
    settings = client.get("/api/v1/settings").json()["data"]
    settings["theme"] = "goldnam"
    assert client.post("/api/v1/settings", json=settings).status_code == 200
    assert client.get("/api/v1/strategy").json()["data"]["max_positions"] == 8
    backup = client.get("/api/v1/export").json()["data"]
    assert client.delete("/api/v1/watchlist/AAPL").status_code == 200
    assert client.delete(f"/api/v1/journal/{row['id']}").status_code == 200
    assert client.post("/api/v1/import", json=backup).json()["data"]["journal"] == 1
    assert client.get("/api/v1/settings").json()["data"]["theme"] == "goldnam"
    assert "session" not in str(backup)


def test_trade_plan_simulation_and_execution(bundle):
    client, _, _, _ = bundle
    login(client)
    assert client.post("/api/v1/trade-lab/plan", json={}).json()["data"]["수량"] > 0
    ladder = client.post(
        "/api/v1/trade-lab/plan", json={"kind": "ladder", "prices": [100, 90], "weights": [1, 1]}
    )
    assert ladder.status_code == 200 and len(ladder.json()["data"]) == 2
    target = client.post(
        "/api/v1/trade-lab/plan",
        json={"kind": "target_average", "shares": 10, "average": 100, "entry": 80, "target": 90},
    )
    assert target.status_code == 200 and target.json()["data"]["quantity"] > 0
    simulation = client.post(
        "/api/v1/trade-lab/simulate", json={"path": [100, 90, 110], "shares": 2}
    )
    assert simulation.status_code == 200 and len(simulation.json()["data"]["rows"]) == 3
    losses = client.post("/api/v1/trade-lab/simulate", json={"kind": "loss_streak"})
    assert losses.status_code == 200 and losses.json()["data"]["simulations"] == 10000
    execution = client.post(
        "/api/v1/execution-study", json={"symbol": "AAPL", "start": "2025-01-01"}
    )
    assert execution.status_code == 200, execution.text
    assert execution.json()["data"]["summary"]["random_repetitions"] == 20


def test_inputs_do_not_echo_secrets_or_allow_traversal(bundle):
    client, _, _, _ = bundle
    login(client)
    response = client.post(
        "/api/v1/auth/login", json={"passcode": "secret-fixture", "unexpected": "sensitive"}
    )
    assert (
        response.status_code == 422
        and "secret-fixture" not in response.text
        and "sensitive" not in response.text
    )
    assert client.post("/api/v1/trade-lab/plan", json={"stop": 200}).status_code == 422
    assert client.get("/%2e%2e%2fpyproject.toml").status_code == 404
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/robots.txt").text == "User-agent: *\nDisallow: /\n"


def test_missing_auth_configuration_fails_closed(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app = create_app(passcode_hash="", session_secret="")
    with TestClient(app, base_url="https://testserver") as client:
        assert client.post("/api/v1/auth/login", json={"passcode": PASSWORD}).status_code == 503
        assert client.get("/api/v1/health").json()["data"]["status"] == "configuration_required"


def test_public_asset_prefix_cannot_bypass_private_page(bundle):
    client, _, _, _ = bundle
    assert client.get("/_next/%2e%2e/index.html", follow_redirects=False).status_code == 404
    assert client.get("/_next/private.html", follow_redirects=False).status_code == 303


def test_expired_session_and_changed_passcode_invalidate(bundle):
    client, store, _, app = bundle
    login(client)
    record = store.list("session")[0]
    record["expires"] = 0
    store.put("session", record["id"], record)
    assert client.get("/api/v1/auth/session").status_code == 401
    client.cookies.clear()
    login(client)
    app.state.auth.passcode_hash = PasswordHasher().hash("different-test-fixture")
    assert client.get("/api/v1/auth/session").status_code == 401


def test_legacy_history_import_is_versioned_and_never_merges_scores(bundle):
    client, store, _, _ = bundle
    login(client)
    rows = [{"symbol": "AAPL", "date": "2020-01-01", "opportunity": 75, "metadata": "{}"}]
    assert client.post("/api/v1/history/import", json=rows).json()["data"]["imported"] == 1
    assert client.post("/api/v1/history/import", json=rows).status_code == 200
    result = client.get("/api/v1/history").json()["data"]
    assert len(result) == 1 and result[0]["score_version"] == "v6"
    assert store.list("scores") == []
    assert client.post("/api/v1/history/import", json=[{"symbol": "AAPL"}]).status_code == 422


def test_saved_costs_apply_and_bad_holdings_are_validation_errors(bundle):
    client, _, _, _ = bundle
    login(client)
    defaults = client.get("/api/v1/settings").json()["data"]
    defaults["costs"] = dict(buy_fee=0.01, sell_fee=0.01, sell_tax=0.01, slippage=0.01)
    client.post("/api/v1/settings", json=defaults)
    implicit = client.post("/api/v1/trade-lab/plan", json={}).json()["data"]
    explicit = client.post("/api/v1/trade-lab/plan", json={"costs": defaults["costs"]}).json()[
        "data"
    ]
    assert implicit == explicit
    assert (
        client.post("/api/v1/trade-lab/plan", json={"holdings": [{"bad": "value"}]}).status_code
        == 422
    )
