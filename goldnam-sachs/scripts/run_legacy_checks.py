"""Run preserved Streamlit scripts against the installed migrated engine, offline.

Compatibility names exist only inside this subprocess, never in the package.
Use --baseline PATH to run the same scripts against an untouched source checkout.
"""

import argparse
import importlib
import json
import os
import runpy
import sys
import tempfile
from pathlib import Path

from pytest_socket import disable_socket

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "script",
        choices=[
            "smoke_test.py",
            "test_trade_ui.py",
            "test_execution_ui.py",
            "test_analysis_ui.py",
        ],
    )
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    if args.baseline:
        fixture = args.baseline.resolve()
        sys.path.insert(0, str(fixture))
    else:
        fixture = ROOT / "engine/tests/legacy_ui"
        mapping = json.loads((ROOT / "docs/migration-map.json").read_text())
        for old, new in mapping.items():
            if old != "options_analyzer":
                sys.modules[old] = importlib.import_module("goldnam_engine." + new)
        sys.modules["smoke_test"] = importlib.import_module("engine.tests.smoke_test")
        sys.modules["test_execution_engine"] = importlib.import_module(
            "engine.tests.test_execution_engine"
        )
        sys.path.insert(0, str(fixture))
    # Imports may initialize libraries; no data calls are permitted during checks.
    disable_socket(allow_unix_socket=True)
    os.chdir(fixture)
    with tempfile.TemporaryDirectory(prefix="goldnam-ui-") as tmp:
        os.environ["ANALYZER_DB_FILE"] = str(Path(tmp) / "history.sqlite")
        if args.script == "smoke_test.py" and not args.baseline:
            sys.modules["smoke_test"].main()
        else:
            runpy.run_path(str(fixture / args.script), run_name="__main__")


if __name__ == "__main__":
    main()
