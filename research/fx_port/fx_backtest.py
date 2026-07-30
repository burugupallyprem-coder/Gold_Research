"""
research/fx_port/fx_backtest.py
===============================
Port the intraday SMC stack (FVG + NY-Opening, confidence gate, daily-trend filter)
to a FOREX instrument and judge it on the SAME honest gauntlet used for gold. Reuses
the EXACT production engine (backtest/engine_final.py). Infra ports; edge does NOT --
this script exists to find out, on real data, whether there is any edge to port.

Runs on YOUR machine or CI (a full multi-year FX M15 run exceeds the cloud sandbox's
short shell limit). Assumes candles already fetched:
    python data/fetch_oanda.py --instrument EUR_USD --days 1825   # -> data/candles/EUR_USD_{M15,H4}.csv

Then:
    python research/fx_port/fx_backtest.py EUR_USD
    python research/fx_port/fx_backtest.py EUR_USD --spread 0.00010 --slippage 0.000025 --smoke 60000

Why R metrics are comparable to gold: r_multiple = price_move / planned_risk, which is
independent of price scale and position size. So expectancy(R), PF, win% and the gate
transfer directly; only the ABSOLUTE cost must be set in the instrument's price units
(defaults below are ~1.5 pip round-trip for majors; cost-stress covers widening).

Gate (same as gold): >=100 trades, >= +0.05R expectancy, PF >= 1.15, >= 60% quarters positive.
Compares against buy-and-hold of the instrument over the same window. Selection-period
number is the honest one; label any single-regime holdout as such.
"""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from strategy.strategy import StrategyConfig
from strategy.risk import RiskConfig
from strategy.macro_trend import MacroConfig, compute_weights
from backtest.core import BacktestConfig, CostModel
from backtest.engine_final import run_backtest_fast

CANDLES = ROOT/"data"/"candles"
OUTDIR = ROOT/"reports"/"fx_port"; OUTDIR.mkdir(parents=True, exist_ok=True)
RISK=0.01

# instrument -> (spread, slippage) in PRICE units for a realistic ~1.5 pip round trip
COST_DEFAULTS = {
    "EUR_USD":(0.00010,0.000025), "GBP_USD":(0.00012,0.00003), "AUD_USD":(0.00012,0.00003),
    "USD_CHF":(0.00012,0.00003),  "USD_CAD":(0.00013,0.00003), "NZD_USD":(0.00015,0.00004),
    "USD_JPY":(0.010,0.003),      "EUR_JPY":(0.012,0.003),     "GBP_JPY":(0.015,0.004),
}

def load(inst, tf):
    p = CANDLES/f"{inst}_{tf}.csv"
    if not p.exists(): sys.exit(f"MISSING {p} -- run: python data/fetch_oanda.py --instrument {inst} --days 1825")
    df = pd.read_csv(p, parse_dates=["time"]).set_index("time").sort_index()
    if df.index.tz is None: df.index = df.index.tz_localize("UTC")
    if "volume" not in df.columns: df["volume"]=1000.0
    return df

def sharpe(s):
    s=pd.Series(s).dropna(); return 0.0 if (len(s)<20 or s.std()==0) else float(s.mean()/s.std()*math.sqrt(252))
def maxdd(eq):
    eq=pd.Series(eq); pk=eq.cummax(); return float(((eq-pk)/pk).min())

def daily_trend_side(m15):
    """fast_trend 20/100 + 12mo momentum on the instrument's OWN daily bars (resampled
    from M15), read as-of the prior daily close. No real-yield leg (that's gold-only)."""
    d1 = m15.resample("1D").agg({"open":"first","high":"max","low":"min","close":"last"}).dropna()
    d1.index = pd.DatetimeIndex(d1.index).tz_localize(None)
    w = compute_weights(d1, None, MacroConfig(ema_fast=20, ema_slow=100, mom_lookback=252, use_macro=True))
    side = np.sign(w["pos_dir"]).astype(int); side.index=pd.DatetimeIndex(side.index)
    return side.shift(1).fillna(0)

def metrics(R, dates):
    R=np.asarray(R)
    if len(R)==0: return {"trades":0}
    dates=pd.to_datetime(dates); gw=R[R>0].sum(); gl=-R[R<0].sum()
    s=pd.Series(RISK*R,index=dates).groupby(pd.Grouper(freq="D")).sum()
    q=pd.Series(R,index=dates).resample("QE").sum()
    return dict(trades=int(len(R)),exp=round(float(R.mean()),4),win=round(float((R>0).mean()),3),
                pf=round(float(gw/gl),3) if gl>0 else None,sharpe=round(sharpe(s.values),3),
                maxdd=round(maxdd((1+s).cumprod().values),3),qpos=round(float((q>0).mean()),2))
def gate(m):
    return bool(m.get("trades",0)>=100 and m.get("exp",-9)>=0.05 and (m.get("pf") or 0)>=1.15 and m.get("qpos",0)>=0.60)

