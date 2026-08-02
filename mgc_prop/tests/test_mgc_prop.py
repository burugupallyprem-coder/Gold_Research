import sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import numpy as np, pandas as pd
from mgc_prop.strategy import trend_signal, overlay_contracts
from mgc_prop.apex import simulate_combine, ACCOUNTS
from mgc_prop.backtest import run_backtest


def _ohlc(closes):
    c = pd.Series(closes, index=pd.date_range("2020-01-01", periods=len(closes)))
    return pd.DataFrame({"open": c, "high": c + 1, "low": c - 1, "close": c})


def test_trend_signal_causal_and_directional():
    up = pd.Series(np.linspace(100, 200, 200))
    dn = pd.Series(np.linspace(200, 100, 200))
    assert trend_signal(up).iloc[-1] == 1
    assert trend_signal(dn).iloc[-1] == -1


def test_overlay_sizing_respects_floor_and_cap():
    # tiny room -> 0 contracts (can't risk a stop-out through the floor)
    assert overlay_contracts(50, 12, 3, 1.5, 10) == 0
    # big room -> capped at base, not cap
    assert overlay_contracts(100000, 12, 3, 1.5, 10) == 3
    # room grows -> size rises toward base
    assert overlay_contracts(600, 12, 1, 1.0, 10) >= 1


def test_lock_makes_a_won_combine_stick():
    # steady uptrend: long trend should reach the $50k target and pass
    closes = list(np.linspace(1800, 2100, 300))
    o = _ohlc(closes)
    sig = trend_signal(o["close"]).shift(1).fillna(0.0).values
    ok, d, why = simulate_combine(o["close"].values, o["high"].values, o["low"].values,
                                  sig, 120, "50k", 12, 3, 1.5)
    assert ok and why == "hit_profit_target", (ok, d, why)


def test_drawdown_breach_detected_on_a_one_day_gap():
    # minimal scenario: fresh account, then a 150pt one-day gap down while long, with a
    # loose 100pt stop + under-1 safety so the stop-out ($3,000) exceeds room ($2,500).
    close = np.array([2000.0, 2000.0, 1850.0]); high = close + 1; low = close - 1
    sig = np.array([0.0, 1.0, 1.0])
    ok, d, why = simulate_combine(close, high, low, sig, 2, "50k", 100, 3, 0.5)
    assert (not ok) and why == "breach_trailing_drawdown", (ok, d, why)


def test_overlay_prevents_breach_by_derisking():
    # SAME drop, but the real 12pt-stop overlay sizes down to flat before the floor:
    # it should NOT breach - it protects capital and simply fails to hit target.
    closes = list(np.linspace(2000, 2000, 130)) + list(np.linspace(2000, 1500, 60))
    o = _ohlc(closes)
    sig = np.ones(len(o))
    ok, d, why = simulate_combine(o["close"].values, o["high"].values, o["low"].values,
                                  sig, 131, "50k", 12, 3, 1.5)
    assert (not ok) and why != "breach_trailing_drawdown", (ok, d, why)


def test_backtest_runs_and_reports_sane_numbers():
    closes = list(2000 + 200 * np.sin(np.linspace(0, 20, 800)))
    r = run_backtest(_ohlc(closes), "50k", step=20)
    assert 0 <= r["pass_rate"] <= 100 and r["attempts"] > 0


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    p = 0
    for fn in fns:
        try: fn(); p += 1
        except Exception: print("FAIL", fn.__name__); traceback.print_exc()
    print(f"{p}/{len(fns)} tests passed")
