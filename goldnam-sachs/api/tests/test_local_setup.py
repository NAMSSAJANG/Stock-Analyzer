from pathlib import Path
from unittest.mock import patch

import pytest
from argon2 import PasswordHasher

from scripts.setup_local import configure


def test_local_credentials_are_hashed_and_never_overwritten(tmp_path: Path) -> None:
    target = tmp_path / ".env"
    with patch("scripts.setup_local.getpass.getpass", return_value="local-fixture-password"):
        assert configure(target)
    original = target.read_text()
    assert "local-fixture-password" not in original
    hashed = original.splitlines()[0].split("=", 1)[1].strip("'")
    assert PasswordHasher().verify(hashed, "local-fixture-password")
    with patch(
        "scripts.setup_local.getpass.getpass", side_effect=AssertionError("must not prompt")
    ):
        assert not configure(target)
    assert target.read_text() == original


def test_invalid_password_does_not_create_config(tmp_path: Path) -> None:
    target = tmp_path / ".env"
    for values in [["short"], ["local-fixture-password", "different-password"]]:
        with patch("scripts.setup_local.getpass.getpass", side_effect=values):
            with pytest.raises(ValueError):
                configure(target)
        assert not target.exists()
