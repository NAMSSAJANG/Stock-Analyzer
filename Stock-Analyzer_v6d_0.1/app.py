from __future__ import annotations
import html
from datetime import date, datetime
from zoneinfo import ZoneInfo
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import VERSION, ENGINE_VERSION, MENUS, NAMES, normalize_symbol, safe_url
from store import Store
from provider import fetch
from analysis_service import frame_of, required_symbols, earnings_event, build_analysis, changes

st.set_page_config(page_title=f"Stock Analyzer {VERSION}",page_icon="📈",layout="wide")
st.markdown('''<style>
.block-container{max-width:1440px;padding-top:2rem;padding-bottom:4rem}
h1{letter-spacing:-.04em!important} h2,h3{letter-spacing:-.025em!important}
[data-testid="stMetric"]{background:white;border:1px solid #DFE7ED;border-radius:12px;padding:16px}
[data-testid="stSidebar"]{border-right:1px solid #DFE7ED}
.hero{background:#183A43;color:#fff;padding:25px 28px;border-radius:16px;margin-bottom:22px}
.hero small{color:#A3DAD0;letter-spacing:.12em}.hero h2{color:#fff;margin:7px 0}.hero p{color:#D4E3E6;margin:0}
</style>''',unsafe_allow_html=True)
store=Store()
if st.session_state.get("pending_symbol"):
    st.session_state.symbol=st.session_state.pop("pending_symbol")
    st.session_state.menu="종목 분석"

@st.cache_data(ttl=600,show_spinner=False)
def cached_load(request, nonce): return fetch(request, force=nonce>0)

def load(request): return cached_load(request, st.session_state.get("refresh_nonce",0))

def goto(page, symbol=None):
    st.session_state["menu"]=page
    if symbol: st.session_state["symbol"]=symbol

def label(s): return f"{NAMES.get(s,s)} · {s}" if s in NAMES else s

def display_time(value):
    try:
        ts=pd.Timestamp(value)
        ts=ts.tz_localize("UTC") if ts.tzinfo is None else ts
        return ts.tz_convert("Asia/Seoul").strftime("%Y-%m-%d %H:%M KST")
    except (ValueError,TypeError): return "시각 미확인"

def stamp(response):
    if response.get("error"): st.warning(response["error"])
    if response.get("fetched_at"): st.caption(f"수집 시각 {display_time(response['fetched_at'])} · {'갱신 미확인 / 이전 자료 포함' if response.get('stale') else '조회 완료'}")

def hero(kicker,title,body):
    st.markdown(f'<div class="hero"><small>{html.escape(kicker)}</small><h2>{html.escape(title)}</h2><p>{html.escape(body)}</p></div>',unsafe_allow_html=True)

