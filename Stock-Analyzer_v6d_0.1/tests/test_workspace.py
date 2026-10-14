from __future__ import annotations
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
from common import ROOT, normalize_symbol, safe_url, utcnow
from store import Store
from analysis_service import build_analysis, required_symbols, earnings_event

def fixture_response(request):
    if request["kind"]=="company":
        return {"data":{"info":{"shortName":"TEST COMPANY", "currency":"KRW" if request["symbol"].endswith(".KS") else "USD", "sector":"Technology", "revenueGrowth":.22,"earningsGrowth":.28,"operatingMargins":.24,"profitMargins":.18,"returnOnEquity":.26,"debtToEquity":55,"currentRatio":1.6,"trailingPE":28,"forwardPE":24,"priceToBook":5,"totalRevenue":1e11,"freeCashflow":1.5e10},"calendar":{"Earnings Date":[(date.today()+timedelta(days=20)).isoformat()]}},"stale":False,"error":"","fetched_at":"2026-09-12T00:00:00+00:00"}
    if request["kind"]=="news":
        return {"data":{s:{"items":[{"id":"test-news","title":"TEST NEWS — synthetic fixture","url":"https://example.com/article","published_at":"2026-09-12T00:00:00Z","publisher":"TEST","symbols":[s]}]} for s in request["symbols"]},"stale":False,"error":"","fetched_at":"2026-09-12T00:00:00+00:00"}
    rng=np.random.default_rng(42)
    dates=pd.bdate_range(end=date.today(),periods=360)
    close=100*np.exp(np.cumsum(.001+rng.normal(0,.008,360)))
    rows=[{"Date":d.date().isoformat(),"Open":float(c*.998),"High":float(c*1.01),"Low":float(c*.99),"Close":float(c),"Volume":1_500_000} for d,c in zip(dates,close)]
    data={s:{"rows":rows,"fetched_at":"2026-09-12T00:00:00+00:00"} for s in request["symbols"]}
    if "KRW=X" in data:
        data["KRW=X"]={"rows":[dict(r,Open=1300,High=1310,Low=1290,Close=1300) for r in rows]}
    return {"data":data,"stale":False,"error":"","fetched_at":"2026-09-12T00:00:00+00:00"}

def analysis_fixture(symbol="MU"):
    corp=fixture_response({"kind":"company","symbol":symbol})
    prices=fixture_response({"kind":"prices","symbols":required_symbols(symbol,corp["data"]["info"])})
    return build_analysis(symbol,corp,prices)

class PersistenceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/"test.sqlite")
    def tearDown(self): self.temp.cleanup()
    def test_persistence_append_only_and_duplicate(self):
        self.store.save_watch("MU","수요","마진","메모")
        self.assertEqual(Store(self.store.path).watches()[0]["note"],"메모")
        result,inputs,_=analysis_fixture()
        sid=self.store.save_snapshot(result,inputs)
        self.assertEqual(sid,self.store.save_snapshot(result,inputs))
        self.assertEqual(len(self.store.snapshots("MU")),1)
        self.store.decision("MU",sid,"기존 판단 유지")
        with self.assertRaises(ValueError): self.store.decision("NVDA",sid,"잘못 연결")
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store.connect() as db: db.execute("UPDATE snapshots SET symbol='FAIL'")
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store.connect() as db: db.execute("DELETE FROM decisions")
        backup=json.loads(self.store.export())
        self.assertEqual(len(backup["tables"]["inputs"]),1)
    def test_event_range_tracking_persists(self):
        event=earnings_event("MU",{"Earnings Date":["2026-12-15","2026-12-18"]})
        eid=self.store.upsert_event(event); self.store.track(eid)
        self.assertEqual(Store(self.store.path).events()[0]["tracked"],1)
        self.assertEqual(self.store.events()[0]["end_day"],"2026-12-18")
        self.store.track(eid,False)
        self.assertEqual(self.store.events()[0]["tracked"],0)
    def test_symbol_and_url_validation(self):
        self.assertEqual(normalize_symbol("삼성전자"),"005930.KS")
        self.assertEqual(normalize_symbol("247540"),"247540.KQ")
        with self.assertRaises(ValueError): normalize_symbol("123456")
        self.assertEqual(safe_url("javascript:alert(1)"),"")

    def test_refresh_failure_preserves_last_success_and_timestamp(self):
        from common import digest
        from provider import fetch
        import subprocess
        request={"kind":"prices","symbols":["MU"]}
        data=fixture_response(request)["data"]
        self.store.cache_put(digest(request),data)
        before=self.store.cache_get(digest(request))["saved_at"]
        with patch("provider.Store",return_value=self.store),patch("provider.subprocess.run",side_effect=subprocess.TimeoutExpired("test",65)):
            result=fetch(request,force=True)
        self.assertTrue(result["stale"])
        self.assertEqual(result["fetched_at"],before)
        self.assertEqual(result["data"],data)
        self.assertEqual(self.store.cache_get(digest(request))["payload"],data)

