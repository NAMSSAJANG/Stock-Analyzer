"""Offline browser fixture. Never imported by the production application."""

import tempfile
from pathlib import Path

import pytest
import uvicorn

from api.tests.test_api import bundle

ROOT = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as temporary:
    patches = pytest.MonkeyPatch()
    fixtures = bundle.__wrapped__(Path(temporary), patches)
    client, store, service, app = next(fixtures)
    # Use production exported pages with mock sources and real auth/database code.
    from argon2 import PasswordHasher

    from api.main import create_app
    from api.tests.test_api import PASSWORD, SECRET

    store.put("watchlist", "AAPL", {"symbol": "AAPL"})
    store.put("batch", "us", {"as_of": "2026-01-01", "warnings": ["브라우저 테스트용 고정 데이터"]})
    for symbol in ["AAPL", "MSFT"]:
        store.put(
            "scores",
            f"us:2026-01-01:{symbol}",
            {
                "symbol": symbol,
                "name": symbol,
                "market": "us",
                "score": {
                    "value": None,
                    "as_of": "2026-01-01",
                    "coverage": 0.4,
                    "evidence": "미검증",
                    "badges": ["부분 점수 · 테스트 데이터"],
                },
                "factors": {},
            },
        )
    app = create_app(store, service, PasswordHasher().hash(PASSWORD), SECRET, ROOT / "web/out")
    try:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8765,
            ssl_keyfile="/tmp/goldnam-e2e.key",
            ssl_certfile="/tmp/goldnam-e2e.crt",
        )
    finally:
        fixtures.close()
        patches.undo()
