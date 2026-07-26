"""
robustness_overlays.py — #3 exits, #4 ATR vol filter, #5 risk overlays, #6 session windows,
#8 loser analysis, #7 confidence reframe. Post-processing on the baseline router (EMA20/100).

IMPORTANT HONEST CAVEAT: the exit tests RE-SIMULATE each entry on the M15 path with a
simplified bracket (fixed/ATR/trailing/partial/BE/time). This is NOT the production engine
(it omits the engine's swing-stop nuance), so treat exit expectancies as *relative* comparisons
among themselves, not as the engine's exact P&L. The #4/#5/#6/#8 overlays use the engine's own
realized r_1x and are exact.
"""
from __future__ import annotations
import json, math, glob
from pathlib import Path
import numpy as np, pandas as pd
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/"reports"/"backtest_data_2026-07-25"
ET=ZoneInfo("America/New_York")
RISK=0.01; COST_RT=0.40; SPLIT=pd.Timestamp("2024-01-01"); VAL_END=pd.Timestamp("2026-07-01")
RRmap={"NY":3.0,"FVG":2.5,"OTHER":2.5}

def sharpe(s):
    s=pd.Series(s).dropna(); return 0.0 if (len(s)<20 or s.std()==0) else float(s.mean()/s.std()*math.sqrt(252))

def load_router():
    import sys; sys.path.insert(0,str(ROOT))
    from strategy.macro_trend import MacroConfig, compute_weights
    t=pd.concat([pd.read_csv(f) for f in sorted(glob.glob(str(OUT/"trades_*.csv")))],ignore_index=True)
    t["entry_ts"]=pd.to_datetime(t["entry_ts"],utc=True); t["exit_ts"]=pd.to_datetime(t["exit_ts"],utc=True)
    t=t.sort_values("entry_ts").drop_duplicates(subset=["entry_ts","side","entry"]).reset_index(drop=True)
    px=pd.read_csv(ROOT/"data"/"daily"/"XAU_USD_D.csv",parse_dates=["time"]).set_index("time").sort_index()
    w=compute_weights(px,None,MacroConfig(ema_fast=20,ema_slow=100,mom_lookback=252,use_macro=True))
    side=np.sign(w["pos_dir"]).astype(int); side.index=pd.DatetimeIndex(side.index); side=side.shift(1).fillna(0)
    ed=t["entry_ts"].dt.tz_convert(None).dt.normalize()
    grid=side.reindex(side.index.union(pd.DatetimeIndex(ed.unique()))).ffill()
    t["allowed"]=grid.reindex(ed).values
    r=t[(t["side"]==t["allowed"])&(t["allowed"]!=0)].copy().reset_index(drop=True)
    return r

def load_m15():
    m=pd.read_csv(ROOT/"data"/"candles"/"XAU_USD_M15.csv",parse_dates=["time"]).set_index("time").sort_index()
    if m.index.tz is None: m.index=m.index.tz_localize("UTC")
    h,l,c=m["high"],m["low"],m["close"]
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    m["atr"]=tr.rolling(56).mean()   # ~14 hours ATR on M15 (proxy for session vol)
    return m

def gate(n,exp,pf,qpos): return bool(n>=100 and exp>=0.05 and (pf or 0)>=1.15 and qpos>=0.60)

