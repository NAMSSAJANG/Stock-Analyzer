from __future__ import annotations

import html

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.analysis_engine import analyze_stock
from modules.history_store import list_history, save_snapshot
from modules.market_data import auxiliary_market, load_market_assets, market_health


st.set_page_config(page_title="Analyzer by Kijung V3.3", page_icon="📈", layout="wide")


def inject_css():
    st.markdown("""<style>
    .block-container{max-width:1500px;padding-top:1.4rem;padding-bottom:4rem}
    [data-testid="stSidebar"]{background:#0b1627;border-right:1px solid #20314a}
    .eyebrow{color:#7dd3fc;font-size:.72rem;font-weight:800;letter-spacing:.16em;text-transform:uppercase}
    .hero{padding:1.45rem;border:1px solid #243651;border-radius:20px;background:linear-gradient(135deg,#0e1c31,#101827);box-shadow:0 16px 48px #02061755}
    .hero-grid{display:grid;grid-template-columns:220px 1fr;gap:1.4rem;align-items:center}.hero-score{font-size:3.2rem;font-weight:850;line-height:1}.muted{color:#94a3b8}
    .card{height:100%;padding:1rem;border:1px solid #22334d;border-radius:16px;background:#0d192a}.card-title{font-size:.75rem;color:#94a3b8;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.value{font-size:1.55rem;font-weight:760}
    .gauge{height:7px;border-radius:8px;background:#1e293b;overflow:hidden;margin:.55rem 0}.gauge>span{display:block;height:100%;border-radius:8px}
    .status{font-size:.78rem;font-weight:800}.reason{padding:.72rem .85rem;margin:.42rem 0;background:#0b1525;border-left:3px solid #38bdf8;border-radius:7px}
    .up{color:#60a5fa}.down{color:#f87171}.flat{color:#facc15}.metric-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:.5rem}.metric-chip{padding:.6rem .75rem;border:1px solid #213149;border-radius:10px;background:#0b1626}.metric-chip b{display:block;font-size:1rem}
    .section-title{font-size:1.25rem;font-weight:800;margin:1.6rem 0 .6rem}.disclaimer{color:#64748b;font-size:.76rem;margin-top:2rem}.brief-card{padding:1rem 1.05rem;border:1px solid #243651;border-radius:14px;background:linear-gradient(145deg,#0b1728,#0d1a2d);margin:.55rem 0}.brief-card h4{margin:.1rem 0 .45rem}.brief-card p{margin:.25rem 0;color:#cbd5e1;line-height:1.65}.price-zone{padding:1rem;border:1px solid #29405e;border-radius:15px;background:#0b1728;text-align:center}.price-zone .big{font-size:1.45rem;font-weight:800;margin-top:.25rem}.nav-title{text-align:center;margin:.15rem 0 .7rem}.nav-title h1{font-size:1.65rem;margin:0}.nav-title p{margin:.1rem;color:#7dd3fc;font-size:.78rem;letter-spacing:.12em}.return-box{padding:.8rem;border-radius:12px;background:#0b1728;border:1px solid #243651;text-align:center}.return-value{font-size:1.25rem;font-weight:850}.ret-up{color:#4ade80}.ret-down{color:#f87171}
    div[role="radiogroup"]{justify-content:center;gap:.35rem}div[role="radiogroup"] label{background:#0d192a;border:1px solid #263955;border-radius:11px;padding:.4rem .8rem}
    @media(max-width:700px){.hero-grid{grid-template-columns:1fr}.hero-score{font-size:2.6rem}.metric-strip{grid-template-columns:repeat(2,1fr)}.block-container{padding-left:.7rem;padding-right:.7rem}[data-testid="stHorizontalBlock"]{flex-wrap:wrap!important;gap:.55rem!important}[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{flex:1 1 calc(50% - .55rem)!important;min-width:calc(50% - .55rem)!important}}
    </style>""", unsafe_allow_html=True)


def status(score: int):
    if score >= 85: return "Strong", "#22c55e", "🟢"
    if score >= 70: return "Good", "#4ade80", "🟢"
    if score >= 50: return "Neutral", "#facc15", "🟡"
    if score >= 30: return "Weak", "#fb923c", "🟠"
    return "Very Weak", "#ef4444", "🔴"