class AnalysisTest(unittest.TestCase):
    def test_missing_benchmark_blocks(self):
        corp=fixture_response({"kind":"company","symbol":"MU"})
        prices=fixture_response({"kind":"prices","symbols":["MU"]})
        with self.assertRaisesRegex(ValueError,"기준지수"): build_analysis("MU",corp,prices)
    def test_unknown_event_and_missing_company_are_visible(self):
        corp={"data":{"info":{},"calendar":{}},"stale":True}
        price=fixture_response({"kind":"prices","symbols":required_symbols("MU",{})})
        result,_,_=build_analysis("MU",corp,price)
        self.assertEqual(result["risk"]["earnings"],"미확인")
        self.assertIsNone(result["company"]["score"])
        self.assertEqual(result["state"],"확인 필요")
    def test_korean_liquidity_is_converted_without_changing_technical_prices(self):
        from engine.risk_engine import build_risk_snapshot
        corp=fixture_response({"kind":"company","symbol":"005930.KS"})
        price=fixture_response({"kind":"prices","symbols":required_symbols("005930.KS",corp["data"]["info"])})
        with patch("analysis_service.build_risk_snapshot",wraps=build_risk_snapshot) as risk:
            result,_,_=build_analysis("005930.KS",corp,price)
        self.assertAlmostEqual(risk.call_args.args[0].dollar_volume,result["technical"]["dollar_volume"]/1300)
        del price["data"]["KRW=X"]
        with self.assertRaisesRegex(ValueError,"달러"): build_analysis("005930.KS",corp,price)

class AppFlowTest(unittest.TestCase):
    def test_actual_widgets_and_reopen(self):
        import streamlit as st
        from streamlit.testing.v1 import AppTest
        with tempfile.TemporaryDirectory() as tmp, patch("store.DATA_DIR",Path(tmp)), patch("provider.fetch",side_effect=lambda request,**kw:fixture_response(request)):
            st.cache_data.clear()
            app=AppTest.from_file(str(ROOT/"app.py"),default_timeout=30).run()
            def button(label): return next(x for x in app.button if x.label==label)
            def text(label): return next(x for x in app.text_input if x.label==label)
            self.assertFalse(app.exception)
            app.radio(key="menu").set_value("내 투자").run()
            text("종목명 / 티커").set_value("MU")
            text("관심 이유").set_value("테스트 이유")
            text("다음 확인 질문").set_value("테스트 질문")
            button("관심종목 저장").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(Store(Path(tmp)/"workspace.sqlite").watches()[0]["reason"],"테스트 이유")
            button("종목 분석 →").click().run()
            self.assertEqual(app.radio(key="menu").value,"종목 분석")
            button("실제 자료로 분석 실행").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(Store(Path(tmp)/"workspace.sqlite").snapshots("MU")),1)
            for tab in ["투자 가설","진입 계획","뉴스·근거","판단 변화"]:
                app.radio(key="analysis_view").set_value(tab).run()
                self.assertFalse(app.exception,tab)
            app.radio(key="menu").set_value("일정·이벤트").run()
            button("일정 추적").click().run()
            self.assertEqual(Store(Path(tmp)/"workspace.sqlite").events()[0]["tracked"],1)
            app.radio(key="menu").set_value("후보 찾기").run()
            button("후보 비교 실행").click().run()
            self.assertFalse(app.exception)
            app.radio(key="menu").set_value("기록·검증").run()
            self.assertFalse(app.exception)
            app.radio(key="menu").set_value("오늘의 시장").run()
            app.radio(key="home_view").set_value("시장환경").run()
            self.assertFalse(app.exception)
            text("종목 바로가기").set_value("삼성전자")
            button("종목 열기").click().run()
            self.assertEqual(app.radio(key="menu").value,"종목 분석")
            self.assertEqual(app.session_state.symbol,"005930.KS")
            reopened=AppTest.from_file(str(ROOT/"app.py"),default_timeout=30).run()
            reopened.radio(key="menu").set_value("내 투자").run()
            self.assertFalse(reopened.exception)
            self.assertTrue(any(x.value=="테스트 이유" for x in reopened.text_input))
            reopened.radio(key="menu").set_value("종목 분석").run()
            self.assertFalse(reopened.exception)
            self.assertTrue(reopened.get("plotly_chart"))
            st.cache_data.clear()

    def test_offline_empty_state_does_not_crash(self):
        import streamlit as st
        from streamlit.testing.v1 import AppTest
        failed={"data":{},"stale":True,"error":"TEST unavailable","fetched_at":""}
        with tempfile.TemporaryDirectory() as tmp,patch("store.DATA_DIR",Path(tmp)),patch("provider.fetch",return_value=failed):
            st.cache_data.clear()
            app=AppTest.from_file(str(ROOT/"app.py"),default_timeout=20).run()
            self.assertFalse(app.exception)
            self.assertTrue(app.warning)
            app.radio(key="menu").set_value("종목 분석").run()
            next(x for x in app.button if x.label=="실제 자료로 분석 실행").click().run()
            self.assertTrue(app.error)
            self.assertFalse(app.exception)
            self.assertEqual(Store(Path(tmp)/"workspace.sqlite").snapshots("MU"),[])
            st.cache_data.clear()

if __name__=="__main__": unittest.main()
