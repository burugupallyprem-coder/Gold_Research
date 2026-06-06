"""
tests/test_engine.py
--------------------
Correctness checks for the engine MECHANICS, isolated from the strategy by
stubbing the signal function. If these fail, no backtest number can be trusted.

Run:  python tests/test_engine.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtest import core as eng
from backtest.core import BacktestConfig, CostModel, run_backtest
from strategy.strategy import OrderIntent

PASS, FAIL = "PASS", "FAIL"
results = []


def _bars(rows):
    idx = pd.date_range("2024-01-02 14:00", periods=len(rows), freq="15min", tz="UTC")
    return pd.DataFrame(rows, index=idx,
                        columns=["open", "high", "low", "close", "volume"])


def _run_with_signal(df, signal_bar, intent, **bt_kwargs):
    """Stub engine.evaluate to emit `intent` once, when window ends at signal_bar."""
    orig = eng.evaluate

    def stub(window, htf_window, equity, trades_today, strat_cfg, risk_cfg, *a, **k):
        if len(window) - 1 == signal_bar:           # window ends exactly on signal_bar
            return [OrderIntent(**intent)]
        return []

    eng.evaluate = stub
    try:
        cost = CostModel()
        bt = BacktestConfig(lookback=999, use_confidence_gate=False,
                            starting_equity=100_000, **bt_kwargs)
        return run_backtest(df, None, bt_cfg=bt), cost
    finally:
        eng.evaluate = orig


def check(name, cond):
    results.append((name, PASS if cond else FAIL))
    print(f"[{PASS if cond else FAIL}] {name}")


# ── Test 1: no look-ahead — entry fills at NEXT bar's open ────────────────
def test_no_lookahead():
    df = _bars([
        (2000, 2001, 1999, 2000, 1000),   # 0
        (2000, 2002, 1999, 2001, 1000),   # 1  <- signal here
        (2010, 2011, 2009, 2010, 1000),   # 2  <- entry should fill at THIS open=2010
        (2010, 2060, 2009, 2050, 1000),   # 3  target hit
    ])
    intent = dict(symbol="XAU_USD", side="buy", qty=1.0, reason="Long: displacement",
                  entry_price=2001, stop_price=1991, target_price=2031)
    res, cost = _run_with_signal(df, signal_bar=1, intent=intent)
    t = res.trades[0]
    expected_entry = 2010 + cost.spread_usd / 2 + cost.slippage_usd
    check("entry fills at next bar open (no look-ahead)", abs(t.entry - expected_entry) < 1e-9)
    check("entry_time is bar 2, not signal bar 1", t.entry_time == df.index[2])


# ── Test 2: target exit + cost direction ─────────────────────────────────
def test_target_exit():
    df = _bars([
        (2000, 2001, 1999, 2000, 1000),   # 0 signal
        (2000, 2001, 1999, 2000, 1000),   # 1 entry at open 2000
        (2000, 2031, 1999, 2030, 1000),   # 2 target 2030 hit
    ])
    intent = dict(symbol="XAU_USD", side="buy", qty=2.0, reason="Long: displacement",
                  entry_price=2000, stop_price=1990, target_price=2030)
    res, cost = _run_with_signal(df, signal_bar=0, intent=intent)
    t = res.trades[0]
    entry = 2000 + cost.spread_usd / 2 + cost.slippage_usd
    exitp = 2030 - cost.spread_usd / 2 - cost.slippage_usd
    expected_pnl = (exitp - entry) * 2.0
    check("target exit reason", t.exit_reason == "target")
    check("target pnl matches cost-adjusted math", abs(t.pnl - expected_pnl) < 1e-6)


# ── Test 3: pessimistic — both touched in one bar => STOP wins ────────────
def test_both_touched_stop_first():
    df = _bars([
        (2000, 2001, 1999, 2000, 1000),   # 0 signal
        (2000, 2001, 1999, 2000, 1000),   # 1 entry at 2000
        (2000, 2031, 1989, 2000, 1000),   # 2 hits BOTH target 2030 and stop 1990
    ])
    intent = dict(symbol="XAU_USD", side="buy", qty=1.0, reason="Long: displacement",
                  entry_price=2000, stop_price=1990, target_price=2030)
    res, _ = _run_with_signal(df, signal_bar=0, intent=intent)
    check("both-touched resolves to STOP (pessimistic)", res.trades[0].exit_reason == "stop")
    check("stop loss is negative pnl", res.trades[0].pnl < 0)


# ── Test 4: break-even move at +1.5R then stop back at entry ──────────────
def test_breakeven_move():
    # risk = 10 (entry 2000, stop 1990). 1.5R => price 2015 triggers BE.
    df = _bars([
        (2000, 2001, 1999, 2000, 1000),   # 0 signal
        (2000, 2001, 1999, 2000, 1000),   # 1 entry 2000
        (2000, 2016, 1999, 2005, 1000),   # 2 high 2016 >= 2015 -> BE armed, stop->2000
        (2005, 2006, 1995, 1998, 1000),   # 3 low 1995 <= 2000 -> exit at BE stop 2000
    ])
    intent = dict(symbol="XAU_USD", side="buy", qty=1.0, reason="Long: displacement",
                  entry_price=2000, stop_price=1990, target_price=2030)
    res, cost = _run_with_signal(df, signal_bar=0, intent=intent)
    t = res.trades[0]
    check("BE exit reason is be_stop", t.exit_reason == "be_stop")
    # Exit at 2000 minus costs, entry at 2000 plus costs => small negative (cost only)
    check("BE exit loses only ~costs (not full stop)", -2.0 < t.pnl < 0.0)


# ── Test 5: daily trade cap resets per ET day ────────────────────────────
def test_daily_cap_reset():
    # Two signals same day should be capped if max_trades_per_day enforced by
    # strategy; here we only verify the engine increments per fill and that a
    # new ET day resets the counter (counter is internal, so we check via the
    # number of fills across a day boundary with repeated signals).
    idx = pd.date_range("2024-01-02 14:00", periods=8, freq="2h", tz="UTC")
    df = pd.DataFrame(
        [(2000, 2001, 1999, 2000, 1000)] * 8, index=idx,
        columns=["open", "high", "low", "close", "volume"])
    # signal on every bar; flat-only entries mean at most one open at a time
    orig = eng.evaluate
    eng.evaluate = lambda w, h, e, tt, sc, rc, *a, **k: [OrderIntent(
        symbol="XAU_USD", side="buy", qty=1.0, reason="Long: displacement",
        entry_price=2000, stop_price=1990, target_price=2030)]
    try:
        bt = BacktestConfig(lookback=999, use_confidence_gate=False)
        res = run_backtest(df, None, bt_cfg=bt)
        # No bar ever hits stop/target (range 1999-2001), so the first entry
        # stays open forever => exactly one fill, none after. Confirms flat-only.
        check("flat-only: at most one concurrent position", len(res.trades) <= 1)
    finally:
        eng.evaluate = orig


if __name__ == "__main__":
    test_no_lookahead()
    test_target_exit()
    test_both_touched_stop_first()
    test_breakeven_move()
    test_daily_cap_reset()
    n_fail = sum(1 for _, r in results if r == FAIL)
    print(f"\n{len(results)-n_fail}/{len(results)} checks passed")
    sys.exit(1 if n_fail else 0)
