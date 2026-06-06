"""
strategy/features.py
--------------------
Vectorized, single-pass precomputation of every input the signal logic needs,
plus a scalar per-bar decision function. This is the SAME logic as
strategy.evaluate(), just computed once over the whole series instead of
re-derived on a rolling window every bar — which makes a multi-year M15
backtest run in seconds instead of timing out.

A correctness test (tests/test_parity.py) checks that decide_at() reproduces
evaluate() bar-for-bar, so there is no silent divergence between the fast
backtest path and the live path.

No look-ahead: every column at row i uses only information available at or
before bar i. Pivots are placed at i+right (confirmed only after `right`
future bars), HTF is merged backward (htf_time <= bar_time), FVG/displacement
use the closed bar and earlier bars.
"""

from __future__ import annotations

import math
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .strategy import StrategyConfig, OrderIntent
from .risk import (RiskConfig, long_stop_price, short_stop_price,
                   target_price, position_size)

ET = ZoneInfo("America/New_York")


def _atr(df, length=14):
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(length).mean()


def _rsi(close, length=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(length).mean()
    loss = -delta.clip(upper=0).rolling(length).mean()
    rs = gain / loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def _vwap(df):
    typical = (df["high"] + df["low"] + df["close"]) / 3
    pv = typical * df["volume"]
    et_date = pd.Series(df.index.tz_convert(ET).date, index=df.index)
    return pv.groupby(et_date).cumsum() / df["volume"].groupby(et_date).cumsum()


def _pivots_once(arr, left=5, right=5, kind="high"):
    """Single pass over the FULL series. Value placed at i+right (confirmation
    bar), matching the windowed _pivot_* in strategy.py."""
    n = len(arr)
    out = np.full(n, np.nan)
    for i in range(left, n - right):
        w = arr[i - left:i + right + 1]
        c = arr[i]
        if kind == "high":
            if c == w.max() and (w == c).sum() == 1:
                out[i + right] = c
        else:
            if c == w.min() and (w == c).sum() == 1:
                out[i + right] = c
    return out


def _t_dec_arr(idx):
    et = idx.tz_convert(ET)
    return et.hour + et.minute / 60.0


def precompute(df: pd.DataFrame, htf: pd.DataFrame | None,
               strat_cfg: StrategyConfig) -> pd.DataFrame:
    if df.index.tz is None:
        df = df.tz_localize("UTC")
    f = pd.DataFrame(index=df.index)
    for c in ("open", "high", "low", "close", "volume"):
        f[c] = df[c].values

    f["atr"] = _atr(df, 14).values
    f["vol_ma"] = df["volume"].rolling(20).mean().values
    f["rsi"] = _rsi(df["close"], 14).values
    f["vwap"] = _vwap(df).values
    f["swing_low"] = pd.Series(_pivots_once(df["low"].values, kind="low"),
                               index=df.index).ffill().values
    f["swing_high"] = pd.Series(_pivots_once(df["high"].values, kind="high"),
                                index=df.index).ffill().values

    # HTF trend (4H EMA) merged backward; fallback to same-TF MA
    if htf is not None and len(htf) >= strat_cfg.htf_ema_length:
        if htf.index.tz is None:
            htf = htf.tz_localize("UTC")
        ema = htf["close"].ewm(span=strat_cfg.htf_ema_length, adjust=False).mean()
        htf_sig = pd.DataFrame({"ts": pd.DatetimeIndex(htf.index),
                                "htf_close": htf["close"].values,
                                "htf_ema": ema.values})
        left = pd.DataFrame({"ts": pd.DatetimeIndex(f.index)})
        merged = pd.merge_asof(left, htf_sig, on="ts", direction="backward")
        f["htf_bull"] = (merged["htf_close"].values > merged["htf_ema"].values)
        f["htf_bear"] = (merged["htf_close"].values < merged["htf_ema"].values)
    else:
        ma = df["close"].rolling(strat_cfg.htf_ema_length).mean()
        f["htf_bull"] = (df["close"] > ma).values
        f["htf_bear"] = (df["close"] < ma).values

    # Displacement (vectorized, row-wise)
    body = (f["close"] - f["open"]).abs()
    upper_wick = f["high"] - f[["open", "close"]].max(axis=1)
    lower_wick = f[["open", "close"]].min(axis=1) - f["low"]
    m = strat_cfg.displacement_atr_mult
    f["disp_bull"] = ((f["close"] > f["open"]) & (body > f["atr"] * m) &
                      (body > upper_wick * 1.5)) if strat_cfg.use_displacement else False
    f["disp_bear"] = ((f["close"] < f["open"]) & (body > f["atr"] * m) &
                      (body > lower_wick * 1.5)) if strat_cfg.use_displacement else False

    # FVG (3-bar gap)
    if strat_cfg.use_fvg:
        gap_bull = f["low"] - f["high"].shift(2)
        gap_bear = f["low"].shift(2) - f["high"]
        f["fvg_bull"] = (gap_bull > 0) & ((gap_bull / f["atr"]) > strat_cfg.fvg_min_atr)
        f["fvg_bear"] = (gap_bear > 0) & ((gap_bear / f["atr"]) > strat_cfg.fvg_min_atr)
    else:
        f["fvg_bull"] = False
        f["fvg_bear"] = False

    # Sessions (ET)
    t = _t_dec_arr(df.index)
    in_lam = (t >= 5.00) & (t < 6.50)
    in_usd = (t >= 8.25) & (t < 9.50)
    in_lpm = (t >= 9.50) & (t < 10.50)
    f["sess_ok"] = ((strat_cfg.enable_london_am & pd.Series(in_lam, index=df.index)) |
                    (strat_cfg.enable_us_data & pd.Series(in_usd, index=df.index)) |
                    (strat_cfg.enable_london_pm & pd.Series(in_lpm, index=df.index)))

    # NY opening 2-candle arming, per ET day, gated to bars at/after the 8:15 bar
    f["ny_long_armed"] = False
    f["ny_short_armed"] = False
    et = df.index.tz_convert(ET)
    et_day = pd.Series(et.date, index=df.index)
    hr = pd.Series(et.hour, index=df.index)
    mn = pd.Series(et.minute, index=df.index)
    pos = {ts: k for k, ts in enumerate(df.index)}
    for day, day_idx in df.groupby(et_day).groups.items():
        day_idx = list(day_idx)
        eight = [ts for ts in day_idx if hr[ts] == 8 and mn[ts] == 0]
        if not eight:
            continue
        b1 = eight[0]
        p1 = day_idx.index(b1)
        if p1 + 1 >= len(day_idx):
            continue
        b2 = day_idx[p1 + 1]
        bull = (f.at[b1, "close"] > f.at[b1, "open"]) and (f.at[b2, "close"] > f.at[b2, "open"])
        bear = (f.at[b1, "close"] < f.at[b1, "open"]) and (f.at[b2, "close"] < f.at[b2, "open"])
        if not (bull or bear):
            continue
        b2_pos = pos[b2]
        for ts in day_idx:
            if pos[ts] >= b2_pos:                      # armed only after 8:15 forms
                f.at[ts, "ny_long_armed"] = bull
                f.at[ts, "ny_short_armed"] = bear
    return f


def decide_at(f: pd.DataFrame, i: int, equity: float, trades_today: int,
              strat_cfg: StrategyConfig, risk_cfg: RiskConfig,
              held: bool = False, symbol: str = "XAU_USD") -> list:
    """Scalar decision for bar i using precomputed features. Mirrors the tail
    of strategy.evaluate()."""
    if trades_today >= risk_cfg.max_trades_per_day:
        return []
    r = f.iloc[i]
    atr = r["atr"]
    if pd.isna(atr):
        return []
    swing_low = None if pd.isna(r["swing_low"]) else float(r["swing_low"])
    swing_high = None if pd.isna(r["swing_high"]) else float(r["swing_high"])

    trig_long = bool(r["disp_bull"]) or bool(r["fvg_bull"])
    trig_short = bool(r["disp_bear"]) or bool(r["fvg_bear"])

    vol_ok = (not strat_cfg.require_volume) or (
        pd.notna(r["vol_ma"]) and r["volume"] > r["vol_ma"] * strat_cfg.volume_mult)
    trend_long_ok = (not strat_cfg.require_htf_trend) or bool(r["htf_bull"])
    trend_short_ok = (not strat_cfg.require_htf_trend) or bool(r["htf_bear"])

    ny_rsi_long_ok = (not strat_cfg.ny_use_rsi_filter) or (
        pd.notna(r["rsi"]) and 45 < r["rsi"] < 75
        and pd.notna(r["vwap"]) and r["close"] > r["vwap"])
    ny_rsi_short_ok = (not strat_cfg.ny_use_rsi_filter) or (
        pd.notna(r["rsi"]) and 25 < r["rsi"] < 55
        and pd.notna(r["vwap"]) and r["close"] < r["vwap"])
    ny_long = (strat_cfg.enable_ny_opening and bool(r["ny_long_armed"])
               and ny_rsi_long_ok and trend_long_ok and not held)
    ny_short = (strat_cfg.enable_ny_opening and bool(r["ny_short_armed"])
                and ny_rsi_short_ok and trend_short_ok and not held)

    reg_long = bool(r["sess_ok"]) and trig_long and trend_long_ok and vol_ok and not held
    reg_short = bool(r["sess_ok"]) and trig_short and trend_short_ok and vol_ok and not held

    is_ny = ny_long or ny_short
    rr = risk_cfg.ny_opening_rr if is_ny else risk_cfg.rr_target
    entry = float(r["close"])
    atr = float(atr)
    intents = []

    if reg_long or ny_long:
        stop = long_stop_price(entry, atr, swing_low, risk_cfg)
        tgt = target_price(entry, stop, rr, "buy")
        qty = position_size(equity, entry, stop, risk_cfg)
        if qty > 0:
            intents.append(OrderIntent(
                symbol=symbol, side="buy", qty=qty,
                reason=("NY Opening 2-candle long" if ny_long
                        else f"Long: {'displacement' if bool(r['disp_bull']) else 'FVG'}"),
                entry_price=entry, stop_price=stop, target_price=tgt,
                is_ny_opening=ny_long))

    if reg_short or ny_short:
        stop = short_stop_price(entry, atr, swing_high, risk_cfg)
        tgt = target_price(entry, stop, rr, "sell")
        qty = position_size(equity, entry, stop, risk_cfg)
        if qty > 0:
            intents.append(OrderIntent(
                symbol=symbol, side="sell", qty=qty,
                reason=("NY Opening 2-candle short" if ny_short
                        else f"Short: {'displacement' if bool(r['disp_bear']) else 'FVG'}"),
                entry_price=entry, stop_price=stop, target_price=tgt,
                is_ny_opening=ny_short))

    return intents