def score_card(title, score, subtitle=""):
    label, color, icon = status(score)
    st.markdown(f"""<div class="card"><div class="card-title">{html.escape(title)}</div>
    <div class="value">{score}<span class="muted" style="font-size:.85rem"> / 100</span></div>
    <div class="gauge"><span style="width:{score}%;background:{color}"></span></div>
    <div class="status" style="color:{color}">{icon} {label}</div><div class="muted" style="font-size:.75rem">{html.escape(subtitle)}</div></div>""", unsafe_allow_html=True)


def ai_briefings(a):
    s, m = a.scores, a.metrics
    overall_action = "분할 접근을 검토할 수 있습니다" if s["overall"] >= 75 else ("추천 가격대에서 조건을 확인하는 편이 유리합니다" if s["overall"] >= 50 else "신규 진입보다 위험 관리와 관망이 우선입니다")
    fundamental = (
        f"펀더멘털 점수는 {s['fundamental']}점입니다. 공개 재무자료에서 수익성·성장성·부채 부담을 함께 평가했습니다. "
        + ("사업 체력은 비교적 우호적이지만 밸류에이션과 다음 실적에서 지속성을 확인해야 합니다." if s["fundamental"] >= 70 else "현재 데이터만으로 강한 우위를 단정하기 어려워 다음 실적과 현금흐름 확인이 중요합니다.")
    )
    technical = (
        f"테크니컬 점수는 {s['technical']}점입니다. 현재가 {a.price:,.2f}, 20일선 {m['ma20']:,.2f}, 50일선 {m['ma50']:,.2f}, 200일선 {m['ma200']:,.2f}의 배열과 RSI {m['rsi']:.1f}를 반영했습니다. "
        + ("장단기 이동평균 구조가 가격에 우호적입니다." if a.price > m['ma200'] and m['ma20'] > m['ma50'] else "추세 신호가 혼재하므로 가격 확인 없이 추격하기에는 부담이 있습니다.")
    )
    market = (
        f"시장환경 점수는 {s['market']}점입니다. S&P 500·Nasdaq 100·SOX의 방향, VIX, 위험자산과 신용시장을 종합했습니다. "
        + ("시장 바람이 종목의 상승 시나리오를 돕는 구간입니다." if s["market"] >= 70 else ("시장 신호가 혼재해 종목 자체의 지지 확인이 더 중요합니다." if s["market"] >= 45 else "시장 역풍 가능성이 있어 포지션 크기를 보수적으로 관리할 필요가 있습니다."))
    )
    trend = f"장기 추세 {s['long']}점, 단기 추세 {s['short']}점, AI 눌림목 {s['pullback']}점입니다. 추천 진입 참고가격대 {a.entry_low:,.2f}~{a.entry_high:,.2f}에서 지지가 확인되는지, 무효화선 {a.invalidation:,.2f}을 지키는지가 핵심입니다."
    summary = f"종합점수 {s['overall']}점으로, 현재는 {overall_action}. 강점은 {a.positives[0]} 반면 {a.cautions[0]}"
    return {"종합 AI 브리핑": summary, "펀더멘털 브리핑": fundamental, "테크니컬 브리핑": technical, "시장환경 브리핑": market, "추세·진입 브리핑": trend}


def render_ai_briefings(a):
    briefs = ai_briefings(a)
    st.markdown('<div class="section-title">AI 종합 브리핑</div>', unsafe_allow_html=True)
    first = briefs.pop("종합 AI 브리핑")
    st.markdown(f'<div class="brief-card"><div class="eyebrow">Decision Brief</div><h4>종합 AI 브리핑</h4><p>{html.escape(first)}</p></div>', unsafe_allow_html=True)
    cols = st.columns(2)
    for index, (title, body) in enumerate(briefs.items()):
        with cols[index % 2]:
            st.markdown(f'<div class="brief-card"><h4>{title}</h4><p>{html.escape(body)}</p></div>', unsafe_allow_html=True)