def main():
    r=load_router(); m=load_m15()
    mi=m.index.values; O=m["open"].values; H=m["high"].values; L=m["low"].values; C=m["close"].values; A=m["atr"].values
    et=m.index.tz_convert(ET); et_hour=et.hour+et.minute/60.0
    # entry index per router trade
    r["i"]=np.searchsorted(mi, r["entry_ts"].values, side="right")
    r=r[r["i"]<len(O)-1].reset_index(drop=True)
    hold=r[(r["exit_ts"].dt.tz_convert(None)>=SPLIT)&(r["exit_ts"].dt.tz_convert(None)<VAL_END)].reset_index(drop=True)
    Hcap=288

    def sim_exit(row, mode):
        # CLEAN rewrite. R measured in units of the trade's 1R (=risk_price, or 1.5*ATR for atr mode).
        # exit multiplier = 0.5 if a partial was already booked, else 1.0. cost charged once.
        i=int(row["i"]); s=int(row["side"]); risk=float(row["risk_price"]); rr=RRmap.get(row["setup"],2.5)
        atr=A[i] if not np.isnan(A[i]) else risk
        entry=O[i]
        if mode=="atr_fixed": risk=1.5*atr
        if risk<=0: return 0.0
        be_at={"be1":1.0,"be15":1.5,"be2":2.0}.get(mode)
        trail=mode in ("atr_trail","partial_trail"); part=mode=="partial_trail"
        tcap={"time12":12,"time24":24}.get(mode, Hcap)
        stop=entry - s*risk; tgt=entry + s*rr*risk
        peak=entry; have_partial=False; booked=0.0
        end=min(i+tcap,len(O))
        for j in range(i,end):
            hi,lo=H[j],L[j]; fav_hi=s*(hi-entry)     # best favorable excursion this bar
            if part and not have_partial and fav_hi>=risk:      # take half at +1R, remainder to BE
                booked=0.5*1.0; have_partial=True; stop=entry
            if be_at is not None and fav_hi>=be_at*risk:        # move to break-even
                stop=entry
            mult=0.5 if have_partial else 1.0
            if s==1:
                if lo<=stop: return booked + mult*((stop-entry)/risk) - COST_RT/risk
                if (not trail) and hi>=tgt: return booked + mult*rr - COST_RT/risk
            else:
                if hi>=stop: return booked + mult*((entry-stop)/risk) - COST_RT/risk
                if (not trail) and lo<=tgt: return booked + mult*rr - COST_RT/risk
            if trail:                                            # trail 1.5*ATR from favorable peak
                if s==1:
                    peak=max(peak,hi); stop=max(stop, peak-1.5*atr)
                else:
                    peak=min(peak,lo); stop=min(stop, peak+1.5*atr)
        j=end-1; mult=0.5 if have_partial else 1.0
        return booked + mult*(s*(C[j]-entry)/risk) - COST_RT/risk

    modes=["fixed","be1","be15","be2","atr_fixed","atr_trail","partial_trail","time12","time24"]
    res={"exits_holdout":{}}
    for mode in modes:
        Rr=hold.apply(lambda row: sim_exit(row,mode),axis=1).values
        gw=Rr[Rr>0].sum(); gl=-Rr[Rr<0].sum()
        res["exits_holdout"][mode]=dict(n=int(len(Rr)),exp=round(float(Rr.mean()),3),
            pf=round(float(gw/gl),2) if gl>0 else None, win=round(float((Rr>0).mean()),3))
    # engine baseline for reference
    res["exits_holdout"]["ENGINE_r1x(ref)"]=dict(n=int(len(hold)),exp=round(float(hold["r_1x"].mean()),3),
        pf=round(float(hold.loc[hold.r_1x>0,"r_1x"].sum()/-hold.loc[hold.r_1x<0,"r_1x"].sum()),2), win=round(float((hold["r_1x"]>0).mean()),3))

    # #4 ATR vol buckets (engine r_1x, exact) on holdout
    hold=hold.copy(); hold["atr_entry"]=A[hold["i"].values]
    hold["atr_med"]=np.nanmedian(hold["atr_entry"])
    def bstats(d):
        R=d["r_1x"].values; gw=R[R>0].sum(); gl=-R[R<0].sum()
        return dict(n=int(len(R)),exp=round(float(R.mean()),3),pf=round(float(gw/gl),2) if gl>0 else None)
    q=hold["atr_entry"].quantile([0.33,0.66,0.9])
    res["atr_buckets_holdout"]={
        "low_atr(<33pct)":bstats(hold[hold.atr_entry<=q[0.33]]),
        "mid_atr":bstats(hold[(hold.atr_entry>q[0.33])&(hold.atr_entry<=q[0.66])]),
        "high_atr(66-90)":bstats(hold[(hold.atr_entry>q[0.66])&(hold.atr_entry<=q[0.9])]),
        "extreme_atr(>90pct)":bstats(hold[hold.atr_entry>q[0.9]])}

    # #6 session buckets by ET minutes since NY 8:00 open (engine r_1x)
    ehr=pd.Series(et_hour, index=m.index)
    hold["ethour"]=ehr.reindex(hold["entry_ts"]).values
    def sess(dlo,dhi):
        d=hold[(hold.ethour>=dlo)&(hold.ethour<dhi)]; return bstats(d)
    res["session_buckets_holdout(ET hour)"]={
        "08:00-08:30":sess(8,8.5),"08:30-09:00":sess(8.5,9),"09:00-09:30":sess(9,9.5),
        "09:30-11:00":sess(9.5,11),"rest_of_day":sess(0,8) }
    # NY-only subset windows
    ny=hold[hold.setup=="NY"]
    def nsess(dlo,dhi): d=ny[(ny.ethour>=dlo)&(ny.ethour<dhi)]; return bstats(d)
    res["NY_first_minutes_holdout"]={"first30(8-8.5)":nsess(8,8.5),"first60(8-9)":nsess(8,9),"first90(8-9.5)":nsess(8,9.5)}

    # #8 loser analysis (engine r_1x): weekday & hour concentration (full sample)
    r_all=r.copy(); r_all["dow"]=r_all["entry_ts"].dt.tz_convert(ET).dt.day_name()
    r_all["ethr"]=pd.Series(et_hour,index=m.index).reindex(r_all["entry_ts"]).values.astype(int)
    def slice_exp(col):
        g=r_all.groupby(col)["r_1x"]; return {str(k):(int(v.count()),round(float(v.mean()),3)) for k,v in g}
    res["loser_analysis_full"]={"by_weekday(n,expR)":slice_exp("dow"),"by_ET_hour(n,expR)":slice_exp("ethr"),
        "by_setup":{k:(int(v.count()),round(float(v.mean()),3)) for k,v in r_all.groupby("setup")["r_1x"]}}

    # #5 risk overlays on chronological holdout sequence (engine r_1x)
    seq=hold.sort_values("entry_ts").reset_index(drop=True)
    def run_overlay(daily_stop=None, max_consec=None, max_per_day=None):
        eq=0.0; peak=0.0; mdd=0.0; day=None; day_pnl=0.0; consec=0; cnt=0; kept=[]
        paused=False
        for _,x in seq.iterrows():
            d=x["entry_ts"].tz_convert(ET).date()
            if d!=day: day=d; day_pnl=0.0; cnt=0; paused=False
            if paused: continue
            if max_per_day and cnt>=max_per_day: continue
            R=x["r_1x"]; eq+=R; day_pnl+=R; cnt+=1; kept.append(R)
            peak=max(peak,eq); mdd=min(mdd,eq-peak)
            consec=consec+1 if R<0 else 0
            if daily_stop and day_pnl<=daily_stop: paused=True
            if max_consec and consec>=max_consec: paused=True
        R=np.array(kept)
        return dict(n=int(len(R)),totR=round(float(R.sum()),1),exp=round(float(R.mean()),3) if len(R) else 0,
                    maxdd_R=round(float(mdd),1))
    res["risk_overlays_holdout"]={
        "baseline(no overlay)":run_overlay(),
        "max_daily_loss_-2R":run_overlay(daily_stop=-2.0),
        "max_3_consec_losses":run_overlay(max_consec=3),
        "max_3_trades_per_day":run_overlay(max_per_day=3),
        "max_daily_-2R + 3/day":run_overlay(daily_stop=-2.0,max_per_day=3)}

    # #7 confidence reframe
    res["confidence_note"]="engine confidence = 30(trigger)+20(HTF)+15(vol)+10(NY)+/-25(macro,default 0). With macro=0, every trade scores 65 (non-NY) or 75 (NY) — all >= gate 60. So the gate is NEAR-INERT on this data (it filters almost nothing). To make confidence predictive we'd need to (a) turn on the macro component or (b) save per-trade FVG size / sweep / structure and correlate — an engine change. Flagged, not faked."

    (OUT/"robustness_overlays.json").write_text(json.dumps(res,indent=2,default=str))
    print(json.dumps(res,indent=2,default=str))

if __name__=="__main__": main()
