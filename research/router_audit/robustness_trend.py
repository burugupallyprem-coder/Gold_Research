"""
robustness_trend.py — #1 trend-filter robustness + #9 sensitivity + #10 rolling walk-forward.
Post-processing on the fixed FVG+NY trade universe (trades_*.csv). Direction filters are the
one thing we vary; the entries themselves are the engine's real trades. No engine re-run.

Reports the SPREAD across neighbouring parameters (robustness), not just the best pick.
"""
from __future__ import annotations
import json, math, glob
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/"reports"/"backtest_data_2026-07-25"
RISK=0.01; COST_RT=0.40; SPLIT=pd.Timestamp("2024-01-01"); VAL_END=pd.Timestamp("2026-07-01")

def sharpe(s):
    s=pd.Series(s).dropna(); return 0.0 if (len(s)<20 or s.std()==0) else float(s.mean()/s.std()*math.sqrt(252))
def r_at_cost(r1x,rp,k): return r1x-COST_RT*(k-1)/rp

# ---- load universe trades + daily OHLC ----
def load_universe():
    t=pd.concat([pd.read_csv(f) for f in sorted(glob.glob(str(OUT/"trades_*.csv")))],ignore_index=True)
    t["entry_ts"]=pd.to_datetime(t["entry_ts"],utc=True); t["exit_ts"]=pd.to_datetime(t["exit_ts"],utc=True)
    t=t.sort_values("entry_ts").drop_duplicates(subset=["entry_ts","side","entry"]).reset_index(drop=True)
    return t
def daily():
    px=pd.read_csv(ROOT/"data"/"daily"/"XAU_USD_D.csv",parse_dates=["time"]).set_index("time").sort_index()
    px.index=pd.DatetimeIndex(px.index); return px

def adx(px,n=14):
    h,l,c=px["high"],px["low"],px["close"]
    up=h.diff(); dn=-l.diff()
    plus=np.where((up>dn)&(up>0),up,0.0); minus=np.where((dn>up)&(dn>0),dn,0.0)
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr=tr.ewm(alpha=1/n,adjust=False).mean()
    pdi=100*pd.Series(plus,index=px.index).ewm(alpha=1/n,adjust=False).mean()/atr
    mdi=100*pd.Series(minus,index=px.index).ewm(alpha=1/n,adjust=False).mean()/atr
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    return dx.ewm(alpha=1/n,adjust=False).mean()

def trend_side(px, kind="ema", fast=20, slow=100, mom=252, adx_thr=None):
    c=px["close"].astype(float)
    if kind=="ema":
        f=c.ewm(span=fast,adjust=False).mean(); s=c.ewm(span=slow,adjust=False).mean()
    else:
        f=c.rolling(fast).mean(); s=c.rolling(slow).mean()
    tr=np.sign(f-s)
    m=c/c.shift(mom)-1.0
    direction=np.where((tr>0)&(m>0),1,np.where((tr<0)&(m<0),-1,0))
    side=pd.Series(direction,index=px.index)
    if adx_thr is not None:
        side=side.where(adx(px)>=adx_thr, 0)
    return side.shift(1).fillna(0)   # as-of prior close

def apply_side(t, side):
    ed=t["entry_ts"].dt.tz_convert(None).dt.normalize()
    grid=side.reindex(side.index.union(pd.DatetimeIndex(ed.unique()))).ffill()
    al=grid.reindex(ed).values
    r=t[(t["side"]==al)&(al!=0)].copy()
    return r

def metrics(r, col, lo, hi):
    d=r[(r["exit_ts"].dt.tz_convert(None)>=lo)&(r["exit_ts"].dt.tz_convert(None)<hi)]
    R=d[col].values
    if len(R)==0: return dict(n=0)
    gw=R[R>0].sum(); gl=-R[R<0].sum()
    s=pd.Series(RISK*R,index=d["exit_ts"].dt.tz_convert(None)).groupby(pd.Grouper(freq="D")).sum()
    q=pd.Series(R,index=d["exit_ts"].dt.tz_convert(None)).resample("QE").sum()
    return dict(n=int(len(R)),exp=round(float(R.mean()),3),pf=round(float(gw/gl),2) if gl>0 else None,
                sharpe=round(sharpe(s.values),2),qpos=round(float((q>0).mean()),2))