def sparkline(asset):
    fig = go.Figure()
    values = np.asarray(asset.spark, dtype=float)
    if len(values):
        x = np.arange(len(values))
        positive = np.where(values >= 0, values, np.nan)
        negative = np.where(values <= 0, values, np.nan)
        fig.add_trace(go.Scatter(x=x, y=positive, mode="lines", line=dict(color="#60a5fa", width=2), connectgaps=False, hovertemplate="%{y:.2f}%<extra></extra>"))
        fig.add_trace(go.Scatter(x=x, y=negative, mode="lines", line=dict(color="#f87171", width=2), connectgaps=False, hovertemplate="%{y:.2f}%<extra></extra>"))
        # Overlay faint full line so baseline crossings remain visually connected.
        fig.add_trace(go.Scatter(x=x, y=values, mode="lines", line=dict(color="#94a3b8", width=.7), hoverinfo="skip"))
    fig.add_hline(y=0, line_color="#64748b", line_width=1)
    fig.update_layout(height=66, margin=dict(l=0,r=0,t=0,b=0), showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(visible=False), yaxis=dict(visible=False, fixedrange=True))
    return fig


@st.cache_data(ttl=300, show_spinner=False)
def get_market():
    assets = load_market_assets(); aux = auxiliary_market(); health = market_health(assets, aux)
    return assets, aux, health


def market_page():
    with st.spinner("시장 데이터를 불러오는 중입니다..."):
        assets, aux, (score, confidence, brief, reasons) = get_market()
    label, color, icon = status(score)
    st.markdown(f"""<div class="hero"><div class="eyebrow">Today's Market · V3.3</div><div class="hero-grid">
    <div><div class="muted">MARKET HEALTH</div><div class="hero-score">{score}<span class="muted" style="font-size:1rem"> / 100</span></div><div class="gauge"><span style="width:{score}%;background:{color}"></span></div><b style="color:{color}">{icon} {label}</b></div>
    <div><div class="card-title">AI Market Brief</div><h3 style="margin:.3rem 0">{html.escape(brief)}</h3><span class="muted">AI Confidence {confidence}% · 수집 범위와 신호 일치도를 반영</span></div></div></div>""", unsafe_allow_html=True)
    with st.expander("Market Health 산출 근거"):
        for reason in reasons: st.markdown(f"- {reason}")
        st.caption("주요 지수, VIX, 위험자산, 신용 ETF를 규칙 기반으로 합산합니다. 투자 권유가 아닙니다.")
    st.markdown('<div class="section-title" style="margin-top:1rem">Market Pulse</div>', unsafe_allow_html=True)
    for row in range(0, 12, 4):
        cols = st.columns(4)
        for col, asset in zip(cols, assets[row:row+4]):
            with col:
                value = "데이터 없음" if asset.value is None else f"{asset.value:,.2f}"
                change = "—" if asset.change is None else f"{asset.change:+.2f}%"
                cls = "flat" if asset.change is None else ("up" if asset.change >= 0 else "down")
                st.markdown(f'<div class="card-title">{asset.name}</div><div class="value">{value}</div><div class="{cls}"><b>{change}</b></div>', unsafe_allow_html=True)
                st.plotly_chart(sparkline(asset), use_container_width=True, config={"displayModeBar":False})
    st.caption("Sparkline은 전일 종가를 0%로 둔 장중 수익률입니다. 파랑은 0% 이상, 빨강은 0% 이하입니다.")
    st.markdown('<div class="section-title">Rates & Credit</div>', unsafe_allow_html=True)
    rate_labels = ["US 2Y","US 10Y","US 30Y","10Y-2Y"]
    credit_labels = ["HYG","LQD","Credit Spread"]
    for labels in (rate_labels, credit_labels):
        st.markdown('<div class="metric-strip">' + ''.join(
            f'<div class="metric-chip"><span class="muted">{label}</span><b>{"—" if aux[label][0] is None else f"{aux[label][0]:.2f}"}</b><small>{"" if aux[label][1] is None else f"{aux[label][1]:+.2f}%"}</small></div>' for label in labels
        ) + '</div>', unsafe_allow_html=True)
    return score


