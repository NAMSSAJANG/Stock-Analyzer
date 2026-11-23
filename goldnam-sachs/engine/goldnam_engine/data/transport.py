"""Timeout shim for pinned providers which omit requests' timeout argument.

Only their module-local requests references are replaced. The global requests
module and other application clients remain unchanged.
"""

import sys
from threading import Lock
from typing import Any

import requests

_lock = Lock()


class BoundedSession(requests.Session):
    def send(self, request: requests.PreparedRequest, **kwargs: Any) -> requests.Response:
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = (5, 15)
        return super().send(request, **kwargs)


class BoundedRequests:
    def get(self, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", (5, 15))
        return requests.get(url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", (5, 15))
        return requests.post(url, **kwargs)

    def Session(self) -> BoundedSession:
        return BoundedSession()

    def __getattr__(self, name: str) -> Any:
        return getattr(requests, name)


def bound_provider(prefix: str) -> None:
    with _lock:
        for name, module in list(sys.modules.items()):
            if (
                name.startswith(prefix + ".")
                and module is not None
                and vars(module).get("requests") is requests
            ):
                setattr(module, "requests", BoundedRequests())
