"""
strategy/strategy.py
--------------------
Gold SMC v8 signal logic, ported verbatim from the Alpaca repo's
execution/strategy.py and decoupled from any broker.

Public surface:
  evaluate(df, htf_df, equity, trades_today, strat_cfg, risk_cfg, held=False)
      -> list[OrderIntent]

`df`     : entry-timeframe OHLCV DataFrame (tz-aware UTC index), oldest..latest.
           Only data UP TO AND INCLUDING the latest row is used — the engine
           guarantees no future bars are present, so there is no look-ahead.
`htf_df` : higher-timeframe (4H) OHLCV DataFrame, or None to fall back to a
           same-TF rolling MA for the trend filter.

Differences from the GLD version, all driven by XAU/USD being 24/5 spot:
  * London AM and US Data sessions are ENABLED by default (gold trades then).
  * `volume` is OANDA tick volume, a standard liquidity proxy for spot.
Everything else — triggers, filters, NY-opening state machine, stop/target
math — is identical to the Pine-derived Alpaca port.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from .risk import (
    RiskConfig, can_trade_today,
    long_stop_price, position_size, short_stop_price, target_price,
)

ET = ZoneInfo("America/New_York")


@dataclass
class OrderIntent:
    symbol: str
    side: Literal["buy", "sell"]
    qty: float
    reason: str
    entry_price: float
    stop_price: float
    target_price: float
    is_ny_opening: bool = False
    confidence: Optional[float] = None


@dataclass
class StrategyConfig:
    enable_london_am: bool = True      # XAU/USD: gold trades the London AM session
    enable_us_data: bool = True
    enable_london_pm: bool = True      # overlaps NY for spot; enabled
    enable_ny_opening: bool = True
    use_displacement: bool = True
    displacement_atr_mult: float = 1.2
    use_fvg: bool = True
    fvg_min_atr: float = 0.25
    require_htf_trend: bool = True
    htf_ema_length: int = 50
    require_volume: bool = True
    volume_mult: float = 1.2
    ny_use_rsi_filter: bool = True


# ─── Indicators (manual; no talib) ───────────────────────────────────────
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
    if df.index.tz is not None:
        et_date = [d.date() for d in df.index.tz_convert(ET)]
    else:
        et_date = [d.date() for d in df.index]
    grp = pd.Series(et_date, index=df.index)
    return pv.groupby(grp).cumsum() / df["volume"].groupby(grp).cumsum()


def _pivot_high(high, left=5, right=5):
    n = len(high)
    out = pd.Series([math.nan] * n, index=high.index)
    for i in range(left, n - right):
        window = high.iloc[i - left:i + right + 1]
        if high.iloc[i] == window.max() and (window == high.iloc[i]).sum() == 1:
            out.iloc[i + right] = high.iloc[i]
    return out


def _pivot_low(low, left=5, right=5):
    n = len(low)
    out = pd.Series([math.nan] * n, index=low.index)
    for i in range(left, n - right):
        window = low.iloc[i - left:i + right + 1]
        if low.iloc[i] == window.min() and (window == low.iloc[i]).sum() == 1:
            out.iloc[i + right] = low.iloc[i]
    return out


def _t_dec(ts):
    et = ts.astimezone(ET)
    return et.hour + et.minute / 60.0


def _in_london_am(ts): return 5.00 <= _t_dec(ts) < 6.50
def _in_us_data(ts):   return 8.25 <= _t_dec(ts) < 9.50
def _in_london_pm(ts): return 9.50 <= _t_dec(ts) < 10.50


def _session_active(ts, cfg):
    return ((cfg.enable_london_am and _in_london_am(ts)) or
            (cfg.enable_us_data and _in_us_data(ts)) or
            (cfg.enable_london_pm and _in_london_pm(ts)))


def _displacement_bull(row, atr, mult):
    body = abs(row.close - row.open)
    upper_wick = row.high - max(row.open, row.close)
    return row.close > row.open and body > atr * mult and body > upper_wick * 1.5


def _displacement_bear(row, atr, mult):
    body = abs(row.close - row.open)
    lower_wick = min(row.open, row.close) - row.low
    return row.close < row.open and body > atr * mult and body > lower_wick * 1.5


def _fvg_bull(df, i, atr, min_atr):
    if i < 2 or atr <= 0:
        return False
    gap = df["low"].iloc[i] - df["high"].iloc[i - 2]
    return gap > 0 and (gap / atr) > min_atr


def _fvg_bear(df, i, atr, min_atr):
    if i < 2 or atr <= 0:
        return False
    gap = df["low"].iloc[i - 2] - df["high"].iloc[i]
    return gap > 0 and (gap / atr) > min_atr


def _ny_opening_state(df):
    if df.empty or df.index.tz is None:
        return (False, False)
    today = df.index[-1].astimezone(ET).date()
    et_dates = df.index.tz_convert(ET)
    mask = pd.Series([d.date() == today for d in et_dates], index=df.index)
    today_df = df[mask]
    if today_df.empty or len(today_df) < 2:
        return (False, False)
    first_bars = today_df[[d.hour == 8 and d.minute == 0
                           for d in today_df.index.tz_convert(ET)]]
    if first_bars.empty:
        return (False, False)
    first_idx = today_df.index.get_loc(first_bars.index[0])
    if first_idx + 1 >= len(today_df):
        return (False, False)
    b1 = today_df.iloc[first_idx]
    b2 = today_df.iloc[first_idx + 1]
    bull1, bear1 = b1.close > b1.open, b1.close < b1.open
    bull2, bear2 = b2.close > b2.open, b2.close < b2.open
    return (bull1 and bull2, bear1 and bear2)


# ─── Main evaluation ─────────────────────────────────────────────────────
def evaluate(df, htf_df, equity, trades_today, strat_cfg=None, risk_cfg=None,
             held=False, symbol="XAU_USD"):
    strat_cfg = strat_cfg or StrategyConfig()
    risk_cfg = risk_cfg or RiskConfig()

    if not can_trade_today(risk_cfg, trades_today):
        return []
    if len(df) < 25:
        return []

    if df.index.tz is None:
        df = df.tz_localize("UTC")

    atr_series = _atr(df, 14)
    vol_ma = df["volume"].rolling(20).mean()
    rsi = _rsi(df["close"], 14)
    try:
        vwap = _vwap(df)
    except Exception:
        vwap = pd.Series([math.nan] * len(df), index=df.index)
    pivot_lows = _pivot_low(df["low"]).ffill()
    pivot_highs = _pivot_high(df["high"]).ffill()

    if pd.isna(atr_series.iloc[-1]):
        return []
    atr = float(atr_series.iloc[-1])
    last_swing_low = float(pivot_lows.iloc[-1]) if pd.notna(pivot_lows.iloc[-1]) else None
    last_swing_high = float(pivot_highs.iloc[-1]) if pd.notna(pivot_highs.iloc[-1]) else None

    # True HTF (4H) trend, else same-TF MA fallback
    if htf_df is not None and len(htf_df) >= strat_cfg.htf_ema_length:
        htf_closes = htf_df["close"]
        htf_ema_value = htf_closes.ewm(span=strat_cfg.htf_ema_length, adjust=False).mean().iloc[-1]
        htf_latest = htf_closes.iloc[-1]
        htf_bull = htf_latest > htf_ema_value
        htf_bear = htf_latest < htf_ema_value
    else:
        htf_ma = df["close"].rolling(strat_cfg.htf_ema_length).mean()
        htf_bull = df["close"].iloc[-1] > htf_ma.iloc[-1]
        htf_bear = df["close"].iloc[-1] < htf_ma.iloc[-1]

    last = df.iloc[-1]
    last_ts = df.index[-1].to_pydatetime()

    sess_ok = _session_active(last_ts, strat_cfg)
    disp_bull = strat_cfg.use_displacement and _displacement_bull(last, atr, strat_cfg.displacement_atr_mult)
    disp_bear = strat_cfg.use_displacement and _displacement_bear(last, atr, strat_cfg.displacement_atr_mult)
    fvg_bull_ok = strat_cfg.use_fvg and _fvg_bull(df, len(df) - 1, atr, strat_cfg.fvg_min_atr)
    fvg_bear_ok = strat_cfg.use_fvg and _fvg_bear(df, len(df) - 1, atr, strat_cfg.fvg_min_atr)

    trig_long = disp_bull or fvg_bull_ok
    trig_short = disp_bear or fvg_bear_ok

    vol_ok = (not strat_cfg.require_volume) or (
        pd.notna(vol_ma.iloc[-1]) and last.volume > vol_ma.iloc[-1] * strat_cfg.volume_mult)
    trend_long_ok = (not strat_cfg.require_htf_trend) or htf_bull
    trend_short_ok = (not strat_cfg.require_htf_trend) or htf_bear

    ny_long_armed, ny_short_armed = _ny_opening_state(df)
    ny_rsi_long_ok = (not strat_cfg.ny_use_rsi_filter) or (
        pd.notna(rsi.iloc[-1]) and 45 < rsi.iloc[-1] < 75
        and pd.notna(vwap.iloc[-1]) and last.close > vwap.iloc[-1])
    ny_rsi_short_ok = (not strat_cfg.ny_use_rsi_filter) or (
        pd.notna(rsi.iloc[-1]) and 25 < rsi.iloc[-1] < 55
        and pd.notna(vwap.iloc[-1]) and last.close < vwap.iloc[-1])
    ny_long = strat_cfg.enable_ny_opening and ny_long_armed and ny_rsi_long_ok and trend_long_ok and not held
    ny_short = strat_cfg.enable_ny_opening and ny_short_armed and ny_rsi_short_ok and trend_short_ok and not held

    reg_long = sess_ok and trig_long and trend_long_ok and vol_ok and not held
    reg_short = sess_ok and trig_short and trend_short_ok and vol_ok and not held

    is_ny_trade = ny_long or ny_short
    rr = risk_cfg.ny_opening_rr if is_ny_trade else risk_cfg.rr_target
    entry = float(last.close)

    intents: list[OrderIntent] = []

    if reg_long or ny_long:
        stop = long_stop_price(entry, atr, last_swing_low, risk_cfg)
        tgt = target_price(entry, stop, rr, "buy")
        qty = position_size(equity, entry, stop, risk_cfg)
        if qty > 0:
            intents.append(OrderIntent(
                symbol=symbol, side="buy", qty=qty,
                reason=("NY Opening 2-candle long" if ny_long
                        else f"Long: {'displacement' if disp_bull else 'FVG'}"),
                entry_price=entry, stop_price=stop, target_price=tgt,
                is_ny_opening=ny_long))

    if reg_short or ny_short:
        stop = short_stop_price(entry, atr, last_swing_high, risk_cfg)
        tgt = target_price(entry, stop, rr, "sell")
        qty = position_size(equity, entry, stop, risk_cfg)
        if qty > 0:
            intents.append(OrderIntent(
                symbol=symbol, side="sell", qty=qty,
                reason=("NY Opening 2-candle short" if ny_short
                        else f"Short: {'displacement' if disp_bear else 'FVG'}"),
                entry_price=entry, stop_price=stop, target_price=tgt,
                is_ny_opening=ny_short))

    return intents
