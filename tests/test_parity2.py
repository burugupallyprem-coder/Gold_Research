"""
tests/test_parity2.py
---------------------
Prove strategy.feat.decide_at reproduces strategy.evaluate bar-for-bar, by
feeding evaluate() the FULL history up to each sampled bar (identical info to
what precompute sees) and comparing the resulting intent.

Run:  python tests/test_parity2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from strategy.strategy import StrategyConfig, evaluate
from strategy.risk import RiskConfig
from strategy.feat import precompute, decide_at


def _key(intents):
    if not intents:
        return None
    o = intents[0]
    return (o.side, round(o.entry_price, 4), round(o.stop_price, 4),
            round(o.target_price, 4), round(o.qty, 4), o.is_ny_opening)


def main():
    candles = ROOT / "data" / "candles"
    df = pd.read_csv(candles / "XAU_USD_M15.csv", parse_dates=["time"]).set_index("time").sort_index()
    htf = pd.read_csv(candles / "XAU_USD_H4.csv", parse_dates=["time"]).set_index("time").sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    if htf.index.tz is None:
        htf.index = htf.index.tz_localize("UTC")

    strat_cfg, risk_cfg = StrategyConfig(), RiskConfig()
    feat = precompute(df, htf, strat_cfg)

    n = len(df)
    lo, hi = min(400, n // 4), min(n - 1, 1600)
    equity, trades_today = 100_000.0, 0
    compared = mismatches = signals = 0
    first_bad = []

    for i in range(lo, hi):
        ts = df.index[i]
        ref = evaluate(df.iloc[:i + 1], htf[htf.index <= ts], equity, trades_today,
                       strat_cfg, risk_cfg)
        fast = decide_at(feat, i, equity, trades_today, strat_cfg, risk_cfg)
        compared += 1
        if _key(ref) is not None or _key(fast) is not None:
            signals += 1
        if _key(ref) != _key(fast):
            mismatches += 1
            if len(first_bad) < 8:
                first_bad.append((str(ts), _key(ref), _key(fast)))

    rate = 1.0 - (mismatches / compared if compared else 0)
    print(f"compared bars : {compared}")
    print(f"bars w/ signal: {signals}")
    print(f"mismatches    : {mismatches}")
    print(f"parity rate   : {rate:.4f}")
    for b in first_bad:
        print("  MISMATCH", b)
    ok = mismatches == 0
    print("\nPARITY", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
