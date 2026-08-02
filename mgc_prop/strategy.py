"""MGC prop strategy: the validated 20/100 gold trend + a drawdown-aware overlay.
Pure, causal, unit-tested. Defaults are the config tuned against Apex $50k EOD rules.
RESEARCH ONLY - paper/backtest, human-approved, F-1 gated before any real money."""

import numpy as np
import pandas as pd

DEFAULTS = dict(ema_fast=20, ema_slow=100, stop_pts=12, base_contracts=3,
                safety=1.5, contract_cap=10)


def trend_signal(close, fast=20, slow=100):
    """+1/-1 daily trend position from an EMA cross. Causal; the CALLER shifts by 1
    day before applying it to returns (never trade on the same bar you computed on)."""
    ef = close.ewm(span=fast, adjust=False).mean()
    es = close.ewm(span=slow, adjust=False).mean()
    return np.sign(ef - es)


def overlay_contracts(room, stop_pts, base, safety, cap, dollars_per_point=10.0):
    """Position size so even a full stop-out leaves us above the trailing floor.
    room = current balance minus the failure floor ($). Returns an integer 0..cap."""
    risk = stop_pts * dollars_per_point
    if risk <= 0:
        allowed = base
    else:
        allowed = int(room / (risk * safety))
    return max(0, min(base, allowed, cap))
