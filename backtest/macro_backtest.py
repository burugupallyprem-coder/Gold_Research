"""
backtest/macro_backtest.py
--------------------------
Vectorized daily backtest for the Gold Macro-Trend strategy. Position-based
(not discrete trades): each day we hold the target weight, earn that day's gold
return, and pay a turnover cost when the weight changes. No look-ahead — the
weight is lagged one day before applying returns.

Honest reporting: full-sample, in-sample (first 60%), out-of-sample (last 40%),
and a cost-stress run (5x costs). The verdict keys on the OUT-OF-SAMPLE Sharpe
surviving costs.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from strategy.macro_trend import MacroConfig, compute_weights

ANN = 252


def _metrics(strat_ret: pd.Series, pos: pd.Series, turnover: pd.Series) -> dict:
    r = strat_ret.dropna()
    if len(r) < 30 or r.std() == 0:
        return {"days": int(len(r)), "sharpe": 0.0, "cagr": 0.0,
                "max_dd": 0.0, "exposure": 0.0, "ann_turnover": 0.0, "hit": 0.0}
    eq = (1 + r).cumprod()
    sharpe = r.mean() / r.std() * math.sqrt(ANN)
    yrs = len(r) / ANN
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if eq.iloc[-1] > 0 else -1
    peak = eq.cummax()
    max_dd = ((eq - peak) / peak).min()
    return {
        "days": int(len(r)),
        "sharpe": round(sharpe, 3),
        "cagr": round(cagr * 100, 2),
        "max_dd": round(max_dd * 100, 2),
        "exposure": round(pos.abs().mean(), 3),
        "ann_turnover": round(turnover.sum() / yrs, 1),
        "hit": round((r > 0).mean(), 3),
    }


def run(prices: pd.DataFrame, ry: pd.Series | None,
        cfg: MacroConfig | None = None, cost_bps: float = 2.0) -> dict:
    cfg = cfg or MacroConfig()
    w = compute_weights(prices, ry, cfg)["weight"]
    ret = prices["close"].astype(float).pct_change().fillna(0.0)

    pos = w.shift(1).fillna(0.0)                       # trade next day (no look-ahead)
    turnover = (pos - pos.shift(1)).abs().fillna(0.0)
    cost = turnover * (cost_bps / 1e4)
    strat_ret = pos * ret - cost

    full = _metrics(strat_ret, pos, turnover)
    n = len(strat_ret)
    cut = int(n * 0.6)
    insample = _metrics(strat_ret.iloc[:cut], pos.iloc[:cut], turnover.iloc[:cut])
    oos = _metrics(strat_ret.iloc[cut:], pos.iloc[cut:], turnover.iloc[cut:])

    eq = (1 + strat_ret).cumprod()
    return {"full": full, "in_sample": insample, "out_of_sample": oos,
            "equity_final": round(float(eq.iloc[-1]), 4),
            "cost_bps": cost_bps,
            "period": f"{prices.index[0].date()}..{prices.index[-1].date()}"}


def verdict(base: dict, stress: dict) -> dict:
    oos_s = base["out_of_sample"]["sharpe"]
    full_s = base["full"]["sharpe"]
    stress_oos = stress["out_of_sample"]["sharpe"]
    if base["out_of_sample"]["days"] < 250:
        branch = "INSUFFICIENT DATA"
        msg = "Need more daily history (a few years) before judging."
    elif oos_s >= 0.3 and full_s >= 0.3 and stress_oos >= 0.2:
        branch = "REAL (MODEST) EDGE"
        msg = ("Out-of-sample risk-adjusted return is positive AND survives 5x "
               "costs. This is a genuine, documented-style premium. Expect long "
               "flat stretches; size small and keep validating on new data.")
    elif oos_s > 0 and stress_oos > 0:
        branch = "MARGINAL"
        msg = ("Weakly positive out-of-sample after costs. Promising but not "
               "conclusive — keep it research-only and gather more data.")
    else:
        branch = "NO EDGE AFTER COSTS"
        msg = ("Out-of-sample Sharpe is at/below zero after costs. Even the "
               "documented premium did not show on gold in this sample. Honest "
               "result — do not risk money.")
    return {"branch": branch, "oos_sharpe": oos_s, "full_sharpe": full_s,
            "stress_oos_sharpe": stress_oos, "message": msg}


def slack_text(base: dict, stress: dict, v: dict) -> str:
    b, o = base["full"], base["out_of_sample"]
    return "\n".join([
        f"[MACRO] Gold Macro-Trend {base['period']} — VERDICT: *{v['branch']}*",
        f"Out-of-sample: Sharpe={o['sharpe']} CAGR={o['cagr']}% maxDD={o['max_dd']}% "
        f"({o['days']}d)",
        f"Full sample: Sharpe={b['sharpe']} CAGR={b['cagr']}% maxDD={b['max_dd']}% "
        f"turnover={b['ann_turnover']}/yr exposure={b['exposure']}",
        f"Cost-stress (5x) OOS Sharpe={stress['out_of_sample']['sharpe']}",
        v["message"],
    ])
