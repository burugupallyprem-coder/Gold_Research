"""The document's strategies as STRICTLY CAUSAL daily position generators.
Each returns a position (+1/0/-1) DECIDED at each bar's close using only prior-bar rolling
windows + the current close; the runner shifts(1) before trading (so a signal at close of
day t is traded day t+1). Look-ahead audited after the chandelier bug: every rolling
extreme is .shift(1) (prior N bars), never includes the same bar it gates.

Strategies: Donchian 20/10, Turtle 55/20, EMA-cross 10/30, EMA-cross 20/100 (our baseline),
Bollinger reversion (mean-reversion), Bollinger squeeze breakout (vol-expansion)."""

import numpy as np
import pandas as pd


def _channel(close, high, low, n_in, n_out):
    hh = high.rolling(n_in).max().shift(1).values
    ll = low.rolling(n_in).min().shift(1).values
    xh = high.rolling(n_out).max().shift(1).values
    xl = low.rolling(n_out).min().shift(1).values
    c = close.values
    pos = np.zeros(len(close)); p = 0
    for i in range(len(close)):
        if p == 0:
            if not np.isnan(hh[i]) and c[i] > hh[i]: p = 1
            elif not np.isnan(ll[i]) and c[i] < ll[i]: p = -1
        elif p == 1:
            if not np.isnan(xl[i]) and c[i] < xl[i]: p = 0
        elif p == -1:
            if not np.isnan(xh[i]) and c[i] > xh[i]: p = 0
        pos[i] = p
    return pd.Series(pos, index=close.index)


def donchian(close, high, low):   return _channel(close, high, low, 20, 10)
def turtle(close, high, low):     return _channel(close, high, low, 55, 20)


def ema_cross(close, high, low, fast=10, slow=30):
    ef = close.ewm(span=fast, adjust=False).mean()
    es = close.ewm(span=slow, adjust=False).mean()
    return np.sign(ef - es)            # decided at close t; runner shifts(1)


def ema_cross_20_100(close, high, low):
    return ema_cross(close, high, low, 20, 100)


def bollinger_revert(close, high, low, n=20, k=2.0):
    mid = close.ewm(span=n, adjust=False).mean()
    sd = close.rolling(n).std()
    up = (mid + k * sd).shift(1).values; lo = (mid - k * sd).shift(1).values
    mv = mid.shift(1).values; c = close.values
    pos = np.zeros(len(close)); p = 0
    for i in range(len(close)):
        if np.isnan(mv[i]): pos[i] = 0; continue
        if p == 0:
            if c[i] < lo[i]: p = 1          # oversold -> long (fade)
            elif c[i] > up[i]: p = -1        # overbought -> short (fade)
        elif p == 1 and c[i] >= mv[i]: p = 0
        elif p == -1 and c[i] <= mv[i]: p = 0
        pos[i] = p
    return pd.Series(pos, index=close.index)


def bollinger_squeeze(close, high, low, n=20, k=2.0):
    mid = close.ewm(span=n, adjust=False).mean()
    sd = close.rolling(n).std()
    bbw = (2 * k * sd / mid)
    squeezed = (bbw < bbw.rolling(126).median()).shift(1).fillna(False).astype(bool).values
    up = (mid + k * sd).shift(1).values; lo = (mid - k * sd).shift(1).values
    mv = mid.shift(1).values; c = close.values
    pos = np.zeros(len(close)); p = 0
    for i in range(len(close)):
        if np.isnan(mv[i]): pos[i] = 0; continue
        if p == 0:
            if squeezed[i] and c[i] > up[i]: p = 1      # breakout up from squeeze
            elif squeezed[i] and c[i] < lo[i]: p = -1
        elif p == 1 and c[i] < mv[i]: p = 0
        elif p == -1 and c[i] > mv[i]: p = 0
        pos[i] = p
    return pd.Series(pos, index=close.index)


ZOO = {
    "donchian_20_10": donchian,
    "turtle_55_20": turtle,
    "ema_cross_10_30": ema_cross,
    "ema_cross_20_100": ema_cross_20_100,
    "bollinger_revert": bollinger_revert,
    "bollinger_squeeze": bollinger_squeeze,
}
