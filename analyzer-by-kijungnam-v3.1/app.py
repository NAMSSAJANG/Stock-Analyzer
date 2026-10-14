import math
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

APP_NAME = "분석기 by kijungnam"
VERSION = "V3.1.4"
st.set_page_config(page_title=f"{APP_NAME} {VERSION}", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
[data-testid="stHeader"]{background:transparent}
.block-container{max-width:1380px;padding-top:1.05rem;padding-bottom:4rem}
.hero{padding:1.25rem 1.4rem;border:1px solid #26354b;border-radius:20px;background:linear-gradient(135deg,#111c2d,#0b1220);margin-bottom:.85rem}
.hero h1{font-size:clamp(1.6rem,4.5vw,2.5rem);margin:0;color:#f8fafc}.hero p{color:#94a3b8;margin:.35rem 0 0}
.pill{display:inline-block;padding:.22rem .58rem;border-radius:99px;background:#123d32;color:#5ee6b1;font-size:.76rem;margin-bottom:.55rem}
.section-title{font-size:1.08rem;font-weight:760;color:#e2e8f0;margin:.55rem 0 .42rem}
.market-status{padding:1rem 1.1rem;border:1px solid #26354b;border-radius:16px;background:#0f172a;margin-bottom:.7rem;min-height:190px}
.status-score{font-size:2rem;font-weight:850}.status-label{font-size:1.05rem;font-weight:750}.muted{color:#94a3b8;font-size:.79rem}
.card{min-width:0;padding:.75rem;border:1px solid #26354b;border-radius:14px;background:#111827}
.index-card{border:1px solid #26354b;border-radius:16px;background:#111827;padding:.78rem .85rem .45rem;overflow:hidden;min-height:178px}
.index-head{display:flex;justify-content:space-between;gap:.5rem;align-items:flex-start}.index-name{font-size:.93rem;font-weight:780;color:#f8fafc;white-space:nowrap}.index-price{font-size:.95rem;font-weight:760;color:#f8fafc;white-space:nowrap;font-variant-numeric:tabular-nums}.index-meta{font-size:.69rem;color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:.18rem}.index-change{font-size:.82rem;font-weight:750;white-space:nowrap}.search-result{padding:.55rem .7rem;border:1px solid #26354b;border-radius:10px;background:#0f172a;margin:.25rem 0}
.card .name{color:#94a3b8;font-size:.78rem}.card .value{font-size:1.18rem;font-weight:780;margin:.18rem 0;white-space:nowrap;font-variant-numeric:tabular-nums}.up{color:#34d399}.down{color:#fb7185}.neutral{color:#fbbf24}
.market-panel{border:1px solid #26354b;border-radius:16px;background:#0f172a;padding:.75rem .85rem;min-height:250px}
.market-panel-title{font-size:1rem;font-weight:780;color:#f8fafc;margin-bottom:.35rem}
.market-row{display:grid;grid-template-columns:minmax(84px,1.2fr) minmax(82px,.9fr) minmax(70px,.75fr);gap:.45rem;align-items:center;padding:.5rem .1rem;border-bottom:1px solid rgba(148,163,184,.12)}
.market-row:last-child{border-bottom:none}.market-row .asset{color:#cbd5e1;font-size:.8rem;line-height:1.2}.market-row .price{font-size:.93rem;font-weight:760;color:#f8fafc;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}.market-row .change{text-align:right;font-size:.78rem;white-space:nowrap;font-variant-numeric:tabular-nums}
.market-note{font-size:.7rem;color:#64748b;margin-top:.35rem}.market-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.75rem;margin-top:.55rem}
.gauge-wrap{padding:.9rem 1rem;border:1px solid #26354b;border-radius:16px;background:#0f172a}
.gauge-head{display:flex;justify-content:space-between;align-items:end}.gauge-score{font-size:2.2rem;font-weight:850}.gauge-label{font-size:1.05rem;font-weight:760}
.gauge-track{height:14px;background:#26354b;border-radius:99px;overflow:hidden;margin:.65rem 0 .3rem}.gauge-fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#fb7185,#fbbf24,#34d399)}
.explain{padding:.85rem 1rem;border-left:3px solid #38bdf8;background:#101a2b;border-radius:8px;color:#cbd5e1}
.briefing{padding:1rem 1.05rem;border:1px solid #2d405d;border-radius:14px;background:linear-gradient(135deg,#101a2b,#0e1726);line-height:1.65}
.pullback{padding:.9rem 1rem;border:1px solid #2c3d56;border-radius:14px;background:#111827}
.entry-card{padding:1rem 1.05rem;border:1px solid #2f4d69;border-radius:16px;background:linear-gradient(135deg,#102033,#0d1726);margin:.65rem 0}.entry-range{font-size:1.72rem;font-weight:850;color:#f8fafc;white-space:nowrap;font-variant-numeric:tabular-nums}.entry-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.65rem;margin-top:.7rem}.entry-item{padding:.65rem .7rem;border:1px solid rgba(148,163,184,.17);border-radius:11px;background:rgba(15,23,42,.55)}.entry-item .label{font-size:.7rem;color:#94a3b8}.entry-item .num{font-size:.98rem;font-weight:760;color:#f8fafc;white-space:normal}.return-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.65rem;margin:.5rem 0 .8rem}.return-card{padding:.72rem .8rem;border:1px solid #26354b;border-radius:12px;background:#111827}.return-card .period{font-size:.72rem;color:#94a3b8}.return-card .ret{font-size:1.12rem;font-weight:800;font-variant-numeric:tabular-nums}
div[data-testid="stTabs"] button{min-height:46px;white-space:nowrap}
@media(max-width:1100px){.market-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){
.entry-grid,.return-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.block-container{padding:.85rem .5rem 4rem}.hero{padding:1rem}.market-grid{grid-template-columns:1fr;gap:.5rem}.market-panel{min-height:auto}.market-row{grid-template-columns:minmax(88px,1.25fr) minmax(80px,.85fr) minmax(64px,.7fr)}.card{padding:.55rem}.card .value{font-size:.92rem}.card .name{font-size:.67rem}.status-score{font-size:1.55rem}.gauge-score{font-size:1.8rem}.stButton button{min-height:46px}
}
</style>
""", unsafe_allow_html=True)

MARKET_INDEX = {
    "S&P 500": "^GSPC", "Nasdaq 100": "^NDX", "반도체 SOX": "^SOX", "VIX": "^VIX"
}
TREASURIES = {"미국채 2년": "^UST2YR", "미국채 10년": "^TNX", "미국채 30년": "^TYX"}
COMMODITIES = {"금": "GC=F", "은": "SI=F", "WTI 원유": "CL=F", "천연가스": "NG=F", "구리": "HG=F"}
CREDIT = {"하이일드 HYG": "HYG", "투자등급 LQD": "LQD", "신흥국 EMB": "EMB"}
FX_CRYPTO = {"원/달러": "KRW=X", "달러지수": "DX-Y.NYB", "비트코인": "BTC-USD", "이더리움": "ETH-USD"}

STOCK_UNIVERSE = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA", "AMZN": "Amazon", "GOOGL": "Alphabet",
    "META": "Meta Platforms", "TSLA": "Tesla", "PLTR": "Palantir Technologies", "AMD": "Advanced Micro Devices",
    "AVGO": "Broadcom", "TSM": "Taiwan Semiconductor", "ASML": "ASML Holding", "NFLX": "Netflix",
    "COST": "Costco", "WMT": "Walmart", "JPM": "JPMorgan Chase", "XOM": "Exxon Mobil", "UNH": "UnitedHealth",
    "KO": "Coca-Cola", "PEP": "PepsiCo", "QQQ": "Invesco QQQ", "VOO": "Vanguard S&P 500 ETF",
    "SPY": "SPDR S&P 500 ETF", "JEPQ": "JPMorgan Nasdaq Equity Premium Income ETF", "JEPI": "JPMorgan Equity Premium Income ETF",
    "SCHD": "Schwab US Dividend Equity ETF", "TQQQ": "ProShares UltraPro QQQ", "QLD": "ProShares Ultra QQQ",
    "005930.KS": "삼성전자", "000660.KS": "SK하이닉스", "005380.KS": "현대차", "035420.KS": "NAVER",
    "035720.KS": "카카오", "051910.KS": "LG화학", "006400.KS": "삼성SDI", "207940.KS": "삼성바이오로직스"
}

@st.cache_data(ttl=300, show_spinner=False)
def market_history(mapping, period="3mo"):
    out = {}
    for name, symbol in mapping.items():
        try:
            h = yf.Ticker(symbol).history(period=period, auto_adjust=True)
            c = h["Close"].dropna()
            if len(c) >= 2:
                value = float(c.iloc[-1]); prev = float(c.iloc[-2]); change = (value / prev - 1) * 100
                out[name] = {"value": value, "change": change, "series": c.tail(25)}
            else:
                out[name] = {"value": None, "change": None, "series": pd.Series(dtype=float)}
        except Exception:
            out[name] = {"value": None, "change": None, "series": pd.Series(dtype=float)}
    return out

@st.cache_data(ttl=180, show_spinner=False)
def market_intraday(mapping):
    out = {}
    for name, symbol in mapping.items():
        series = pd.Series(dtype=float)
        value = change = day_high = day_low = None
        label = "1일 · 5분"
        try:
            h = yf.Ticker(symbol).history(period="1d", interval="5m", auto_adjust=True, prepost=False)
            c = h.get("Close", pd.Series(dtype=float)).dropna()
            if len(c) >= 2:
                series = c
                value = float(c.iloc[-1])
                prev_close = None
                try:
                    d = yf.Ticker(symbol).history(period="5d", interval="1d", auto_adjust=True)
                    dc = d.get("Close", pd.Series(dtype=float)).dropna()
                    if len(dc) >= 2:
                        prev_close = float(dc.iloc[-2])
                except Exception:
                    pass
                base = prev_close if prev_close not in (None, 0) else float(c.iloc[0])
                change = (value / base - 1) * 100
                day_high = float(h["High"].dropna().max()) if "High" in h else float(c.max())
                day_low = float(h["Low"].dropna().min()) if "Low" in h else float(c.min())
            else:
                raise ValueError("intraday unavailable")
        except Exception:
            label = "최근 5일 · 일봉"
            try:
                h = yf.Ticker(symbol).history(period="5d", interval="1d", auto_adjust=True)
                c = h.get("Close", pd.Series(dtype=float)).dropna()
                if len(c) >= 2:
                    series = c
                    value = float(c.iloc[-1]); prev = float(c.iloc[-2]); change = (value / prev - 1) * 100
                    day_high = float(h["High"].dropna().iloc[-1]) if "High" in h else value
                    day_low = float(h["Low"].dropna().iloc[-1]) if "Low" in h else value
            except Exception:
                pass
        out[name] = {"value": value, "change": change, "series": series.tail(78), "high": day_high, "low": day_low, "label": label}
    return out

@st.cache_data(ttl=600, show_spinner=False)
def stock_data(symbol):
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="2y", auto_adjust=True)
    if hist.empty:
        raise ValueError("가격 데이터를 찾을 수 없습니다. 티커 또는 종목명을 확인해 주세요.")
    try:
        info = ticker.info or {}
    except Exception:
        info = {}
    try:
        news = ticker.news or []
    except Exception:
        news = []
    for n in (5, 10, 20, 50, 200):
        hist[f"MA{n}"] = hist["Close"].rolling(n).mean()
    d = hist["Close"].diff(); gain = d.clip(lower=0).rolling(14).mean(); loss = -d.clip(upper=0).rolling(14).mean()
    hist["RSI"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    ema12 = hist["Close"].ewm(span=12, adjust=False).mean(); ema26 = hist["Close"].ewm(span=26, adjust=False).mean()
    hist["MACD"] = ema12 - ema26; hist["SIGNAL"] = hist["MACD"].ewm(span=9, adjust=False).mean()
    hist["VOL20"] = hist["Volume"].rolling(20).mean(); hist["STD20"] = hist["Close"].rolling(20).std()
    hist["BB_UP"] = hist["MA20"] + 2 * hist["STD20"]; hist["BB_LOW"] = hist["MA20"] - 2 * hist["STD20"]
    tr = pd.concat([(hist.High - hist.Low), (hist.High - hist.Close.shift()).abs(), (hist.Low - hist.Close.shift()).abs()], axis=1).max(axis=1)
    hist["ATR"] = tr.rolling(14).mean()
    return hist, info, news

@st.cache_data(ttl=600, show_spinner=False)
def relative_strength(symbol):
    benchmark = "^KS11" if symbol.endswith((".KS", ".KQ")) else "^GSPC"
    try:
        data = yf.download([symbol, benchmark], period="6mo", auto_adjust=True, progress=False, group_by="ticker", threads=True)
        stock = data[symbol]["Close"].dropna(); market = data[benchmark]["Close"].dropna()
        days = min(63, len(stock)-1, len(market)-1)
        if days < 20:
            return None, benchmark
        stock_ret = (stock.iloc[-1] / stock.iloc[-days] - 1) * 100
        market_ret = (market.iloc[-1] / market.iloc[-days] - 1) * 100
        return float(stock_ret - market_ret), benchmark
    except Exception:
        return None, benchmark

def safe_num(v, default=None):
    try:
        v = float(v)
        return v if math.isfinite(v) else default
    except Exception:
        return default

def clamp(v): return float(np.clip(v, 0, 100))
def pct_return(s, days): return (float(s.iloc[-1] / s.iloc[-days] - 1) * 100) if len(s) >= days else 0.0

def calendar_return(close, calendar_days):
    close = close.dropna()
    if len(close) < 2:
        return None
    last_time = close.index[-1]
    cutoff = last_time - pd.Timedelta(days=calendar_days)
    prior = close.loc[close.index <= cutoff]
    if prior.empty:
        return None
    base = float(prior.iloc[-1])
    current = float(close.iloc[-1])
    return (current / base - 1) * 100 if base else None
def smooth_score(value, scale): return clamp(50 + 45 * np.tanh(value / scale))
def level(s): return "강함" if s >= 80 else "양호" if s >= 65 else "중립" if s >= 45 else "약함" if s >= 30 else "매우 약함"
def strength_label(s): return "매우 강함" if s >= 80 else "강함" if s >= 65 else "보통" if s >= 45 else "약함"

def fmt(v, kind="number"):
    if v is None or not math.isfinite(float(v)): return "—"
    if kind == "krw": return f"₩{v:,.2f}"
    if kind == "money": return f"${v:,.2f}"
    if kind == "crypto": return f"${v:,.0f}"
    if kind == "yield": return f"{v:.2f}%"
    return f"{v:,.2f}"

def market_temperature(index_data, treasury_data, credit_data, fx_data):
    parts=[]; positives=[]; risks=[]
    def chg(d,k): return d.get(k,{}).get("change")
    def val(d,k): return d.get(k,{}).get("value")
    for k in ("S&P 500","Nasdaq 100","반도체 SOX"):
        c=chg(index_data,k)
        if c is not None:
            parts.append(clamp(50+c*12)); (positives if c>=0 else risks).append(f"{k} {c:+.2f}%")
    vix=val(index_data,"VIX")
    if vix is not None:
        s=88 if vix<15 else 75 if vix<20 else 55 if vix<25 else 35 if vix<35 else 18
        parts.append(s); (positives if vix<20 else risks).append(f"VIX {vix:.1f}")
    hyg=chg(credit_data,"하이일드 HYG"); lqd=chg(credit_data,"투자등급 LQD")
    for name,c in (("HYG",hyg),("LQD",lqd)):
        if c is not None: parts.append(clamp(50+c*20)); (positives if c>=0 else risks).append(f"{name} {c:+.2f}%")
    dxy=chg(fx_data,"달러지수")
    if dxy is not None: parts.append(clamp(50-dxy*12)); (risks if dxy>0.3 else positives).append(f"DXY {dxy:+.2f}%")
    score=round(np.mean(parts)) if parts else 50
    label="RISK ON" if score>=68 else "NEUTRAL" if score>=45 else "RISK OFF"
    temp="🔥 HOT" if score>=78 else "🟢 WARM" if score>=62 else "🟡 NORMAL" if score>=45 else "❄️ COLD"
    return score,label,temp,positives[:4],risks[:4]

def support_resistance(hist):
    h=hist.tail(300).copy(); p=float(h.Close.iloc[-1]); atr=safe_num(h.ATR.iloc[-1],p*.025)
    candidates=[]; window=5; highs=h.High.to_numpy(); lows=h.Low.to_numpy(); vols=h.Volume.to_numpy(); avg=max(float(h.Volume.tail(20).mean()),1)
    for i in range(window,len(h)-window):
        recency=.55+.45*(i/len(h)); vw=min(max(vols[i]/avg,0),3)/3
        if highs[i]>=np.max(highs[i-window:i+window+1]): candidates.append((float(highs[i]),1.25*recency+.55*vw,"스윙 고점"))
        if lows[i]<=np.min(lows[i-window:i+window+1]): candidates.append((float(lows[i]),1.25*recency+.55*vw,"스윙 저점"))
    last=h.iloc[-1]
    for key,w in (("MA20",1.0),("MA50",1.15),("MA200",1.35)):
        v=safe_num(last.get(key))
        if v: candidates.append((v,w,key))
    if not candidates:
        return {"supports":[],"resistances":[],"current":None,"atr":atr,"atr_pct":atr/p*100}
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
    near=sorted(zones,key=lambda z:abs(z["center"]-p))[0]
    current=near if near["low"]-atr*.15<=p<=near["high"]+atr*.15 else None
    return {"supports":supports,"resistances":resistances,"current":current,"atr":atr,"atr_pct":atr/p*100}

def analyze(hist,info,zones):
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
    ma_gap=(p/x.MA20-1)*100; ma50_gap=(p/x.MA50-1)*100; ma200_gap=(p/x.MA200-1)*100
    ma_alignment="정배열" if x.MA20>x.MA50>x.MA200 else "역배열" if x.MA20<x.MA50<x.MA200 else "혼조 배열"
    ret20=pct_return(hist.Close,20); ret126=pct_return(hist.Close,126); ret252=pct_return(hist.Close,252)
    ret7=calendar_return(hist.Close,7); ret30=calendar_return(hist.Close,30); ret90=calendar_return(hist.Close,90); ret365=calendar_return(hist.Close,365)
    macd_state="상승 우위" if x.MACD>x.SIGNAL else "하락 우위"
    positive=[]; caution=[]
    (positive if long_score>=55 else caution).append(f"장기 추세 {level(long_score)} ({long_score:.0f}점)")
    (positive if short_score>=55 else caution).append(f"단기 추세 {level(short_score)} ({short_score:.0f}점)")
    (positive if fundamental>=60 else caution).append(f"펀더멘털 {level(fundamental)} ({fundamental:.0f}점)")
    if rsi>=70: caution.append(f"RSI {rsi:.1f}: 과열 가능성")
    elif rsi<=30: caution.append(f"RSI {rsi:.1f}: 과매도 상태에서도 하락 지속 가능")
    else: positive.append(f"RSI {rsi:.1f}: 중립 범위")
    if vol_ratio>=1.3: positive.append(f"거래량이 20일 평균의 {vol_ratio:.1f}배")
    fundamental_basis=[f'ROE {roe*100:.1f}%' if roe is not None else 'ROE 데이터 없음',f'영업이익률 {margin*100:.1f}%' if margin is not None else '영업이익률 데이터 없음',f'매출성장률 {growth*100:.1f}%' if growth is not None else '매출성장률 데이터 없음',f'부채비율 {debt:.1f}%' if debt is not None else '부채비율 데이터 없음',f'Forward P/E {pe:.1f}배' if pe is not None else 'Forward P/E 데이터 없음']
    long_basis=[f'현재가의 200일선 이격도 {ma200_gap:+.2f}%',f'50일선의 최근 20거래일 기울기 {ma50_slope*100:+.2f}%',f'200일선의 최근 20거래일 기울기 {ma200_slope*100:+.2f}%',f'6개월 수익률 {ret126:+.2f}%',f'12개월 수익률 {ret252:+.2f}%']
    short_basis=[f'현재가의 20일선 이격도 {ma_gap:+.2f}%',f'20일선의 최근 10거래일 기울기 {ma20_slope*100:+.2f}%',f'최근 20거래일 수익률 {ret20:+.2f}%',f'MACD는 시그널 대비 {macd_state}',f'거래량은 20일 평균의 {vol_ratio:.2f}배']
    support=zones["supports"][0] if zones["supports"] else None; resistance=zones["resistances"][0] if zones["resistances"] else None
    support_dist=abs(support["distance"]) if support else 10; trend_bonus=(long_score+short_score)/2
    pullback=clamp(78-abs(ma_gap-1.5)*8-max(rsi-65,0)*2.5+(trend_bonus-50)*.45+(volume-50)*.15-max(atr_pct-5,0)*4-min(support_dist,8)*2)

    # 진입 참고구간: 추세, 눌림목, 지지구간, 20일선과 ATR을 함께 결합합니다.
    atr = zones["atr"]
    ma20 = float(x.MA20) if pd.notna(x.MA20) else p
    support_score = support["score"] if support else 45
    support_center = support["center"] if support else ma20
    trend_score = .55*long_score + .45*short_score
    entry_score = clamp(.34*pullback + .28*trend_score + .20*support_score + .18*technical)
    ma_weight = .42 if trend_score >= 65 else .30 if trend_score >= 48 else .18
    support_weight = 1 - ma_weight
    entry_center = support_center*support_weight + ma20*ma_weight
    if pullback >= 70 and short_score >= 58:
        entry_center = .75*entry_center + .25*min(p, ma20 + .35*atr)
    elif short_score < 42:
        entry_center -= .20*atr
    half_width = max(.32*atr, p*.0045)
    entry_low = entry_center - half_width
    entry_high = entry_center + half_width
    if entry_low > p + .20*atr:
        entry_low, entry_high = p-.15*atr, p+.20*atr
    entry_low=max(entry_low,0.01); entry_high=max(entry_high,entry_low)
    stop_base = support["low"] if support else min(entry_low,ma20-.35*atr)
    stop=stop_base-.70*atr
    target=resistance["center"] if resistance else max(p,entry_high)+3*atr
    entry_mid=(entry_low+entry_high)/2
    rr=(target-entry_mid)/(entry_mid-stop) if entry_mid>stop and target>entry_mid else None
    breakout=resistance["high"]+.15*atr if resistance else target-.5*atr
    if p < entry_low:
        entry_status="현재가는 참고구간 아래 · 반등 확인 필요"
    elif p <= entry_high:
        entry_status="현재가가 참고구간 안에 있음"
    else:
        gap=(p/entry_high-1)*100
        entry_status=f"현재가는 참고구간 상단보다 {gap:.1f}% 높음"
    entry_label="우호적" if entry_score>=72 and overall>=60 else "관찰" if entry_score>=52 else "보수적"
    entry_basis=[
        f"추세 종합 {trend_score:.0f}점 (장기 {long_score:.0f} · 단기 {short_score:.0f})",
        f"AI 눌림목 {pullback:.0f}점 · 20일선 이격도 {ma_gap:+.2f}%",
        f"가까운 지지 강도 {support_score:.0f}점" if support else "가까운 지지구간이 부족하여 20일선과 ATR 중심",
        f"ATR {atr_pct:.2f}%를 이용해 구간 폭과 무효화선을 조정",
    ]
    buy_low,buy_high=entry_low,entry_high
    return {"overall":round(overall),"fundamental":round(fundamental),"technical":round(technical),"long":round(long_score),"short":round(short_score),"momentum":round(momentum),"volume":round(volume),"volatility":round(volatility),"profitability":round(profitability),"growth":round(growth_score),"health":round(health),"valuation":round(valuation),"rsi":rsi,"confidence":confidence,"ma_gap":ma_gap,"ma50_gap":ma50_gap,"ma200_gap":ma200_gap,"ma_alignment":ma_alignment,"macd_state":macd_state,"vol_ratio":vol_ratio,"ret20":ret20,"ret126":ret126,"ret252":ret252,"ret7":ret7,"ret30":ret30,"ret90":ret90,"ret365":ret365,"positive":positive[:5],"caution":caution[:5],"horizon_short":round(horizon_short),"horizon_mid":round(horizon_mid),"horizon_long":round(horizon_long),"fundamental_basis":fundamental_basis,"long_basis":long_basis,"short_basis":short_basis,"atr_pct":atr_pct,"pullback":round(pullback),"buy_low":buy_low,"buy_high":buy_high,"stop":stop,"target":target,"entry_score":round(entry_score),"entry_label":entry_label,"entry_status":entry_status,"entry_basis":entry_basis,"breakout":breakout,"rr":rr}

def briefing(symbol,s,zones,temp_label):
    trend="상승 추세가 우세" if s["technical"]>=65 else "방향성이 혼조" if s["technical"]>=45 else "하락 압력이 우세"
    rsi_text="과열 구간" if s["rsi"]>=70 else "과매도 구간" if s["rsi"]<=30 else "중립 구간"
    pull="눌림목 조건이 양호" if s["pullback"]>=70 else "일부 조건만 충족" if s["pullback"]>=50 else "현재는 추격 또는 추세 훼손 위험"
    market="시장 환경은 위험선호 우위" if temp_label=="RISK ON" else "시장 환경은 중립" if temp_label=="NEUTRAL" else "시장 환경은 위험회피 우위"
    return [f"{symbol}은 현재 {trend}하며 RSI {s['rsi']:.1f}로 {rsi_text}입니다.",f"20일선 이격도는 {s['ma_gap']:+.2f}%이고, {pull}으로 평가됩니다.",f"{market}입니다. 관심 매수구간은 ${s['buy_low']:,.2f}~${s['buy_high']:,.2f}, 무효화 참고선은 ${s['stop']:,.2f}입니다."]

def news_summary(news):
    items=[]
    for n in news[:12]:
        content=n.get("content",n) if isinstance(n,dict) else {}
        title=content.get("title") or n.get("title") if isinstance(n,dict) else None
        provider=(content.get("provider") or {}).get("displayName") if isinstance(content,dict) else None
        url=((content.get("canonicalUrl") or {}).get("url") or (content.get("clickThroughUrl") or {}).get("url")) if isinstance(content,dict) else None
        if title: items.append({"title":title,"provider":provider or "News","url":url})
    return items[:3]

def resolve_symbol(query):
    q=query.strip()
    if not q: return "AAPL"
    uq=q.upper()
    if uq in STOCK_UNIVERSE: return uq
    for ticker,name in STOCK_UNIVERSE.items():
        if q.lower() in name.lower(): return ticker
    return uq

def mini_chart(name, record):
    series = record.get("series", pd.Series(dtype=float)).dropna()
    fig = go.Figure()
    if not series.empty:
        base = float(series.iloc[0]) if float(series.iloc[0]) != 0 else 1.0
        normalized = (series / base - 1) * 100
        x = series.index
        fig.add_trace(go.Scatter(
            x=x, y=normalized, mode="lines",
            line=dict(width=2.6),
            hovertemplate="%{x}<br>%{y:+.2f}%<extra></extra>"
        ))
        ymin, ymax = float(normalized.min()), float(normalized.max())
        pad = max((ymax - ymin) * 0.22, 0.12)
        yrange = [ymin - pad, ymax + pad]
    else:
        yrange = [-1, 1]
    fig.update_layout(
        height=92, margin=dict(l=2, r=2, t=4, b=2), template="plotly_dark",
        showlegend=False, xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True, range=yrange),
        paper_bgcolor="#111827", plot_bgcolor="#111827", hovermode="x"
    )
    return fig

@st.cache_data(ttl=3600, show_spinner=False)
def search_symbols(query, max_results=8):
    q = query.strip()
    if not q:
        return []
    results = []
    try:
        search = yf.Search(q, max_results=max_results, news_count=0)
        quotes = getattr(search, "quotes", []) or []
        for item in quotes:
            symbol = item.get("symbol")
            if not symbol:
                continue
            quote_type = item.get("quoteType") or item.get("typeDisp") or ""
            if str(quote_type).upper() not in {"EQUITY", "ETF", "MUTUALFUND", "INDEX", "CRYPTOCURRENCY"}:
                continue
            name = item.get("shortname") or item.get("longname") or item.get("name") or symbol
            exchange = item.get("exchange") or item.get("exchDisp") or ""
            results.append({"symbol": symbol, "name": name, "exchange": exchange, "type": quote_type})
    except Exception:
        pass
    # Local fallback and exact ticker validation
    ql = q.lower()
    for ticker, name in STOCK_UNIVERSE.items():
        if ql in ticker.lower() or ql in name.lower():
            if not any(r["symbol"] == ticker for r in results):
                results.append({"symbol": ticker, "name": name, "exchange": "", "type": "EQUITY/ETF"})
    return results[:max_results]

def market_panel(title,data,names,kind_map=None,extra_rows=None):
    rows=[]
    for name in names:
        r=data.get(name,{})
        v=r.get("value"); ch=r.get("change"); kind=(kind_map or {}).get(name,"number")
        css="up" if (ch or 0)>0 else "down" if (ch or 0)<0 else "neutral"
        change_text="N/A" if ch is None else f"{ch:+.2f}%"
        rows.append(f'<div class="market-row"><div class="asset">{name}</div><div class="price">{fmt(v,kind)}</div><div class="change {css}">{change_text}</div></div>')
    if extra_rows:
        rows.extend(extra_rows)
    return f'<div class="market-panel"><div class="market-panel-title">{title}</div>{"".join(rows)}</div>'

st.markdown(f'<section class="hero"><span class="pill">{VERSION} · MARKET FIRST</span><h1>{APP_NAME}</h1><p>시장 → 종목 → 진입구간을 한 화면에서 빠르게 읽는 반응형 투자 대시보드</p></section>',unsafe_allow_html=True)

with st.spinner("시장 환경을 불러오고 있습니다…"):
    idx=market_intraday(MARKET_INDEX); tsy=market_history(TREASURIES); cmd=market_history(COMMODITIES); crd=market_history(CREDIT); fx=market_history(FX_CRYPTO)
market_score,market_label,temp,market_pos,market_risk=market_temperature(idx,tsy,crd,fx)

st.markdown('<div class="section-title">시장 환경</div>',unsafe_allow_html=True)
a,b=st.columns([1,3])
with a:
    st.markdown(f'<div class="market-status"><div class="muted">Market Temperature</div><div class="status-score">{market_score}/100</div><div class="status-label">{temp} · {market_label}</div><div class="muted" style="margin-top:.55rem">긍정: {" · ".join(market_pos) or "뚜렷한 신호 없음"}<br>주의: {" · ".join(market_risk) or "뚜렷한 신호 없음"}</div></div>',unsafe_allow_html=True)
with b:
    cols=st.columns(4, gap="small")
    for c,name in zip(cols,MARKET_INDEX):
        r = idx[name]
        ch = r.get("change")
        ch_text = "N/A" if ch is None else f"{ch:+.2f}%"
        ch_css = "up" if (ch or 0) > 0 else "down" if (ch or 0) < 0 else "neutral"
        range_text = "" if r.get("high") is None or r.get("low") is None else f"고 {r['high']:,.2f} · 저 {r['low']:,.2f}"
        with c:
            with st.container(border=True):
                st.markdown(
                    f'<div class="index-head"><div><div class="index-name">{name}</div><div class="index-price">{fmt(r.get("value"))}</div></div><div class="index-change {ch_css}">{ch_text}</div></div><div class="index-meta">{r.get("label", "1일")} · {range_text}</div>',
                    unsafe_allow_html=True,
                )
                st.plotly_chart(mini_chart(name, r), use_container_width=True, config={"displayModeBar":False}, key=f"index_{name}")

spread=None
if tsy.get("미국채 10년",{}).get("value") is not None and tsy.get("미국채 2년",{}).get("value") is not None:
    spread=tsy["미국채 10년"]["value"]-tsy["미국채 2년"]["value"]
extra={"미국채 10년":f'<div class="muted">10Y-2Y {spread:+.2f}%p</div>' if spread is not None else ''}

spread_row=[]
if spread is not None:
    spread_row=[f'<div class="market-row"><div class="asset">10Y-2Y 스프레드</div><div class="price">{spread:+.2f}%p</div><div class="change neutral">곡선</div></div>']
kinds={"원/달러":"krw","비트코인":"crypto","이더리움":"crypto"}
market_html=(
    '<div class="market-grid">'+
    market_panel("미국채",tsy,list(TREASURIES),{k:"yield" for k in TREASURIES},spread_row)+
    market_panel("원자재",cmd,list(COMMODITIES),{k:"money" for k in COMMODITIES})+
    market_panel("신용시장",crd,list(CREDIT),{k:"money" for k in CREDIT})+
    market_panel("환율·가상자산",fx,list(FX_CRYPTO),kinds)+
    '</div>'
)
st.markdown(market_html,unsafe_allow_html=True)
st.caption("지수 차트는 미국 장중에는 5분 간격 1일 흐름을 우선 표시하며, 장중 데이터가 없으면 최근 5일 일봉으로 자동 전환됩니다.")

st.divider()
st.markdown('<div class="section-title">종목 검색</div>',unsafe_allow_html=True)
qcol, bcol = st.columns([5, 1])
with qcol:
    search_query = st.text_input(
        "티커 또는 종목명",
        value=st.session_state.get("search_text", ""),
        placeholder="예: PLTR, Palantir, Adobe, NVIDIA, 삼성전자",
        label_visibility="collapsed",
    )
with bcol:
    do_search = st.button("검색", use_container_width=True)

if do_search or (search_query.strip() and search_query != st.session_state.get("last_search_text")):
    st.session_state.search_results = search_symbols(search_query)
    st.session_state.last_search_text = search_query
    st.session_state.search_text = search_query

results = st.session_state.get("search_results", [])
selected_symbol = st.session_state.get("selected_symbol", "AAPL")
if results:
    labels = [f"{r['name']} · {r['symbol']}" + (f" · {r['exchange']}" if r['exchange'] else "") for r in results]
    chosen = st.selectbox("검색 결과", labels, index=0)
    selected_symbol = results[labels.index(chosen)]["symbol"]
    if st.button("선택한 종목 분석", type="primary", use_container_width=True):
        st.session_state.selected_symbol = selected_symbol
        st.rerun()
elif search_query.strip() and do_search:
    st.warning("검색 결과를 찾지 못했습니다. 정확한 티커를 입력해 다시 시도해 주세요.")

st.caption("회사명과 티커를 모두 검색할 수 있습니다. 검색 결과를 선택한 뒤 ‘선택한 종목 분석’을 누르세요.")
symbol = st.session_state.get("selected_symbol", selected_symbol)

try:
    with st.spinner("종목을 분석하고 있습니다…"):
        hist,info,news=stock_data(symbol); zones=support_resistance(hist); s=analyze(hist,info,zones); relative,benchmark=relative_strength(symbol)
    p=float(hist.Close.iloc[-1]); prev=float(hist.Close.iloc[-2]); change=(p/prev-1)*100
    signal="적극 매수" if s["overall"]>=80 else "매수 우위" if s["overall"]>=65 else "중립" if s["overall"]>=45 else "주의"
    title=info.get("shortName") or STOCK_UNIVERSE.get(symbol) or symbol
    l,r=st.columns([3,2])
    with l:
        st.subheader(f"{title} · {symbol}")
        st.markdown(f"### {fmt(p,'money')} <span class={'up' if change>=0 else 'down'}>{change:+.2f}%</span>",unsafe_allow_html=True)
        st.caption(f"{info.get('exchange','')} · {datetime.now().strftime('%Y-%m-%d')} · 지연 데이터일 수 있음")
    with r:
        st.markdown(f'<div class="gauge-wrap"><div class="gauge-head"><div><div class="muted">COMPOSITE SCORE</div><div class="gauge-score">{s["overall"]}<span style="font-size:1rem;color:#94a3b8">/100</span></div></div><div class="gauge-label">{signal}</div></div><div class="gauge-track"><div class="gauge-fill" style="width:{s["overall"]}%"></div></div><div class="muted">펀더멘털 {s["fundamental"]} · 테크니컬 {s["technical"]} · 시장환경 {market_score}</div></div>',unsafe_allow_html=True)

    briefs=briefing(symbol,s,zones,market_label)
    st.markdown("#### AI 브리핑")
    st.markdown('<div class="briefing">'+'<br>'.join(f'• {x}' for x in briefs)+'</div>',unsafe_allow_html=True)

    tabs=st.tabs(["종합 분석","장·단기 추세","AI 눌림목","지지·저항","통합 차트","재무·밸류","뉴스 요약","매크로 영향"])
    with tabs[0]:
        cs=st.columns(4); cs[0].metric("종합점수",f'{s["overall"]}/100',level(s["overall"])); cs[1].metric("펀더멘털",f'{s["fundamental"]}/100',level(s["fundamental"])); cs[2].metric("테크니컬",f'{s["technical"]}/100',level(s["technical"])); cs[3].metric("RSI (14)",f'{s["rsi"]:.1f}')
        rr_text=f'{s["rr"]:.2f}:1' if s.get("rr") is not None else "—"
        entry_html = f'<div class="entry-card"><div class="muted">추세 · AI 눌림목 · 지지/저항 종합</div><div style="display:flex;justify-content:space-between;gap:1rem;align-items:end;flex-wrap:wrap"><div><div style="font-weight:780;color:#cbd5e1">추천 진입 참고가격대</div><div class="entry-range">{fmt(s["buy_low"],"money")} ~ {fmt(s["buy_high"],"money")}</div></div><div style="text-align:right"><div class="muted">진입 적합도</div><div style="font-size:1.25rem;font-weight:820">{s["entry_score"]}/100 · {s["entry_label"]}</div></div></div><div class="entry-grid"><div class="entry-item"><div class="label">현재가 위치</div><div class="num">{s["entry_status"]}</div></div><div class="entry-item"><div class="label">무효화 참고선</div><div class="num">{fmt(s["stop"],"money")}</div></div><div class="entry-item"><div class="label">다음 목표 참고선</div><div class="num">{fmt(s["target"],"money")}</div></div><div class="entry-item"><div class="label">예상 보상/위험</div><div class="num">{rr_text}</div></div></div></div>'
        st.markdown(entry_html,unsafe_allow_html=True)
        with st.expander("추천 진입가격 산출 근거", expanded=False):
            for item in s["entry_basis"]: st.write(f"• {item}")
            st.write(f'• 돌파 추종 시에는 {fmt(s["breakout"],"money")} 위 안착과 거래량 증가를 별도로 확인합니다.')
            st.caption("추천 진입가격은 자동 계산된 참고구간이며 체결 보장이나 투자 권유가 아닙니다.")
        st.markdown(f'<div class="explain"><b>종합점수 해석</b><br>펀더멘털 45%와 테크니컬 55%를 결합했습니다. 현재 평가는 <b>{signal}</b>입니다.<br><br><b>펀더멘털</b><br>수익성·성장성·재무건전성·밸류에이션을 평가한 기업 기초체력 점수입니다.<br><br><b>테크니컬</b><br>장·단기 추세, 모멘텀, 거래량과 변동성 안정성을 평가합니다.<br><br><b>RSI 해석</b><br>'+ ("70 이상으로 단기 과열 가능성이 있습니다. 강한 상승장에서는 높은 RSI가 지속될 수 있습니다." if s["rsi"]>=70 else "30 이하로 과매도 가능성이 있습니다. 반등을 보장하는 신호는 아닙니다." if s["rsi"]<=30 else "30~70 사이의 중립 범위입니다.")+'</div>',unsafe_allow_html=True)
        with st.expander("점수 산출 근거 자세히 보기",expanded=True):
            st.markdown(f"""**종합점수 {s['overall']}점이 나온 이유**

펀더멘털 {s['fundamental']}점 × 45% + 테크니컬 {s['technical']}점 × 55%로 계산한 결과입니다. 기업 기초체력과 현재 가격흐름을 함께 보되, 진입 시점에 가까운 테크니컬을 조금 더 반영합니다.

**펀더멘털 {s['fundamental']}점 · {level(s['fundamental'])}**

수익성 30%, 성장성 25%, 재무건전성 25%, 밸류에이션 20%를 반영합니다. 현재 세부점수는 수익성 {s['profitability']}, 성장성 {s['growth']}, 재무건전성 {s['health']}, 밸류에이션 {s['valuation']}입니다.""")
            for item in s["fundamental_basis"]: st.write(f"• {item}")
            st.markdown(f"""**테크니컬 {s['technical']}점 · {level(s['technical'])}**

장기 추세 35%, 단기 추세 25%, 모멘텀 20%, 거래량 10%, 변동성 안정성 10%를 반영했습니다. 현재 세부점수는 장기 {s['long']}, 단기 {s['short']}, 모멘텀 {s['momentum']}, 거래량 {s['volume']}, 변동성 {s['volatility']}입니다.

**RSI {s['rsi']:.1f}**

RSI는 기업의 우열점수가 아니라 최근 상승·하락 에너지의 균형을 나타냅니다.""")
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
        def ret_card(period,value):
            if value is None:
                text,cls="N/A","neutral"
            else:
                text=f"{value:+.2f}%"; cls="up" if value>=0 else "down"
            return f'<div class="return-card"><div class="period">{period} 가격 변화</div><div class="ret {cls}">{text}</div></div>'
        returns_html='<div class="return-grid">'+ret_card("최근 7일",s.get("ret7"))+ret_card("최근 1개월",s.get("ret30"))+ret_card("최근 3개월",s.get("ret90"))+ret_card("최근 1년",s.get("ret365"))+'</div>'
        st.markdown(returns_html,unsafe_allow_html=True)
        st.caption("기간 수익률은 각 기간 시작일과 가장 가까운 이전 거래일 종가 대비 현재 종가 변화율입니다.")
        if relative is not None: st.metric("최근 3개월 시장 대비 상대강도",f"{relative:+.2f}%",f"기준: {benchmark}")
        else: st.caption("시장 대비 상대강도 데이터를 불러오지 못했습니다.")
        st.caption("모든 점수는 공개 데이터 기반 참고지표이며 투자 권유가 아닙니다.")

    with tabs[1]:
        c1,c2=st.columns(2)
        with c1:
            st.metric("장기 추세",f'{s["long"]}/100',level(s["long"])); st.write("50·200일선의 이격과 기울기, 6개월·12개월 수익률을 연속형으로 반영합니다.")
            st.info("점수가 50에 가까우면 방향이 불분명하며, 65 이상은 상승 우위, 35 이하는 하락 우위로 해석합니다.")
            with st.expander("장기점수 산출 근거",expanded=True):
                st.write("일반 해석: 200일선을 중심으로 수개월 이상 유지되는 방향과 장기 수익률을 평가합니다.")
                for item in s["long_basis"]: st.write(f"• {item}")
        with c2:
            st.metric("단기 추세",f'{s["short"]}/100',level(s["short"])); st.write("이동평균선 이격도·기울기, MACD와 20일 수익률을 연속형으로 반영합니다.")
            st.info(f'현재가는 20일선 대비 {s["ma_gap"]:+.2f}%입니다. 단기 추세는 장기 추세와 반대일 수 있습니다.')
            with st.expander("단기점수 산출 근거",expanded=True):
                st.write("일반 해석: 최근 수일~한 달의 가격 위치, 이동평균선 기울기, MACD와 거래량을 평가합니다.")
                for item in s["short_basis"]: st.write(f"• {item}")
        st.markdown("#### 테크니컬 세부점수"); cs=st.columns(5)
        for c,(k,n) in zip(cs,[("long","장기 추세"),("short","단기 추세"),("momentum","모멘텀"),("volume","거래량"),("volatility","변동성 안정성")]): c.metric(n,f'{s[k]}/100')

    with tabs[2]:
        a,b=st.columns([1,2])
        with a:
            st.markdown(f'<div class="pullback"><div class="muted">AI 눌림목 점수</div><div class="gauge-score">{s["pullback"]}/100</div><div class="gauge-track"><div class="gauge-fill" style="width:{s["pullback"]}%"></div></div><b>{"양호한 눌림목" if s["pullback"]>=70 else "관찰 구간" if s["pullback"]>=50 else "추격·추세훼손 주의"}</b></div>',unsafe_allow_html=True)
        with b:
            m1,m2,m3,m4=st.columns(4); m1.metric("현재가",fmt(p,"money")); m2.metric("추천 진입 하단",fmt(s["buy_low"],"money")); m3.metric("추천 진입 상단",fmt(s["buy_high"],"money")); m4.metric("무효화 참고선",fmt(s["stop"],"money"))
            st.markdown(f'<div class="explain">RSI {s["rsi"]:.1f}, 20일선 이격도 {s["ma_gap"]:+.2f}%, 거래량비 {s["vol_ratio"]:.2f}배, ATR {s["atr_pct"]:.2f}%를 함께 반영했습니다. 목표 참고선은 다음 저항대 기준 {fmt(s["target"],"money")}입니다.</div>',unsafe_allow_html=True)

    with tabs[3]:
        st.markdown("#### 현재 테스트 구간")
        current=zones["current"]
        if current: st.warning(f'{fmt(current["low"],"money")} ~ {fmt(current["high"],"money")} · 강도 {strength_label(current["score"])} ({current["score"]}점) · '+" · ".join(current["reasons"]))
        else: st.info("현재가는 계산된 주요 지지·저항 구간 사이에 있습니다.")
        left_z,right_z=st.columns(2)
        def show_zone(container,title,data):
            with container:
                st.markdown(f"#### {title}")
                if not data: st.caption("표시할 구간이 없습니다.")
                for i,z in enumerate(data,1):
                    st.markdown(f'**{i}차 {title}** · {fmt(z["low"],"money")} ~ {fmt(z["high"],"money")}  \n현재가 대비 {z["distance"]:+.2f}% · 강도 {strength_label(z["score"])} ({z["score"]}점)  \n근거: {" · ".join(z["reasons"])}')
        show_zone(left_z,"지지",zones["supports"]); show_zone(right_z,"저항",zones["resistances"])
        support=zones["supports"][0] if zones["supports"] else None; resistance=zones["resistances"][0] if zones["resistances"] else None
        st.markdown("#### 대응 시나리오")
        if resistance: st.success(f'상방 돌파 확인: {fmt(resistance["high"],"money")} 위 일봉 종가 안착과 거래량 증가 여부를 함께 확인합니다.')
        if support:
            st.info(f'지지 확인: {fmt(support["low"],"money")} ~ {fmt(support["high"],"money")}에서 종가 회복과 반전 여부를 확인합니다.')
            st.error(f'지지 무효화 참고: {fmt(support["low"],"money")} 아래 일봉 마감 시 다음 지지구간을 확인합니다.')
        st.caption(f'ATR(14): {fmt(zones["atr"],"money")} · 현재가 대비 {zones["atr_pct"]:.2f}%. 구간은 ATR과 최근 가격 구조에 따라 달라집니다.')

    with tabs[4]:
        v=hist.tail(252); fig=make_subplots(rows=3,cols=1,shared_xaxes=True,row_heights=[.62,.18,.20],vertical_spacing=.035)
        fig.add_trace(go.Candlestick(x=v.index,open=v.Open,high=v.High,low=v.Low,close=v.Close,name="가격"),row=1,col=1)
        for k in ("MA20","MA50","MA200"): fig.add_trace(go.Scatter(x=v.index,y=v[k],name=k,line=dict(width=1.3)),row=1,col=1)
        fig.add_trace(go.Bar(x=v.index,y=v.Volume,name="거래량"),row=2,col=1); fig.add_trace(go.Scatter(x=v.index,y=v.RSI,name="RSI"),row=3,col=1)
        for z in zones["supports"][:3]: fig.add_hrect(y0=z["low"],y1=z["high"],opacity=.12,line_width=0,row=1,col=1)
        for z in zones["resistances"][:3]: fig.add_hrect(y0=z["low"],y1=z["high"],opacity=.10,line_width=0,row=1,col=1)
        fig.add_hrect(y0=s["buy_low"],y1=s["buy_high"],opacity=.08,line_width=0,row=1,col=1,annotation_text="AI 관심구간",annotation_position="bottom left")
        fig.add_hline(y=s["stop"],line_dash="dash",row=1,col=1,annotation_text="무효화 참고선",annotation_position="bottom left")
        fig.add_hline(y=70,line_dash="dot",row=3,col=1); fig.add_hline(y=30,line_dash="dot",row=3,col=1)
        fig.update_layout(height=720,margin=dict(l=8,r=8,t=25,b=8),xaxis_rangeslider_visible=False,legend_orientation="h",template="plotly_dark")
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False,"responsive":True})
        st.markdown("#### 차트 자동 해석")
        chart_lines=[f'이동평균선 배열은 **{s["ma_alignment"]}**입니다.',f'현재가는 20일선 대비 **{s["ma_gap"]:+.2f}%**, 50일선 대비 **{s["ma50_gap"]:+.2f}%**, 200일선 대비 **{s["ma200_gap"]:+.2f}%** 위치입니다.',f'MACD는 시그널 대비 **{s["macd_state"]}**이며, 거래량은 20일 평균의 **{s["vol_ratio"]:.2f}배**입니다.',f'최근 20거래일 수익률은 **{s["ret20"]:+.2f}%**, 약 6개월은 **{s["ret126"]:+.2f}%**, 약 12개월은 **{s["ret252"]:+.2f}%**입니다.']
        if zones["resistances"]: rz=zones["resistances"][0]; chart_lines.append(f'가장 가까운 저항은 **{fmt(rz["low"],"money")}~{fmt(rz["high"],"money")}**로 계산됩니다.')
        if zones["supports"]: sz=zones["supports"][0]; chart_lines.append(f'가장 가까운 지지는 **{fmt(sz["low"],"money")}~{fmt(sz["high"],"money")}**로 계산됩니다.')
        for line in chart_lines: st.write(f"• {line}")
        if s["long"]>=60 and s["short"]<45: st.warning("장기 상승구조 안에서 단기 조정이 진행되는 조합입니다. 단기 지지 확인이 중요합니다.")
        elif s["long"]<45 and s["short"]>=60: st.warning("장기 약세 구조에서 단기 반등이 나타난 조합입니다. 장기 이동평균선 돌파 여부를 확인해야 합니다.")
        elif s["long"]>=60 and s["short"]>=60: st.success("장기와 단기 추세가 모두 상승 우위로 정렬된 상태입니다. 다만 RSI와 가까운 저항구간을 함께 확인하세요.")
        elif s["long"]<45 and s["short"]<45: st.error("장기와 단기 추세가 모두 약세 우위입니다. 반등 기대보다 추세 회복 확인이 우선입니다.")
        else: st.info("장기와 단기 신호가 혼재하거나 중립에 가깝습니다. 지지·저항 돌파 방향을 추가로 확인하세요.")

    with tabs[5]:
        st.markdown("#### 펀더멘털 세부점수"); cs=st.columns(4)
        for c,(k,n) in zip(cs,[("profitability","수익성"),("growth","성장성"),("health","재무건전성"),("valuation","밸류에이션")]): c.metric(n,f'{s[k]}/100',level(s[k]))
        items=[("시가총액",info.get("marketCap"),"large"),("Forward P/E",info.get("forwardPE"),"number"),("P/S",info.get("priceToSalesTrailing12Months"),"number"),("영업이익률",info.get("operatingMargins"),"pct"),("ROE",info.get("returnOnEquity"),"pct"),("부채비율",info.get("debtToEquity"),"number"),("매출성장률",info.get("revenueGrowth"),"pct"),("목표주가",info.get("targetMeanPrice"),"money")]
        for i in range(0,8,4):
            cs=st.columns(4)
            for c,(n,v,k) in zip(cs,items[i:i+4]):
                if k=="large": text="—" if safe_num(v) is None else f"${float(v)/1e9:,.2f}B"
                elif k=="pct": text="—" if safe_num(v) is None else f"{float(v)*100:.2f}%"
                else: text=fmt(safe_num(v),k)
                c.metric(n,text)
        st.metric("펀더멘털 데이터 신뢰도",f'{s["confidence"]}%')
        st.caption("신뢰도는 핵심 재무항목의 데이터 완성도를 뜻합니다. 자료가 없는 항목은 중립값 50점으로 처리됩니다.")

    with tabs[6]:
        summaries=news_summary(news)
        if summaries:
            st.markdown("#### 오늘의 핵심 뉴스 3선")
            for i,n in enumerate(summaries,1):
                if n["url"]: st.markdown(f"**{i}. [{n['title']}]({n['url']})**  \n{n['provider']}")
                else: st.markdown(f"**{i}. {n['title']}**  \n{n['provider']}")
        else: st.info("뉴스 데이터를 불러오지 못했습니다.")

    with tabs[7]:
        sector=info.get("sector") or "업종 정보 없음"; st.metric("현재 매크로 환경",f"{market_score}/100",level(market_score)); st.write(f"분석 종목 업종: **{sector}**")
        if sector in ("Technology","Communication Services","Consumer Cyclical"): text="성장주 성격이 강한 업종은 미국 장기금리와 달러 강세에 상대적으로 민감할 수 있습니다. VIX와 Nasdaq 흐름도 함께 확인하세요."
        elif sector=="Financial Services": text="금융주는 기준금리뿐 아니라 장단기 금리차, 신용위험과 경기 흐름을 함께 확인해야 합니다."
        elif sector in ("Energy","Basic Materials"): text="원유·구리 등 원자재 가격과 달러지수, 글로벌 경기 흐름의 영향을 크게 받을 수 있습니다."
        else: text="현재 매크로 점수는 시장 전반의 위험선호 환경을 나타냅니다. 종목 고유의 경쟁력과 별도로 참고하세요."
        st.info(text); st.warning("매크로 점수는 종합점수에 직접 합산하지 않습니다. 개별 종목 판단을 보완하는 참고자료입니다.")

except Exception as e:
    st.error(str(e))
    st.info("Yahoo Finance 데이터가 일시적으로 제한되었을 수 있습니다. 잠시 후 다시 시도하거나 정확한 티커를 입력해 주세요.")
