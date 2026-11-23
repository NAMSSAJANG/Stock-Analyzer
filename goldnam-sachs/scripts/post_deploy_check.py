"""Read-only deployed app check (login/logout only mutate the checking session)."""

import argparse
import getpass
import os
from urllib.parse import urlparse

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="배포된 HTTPS 주소")
    parser.add_argument("--live-prices", action="store_true", help="AAPL 실제 시세·분석도 확인")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    if urlparse(base).scheme != "https" or urlparse(base).username:
        raise SystemExit("인증정보가 없는 HTTPS 주소가 필요합니다")
    password = os.getenv("GOLDNAM_CHECK_PASSCODE") or getpass.getpass(
        "앱 비밀번호 (표시되지 않음): "
    )
    with httpx.Client(base_url=base, timeout=90, follow_redirects=False) as client:

        def check(path: str, expected: int = 200) -> httpx.Response:
            response = client.get(path)
            if response.status_code != expected:
                raise SystemExit(f"FAIL {path}: HTTP {response.status_code}")
            if "noindex" not in response.headers.get("x-robots-tag", ""):
                raise SystemExit(f"FAIL {path}: noindex 헤더 없음")
            print(f"PASS {path}: {response.status_code}")
            return response

        health = check("/api/v1/health").json()["data"]
        if not health.get("auth_configured"):
            raise SystemExit("FAIL 로그인 환경변수 미설정")
        check("/api/v1/watchlist", 401)
        check("/", 303)
        check("/login/")
        login = client.post(
            "/api/v1/auth/login", json={"passcode": password}, headers={"Origin": base}
        )
        password = ""
        if login.status_code != 200:
            raise SystemExit(f"FAIL 로그인: HTTP {login.status_code}")
        cookie = login.headers.get("set-cookie", "").lower()
        if not all(flag in cookie for flag in ("httponly", "secure", "samesite=lax")):
            raise SystemExit("FAIL 세션 쿠키 속성")
        for path in [
            "/",
            "/api/v1/auth/session",
            "/api/v1/search?q=AAPL",
            "/api/v1/settings",
            "/api/v1/watchlist",
            "/api/v1/journal",
            "/api/v1/universe/us/scores",
            "/api/v1/validation/us/latest",
            "/manifest-personal.webmanifest",
        ]:
            check(path)
        if args.live_prices:
            check("/api/v1/stocks/AAPL/prices?range=1y")
            check("/api/v1/stocks/AAPL/analysis")
        if client.post("/api/v1/auth/logout", headers={"Origin": base}).status_code != 200:
            raise SystemExit("FAIL 로그아웃")
        check("/api/v1/auth/session", 401)
    print("PASS 완료. 데이터 없음/미검증은 별도로 배치와 소스 설정을 확인하세요.")


if __name__ == "__main__":
    main()
