from __future__ import annotations
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from common import ROOT, digest, utcnow
from store import Store

def fetch(request, force=False, ttl=900):
    """Cache successes; on failure keep last good response with explicit stale flag."""
    store=Store()
    key=digest(request)
    cached=store.cache_get(key)
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(cached["saved_at"])).total_seconds() if cached else float("inf")
    if cached and age < ttl and not force:
        return {"data":cached["payload"],"fetched_at":cached["saved_at"],"stale":False,"error":""}
    error=""
    try:
        if os.getenv("ANALYZER_OFFLINE") == "1": raise RuntimeError("오프라인 모드: 외부 자료를 요청하지 않습니다.")
        p=subprocess.run([sys.executable,str(ROOT/"provider_worker.py")],input=json.dumps(request),capture_output=True,text=True,encoding="utf-8",env={**os.environ,"PYTHONIOENCODING":"utf-8"},timeout=65,cwd=ROOT,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        if p.returncode: raise RuntimeError("자료 수집 프로세스 오류")
        data=json.loads(p.stdout)
        kind=request["kind"]
        if kind in ("prices","news"):
            field="rows" if kind=="prices" else "items"
            # Keep each failed symbol's previous data, but propagate stale status.
            missing=[s for s,v in data.items() if not v.get(field)]
            for s in missing:
                old=(cached or {}).get("payload",{}).get(s,{})
                if old.get(field): data[s]=dict(old,error="갱신 실패: 마지막 정상 자료",stale=True)
            if missing: error="일부 자료 미수신: " + ", ".join(missing)
            if not any(v.get(field) for v in data.values()): raise RuntimeError(error or "자료 없음")
        elif not data.get("info") and not data.get("calendar"):
            raise RuntimeError("기업·일정 자료를 받지 못했습니다.")
        if not error: store.cache_put(key,data)
        return {"data":data,"fetched_at":utcnow(),"stale":bool(error),"error":error}
    except subprocess.TimeoutExpired: error="자료 공급처 응답이 65초를 넘었습니다. 다시 조회할 수 있습니다."
    except Exception as exc: error=str(exc)
    return {"data":cached["payload"] if cached else {},"fetched_at":cached["saved_at"] if cached else "", "stale":True,"error":error}
