"""
tests/make_synthetic.py
-----------------------
Generate synthetic XAU/USD-like M15 + H4 candles so the FULL pipeline can be
exercised offline (no OANDA access needed). This data is for plumbing/
correctness checks ONLY — it says nothing about real edge.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CANDLES = ROOT / "data" / "candles"


def make(instrument="XAU_USD", days=120, seed=7):
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2024-01-01 00:00", tz="UTC")
    # 24h * 4 bars/h for M15, weekdays only (gold ~24/5)
    idx = pd.date_range(start, periods=days * 96, freq="15min", tz="UTC")
    idx = idx[idx.weekday < 5]

    n = len(idx)
    # Random walk with mild trend regimes + occasional displacement shocks
    price = 2000.0
    rows = []
    trend = 0.0
    for k in range(n):
        if k % 800 == 0:
            trend = rng.normal(0, 0.04)
        shock = 0.0
        if rng.random() < 0.02:                       # ~2% bars are displacement
            shock = rng.choice([-1, 1]) * rng.uniform(2.0, 5.0)
        step = rng.normal(trend, 0.8) + shock
        o = price
        c = price + step
        hi = max(o, c) + abs(rng.normal(0, 0.4))
        lo = min(o, c) - abs(rng.normal(0, 0.4))
        vol = int(abs(rng.normal(1000, 300)) + (400 if shock else 0))
        rows.append((o, hi, lo, c, vol))
        price = c

    df = pd.DataFrame(rows, index=idx, columns=["open", "high", "low", "close", "volume"])
    CANDLES.mkdir(parents=True, exist_ok=True)
    m15 = CANDLES / f"{instrument}_M15.csv"
    df.reset_index(names="time").to_csv(m15, index=False)

    h4 = df.resample("4h").agg({"open": "first", "high": "max", "low": "min",
                                "close": "last", "volume": "sum"}).dropna()
    h4_path = CANDLES / f"{instrument}_H4.csv"
    h4.reset_index(names="time").to_csv(h4_path, index=False)
    print(f"Wrote {len(df)} M15 and {len(h4)} H4 synthetic bars to {CANDLES}")


if __name__ == "__main__":
    make()
