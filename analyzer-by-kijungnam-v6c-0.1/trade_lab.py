"""Streamlit UI for the independent Trade Lab accounting engine."""
import json
import pandas as pd
import streamlit as st

from trade_core import (Costs, Position, SCENARIOS, affordable_shares, dec,
                          plan_ladder, position_size, simulate, target_average)


def _signature(*values):
    return json.dumps(values, ensure_ascii=False, sort_keys=True, default=str)


def _saved(key, signature):
    result = st.session_state.get(key)
    if result and result[0] != signature:
        st.info("계산 조건이 바뀌었습니다. 계산 버튼을 눌러 결과를 갱신하세요.")
        return None
    return result[1] if result else None


def _download(label, rows, filename, key):
    st.download_button(label, pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig"),
                       filename, "text/csv", key=key)


def _risk_lab(price, cash, initial, costs, currency):
    st.subheader("손실 한도 · 비용 포함 매수 수량")
    st.caption("새로 진입할 물량만 계산합니다. 기존 보유분의 손실 위험은 포함하지 않으며, 모든 금액은 위에서 선택한 통화 기준입니다.")
    c = st.columns(3)
    account = c[0].number_input("전체 계좌 평가액", min_value=.01, value=float(initial.initial_equity), key="tl_account")
    available = c[1].number_input("이번 진입에 쓸 수 있는 현금", min_value=0.0, value=float(cash), key="tl_available")
    allocation = c[2].number_input("이번 진입의 최대 투입 비중 (%)", 0.0, 100.0, 25.0, 1.0, key="tl_allocation")
    c = st.columns(3)
    entry = c[0].number_input("신규 진입가", min_value=.01, value=float(price), key="tl_entry")
    stop = c[1].number_input("신규 손절가", min_value=.01, value=max(.01, price * .9), key="tl_stop")
    take = c[2].number_input("신규 목표가", min_value=.01, value=price * 1.2, key="tl_take")
    c = st.columns(3)
    risk_pct = c[0].number_input("계좌 대비 손실 허용 (%)", 0.0, 100.0, 1.0, .1, key="tl_risk_pct")
    gap = c[1].number_input("손절가보다 추가 하락 체결 (%)", 0.0, 99.0, 0.0, .5, key="tl_gap")
    win = c[2].number_input("직접 가정한 목표 도달 비율 (%)", 0.0, 100.0, 50.0, 1.0, key="tl_win")
    try:
        result = position_size(account, available, entry, stop, take, risk_pct, allocation, costs, gap_pct=gap)
    except ValueError as exc:
        st.info(str(exc))
        return
    c = st.columns(4)
    c[0].metric("계산 수량", f'{result["수량"]:,}주')
    c[1].metric("손절 예상손실", f'{result["손절 예상손실"]:,.2f} {currency}')
    c[2].metric("비용 포함 순손익비", f'{result["순손익비"]:.2f}')
    be = result["손익분기 승률(%)"]
    c[3].metric("손익분기 승률", f"{be:.1f}%" if be is not None else "목표 순이익 없음")
    st.write(f'수량 제한 요인: **{result["제한 요인"]}** · 투입액 **{result["매수 투입액"]:,.2f} {currency}** · 남은 현금 **{result["남은 현금"]:,.2f} {currency}**')
    expected = (win / 100 * result["주당 목표 순이익"] - (1 - win / 100) * result["주당 손실"]) * result["수량"]
    st.write(f"입력한 비율을 가정한 1회 기대손익: **{expected:,.2f} {currency}**")
    if result["주당 목표 순이익"] <= 0:
        st.warning("목표가에서 매도해도 거래비용 때문에 순이익이 남지 않습니다.")
    st.caption("수량은 손실 한도·현금·최대 투입 비중으로 각각 계산한 값 중 최솟값입니다. 손익분기 승률과 기대손익은 목표가 또는 손절가에서 전량 정리하는 두 결과만 가정합니다. 입력한 도달 비율은 예측값이 아닙니다. 급락 시 실제 손실은 체결 가정보다 커질 수 있습니다.")
    _download("위험 계산 CSV 저장", [{"통화": currency, "계좌 평가액": account, "가용 현금": available,
        "진입가": entry, "손절가": stop, "목표가": take, "손실 허용(%)": risk_pct,
        "투입 비중 상한(%)": allocation, "손절 추가 하락(%)": gap,
        "매수 수수료율": costs.buy_fee, "매도 수수료율": costs.sell_fee, "매도세율": costs.sell_tax,
        "체결오차율": costs.slippage, **result, "가정 도달 비율(%)": win, "가정 기대손익": expected}], "trade_lab_risk.csv", "tl_risk_csv")