def price_chart(frame, key):
    if frame.empty: return
    show=frame.tail(130)
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=show.index,y=show.Close,name="조정 가격",line=dict(color="#147D73",width=2)))
    for n,col in [(20,"#E7A548"),(50,"#8799AB")]:
        fig.add_trace(go.Scatter(x=show.index,y=frame.Close.ewm(span=n,adjust=False).mean().tail(130),name=f"EMA {n}",line=dict(color=col,width=1)))
    fig.update_layout(height=320,margin=dict(l=5,r=5,t=10,b=10),legend=dict(orientation="h",y=1.12),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",hovermode="x unified")
    st.plotly_chart(fig,width='stretch',key=key)

def read_news(symbols,key,limit=18):
    if not symbols:
        st.info("관심종목을 먼저 등록하면 해당 종목의 뉴스를 모아볼 수 있습니다.")
        return
    symbols=list(dict.fromkeys(symbols))[:8]
    with st.spinner("종목별 뉴스를 확인하고 있습니다…"):
        response=load({"kind":"news","symbols":symbols})
    stamp(response)
    articles={}
    for symbol,payload in response["data"].items():
        for article in payload.get("items",[]):
            aid=article["id"]
            if aid not in articles: articles[aid]=dict(article,symbols=[])
            if symbol not in articles[aid]["symbols"]: articles[aid]["symbols"].append(symbol)
    if not articles: st.info("표시할 뉴스가 없습니다. 공급처 미제공 또는 조회 실패일 수 있습니다.")
    for article in sorted(articles.values(),key=lambda a:a.get("published_at") or "",reverse=True)[:limit]:
        with st.container(border=True):
            st.write(article["title"])
            st.caption(f"{article['publisher']} · {display_time(article['published_at'])}")
            cols=st.columns([3,1])
            cols[0].caption("연결 종목: " + ", ".join(label(s) for s in article["symbols"]))
            url=safe_url(article["url"])
            if url: cols[1].link_button("기사 원문",url)
            for s in article["symbols"]:
                st.button(f"{label(s)} 분석",key=f"{key}_{article['id']}_{s}",on_click=goto,args=("종목 분석",s))
    st.caption("공급처가 해당 종목에 연결한 기사입니다. 직접 언급이나 수혜를 보장하지 않습니다. 한국어 자동 번역·AI 요약은 이번 버전에 포함하지 않았습니다.")

def event_list(events,key):
    if not events: st.info("조건에 맞는 일정이 없습니다. 일정 페이지에서 조회하거나 직접 등록할 수 있습니다.")
    for event in events:
        with st.container(border=True):
            left,right=st.columns([4,1])
            left.write(f"**{event['day']}** · {event['title']}")
            if event.get("end_day") and event["end_day"]!=event["day"]: left.caption(f"예정 범위 종료: {event['end_day']}")
            left.caption(f"{event['kind']} · {event['status']} · {event['origin']}")
            if event.get("question"): left.write("확인 질문: " + event["question"])
            if safe_url(event.get("source")): left.link_button("일정 출처",event["source"])
            tracked=bool(event.get("tracked"))
            if right.button("추적 해제" if tracked else "일정 추적",key=f"{key}_{event['id']}"):
                store.track(event["id"],not tracked); st.rerun()

with st.sidebar:
    st.title("Stock Analyzer")
    st.caption(f"{VERSION} · 개인 테스트")
    st.radio("작업 공간",MENUS,key="menu",label_visibility="collapsed")
    st.divider()
    st.radio("시장",["미국","한국"],horizontal=True,key="market")
    if "symbol" not in st.session_state: st.session_state.symbol="MU"
    with st.form("search"):
        query=st.text_input("종목 바로가기",placeholder="MU / 삼성전자 / 005930.KS")
        if st.form_submit_button("종목 열기",width='stretch'):
            try:
                selected=normalize_symbol(query)
                # A callback's next run can change the navigation widget safely.
                st.session_state["pending_symbol"]=selected
                st.rerun()
            except ValueError as exc: st.error(str(exc))
    st.caption("한국 신규 종목은 .KS(코스피) 또는 .KQ(코스닥)를 함께 입력하세요.")
    if st.button("자료 다시 조회",width='stretch'):
        st.session_state.refresh_nonce=st.session_state.get("refresh_nonce",0)+1
        cached_load.clear()
        st.rerun()
    st.caption("한 PC의 사용자 1명 기준입니다. 관심종목·메모가 로컬 DB에 저장됩니다. 로그인과 외부 알림은 미연결입니다.")

def home():
    kr=st.session_state.market=="한국"
    hero("MARKET WORKSPACE", "오늘의 시장", "시장 흐름을 읽고, 내 종목에서 확인할 변화를 모읍니다.")
    specs=[("코스피","^KS11"),("코스닥","^KQ11"),("원·달러","KRW=X"),("VIX","^VIX")] if kr else [("S&P 500","^GSPC"),("나스닥 100","^NDX"),("미국 10년물","^TNX"),("VIX","^VIX")]
    with st.spinner("시장 자료를 불러옵니다…"): response=load({"kind":"prices","symbols":[s for _,s in specs]})
    stamp(response)
    for col,(name,symbol) in zip(st.columns(4),specs):
        frame=frame_of(response["data"].get(symbol,{}))
        if len(frame)>1:
            value=float(frame.Close.iloc[-1]); prev=float(frame.Close.iloc[-2])
            delta=f"{value-prev:+.2f}%p" if symbol=="^TNX" else f"{(value/prev-1)*100:+.2f}%"
            col.metric(name,f"{value:,.2f}"+("%" if symbol=="^TNX" else ""),delta,delta_color="off")
            col.caption(f"일봉 기준 {frame.index[-1].date()}")
        else: col.metric(name,"미수신")
    st.caption("Yahoo Finance · 조정 일봉 · 실시간 보장 없음 · 장중에는 당일 미완성 일봉 포함 가능")
    tab=st.radio("시장 보기",["오늘 요약","뉴스","시장환경"],horizontal=True,key="home_view")
    watches=store.watches()
    if tab=="뉴스":
        scope=st.radio("뉴스 범위",["시장 대표 종목","내 관심종목"],horizontal=True)
        symbols=[w["symbol"] for w in watches] if scope=="내 관심종목" else (["005930.KS","000660.KS"] if kr else ["SPY","QQQ"])
        read_news(symbols,"home_news")
    elif tab=="시장환경":
        st.subheader("지수 구조")
        chosen=st.selectbox("지표",[s for _,s in specs],format_func=lambda s:dict((t,n) for n,t in specs)[s])
        price_chart(frame_of(response["data"].get(chosen,{})),"macro_chart")
        macro=load({"kind":"prices","symbols":["HYG","LQD","DX-Y.NYB","GC=F","CL=F"]})
        stamp(macro)
        rows=[]
        for s,p in macro["data"].items():
            f=frame_of(p)
            if len(f)>22: rows.append({"지표":s,"기준일":str(f.index[-1].date()),"1개월 변화 %":round((f.Close.iloc[-1]/f.Close.iloc[-22]-1)*100,2)})
        st.dataframe(pd.DataFrame(rows),hide_index=True,width='stretch')
        st.caption("HYG·LQD는 회사채 ETF 가격 대용지표입니다. 실제 신용 스프레드 수치와 다릅니다.")
        st.info("관측 → 해석 → 다음 확인 조건 순서로 보세요. 이번 버전은 가격 기반 시장환경이며 경제지표 자동 수집·매크로 AI 해석은 미연결입니다.")
    else:
        main,side=st.columns([1.7,1])
        with main:
            st.subheader("오늘 확인할 것")
            primary=frame_of(response["data"].get(specs[0][1],{}))
            if len(primary)>50:
                above=primary.Close.iloc[-1]>primary.Close.rolling(50).mean().iloc[-1]
                st.write(f"**지수 구조** · {specs[0][0]}은 50일 평균 {'위' if above else '아래'}에 있습니다.")
            else: st.write("지수 자료를 확보한 뒤 추세를 확인할 수 있습니다.")
            st.write("**기업과 가격 조건** · 기업을 보는 이유와 현재의 진입 조건을 나눠 점검합니다.")
            st.button("후보 살펴보기 →",on_click=goto,args=("후보 찾기",))
            st.subheader("주요 뉴스")
            read_news(["005930.KS"] if kr else ["SPY"],"brief_news",limit=4)
            st.caption("더 많은 기사는 위의 뉴스 탭에서 확인할 수 있습니다.")
        with side:
            st.subheader("내 종목의 변화")
            if not watches: st.info("내 투자에서 첫 관심종목을 저장해보세요.")
            for w in watches[:6]:
                st.button(label(w["symbol"]),key="watchhome_"+w["symbol"],on_click=goto,args=("종목 분석",w["symbol"]))
                snapshots=store.snapshots(w["symbol"],2)
                if len(snapshots)>=2:
                    changed=[r for r in changes(snapshots[1]["payload"],snapshots[0]["payload"]) if r["변화"] is not None and abs(r["변화"])>=1]
                    st.caption(" · ".join(f"{r['항목']} {r['변화']:+.1f}" for r in changed) or "저장된 점수의 큰 변화 없음")
                elif snapshots: st.caption("첫 분석 기록 저장됨 · 비교 기록 대기")
                else: st.caption("분석 기록 없음")
            st.subheader("추적 중인 일정")
            event_list([e for e in store.events() if e["tracked"] and (e.get("end_day") or e["day"])>=date.today().isoformat()][:4],"home_event")

def discover():
    hero("DISCOVERY","후보 찾기","관찰할 기업을 좁히고, 선정 이유를 확인합니다.")
    kr=st.session_state.market=="한국"
    candidates=[s for s in NAMES if s.endswith((".KS",".KQ"))==kr]
    chosen=st.multiselect("비교할 종목 · 최대 12개",list(dict.fromkeys(candidates+[w["symbol"] for w in store.watches()])),default=candidates[:4],format_func=label)
    st.caption("대표 종목과 관심종목의 가격 비교입니다. 전체 시장 스캔이나 기업 품질 순위가 아닙니다.")
    condition=st.selectbox("조건",["전체","50일 평균 위","1개월 상승"])
    if st.button("후보 비교 실행",type="primary"):
        if not chosen: st.warning("종목을 선택하세요."); return
        response=load({"kind":"prices","symbols":chosen[:12]}); stamp(response)
        rows=[]
        for s,p in response["data"].items():
            f=frame_of(p)
            if len(f)<60: continue
            rows.append({"종목":s,"이름":NAMES.get(s,s),"기준일":str(f.index[-1].date()),"1개월 %":round((f.Close.iloc[-1]/f.Close.iloc[-22]-1)*100,2),"50일 평균 위":bool(f.Close.iloc[-1]>f.Close.rolling(50).mean().iloc[-1]),"거래량 배수":round(f.Volume.iloc[-1]/max(f.Volume.tail(20).mean(),1),2)})
        st.session_state.candidate_rows=rows
    rows=st.session_state.get("candidate_rows",[])
    rows=[r for r in rows if r["종목"] in chosen and (condition!="50일 평균 위" or r["50일 평균 위"]) and (condition!="1개월 상승" or r["1개월 %"]>0)]
    if rows:
        st.dataframe(pd.DataFrame(rows).sort_values("1개월 %",ascending=False),hide_index=True,width='stretch')
        for r in rows: st.button(f"{label(r['종목'])} 분석 →",key="candidate_"+r["종목"],on_click=goto,args=("종목 분석",r["종목"]))
    else: st.info("비교 실행 후 조건에 맞는 후보가 표시됩니다. 선택 조건에 따라 결과가 없을 수 있습니다.")

def analysis():
    symbol=st.session_state.symbol
    hero("COMPANY WORKSPACE",label(symbol),"기업의 근거, 가격 조건, 위험을 나눠 읽습니다.")
    left,right=st.columns([3,1])
    with left:
        run=st.button("실제 자료로 분석 실행",type="primary")
    with right:
        if st.button("관심종목에 추가"):
            if not any(w["symbol"]==symbol for w in store.watches()): store.save_watch(symbol)
            st.success("관심종목에 저장했습니다. 내 투자에서 이유와 질문을 작성할 수 있습니다.")
    if run:
        try:
            with st.spinner("기업·시장 자료를 조회하고 기존 엔진으로 분석합니다…"):
                corp=load({"kind":"company","symbol":symbol})
                price=load({"kind":"prices","symbols":required_symbols(symbol,corp["data"].get("info",{}))})
                result,inputs,frame=build_analysis(symbol,corp,price)
                sid=store.save_snapshot(result,inputs)
                if result["event"]: store.upsert_event(result["event"])
                st.session_state["analysis_"+symbol]=(result,frame,sid)
            st.success("분석 결과와 사용한 자료를 기록했습니다.")
        except Exception as exc: st.error(str(exc))
    active=st.session_state.get("analysis_"+symbol)
    if not active:
        rows=store.snapshots(symbol,1)
        if rows:
            saved=rows[0]["payload"]
            inputs=store.input_data(saved["input_id"])
            stored_frame=frame_of(inputs.get("price_response",{}).get("data",{}).get(symbol,{}))
            active=(saved,stored_frame,rows[0]["id"])
            st.info("마지막 저장 분석을 표시합니다. 새 분석은 위 버튼으로 실행하세요.")
        else: st.info("분석 실행을 누르면 실제 자료를 조회합니다. 가격·시장 자료가 부족하면 분석을 보류합니다."); return
    result,frame,sid=active
    st.caption(f"가격 일봉 {result['price_date']} · 분석 {display_time(result['observed_at'])} · {result['engine_version']}")
    st.caption(result["scope"])
    if result["warnings"]: st.warning(" · ".join(result["warnings"]))
    tab=st.radio("분석 보기",["종합 판단","투자 가설","진입 계획","뉴스·근거","판단 변화"],horizontal=True,key="analysis_view")
    if tab=="종합 판단":
        for col,(name,value) in zip(st.columns(4),[("기업",result["company"]["score"]),("추세",result["technical"]["trend"]),("시장환경",result["market"]["score"]),("위험 · 높을수록 주의",result["risk"]["score"])]):
            col.metric(name,"미확인" if value is None else f"{value:.1f}")
        st.subheader("현재 판단: " + result["state"])
        st.write(result["opportunity"]["interpretation"])
        st.write(result["market"]["interpretation"])
        st.caption("위 설명은 규칙에 따른 요약입니다. AI 기사 분석이나 수익 확률이 아닙니다.")
        price_chart(frame,"stock_chart")
        factors=pd.DataFrame([{"평가 항목":k,"점수":v} for k,v in result["company"]["factors"].items()])
        st.dataframe(factors,hide_index=True,width='stretch')
        st.caption(f"기업 자료 충족도 {result['company']['coverage']:.0%} · 옵션·동종기업 상대평가 미연결")
    elif tab=="투자 가설":
        st.subheader("내가 이 기업을 보는 이유")
        w=next((w for w in store.watches() if w["symbol"]==symbol),{})
        with st.form("thesis_"+symbol):
            reason=st.text_area("투자 가설 / 관심 이유",value=w.get("reason", ""))
            question=st.text_area("다음에 확인할 조건 / 반대 근거",value=w.get("question", ""))
            note=st.text_area("근거·출처·메모",value=w.get("note", ""))
            if st.form_submit_button("가설과 관심종목 저장"):
                store.save_watch(symbol,reason,question,note); st.success("저장했습니다.")
        st.caption("사용자가 작성하는 가설입니다. 자동 기업 리서치와 출처 검증은 미연결입니다.")
    elif tab=="진입 계획":
        st.info("아래는 기존 엔진이 계산한 관찰용 가격 계획입니다. 선호 방식과 실제 준비 상태는 다릅니다. 실적·자료 미확인 상태에서는 실행 판단을 보류하세요.")
        for col,key,name in zip(st.columns(2),["pullback","momentum"],["눌림목","모멘텀"]):
            plan=result["setups"][key]
            with col:
                st.subheader(name)
                st.metric("조건 점수",f"{plan['score']:.1f}")
                status_names={"READY":"조건 충족","DEVELOPING":"조건 형성 중","WATCH":"관찰","NOT IN ZONE":"관찰 구간 밖","EXTENDED":"과열 구간"}
                st.write("상태: " + status_names.get(plan["status"],plan["status"]))
                for text,field in [("관찰 진입가","entry_price"),("무효화 가격","stop_loss"),("목표 1","target1"),("목표 2","target2")]:
                    value=plan.get(field); st.write(f"{text}: {value:,.2f} {result['currency']}" if value is not None else f"{text}: 미확인")
                detail_names={"EMA Position":"평균선 위치","Market":"시장환경","Momentum Stabilization":"모멘텀 안정","Pullback Depth":"조정 깊이","Support Proximity":"지지 구간 거리","Trend Quality":"추세 상태","Volume Pattern":"거래량 흐름","Breakout":"돌파 조건","Momentum":"모멘텀","Relative Strength":"상대강도","Trend Strength":"추세 강도","Volume Confirmation":"거래량 확인"}
                for field,detail in plan["details"].items(): st.caption(f"{detail_names.get(field,field)} · {detail}")
        st.caption("보유 수량·주문 실행은 연결하지 않았습니다. 위험점수는 기존 기준이며 실적 미확인 시 기본값이 포함됩니다.")
    elif tab=="뉴스·근거":
        read_news([symbol],"stock_news")
        st.subheader("기업 자료와 분석 근거")
        with st.expander("기업 원천 수치와 자료 누락 보기"):
            st.json(result["company"])
        st.button("관련 일정으로 →",on_click=goto,args=("일정·이벤트",))
    else: render_history(symbol)
    with st.expander("현재 분석에 내 판단 남기기"):
        with st.form("decision_"+symbol):
            note=st.text_area("지금의 판단과 다음 행동 조건")
            if st.form_submit_button("판단 기록 추가"):
                try: store.decision(symbol,sid,note); st.success("당시 분석과 연결해 기록했습니다.")
                except ValueError as exc: st.error(str(exc))

def events_page():
    hero("EVENT TRACKER","일정·이벤트","발표 전 확인 질문과 다음 점검 날짜를 저장합니다.")
    symbols=list(dict.fromkeys([st.session_state.symbol]+[w["symbol"] for w in store.watches()]))
    selected=st.selectbox("실적 일정을 조회할 기업",symbols,format_func=label)
    if st.button("기업 실적 일정 조회",type="primary"):
        with st.spinner("공급처 일정을 확인합니다…"): response=load({"kind":"company","symbol":selected})
        stamp(response)
        event=earnings_event(selected,response["data"].get("calendar",{}))
        if event:
            store.upsert_event(event); st.success("공급처 예정일을 저장했습니다. 기업 IR에서 재확인하세요.")
        else: st.info("예정일을 확보하지 못했습니다. 기존 일정이 있다면 원문에서 확인하세요.")
    st.caption("자동 수집: Yahoo Finance의 기업 실적 예정일. 경제지표·제품 발표는 아래에서 출처와 함께 직접 등록합니다. 반복 알림·메일 발송은 미연결입니다.")
    with st.expander("경제·기업 일정 직접 등록"):
        with st.form("event_add"):
            title=st.text_input("일정 제목")
            day=st.date_input("발표 예정 날짜")
            kind=st.selectbox("종류",["경제지표","기업 행사","실적","개인 점검"])
            esymbol=st.selectbox("관련 종목",[""]+symbols,format_func=lambda s:label(s) if s else "시장 공통")
            source=st.text_input("확인한 출처 URL")
            status=st.selectbox("확인 상태",["예정 · 재확인 필요","공식 출처에서 날짜 확인"])
            question=st.text_area("확인할 질문")
            if st.form_submit_button("일정 저장"):
                if not title.strip(): st.error("제목을 입력하세요.")
                elif not safe_url(source) and kind!="개인 점검": st.error("공개 일정은 확인한 출처 URL이 필요합니다.")
                else:
                    try:
                        store.upsert_event({"symbol":esymbol,"title":title,"day":day.isoformat(),"end_day":day.isoformat(),"kind":kind,"source":source,"status":status,"question":question,"origin":"사용자 등록"}); st.success("일정을 저장했습니다.")
                    except ValueError as exc: st.error(str(exc))
    scope=st.radio("일정 범위",["전체","관심종목","추적 중"],horizontal=True)
    show_past=st.checkbox("지난 일정 포함")
    watched={w["symbol"] for w in store.watches()}
    rows=[e for e in store.events() if (show_past or (e.get("end_day") or e["day"])>=date.today().isoformat()) and (scope!="관심종목" or e["symbol"] in watched) and (scope!="추적 중" or e["tracked"])]
    event_list(rows,"events")

def portfolio():
    hero("MY WORKSPACE","내 투자","관심 이유와 다음 확인 조건을 남깁니다.")
    watches=store.watches()
    a,b,c=st.columns(3)
    a.metric("관심종목",len(watches)); b.metric("추적 일정",sum(e["tracked"] for e in store.events())); c.metric("저장 방식","로컬 DB")
    with st.expander("관심종목 등록",expanded=not bool(watches)):
        with st.form("watch_add"):
            symbol=st.text_input("종목명 / 티커",placeholder="삼성전자 / MU")
            reason=st.text_input("관심 이유")
            question=st.text_input("다음 확인 질문")
            if st.form_submit_button("관심종목 저장"):
                try:
                    normalized=normalize_symbol(symbol)
                    if any(w["symbol"]==normalized for w in watches): st.warning("이미 등록된 종목입니다. 아래에서 수정하세요.")
                    else: store.save_watch(normalized,reason,question); st.rerun()
                except ValueError as exc: st.error(str(exc))
    for w in watches:
        with st.container(border=True):
            st.subheader(label(w["symbol"]))
            with st.form("edit_"+w["symbol"]):
                reason=st.text_input("관심 이유",value=w["reason"])
                question=st.text_input("다음 확인 질문",value=w["question"])
                note=st.text_area("메모",value=w["note"])
                if st.form_submit_button("수정 저장"):
                    store.save_watch(w["symbol"],reason,question,note); st.success("저장했습니다.")
            st.button("종목 분석 →",key="open_"+w["symbol"],on_click=goto,args=("종목 분석",w["symbol"]))
            if st.button("관심 해제",key="remove_"+w["symbol"]): store.remove_watch(w["symbol"]); st.rerun()
    st.subheader("추적 일정")
    event_list([e for e in store.events() if e["tracked"]],"portfolio")
    st.download_button("개인 기록·분석 자료 백업",store.export(),file_name=f"stock-analyzer-{VERSION}-backup.json",mime="application/json")
    st.caption("백업에 개인 메모가 포함됩니다. 이번 버전은 내보내기를 지원하며 백업 파일 복원 UI는 미포함입니다. 보유 계좌·손익은 미연결입니다.")

def render_history(symbol):
    rows=store.snapshots(symbol)
    if not rows: st.info("분석 실행 후 기록이 표시됩니다."); return
    st.caption("실제로 실행해 저장한 분석만 표시합니다. 과거 데이터를 현재 정보로 재구성한 이력이 아닙니다.")
    if len(rows)>1:
        previous=st.selectbox("비교할 이전 분석",[r["id"] for r in rows[1:]],format_func=lambda rid:next(r["created_at"]+" · "+r["payload"]["price_date"] for r in rows if r["id"]==rid))
        prev=next(r["payload"] for r in rows if r["id"]==previous)
        st.dataframe(pd.DataFrame(changes(prev,rows[0]["payload"])),hide_index=True,width='stretch')
        st.write("이전 확인 사항: " + (" · ".join(prev["warnings"]) or "추가 확인 사항 없음"))
        st.write("현재 확인 사항: " + (" · ".join(rows[0]["payload"]["warnings"]) or "추가 확인 사항 없음"))
        if prev["engine_version"]!=rows[0]["payload"]["engine_version"]: st.warning("엔진 버전이 달라 점수 변화에 규칙 변경이 포함됩니다.")
    else: st.info("첫 분석 기록입니다. 다른 시점의 자료로 분석하면 변화 비교가 가능합니다.")
    st.dataframe(pd.DataFrame([{"기록 시각":r["created_at"],"가격 기준일":r["payload"]["price_date"],"상태":r["payload"]["state"],"엔진":r["payload"]["engine_version"],"기록 ID":r["id"]} for r in rows]),hide_index=True,width='stretch')
    st.subheader("내 판단 기록")
    for d in store.decisions(symbol):
        with st.container(border=True): st.caption(d["created_at"]+" · 분석 "+d["snapshot_id"][:8]); st.write(d["note"])

def history_page():
    hero("DECISION LEDGER","기록·검증","당시 분석을 보존하고, 판단이 달라진 이유를 확인합니다.")
    with store.connect() as db: symbols=[r[0] for r in db.execute("SELECT DISTINCT symbol FROM snapshots ORDER BY symbol")]
    if not symbols: st.info("종목 분석에서 첫 분석을 실행해보세요."); return
    symbol=st.selectbox("기록 종목",symbols,format_func=label)
    render_history(symbol)
    st.info("현재는 분석·판단 기록과 점수 변화 비교입니다. Strategy Lab, 수수료 반영 백테스트, OOS·Walk-forward 성과 검증은 아직 연결하지 않았습니다.")

{"오늘의 시장":home,"후보 찾기":discover,"종목 분석":analysis,"일정·이벤트":events_page,"내 투자":portfolio,"기록·검증":history_page}[st.session_state.menu]()
