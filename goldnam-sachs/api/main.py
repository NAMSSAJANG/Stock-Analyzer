"""Development-only liveness endpoint. Product API is Phase 5."""

from fastapi import FastAPI
from goldnam_engine._version import APP_VERSION

app = FastAPI(title="Goldnam Sachs", version=APP_VERSION)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "scaffold", "version": APP_VERSION}