def _ladder_lab(shares, average, cash, price, costs, currency):
    st.subheader("분할매수 예산 배분 · 추가 하락 점검")
    st.caption("가격과 배분 가중치를 입력하면 비용을 포함한 정수 수량을 계산합니다. 가중치 1·2·3은 예산을 1:2:3으로 나누며, 각 단계의 남는 돈은 현금으로 보관합니다.")
    c = st.columns(2)
    reserve = c[0].number_input("시작 현금 중 반드시 남길 비율 (%)", 0.0, 100.0, 20.0, 5.0, key="tl_reserve")
    stress = c[1].number_input("계획 이후 하락 점검 가격", min_value=.01, value=max(.01, price * .7), key="tl_stress")
    ladder = st.data_editor(pd.DataFrame([
        {"매수가": max(.01, round(price * factor, 2)), "배분 가중치": 1.0}
        for factor in (1, .95, .9)
    ]), num_rows="dynamic", hide_index=True, key="tl_ladder", column_config={
        "매수가": st.column_config.NumberColumn(min_value=.01, required=True),
        "배분 가중치": st.column_config.NumberColumn(min_value=.01, required=True)})
    try:
        rows = plan_ladder(cash, ladder["매수가"], ladder["배분 가중치"], costs, reserve)
        p = Position(shares, average, cash, price, costs)
        hold = Position(shares, average, cash, price, costs)
        hold_stress = hold.snapshot(stress)["청산가정 총자산"]
        states = []
        for row in rows:
            if row["매수수량"]:
                p.trade("매수", row["매수수량"], row["매수가"])
            stressed = p.snapshot(stress)
            snap = p.snapshot(price)
            states.append({**row, "누적 보유수량": int(p.shares), "평균단가": snap["평균단가"],
                           "청산 본전가": snap["잔여주식 본전가"],
                           "하락 시 청산 총자산": stressed["청산가정 총자산"],
                           "시작 평가액 대비 손익": stressed["청산가정 총자산"] - float(p.initial_equity),
                           "하락 시 단순보유 대비": stressed["청산가정 총자산"] - hold_stress})
        st.dataframe(pd.DataFrame(states), hide_index=True, width="stretch")
        st.caption(f"각 행은 그 단계까지만 매수가 체결된 상태입니다. 이후 점검 가격 {stress:,.2f} {currency}에서 잔여주식을 모두 매도하는 비용을 반영합니다. 가격 도달·전량 체결을 가정하며, 분할매수가 손실을 줄인다고 보장하지 않습니다.")
        stress_rows = []
        for move in (-40, -30, -20, -10, 0, 10, 20):
            mark = dec(price) * (1 + dec(move) / 100)
            s, h = p.snapshot(mark), hold.snapshot(mark)
            stress_rows.append({"현재가 대비 변동(%)": move, "평가가격": float(mark),
                                "분할매수 후 청산자산": s["청산가정 총자산"],
                                "단순보유 청산자산": h["청산가정 총자산"],
                                "차이": s["청산가정 총자산"] - h["청산가정 총자산"]})
        st.line_chart(pd.DataFrame(stress_rows).set_index("현재가 대비 변동(%)")[["분할매수 후 청산자산", "단순보유 청산자산"]])
        st.caption("그래프는 모든 단계가 체결된 최종 보유 상태를 평가가격별로 비교합니다. 가격 경로 시뮬레이션과는 별개입니다.")
        _download("분할매수 계획 CSV 저장", [{"통화": currency, **row} for row in states], "trade_lab_ladder.csv", "tl_ladder_csv")
    except (ValueError, TypeError, ArithmeticError) as exc:
        st.info(f"분할매수 입력값을 확인하세요: {exc}")


