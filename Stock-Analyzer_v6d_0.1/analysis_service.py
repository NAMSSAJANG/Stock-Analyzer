from __future__ import annotations
from dataclasses import asdict, replace
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pandas as pd
from common import ENGINE_VERSION, VERSION, clean, digest, utcnow
from engine.company_engine import build_company_snapshot
from engine.technical_engine import build_technical_snapshot
from engine.market_regime import build_market_regime, market_for_symbol, US_SECTOR_PROXY, KR_GLOBAL_PROXY
from engine.opportunity_engine import build_opportunity
from engine.sr_engine import build_zones
from engine.setup_engine import build_setups
from engine.risk_engine import build_risk_snapshot
from engine.consensus_engine import build_consensus_v2

def frame_of(payload):
    rows=payload.get("rows",[]) if payload else []
    if not rows: return pd.DataFrame()
    frame=pd.DataFrame(rows)
    frame["Date"]=pd.to_datetime(frame["Date"])
    frame=frame.set_index("Date").sort_index()
    frame=frame.loc[~frame.index.duplicated(keep="last")]
    for col in ["Open","High","Low","Close","Volume"]: frame[col]=pd.to_numeric(frame[col],errors="coerce")
    frame=frame.dropna(subset=["Open","High","Low","Close","Volume"])
    return frame[(frame.Close>0)&(frame.High>=frame.Low)&(frame.Volume>=0)]

def required_symbols(symbol, info):
    sector=str(info.get("sector","")).lower()
    if market_for_symbol(symbol)=="KR":
        symbols=[symbol,"^KS11","^KQ11","^NDX","HYG","KRW=X","^VIX",KR_GLOBAL_PROXY.get(sector,"^GSPC")]
        if "semi" in sector: symbols.append("^SOX")
    else:
        symbols=[symbol,"^GSPC","^NDX","HYG",US_SECTOR_PROXY.get(sector,"SPY"),"^VIX","DX-Y.NYB","LQD"]
    return list(dict.fromkeys(symbols))

def earnings_event(symbol, calendar):
    raw=calendar.get("Earnings Date") or calendar.get("EarningsDate") or []
    if not isinstance(raw,list): raw=[raw]
    dates=[]
    for value in raw:
        try:
            day=pd.Timestamp(value).date().isoformat()
            if day not in dates: dates.append(day)
        except (ValueError,TypeError): continue
    if not dates: return None
    dates.sort()
    return {"id":digest({"symbol":symbol,"earnings_start":dates[0]}),"symbol":symbol,"title":f"{symbol} 실적 발표", "day":dates[0],"end_day":dates[-1],"kind":"실적", "source":f"https://finance.yahoo.com/quote/{symbol}/calendar/", "status":"공급처 예정 범위 · 시각 미확인" if len(dates)>1 else "공급처 예정일 · 시각 미확인", "question":"매출·마진·가이던스가 기존 가정과 일치하는가?", "origin":"Yahoo Finance"}

