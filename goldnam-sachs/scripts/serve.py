"""Single worker keeps the in-memory login rate limit consistent."""

import os
import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
uvicorn.run(
    "api.main:app",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "10000")),
    workers=1,
    proxy_headers=False,
    limit_concurrency=16,
)