def render_trade_lab():
    st.header("Trade Lab · 분할매매 실험실")
    st.caption("수량·평단·현금·총자산을 함께 비교합니다. 종목 검색 없이 사용할 수 있으며 모든 금액은 선택한 한 통화 기준입니다.")
    currency = st.selectbox("계산 통화", ["USD", "KRW"], key="tl_currency")
    cols = st.columns(4)
    shares = cols[0].number_input("보유수량 (주)", min_value=0, value=20, step=1, key="tl_shares")
    average = cols[1].number_input("기존 평균단가", min_value=0.0, value=100.0, key="tl_average")
    price = cols[2].number_input("현재가 / 시작가", min_value=0.01, value=70.0, key="tl_price")
    cash = cols[3].number_input("시작 현금 (추가매수 자금 포함)", min_value=0.0, value=1400.0, key="tl_cash")
    st.caption(f"단위: {currency}. 기존 평균단가는 매수비용을 포함한 값으로 입력하세요. 시작 현금은 모든 비교 전략에 똑같이 적용합니다. 통화 선택은 단위 표시이며 금액을 자동 환전하지 않습니다.")
    with st.expander("수수료·거래세·체결 오차"):
        c = st.columns(4)
        bf = c[0].number_input("매수 수수료 (%)", 0.0, 10.0, 0.0, .01, key="tl_bf")
        sf = c[1].number_input("매도 수수료 (%)", 0.0, 10.0, 0.0, .01, key="tl_sf")
        tax = c[2].number_input("매도금액 기준 거래세 (%)", 0.0, 10.0, 0.0, .01, key="tl_tax")
        slip = c[3].number_input("불리한 체결 오차 (%)", 0.0, 10.0, 0.0, .01, key="tl_slip")
        st.caption("기본 비용은 0이므로 적용할 값을 직접 입력하세요. 거래세는 매도대금 기준이며 양도소득세 계산은 포함하지 않습니다. 환율·배당·주식분할·이자는 반영하지 않습니다.")
    costs = Costs(dec(bf) / 100, dec(sf) / 100, dec(tax) / 100, dec(slip) / 100)
    try:
        initial = Position(shares, average, cash, price, costs)
    except ValueError as exc:
        st.info(str(exc))
        return
    base_signature = _signature(currency, shares, average, price, cash, bf, sf, tax, slip)
    overview = initial.snapshot(price)
    c = st.columns(3)
    c[0].metric("시작 평가자산", f'{overview["총자산"]:,.2f} {currency}')
    c[1].metric("지금 청산 시 총자산", f'{overview["청산가정 총자산"]:,.2f} {currency}')
    c[2].metric("시작 종목 비중", f'{overview["종목 비중(%)"]:.1f}%')
    calculator, scenario, target, risk_tab, ladder_tab = st.tabs([
        "매매 계산 · 물타기/불타기", "시나리오 · 단순보유 비교", "목표 평단 · 수량 늘리기",
        "손실 한도 · 순손익비", "분할매수 · 하락 점검"])
    with calculator:
        st.subheader("계획한 순서대로 매수·매도")
        st.caption("표 위에서 아래로 실행합니다. 가격과 수량을 수정하거나 행을 추가하세요. 현금·수량이 부족한 주문은 전량 미체결 처리합니다.")
        orders = st.data_editor(pd.DataFrame([{"매매": "매수", "가격": float(price), "수량": 1}]),
            num_rows="dynamic", hide_index=True, key="tl_orders",
            column_config={"매매": st.column_config.SelectboxColumn(options=["매수", "매도"], required=True),
                           "가격": st.column_config.NumberColumn(min_value=.01, required=True),
                           "수량": st.column_config.NumberColumn(min_value=1, step=1, required=True)})
        mark = st.number_input("매매 후 평가할 가격", min_value=.01, value=float(price), key="tl_mark")
        signature = _signature(base_signature, orders.to_dict("records"), mark)
        if st.button("매매 계획 계산", type="primary", key="tl_calc"):
            p = Position(shares, average, cash, price, costs)
            rows = [{"순서": 0, "결과": "시작", **p.snapshot(price)}]
            for idx, row in enumerate(orders.to_dict("records"), 1):
                try:
                    p.trade(row["매매"], row["수량"], row["가격"])
                    status = f'{row["매매"]} 체결'
                except (ValueError, TypeError, ArithmeticError) as exc:
                    status = f"미체결: {exc}"
                rows.append({"순서": idx, "매매": row["매매"], "주문가격": row["가격"], "주문수량": row["수량"], "결과": status, **p.snapshot(mark)})
            st.session_state["tl_calc_result"] = (signature, (rows, p.snapshot(mark)))
        saved = _saved("tl_calc_result", signature)
        if saved is not None:
            rows, last = saved
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            hold = initial.snapshot(mark)
            c = st.columns(3)
            c[0].metric("단순보유 대비 총자산 차이", f'{last["총자산"] - hold["총자산"]:,.2f} {currency}')
            c[1].metric("청산 후 단순보유 대비", f'{last["청산가정 총자산"] - hold["청산가정 총자산"]:,.2f} {currency}')
            c[2].metric("발생한 매매비용", f'{last["누적 매매비용"]:,.2f} {currency}')
            _download("매매 계산 CSV 저장", [{"통화": currency, **row} for row in rows], "trade_lab_orders.csv", "tl_orders_csv")
            st.caption("평가손익은 잔여주식의 비용 포함 원가 기준입니다. 매도해도 잔여주식 평단은 유지됩니다. 전체투자 본전가는 누적 실현손익과 남은 현금을 포함하고, 잔여주식 본전가는 보유주식만의 청산비용을 포함합니다.")
    with scenario:
        st.subheader("같은 시작 자산으로 전략 비교")
        core = st.number_input("매도하지 않고 유지할 수량", min_value=0, max_value=shares, value=0, key=f"tl_core_{shares}")
        st.caption("각 규칙은 시작 이후 조건이 처음 충족된 관측점에서 한 번만 처리됩니다. 같은 단계에서는 표 순서로 처리하고, 미체결 주문도 자동 재시도하지 않습니다.")
        rules = st.data_editor(pd.DataFrame([
            {"매매": "매도", "조건": "이상", "기준가격": round(price * 1.10, 2), "수량": max(1, shares // 5)},
            {"매매": "매수", "조건": "이하", "기준가격": round(price * .95, 2), "수량": max(1, shares // 4)},
            {"매매": "매수", "조건": "이하", "기준가격": round(price * .85, 2), "수량": max(1, shares // 4)},
        ]), num_rows="dynamic", hide_index=True, key="tl_rules",
            column_config={"매매": st.column_config.SelectboxColumn(options=["매수", "매도"], required=True),
                           "조건": st.column_config.SelectboxColumn(options=["이하", "이상"], required=True),
                           "기준가격": st.column_config.NumberColumn(min_value=.01, required=True),
                           "수량": st.column_config.NumberColumn(min_value=1, step=1, required=True)})
        custom = st.text_input("직접 가격 경로 (선택 · 쉼표로 구분, 첫 가격은 시작가)", placeholder="70, 80, 65, 85, 60, 90", key="tl_path")
        signature = _signature(base_signature, core, rules.to_dict("records"), custom)
        st.caption("조건가격을 건너뛰면 실제 관측가격에 체결 오차를 더해 계산합니다. 관측점 사이의 움직임과 일중 고저가는 추정하지 않습니다. 이는 가정 시나리오이며 과거 주가 백테스트나 확률 예측이 아닙니다.")
        if st.button("5가지 시나리오 비교", type="primary", key="tl_sim"):
            paths = {name: [dec(price) * dec(x) for x in multipliers] for name, multipliers in SCENARIOS.items()}
            try:
                if custom.strip():
                    values = [dec(x.strip()) for x in custom.split(",")]
                    if not values or values[0] != dec(price):
                        raise ValueError("직접 경로의 첫 가격은 현재가 / 시작가와 같아야 합니다.")
                    paths["직접 경로"] = values
                summary = []
                details = []
                for name, path in paths.items():
                    for strategy, recycle, active in [("단순보유", False, []), ("분할매매 · 매도금 보관", False, rules.to_dict("records")), ("분할매매 · 매도금 재사용", True, rules.to_dict("records"))]:
                        records, journal = simulate(shares, average, cash, path, active, costs, core, recycle)
                        end = records[-1]
                        summary.append({"시나리오": name, "전략": strategy, "통화": currency,
                            **{k: end[k] for k in ["보유수량", "평균단가", "현금", "총자산", "청산가정 총자산", "실현손익", "기간수익률(%)", "청산가정 기간수익률(%)", "최대낙폭(%)", "청산가정 최대낙폭(%)", "누적 매매비용", "체결 건수", "청산 후 단순보유 대비"]},
                            "미체결 건수": sum(j["결과"].startswith("미체결") for j in journal),
                            "단순보유 대비": end["총자산"] - end["단순보유 총자산"]})
                        details.append((name, strategy, records, journal))
                st.session_state["tl_sim_result"] = (signature, (summary, details))
            except (ValueError, TypeError, ArithmeticError) as exc:
                st.session_state.pop("tl_sim_result", None)
                st.error(f"입력값을 확인해 주세요: {exc}")
        saved = _saved("tl_sim_result", signature)
        if saved is not None:
            summary, details = saved
            st.dataframe(pd.DataFrame(summary), hide_index=True, width="stretch")
            _download("비교 결과 CSV 저장", summary, "trade_lab_scenarios.csv", "tl_sim_csv")
            all_journal = [{"시나리오": name, "전략": strategy, "통화": currency, **row}
                           for name, strategy, _, journal in details for row in journal]
            if all_journal:
                _download("전체 체결·미체결 내역 CSV 저장", all_journal, "trade_lab_journal.csv", "tl_journal_csv")
            for name, strategy, records, journal in details:
                if strategy == "단순보유":
                    continue
                with st.expander(f"{name} · {strategy} · 경로와 매매 내역"):
                    history = pd.DataFrame(records).set_index("단계")
                    st.line_chart(history[["청산가정 총자산", "단순보유 청산가정 총자산"]])
                    st.dataframe(history, width="stretch")
                    st.dataframe(pd.DataFrame(journal), hide_index=True, width="stretch") if journal else st.caption("조건을 충족한 주문이 없습니다.")
            st.caption("기간수익률의 분모는 시작 시가평가 총자산입니다. 청산가정 값은 남은 주식의 매도비용까지 차감합니다. 누적 매매비용은 실제 처리된 주문의 수수료·거래세·체결오차 합계이며, 초기 보유분의 과거 비용과 미래 청산비용은 별도입니다. 최대낙폭은 각 관측점의 자산을 기준으로 계산하며 관측점 사이의 하락은 포함하지 않습니다.")
    with target:
        st.subheader("목표 평단과 필요한 자금")
        c = st.columns(2)
        buy_price = c[0].number_input("추가매수 예정가격", min_value=.01, value=float(price), key="tl_target_buy")
        target_avg = c[1].number_input("목표 평균단가", min_value=.01, value=max(.01, (average + price) / 2), key="tl_target_avg")
        try:
            quantity, required = target_average(shares, average, buy_price, target_avg, costs)
            st.write(f"목표 평단에 도달하거나 넘어서는 최소 수량: **{quantity:,}주** · 필요 자금 **{required:,.2f} {currency}** · 현금 외 추가 필요 **{max(0, required - cash):,.2f} {currency}**")
        except ValueError as exc:
            st.info(str(exc))
        goal = st.number_input("목표 보유수량", min_value=1, value=max(1, shares + 10), key="tl_goal")
        need = max(0, goal - shares)
        required = float(costs.buy_unit(buy_price)) * need
        st.write(f"추가 {need:,}주 · 필요 자금 {required:,.2f} {currency} · 현재 목표 달성률 {shares / goal * 100:.1f}%")
        st.subheader("일부 매도 후 재매수로 수량 늘리기")
        c = st.columns(3)
        sell_q = c[0].number_input("먼저 매도할 수량", min_value=0, max_value=shares, value=min(shares, 4), key=f"tl_sell_q_{shares}")
        sell_price = c[1].number_input("예정 매도가", min_value=.01, value=price * 1.1, key="tl_sell_price")
        rebuy = c[2].number_input("예정 재매수가", min_value=.01, value=float(price), key="tl_rebuy")
        proceeds = costs.sell_unit(sell_price) * sell_q
        bought = affordable_shares(proceeds, rebuy, costs)
        st.write(f"매도대금만 재사용 시 {bought:,}주 재매수 → 최종 {shares - sell_q + bought:,}주 ({bought - sell_q:+,}주), 잔액 {proceeds - costs.buy_unit(rebuy) * bought:,.2f} {currency}")
        st.caption("매도 후 예정 재매수가가 오지 않으면 재매수되지 않습니다. 위 결과는 두 가격에서 모두 체결된다는 가정입니다.")
        st.subheader("물타기·불타기 자금별 회복 비교")
        recovery = []
        for fraction in (0, .25, .5, .75, 1):
            budget = cash * fraction
            q = affordable_shares(budget, buy_price, costs)
            p = Position(shares, average, cash, price, costs)
            if q:
                p.trade("매수", q, buy_price)
            snap = p.snapshot(price)
            be = snap["잔여주식 본전가"]
            recovery.append({"현금 사용 비율(%)": fraction * 100, "추가수량": q,
                "실제 투입액": float(costs.buy_unit(buy_price)) * q,
                "새 평단": snap["평균단가"], "평가손익": snap["평가손익"],
                "종목 평가금액": snap["보유수량"] * price,
                "본전가": be, "본전 필요 변동률(%)": (be / price - 1) * 100 if be is not None else None})
        st.dataframe(pd.DataFrame(recovery), hide_index=True, width="stretch")
        st.caption("평단이 낮아져도 투자금과 하락 노출은 커질 수 있습니다. 본전 도달 날짜는 예측하지 않으며 필요한 가격 변동만 계산합니다.")
    with risk_tab:
        _risk_lab(price, cash, initial, costs, currency)
    with ladder_tab:
        _ladder_lab(shares, average, cash, price, costs, currency)