def build_analysis(symbol, company_response, price_response, evaluated_day=None):
    data=price_response.get("data",{})
    frames={s:frame_of(p) for s,p in data.items()}
    frame=frames.get(symbol,pd.DataFrame())
    if len(frame)<210: raise ValueError("분석에는 정상 가격 자료가 최소 210거래일 필요합니다. 공급처 상태와 종목코드를 확인하세요.")
    region=market_for_symbol(symbol)
    cutoff=frame.index[-1]
    frames={s:f.loc[f.index<=cutoff] for s,f in frames.items() if not f.empty}
    benchmark=frames.get("^KS11" if region=="KR" else "^GSPC",pd.DataFrame())
    if len(benchmark)<55: raise ValueError("시장 기준지수 자료가 부족해 상대강도와 종합 분석을 보류합니다.")
    company_data=company_response.get("data",{})
    info=company_data.get("info",{})
    event=earnings_event(symbol,company_data.get("calendar",{}))
    today=pd.Timestamp(evaluated_day).date() if evaluated_day else datetime.now(ZoneInfo("Asia/Seoul")).date()
    days=(pd.Timestamp(event["day"]).date()-today).days if event else None
    if days is not None and days<0: days=None
    warnings=[]
    if company_response.get("stale"): warnings.append("기업 자료 갱신 미확인")
    if price_response.get("stale"): warnings.append("가격·시장 자료 일부 갱신 미확인")
    if (today-cutoff.date()).days>7: warnings.append("종목 가격 기준일이 7일 이상 지났습니다")
    if days is None: warnings.append("다가오는 실적 일정 미확인")
    if event and event["day"]!=event["end_day"]: warnings.append("실적 발표일이 범위로 제공됨")
    def loader(ticker, period="2y"):
        f=frames.get(ticker,pd.DataFrame())
        if len(f)<60: return pd.DataFrame()
        return f
    market=build_market_regime(symbol,info.get("sector",""),loader,as_of=cutoff.date())
    if market.data_quality==0: raise ValueError("시장환경 자료를 확보하지 못했습니다.")
    if market.data_quality<1: warnings.append("시장환경 구성 자료 일부 누락")
    tech=build_technical_snapshot(frame,benchmark)
    risk_tech=tech
    currency=info.get("currency") or ("KRW" if region=="KR" else "USD")
    if region=="KR":
        fx=frames.get("KRW=X",pd.DataFrame())
        if fx.empty or float(fx.Close.iloc[-1])<=0: raise ValueError("한국 종목 거래대금의 달러 환산에 필요한 원·달러 자료가 없습니다.")
        risk_tech=replace(tech,dollar_volume=tech.dollar_volume/float(fx.Close.iloc[-1]))
    elif currency!="USD": raise ValueError("이번 버전은 미국 USD·한국 KRW 종목을 지원합니다.")
    company=build_company_snapshot(info)
    if company.coverage<0.6: warnings.append("기업 평가 자료 충족도 60% 미만")
    risk=build_risk_snapshot(risk_tech,market,days)
    if days is None:
        risk=replace(risk,earnings="미확인",details={**risk.details,"Earnings":"미확인 · 기존 위험점수에는 기본값이 포함됩니다"})
    zones=build_zones(frame,tech)
    setups=build_setups(float(frame.Close.iloc[-1]),tech,market,zones,risk)
    opportunity=build_opportunity(company,tech,market)
    consensus=build_consensus_v2(company,tech,setups,market,None,None)
    state="확인 필요" if warnings else "조건 관찰"
    result=clean({"version":VERSION,"engine_version":ENGINE_VERSION,"symbol":symbol,"name":info.get("shortName",symbol),"currency":currency,"observed_at":utcnow(),"price_date":cutoff.date().isoformat(),"price":float(frame.Close.iloc[-1]),"state":state,"warnings":warnings,"company":asdict(company),"technical":asdict(tech),"market":asdict(market),"risk":asdict(risk),"setups":asdict(setups),"opportunity":asdict(opportunity),"consensus":asdict(consensus),"event":event,"scope":"현재 조회 자료의 분석. 동종기업 상대평가·옵션 미연결. 가격은 배당·분할 조정 일봉이며 장중에는 미완성 일봉이 포함될 수 있습니다.","evaluated_day":today.isoformat()})
    inputs={"symbol":symbol,"company_response":company_response,"price_response":price_response,"evaluated_day":today.isoformat()}
    return result,inputs,frame

def changes(previous, current):
    specs=[("기업","company","score"),("추세","technical","trend"),("상대강도","technical","relative_strength"),("시장환경","market","score"),("위험","risk","score")]
    rows=[]
    for name,group,key in specs:
        before=previous.get(group,{}).get(key); after=current.get(group,{}).get(key)
        rows.append({"항목":name,"이전":before,"현재":after,"변화":round(after-before,2) if before is not None and after is not None else None})
    return rows

