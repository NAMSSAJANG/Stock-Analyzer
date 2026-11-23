"""Expose offline test failures as GitHub annotations when log downloads are unavailable."""

from pathlib import Path
from xml.etree import ElementTree

path = Path(".data/ci-results.xml")
if path.exists():
    root = ElementTree.parse(path).getroot()
    for case in root.iter("testcase"):
        for failure in list(case.findall("failure")) + list(case.findall("error")):
            message = (failure.text or failure.get("message", "Test failed"))[-12000:]
            escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            title = case.get("name", "pytest").replace(",", " ")
            print(f"::error title={title}::{escaped}")
