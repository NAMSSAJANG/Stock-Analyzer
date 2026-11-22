from __future__ import annotations

from goldnam_engine.models import (
    MarketRegimeSnapshot,
    PriceZone,
    SetupScore,
    SetupSnapshot,
    TechnicalSnapshot,
)
from goldnam_engine.risk.current import RiskState
from goldnam_engine.scoring.scoring_utils import clip, scale, weighted
from goldnam_engine.strategy import STRATEGY as C
from goldnam_engine.timing.sr_engine import ZoneSet


def _nearest_support(zones: ZoneSet) -> PriceZone | None:
    return zones.supports[0] if zones.supports else None


def _nearest_resistance(zones: ZoneSet) -> PriceZone | None:
    return zones.resistances[0] if zones.resistances else None


def _targets_from_resistance(
    entry_ref: float, zones: ZoneSet, atr: float, mult1: float, mult2: float
) -> tuple[float, float]:
    """Pick 1st/2nd target prices above entry_ref from known resistance zones,
    falling back to ATR multiples when structure is not available so a target
    is always shown rather than left blank."""
    above = [z for z in zones.resistances if z.center > entry_ref]
    t1 = above[0].center if above else entry_ref + max(atr, entry_ref * 0.004) * mult1
    remaining = [z for z in above if z.center > t1 + atr * 0.3]
    t2 = (
        remaining[0].center
        if remaining
        else max(t1 + atr * (mult2 - mult1), entry_ref + atr * mult2)
    )
    return t1, t2


def _risk_reward(entry_ref: float, stop: float | None, target: float) -> float | None:
    if stop is None:
        return None
    risk = entry_ref - stop
    if risk <= 0:
        return None
    return round((target - entry_ref) / risk, 2)


