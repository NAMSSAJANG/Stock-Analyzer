import os

import pytest
from goldnam_engine.data.store import Store


@pytest.mark.live
def test_real_postgres_reconnect_and_upsert():
    url = os.getenv("GOLDNAM_TEST_DATABASE_URL")
    if not url:
        pytest.skip("명시적인 임시 Postgres URL 필요")
    first = Store(url)
    first.put("test-integration", "persistence", {"value": 42})
    first.engine.dispose()
    second = Store(url)
    try:
        assert second.get("test-integration", "persistence") == {"value": 42}
        second.put("test-integration", "persistence", {"value": 43})
        assert second.list("test-integration")[0]["value"] == 43
        second.remove("test-integration", "persistence")
        assert second.get("test-integration", "persistence") is None
    finally:
        second.remove("test-integration", "persistence")
        second.engine.dispose()
