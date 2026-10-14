"""Deterministic, long-only position accounting. No data feeds or UI dependencies."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_FLOOR


def dec(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("입력값은 유한한 숫자여야 합니다.") from exc
    if not result.is_finite():
        raise ValueError("입력값은 유한한 숫자여야 합니다.")
    return result


@dataclass(frozen=True)
class Costs:
    buy_fee: float = 0.0
    sell_fee: float = 0.0
    sell_tax: float = 0.0
    slippage: float = 0.0

    def __post_init__(self):
        for value in (self.buy_fee, self.sell_fee, self.sell_tax, self.slippage):
            if not 0 <= dec(value) < 1:
                raise ValueError("비용 비율은 0 이상 1 미만이어야 합니다.")
        if dec(self.sell_fee) + dec(self.sell_tax) >= 1:
            raise ValueError("매도 수수료와 거래세 합계는 100% 미만이어야 합니다.")

    def buy_unit(self, price):
        return dec(price) * (1 + dec(self.slippage)) * (1 + dec(self.buy_fee))

    def sell_unit(self, price):
        return dec(price) * (1 - dec(self.slippage)) * (1 - dec(self.sell_fee) - dec(self.sell_tax))


class Position:
    def __init__(self, shares, average, cash, price, costs=None, core=0, recycle=True):
        self.shares, self.cash, self.price = map(dec, (shares, cash, price))
        self.core = dec(core)
        average = dec(average)
        if min(self.shares, average, self.cash, self.core) < 0 or self.price <= 0:
            raise ValueError("수량·평단·현금은 0 이상, 현재가는 0 초과여야 합니다.")
        if self.shares != self.shares.to_integral_value() or self.core != self.core.to_integral_value():
            raise ValueError("이 버전은 정수 주식 수량을 사용합니다.")
        if self.core > self.shares:
            raise ValueError("유지 수량은 초기 보유수량 이하여야 합니다.")
        self.costs = costs or Costs()
        self.basis = self.shares * average
        self.initial_book = self.basis + self.cash
        self.initial_equity = self.shares * self.price + self.cash
        if self.initial_equity <= 0:
            raise ValueError("초기 총자산이 0보다 커야 합니다.")
        self.initial_shares, self.initial_cash = self.shares, self.cash
        self.buy_budget = self.cash
        self.recycle = recycle
        self.realized = Decimal(0)
        self.fees = Decimal(0)
        self.slippage_cost = Decimal(0)
        self.trade_count = 0

    def trade(self, side, quantity, price):
        quantity, price = dec(quantity), dec(price)
        if side not in ("매수", "매도") or quantity <= 0 or price <= 0:
            raise ValueError("매수/매도, 양수 수량과 가격을 입력하세요.")
        if quantity != quantity.to_integral_value():
            raise ValueError("매매 수량은 정수여야 합니다.")
        if side == "매수":
            amount = self.costs.buy_unit(price) * quantity
            if amount > self.cash or (not self.recycle and amount > self.buy_budget):
                raise ValueError("매수 가능 현금 부족")
            self.cash -= amount
            self.buy_budget -= amount
            self.basis += amount
            self.shares += quantity
            self.fees += price * (1 + dec(self.costs.slippage)) * dec(self.costs.buy_fee) * quantity
        else:
            if quantity > self.shares - self.core:
                raise ValueError("매도 가능 수량 부족 (유지 수량 포함)")
            proceeds = self.costs.sell_unit(price) * quantity
            removed_basis = self.basis if quantity == self.shares else self.basis / self.shares * quantity
            self.realized += proceeds - removed_basis
            self.basis -= removed_basis
            self.shares -= quantity
            self.cash += proceeds
            if self.recycle:
                self.buy_budget += proceeds
            self.fees += price * (1 - dec(self.costs.slippage)) * (dec(self.costs.sell_fee) + dec(self.costs.sell_tax)) * quantity
        self.slippage_cost += price * dec(self.costs.slippage) * quantity
        self.trade_count += 1
        self.price = price

    def snapshot(self, price):
        price = dec(price)
        if price <= 0:
            raise ValueError("평가 가격은 0 초과여야 합니다.")
        equity = self.cash + self.shares * price
        liquidation = self.cash + self.shares * self.costs.sell_unit(price)
        factor = self.costs.sell_unit(1)
        average = self.basis / self.shares if self.shares else None
        remaining_be = average / factor if average is not None else None
        total_be = max(Decimal(0), (self.initial_book - self.cash) / (self.shares * factor)) if self.shares else None
        return {"가격": float(price), "보유수량": int(self.shares),
                "평균단가": float(average) if average is not None else None,
                "현금": float(self.cash), "실현손익": float(self.realized),
                "평가손익": float(self.shares * price - self.basis),
                "총자산": float(equity),
                "청산가정 총자산": float(liquidation),
                "청산가정 기간수익률(%)": float((liquidation / self.initial_equity - 1) * 100),
                "매수가능 현금": float(max(Decimal(0), min(self.cash, self.buy_budget))),
                "종목 비중(%)": float(self.shares * price / equity * 100),
                "누적 수수료·거래세": float(self.fees),
                "누적 체결오차 비용": float(self.slippage_cost),
                "누적 매매비용": float(self.fees + self.slippage_cost),
                "체결 건수": self.trade_count,
                "기간수익률(%)": float((equity / self.initial_equity - 1) * 100),
                "잔여주식 본전가": float(remaining_be) if remaining_be is not None else None,
                "전체투자 본전가": float(total_be) if total_be is not None else None,
                "청산가정 총손익": float(liquidation - self.initial_book)}


def target_average(shares, average, buy_price, target, costs=None):
    shares, average, buy_price, target = map(dec, (shares, average, buy_price, target))
    if shares <= 0 or average < 0 or buy_price <= 0 or target <= 0:
        raise ValueError("목표 평단 계산에는 양수 보유수량·매수가·목표가가 필요합니다.")
    if shares != shares.to_integral_value():
        raise ValueError("보유수량은 정수여야 합니다.")
    unit = (costs or Costs()).buy_unit(buy_price)
    if target == average:
        return 0, 0.0
    if not min(average, unit) < target < max(average, unit):
        raise ValueError("목표 평단은 기존 평단과 비용 포함 매수단가 사이여야 합니다. 경계값은 유한 수량으로 달성할 수 없습니다.")
    exact = shares * (average - target) / (target - unit)
    quantity = int(exact.to_integral_value(rounding="ROUND_CEILING"))
    return quantity, float(unit * quantity)


def affordable_shares(cash, price, costs=None):
    cash, price = dec(cash), dec(price)
    if cash < 0 or price <= 0:
        raise ValueError("자금은 0 이상, 가격은 0 초과여야 합니다.")
    return int((cash / (costs or Costs()).buy_unit(price)).to_integral_value(rounding=ROUND_FLOOR))


def position_size(account, cash, entry, stop, target, risk_pct=1, max_position_pct=100,
                  costs=None, risk_multiplier=1, gap_pct=0):
    """Size a NEW long position; all three caps apply to cost-inclusive outlay.

    Stop execution is stressed by gap_pct, then ordinary adverse slippage and
    fees are applied. This is a specified fill assumption, not a loss guarantee.
    """
    account, cash, entry, stop, target, risk_pct, max_position_pct, risk_multiplier, gap_pct = map(
        dec, (account, cash, entry, stop, target, risk_pct, max_position_pct, risk_multiplier, gap_pct))
    if account <= 0 or not 0 <= cash <= account:
        raise ValueError("계좌는 양수, 매수 가능 현금은 0 이상 계좌 평가액 이하여야 합니다.")
    if not 0 < stop < entry < target:
        raise ValueError("0 < 손절가 < 진입가 < 목표가 순서로 입력하세요.")
    if not (0 <= risk_pct <= 100 and 0 <= max_position_pct <= 100 and 0 <= risk_multiplier <= 1 and 0 <= gap_pct < 100):
        raise ValueError("손실·비중 한도는 0~100%, 위험 배율은 0~1, 추가 하락은 0~100% 미만이어야 합니다.")
    costs = costs or Costs()
    unit = costs.buy_unit(entry)
    stop_fill = stop * (1 - gap_pct / 100)
    loss = unit - costs.sell_unit(stop_fill)
    gain = costs.sell_unit(target) - unit
    budget = account * risk_pct / 100 * risk_multiplier
    caps = {"손실 한도": int(budget // loss), "현금 한도": int(cash // unit),
            "종목 비중 한도": int((account * max_position_pct / 100) // unit)}
    quantity = min(caps.values())
    return {"수량": quantity, "제한 요인": " · ".join(k for k, v in caps.items() if v == quantity),
            "손실 허용액": float(budget), "매수 투입액": float(unit * quantity),
            "남은 현금": float(cash - unit * quantity), "손절 체결 가정가": float(stop_fill),
            "주당 손실": float(loss), "주당 목표 순이익": float(gain),
            "손절 예상손실": float(loss * quantity), "목표 예상순이익": float(gain * quantity),
            "순손익비": float(gain / loss),
            "손익분기 승률(%)": float(loss / (loss + gain) * 100) if gain > 0 else None,
            "계좌 손실률(%)": float(loss * quantity / account * 100),
            "투입 비중(%)": float(unit * quantity / account * 100)}


def plan_ladder(cash, prices, weights, costs=None, reserve_pct=0):
    """Allocate a fixed cash pool across rows; unused integer-share cash is kept."""
    cash, reserve_pct = dec(cash), dec(reserve_pct)
    prices, weights = [dec(p) for p in prices], [dec(w) for w in weights]
    if cash < 0 or not 0 <= reserve_pct <= 100:
        raise ValueError("현금은 0 이상, 현금 보존 비율은 0~100%여야 합니다.")
    if not prices or len(prices) != len(weights) or any(p <= 0 for p in prices) or any(w <= 0 for w in weights):
        raise ValueError("단계마다 양수 가격과 배분 가중치를 입력하세요.")
    costs = costs or Costs()
    pool, total_weight = cash * (1 - reserve_pct / 100), sum(weights)
    rows = []
    spent = Decimal(0)
    for idx, (price, weight) in enumerate(zip(prices, weights), 1):
        budget = min(pool * weight / total_weight, pool - spent)
        q = affordable_shares(budget, price, costs)
        amount = costs.buy_unit(price) * q
        spent += amount
        rows.append({"단계": idx, "매수가": float(price), "배분 예산": float(budget),
                     "매수수량": q, "투입액": float(amount), "잔여 현금": float(cash - spent)})
    return rows


def simulate(shares, average, cash, path, rules, costs=None, core=0, recycle=True):
    """At each supplied observation, execute newly satisfied rules once, in table order.

    Fill at the observed price with adverse slippage, not at a skipped trigger.
    Starting observation only values the portfolio; it does not trigger orders.
    Rejected rules are recorded once and not retried automatically.
    """
    path = [dec(p) for p in path]
    if len(path) < 2 or any(p <= 0 for p in path):
        raise ValueError("가격 경로에는 양수 가격이 두 개 이상 필요합니다.")
    rules = list(rules)
    for rule in rules:
        if not isinstance(rule, dict) or not {"수량", "매매", "조건", "기준가격"}.issubset(rule):
            raise ValueError("규칙에는 매매·조건·기준가격·수량이 필요합니다.")
        q = dec(rule["수량"])
        if rule["매매"] not in ("매수", "매도") or rule["조건"] not in ("이하", "이상"):
            raise ValueError("규칙의 매매·조건을 확인하세요.")
        if dec(rule["기준가격"]) <= 0 or q <= 0 or q != q.to_integral_value():
            raise ValueError("규칙 가격은 양수, 수량은 양의 정수여야 합니다.")
    position = Position(shares, average, cash, path[0], costs, core, recycle)
    records, journal, used = [], [], set()
    peak = position.initial_equity
    net_peak = position.cash + position.shares * position.costs.sell_unit(path[0])
    hold_peak = peak
    mdd = Decimal(0)
    net_mdd = hold_mdd = Decimal(0)
    for step, price in enumerate(path):
        if step:
            for idx, rule in enumerate(rules):
                if idx in used:
                    continue
                trigger = dec(rule["기준가격"])
                hit = price <= trigger if rule["조건"] == "이하" else price >= trigger
                if not hit:
                    continue
                used.add(idx)
                try:
                    position.trade(rule["매매"], rule["수량"], price)
                    status = "체결"
                except ValueError as exc:
                    status = f"미체결: {exc}"
                journal.append({"단계": step, "규칙": idx + 1, **rule,
                                "관측가격": float(price), "결과": status, **position.snapshot(price)})
        snap = position.snapshot(price)
        equity = position.cash + position.shares * price
        peak = max(peak, equity)
        mdd = min(mdd, equity / peak - 1)
        net_equity = position.cash + position.shares * position.costs.sell_unit(price)
        net_peak = max(net_peak, net_equity)
        net_mdd = min(net_mdd, net_equity / net_peak - 1)
        hold_equity = position.initial_cash + position.initial_shares * price
        hold_peak = max(hold_peak, hold_equity)
        hold_mdd = min(hold_mdd, hold_equity / hold_peak - 1)
        hold_net = position.initial_cash + position.initial_shares * position.costs.sell_unit(price)
        snap.update({"단계": step, "단순보유 총자산": float(hold_equity),
                     "단순보유 청산가정 총자산": float(hold_net),
                     "청산 후 단순보유 대비": float(net_equity - hold_net),
                     "단순보유 최대낙폭(%)": float(hold_mdd * 100),
                     "청산가정 최대낙폭(%)": float(net_mdd * 100),
                     "최대낙폭(%)": float(mdd * 100)})
        records.append(snap)
    return records, journal


SCENARIOS = {
    "지속 상승": [1, 1.05, 1.12, 1.20, 1.30],
    "상승 후 눌림": [1, 1.15, 1.05, 1.22, 1.12, 1.30],
    "박스권": [1, 1.10, .98, 1.08, .96, 1.12],
    "급락": [1, .95, .85, .70, .75],
    "V자 회복": [1, .85, .70, .90, 1.10, 1.30],
}
