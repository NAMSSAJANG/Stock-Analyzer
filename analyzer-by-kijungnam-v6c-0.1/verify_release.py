"""Offline release integrity and import checks. Run before uploading.

Maintainers: after intentional edits, run --write-manifest, then verify again.
Line endings are normalized so Git CRLF/LF conversion is harmless.
"""
import argparse
import hashlib
import importlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "release_manifest.json"


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    if args.write_manifest:
        files = sorted([*ROOT.glob("*.py"), ROOT / "requirements.txt", ROOT / ".streamlit/config.toml"])
        MANIFEST.write_text(json.dumps({"version": "v6_A_0.3", "sha256_lf": {
            f.relative_to(ROOT).as_posix(): digest(f) for f in files}}, indent=2) + "\n", encoding="utf-8")
        print("Release manifest written. Run verification next.")
        return
    if not MANIFEST.exists():
        raise SystemExit("FAIL: release_manifest.json is missing. Upload the whole release.")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors = []
    for name, expected in manifest["sha256_lf"].items():
        path = ROOT / name
        if not path.is_file():
            errors.append(f"Missing: {name}")
        elif digest(path) != expected:
            errors.append(f"Modified / different release: {name}")
    if errors:
        raise SystemExit("FAIL\n" + "\n".join(errors))
    contracts = {"trade_core": ["Costs", "dec", "position_size", "simulate", "plan_ladder"],
                 "trade_engine": ["Costs", "dec", "position_size"],
                 "trade_lab": ["render_trade_lab"],
                 "execution_engine": ["run_execution_study"],
                 "execution_lab": ["render_execution_lab"],
                 "calibration_engine": ["run_setup_calibration"],
                 "calibration_cache": ["calibration_key"]}
    for name, attrs in contracts.items():
        module = importlib.import_module(name)
        if Path(module.__file__).resolve().parent != ROOT:
            raise SystemExit(f"FAIL: {name} was imported outside this release")
        for attr in attrs:
            if not callable(getattr(module, attr, None)):
                raise SystemExit(f"FAIL: {name}.{attr} missing")
    print(f"PASS: {manifest['version']} / {len(manifest['sha256_lf'])} files / import contracts")


if __name__ == "__main__":
    main()
