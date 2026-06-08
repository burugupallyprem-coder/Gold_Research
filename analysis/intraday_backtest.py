"""
analysis/intraday_backtest.py  --  STANDALONE intraday backtest (read-only)
===========================================================================
Runs an INTRADAY version of the trend strategy (the same engine as the daily
Macro-Trend, ported to intraday bars) PLUS the anomaly stand-down filter, with
REALISTIC transaction costs. It does NOT import or modify paper_trader.py and
changes nothing about the live bot. It only reads cached candles and prints a
report so you can decide whether intraday is worth keeping.

Data it reads (fetch on your machine first):
    data/candles/XAU_USD_H4.csv   (or M15) -- from: python data/fetch_oanda.py
    data/daily/DFII10.csv         (optional real-yield gate)

Run:
    python analysis/intraday_backtest.py                 # H4, default params
    python analysis/intraday_backtest.py --tf M15
    python analysis/intraday_backtest.py --tf H4 --no-macro --spread 0.30 --slippage 0.10

HONEST WARNING: intraday trading multiplies trade count, and gold's spread +
slippage eats intraday edges -- this is exactly what killed your SMC strategy.
The whole point of this file is to show you GROSS vs NET so you can see if any
edge survives costs before risking a paper account.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import SETTINGS  # noqa: E402

CANDLES = ROOT / "data" / "candles"
DAILY = ROOT / "data" / "daily"


def load_intraday(tf: str) -> pd.DataFrame:
    p = CANDLES / f"{SETTINGS.instrument}_{tf}.csv"
    if not p.exists():
        sys.exit(f"No candles at {p}\n"
                 f"Fetch first:  python data/fetch_oanda.py --tf {tf} --days 2700")
    df = pd.read_csv(p, parse_dates=["time"]).set_index("time").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df


def periods_per_year(idx: pd.DatetimeIndex) -> float:
    d = idx.to_series().diff().dropna().median()
    if pd.isna(d) or d.total_seconds() <= 0:
        return 252.0
    return float(pd.Timedelta(days=365.25) / d)


def macro_gate(df: pd.DataFrame, ry_days: int):
    """Slow daily real-yield gate mapped onto intraday bars by date.
    Returns (allow_long, allow_short) bool Series aligned to df.index.
    If DFII10 is missing, both are all-True (gate disabled)."""
    p = DAILY / "DFII10.csv"
    if not p.exists():
        idx = df.index
        return pd.Series(True, index=idx), pd.Series(True, index=idx), False
    try:
        ry = (pd.read_csv(p, parse_dates=["time"]).set_index("time")
              .sort_index()["dfii10"])
        ry.index = ry.index.normalize()
        ry_mom = ry - ry.shift(ry_days)
        allow_long_d = (ry_mom <= 0.0)
        allow_short_d = (ry_mom > 0.0)
        days = df.index.normalize()
        al = allow_long_d.reindex(days, method="ffill").fillna(True)
        ash = allow_short_d.reindex(days, method="ffill").fillna(True)
        al.index = df.index
        ash.index = df.index
        return al.astype(bool), ash.astype(bool), True
    except Exception as e:  # noqa: BLE001
        print(f"  [macro gate disabled: {e}]")
        idx = df.index
        return pd.Series(True, index=idx), pd.Series(True, index=idx), False


def weights(df, ppy, ema_fast, ema_slow, mom, vol_lb, target_vol, maxlev,
            use_macro, ry_days):
    close = df["close"].astype(float)
    ema_f = close.ewm(span=ema_fast, adjust=False).mean()
    ema_s = close.ewm(span=ema_slow, adjust=False).mean()
    trend = np.sign(ema_f - ema_s)
    m = close / close.shift(mom) - 1.0
    direction = np.where((trend > 0) & (m > 0), 1,
                np.where((trend < 0) & (m < 0), -1, 0))
    direction = pd.Series(direction, index=close.index)

    if use_macro:
        al, ash, on = macro_gate(df, ry_days)
    else:
        al = pd.Series(True, index=close.index); ash = al; on = False

    pos_dir = np.where((direction > 0) & al.values, 1,
              np.where((direction < 0) & ash.values, -1, 0))
    pos_dir = pd.Series(pos_dir, index=close.index)

    realized = close.pct_change().rolling(vol_lb).std() * np.sqrt(ppy)
    scale = (target_vol / realized).clip(upper=maxlev).replace([np.inf, -np.inf], np.nan)
    w = (pos_dir * scale).fillna(0.0)
    return w, on


def anomaly_flags(df, lookback, z, volx, atrx, gapx, min_flags):
    close = df["close"].astype(float); high = df["high"].astype(float)
    low = df["low"].astype(float); openp = df["open"].astype(float)
    vol = df["volume"].astype(float) if "volume" in df else None
    ret = np.log(close / close.shift(1))
    ret_z = (ret - ret.rolling(lookback).mean()) / ret.rolling(lookback).std()
    tr = pd.concat([(high - low), (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    f_ret = ret_z.abs() >= z
    f_rng = (high - low) / atr >= atrx
    f_gap = (openp - close.shift()).abs() / atr >= gapx
    f_vol = (vol / vol.rolling(lookback).median() >= volx) if vol is not None else pd.Series(False, index=close.index)
    n = (f_ret.astype(int) + f_vol.astype(int) + f_rng.astype(int) + f_gap.astype(int))
    return (n >= min_flags).fillna(False)


def run_curve(pos, ret, close, spread, slippage):
    pos = pos.shift(1).fillna(0.0)
    turn = (pos - pos.shift(1)).abs().fillna(0.0)
    cost = turn * (spread + slippage) / close
    gross = pos * ret
    net = gross - cost
    return gross, net, turn


def stats(r, ppy):
    r = r.dropna()
    if len(r) < 30:
        return {"sharpe": 0.0, "ret": 0.0, "mdd": 0.0}
    sh = r.mean() / r.std() * np.sqrt(ppy) if r.std() > 0 else 0.0
    eq = (1 + r).cumprod()
    mdd = (eq / eq.cummax() - 1).min()
    return {"sharpe": round(float(sh), 3),
            "ret": round(float((eq.iloc[-1] - 1) * 100), 1),
            "mdd": round(float(mdd * 100), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="H4")
    ap.add_argument("--ema-fast", type=int, default=50)
    ap.add_argument("--ema-slow", type=int, default=200)
    ap.add_argument("--mom", type=int, default=120)
    ap.add_argument("--vol-lookback", type=int, default=100)
    ap.add_argument("--target-vol", type=float, default=0.10)
    ap.add_argument("--maxlev", type=float, default=3.0)
    ap.add_argument("--no-macro", action="store_true")
    ap.add_argument("--ry-days", type=int, default=60)
    ap.add_argument("--spread", type=float, default=SETTINGS.spread_usd)
    ap.add_argument("--slippage", type=float, default=SETTINGS.slippage_usd)
    ap.add_argument("--an-lookback", type=int, default=96)
    ap.add_argument("--z", type=float, default=3.0)
    ap.add_argument("--volx", type=float, default=3.0)
    ap.add_argument("--atrx", type=float, default=2.5)
    ap.add_argument("--gapx", type=float, default=2.0)
    ap.add_argument("--min-flags", type=int, default=2)
    args = ap.parse_args()

    df = load_intraday(args.tf)
    ppy = periods_per_year(df.index)
    years = (df.index[-1] - df.index[0]).days / 365.25
    close = df["close"].astype(float)
    ret = close.pct_change().fillna(0.0)

    w, macro_on = weights(df, ppy, args.ema_fast, args.ema_slow, args.mom,
                          args.vol_lookback, args.target_vol, args.maxlev,
                          not args.no_macro, args.ry_days)
    gross, net, turn = run_curve(w, ret, close, args.spread, args.slippage)

    flagged = anomaly_flags(df, args.an_lookback, args.z, args.volx, args.atrx,
                            args.gapx, args.min_flags)
    standdown = flagged.shift(1, fill_value=False).astype(bool)
    w_filt = w.copy(); w_filt[standdown.values] = 0.0
    _, net_filt, turn_filt = run_curve(w_filt, ret, close, args.spread, args.slippage)

    s_gross = stats(gross, ppy)
    s_net = stats(net, ppy)
    s_filt = stats(net_filt, ppy)
    changes = int((turn > 1e-9).sum())
    ann_turn = round(float(turn.sum() / max(years, 1e-9)), 1)
    cost_drag = round(float((gross.sum() - net.sum()) * 100), 1)

    print("=" * 70)
    print("INTRADAY BACKTEST  (standalone; live bot untouched)")
    print(f"{SETTINGS.instrument} {args.tf} | bars={len(df)} | "
          f"{df.index[0].date()}..{df.index[-1].date()} | ~{years:.1f}y | "
          f"~{ppy:.0f} bars/yr")
    print(f"Macro real-yield gate: {'ON' if macro_on else 'OFF'} | "
          f"costs: spread {args.spread} + slippage {args.slippage} per side")
    print("-" * 70)
    print(f"{'':24}{'Sharpe':>8}{'Return%':>10}{'MaxDD%':>9}")
    print(f"{'GROSS (no costs)':24}{s_gross['sharpe']:>8}{s_gross['ret']:>10}{s_gross['mdd']:>9}")
    print(f"{'NET (after costs)':24}{s_net['sharpe']:>8}{s_net['ret']:>10}{s_net['mdd']:>9}")
    print(f"{'NET + anomaly filter':24}{s_filt['sharpe']:>8}{s_filt['ret']:>10}{s_filt['mdd']:>9}")
    print("-" * 70)
    print(f"Position changes: {changes} | annual turnover: {ann_turn}x | "
          f"cost drag: {cost_drag} pts of return")
    print(f"Anomaly bars flagged: {int(flagged.sum())} "
          f"({100.0*flagged.sum()/max(len(df),1):.2f}%) | "
          f"bars stood down: {int(standdown.sum())}")
    print("-" * 70)
    if s_net["sharpe"] <= 0:
        verdict = "NET edge is GONE after costs -- intraday not worth it as-is."
    elif s_net["sharpe"] < s_gross["sharpe"] * 0.5:
        verdict = "Costs eat most of the edge -- weak; be very skeptical."
    else:
        verdict = "Some edge survives costs -- worth deeper validation."
    filt_note = ("filter helps" if s_filt["sharpe"] > s_net["sharpe"]
                 else "filter does not help here")
    print(f"Read: {verdict}  ({filt_note})")
    print("Shadow output only. Nothing in the live bot was changed.")
    print("=" * 70)


if __name__ == "__main__":
    main()
