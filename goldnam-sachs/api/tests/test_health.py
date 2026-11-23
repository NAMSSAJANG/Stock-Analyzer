from fastapi.testclient import TestClient
from goldnam_engine._version import APP_VERSION

from api.main import app


def test_scaffold_health_does_not_claim_data_readiness():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "scaffold", "version": APP_VERSION}
