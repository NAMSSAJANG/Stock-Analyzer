"""Export contracts without opening the configured application database."""

import json
import os
from pathlib import Path

os.environ.pop("DATABASE_URL", None)
from api.main import create_app  # noqa: E402

schema = create_app().openapi()
path = Path("web/generated/openapi.json")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(schema, ensure_ascii=False, indent=2))
print(f"OpenAPI written: {len(schema['paths'])} paths")