def gate(m): return bool(m.get("n",0)>=100 and m.get("exp",-9)>=0.05 and (m.get("pf") or 0)>=1.15 and m.get("qpos",0)>=0.60)

def main():
    t=load_universe(); px=daily()
    variants={
      "EMA 20/100 (baseline)":dict(kind="ema",fast=20,slow=100,mom=252),
      "EMA 18/90":dict(kind="ema",fast=18,slow=90,mom=252),
      "EMA 22/110":dict(kind="ema",fast=22,slow=110,mom=252),
      "EMA 20/150":dict(kind="ema",fast=20,slow=150,mom=252),
      "EMA 20/200":dict(kind="ema",fast=20,slow=200,mom=252),
      "EMA 50/200":dict(kind="ema",fast=50,slow=200,mom=252),
      "EMA 50/150":dict(kind="ema",fast=50,slow=150,mom=252),
      "SMA 20/100":dict(kind="sma",fast=20,slow=100,mom=252),
      "SMA 50/200":dict(kind="sma",fast=50,slow=200,mom=252),
      "mom 3mo (63)":dict(kind="ema",fast=20,slow=100,mom=63),
      "mom 6mo (126)":dict(kind="ema",fast=20,slow=100,mom=126),
      "mom 9mo (189)":dict(kind="ema",fast=20,slow=100,mom=189),
      "ADX>20 (EMA20/100)":dict(kind="ema",fast=20,slow=100,mom=252,adx_thr=20),
      "ADX>25 (EMA20/100)":dict(kind="ema",fast=20,slow=100,mom=252,adx_thr=25),
      "ADX>30 (EMA20/100)":dict(kind="ema",fast=20,slow=100,mom=252,adx_thr=30),
    }
    rows={}
    for name,cfg in variants.items():
        r=apply_side(t,trend_side(px,**cfg))
        for k in (1,3,5): r[f"R{k}"]=r_at_cost(r["r_1x"],r["risk_price"],k)
        sel=metrics(r,"R1",pd.Timestamp("2000-01-01"),SPLIT)
        hold=metrics(r,"R1",SPLIT,VAL_END)
        hold3=metrics(r,"R3",SPLIT,VAL_END); hold5=metrics(r,"R5",SPLIT,VAL_END)
        rows[name]=dict(sel=sel,hold=hold,hold3=hold3,hold5=hold5,gate_hold=gate(hold))
    # rolling walk-forward (test-year expectancy), baseline + 3 robustness neighbours
    wf_variants={"EMA 20/100":dict(kind="ema",fast=20,slow=100,mom=252),
                 "EMA 50/200":dict(kind="ema",fast=50,slow=200,mom=252),
                 "EMA 20/200":dict(kind="ema",fast=20,slow=200,mom=252),
                 "ADX>25":dict(kind="ema",fast=20,slow=100,mom=252,adx_thr=25)}
    wf={}
    for name,cfg in wf_variants.items():
        r=apply_side(t,trend_side(px,**cfg)); r["R1"]=r["r_1x"]
        yr={}
        for y in (2020,2021,2022,2023,2024,2025):
            m=metrics(r,"R1",pd.Timestamp(f"{y}-01-01"),pd.Timestamp(f"{y+1}-01-01"))
            yr[y]=(m.get("n",0),m.get("exp"))
        wf[name]=yr
    out={"trend_variants":rows,"rolling_walkforward":wf,
         "sensitivity_note":"compare neighbours (18/90, 20/100, 22/110, 20/150) — small changes should give similar numbers if robust"}
    (OUT/"robustness_trend.json").write_text(json.dumps(out,indent=2,default=str))
    # print
    print(f"{'variant':24s} {'selEXP':>7} {'selSh':>6} {'holdEXP':>8} {'holdSh':>7} {'hn':>4} {'h3EXP':>6} {'h5EXP':>6} {'gate':>5}")
    for n,d in rows.items():
        print(f"{n:24s} {d['sel'].get('exp'):>7} {d['sel'].get('sharpe'):>6} {d['hold'].get('exp'):>8} {d['hold'].get('sharpe'):>7} {d['hold'].get('n'):>4} {d['hold3'].get('exp'):>6} {d['hold5'].get('exp'):>6} {str(d['gate_hold']):>5}")
    print("\nRolling walk-forward (test-year: n, expectancyR) @1x:")
    for n,yr in wf.items():
        print(f"  {n:12s}", {y:v for y,v in yr.items()})

if __name__=="__main__": main()
