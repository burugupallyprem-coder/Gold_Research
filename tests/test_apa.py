"""Advanced Price Action detector/sim tests. Run: python tests/test_apa.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

import advanced_price_action as apa


def _df(bars):
    idx = pd.date_range("2022-01-01", periods=len(bars), freq="15min", tz="UTC")
    d = pd.DataFrame(bars, columns=["open", "high", "low", "close"], index=idx)
    return apa.add_indicators(d)


def _uptrend_then_wedge_then_break(n_up=260, wedge=12):
    """Build: long uptrend (so EMA is below price + support forms), a falling
    wedge pullback, then a long breakout bar."""
    bars = []
    px = 100.0
    for _ in range(n_up):                       # steady uptrend
        px += 0.5
        bars.append((px - 0.2, px + 0.3, px - 0.3, px))
    top = px
    # falling wedge: lower highs + lower lows, contracting, back down toward support
    hi, lo = top + 0.3, top - 1.0
    for k in range(wedge):
        hi -= 0.5 - 0.02 * k                    # highs fall, steps shrink (contract)
        lo -= 0.35 - 0.02 * k                   # lows fall less each step (contract)
        c = (hi + lo) / 2
        bars.append((c, hi, lo, c))
    wedge_hi = max(b[1] for b in bars[-wedge:])
    # long bullish breakout bar: big range, closes above wedge highs
    base = bars[-1][3]
    bars.append((base, wedge_hi + 6.0, base - 0.2, wedge_hi + 5.5))          # breakout signal bar
    bars.append((wedge_hi + 5.5, wedge_hi + 7, wedge_hi + 5, wedge_hi + 6.5))  # entry bar (fills at open)
    px = wedge_hi + 6.5
    for _ in range(30):                          # rally so the trade resolves (hits target)
        px += 2.0
        bars.append((px - 1.0, px + 1.0, px - 1.2, px))
    return _df(bars)


def test_indicators_present():
    df = _uptrend_then_wedge_then_break()
    for col in ("ema", "atr", "support"):
        assert col in df.columns
    assert df["atr"].iloc[-1] > 0


def test_detects_long_breakout_after_wedge():
    df = _uptrend_then_wedge_then_break(wedge=12)
    trades = apa.simulate(df, {"wedge_len": 12, "breakout_atr": 1.0, "rr": 1.5})
    assert len(trades) >= 1
    t = trades[0]
    assert t["risk"] > 0
    assert t["entry"] > 0
    assert t["exit_ts"] >= t["entry_ts"]         # causal


def test_no_trade_without_uptrend_context():
    # pure downtrend: close never above EMA -> context filter blocks everything
    bars = []
    px = 300.0
    for _ in range(300):
        px -= 0.5
        bars.append((px + 0.2, px + 0.3, px - 0.3, px))
    df = _df(bars)
    assert apa.simulate(df, {"wedge_len": 12, "breakout_atr": 1.5, "rr": 1.5}) == []


def test_stats_costs_and_split():
    trades = [dict(entry_ts=pd.Timestamp("2022-06-01", tz="UTC"), exit_ts=pd.Timestamp("2022-06-02", tz="UTC"),
                   entry=1800.0, risk=6.0, pnl_price=12.0, kind="target")]
    m1 = apa.stats(trades, 0.40)                 # net (12-0.8)/6 = 1.867
    assert abs(m1["expectancy_r"] - 1.867) < 1e-3
    m3 = apa.stats(trades, 1.20)                 # 3x cost lowers R
    assert m3["expectancy_r"] < m1["expectancy_r"]
    tr, va = apa.split(trades)
    assert len(tr) == 1 and len(va) == 0         # 2022 is train


def test_stats_empty():
    assert apa.stats([], 0.4) == {"trades": 0}


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} tests passed")
