"""
tests/make_synthetic_daily.py
-----------------------------
Synthetic daily gold + real-yield series to exercise the macro-trend pipeline
offline. Plumbing test only — results are meaningless. Includes deliberate
trend regimes and an (anti-)correlated real-yield series so the gates activate.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "daily"


def make(instrument="XAU_USD", days=1600, seed=11):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-01", periods=days)
    price, trend, ry = 1300.0, 0.0, 0.8
    prows, rrows = [], []
    for k in range(days):
        if k % 180 == 0:
            trend = rng.normal(0, 0.0006)
        # real yield wanders; gold gets a tailwind when ry falls
        ry += rng.normal(-0.0008 if trend > 0 else 0.0008, 0.02)
        drift = trend - 0.15 * (ry - 0.8) / 100
        step = price * (drift + rng.normal(0, 0.009))
        o = price
        c = price + step
        hi = max(o, c) * (1 + abs(rng.normal(0, 0.004)))
        lo = min(o, c) * (1 - abs(rng.normal(0, 0.004)))
        prows.append((idx[k].date(), round(o, 2), round(hi, 2), round(lo, 2),
                      round(c, 2), int(abs(rng.normal(50000, 10000)))))
        rrows.append((idx[k].date(), round(ry, 3)))
        price = c

    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(prows, columns=["time", "open", "high", "low", "close", "volume"]
                 ).to_csv(OUT / f"{instrument}_D.csv", index=False)
    pd.DataFrame(rrows, columns=["time", "dfii10"]).to_csv(OUT / "DFII10.csv", index=False)
    print(f"Wrote {days} synthetic daily bars + real-yield series to {OUT}")


if __name__ == "__main__":
    make()
