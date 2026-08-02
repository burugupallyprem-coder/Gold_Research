"""Multi-market trend portfolio - the professional CTA construction.

Runs the SAME disciplined trend signal across a diversified basket, but scales each
market to equal risk (ex-ante volatility targeting) so no single market dominates, then
targets a portfolio-level volatility. A diversified trend premium is far less
regime-dependent than one crowded single-instrument signal - that is the whole point.

Everything is causal (no look-ahead): the signal and the vol estimate at day t use only
data through t-1, applied to the t-1->t return. Pure functions, unit-tested offline."""

import numpy as np
import pandas as pd

ANN = 252


def trend_signal(close, fast=20, slow=100):
    """+1/-1 daily trend (EMA cross), causal (shifted by the caller before use)."""
    return np.sign(close.ewm(span=fast, adjust=False).mean()
                   - close.ewm(span=slow, adjust=False).mean())


def ex_ante_vol(returns, lookback=63):
    """Causal annualized volatility estimate (uses only past returns)."""
    return returns.rolling(lookback).std().shift(1) * np.sqrt(ANN)


def market_position(close, fast=20, slow=100, vol_lookback=63,
                    target_vol=0.15, max_leverage=5.0):
    """Per-market position: trend direction, scaled so the market targets `target_vol`
    annualized. Position at day t uses info through t-1 (both signal and vol shifted)."""
    ret = close.pct_change().fillna(0.0)
    sig = trend_signal(close, fast, slow).shift(1).fillna(0.0)
    vol = ex_ante_vol(ret, vol_lookback)
    scale = (target_vol / vol).clip(upper=max_leverage).fillna(0.0)
    return sig * scale


def portfolio_returns(closes: dict, fast=20, slow=100, vol_lookback=63,
                      market_target_vol=0.15, port_target_vol=0.10,
                      cost_bps=1.0):
    """closes: {market: close Series}. Returns a daily portfolio-return Series:
    equal-risk trend across all markets, then scaled to `port_target_vol`."""
    idx = None
    contribs = []
    for m, close in closes.items():
        close = close.dropna()
        pos = market_position(close, fast, slow, vol_lookback, market_target_vol)
        ret = close.pct_change().fillna(0.0)
        turn = pos.diff().abs().fillna(0.0)
        c = pos * ret - turn * cost_bps / 1e4
        c.name = m
        contribs.append(c)
        idx = c.index if idx is None else idx.union(c.index)
    mat = pd.concat(contribs, axis=1).reindex(idx).fillna(0.0)
    gross = mat.mean(axis=1)                                   # equal weight across markets
    # scale the whole book to the portfolio vol target (causal: use trailing realized vol)
    realized = gross.rolling(63).std().shift(1) * np.sqrt(ANN)
    lever = (port_target_vol / realized).clip(upper=3.0).fillna(0.0)
    port = gross * lever
    return port, mat


def stats(returns):
    r = returns.dropna()
    if len(r) < 30 or r.std() == 0:
        return dict(sharpe=0.0, ann_return=0.0, ann_vol=0.0, max_dd=0.0, n=len(r))
    sharpe = r.mean() / r.std() * np.sqrt(ANN)
    eq = (1 + r).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    return dict(sharpe=round(float(sharpe), 3),
                ann_return=round(float(r.mean() * ANN), 4),
                ann_vol=round(float(r.std() * np.sqrt(ANN)), 4),
                max_dd=round(float(dd), 4), n=int(len(r)))


def by_year(returns):
    out = {}
    for y, g in returns.groupby(returns.index.year):
        if g.std() > 0 and len(g) > 30:
            out[int(y)] = round(float(g.mean() / g.std() * np.sqrt(ANN)), 2)
    return out
