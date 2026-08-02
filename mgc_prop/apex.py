"""Apex Trader Funding rules engine (2026, verified) + honest combine simulator.

Verified facts: profit target 6% of start; trailing DD $50k->$2,500, $100k->$3,000;
NO daily loss limit; consistency 50% rule is PAYOUT-only (not in eval); trailing floor
LOCKS to +$100 once balance reaches +(trailing+100). EOD-trailing account modelled
(recommended for a trend strategy: the floor does not ratchet on intraday spikes).

MGC = $10 per 1.0 gold point; ~$3 round-trip cost/contract. Balances are RELATIVE to
the starting balance (start = 0). Intraday highs/lows approximate intraday drawdown."""

import numpy as np
from .strategy import overlay_contracts

DPP = 10.0          # $ per 1.0 gold point per MGC contract
ROUND_TRIP = 3.0    # $ per contract

ACCOUNTS = {           # target, trailing, contract_cap
    "50k":  dict(target=3000, trail=2500, cap=10),
    "100k": dict(target=6000, trail=3000, cap=14),
}


def simulate_combine(close, high, low, signal, start_i, account,
                     stop_pts, base, safety, horizon=180):
    """Trade the shifted `signal` forward from start_i under Apex EOD-trailing rules.
    Returns (passed: bool, days: int, reason). No look-ahead: signal is pre-shifted."""
    a = ACCOUNTS[account]
    target, trail, cap = a["target"], a["trail"], a["cap"]
    bal = 0.0; peak = 0.0; floor = -trail; locked = False
    end = min(len(close), start_i + horizon)
    for k in range(max(1, start_i), end):
        p = signal[k]
        room = bal - floor
        c = overlay_contracts(room, stop_pts, base, safety, cap, DPP)
        if p == 0 or c == 0:
            intraday_min = bal; realized = 0.0
        else:
            pc = close[k - 1]
            if p > 0:
                adverse = max(pc - low[k], 0.0); pclose = close[k] - pc
            else:
                adverse = max(high[k] - pc, 0.0); pclose = pc - close[k]
            stopped = adverse >= stop_pts
            loss = min(adverse, stop_pts)
            realized = ((-stop_pts if stopped else pclose) * DPP - ROUND_TRIP) * c
            intraday_min = bal + (-loss * DPP - ROUND_TRIP) * c
        if intraday_min < floor:
            return (False, k - start_i + 1, "breach_trailing_drawdown")
        bal += realized
        if not locked:
            peak = max(peak, bal); floor = peak - trail
            if peak >= trail + 100:
                locked = True; floor = 100.0
        if bal >= target:
            return (True, k - start_i + 1, "hit_profit_target")
    return (False, end - start_i, "horizon_expired")
