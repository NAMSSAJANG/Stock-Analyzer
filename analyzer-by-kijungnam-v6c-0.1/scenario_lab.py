"""Scenario UI with per-session drafts and explicit, downloadable snapshots."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scenario_engine import ScenarioInputs, evaluate, implied_growth, make_snapshot, source_defaults

DEFAULTS = dict(growth=15., margin=20., capex=10., dilution=1., multiple=12.,
                years=3, discount=10., tax=25., depreciation=5., working_capital=2.)
DEMO = dict(revenue=40000., shares=1000., net_debt=3000., price=100., currency="USD")


def _records():
    records = st.session_state.setdefault("scenario_records", [])
    with st.expander(f"내 가정 기록 · {len(records)}건", expanded=False):
        st.caption("이 브라우저 세션에서만 보관합니다. 창을 닫기 전에 JSON을 내려받으세요. 기존 History와 별도로 관리합니다.")
        if records:
            st.dataframe(pd.DataFrame([{
                "기록 시각 (UTC)": r["created_at"], "종목": r["symbol"], "통화": r["currency"],
                "성장률 (%)": r["inputs"]["growth"] * 100, "주당 모형 가치": r["result"]["value"],
                "비교 가격": r["inputs"]["price"], "메모": r["note"],
            } for r in records]), hide_index=True, width="stretch")
            st.download_button("가정 기록 JSON 내보내기", json.dumps({"schema": "scenario-records-1", "records": records},
                               ensure_ascii=False, indent=2, allow_nan=False),
                               "stock-scenarios.json", "application/json", key="sc_export")


def render_scenario_lab(symbol="", info_loader=None):
    st.header("Scenario Lab · 내 가정으로 보는 기업가치")
    st.caption("매출 성장·수익성·투자·희석을 바꾸고, 같은 조건에서 가격에 담긴 기대치를 살펴봅니다.")
    _records()
    mode = st.radio("입력 기준", ["선택 종목 / 직접 입력", "가상 예제"],
                    index=0 if symbol else 1, horizontal=True, key="sc_mode")
    demo = mode == "가상 예제"
    identity = "MODEL A" if demo else symbol or "MANUAL"
    context = f"{mode}:{identity}"
    drafts = st.session_state.setdefault("scenario_drafts", {})
    if context not in drafts:
        drafts[context] = dict(values={**DEFAULTS, **(DEMO if demo else dict(
            revenue=None, shares=None, net_debt=None, price=None, currency=""))},
            source={"kind": "fictional" if demo else "manual"})
    draft = drafts[context]
    # Model values live outside widget keys, so switching menus cannot erase a draft.
    prefix = "sc_" + hashlib.sha256(context.encode()).hexdigest()[:10] + "_"
    values = draft["values"]
    if demo:
        st.info("MODEL A · 모든 기준 자료는 가상입니다. 선택한 실제 종목과 연결되지 않습니다.")
    else:
        st.subheader(f"기준 자료 · {identity}")
        if symbol and info_loader is not None and st.button("선택 종목 자료 불러오기", key="sc_load"):
            try:
                supplied = info_loader(symbol) or {}
                if not supplied:
                    raise ValueError("공급처 자료를 받지 못했습니다. 직접 입력하거나 다시 시도하세요.")
                raw = source_defaults(supplied)
                for field in ("revenue", "shares", "net_debt", "price", "currency"):
                    values[field] = raw[field]
                    st.session_state.pop(prefix + field, None)
                draft["source"] = dict(kind="Yahoo Finance / yfinance", loaded_at=datetime.now(timezone.utc).isoformat(),
                                       supplied=raw, symbol=symbol)
            except Exception as exc:
                st.warning(f"불러오기 실패: {exc}")
        st.caption("매출·순차입금은 백만 통화단위, 주식 수는 백만 주로 입력합니다. 예: 40억 매출 → 4,000. 가격은 1주당 금액입니다.")
        supplied = draft["source"].get("supplied")
        if supplied:
            st.caption(f"재무 통화 {supplied['currency'] or '미확인'} · 가격 통화 {supplied['quote_currency'] or '미확인'} · 불러온 시각 {draft['source']['loaded_at']} (캐시 자료일 수 있음)")
            if not supplied["currency_compatible"]:
                st.warning("통화가 다르거나 확인되지 않아 비교 가격을 비웠습니다. 재무 통화로 환산한 가격을 직접 입력하세요.")
            if any(supplied[k] is None for k in ("revenue", "shares", "net_debt")):
                st.info("공급처에 없는 값은 빈칸입니다. 공시 등에서 확인 후 직접 입력하세요. 순차입금 0도 확인 후 입력합니다.")
            with st.expander("불러온 원자료와 기준시각"):
                st.json(supplied)
                st.caption("매출은 공급처 TTM 필드, 순차입금·주식 수는 현재 조회 필드입니다. mostRecentQuarter는 각 값의 동일 기준일을 보장하지 않습니다. ADR·우선주·다중 주식종류는 주식 수와 가격의 대응을 별도로 확인하세요.")

    cols = st.columns(3)
    specs = [("revenue", "기준 매출 (백만)", 0.), ("shares", "기준 주식 수 (백만 주)", 0.),
             ("net_debt", "순차입금 (백만 · 부채−현금)", None), ("price", "비교 가격 (통화/주)", 0.)]
    for index, (key, label, minimum) in enumerate(specs):
        values[key] = cols[index % 3].number_input(label, min_value=minimum, value=values[key],
                                                 format="%.4f", key=prefix + key)
    values["currency"] = cols[1].text_input("금액 통화", value=values["currency"], key=prefix + "currency").strip()
    with cols[2]:
        values["years"] = st.selectbox("예측 기간 (년)", [1, 2, 3, 5, 10],
                                       index=[1, 2, 3, 5, 10].index(values["years"]), key=prefix + "years")

    left, right = st.columns([1, 1.8], gap="large")
    with left:
        st.subheader("나의 가정")
        st.caption("초기 슬라이더 값은 편집용 예시입니다. 실제 전망·컨센서스가 아닙니다.")
        for key, label, low, high, step in [
            ("growth", "연 매출 성장률 (%)", -60., 100., 1.),
            ("margin", "영업이익률 (%)", -50., 80., 1.),
            ("capex", "CAPEX / 매출 (%)", 0., 100., 1.),
            ("dilution", "연 주식 수 증가율 (%)", 0., 50., .5),
            ("multiple", "말기 EV/EBITDA (배)", .1, 60., .1),
        ]:
            values[key] = st.slider(label, low, high, float(values[key]), step, key=prefix + key)
        with st.expander("할인율·세금·재투자 가정", expanded=False):
            for key, label, low, high in [
                ("discount", "할인율 WACC (%)", 1., 50.), ("tax", "영업이익 세율 (%)", 0., 60.),
                ("depreciation", "감가상각 / 매출 (%)", 0., 100.),
                ("working_capital", "매출 증가분 대비 운전자본 (%)", 0., 100.),
            ]:
                values[key] = st.number_input(label, min_value=low, max_value=high,
                                              value=float(values[key]), step=.5, key=prefix + key)
        approved = demo
        if not demo:
            basis = {k: values[k] for k in ("revenue", "shares", "net_debt", "price", "currency")}
            checkkey = prefix + "confirm_" + hashlib.sha256(json.dumps(basis, sort_keys=True).encode()).hexdigest()[:12]
            approved = st.checkbox("자료의 단위·기간·통화 및 주식 수 기준을 확인했습니다", key=checkkey)
    with right:
        if any(values[k] is None for k in ("revenue", "shares", "net_debt", "price")) or not values["currency"]:
            st.info("기준 매출·주식 수·순차입금·비교 가격·통화를 입력하면 계산합니다.")
            return
        if not approved:
            st.info("기준 자료를 확인하면 현재 입력에 대한 결과를 표시합니다.")
            return
        try:
            params = {k: values[k] / 100 for k in DEFAULTS if k not in ("multiple", "years")}
            params.update({k: values[k] for k in ("revenue", "shares", "net_debt", "price", "multiple", "years")})
            inputs = ScenarioInputs(**params)
            result = evaluate(inputs)
            reverse = implied_growth(inputs)
        except (ValueError, ArithmeticError) as exc:
            st.error(str(exc))
            return
        currency = values["currency"]
        st.subheader("가정에 따른 현재가치")
        m1, m2 = st.columns(2)
        m1.metric(f"주당 모형 가치 ({currency})", f"{result['value']:,.2f}")
        m2.metric("비교 가격 대비 차이", f"{result['gap_pct']:+.1f}%")
        st.caption(f"비교 가격 {inputs.price:,.2f} {currency} · 예측 기간 {inputs.years}년 · 매매 신호와 별도로 보는 가정 실험")
        if result["value"] <= 0:
            st.warning("부채 조정 후 잔여가치가 0 이하입니다. 음수 주가를 예측하는 뜻은 아닙니다.")
        if any(row["fcff"] < 0 for row in result["flows"]):
            st.warning("현금흐름이 음수인 기간이 있습니다. 추가 자금조달과 그에 따른 희석·부채 변화는 이 모형에 자동 반영되지 않습니다.")
        st.markdown("**이 가격을 설명하는 연 매출 성장률**")
        if reverse["status"] == "unique":
            st.metric("조건부 역산", f"{reverse['roots'][0] * 100:.1f}% / 년")
        elif reverse["status"] == "multiple":
            st.warning("여러 해가 있습니다: " + ", ".join(f"{g * 100:.2f}%" for g in reverse["roots"]))
        else:
            st.info("성장률 −60~100% 범위에서 단일 값을 제시할 수 없습니다. " +
                    ("가격을 만족하는 해가 없습니다." if reverse["status"] == "outside_range" else "이 조건에서는 성장률을 특정할 수 없습니다."))
        st.caption("다른 가정을 고정한 수학적 역산입니다. 시장의 유일한 기대치나 실제 컨센서스가 아닙니다.")
        flows = pd.DataFrame(result["flows"])
        chart = go.Figure()
        chart.add_trace(go.Bar(x=flows.year, y=flows.revenue, name="매출", marker_color="#90b8fc"))
        chart.add_trace(go.Scatter(x=flows.year, y=flows.fcff, name="FCFF", mode="lines+markers", line_color="#78e1ba"))
        chart.update_layout(height=300, margin=dict(l=10, r=10, t=20, b=10),
                            yaxis_title=f"백만 {currency}", xaxis_title="예측 연도", xaxis=dict(dtick=1),
                            legend=dict(orientation="h"))
        st.plotly_chart(chart, width="stretch", key=prefix + "flows")

    st.subheader("성장률 × 말기 배수 민감도")
    growths = sorted(set(max(-.6, min(1., inputs.growth + offset)) for offset in (-.10, -.05, 0., .05, .10)))
    multiples = sorted(set(max(.1, min(60., inputs.multiple + offset)) for offset in (-4., -2., 0., 2., 4.)))
    grid = [[evaluate(replace(inputs, growth=g, multiple=m))["value"] for m in multiples] for g in growths]
    heat = go.Figure(go.Heatmap(z=grid, x=[f"{m:.1f}×" for m in multiples],
                              y=[f"{g * 100:.1f}%" for g in growths], colorscale="Teal", texttemplate="%{z:,.2f}",
                              hovertemplate="성장 %{y} · 배수 %{x}<br>주당 가치 %{z:,.2f}<extra></extra>"))
    heat.update_layout(height=310, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="말기 EV/EBITDA", yaxis_title="연 성장률")
    st.plotly_chart(heat, width="stretch", key=prefix + "sensitivity")
    st.caption(f"주당 {currency} · 나머지 가정 고정 · 각 경우의 발생 확률은 계산하지 않습니다.")
    with st.expander("계산 과정·한계", expanded=False):
        st.markdown("FCFF = 영업이익 − 양수 영업이익에 대한 세금 + 감가상각 − CAPEX − 운전자본 증가. "
                    "기업가치 = 기간별 FCFF 현재가치 합 + 말기 EBITDA × 배수의 현재가치. "
                    "주당 가치 = (기업가치 − 현재 순차입금) ÷ 말기 희석 주식 수.")
        st.write("전체 현재가치를 말기 주식 수로 나누는 단순화이며, 주식 발행대금·자사주 매입·이월결손·미래 차입금 변화는 반영하지 않습니다. "
                 "성장률과 CAPEX는 독립 입력이므로 사업계획의 실현 가능성을 별도로 확인해야 합니다. 금융업·음수 EBITDA 기업에는 이 모형이 적합하지 않습니다.")
        st.dataframe(flows.rename(columns={"year": "연도", "revenue": "매출", "ebit": "영업이익", "taxes": "세금",
                                          "depreciation": "감가상각", "capex": "CAPEX", "working_capital_change": "운전자본 증가",
                                          "fcff": "FCFF", "pv_fcff": "FCFF 현재가치"}), hide_index=True, width="stretch")
        st.write({"기업가치": result["enterprise"], "FCFF 현재가치 합": result["pv_fcff"],
                  "말기 가치의 현재가치": result["terminal_pv"], "말기 주식 수 (백만)": result["diluted_shares"]})
    note = st.text_area("이 가정의 근거·틀릴 수 있는 조건", key=prefix + "note", max_chars=4000)
    if st.button("현재 가정 기록하기", type="primary", key="sc_save", disabled=len(st.session_state["scenario_records"]) >= 100):
        source = {**draft["source"], "basis": "editable inputs; see snapshot.inputs for values actually used"}
        st.session_state["scenario_records"].append(make_snapshot(inputs, identity, currency, source, note))
        st.rerun()
    st.caption("기록은 세션당 최대 100건입니다. 새 기록을 추가하며 이전 가정을 덮어쓰지 않습니다.")
    st.download_button("현재 현금흐름 CSV", flows.to_csv(index=False).encode("utf-8-sig"),
                       "scenario-cashflows.csv", "text/csv", key="sc_csv")
