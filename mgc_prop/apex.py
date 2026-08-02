"""Apex Trader Funding rules engine (2026, verified) + honest combine simulator.

Verified: profit target 6% of start; trailing DD $50k->$2,500, $100k->$3,000; NO daily
loss limit; consistency 50% rule is PAYOUT-only (not eval); trailing floor LOCKS to +$100
once balance reaches +(trailing+100). EOD-trailing account modelled (best for a trend
strategy - the floor does not ratchet on intraday spikes).

MGC = $10 per 1.0 gold point. Costs are charged on TURNOVER ONLY (you pay when you
trade, not for holding): commission ~$1.50/side + optional slippage/side, plus extra
slippage on forced stop-outs. Balances RELATIVE to start (=0). Intraday H/L approximate
the intraday drawdown."""

from .strategy import overlay_contracts

DPP = 10.0
COMMISSION_SIDE = 1.5

ACCOUNTS = {
    "50k":  dict(target=3000, trail=2500, cap=10),
    "100k": dict(target=6000, trail=3000, cap=14),
}


def _day_pl(signed, close, high, low, k, stop_pts, stop_slip_pts):
    """P&L ($) and intraday-min ($ vs prior balance) of holding `signed` contracts
    through day k, plus whether it stopped out. Turnover cost handled separately."""
    if signed == 0:
        return 0.0, 0.0, False
    pc = close[k - 1]
    if signed > 0:
        adverse = max(pc - low[k], 0.0); pclose = close[k] - pc
    else:
        adverse = max(high[k] - pc, 0.0); pclose = pc - close[k]
    n = abs(signed)
    stopped = adverse >= stop_pts
    stop_slip = stop_slip_pts if stopped else 0.0
    gross_pts = (-stop_pts if stopped else pclose)
    realized = (gross_pts - stop_slip) * DPP * n
    intraday_min = (-(min(adverse, stop_pts) + stop_slip)) * DPP * n
    return realized, intraday_min, stopped


def _turnover_cost(signed, signed_prev, slippage_pts):
    return abs(signed - signed_prev) * (COMMISSION_SIDE + slippage_pts * DPP)


def simulate_combine(close, high, low, signal, start_i, account,
                     stop_pts, base, safety, horizon=180,
                     slippage_pts=0.0, stop_slip_pts=0.0):
    """Trade the shifted `signal` under Apex EOD-trailing rules. Costs on turnover only.
    Returns (passed, days, reason)."""
    a = ACCOUNTS[account]
    target, trail, cap = a["target"], a["trail"], a["cap"]
    bal = 0.0; peak = 0.0; floor = -trail; locked = False; signed_prev = 0.0
    end = min(len(close), start_i + horizon)
    for k in range(max(1, start_i), end):
        c = overlay_contracts(bal - floor, stop_pts, base, safety, cap, DPP)
        signed = signal[k] * c
        tcost = _turnover_cost(signed, signed_prev, slippage_pts)
        realized, intr, stopped = _day_pl(signed, close, high, low, k, stop_pts, stop_slip_pts)
        realized -= tcost
        if bal + intr - tcost < floor:
            return (False, k - start_i + 1, "breach_trailing_drawdown")
        bal += realized
        signed_prev = 0.0 if stopped else signed
        if not locked:
            peak = max(peak, bal); floor = peak - trail
            if peak >= trail + 100:
                locked = True; floor = 100.0
        if bal >= target:
            return (True, k - start_i + 1, "hit_profit_target")
    return (False, end - start_i, "horizon_expired")


def run_forward(close, high, low, signal, start_i, account,
                stop_pts, base, safety, slippage_pts=0.0, stop_slip_pts=0.0):
    """Runs to the LAST bar and reports CURRENT status (passed/failed/in_progress)."""
    a = ACCOUNTS[account]
    target, trail, cap = a["target"], a["trail"], a["cap"]
    bal = 0.0; peak = 0.0; floor = -trail; locked = False; signed_prev = 0.0
    days = 0; today_c = 0; today_sig = 0.0
    for k in range(max(1, start_i), len(close)):
        days = k - start_i + 1; today_sig = float(signal[k])
        c = overlay_contracts(bal - floor, stop_pts, base, safety, cap, DPP); today_c = c
        signed = signal[k] * c
        tcost = _turnover_cost(signed, signed_prev, slippage_pts)
        realized, intr, stopped = _day_pl(signed, close, high, low, k, stop_pts, stop_slip_pts)
        realized -= tcost
        if bal + intr - tcost < floor:
            return dict(status="failed", reason="breach_trailing_drawdown", days=days,
                        balance=round(bal, 2), floor=round(floor, 2), peak=round(peak, 2),
                        locked=locked, today_contracts=c, today_signal=today_sig)
        bal += realized
        signed_prev = 0.0 if stopped else signed
        if not locked:
            peak = max(peak, bal); floor = peak - trail
            if peak >= trail + 100:
                locked = True; floor = 100.0
        if bal >= target:
            return dict(status="passed", reason="hit_profit_target", days=days,
                        balance=round(bal, 2), floor=round(floor, 2), peak=round(peak, 2),
                        locked=locked, today_contracts=today_c, today_signal=today_sig)
    return dict(status="in_progress", reason="", days=days, balance=round(bal, 2),
                floor=round(floor, 2), peak=round(peak, 2), locked=locked,
                target=target, today_contracts=today_c, today_signal=today_sig)
