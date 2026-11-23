"""Validate locally against Render's checked-in public schema snapshot."""

import json
from pathlib import Path

import yaml
from jsonschema import validate

ROOT = Path(__file__).resolve().parents[1]
validate(
    yaml.safe_load((ROOT / "render.yaml").read_text()),
    json.loads((ROOT / "docs/render-schema.json").read_text()),
)
print("Render Blueprint JSON Schema: PASS (no remote validation or deployment)")
