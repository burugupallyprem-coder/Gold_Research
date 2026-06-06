"""
backtest/metrics2.py
--------------------
Adds long/short split (item 3) and keeps the base by-setup breakdown (item 4)
on top of backtest.metrics.compute_metrics.
"""

from __future__ import annotations

import math

from backtest.metrics import compute_metrics


def _sub(trades):
    n = len(trades)
    if n == 0:
        return {"trades": 0, "win_rate": 0, "profit_factor": 0, "expectancy_R": 0, "pnl": 0}
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl < 0]
    gw, gl = sum(wins), -sum(losses)
    pf = (gw / gl) if gl > 0 else (math.inf if gw > 0 else 0)
    return {
        "trades": n,
        "win_rate": round(len(wins) / n, 4),
        "profit_factor": round(pf, 3) if math.isfinite(pf) else "inf",
        "expectancy_R": round(sum(t.r_multiple for t in trades) / n, 4),
        "pnl": round(sum(t.pnl for t in trades), 2),
    }


def compute_metrics2(trades, equity_curve, starting_equity):
    base = compute_metrics(trades, equity_curve, starting_equity)
    longs = [t for t in trades if t.side == "buy"]
    shorts = [t for t in trades if t.side == "sell"]
    base["by_direction"] = {"long": _sub(longs), "short": _sub(shorts)}
    return base
