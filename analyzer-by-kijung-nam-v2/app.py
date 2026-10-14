import math
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

APP_NAME = "분석기 by kijungnam"
st.set_page_config(page_title=APP_NAME, page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
[data-testid="stHeader"]{background:transparent}.block-container{max-width:1280px;padding-top:1.25rem;padding-bottom:4rem}
.hero{padding:1.3rem 1.4rem;border:1px solid #26354b;border-radius:20px;background:linear-gradient(135deg,#111c2d,#0b1220);margin-bottom:1rem}
.hero h1{font-size:clamp(1.65rem,5vw,2.65rem);margin:0;color:#f8fafc}.hero p{color:#94a3b8;margin:.35rem 0 0}
.pill{display:inline-block;padding:.22rem .58rem;border-radius:99px;background:#123d32;color:#5ee6b1;font-size:.78rem;margin-bottom:.6rem}
.market-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.65rem;margin-bottom:1rem}
.card{min-width:0;min-height:94px;padding:.8rem;border:1px solid #26354b;border-radius:14px;background:#111827}
.name{color:#94a3b8;font-size:.8rem}.value{font-size:1.28rem;font-weight:750;margin:.22rem 0}.up{color:#34d399}.down{color:#fb7185}.muted{color:#94a3b8;font-size:.78rem}
.score{display:flex;align-items:center;justify-content:center;width:116px;height:116px;border-radius:50%;background:conic-gradient(#34d399 var(--p),#26354b 0);margin:auto}
.score:after{content:attr(data-score);display:flex;align-items:center;justify-content:center;width:91px;height:91px;border-radius:50%;background:#0e1726;font-size:1.75rem;font-weight:800}
div[data-testid="stTabs"] button{min-height:48px;white-space:nowrap}.explain{padding:.8rem 1rem;border-left:3px solid #38bdf8;background:#101a2b;border-radius:8px;color:#cbd5e1}
@media(max-width:640px){
  .block-container{padding:1rem .55rem 4rem}.hero{padding:1.05rem}
  .market-grid{grid-template-columns:repeat(4,minmax(0,1fr));gap:.32rem}
  .card{min-height:76px;padding:.48rem .35rem;border-radius:10px;overflow:hidden}
  .card .name{font-size:.64rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .card .value{font-size:.8rem;line-height:1.15;white-space:nowrap;letter-spacing:-.04em}
  .card .up,.card .down{font-size:.67rem;white-space:nowrap}
  .stButton button{min-height:48px}
}
</style>""", unsafe_allow_html=True)

CORE_MARKETS = {
    "원/달러": "KRW=X", "금": "GC=F", "비트코인": "BTC-USD", "이더리움": "ETH-USD",
    "VIX": "^VIX", "달러지수": "DX-Y.NYB", "S&P 500": "^GSPC", "Nasdaq 100": "^NDX"
}
EXTRA_MARKETS = {"WTI 원유": "CL=F", "구리": "HG=F", "하이일드 채권": "HYG"}
TREASURIES = {"3개월": "^IRX", "2년": "^UST2YR", "5년": "^FVX", "10년": "^TNX", "30년": "^TYX"}

@st.cache_data(ttl=300, show_spinner=False)
def snapshots(mapping):
    out = {}
    for name, symbol in mapping.items():
        try:
            h = yf.Ticker(symbol).history(period="7d", auto_adjust=True)
            c = h.Close.dropna(); value=float(c.iloc[-1]); prev=float(c.iloc[-2])
            out[name] = (value, (value/prev-1)*100)
        except Exception: out[name] = (None, None)
    return out

@st.cache_data(ttl=600, show_spinner=False)
def stock_data(symbol):
    t=yf.Ticker(symbol); h=t.history(period="2y", auto_adjust=True)
    if h.empty: raise ValueError("가격 데이터를 찾을 수 없습니다. 티커를 확인해 주세요.")
    try: info=t.info or {}
    except Exception: info={}
    for n in (5,10,20,50,200): h[f"MA{n}"]=h.Close.rolling(n).mean()
    d=h.Close.diff(); gain=d.clip(lower=0).rolling(14).mean(); loss=-d.clip(upper=0).rolling(14).mean()
    h["RSI"]=100-100/(1+gain/loss.replace(0,np.nan))
    ema12=h.Close.ewm(span=12,adjust=False).mean(); ema26=h.Close.ewm(span=26,adjust=False).mean()
    h["MACD"]=ema12-ema26; h["SIGNAL"]=h.MACD.ewm(span=9,adjust=False).mean()
    h["VOL20"]=h.Volume.rolling(20).mean(); h["STD20"]=h.Close.rolling(20).std()
    h["BB_UP"]=h.MA20+2*h.STD20; h["BB_LOW"]=h.MA20-2*h.STD20
    tr=pd.concat([(h.High-h.Low),(h.High-h.Close.shift()).abs(),(h.Low-h.Close.shift()).abs()],axis=1).max(axis=1)
    h["ATR"]=tr.rolling(14).mean()
    return h,info

@st.cache_data(ttl=600, show_spinner=False)
def relative_strength(symbol):
    benchmark="^KS11" if symbol.endswith((".KS",".KQ")) else "^GSPC"
    try:
        data=yf.download([symbol,benchmark],period="6mo",auto_adjust=True,progress=False,group_by="ticker",threads=True)
        stock=data[symbol]["Close"].dropna(); market=data[benchmark]["Close"].dropna()
        days=min(63,len(stock)-1,len(market)-1)
        if days<20:return None,benchmark
        stock_ret=(stock.iloc[-1]/stock.iloc[-days]-1)*100; market_ret=(market.iloc[-1]/market.iloc[-days]-1)*100
        return float(stock_ret-market_ret),benchmark
    except Exception:return None,benchmark

def clamp(v): return float(np.clip(v,0,100))
def safe_num(v, default=None): return float(v) if isinstance(v,(int,float)) and math.isfinite(v) else default
def pct_return(s, days): return (float(s.iloc[-1]/s.iloc[-days]-1)*100) if len(s)>=days else 0

def smooth_score(value, scale):
    """연속값을 5~95 범위 점수로 변환해 경계값 점프를 방지합니다."""
    return clamp(50 + 45*np.tanh(value/scale))

def support_resistance(hist):
    """스윙 가격·거래량·이동평균을 ATR 폭으로 군집화해 가격 구간을 만듭니다."""
    h=hist.tail(300).copy(); p=float(h.Close.iloc[-1]); atr=safe_num(h.ATR.iloc[-1],p*.025)
    candidates=[]; window=5
    highs=h.High.to_numpy(); lows=h.Low.to_numpy(); volumes=h.Volume.to_numpy(); avg_vol=max(float(h.Volume.tail(20).mean()),1)
    for i in range(window,len(h)-window):
        recency=.55+.45*(i/len(h)); vol_weight=min(max(volumes[i]/avg_vol,0),3)/3
        if highs[i]>=np.max(highs[i-window:i+window+1]): candidates.append((float(highs[i]),1.25*recency+.55*vol_weight,"스윙 고점"))
        if lows[i]<=np.min(lows[i-window:i+window+1]): candidates.append((float(lows[i]),1.25*recency+.55*vol_weight,"스윙 저점"))
    last=h.iloc[-1]
    for key,weight in (("MA20",1.0),("MA50",1.15),("MA200",1.35)):
        v=safe_num(last.get(key))
        if v: candidates.append((v,weight,key))
    if not candidates: return {"supports":[],"resistances":[],"current":None,"atr":atr,"atr_pct":atr/p*100}
    tolerance=max(atr*.65,p*.006); clusters=[]
    for price,weight,reason in sorted(candidates):
        if clusters and abs(price-clusters[-1]["center"])<=tolerance:
            c=clusters[-1]; total=c["weight"]+weight; c["center"]=(c["center"]*c["weight"]+price*weight)/total; c["weight"]=total; c["reasons"].append(reason); c["touches"]+=1
        else: clusters.append({"center":price,"weight":weight,"reasons":[reason],"touches":1})
    zones=[]
    for c in clusters:
        band=max(atr*.28,c["center"]*.0035); strength=clamp(18+c["weight"]*11+c["touches"]*4)
        zones.append({"center":c["center"],"low":c["center"]-band,"high":c["center"]+band,"score":round(strength),"reasons":list(dict.fromkeys(c["reasons"]))[:4],"distance":(c["center"]/p-1)*100})
    supports=sorted([z for z in zones if z["center"]<p],key=lambda z:z["center"],reverse=True)[:4]
    resistances=sorted([z for z in zones if z["center"]>=p],key=lambda z:z["center"])[:4]
    near=sorted(zones,key=lambda z:abs(z["center"]-p))[0]; current=near if near["low"]-atr*.15<=p<=near["high"]+atr*.15 else None
    return {"supports":supports,"resistances":resistances,"current":current,"atr":atr,"atr_pct":atr/p*100}

def analyze(hist,info):
    x=hist.iloc[-1]; p=float(x.Close); rsi=safe_num(x.RSI,50)
    ma50_slope=float(hist.MA50.iloc[-1]/hist.MA50.iloc[-21]-1) if pd.notna(hist.MA50.iloc[-21]) else 0
    ma200_slope=float(hist.MA200.iloc[-1]/hist.MA200.iloc[-21]-1) if pd.notna(hist.MA200.iloc[-21]) else 0
    long_parts=[smooth_score(p/x.MA200-1,.12),smooth_score(x.MA50/x.MA200-1,.08),smooth_score(ma50_slope,.05),smooth_score(ma200_slope,.025),smooth_score(pct_return(hist.Close,126)/100,.25),smooth_score(pct_return(hist.Close,252)/100,.40)]
    long_score=float(np.average(long_parts,weights=[22,18,18,12,15,15]))
    ma20_slope=float(hist.MA20.iloc[-1]/hist.MA20.iloc[-11]-1) if pd.notna(hist.MA20.iloc[-11]) else 0
    short_parts=[smooth_score(p/x.MA20-1,.06),smooth_score(x.MA5/x.MA20-1,.04),smooth_score(ma20_slope,.045),smooth_score((x.MACD-x.SIGNAL)/p,.012),smooth_score(pct_return(hist.Close,20)/100,.12)]
    short_score=float(np.average(short_parts,weights=[25,15,20,20,20]))
    momentum=clamp(100-abs(rsi-58)*2)
    vol_ratio=safe_num(x.Volume/x.VOL20,1); volume=clamp(50+(vol_ratio-1)*35)
    atr_pct=safe_num(x.ATR/p,0.03)*100; volatility=clamp(90-atr_pct*8)
    technical=.35*long_score+.25*short_score+.20*momentum+.10*volume+.10*volatility
    roe=safe_num(info.get("returnOnEquity")); margin=safe_num(info.get("operatingMargins")); debt=safe_num(info.get("debtToEquity")); growth=safe_num(info.get("revenueGrowth")); pe=safe_num(info.get("forwardPE"))
    profitability=np.mean([50 if roe is None else clamp(50+roe*100),50 if margin is None else clamp(50+margin*120)])
    growth_score=50 if growth is None else clamp(50+growth*150)
    health=50 if debt is None else clamp(90-debt/2)
    valuation=50 if pe is None else clamp(100-pe*2) if pe>0 else 35
    fundamental=.30*profitability+.25*growth_score+.25*health+.20*valuation
    overall=.45*fundamental+.55*technical
    horizon_short=.55*short_score+.25*momentum+.20*volume
    horizon_mid=.45*short_score+.35*long_score+.20*fundamental
    horizon_long=.55*fundamental+.45*long_score
    fields=[roe,margin,debt,growth,pe]; confidence=round(55+45*sum(v is not None for v in fields)/len(fields))
    ma_gap=(p/x.MA20-1)*100; positive=[]; caution=[]
    (positive if long_score>=55 else caution).append(f"장기 추세 {level(long_score)} ({long_score:.0f}점)")
    (positive if short_score>=55 else caution).append(f"단기 추세 {level(short_score)} ({short_score:.0f}점)")
    (positive if fundamental>=60 else caution).append(f"펀더멘털 {level(fundamental)} ({fundamental:.0f}점)")
    if rsi>=70: caution.append(f"RSI {rsi:.1f}: 과열 가능성")
    elif rsi<=30: caution.append(f"RSI {rsi:.1f}: 과매도 상태에서도 하락 지속 가능")
    else: positive.append(f"RSI {rsi:.1f}: 중립 범위")
    if vol_ratio>=1.3: positive.append(f"거래량이 20일 평균의 {vol_ratio:.1f}배")
    return {"overall":round(overall),"fundamental":round(fundamental),"technical":round(technical),"long":round(long_score),"short":round(short_score),"momentum":round(momentum),"volume":round(volume),"volatility":round(volatility),"profitability":round(profitability),"growth":round(growth_score),"health":round(health),"valuation":round(valuation),"rsi":rsi,"confidence":confidence,"ma_gap":ma_gap,"positive":positive[:4],"caution":caution[:4],"horizon_short":round(horizon_short),"horizon_mid":round(horizon_mid),"horizon_long":round(horizon_long)}

def macro_score(m):
    def val(k): return m.get(k,(None,None))[0]
    def chg(k): return m.get(k,(None,None))[1]
    parts=[]; reasons=[]; risks=[]
    vix=val("VIX")
    if vix is not None:
        s=85 if vix<15 else 70 if vix<20 else 50 if vix<25 else 30 if vix<35 else 15; parts.append(s)
        (reasons if vix<20 else risks).append(f"VIX {vix:.1f}: " + ("변동성 안정" if vix<20 else "시장 경계심 확대"))
    for key in ("S&P 500","Nasdaq 100"):
        c=chg(key)
        if c is not None: parts.append(clamp(50+c*12)); (reasons if c>=0 else risks).append(f"{key} 당일 {c:+.2f}%")
    dxy=chg("달러지수")
    if dxy is not None: parts.append(clamp(50-dxy*10)); (risks if dxy>0.3 else reasons).append(f"달러지수 {dxy:+.2f}%")
    score=round(np.mean(parts)) if parts else 50
    return score,reasons[:3],risks[:3]

def fmt(v,kind="number"):
    if v is None or not isinstance(v,(int,float)) or not math.isfinite(v): return "—"
    if kind=="pct": return f"{v*100:.1f}%"
    if kind=="money": return f"${v:,.2f}"
    if kind=="large":
        for n,s in ((1e12,"T"),(1e9,"B"),(1e6,"M")):
            if abs(v)>=n:return f"{v/n:.2f}{s}"
    return f"{v:,.2f}"
def level(s): return "강함" if s>=80 else "양호" if s>=65 else "중립" if s>=45 else "약함" if s>=30 else "매우 약함"
def strength_label(s): return "매우 강함" if s>=80 else "강함" if s>=65 else "보통" if s>=45 else "약함"

st.markdown(f'<section class="hero"><span class="pill">V2.1 · PRICE ZONES</span><h1>{APP_NAME}</h1><p>매크로 환경, 기업가치, 장·단기 추세와 지지·저항 구간을 함께 확인하세요.</p></section>',unsafe_allow_html=True)

with st.spinner("시장 환경을 확인하고 있습니다…"):
    core=snapshots(CORE_MARKETS); treasury=snapshots(TREASURIES); extra=snapshots(EXTRA_MARKETS)
macro,reasons,risks=macro_score(core)

st.subheader("시장 환경")
market_cards=[]
for name in CORE_MARKETS:
    v,ch=core[name]; css="up" if (ch or 0)>=0 else "down"
    if name=="원/달러": txt="—" if v is None else f"₩{v:,.2f}"
    elif name in ("비트코인","이더리움"): txt="—" if v is None else f"${v:,.0f}"
    else: txt=fmt(v)
    delta="데이터 없음" if ch is None else f"{ch:+.2f}%"
    market_cards.append(f'<div class="card"><div class="name">{name}</div><div class="value">{txt}</div><div class="{css}">{delta}</div></div>')
st.markdown('<div class="market-grid">'+''.join(market_cards)+'</div>',unsafe_allow_html=True)

with st.expander("미국채 금리·원자재·신용시장 보기",expanded=False):
    st.markdown("#### 미국채 만기별 금리")
    cs=st.columns(5); curve_x=[]; curve_y=[]
    for c,name in zip(cs,TREASURIES):
        v,ch=treasury[name]; c.metric(name,"—" if v is None else f"{v:.2f}%",None if ch is None else f"{ch:+.2f}%")
        if v is not None: curve_x.append(name); curve_y.append(v)
    if curve_y:
        f=go.Figure(go.Scatter(x=curve_x,y=curve_y,mode="lines+markers",line=dict(color="#38bdf8",width=3)))
        f.update_layout(height=270,margin=dict(l=10,r=10,t=20,b=10),template="plotly_dark",yaxis_title="수익률 (%)")
        st.plotly_chart(f,use_container_width=True,config={"displayModeBar":False})
    cs=st.columns(3)
    for c,name in zip(cs,EXTRA_MARKETS):
        v,ch=extra[name]; c.metric(name,fmt(v),None if ch is None else f"{ch:+.2f}%")

mc1,mc2=st.columns([1,3]); mc1.metric("매크로 환경점수",f"{macro}/100",level(macro))
with mc2:
    pos=" · ".join(reasons) or "뚜렷한 긍정 신호 없음"; neg=" · ".join(risks) or "뚜렷한 위험 신호 없음"
    st.markdown(f'<div class="explain"><b>긍정 요인</b> {pos}<br><b>주의 요인</b> {neg}<br><span class="muted">매크로 점수는 종목 종합점수와 분리된 참고지표입니다.</span></div>',unsafe_allow_html=True)

st.divider()
with st.form("search"):
    a,b=st.columns([4,1]); symbol=a.text_input("종목 티커",value=st.session_state.get("symbol","AAPL"),placeholder="AAPL, NVDA, 005930.KS").strip().upper(); submit=b.form_submit_button("분석하기",use_container_width=True)
if submit: st.session_state.symbol=symbol
symbol=st.session_state.get("symbol",symbol)

try:
    with st.spinner("종목을 분석하고 있습니다…"): hist,info=stock_data(symbol); s=analyze(hist,info); zones=support_resistance(hist); relative,benchmark=relative_strength(symbol)
    p=float(hist.Close.iloc[-1]); prev=float(hist.Close.iloc[-2]); change=(p/prev-1)*100
    signal="적극 매수" if s["overall"]>=80 else "매수 우위" if s["overall"]>=65 else "중립" if s["overall"]>=45 else "주의"
    l,r=st.columns([3,1])
    with l:
        st.subheader(f"{info.get('shortName') or symbol} · {symbol}"); st.markdown(f"### {fmt(p,'money')} <span class={'up' if change>=0 else 'down'}>{change:+.2f}%</span>",unsafe_allow_html=True)
        st.caption(f"{info.get('exchange','')} · {datetime.now().strftime('%Y-%m-%d')} · 지연 데이터일 수 있음")
    r.markdown(f'<div class="score" style="--p:{s["overall"]}%" data-score="{s["overall"]}"></div><p style="text-align:center;margin:.45rem 0">{signal}</p>',unsafe_allow_html=True)

    tabs=st.tabs(["종합 분석","장·단기 추세","지지·저항","차트","재무·밸류","매크로 영향"])
    with tabs[0]:
        cs=st.columns(4); cs[0].metric("종합점수",f'{s["overall"]}/100',level(s["overall"])); cs[1].metric("펀더멘털",f'{s["fundamental"]}/100',level(s["fundamental"])); cs[2].metric("테크니컬",f'{s["technical"]}/100',level(s["technical"])); cs[3].metric("RSI (14)",f'{s["rsi"]:.1f}')
        st.markdown(f'<div class="explain"><b>종합점수 해석</b><br>펀더멘털 45%와 테크니컬 55%를 결합했습니다. 현재 평가는 <b>{signal}</b>입니다.<br><br><b>펀더멘털</b><br>수익성·성장성·재무건전성·밸류에이션을 평가한 기업 기초체력 점수입니다.<br><br><b>테크니컬</b><br>장·단기 추세, 모멘텀, 거래량과 변동성 안정성을 평가합니다.<br><br><b>RSI 해석</b><br>'+ ("70 이상으로 단기 과열 가능성이 있습니다. 강한 상승장에서는 높은 RSI가 지속될 수 있습니다." if s["rsi"]>=70 else "30 이하로 과매도 가능성이 있습니다. 반등을 보장하는 신호는 아닙니다." if s["rsi"]<=30 else "30~70 사이의 중립 범위입니다.")+'</div>',unsafe_allow_html=True)
        pc,nc=st.columns(2)
        with pc:
            st.markdown("#### 긍정 요인")
            for item in s["positive"]: st.success(item)
        with nc:
            st.markdown("#### 주의 요인")
            if s["caution"]:
                for item in s["caution"]: st.warning(item)
            else: st.info("현재 계산상 뚜렷한 주의 요인이 없습니다.")
        st.markdown("#### 투자기간별 참고")
        hc=st.columns(3); hc[0].metric("단기 관점",f'{s["horizon_short"]}/100',level(s["horizon_short"])); hc[1].metric("중기 관점",f'{s["horizon_mid"]}/100',level(s["horizon_mid"])); hc[2].metric("장기 관점",f'{s["horizon_long"]}/100',level(s["horizon_long"]))
        if relative is not None: st.metric("최근 3개월 시장 대비 상대강도",f"{relative:+.2f}%",f"기준: {benchmark}")
        else: st.caption("시장 대비 상대강도 데이터를 불러오지 못했습니다.")
        st.caption("모든 점수는 공개 데이터 기반 참고지표이며 투자 권유가 아닙니다.")
    with tabs[1]:
        c1,c2=st.columns(2)
        with c1:
            st.metric("장기 추세",f'{s["long"]}/100',level(s["long"])); st.write("50·200일선의 이격과 기울기, 6개월·12개월 수익률을 연속형으로 반영합니다.")
            st.info("점수가 50에 가까우면 방향이 불분명하며, 65 이상은 상승 우위, 35 이하는 하락 우위로 해석합니다.")
        with c2:
            st.metric("단기 추세",f'{s["short"]}/100',level(s["short"])); st.write("이동평균선 이격도·기울기, MACD와 20일 수익률을 연속형으로 반영합니다.")
            st.info(f'현재가는 20일선 대비 {s["ma_gap"]:+.2f}%입니다. 단기 추세는 장기 추세와 반대일 수 있습니다.')
        st.markdown("#### 테크니컬 세부점수"); cs=st.columns(5)
        for c,(k,n) in zip(cs,[("long","장기 추세"),("short","단기 추세"),("momentum","모멘텀"),("volume","거래량"),("volatility","변동성 안정성")]): c.metric(n,f'{s[k]}/100')
    with tabs[2]:
        st.markdown("#### 현재 테스트 구간")
        current=zones["current"]
        if current:
            st.warning(f'{fmt(current["low"],"money")} ~ {fmt(current["high"],"money")} · 강도 {strength_label(current["score"])} ({current["score"]}점) · '+" · ".join(current["reasons"]))
        else: st.info("현재가는 계산된 주요 지지·저항 구간 사이에 있습니다.")
        left_z,right_z=st.columns(2)
        def show_zone(container,title,data,color):
            with container:
                st.markdown(f"#### {title}")
                if not data: st.caption("표시할 구간이 없습니다.")
                for i,z in enumerate(data,1):
                    zone_text=(f'**{i}차 {title}** · {fmt(z["low"],"money")} ~ {fmt(z["high"],"money")}  \n'
                               f'현재가 대비 {z["distance"]:+.2f}% · 강도 {strength_label(z["score"])} ({z["score"]}점)  \n'
                               f'근거: {" · ".join(z["reasons"])}')
                    st.markdown(zone_text)
        show_zone(left_z,"지지",zones["supports"],"green"); show_zone(right_z,"저항",zones["resistances"],"red")
        support=zones["supports"][0] if zones["supports"] else None; resistance=zones["resistances"][0] if zones["resistances"] else None
        st.markdown("#### 대응 시나리오")
        if resistance: st.success(f'상방 돌파 확인: {fmt(resistance["high"],"money")} 위 일봉 종가 안착과 거래량 증가 여부를 함께 확인합니다.')
        if support:
            st.info(f'지지 확인: {fmt(support["low"],"money")} ~ {fmt(support["high"],"money")}에서 종가 회복과 반전 여부를 확인합니다.')
            st.error(f'지지 무효화 참고: {fmt(support["low"],"money")} 아래 일봉 마감 시 다음 지지구간을 확인합니다.')
        st.caption(f'ATR(14): {fmt(zones["atr"],"money")} · 현재가 대비 {zones["atr_pct"]:.2f}%. 구간은 ATR과 최근 가격 구조에 따라 달라집니다.')
    with tabs[3]:
        v=hist.tail(252); fig=make_subplots(rows=3,cols=1,shared_xaxes=True,row_heights=[.62,.18,.20],vertical_spacing=.035)
        fig.add_trace(go.Candlestick(x=v.index,open=v.Open,high=v.High,low=v.Low,close=v.Close,name="가격"),row=1,col=1)
        for k,color in [("MA20","#38bdf8"),("MA50","#f59e0b"),("MA200","#a78bfa")]: fig.add_trace(go.Scatter(x=v.index,y=v[k],name=k,line=dict(width=1.3,color=color)),row=1,col=1)
        fig.add_trace(go.Bar(x=v.index,y=v.Volume,name="거래량",marker_color="#475569"),row=2,col=1)
        fig.add_trace(go.Scatter(x=v.index,y=v.RSI,name="RSI",line=dict(color="#34d399")),row=3,col=1)
        for z in zones["supports"][:3]: fig.add_hrect(y0=z["low"],y1=z["high"],fillcolor="#22c55e",opacity=.10,line_width=0,row=1,col=1)
        for z in zones["resistances"][:3]: fig.add_hrect(y0=z["low"],y1=z["high"],fillcolor="#ef4444",opacity=.10,line_width=0,row=1,col=1)
        fig.add_hline(y=70,line_dash="dot",line_color="#fb7185",row=3,col=1); fig.add_hline(y=30,line_dash="dot",line_color="#38bdf8",row=3,col=1)
        fig.update_layout(height=690,margin=dict(l=8,r=8,t=25,b=8),xaxis_rangeslider_visible=False,legend_orientation="h",template="plotly_dark")
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False,"responsive":True})
    with tabs[4]:
        st.markdown("#### 펀더멘털 세부점수"); cs=st.columns(4)
        for c,(k,n) in zip(cs,[("profitability","수익성"),("growth","성장성"),("health","재무건전성"),("valuation","밸류에이션")]): c.metric(n,f'{s[k]}/100',level(s[k]))
        items=[("시가총액",fmt(info.get("marketCap"),"large")),("Forward P/E",fmt(info.get("forwardPE"))),("P/S",fmt(info.get("priceToSalesTrailing12Months"))),("영업이익률",fmt(info.get("operatingMargins"),"pct")),("ROE",fmt(info.get("returnOnEquity"),"pct")),("부채비율",fmt(info.get("debtToEquity"))),("매출성장률",fmt(info.get("revenueGrowth"),"pct")),("목표주가",fmt(info.get("targetMeanPrice"),"money"))]
        for i in range(0,8,4):
            cs=st.columns(4)
            for c,(n,v) in zip(cs,items[i:i+4]): c.metric(n,v)
        st.metric("펀더멘털 데이터 신뢰도",f'{s["confidence"]}%')
        st.caption("신뢰도는 핵심 재무항목의 데이터 완성도를 뜻합니다. 자료가 없는 항목은 중립값 50점으로 처리됩니다.")
    with tabs[5]:
        sector=info.get("sector") or "업종 정보 없음"; st.metric("현재 매크로 환경",f"{macro}/100",level(macro)); st.write(f"분석 종목 업종: **{sector}**")
        if sector in ("Technology","Communication Services","Consumer Cyclical"):
            text="성장주 성격이 강한 업종은 미국 장기금리와 달러 강세에 상대적으로 민감할 수 있습니다. VIX와 Nasdaq 흐름도 함께 확인하세요."
        elif sector=="Financial Services": text="금융주는 기준금리뿐 아니라 장단기 금리차, 신용위험과 경기 흐름을 함께 확인해야 합니다."
        elif sector in ("Energy","Basic Materials"): text="원유·구리 등 원자재 가격과 달러지수, 글로벌 경기 흐름의 영향을 크게 받을 수 있습니다."
        else: text="현재 매크로 점수는 시장 전반의 위험선호 환경을 나타냅니다. 종목 고유의 경쟁력과 별도로 참고하세요."
        st.info(text); st.warning("V2의 매크로 점수는 종합점수에 직접 합산하지 않습니다. 개별 종목 판단을 보완하는 참고자료입니다.")
except Exception as e:
    st.error(f"{symbol} 분석을 불러오지 못했습니다: {e}"); st.info("미국 종목은 AAPL, 한국 종목은 005930.KS처럼 입력해 보세요.")
