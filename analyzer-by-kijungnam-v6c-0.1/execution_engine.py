"""Daily-bar, next-open long-only execution study; no network or UI.

Signals and fixed stop/target plans must be computed using signal-day data only.
Each setup is evaluated independently, with one position at a time. Statistics
describe individual trades, not a compounded or account-sized portfolio.
"""
import numpy as np
import pandas as pd

from trade_core import Costs

EXECUTION_LOGIC_VERSION = "next-open-v1"


def _daily_index(index):
    return pd.Index(pd.DatetimeIndex(pd.to_datetime(index)).date)


def run_execution_study(frame, signals, threshold=75, holding_days=20, costs=None):
    if not np.isfinite(threshold) or not 0 <= threshold <= 100:
        raise ValueError("검증 기준점수는 0~100이어야 합니다.")
    if isinstance(holding_days, bool) or int(holding_days) != holding_days or holding_days < 1:
        raise ValueError("최대 보유기간은 양의 정수여야 합니다.")
    holding_days = int(holding_days)
    required = ["Open", "High", "Low", "Close"]
    if not set(required).issubset(frame.columns):
        raise ValueError("체결 검증에는 시가·고가·저가·종가가 모두 필요합니다.")
    d = frame[required].apply(pd.to_numeric, errors="coerce").copy()
    d.index = _daily_index(d.index)
    if d.index.has_duplicates or not d.index.is_monotonic_increasing:
        raise ValueError("가격 날짜는 중복 없이 과거부터 정렬되어야 합니다.")
    if not np.isfinite(d.to_numpy()).all() or (d <= 0).any().any():
        raise ValueError("가격에 결측치나 0 이하 값이 있습니다. 체결 검증을 중단합니다.")
    if ((d.High < d[["Open", "Close", "Low"]].max(axis=1)) |
            (d.Low > d[["Open", "Close", "High"]].min(axis=1))).any():
        raise ValueError("고가·저가 범위를 벗어난 가격 데이터가 있습니다.")
    if signals.empty:
        return pd.DataFrame(), pd.DataFrame()
    if "date" not in signals:
        raise ValueError("신호 기준일이 필요합니다.")
    s = signals.copy()
    s.index = _daily_index(s["date"])
    if s.index.has_duplicates or not s.index.is_monotonic_increasing:
        raise ValueError("신호 날짜는 중복 없이 과거부터 정렬되어야 합니다.")
    if not s.index.isin(d.index).all():
        raise ValueError("가격 데이터에 없는 신호 날짜가 있습니다. 과거 검증을 다시 실행하세요.")
    costs = costs or Costs()
    positions = {day: pos for pos, day in enumerate(d.index)}
    ledger, summaries = [], []
    for setup, prefix in (("Pullback", "pullback"), ("Momentum", "momentum")):
        cols = [prefix, f"{prefix}_stop_loss", f"{prefix}_target1"]
        if not set(cols).issubset(s.columns):
            raise ValueError("손절·목표 계획이 없는 이전 검증 결과입니다. 과거 진입 검증을 다시 실행하세요.")
        last_exit = -1
        records = []
        for day, signal in s.iterrows():
            score = pd.to_numeric(signal[prefix], errors="coerce")
            if not np.isfinite(score) or score < threshold:
                continue
            i = positions[day]
            entry_pos, deadline = i + 1, i + holding_days
            row = {"Setup": setup, "신호일": day.isoformat(), "신호 점수": float(score),
                   "상태": "", "사유": ""}
            if entry_pos <= last_exit:
                row.update({"상태": "제외", "사유": "기존 포지션 보유 중"})
            elif deadline >= len(d):
                # Require the entire planned observation window, even if a recent
                # trade might already have hit a barrier. Avoid outcome selection.
                row.update({"상태": "제외", "사유": "최대 보유기간 데이터 부족"})
            else:
                stop = pd.to_numeric(signal[f"{prefix}_stop_loss"], errors="coerce")
                target = pd.to_numeric(signal[f"{prefix}_target1"], errors="coerce")
                entry = float(d.Open.iloc[entry_pos])
                row.update({"진입일": d.index[entry_pos].isoformat(), "진입 시가": entry,
                            "손절가": stop, "목표가": target})
                if not np.isfinite([stop, target]).all() or not 0 < stop < entry < target:
                    row.update({"상태": "제외", "사유": "다음 시가가 손절·목표 범위 밖 또는 계획 없음"})
                else:
                    exit_pos, exit_price, reason = deadline, float(d.Close.iloc[deadline]), "기간 종료"
                    for j in range(entry_pos, deadline + 1):
                        bar = d.iloc[j]
                        if bar.Open <= stop:
                            exit_pos, exit_price, reason = j, float(bar.Open), "손절 갭"
                        elif bar.Open >= target:
                            exit_pos, exit_price, reason = j, float(target), "목표 갭 (목표가 체결)"
                        elif bar.Low <= stop:
                            reason = "동일 봉 양쪽 도달 · 손절 우선" if bar.High >= target else "손절"
                            exit_pos, exit_price = j, float(stop)
                        elif bar.High >= target:
                            exit_pos, exit_price, reason = j, float(target), "목표"
                        else:
                            continue
                        break
                    unit = costs.buy_unit(entry)
                    proceeds = costs.sell_unit(exit_price)
                    row.update({"상태": "체결", "사유": reason,
                                "청산일": d.index[exit_pos].isoformat(), "청산 기준가": exit_price,
                                "보유 거래일": exit_pos - entry_pos + 1,
                                "비용 포함 매수단가": float(unit), "비용 차감 매도단가": float(proceeds),
                                "비용 전 수익률(%)": (exit_price / entry - 1) * 100,
                                "순수익률(%)": float((proceeds / unit - 1) * 100)})
                    last_exit = exit_pos
            records.append(row)
        ledger.extend(records)
        filled = [r for r in records if r["상태"] == "체결"]
        returns = pd.Series([r["순수익률(%)"] for r in filled], dtype=float)
        summaries.append({"Setup": setup, "기준 이상 신호": len(records), "체결 사례": len(filled),
                          "제외 사례": len(records) - len(filled),
                          "순이익 사례 비율(%)": float((returns > 0).mean() * 100) if len(returns) else np.nan,
                          "평균 순수익률(%)": returns.mean(), "중앙값 순수익률(%)": returns.median(),
                          "최저 순수익률(%)": returns.min()})
    return pd.DataFrame(ledger), pd.DataFrame(summaries)
