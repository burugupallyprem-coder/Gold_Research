"""
strategy/macro_trend.py
-----------------------
Gold Macro-Trend strategy — the documented-premium replacement for SMC.

Three ingredients, each with real empirical support:
  1. TIME-SERIES MOMENTUM (trend): long when gold is in an uptrend
     (EMA(fast) > EMA(slow)) AND 12-month momentum agrees; short when both
     point down. (Moskowitz, Ooi, Pedersen 2012.)
  2. REAL-YIELD MACRO FILTER: gold's strongest fundamental driver is the 10y
     real yield (TIPS / FRED DFII10). Allow longs only when real-yield momentum
     is flat/falling; allow shorts only when it is rising.
  3. VOLATILITY TARGETING: scale the position so its annualized volatility ≈ a
     fixed target. (Moreira & Muir 2017 — reliably improves risk-adjusted return.)

compute_weights(prices, ry, cfg) -> DataFrame with the daily target weight and
its components. No look-ahead here; the backtester lags the weight by one day
before applying returns.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

ANN = 252


@dataclass
class MacroConfig:
    ema_fast: int = 50
    ema_slow: int = 200
    mom_lookback: int = 252      # 12-month time-series momentum
    use_mom_confirm: bool = True
    use_macro: bool = True
    ry_mom_lookback: int = 60    # change in real yield over ~3 months
    ry_threshold: float = 0.0    # falling/flat real yields => gold tailwind
    vol_lookback: int = 20
    target_vol: float = 0.10     # 10% annualized
    max_leverage: float = 3.0


def compute_weights(prices: pd.DataFrame, ry: pd.Series | None,
                    cfg: MacroConfig) -> pd.DataFrame:
    px = prices["close"].astype(float)
    f = pd.DataFrame(index=px.index)
    f["close"] = px

    ema_f = px.ewm(span=cfg.ema_fast, adjust=False).mean()
    ema_s = px.ewm(span=cfg.ema_slow, adjust=False).mean()
    trend = np.sign(ema_f - ema_s)                      # +1 / -1
    mom = px / px.shift(cfg.mom_lookback) - 1.0
    if cfg.use_mom_confirm:
        direction = np.where((trend > 0) & (mom > 0), 1,
                    np.where((trend < 0) & (mom < 0), -1, 0))
    else:
        direction = trend.fillna(0).astype(int).values
    f["direction"] = direction

    # Real-yield macro gate
    if cfg.use_macro and ry is not None:
        ry_al = ry.reindex(px.index).ffill()
        ry_mom = ry_al - ry_al.shift(cfg.ry_mom_lookback)
        macro_long_ok = (ry_mom <= cfg.ry_threshold).fillna(False).values
        macro_short_ok = (ry_mom > cfg.ry_threshold).fillna(False).values
        f["ry"] = ry_al.values
        f["ry_mom"] = ry_mom.values
    else:
        macro_long_ok = np.ones(len(px), dtype=bool)
        macro_short_ok = np.ones(len(px), dtype=bool)
        f["ry"] = np.nan
        f["ry_mom"] = np.nan

    pos_dir = np.where((f["direction"].values > 0) & macro_long_ok, 1,
              np.where((f["direction"].values < 0) & macro_short_ok, -1, 0))
    f["pos_dir"] = pos_dir

    # Volatility targeting
    realized = px.pct_change().rolling(cfg.vol_lookback).std() * np.sqrt(ANN)
    scale = (cfg.target_vol / realized).clip(upper=cfg.max_leverage)
    scale = scale.replace([np.inf, -np.inf], np.nan)
    f["realized_vol"] = realized.values
    f["weight"] = (pos_dir * scale).fillna(0.0).values
    return f
