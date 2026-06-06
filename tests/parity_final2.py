"""
tests/parity_final2.py
----------------------
strategy.signals.decide_at vs strategy.evaluate, sampled (stride 9, 500-bar
capped window, full HTF). ~300 samples completes well under the time budget
while covering the HTF warmup region where the earlier divergence appeared.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from strategy.strategy import StrategyConfig, evaluate
from strategy.risk import RiskConfig
from strategy.signals import precompute, decide_at

WIN = 500
STRIDE = 9


def _key(intents):
    if not intents:
        return None
    o = intents[0]
    return (o.side, round(o.entry_price, 3), round(o.stop_price, 3),
            round(o.target_price, 3), round(o.qty, 3), o.is_ny_opening)


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
    lo, hi = WIN, min(n - 1, 3200)
    equity, trades_today = 100_000.0, 0
    compared = mismatches = signals = 0
    first_bad = []

    for i in range(lo, hi, STRIDE):
        ts = df.index[i]
        window = df.iloc[i - WIN + 1:i + 1]
        ref = evaluate(window, htf[htf.index <= ts], equity, trades_today, strat_cfg, risk_cfg)
        fast = decide_at(feat, i, equity, trades_today, strat_cfg, risk_cfg)
        compared += 1
        if _key(ref) is not None or _key(fast) is not None:
            signals += 1
        if _key(ref) != _key(fast):
            mismatches += 1
            if len(first_bad) < 10:
                first_bad.append((str(ts), _key(ref), _key(fast)))

    rate = 1.0 - (mismatches / compared if compared else 0)
    print(f"sampled bars  : {compared} (win {WIN}, stride {STRIDE})")
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
