"""
tests/test_engine_v2.py
-----------------------
Correctness checks for the partial-profit + trailing engine, isolated from the
strategy by stubbing the signal function. Run: python tests/test_engine_v2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import engine_v2 as eng
from backtest.core import BacktestConfig, CostModel
from strategy.strategy import OrderIntent
from strategy.signals_v2 import RegimeConfig

results = []


def check(name, cond):
    results.append(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")


def _df(action_rows):
    """16 flat warmup bars at 2000, then the action rows."""
    rows = [(2000, 2000, 2000, 2000, 1000)] * 16 + action_rows
    idx = pd.date_range("2024-02-20 13:00", periods=len(rows), freq="15min", tz="UTC")
    return pd.DataFrame(rows, index=idx, columns=["open", "high", "low", "close", "volume"])


def _run(df, sig_bar=15, qty=2.0):
    intent = OrderIntent(symbol="XAU_USD", side="buy", qty=qty, reason="Long: displacement",
                         entry_price=2000, stop_price=1990, target_price=2025)
    orig = eng.decide_at_v2
    eng.decide_at_v2 = lambda f, i, e, tt, sc, rc, rg, *a, **k: [intent] if i == sig_bar else []
    try:
        rcfg = RegimeConfig(require_regime=False, stand_down_events=False,
                            partial_frac=0.5, partial_at_r=1.0, trail_atr_mult=1.5)
        bt = BacktestConfig(use_confidence_gate=False, starting_equity=100_000)
        return eng.run_backtest_v2(df, None, bt_cfg=bt, regime_cfg=rcfg, cost=CostModel())
    finally:
        eng.decide_at_v2 = orig


# A: partial at +1R, runner hits target
def test_partial_then_target():
    df = _df([(2000, 2011, 1999, 2010, 1000),   # bar16 entry fill @2000; this is bar17 -> partial
              (2015, 2026, 2014, 2025, 1000)])   # bar18 -> runner hits target
    # NOTE bar16 is the entry fill bar; action begins bar17
    r = _run(df)
    t = r.trades[0]
    check("A exit reason = target", t.exit_reason == "target")
    check("A took partial (be_moved)", t.be_moved is True)
    check("A blended R ~1.5-1.8", 1.4 < t.r_multiple < 1.85)
    check("A pnl positive", t.pnl > 0)


# B: full stop in phase 1
def test_full_stop():
    df = _df([(2000, 2001, 1989, 1995, 1000)])   # dips to 1989 <= stop 1990 before any partial
    r = _run(df)
    t = r.trades[0]
    check("B exit reason = stop", t.exit_reason == "stop")
    check("B R ~ -1", -1.1 < t.r_multiple < -0.9)


# C: partial then runner stopped at break-even
def test_partial_then_be():
    df = _df([(2000, 2011, 1999, 2010, 1000),    # partial books, stop -> entry
              (2005, 2006, 1999, 2000, 1000)])    # falls back to BE stop
    r = _run(df)
    t = r.trades[0]
    check("C exit reason = be_stop", t.exit_reason == "be_stop")
    check("C keeps ~half of +1R", 0.2 < t.r_multiple < 0.6)
    check("C pnl positive (banked partial)", t.pnl > 0)


if __name__ == "__main__":
    test_partial_then_target()
    test_full_stop()
    test_partial_then_be()
    n = len(results); ok = sum(results)
    print(f"\n{ok}/{n} checks passed")
    sys.exit(0 if ok == n else 1)
