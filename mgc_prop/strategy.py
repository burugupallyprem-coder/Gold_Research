"""MGC prop strategy: long-only gold trend + drawdown overlay + validated EXECUTION plan
(chandelier ATR-trailing exit + re-entry on a new high). Pure, causal, unit-tested.
Defaults tuned against Apex $50k EOD rules. RESEARCH ONLY - paper/backtest, F-1 gated.

Execution plan (largest improvement observed so far; pending forward confirmation):
  - LONG-ONLY (short side was a net loser and deepened drawdown).
  - CHANDELIER exit: leave when close < running-high-since-entry - atr_k x ATR(14).
  - RE-ENTRY: after a chandelier exit, re-enter only when price makes a NEW high while the
    trend is still up (recovers continuation missed by a whipsaw exit; robust in both regimes)."""

import numpy as np
import pandas as pd

DEFAULTS = dict(ema_fast=20, ema_slow=100, stop_pts=12, base_contracts=3,
                safety=1.5, contract_cap=10, atr_k=2.5, long_only=True)


def trend_signal(close, fast=20, slow=100):
    """+1/-1 raw EMA-cross trend (kept for reference/tests). Caller shifts before use."""
    ef = close.ewm(span=fast, adjust=False).mean()
    es = close.ewm(span=slow, adjust=False).mean()
    return np.sign(ef - es)


def atr(high, low, close, n=14):
    pc = close.shift(1)
    tr = pd.concat([(high - low), (high - pc).abs(), (low - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def trend_position(close, high, low, fast=20, slow=100, atr_k=2.5, long_only=True):
    """FAILED EXPERIMENT (kept for the record). Chandelier ATR-trailing exit + re-entry.
    When tested STRICTLY CAUSALLY it did NOT beat plain long-only (exit on flip) - the
    earlier apparent gain was a look-ahead artifact in a throwaway test script. The live
    strategy uses long-only trend_signal, NOT this. Causal up to each bar; caller shifts."""
    up = (close.ewm(span=fast, adjust=False).mean()
          > close.ewm(span=slow, adjust=False).mean()).values
    a = atr(high, low, close).values
    c = close.values; h = high.values
    pos = np.zeros(len(close)); p = 0; ehigh = 0.0; stopped = False; exit_high = 0.0
    for i in range(len(close)):
        if p == 0:
            if up[i]:
                if stopped:
                    if c[i] > exit_high:          # re-enter only on a fresh new high
                        p = 1; ehigh = h[i]; stopped = False
                else:
                    p = 1; ehigh = h[i]
            else:
                stopped = False
                if not long_only:
                    p = -1; ehigh = -low.values[i]  # (symmetric mode, unused by default)
        else:
            ehigh = max(ehigh, h[i])
            if not up[i]:
                p = 0; stopped = False
            elif not np.isnan(a[i]) and c[i] < ehigh - atr_k * a[i]:
                p = 0; stopped = True; exit_high = ehigh   # chandelier exit -> allow re-entry
        pos[i] = p
    return pd.Series(pos, index=close.index)


def overlay_contracts(room, stop_pts, base, safety, cap, dollars_per_point=10.0):
    """Position size so even a full stop-out leaves us above the trailing floor.
    room = current balance minus the failure floor ($). Returns an integer 0..cap."""
    risk = stop_pts * dollars_per_point
    allowed = base if risk <= 0 else int(room / (risk * safety))
    return max(0, min(base, allowed, cap))
