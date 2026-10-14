import math
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="분석기 by Kijung Nam V1", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
  [data-testid="stHeader"] {background: transparent}
  .block-container {max-width: 1240px; padding-top: 1.4rem; padding-bottom: 4rem}
  .hero {padding:1.3rem 1.4rem;border:1px solid #26354b;border-radius:20px;background:linear-gradient(135deg,#111c2d,#0b1220);margin-bottom:1rem}
  .hero h1 {font-size:clamp(1.7rem,5vw,2.7rem);margin:0;color:#f8fafc}
  .hero p {color:#94a3b8;margin:.35rem 0 0}
  .pill {display:inline-block;padding:.22rem .58rem;border-radius:99px;background:#123d32;color:#5ee6b1;font-size:.78rem;margin-bottom:.6rem}
  .metric-card {min-height:112px;padding:1rem;border:1px solid #26354b;border-radius:16px;background:#111827;margin-bottom:.5rem}
  .metric-name {color:#94a3b8;font-size:.8rem}.metric-value {font-size:1.35rem;font-weight:750;margin:.25rem 0}.up{color:#34d399}.down{color:#fb7185}.muted{color:#94a3b8;font-size:.78rem}
  .score {display:flex;align-items:center;justify-content:center;width:116px;height:116px;border-radius:50%;background:conic-gradient(#34d399 var(--p),#26354b 0);margin:auto}
  .score:after {content:attr(data-score);display:flex;align-items:center;justify-content:center;width:91px;height:91px;border-radius:50%;background:#0e1726;font-size:1.75rem;font-weight:800}
  div[data-testid="stTabs"] button {min-height:48px;white-space:nowrap}
  @media(max-width:640px){.block-container{padding:1rem .8rem 4rem}.hero{padding:1.1rem}.metric-card{min-height:96px}.stButton button{min-height:48px}}
</style>
""", unsafe_allow_html=True)

MARKETS = {"원/달러": "KRW=X", "금": "GC=F", "비트코인": "BTC-USD", "이더리움": "ETH-USD"}

@st.cache_data(ttl=300, show_spinner=False)
def market_snapshot(symbols):
    data = yf.download(list(symbols), period="7d", interval="1d", group_by="ticker", auto_adjust=True, progress=False, threads=True)
    out = {}
    for symbol in symbols:
        try:
            close = (data[symbol]["Close"] if len(symbols) > 1 else data["Close"]).dropna()
            value = float(close.iloc[-1]); prev = float(close.iloc[-2])
            out[symbol] = (value, (value / prev - 1) * 100)
        except Exception:
            out[symbol] = (None, None)
    return out

@st.cache_data(ttl=600, show_spinner=False)
def stock_data(symbol):
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="1y", auto_adjust=True)
    if hist.empty:
        raise ValueError("가격 데이터를 찾을 수 없습니다. 티커를 확인해 주세요.")
    info = ticker.info or {}
    hist["MA20"] = hist.Close.rolling(20).mean()
    hist["MA50"] = hist.Close.rolling(50).mean()
    hist["MA200"] = hist.Close.rolling(200).mean()
    delta = hist.Close.diff(); gain = delta.clip(lower=0).rolling(14).mean(); loss = -delta.clip(upper=0).rolling(14).mean()
    hist["RSI"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    tr = pd.concat([(hist.High-hist.Low), (hist.High-hist.Close.shift()).abs(), (hist.Low-hist.Close.shift()).abs()], axis=1).max(axis=1)
    hist["ATR"] = tr.rolling(14).mean()
    return hist, info

def scores(hist, info):
    last = hist.iloc[-1]; price = float(last.Close)
    trend = np.mean([price > last.get("MA20", price), price > last.get("MA50", price), price > last.get("MA200", price)]) * 100
    rsi = float(last.RSI) if pd.notna(last.RSI) else 50
    momentum = max(0, min(100, 100 - abs(rsi - 58) * 2))
    roe = info.get("returnOnEquity")
    margin = info.get("operatingMargins")
    debt = info.get("debtToEquity")
    fundamental_parts = [50 if roe is None else np.clip(50 + roe*100, 0, 100), 50 if margin is None else np.clip(50 + margin*100, 0, 100), 50 if debt is None else np.clip(90-debt/2, 0, 100)]
    fundamental = float(np.mean(fundamental_parts)); technical = float(.65*trend + .35*momentum)
    overall = int(round(.45*fundamental + .55*technical))
    return overall, int(round(fundamental)), int(round(technical)), rsi

def fmt(value, kind="number"):
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value): return "—"
    if kind == "pct": return f"{value*100:.1f}%"
    if kind == "money": return f"${value:,.2f}"
    if kind == "large":
        for n, suffix in [(1e12,"T"),(1e9,"B"),(1e6,"M")]:
            if abs(value)>=n:return f"{value/n:.2f}{suffix}"
    return f"{value:,.2f}"

st.markdown('<section class="hero"><span class="pill">MOBILE READY</span><h1>분석기 by Kijung Nam V1</h1><p>시장 흐름과 종목의 펀더멘털·기술적 신호를 한 화면에서 확인하세요.</p></section>', unsafe_allow_html=True)

try: snap = market_snapshot(tuple(MARKETS.values()))
except Exception: snap = {s:(None,None) for s in MARKETS.values()}
cols = st.columns(4)
for col, (name, symbol) in zip(cols, MARKETS.items()):
    value, change = snap[symbol]; css = "up" if (change or 0)>=0 else "down"
    if name == "원/달러": value_text = "—" if value is None else f"₩{value:,.2f}"
    elif name in ("비트코인","이더리움"): value_text = "—" if value is None else f"${value:,.0f}"
    else: value_text = "—" if value is None else f"${value:,.2f}"
    change_text = "데이터 확인 중" if change is None else f"{change:+.2f}%"
    col.markdown(f'<div class="metric-card"><div class="metric-name">{name}</div><div class="metric-value">{value_text}</div><div class="{css}">{change_text}</div></div>', unsafe_allow_html=True)

with st.form("search"):
    a,b = st.columns([4,1]); symbol = a.text_input("종목 티커", value=st.session_state.get("symbol","AAPL"), placeholder="예: AAPL, NVDA, 005930.KS").strip().upper(); submitted = b.form_submit_button("분석하기", use_container_width=True)
if submitted: st.session_state.symbol = symbol
symbol = st.session_state.get("symbol", symbol)

try:
    with st.spinner("최신 시장 데이터를 분석하고 있습니다…"):
        hist, info = stock_data(symbol); overall, fundamental, technical, rsi = scores(hist, info)
    price=float(hist.Close.iloc[-1]); prev=float(hist.Close.iloc[-2]); change=(price/prev-1)*100
    signal = "적극 매수" if overall>=80 else "매수 우위" if overall>=65 else "중립" if overall>=45 else "주의"
    left,right = st.columns([3,1])
    with left:
        st.subheader(f"{info.get('shortName') or symbol} · {symbol}")
        st.markdown(f"### {fmt(price,'money')}  <span class={'up' if change>=0 else 'down'}>{change:+.2f}%</span>", unsafe_allow_html=True)
        st.caption(f"{info.get('exchange','')} · {datetime.now().strftime('%Y-%m-%d')} · 지연 데이터일 수 있음")
    with right:
        st.markdown(f'<div class="score" style="--p:{overall}%" data-score="{overall}"></div><p style="text-align:center;margin:.45rem 0">{signal}</p>', unsafe_allow_html=True)

    tab1,tab2,tab3 = st.tabs(["종합 분석","차트","재무·밸류"])
    with tab1:
        c1,c2,c3,c4=st.columns(4)
        c1.metric("종합 점수",f"{overall}/100"); c2.metric("펀더멘털",f"{fundamental}/100"); c3.metric("테크니컬",f"{technical}/100"); c4.metric("RSI (14)",f"{rsi:.1f}")
        st.subheader("분석 브리핑")
        trend_text = "주요 이동평균선 위에서 거래되어 추세가 양호합니다." if technical>=65 else "추세 확인이 더 필요하며 분할 접근이 유리합니다."
        valuation = info.get("forwardPE"); val_text = "Forward P/E 자료가 없습니다." if valuation is None else f"Forward P/E는 {valuation:.1f}배입니다."
        st.info(f"{trend_text} RSI는 {rsi:.1f}로 " + ("과열 구간에 가깝습니다. " if rsi>70 else "중립 범위입니다. ") + val_text)
        st.caption("점수는 공개 시장 데이터 기반 참고 지표이며 투자 권유가 아닙니다.")
    with tab2:
        view=hist.tail(180)
        fig=go.Figure([go.Candlestick(x=view.index,open=view.Open,high=view.High,low=view.Low,close=view.Close,name="가격")])
        for key,color in [("MA20","#38bdf8"),("MA50","#f59e0b"),("MA200","#a78bfa")]: fig.add_trace(go.Scatter(x=view.index,y=view[key],name=key,line=dict(width=1.4,color=color)))
        fig.update_layout(height=480,margin=dict(l=8,r=8,t=25,b=8),xaxis_rangeslider_visible=False,legend_orientation="h",template="plotly_dark")
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False,"responsive":True})
    with tab3:
        items=[("시가총액",fmt(info.get("marketCap"),"large")),("Forward P/E",fmt(info.get("forwardPE"))),("P/S",fmt(info.get("priceToSalesTrailing12Months"))),("영업이익률",fmt(info.get("operatingMargins"),"pct")),("ROE",fmt(info.get("returnOnEquity"),"pct")),("부채비율",fmt(info.get("debtToEquity"))),("배당수익률",fmt(info.get("dividendYield"),"pct")),("목표주가",fmt(info.get("targetMeanPrice"),"money"))]
        for row in range(0,len(items),4):
            cs=st.columns(4)
            for c,(label,value) in zip(cs,items[row:row+4]): c.metric(label,value)
except Exception as exc:
    st.error(f"{symbol} 분석을 불러오지 못했습니다: {exc}")
    st.info("미국 종목은 AAPL, 한국 종목은 005930.KS처럼 입력해 보세요.")
