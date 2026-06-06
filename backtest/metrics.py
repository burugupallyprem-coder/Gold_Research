"""
backtest/metrics.py
-------------------
Performance metrics computed from the trade list and equity curve.
All honest, no annualization tricks hidden from view.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def compute_metrics(trades: list, equity_curve: pd.DataFrame,
                    starting_equity: float, bars_per_year: float = 35040) -> dict:
    """
    bars_per_year default = 24h * 60 / 15 * ~365 trading-ish days for M15 spot.
    Used only for a rough Sharpe annualization on the equity curve.
    """
    n = len(trades)
    if n == 0:
        return {"trades": 0, "note": "No trades generated."}

    pnls = np.array([t.pnl for t in trades], dtype=float)
    r_mults = np.array([t.r_multiple for t in trades], dtype=float)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]

    gross_win = wins.sum()
    gross_loss = -losses.sum()
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else math.inf

    win_rate = len(wins) / n
    avg_win = wins.mean() if len(wins) else 0.0
    avg_loss = losses.mean() if len(losses) else 0.0
    expectancy_r = r_mults.mean()

    final_equity = starting_equity + pnls.sum()
    total_return = final_equity / starting_equity - 1.0

    # Max drawdown on the equity curve
    eq = equity_curve["equity"].values
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    max_dd = dd.min() if len(dd) else 0.0

    # Rough Sharpe from per-bar equity returns
    rets = pd.Series(eq).pct_change().dropna()
    if rets.std() > 0:
        sharpe = (rets.mean() / rets.std()) * math.sqrt(bars_per_year)
    else:
        sharpe = 0.0

    # Streaks
    streak = max_streak = 0
    for p in pnls:
        if p < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    by_reason: dict[str, dict] = {}
    for t in trades:
        key = ("NY Opening" if "NY Opening" in t.reason
               else "Displacement" if "displacement" in t.reason
               else "FVG" if "FVG" in t.reason else "Other")
        b = by_reason.setdefault(key, {"n": 0, "wins": 0, "pnl": 0.0, "r": 0.0})
        b["n"] += 1
        b["wins"] += 1 if t.pnl > 0 else 0
        b["pnl"] += t.pnl
        b["r"] += t.r_multiple
    for b in by_reason.values():
        b["win_rate"] = round(b["wins"] / b["n"], 3)
        b["avg_r"] = round(b["r"] / b["n"], 3)
        b["pnl"] = round(b["pnl"], 2)

    return {
        "trades": n,
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 3) if math.isfinite(profit_factor) else "inf",
        "expectancy_R": round(expectancy_r, 4),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "total_pnl": round(pnls.sum(), 2),
        "total_return_pct": round(total_return * 100, 2),
        "final_equity": round(final_equity, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "sharpe_annual_est": round(sharpe, 2),
        "max_losing_streak": int(max_streak),
        "exit_breakdown": _exit_breakdown(trades),
        "by_setup": by_reason,
    }


def _exit_breakdown(trades: list) -> dict:
    out: dict[str, int] = {}
    for t in trades:
        out[t.exit_reason] = out.get(t.exit_reason, 0) + 1
    return out


def trades_to_frame(trades: list) -> pd.DataFrame:
    return pd.DataFrame([{
        "entry_time": t.entry_time, "exit_time": t.exit_time,
        "side": t.side, "qty": t.qty, "entry": round(t.entry, 3),
        "stop": round(t.stop, 3), "target": round(t.target, 3),
        "exit_price": round(t.exit_price, 3) if t.exit_price else None,
        "exit_reason": t.exit_reason, "reason": t.reason,
        "confidence": t.confidence, "r_multiple": round(t.r_multiple, 3),
        "pnl": round(t.pnl, 2),
    } for t in trades])
