"""Create local Compose credentials interactively without printing secrets."""

import getpass
import os
import secrets
from pathlib import Path

from argon2 import PasswordHasher


def configure(target: Path) -> bool:
    if target.exists():
        print("Existing .env preserved. Setup skipped.")
        return False
    password = getpass.getpass("Choose app password (12+ characters): ")
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")
    if password != getpass.getpass("Confirm password: "):
        raise ValueError("Passwords do not match.")
    hashed = PasswordHasher().hash(password)
    content = (
        f"APP_PASSCODE_HASH='{hashed}'\n"
        f"SESSION_SECRET='{secrets.token_urlsafe(48)}'\n"
        "OPENDART_API_KEY=''\nSEC_USER_AGENT=''\n"
    )
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)
    print("Local credentials saved. Password is not stored in plain text.")
    return True


if __name__ == "__main__":
    try:
        configure(Path("/local/.env"))
    except (ValueError, EOFError) as exc:
        raise SystemExit(str(exc)) from None
