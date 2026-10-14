from __future__ import annotations
import hashlib
import json
import math
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

VERSION = "v-6d_0.1"
ENGINE_VERSION = "v6.0.22-baseline+d01-adapter1"
ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("ANALYZER_DATA_DIR", str(ROOT / ".data")))
NAMES = {"MU":"마이크론", "NVDA":"엔비디아", "MSFT":"마이크로소프트", "AAPL":"애플", "AMD":"AMD", "GOOGL":"알파벳", "005930.KS":"삼성전자", "000660.KS":"SK하이닉스", "005380.KS":"현대차", "035420.KS":"NAVER", "105560.KS":"KB금융", "247540.KQ":"에코프로비엠"}
MENUS = ["오늘의 시장", "후보 찾기", "종목 분석", "일정·이벤트", "내 투자", "기록·검증"]

def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def normalize_symbol(value):
    value = str(value).strip().upper()
    for symbol, name in NAMES.items():
        if value == name.upper():
            return symbol
    if re.fullmatch(r"\d{6}", value):
        known = [s for s in NAMES if s.startswith(value + ".")]
        if known:
            return known[0]
        raise ValueError("한국 종목은 거래소까지 입력하세요. 예: 005930.KS / 247540.KQ")
    if not re.fullmatch(r"(?:[A-Z][A-Z0-9.-]{0,14}|\d{6}\.(?:KS|KQ))", value):
        raise ValueError("미국 티커 또는 한국 종목코드.KS/.KQ를 입력하세요.")
    return value

def safe_url(value):
    value = str(value or "")
    p = urlparse(value)
    return value if p.scheme in ("https", "http") and p.netloc and not p.username else ""

def clean(value):
    if isinstance(value, dict): return {str(k): clean(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if isinstance(value, (datetime, date)): return value.isoformat()
    if hasattr(value, "item"): return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value): return None
    return value

def dumps(value):
    return json.dumps(clean(value), ensure_ascii=False, sort_keys=True, allow_nan=False)

def digest(value):
    return hashlib.sha256(dumps(value).encode("utf-8")).hexdigest()