def price_chart(a):
    frame = a.history.tail(260)
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=frame.index, open=frame.Open, high=frame.High, low=frame.Low, close=frame.Close, name="Price", increasing_line_color="#60a5fa", decreasing_line_color="#f87171"))
    for w, color in [(20,"#38bdf8"),(50,"#facc15"),(200,"#a78bfa")]:
        fig.add_trace(go.Scatter(x=frame.index,y=frame[f"MA{w}"],name=f"MA {w}",line=dict(width=1.2,color=color)))
    fig.add_hrect(y0=a.entry_low,y1=a.entry_high,fillcolor="#22c55e",opacity=.12,line_width=0,annotation_text="추천 진입")
    for value, _ in a.supports: fig.add_hline(y=value,line_color="#22c55e",line_dash="dot",line_width=1)
    for value, _ in a.resistances: fig.add_hline(y=value,line_color="#ef4444",line_dash="dot",line_width=1)
    fig.add_hline(y=a.invalidation,line_color="#fb923c",line_dash="dash",annotation_text="무효화")
    fig.update_layout(height=520,margin=dict(l=0,r=0,t=25,b=0),xaxis_rangeslider_visible=False,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#091423",legend=dict(orientation="h"),hovermode="x unified")
    return fig


def analyzer_page(market_score):
    st.markdown('<div class="eyebrow">Stock Analyzer · Full Detail</div><h1>종목 분석</h1>', unsafe_allow_html=True)
    with st.form("ticker-form"):
        ticker = st.text_input("티커", value=st.session_state.get("ticker", "AAPL"), placeholder="예: AAPL, NVDA, 005930.KS")
        submitted = st.form_submit_button("분석 시작", use_container_width=True)
    if submitted: st.session_state.ticker = ticker
    ticker = st.session_state.get("ticker", ticker)
    if not ticker: return
    try:
        with st.spinner(f"{ticker.upper()} 데이터를 분석하는 중입니다..."):
            a = analyze_stock(ticker, market_score)
    except Exception as exc:
        st.error(f"분석하지 못했습니다: {exc}"); return
    previous, current = save_snapshot(a.ticker, a.scores, a.score_reasons)
    overall = a.scores["overall"]; label, color, icon = status(overall)
    confidence = int(np.clip(65 + abs(overall-50)*.45 + (5 if a.news else 0), 55, 94))
    verdict = "BUY · 분할 접근" if overall >= 75 else ("WAIT FOR ENTRY · 조건 확인" if overall >= 50 else "CAUTION · 관망 우선")
    st.markdown(f"""<div class="hero"><div class="eyebrow">{html.escape(a.ticker)} · {html.escape(a.name)}</div><div class="hero-grid"><div><div class="hero-score">{overall}<span class="muted" style="font-size:1rem"> / 100</span></div><div class="gauge"><span style="width:{overall}%;background:{color}"></span></div><b style="color:{color}">{icon} {label}</b></div><div><h2 style="margin:.1rem 0">{verdict}</h2><div class="muted">AI Confidence {confidence}%</div><p>{html.escape(a.positives[0])} {html.escape(a.cautions[0])}</p></div></div></div>""", unsafe_allow_html=True)
    render_ai_briefings(a)
    st.markdown('<div class="section-title">종합 점수</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    for col, key, title in zip(cols,["fundamental","technical","market","news"],["Fundamental","Technical","Market","News"]):
        with col: score_card(title,a.scores[key])
    with st.expander("종합점수 해석 및 실제 산출근거", expanded=True):
        st.write("종합점수 = 펀더멘털 30% + 테크니컬 40% + 시장환경 20% + 뉴스/단기반응 10%")
        for key, reasons in a.score_reasons.items():
            st.markdown(f"**{key.title()}**")
            for reason in reasons: st.markdown(f'<div class="reason">{html.escape(reason)}</div>', unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1:
        st.subheader("긍정요인")
        for item in a.positives: st.success(item)
    with c2:
        st.subheader("주의요인")
        for item in a.cautions: st.warning(item)
    st.markdown('<div class="section-title">장·단기 추세 / AI 눌림목</div>', unsafe_allow_html=True)
    cols=st.columns(3)
    for col,key,title in zip(cols,["long","short","pullback"],["Long Trend","Short Trend","AI Pullback"]):
        with col: score_card(title,a.scores[key])
    with st.expander("장단기 추세 및 눌림목 산출근거"):
        st.write(f"장기: 현재가 {a.price:,.2f}, MA200 {a.metrics['ma200']:,.2f} / 단기: MA20 {a.metrics['ma20']:,.2f}, MA50 {a.metrics['ma50']:,.2f}")
        st.write(f"RSI {a.metrics['rsi']:.1f}, ATR {a.metrics['atr']:.2f}, 최근 거래량비 {a.metrics['volume_ratio']:.2f}x")
    st.markdown('<div class="section-title">추천 진입 참고가격대 · AI 진입 전략</div>', unsafe_allow_html=True)
    top=st.columns(4)
    values=[("현재가",f"{a.price:,.2f}"),("추천 진입",f"{a.entry_low:,.2f} ~ {a.entry_high:,.2f}"),("추천 비중",f"{max(10,min(70,(overall//10)*10-10))}%"),("무효화 / 목표",f"{a.invalidation:,.2f} / {a.target:,.2f}")]
    for col,(title,value) in zip(top,values):
        with col: st.markdown(f'<div class="price-zone"><div class="card-title">{title}</div><div class="big">{value}</div></div>', unsafe_allow_html=True)
    weights = (30,40,30) if overall >= 65 else (20,40,40)
    levels = [min(a.price,a.entry_high), (a.entry_low+a.entry_high)/2, a.entry_low]
    st.info(f"장기 추세와 저항 거리를 함께 고려한 분할 접근입니다. 1차 {weights[0]}% @ {levels[0]:,.2f} → 2차 {weights[1]}% @ {levels[1]:,.2f} → 3차 {weights[2]}% @ {levels[2]:,.2f}. 무효화 참고선은 {a.invalidation:,.2f}입니다.")
    with st.expander("추천 진입가격 해석 및 산출근거", expanded=True):
        st.markdown(f"""
- **핵심 지지:** 가장 가까운 이동평균·최근 저점 기반 지지선은 `{a.supports[0][0]:,.2f}`입니다.
- **변동성 조정:** ATR `{a.metrics['atr']:.2f}`를 사용해 한 가격이 아닌 `{a.entry_low:,.2f}~{a.entry_high:,.2f}` 범위로 계산했습니다.
- **추세 반영:** 장기 `{a.scores['long']}점`, 단기 `{a.scores['short']}점`, 눌림목 `{a.scores['pullback']}점`을 비중과 분할 순서에 반영했습니다.
- **위험 관리:** `{a.invalidation:,.2f}` 이탈 시 지지 가정이 약해진 것으로 보고 전략을 재검토합니다.
- **상방 확인:** 가까운 저항·목표 `{a.target:,.2f}` 돌파 시에는 거래량 동반 여부를 함께 확인합니다.
        """)
    st.markdown('<div class="section-title">가격 · 지지저항 차트</div>', unsafe_allow_html=True)
    st.plotly_chart(price_chart(a),use_container_width=True,config={"displayModeBar":False})
    c1,c2=st.columns(2)
    with c1:
        st.subheader("지지 구간")
        for v, reason in a.supports: st.write(f"🟢 **{v:,.2f}** · {reason}")
    with c2:
        st.subheader("저항 구간")
        for v, reason in a.resistances: st.write(f"🔴 **{v:,.2f}** · {reason}")
    with st.expander("상승·지지·무효화 시나리오", expanded=True):
        st.markdown(f"- **돌파:** {a.target:,.2f} 상향 돌파와 거래량 증가 시 추세 지속 가능성을 확인합니다.\n- **지지:** {a.entry_low:,.2f}~{a.entry_high:,.2f}에서 반등하면 분할 접근 구간으로 봅니다.\n- **무효화:** {a.invalidation:,.2f} 이탈 시 기존 진입 가정을 재검토합니다.")
    st.markdown('<div class="section-title">기간별 참고</div>',unsafe_allow_html=True)
    cols=st.columns(4)
    for col,(period,value) in zip(cols,a.returns.items()):
        with col:
            if value is None:
                shown, css = "데이터 부족", "muted"
            else:
                shown, css = f"{value:+.2f}%", ("ret-up" if value >= 0 else "ret-down")
            st.markdown(f'<div class="return-box"><div class="card-title">{period}</div><div class="return-value {css}">{shown}</div></div>', unsafe_allow_html=True)
    score_history_section(a,previous,current)
    st.markdown('<div class="section-title">최신 뉴스</div>',unsafe_allow_html=True)
    if not a.news: st.info("현재 표시 가능한 최신 뉴스가 없습니다. 뉴스 점수는 중립으로 처리했습니다.")
    for item in a.news:
        title=html.escape(item["title"]); publisher=html.escape(item["publisher"])
        st.markdown(f"- [{title}]({item['url']}) · {publisher}" if item["url"] else f"- {title} · {publisher}")


def score_history_section(a,previous,current):
    st.markdown('<div class="section-title">AI Score History</div>',unsafe_allow_html=True)
    if previous is None:
        st.info("첫 분석 기록을 저장했습니다. 다음 날짜에 같은 종목을 다시 분석하면 점수 변화와 원인이 표시됩니다.")
    else:
        delta=current["score"]-previous["score"]
        cols=st.columns(3)
        cols[0].metric("오늘 점수",current["score"])
        cols[1].metric("이전 저장 점수",previous["score"])
        cols[2].metric("변화량",f"{delta:+d}",delta=f"{delta:+d}")
        labels={"fundamental":"펀더멘털","technical":"테크니컬","market":"시장환경","news":"뉴스"}
        changes=[]
        for key,label in labels.items():
            value=current[key]-previous[key]
            if value: changes.append((label,value))
        if changes:
            st.write("변화 원인(카테고리 점수 변화 기준): " + " · ".join(f"{label} {value:+d}" for label,value in changes))
        else: st.caption("세부 카테고리 점수 변화가 없습니다.")
    rows=list_history(a.ticker)
    if len(rows)>1:
        frame=pd.DataFrame(rows).sort_values("captured_at")
        fig=go.Figure(go.Scatter(x=pd.to_datetime(frame.captured_at),y=frame.score,mode="lines+markers",line=dict(color="#38bdf8",width=2)))
        fig.update_layout(height=240,margin=dict(l=0,r=0,t=10,b=0),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="#091423",yaxis=dict(range=[0,100],title="Score"),xaxis_title=None)
        st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})


def lab_page():
    st.markdown('<div class="eyebrow">Experimental Lab</div><h1>Coming Soon</h1>',unsafe_allow_html=True)
    st.info("V4에서 순차적으로 제공할 실험 기능입니다.")
    cols=st.columns(2)
    for col,title,desc in [(cols[0],"백테스트","AI 전략과 Buy & Hold 비교"),(cols[1],"포트폴리오","비중·변동성·최대낙폭 분석"),(cols[0],"전략 비교","RSI·MACD·추세 전략 비교"),(cols[1],"AI Simulation","투자기간별 가상 시나리오")]:
        with col: st.markdown(f'<div class="card"><div class="card-title">{title}</div><div class="value" style="font-size:1.1rem">{desc}</div></div>',unsafe_allow_html=True)


inject_css()
st.markdown('<div class="nav-title"><h1>Analyzer by Kijungnam</h1><p>V3.3 · AI DECISION DASHBOARD</p></div>', unsafe_allow_html=True)
page=st.radio("메뉴",["🏠 분석","🌎 시장환경","🧪 Lab"],horizontal=True,label_visibility="collapsed")
if page=="🌎 시장환경":
    refresh_col, caption_col = st.columns([1,4])
    with refresh_col:
        if st.button("↻ 시장 새로고침",use_container_width=True):
            get_market.clear(); st.rerun()
    with caption_col: st.caption("12개 핵심자산 · 미국채 · 신용시장 · 전일 종가 기준 장중 흐름")

if page=="🌎 시장환경": market_page()
elif page=="🧪 Lab": lab_page()
else:
    try:
        assets,aux,(market_score,_,_,_)=get_market()
    except Exception:
        market_score=50
    analyzer_page(market_score)

st.markdown('<div class="disclaimer">본 서비스는 교육·정보 제공 목적이며 투자 권유가 아닙니다. 가격, 재무, 뉴스 데이터에는 지연·누락·오류가 있을 수 있으며 실제 투자 판단과 책임은 사용자에게 있습니다.</div>',unsafe_allow_html=True)
