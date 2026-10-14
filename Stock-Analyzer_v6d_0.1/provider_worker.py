"""Network work runs in a child process so the UI has a hard time limit."""
from __future__ import annotations
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import pandas as pd
import yfinance as yf
from common import DATA_DIR, clean, safe_url, digest, utcnow

def prices(symbol):
    try:
        frame = yf.Ticker(symbol).history(period="2y", auto_adjust=True, timeout=8)
        if frame.empty: return {"error":"시세 자료를 받지 못했습니다.","rows":[]}
        frame = frame[["Open","High","Low","Close","Volume"]].copy()
        frame["Date"] = frame.index.strftime("%Y-%m-%d")
        return {"rows":clean(frame.to_dict("records")),"fetched_at":utcnow(),"source":"Yahoo Finance / yfinance", "adjusted":True}
    except Exception as exc: return {"rows":[],"error":type(exc).__name__}

def news(symbol):
    try:
        rows = []
        for item in yf.Ticker(symbol).get_news(count=12):
            c = item.get("content") or item
            url = c.get("canonicalUrl") or c.get("clickThroughUrl") or item.get("link") or ""
            if isinstance(url,dict): url = url.get("url", "")
            url = safe_url(url)
            title = c.get("title") or ""
            if not title or not url: continue
            published = c.get("pubDate") or item.get("providerPublishTime")
            if isinstance(published,(int,float)): published=datetime.fromtimestamp(published,timezone.utc).isoformat()
            provider = c.get("provider") or {}
            rows.append({"id":digest(url),"title":title,"url":url,"published_at":published or "", "publisher":provider.get("displayName",item.get("publisher","Yahoo Finance")), "symbols":[symbol],"relation":"공급처의 종목별 뉴스 검색 결과"})
        return {"items":rows,"fetched_at":utcnow(),"source":"Yahoo Finance", "error":"" if rows else "조회 결과가 없습니다. 기사 미존재와 공급처 미제공을 구분할 수 없습니다."}
    except Exception as exc: return {"items":[],"error":type(exc).__name__}

def company(symbol):
    ticker = yf.Ticker(symbol)
    result = {"info":{},"calendar":{},"errors":[],"fetched_at":utcnow()}
    try: result["info"] = clean(ticker.get_info() or {})
    except Exception as exc: result["errors"].append("기업 자료: " + type(exc).__name__)
    try: result["calendar"] = clean(ticker.get_calendar() or {})
    except Exception as exc: result["errors"].append("실적 일정: " + type(exc).__name__)
    return result

def main():
    yf.set_tz_cache_location(str(DATA_DIR / "yfinance"))
    # yfinance 0.2.66 initialises these SQLite schemas lazily; do it before threads.
    from yfinance import cache
    cache.get_tz_cache().initialise()
    cache.get_cookie_cache().initialise()
    request=json.loads(sys.stdin.read())
    kind=request["kind"]
    if kind == "prices":
        with ThreadPoolExecutor(max_workers=4) as pool:
            values=list(pool.map(prices,request["symbols"]))
        result=dict(zip(request["symbols"],values))
    elif kind == "news":
        with ThreadPoolExecutor(max_workers=3) as pool:
            values=list(pool.map(news,request["symbols"]))
        result=dict(zip(request["symbols"],values))
    elif kind == "company": result=company(request["symbol"])
    else: raise ValueError("Unknown request kind")
    print(json.dumps(clean(result),ensure_ascii=True,allow_nan=False))

if __name__ == "__main__": main()
