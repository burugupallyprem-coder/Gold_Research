"""
strategy/signals.py
-------------------
FINAL vectorized precompute + scalar decision. Identical signal logic to
strategy.evaluate(), computed once over the whole series. Proven bar-for-bar
equal to evaluate() by tests/parity_final.py (including the HTF warmup region).

Key faithfulness detail: evaluate() uses the 4H EMA trend ONLY when at least
`htf_ema_length` HTF bars exist up to the current bar; before that it falls
back to an M15 rolling-MA trend. precompute() replicates that per-bar gate via
a cumulative HTF-bar count, so there is no warmup-period divergence.

No look-ahead: rolling/ewm are causal; pivots are placed at i+right; HTF is
merged backward (htf_time <= bar_time).
"""

from __future__ import annotations

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


def precompute(df, htf, strat_cfg):
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

    L = strat_cfg.htf_ema_length
    # M15 rolling-MA fallback trend (used where HTF data is insufficient)
    ma = df["close"].rolling(L).mean()
    fb_bull = (df["close"] > ma).values
    fb_bear = (df["close"] < ma).values

    if htf is not None and len(htf) >= 1:
        if htf.index.tz is None:
            htf = htf.tz_localize("UTC")
        ema = htf["close"].ewm(span=L, adjust=False).mean()
        htf_sig = pd.DataFrame({"ts": pd.DatetimeIndex(htf.index),
                                "htf_close": htf["close"].values,
                                "htf_ema": ema.values})
        left = pd.DataFrame({"ts": pd.DatetimeIndex(f.index)})
        merged = pd.merge_asof(left, htf_sig, on="ts", direction="backward")
        h_close = merged["htf_close"].values
        h_ema = merged["htf_ema"].values
        # how many HTF bars exist up to each M15 bar (htf_index <= ts)
        htf_count = np.searchsorted(htf.index.values, df.index.values, side="right")
        use_htf = htf_count >= L
        htf_bull_h = h_close > h_ema
        htf_bear_h = h_close < h_ema
        f["htf_bull"] = np.where(use_htf, htf_bull_h, fb_bull)
        f["htf_bear"] = np.where(use_htf, htf_bear_h, fb_bear)
    else:
        f["htf_bull"] = fb_bull
        f["htf_bear"] = fb_bear

    body = (f["close"] - f["open"]).abs()
    upper_wick = f["high"] - f[["open", "close"]].max(axis=1)
    lower_wick = f[["open", "close"]].min(axis=1) - f["low"]
    m = strat_cfg.displacement_atr_mult
    if strat_cfg.use_displacement:
        f["disp_bull"] = ((f["close"] > f["open"]) & (body > f["atr"] * m) &
                          (body > upper_wick * 1.5))
        f["disp_bear"] = ((f["close"] < f["open"]) & (body > f["atr"] * m) &
                          (body > lower_wick * 1.5))
    else:
        f["disp_bull"] = False
        f["disp_bear"] = False

    if strat_cfg.use_fvg:
        gap_bull = f["low"] - f["high"].shift(2)
        gap_bear = f["low"].shift(2) - f["high"]
        f["fvg_bull"] = (gap_bull > 0) & ((gap_bull / f["atr"]) > strat_cfg.fvg_min_atr)
        f["fvg_bear"] = (gap_bear > 0) & ((gap_bear / f["atr"]) > strat_cfg.fvg_min_atr)
    else:
        f["fvg_bull"] = False
        f["fvg_bear"] = False

    et = df.index.tz_convert(ET)
    t = et.hour + et.minute / 60.0
    in_lam = pd.Series((t >= 5.00) & (t < 6.50), index=df.index)
    in_usd = pd.Series((t >= 8.25) & (t < 9.50), index=df.index)
    in_lpm = pd.Series((t >= 9.50) & (t < 10.50), index=df.index)
    f["sess_ok"] = ((strat_cfg.enable_london_am & in_lam) |
                    (strat_cfg.enable_us_data & in_usd) |
                    (strat_cfg.enable_london_pm & in_lpm))

    f["ny_long_armed"] = False
    f["ny_short_armed"] = False
    et_day = pd.Series(et.date, index=df.index)
    hr = pd.Series(et.hour, index=df.index)
    mn = pd.Series(et.minute, index=df.index)
    pos = {ts: k for k, ts in enumerate(df.index)}
    for day, grp in df.groupby(et_day).groups.items():
        day_idx = list(grp)
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
            if pos[ts] >= b2_pos:
                f.at[ts, "ny_long_armed"] = bull
                f.at[ts, "ny_short_armed"] = bear
    return f


def decide_at(f, i, equity, trades_today, strat_cfg, risk_cfg,
              held=False, symbol="XAU_USD"):
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