def build_setups(
    now: float,
    tech: TechnicalSnapshot,
    market: MarketRegimeSnapshot,
    zones: ZoneSet,
    risk: RiskState,
    expected_r: dict[str, float] | None = None,
) -> SetupSnapshot:
    zones = structural_zones(zones)
    support = _nearest_support(zones)
    resistance = _nearest_resistance(zones)

    if support:
        support_distance_atr = abs(now - support.center) / max(tech.atr, 1e-9)
        support_proximity = clip(100 - support_distance_atr * 34 + (support.strength - 50) * 0.20)
    else:
        support_distance_atr = 99
        support_proximity = 35.0

    ema_position = weighted(
        [
            (scale(abs(tech.dist_ema20_atr), 0, 2.3, reverse=True), 0.60),
            (scale(abs(tech.dist_ema50_atr), 0, 3.5, reverse=True), 0.40),
        ]
    )
    drawdown_abs = abs(tech.drawdown_from_high60)
    # Healthy pullbacks are usually neither zero nor deep breakdowns. Reward a
    # moderate 4~7% reset instead of treating deeper drawdowns as automatically better.
    depth = clip(100 - abs(drawdown_abs - 5.5) * 12)
    if drawdown_abs < 1.0:
        depth = min(depth, 35.0)
    elif drawdown_abs > 16:
        depth = min(depth, 25.0)
    volume_pullback = scale(tech.volume_ratio, 0.55, 1.10, reverse=True)
    if tech.last_day_return > 0 and tech.volume_ratio >= 1.0:
        volume_pullback = max(volume_pullback, 68)
    # Pullback stabilization differs from momentum strength: mid-range RSI and
    # decelerated-but-intact momentum are desirable here.
    rsi_stable = clip(100 - abs(tech.rsi - 52) * 4.0)
    momentum_reset = clip(100 - abs(tech.momentum - 55) * 1.8)
    momentum_stable = weighted([(rsi_stable, 0.55), (momentum_reset, 0.45)])
    pull_factors = {
        "Trend Quality": tech.trend,
        "Support Proximity": support_proximity,
        "EMA Position": ema_position,
        "Pullback Depth": depth,
        "Volume Pattern": volume_pullback,
        "Momentum Stabilization": momentum_stable,
        "Market": market.score,
    }
    pull_score = weighted(
        [
            (pull_factors["Trend Quality"], 0.20),
            (pull_factors["Support Proximity"], 0.25),
            (pull_factors["EMA Position"], 0.15),
            (pull_factors["Pullback Depth"], 0.15),
            (pull_factors["Volume Pattern"], 0.10),
            (pull_factors["Momentum Stabilization"], 0.10),
            (pull_factors["Market"], 0.05),
        ]
    )
    invalidation = (
        support.low - tech.atr * C.stop_buffer_atr
        if support
        else min(tech.ema50, now - tech.atr * 1.5)
    )
    if tech.trend < C.pull_invalid_trend or now < tech.ema200:
        pull_status = "INVALIDATED"
    elif risk.extension in ("High", "Extreme") and support_distance_atr > C.extension_outside_atr:
        pull_status = "NOT IN ZONE"
    elif pull_score >= C.pull_ready and support_distance_atr <= C.support_ready_atr:
        pull_status = "READY"
    elif pull_score >= C.pull_developing:
        pull_status = "DEVELOPING"
    elif support_distance_atr > C.support_outside_atr:
        pull_status = "NOT IN ZONE"
    else:
        pull_status = "STRUCTURE WARNING" if tech.trend < C.pull_warning_trend else "NOT IN ZONE"

    breakout20 = (now / max(tech.prior_high20, 1e-9) - 1) * 100
    breakout60 = (now / max(tech.prior_high60, 1e-9) - 1) * 100
    breakout = weighted(
        [
            (scale(breakout20, -4, 4), 0.45),
            (scale(breakout60, -5, 5), 0.55),
        ]
    )
    if now >= tech.prior_high60 and tech.volume_ratio >= 1.2:
        breakout = max(breakout, 86)
    volume_confirm = weighted([(scale(tech.volume_ratio, 0.7, 2.0), 0.75), (tech.demand, 0.25)])
    mom_factors = {
        "Trend Strength": tech.trend,
        "Breakout": breakout,
        "Momentum": tech.momentum,
        "Volume Confirmation": volume_confirm,
        "Relative Strength": tech.relative_strength,
        "Market": market.score,
    }
    # One price-trend lens; do not count momentum and relative strength twice.
    mom_score = weighted(
        [(tech.trend, 0.35), (breakout, 0.40), (volume_confirm, 0.20), (market.score, 0.05)]
    )
    trigger = tech.prior_high60
    mom_invalidation = min(trigger - tech.atr * 0.65, tech.ema20 - tech.atr * 0.35)
    if tech.trend < C.momentum_failed and breakout < C.momentum_failed:
        mom_status = "FAILED BREAKOUT"
    elif risk.extension in ("High", "Extreme") and mom_score >= C.momentum_extended:
        mom_status = "EXTENDED"
    elif (
        mom_score >= C.momentum_confirmed
        and now >= trigger
        and tech.volume_ratio >= C.confirmed_volume
    ):
        mom_status = "CONFIRMED"
    elif (
        mom_score >= C.momentum_early and now >= tech.prior_high20 and breakout >= C.early_breakout
    ):
        mom_status = "EARLY BREAKOUT"
    else:
        mom_status = "WATCH"

    pull_details = {
        "Target source": "저항 Zone"
        if any(z.center > (support.center if support else now) for z in zones.resistances)
        else "구조 없음 · ATR 기준",
        "Trend Quality": f"Trend {tech.trend:.1f}",
        "Support Proximity": f"가까운 지지까지 {support_distance_atr:.2f} ATR"
        if support
        else "신뢰 가능한 지지 Zone 부족",
        "EMA Position": f"EMA20 {tech.dist_ema20_atr:+.2f} ATR · EMA50 {tech.dist_ema50_atr:+.2f} ATR",
        "Pullback Depth": f"60일 고점 대비 {tech.drawdown_from_high60:.1f}%",
        "Volume Pattern": f"20일 평균 대비 거래량 {tech.volume_ratio:.2f}x",
        "Momentum Stabilization": f"RSI {tech.rsi:.1f} · Momentum {tech.momentum:.1f}",
        "Market": f"{market.label} {market.score:.1f}",
    }
    mom_details = {
        "Target source": "저항 Zone"
        if any(z.center > max(now, trigger) for z in zones.resistances)
        else "구조 없음 · ATR 기준",
        "Trend Strength": f"Trend {tech.trend:.1f}",
        "Breakout": f"20D {breakout20:+.1f}% · 60D {breakout60:+.1f}%",
        "Momentum": f"Momentum {tech.momentum:.1f} · RSI {tech.rsi:.1f}",
        "Volume Confirmation": f"거래량 {tech.volume_ratio:.2f}x · Demand {tech.demand:.1f}",
        "Relative Strength": f"시장 대비 RS {tech.relative_strength:.1f}",
        "Market": f"{market.label} {market.score:.1f}",
    }
    pull_entry_ref = support.center if support else now
    pull_target1, pull_target2 = _targets_from_resistance(pull_entry_ref, zones, tech.atr, 2.2, 3.8)
    pull_risk_pct = (
        (pull_entry_ref - invalidation) / pull_entry_ref * 100 if pull_entry_ref > 0 else None
    )
    pull = SetupScore(
        "Pullback",
        round(clip(pull_score), 1),
        pull_status,
        pull_factors,
        pull_details,
        invalidation=round(invalidation, 4),
        zone=(support.low, support.high) if support else None,
        entry_price=round(pull_entry_ref, 4),
        stop_loss=round(invalidation, 4),
        target1=round(pull_target1, 4),
        target2=round(pull_target2, 4),
        risk_reward1=_risk_reward(pull_entry_ref, invalidation, pull_target1),
        risk_reward2=_risk_reward(pull_entry_ref, invalidation, pull_target2),
        risk_pct=round(pull_risk_pct, 2) if pull_risk_pct is not None else None,
    )

    mom_entry_ref = max(now, trigger)
    mom_target1, mom_target2 = _targets_from_resistance(mom_entry_ref, zones, tech.atr, 2.5, 4.2)
    mom_risk_pct = (
        (mom_entry_ref - mom_invalidation) / mom_entry_ref * 100 if mom_entry_ref > 0 else None
    )
    momentum = SetupScore(
        "Momentum",
        round(clip(mom_score), 1),
        mom_status,
        mom_factors,
        mom_details,
        trigger=round(trigger, 4),
        invalidation=round(mom_invalidation, 4),
        zone=(resistance.low, resistance.high) if resistance else None,
        entry_price=round(mom_entry_ref, 4),
        stop_loss=round(mom_invalidation, 4),
        target1=round(mom_target1, 4),
        target2=round(mom_target2, 4),
        risk_reward1=_risk_reward(mom_entry_ref, mom_invalidation, mom_target1),
        risk_reward2=_risk_reward(mom_entry_ref, mom_invalidation, mom_target2),
        risk_pct=round(mom_risk_pct, 2) if mom_risk_pct is not None else None,
    )

    preferred = "비교 근거 없음"
    if expected_r:
        eligible = {
            key: value
            for key, value in expected_r.items()
            if key in {"pullback", "momentum"}
            and actionable(pull if key == "pullback" else momentum)
        }
        if eligible:
            preferred = max(eligible, key=lambda key: eligible[key])
    return SetupSnapshot(
        pull,
        momentum,
        preferred,
        "눌림목을 기다리는 구간"
        if momentum.status == "EXTENDED"
        else "상태별 과거 기대값을 확인하세요",
    )


def actionable(setup: SetupScore) -> bool:
    return setup.status in {"READY", "DEVELOPING", "CONFIRMED", "EARLY BREAKOUT"}


def structural_zones(zones: ZoneSet) -> ZoneSet:
    return ZoneSet(
        tuple(z for z in zones.supports if set(z.sources) - {"EMA20"}), zones.resistances
    )
