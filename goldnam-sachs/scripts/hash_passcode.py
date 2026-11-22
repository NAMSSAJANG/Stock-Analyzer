"""Generate an Argon2 hash without echoing a passcode or writing it to logs."""

import getpass
import os
from pathlib import Path

from argon2 import PasswordHasher


def main() -> None:
    first = getpass.getpass("앱 비밀번호 (12자 이상): ")
    second = getpass.getpass("한 번 더: ")
    if len(first) < 12 or first != second:
        raise SystemExit("12자 이상이며 두 입력이 같아야 합니다.")
    target = Path(".data/passcode.env")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as file:
        file.write("APP_PASSCODE_HASH=" + PasswordHasher().hash(first) + "\n")
    print(
        "해시를 .data/passcode.env에 저장했습니다. Render 환경변수에 직접 복사하고 안전하게 보관하세요."
    )


if __name__ == "__main__":
    main()
