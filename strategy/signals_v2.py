"""
strategy/signals_v2.py
----------------------
Adds three of the seven upgrades ON TOP of the parity-tested base signals,
without touching the proven logic:

  * Regime filter  — only trade when 4H ADX >= adx_min (skip chop).
  * Event stand-down — no new trades on FOMC/CPI/NFP ET days.
  * Setup pruning  — handled by the base StrategyConfig flags (enable_ny_opening,
                     use_displacement, use_fvg, enable_london_*), which the base
                     decide_at already respects; set them via env/config to drop
                     losing setups.

precompute_v2() = base precompute + adx (from 4H, merged backward, no
look-ahead) + event_day. decide_at_v2() = base decide_at, then the regime and
event gates. With require_regime=False and stand_down_events=False it is
identical to the base path.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import signals as base
from .calendar_events import is_event_day, event_label
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


@dataclass
class RegimeConfig:
    require_regime: bool = True
    adx_min: float = 20.0
    stand_down_events: bool = True
    # partial-profit / trailing (consumed by backtest/engine_v2)
    partial_frac: float = 0.5        # fraction closed at the partial level
    partial_at_r: float = 1.0        # take partial at +1R
    trail_atr_mult: float = 1.5      # trail the runner by this * ATR


def _adx(htf: pd.DataFrame, n: int = 14) -> pd.Series:
    """Wilder's ADX on the HTF series."""
    h, l, c = htf["high"], htf["low"], htf["close"]
    up = h.diff()
    dn = -l.diff()
    plus_dm = ((up > dn) & (up > 0)) * up.clip(lower=0)
    minus_dm = ((dn > up) & (dn > 0)) * dn.clip(lower=0)
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()],
                   axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / n, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def precompute_v2(df, htf, strat_cfg):
    f = base.precompute(df, htf, strat_cfg)
    if df.index.tz is None:
        df = df.tz_localize("UTC")

    # ADX from 4H, merged backward onto each M15 bar (no look-ahead)
    if htf is not None and len(htf) > 20:
        if htf.index.tz is None:
            htf = htf.tz_localize("UTC")
        adx = _adx(htf, 14)
        sig = pd.DataFrame({"ts": pd.DatetimeIndex(htf.index), "adx": adx.values})
        left = pd.DataFrame({"ts": pd.DatetimeIndex(f.index)})
        merged = pd.merge_asof(left, sig, on="ts", direction="backward")
        f["adx"] = merged["adx"].values
    else:
        f["adx"] = np.nan

    et_dates = df.index.tz_convert(ET).date
    f["event_day"] = [is_event_day(d) for d in et_dates]
    return f


def decide_at_v2(f, i, equity, trades_today, strat_cfg, risk_cfg, regime_cfg,
                 held=False, symbol="XAU_USD"):
    # Event stand-down first (cheapest gate)
    if regime_cfg.stand_down_events and bool(f.iloc[i]["event_day"]):
        return []
    # Regime gate
    if regime_cfg.require_regime:
        adx = f.iloc[i]["adx"]
        if pd.isna(adx) or adx < regime_cfg.adx_min:
            return []
    # Base logic (setup flags already applied inside)
    return base.decide_at(f, i, equity, trades_today, strat_cfg, risk_cfg, held, symbol)