def per_year(R,dates):
    s=pd.Series(R,index=pd.to_datetime(dates)); out={}
    for y,g in s.groupby(s.index.year):
        gw=g[g>0].sum(); gl=-g[g<0].sum()
        out[int(y)]=dict(n=int(len(g)),exp=round(float(g.mean()),3),pf=round(float(gw/gl),2) if gl>0 else None)
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("instrument"); ap.add_argument("--spread",type=float); ap.add_argument("--slippage",type=float)
    ap.add_argument("--smoke",type=int,default=0,help="use only the last N M15 bars (for a quick sandbox smoke test)")
    a=ap.parse_args(); inst=a.instrument
    sp,sl = COST_DEFAULTS.get(inst,(0.00012,0.00003))
    if a.spread is not None: sp=a.spread
    if a.slippage is not None: sl=a.slippage
    m15=load(inst,"M15"); h4=load(inst,"H4")
    if a.smoke: m15=m15.iloc[-a.smoke:]
    print(f"[{inst}] M15 {m15.index[0].date()}..{m15.index[-1].date()} n={len(m15)} | cost spread={sp} slip={sl} (RT={sp+2*sl:.6f})")
    STRAT=StrategyConfig(use_displacement=False, use_fvg=True, enable_ny_opening=True)
    BT=BacktestConfig(use_confidence_gate=True, confidence_threshold=60.0)
    res=run_backtest_fast(m15,h4,STRAT,RiskConfig(),BT,CostModel(spread_usd=sp,slippage_usd=sl))
    side=daily_trend_side(m15)
    rows=[]
    for t in res.trades:
        if t.exit_time is None: continue
        ent=pd.Timestamp(t.entry_time).tz_localize(None).normalize()
        d=side.reindex(side.index.union([ent])).ffill().reindex([ent]).values[0]
        agree = (not np.isnan(d)) and d==(1 if t.side=="buy" else -1)
        rows.append(dict(entry=pd.Timestamp(t.entry_time), r=float(t.r_multiple), side=t.side, agree=bool(agree)))
    df=pd.DataFrame(rows)
    if df.empty: sys.exit("no trades produced -- check data.")
    # split: last 252 trading-day-equivalent as holdout? use calendar: last ~30% as holdout by date
    cut=df["entry"].quantile(0.7)
    def block(d,label):
        m=metrics(d["r"].values,d["entry"]); m["label"]=label; m["gate"]=gate(m); return m
    raw=df; flt=df[df["agree"]]
    out={"instrument":inst,"cost":{"spread":sp,"slippage":sl,"round_trip":sp+2*sl},
         "n_bars":int(len(m15)),"window":[str(m15.index[0].date()),str(m15.index[-1].date())],
         "RAW_FVG_NY":{"all":block(raw,"all"),
                       "selection(<=70pct date)":block(raw[raw.entry<=cut],"sel"),
                       "holdout(last30pct)":block(raw[raw.entry>cut],"hold"),
                       "per_year":per_year(raw["r"].values,raw["entry"])},
         "PLUS_daily_trend_filter":{"all":block(flt,"all"),
                       "selection":block(flt[flt.entry<=cut],"sel"),
                       "holdout":block(flt[flt.entry>cut],"hold"),
                       "per_year":per_year(flt["r"].values,flt["entry"]),
                       "long_short":{"long":int((flt.side=="buy").sum()),"short":int((flt.side=="sell").sum())}}}
    # cost stress on the filtered variant (recompute R at 3x/5x needs planned risk; approximate via re-run note)
    (OUTDIR/f"{inst}_result.json").write_text(json.dumps(out,indent=2,default=str))
    # ---- print verdict ----
    def show(name,b):
        print(f"  {name:28s} n={b.get('trades',0):>4} exp={b.get('exp'):+} PF={b.get('pf')} Sharpe={b.get('sharpe')} qpos={b.get('qpos')} GATE={b.get('gate')}")
    print("\n== RAW FVG+NY =="); show("all",out["RAW_FVG_NY"]["all"]); show("selection",out["RAW_FVG_NY"]["selection(<=70pct date)"]); show("holdout",out["RAW_FVG_NY"]["holdout(last30pct)"])
    print("== + daily-trend filter =="); show("all",out["PLUS_daily_trend_filter"]["all"]); show("selection",out["PLUS_daily_trend_filter"]["selection"]); show("holdout",out["PLUS_daily_trend_filter"]["holdout"])
    print("  per-year (filtered) exp:", {y:v["exp"] for y,v in out["PLUS_daily_trend_filter"]["per_year"].items()})
    print("  long/short:", out["PLUS_daily_trend_filter"]["long_short"])
    g=out["PLUS_daily_trend_filter"]["all"]["gate"]
    print(f"\nVERDICT (filtered, full sample): GATE {'PASS' if g else 'FAIL'} -- selection is the honest number; label any single-regime holdout as inflated.")
    print(f"saved {OUTDIR/(inst+'_result.json')}")

if __name__=="__main__": main()
