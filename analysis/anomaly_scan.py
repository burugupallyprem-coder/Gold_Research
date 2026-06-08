"""
analysis/anomaly_scan.py  --  SHADOW MODE (standalone, read-only)
=================================================================
This is a STANDALONE diagnostic. It does NOT import or modify paper_trader.py,
it does NOT place or affect any trades, and it changes nothing about the live
bot. It only reads historical daily data, flags days that look "not natural,"
and backtests whether standing down on those days would have helped.

Run it, read the report, then decide whether it is worth attaching.

  python analysis/anomaly_scan.py
  python analysis/anomaly_scan.py --z 3.0 --volx 3.0 --atrx 2.5 --min-flags 2

What it computes per day (from daily OHLCV only):
  ret_z      today's log-return vs its rolling mean/std  (how extreme the move is)
  vol_x      today's volume vs its rolling median        (volume spike)
  range_atr  today's high-low range vs ATR(14)           (abnormal range)
  gap_atr    |open - prev close| vs ATR(14)              (abnormal gap)

A day is "flagged" (not natural) if at least --min-flags of those breach their
thresholds. The news-divergence check is intentionally left to a human/Claude
review step -- this math layer only measures statistical strangeness.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import SETTINGS                                   # noqa: E402
from strategy.macro_trend import MacroConfig, compute_weights, ANN  # noqa: E402

DAILY = ROOT / "data" / "daily"
BASELINE = {"ema_fast": 50, "ema_slow": 200, "mom_lookback": 252,
            "ry_mom_lookback": 60, "target_vol": 0.10, "use_macro": True}


def load():
    p = DAILY / f"{SETTINGS.instrument}_D.csv"
    if not p.exists():
        sys.exit(f"No data at {p} -- run: python data/fetch_daily.py --days 800")
    px = pd.read_csv(p, parse_dates=["time"]).set_index("time").sort_index()
    ryp = DAILY / "DFII10.csv"
    ry = (pd.read_csv(ryp, parse_dates=["time"]).set_index("time").sort_index()["dfii10"]
          if ryp.exists() else None)
    return px, ry


def anomaly_table(px, lookback=60, z=3.0, volx=3.0, atrx=2.5, gapx=2.0, min_flags=2):
    close = px["close"].astype(float)
    high = px["high"].astype(float)
    low = px["low"].astype(float)
    openp = px["open"].astype(float)
    vol = px["volume"].astype(float) if "volume" in px else None

    df = pd.DataFrame(index=px.index)
    ret = np.log(close / close.shift(1))
    df["ret_pct"] = (np.exp(ret) - 1.0) * 100.0
    df["ret_z"] = (ret - ret.rolling(lookback).mean()) / ret.rolling(lookback).std()

    tr = pd.concat([(high - low),
                    (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    df["range_atr"] = (high - low) / atr
    df["gap_atr"] = (openp - close.shift()).abs() / atr
    df["vol_x"] = (vol / vol.rolling(lookback).median()) if vol is not None else np.nan

    df["f_ret"] = df["ret_z"].abs() >= z
    df["f_vol"] = (df["vol_x"] >= volx) if vol is not None else False
    df["f_rng"] = df["range_atr"] >= atrx
    df["f_gap"] = df["gap_atr"] >= gapx
    df["n_flags"] = df[["f_ret", "f_vol", "f_rng", "f_gap"]].sum(axis=1)
    df["flagged"] = df["n_flags"] >= min_flags
    return df


def _stats(r):
    r = r.dropna()
    if len(r) < 30:
        return (0.0, 0.0, 0.0)
    sh = r.mean() / r.std() * np.sqrt(ANN) if r.std() > 0 else 0.0
    eq = (1 + r).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    return (round(float(sh), 3), round(float((eq.iloc[-1] - 1) * 100), 1),
            round(float(dd * 100), 1))


def backtest_filter(px, ry, flagged):
    """Compare champion baseline vs the same strategy standing flat the day
    AFTER a flag (you decide at the close, stand down going forward)."""
    cfg = MacroConfig(**BASELINE)
    w = compute_weights(px, ry, cfg)["weight"]
    ret = px["close"].astype(float).pct_change().fillna(0.0)
    base_pos = w.shift(1).fillna(0.0)
    standdown = flagged.shift(1, fill_value=False).astype(bool)
    filt_pos = base_pos.copy()
    filt_pos[standdown.values] = 0.0
    return _stats(base_pos * ret), _stats(filt_pos * ret), int(standdown.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookback", type=int, default=60)
    ap.add_argument("--z", type=float, default=3.0)
    ap.add_argument("--volx", type=float, default=3.0)
    ap.add_argument("--atrx", type=float, default=2.5)
    ap.add_argument("--gapx", type=float, default=2.0)
    ap.add_argument("--min-flags", type=int, default=2)
    args = ap.parse_args()

    px, ry = load()
    df = anomaly_table(px, args.lookback, args.z, args.volx, args.atrx, args.gapx,
                       args.min_flags)
    valid = df.dropna(subset=["ret_z"])
    n = len(valid)
    flagged = df["flagged"].fillna(False)
    nf = int(flagged.sum())

    print("=" * 68)
    print("ANOMALY SHADOW SCAN  (read-only; live bot untouched)")
    print(f"Instrument: {SETTINGS.instrument} | days analysed: {n} "
          f"| {px.index[0].date()} .. {px.index[-1].date()}")
    print(f"Thresholds: |ret_z|>={args.z}  vol_x>={args.volx}  "
          f"range/ATR>={args.atrx}  gap/ATR>={args.gapx}  need>={args.min_flags} flags")
    print("-" * 68)
    print(f"Flagged 'not natural' days: {nf}  ({100.0 * nf / max(n,1):.1f}% of days)")
    print("\nMost recent flagged days:")
    cols = ["ret_pct", "ret_z", "vol_x", "range_atr", "gap_atr", "n_flags"]
    recent = df[flagged].tail(8)
    if recent.empty:
        print("  (none)")
    else:
        for ts, row in recent.iterrows():
            print(f"  {ts.date()}  move={row['ret_pct']:+.2f}%  z={row['ret_z']:+.2f}  "
                  f"vol_x={row['vol_x']:.1f}  rng/atr={row['range_atr']:.1f}  "
                  f"gap/atr={row['gap_atr']:.1f}  flags={int(row['n_flags'])}")

    base, filt, stood = backtest_filter(px, ry, flagged)
    print("-" * 68)
    print("BACKTEST: does standing down on flagged days help?")
    print(f"  {'':18} {'Sharpe':>8} {'Return%':>9} {'MaxDD%':>8}")
    print(f"  {'baseline':18} {base[0]:>8} {base[1]:>9} {base[2]:>8}")
    print(f"  {'with filter':18} {filt[0]:>8} {filt[1]:>9} {filt[2]:>8}")
    print(f"  days stood down: {stood}")
    print("-" * 68)
    verdict = ("HELPS (better Sharpe)" if filt[0] > base[0]
               else "HURTS / NEUTRAL -- likely noise; do not attach")
    print(f"Read: filter {verdict}.")
    print("This is shadow output only. Nothing was changed in the live bot.")
    print("=" * 68)


if __name__ == "__main__":
    main()
