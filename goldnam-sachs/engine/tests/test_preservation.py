import importlib
import json
from pathlib import Path

from scripts.preservation import fingerprints

ROOT = Path(__file__).resolve().parents[2]


def test_original_tests_preserve_assertions_and_fixtures():
    expected = json.loads((ROOT / "docs/preserved-tests.json").read_text())
    for name, baseline in expected.items():
        assert fingerprints((ROOT / "engine/tests" / name).read_text()) == baseline, name


def test_preserved_executable_ast():
    baseline = json.loads((ROOT / "docs/preservation-baseline.json").read_text())
    for module, expected in baseline["modules"].items():
        path = ROOT / "engine/goldnam_engine" / (module.replace(".", "/") + ".py")
        actual = fingerprints(path.read_text())
        assert actual == expected, module


def test_compatibility_exports_share_identity():
    core = importlib.import_module("goldnam_engine.trade.trade_core")
    compat = importlib.import_module("goldnam_engine.trade.trade_engine")
    for name in (
        "Costs",
        "Position",
        "SCENARIOS",
        "affordable_shares",
        "dec",
        "plan_ladder",
        "position_size",
        "simulate",
        "target_average",
    ):
        assert getattr(core, name) is getattr(compat, name)


def test_engine_has_no_web_imports_or_startup_patch():
    import ast

    root = ROOT / "engine/goldnam_engine"
    assert not list(root.rglob("sitecustomize.py"))
    forbidden = {"streamlit", "fastapi", "plotly", "api", "jobs", "web"}
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                assert not {n.name.split(".")[0] for n in node.names} & forbidden, path
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in forbidden, path
