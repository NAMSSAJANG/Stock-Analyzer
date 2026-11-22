"""Single-user auth: Argon2, revocable opaque sessions, bounded IP rate limiting."""

import hashlib
import hmac
import os
import secrets
import time
from collections import OrderedDict
from threading import Lock

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Request
from goldnam_engine.data.store import Store

COOKIE = "goldnam_session"
SESSION_SECONDS = 30 * 24 * 60 * 60


class Auth:
    def __init__(
        self, store: Store | None, passcode_hash: str | None = None, secret: str | None = None
    ) -> None:
        self.store = store
        self.passcode_hash = (
            passcode_hash if passcode_hash is not None else os.getenv("APP_PASSCODE_HASH", "")
        )
        self.secret = secret if secret is not None else os.getenv("SESSION_SECRET", "")
        self.attempts: OrderedDict[str, list[float]] = OrderedDict()
        self.lock = Lock()
        self.hasher = PasswordHasher()

    @property
    def configured(self) -> bool:
        return bool(
            self.store and self.passcode_hash.startswith("$argon2") and len(self.secret) >= 32
        )

    def fingerprint(self, value: str) -> str:
        return hmac.new(self.secret.encode(), value.encode(), hashlib.sha256).hexdigest()

    def allowed(self, ip: str) -> bool:
        key = self.fingerprint(ip)
        now = time.monotonic()
        with self.lock:
            values = [t for t in self.attempts.get(key, []) if now - t < 60]
            allowed = len(values) < 5
            if allowed:
                values.append(now)
            self.attempts[key] = values
            self.attempts.move_to_end(key)
            while len(self.attempts) > 10000:
                self.attempts.popitem(last=False)
        return allowed

    def login(self, passcode: str) -> str | None:
        if not self.configured or self.store is None:
            return None
        try:
            self.hasher.verify(self.passcode_hash, passcode)
        except (VerificationError, InvalidHashError):
            return None
        token = secrets.token_urlsafe(32)
        self.store.put(
            "session",
            self.fingerprint(token),
            {
                "expires": time.time() + SESSION_SECONDS,
                "credential": self.fingerprint(self.passcode_hash),
            },
        )
        return token

    def authenticated(self, request: Request) -> bool:
        token = request.cookies.get(COOKIE, "")
        if not self.configured or self.store is None or not 20 <= len(token) <= 100:
            return False
        record = self.store.get("session", self.fingerprint(token))
        if not record:
            return False
        if record["expires"] < time.time() or not hmac.compare_digest(
            str(record.get("credential", "")), self.fingerprint(self.passcode_hash)
        ):
            self.store.remove("session", self.fingerprint(token))
            return False
        return True

    def logout(self, request: Request) -> None:
        token = request.cookies.get(COOKIE, "")
        if self.store and token:
            self.store.remove("session", self.fingerprint(token))
