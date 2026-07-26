"""
research/router_audit/collect_trades.py
=======================================
STEP 1 of the honest-router audit. Runs the EXISTING production engine
(backtest/engine_final.py) over XAU_USD M15 to produce the raw FVG + NY-Opening
trade universe. This is the exact code that produced reports/backtest_data_2026-07-25/
trades_*.csv. It is committed so the run is inspectable and reproducible.

Strategy config (frozen, identical to the live SMC engine minus Displacement):
    StrategyConfig(use_displacement=False, use_fvg=True, enable_ny_opening=True)
    BacktestConfig(use_confidence_gate=True, confidence_threshold=60)
    RiskConfig()                      # defaults: RR 2.5 / NY 3.0, BE at 1.5R, 1% risk
    CostModel(spread_usd=0.30, slippage_usd=0.05)   # => 0.40 gold points ROUND TRIP (1x)

Cost note: the engine applies (spread/2 + slippage) = 0.20 PER FILL, i.e. 0.40 round
trip, matching the task's "0.40 realistic". We save each trade's ORIGINAL planned risk
(r_planned) so 3x/5x cost can be recomputed EXACTLY downstream without re-running.

THE BUG THAT WAS FIXED (documented for the record):
    risk was first taken as abs(entry - stop). The engine moves the stop to break-even
    at 1.5R, so every winner ends with stop == entry => risk 0 => the winner was dropped
    by a `if risk<=0: continue` guard. That produced a fake ~7% win rate. The fix uses
    t.r_planned (risk recorded AT ENTRY, before any BE move). See `risk = ...` below.

Why per-window files: the shared VM throttles near the shell time limit on long slices,
so we run half-year windows, each to its OWN file (no shared-append race that could
interleave rows). analyze.py concatenates trades_*.csv.

Usage:
    python collect_trades.py 2024                      # full calendar year
    python collect_trades.py 2021a 2021-01-01 2021-07-01   # explicit window
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]          # repo root
sys.path.insert(0, str(ROOT))
from strategy.strategy import StrategyConfig
from strategy.risk import RiskConfig
from backtest.core import BacktestConfig, CostModel
from backtest.engine_final import run_backtest_fast

OUTDIR = ROOT/"reports"/"backtest_data_2026-07-25"; OUTDIR.mkdir(parents=True, exist_ok=True)
SC   = StrategyConfig(use_displacement=False, use_fvg=True, enable_ny_opening=True)
BT   = BacktestConfig(use_confidence_gate=True, confidence_threshold=60.0)
COST = CostModel(spread_usd=0.30, slippage_usd=0.05)      # 0.40 round trip

def load(tf):
    df = pd.read_csv(ROOT/"data"/"candles"/f"XAU_USD_{tf}.csv", parse_dates=["time"]).set_index("time").sort_index()
    if df.index.tz is None: df.index = df.index.tz_localize("UTC")
    return df

def tag(reason):
    r = (reason or "").lower()
    if "ny opening" in r: return "NY"
    if "fvg" in r:        return "FVG"
    return "OTHER"

def main():
    m15 = load("M15"); htf = load("H4")
    if len(sys.argv) >= 4:
        label = sys.argv[1]; start = pd.Timestamp(sys.argv[2], tz="UTC"); end = pd.Timestamp(sys.argv[3], tz="UTC")
    else:
        y = int(sys.argv[1]); label = sys.argv[1]
        start = pd.Timestamp(f"{y}-01-01", tz="UTC"); end = pd.Timestamp(f"{y+1}-01-01", tz="UTC")
    lo = start - pd.Timedelta(days=25); hi = end          # 25-day indicator warm-up lead-in
    sl = m15[(m15.index>=lo)&(m15.index<hi)]
    res = run_backtest_fast(sl, htf, SC, RiskConfig(), BT, COST)
    rows=[]
    for t in res.trades:
        if t.exit_time is None: continue
        et = pd.Timestamp(t.entry_time)
        if not (start <= et < end): continue              # attribute by ENTRY time; no double count
        risk = t.r_planned if t.r_planned > 0 else abs(t.entry - t.stop)   # ORIGINAL risk (BE-safe)
        if risk <= 0: continue
        rows.append(dict(entry_ts=t.entry_time, exit_ts=t.exit_time,
                         side=(1 if t.side=="buy" else -1), setup=tag(t.reason),
                         entry=round(float(t.entry),3), risk_price=round(float(risk),4),
                         r_1x=round(float(t.r_multiple),5)))
    df = pd.DataFrame(rows)
    out = OUTDIR/f"trades_{label}.csv"
    df.to_csv(out, index=False)
    win = round(float((df['r_1x']>0).mean()),3); mean = round(float(df['r_1x'].mean()),3)
    print(f"{label}: wrote {len(df)} trades -> {out.name}  win={win} mean_r={mean}")

if __name__ == "__main__":
    main()
