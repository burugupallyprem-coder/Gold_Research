"""
research/router_audit/analyze.py
================================
STEP 2 of the honest-router audit. Consumes the collected FVG+NY trades and
produces EVERYTHING in reports/honest_router_vs_hindsight_2026-07-25.md, PLUS an
explicit verification block that answers a skeptical trader's six questions.

Run (fast, no engine):  python analyze.py
Outputs (all in reports/backtest_data_2026-07-25/):
  analysis.json            - every metric in the report
  router_trade_log.csv     - CONSOLIDATED, per-trade audit log (inspect this)
  verification.json        - the six-concern diagnostics
  eq_router.csv/eq_buyhold.csv/eq_hindsight.csv - equity curves

Definitions locked here (see the report's methodology doc):
  RISK          = 0.01     equity fraction risked per trade (R -> equity)
  COST_RT       = 0.40     round-trip gold points at 1x; k x => 0.40*k
  R at cost k   = r_1x - 0.40*(k-1)/risk_price     [exact; risk_price = planned risk]
  Sharpe        = mean(daily_eq_return)/std(...) * sqrt(252),  rf = 0
                  daily_eq_return = sum over trades EXITING that day of RISK*R
  quarters +    = fraction of calendar quarters whose summed R > 0
  SPLIT         = 2024-01-01  (train/selection < SPLIT ; validation/holdout >= SPLIT)
  VAL_END       = 2026-07-01
"""
from __future__ import annotations
import json, math, glob
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; import sys; sys.path.insert(0, str(ROOT))
from strategy.macro_trend import MacroConfig, compute_weights

OUT   = ROOT/"reports"/"backtest_data_2026-07-25"
RISK  = 0.01
COST_RT = 0.40
SPLIT   = pd.Timestamp("2024-01-01")
VAL_END = pd.Timestamp("2026-07-01")
RRmap = {"NY":3.0, "FVG":2.5, "OTHER":2.5}

def r_at_cost(r1x, risk_price, k):  return r1x - COST_RT*(k-1)/risk_price
def sharpe(daily_ret):
    d = pd.Series(daily_ret).dropna()
    return 0.0 if (len(d)<20 or d.std()==0) else float(d.mean()/d.std()*math.sqrt(252))   # rf=0
def maxdd(eq):
    eq=pd.Series(eq); pk=eq.cummax(); return float(((eq-pk)/pk).min())

def daily_side_raw_and_shifted():
    """Returns (allowed_shifted, posdir_raw). allowed_shifted[date D] uses the daily
    bar's pos_dir from the PRIOR close (shift 1) -> no same-day lookahead."""
    px = pd.read_csv(ROOT/"data"/"daily"/"XAU_USD_D.csv", parse_dates=["time"]).set_index("time").sort_index()
    w = compute_weights(px, None, MacroConfig(ema_fast=20, ema_slow=100, mom_lookback=252, use_macro=True))
    raw = np.sign(w["pos_dir"]).astype(int); raw.index = pd.DatetimeIndex(raw.index)
    shifted = raw.shift(1).fillna(0)           # AS-OF PRIOR DAILY CLOSE
    return shifted, raw, px

def metrics_block(R, dates, label):
    R=np.asarray(R)
    if len(R)==0: return {"trades":0,"label":label}
    dates=pd.to_datetime(dates)
    gw=R[R>0].sum(); gl=-R[R<0].sum()
    s=pd.Series(RISK*R, index=dates).groupby(pd.Grouper(freq="D")).sum()
    eq=(1+s).cumprod(); q=pd.Series(R,index=dates).resample("QE").sum()
    return dict(trades=int(len(R)), expectancy_R=round(float(R.mean()),4),
                win_rate=round(float((R>0).mean()),3),
                profit_factor=round(float(gw/gl),3) if gl>0 else None,
                total_R=round(float(R.sum()),1), sharpe=round(sharpe(s.values),3),
                maxdd=round(maxdd(eq.values),3), q_pos_frac=round(float((q>0).mean()),2),
                n_quarters=int(len(q)), label=label)
def gate(m):
    return bool(m.get("trades",0)>=100 and m.get("expectancy_R",-9)>=0.05
               and (m.get("profit_factor") or 0)>=1.15 and m.get("q_pos_frac",0)>=0.60)

def main():
    files = sorted(glob.glob(str(OUT/"trades_*.csv")))
    t = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    t["entry_ts"]=pd.to_datetime(t["entry_ts"], utc=True); t["exit_ts"]=pd.to_datetime(t["exit_ts"], utc=True)
    t = t.sort_values("entry_ts").drop_duplicates(subset=["entry_ts","side","entry"]).reset_index(drop=True)

    allowed_shift, raw, px = daily_side_raw_and_shifted()
    ed = t["entry_ts"].dt.tz_convert(None).dt.normalize()
    grid = allowed_shift.reindex(allowed_shift.index.union(pd.DatetimeIndex(ed.unique()))).ffill()
    t["allowed_side"] = grid.reindex(ed).values
    t["agree"] = (t["side"]==t["allowed_side"]) & (t["allowed_side"]!=0)
    router = t[t["agree"]].copy()
    for k in (1,3,5): router[f"R{k}"]=r_at_cost(router["r_1x"], router["risk_price"], k)
    router["window"]=np.where(router["exit_ts"].dt.tz_convert(None)<SPLIT,"selection","holdout")

    # ---------- consolidated audit trade log ----------
    log = router[["entry_ts","exit_ts","side","setup","entry","risk_price","allowed_side","window","r_1x","R1","R3","R5"]].copy()
    log.columns=["entry_ts","exit_ts","side","setup","entry","risk_price","allowed_side","window","R_1x","R_1x_chk","R_3x","R_5x"]
    log.to_csv(OUT/"router_trade_log.csv", index=False)

    res={"universe_trades":int(len(t)),"router_trades":int(len(router))}
    def split(df,col):
        sel=df[df["exit_ts"].dt.tz_convert(None)<SPLIT]; hold=df[(df["exit_ts"].dt.tz_convert(None)>=SPLIT)&(df["exit_ts"].dt.tz_convert(None)<VAL_END)]
        return sel,hold
    res["HONEST_ROUTER"]={}
    for k in (1,3,5):
        sel,hold=split(router,f"R{k}")
        res["HONEST_ROUTER"][f"selection_{k}x"]=metrics_block(sel[f"R{k}"], sel["exit_ts"].dt.tz_convert(None), f"selection(train<2024) {k}x")
        res["HONEST_ROUTER"][f"holdout_{k}x"]  =metrics_block(hold[f"R{k}"], hold["exit_ts"].dt.tz_convert(None), f"holdout(2024-2026 BULL) {k}x")
    res["GATE_validation_1x"]={"PASS":gate(res["HONEST_ROUTER"]["holdout_1x"]),"metrics":res["HONEST_ROUTER"]["holdout_1x"]}
    res["long_short_split"]={"long":int((router["side"]==1).sum()),"short":int((router["side"]==-1).sum())}

    def eqcurve(df,col):
        s=pd.Series(RISK*df[col].values, index=df["exit_ts"].dt.tz_convert(None)).sort_index().groupby(pd.Grouper(freq="D")).sum()
        return (1+s).cumprod()
    router_eq=eqcurve(router.sort_values("exit_ts"),"R1"); router_eq.to_csv(OUT/"eq_router.csv")

    # ---------- buy & hold (passive, daily close, full compounding, NO cost/leverage/vol-target) ----------
    pc=px["close"].astype(float); ret=pc.pct_change().fillna(0)
    win_start=router["exit_ts"].dt.tz_convert(None).min().normalize()
    bh_sel=ret[(ret.index>=win_start)&(ret.index<SPLIT)]; bh_hold=ret[(ret.index>=SPLIT)&(ret.index<VAL_END)]
    res["BUY_HOLD_gold"]={"definition":"daily close pct-change, full compounding, no leverage/vol-target/cost/cash-drag",
      "selection_window":[str(win_start.date()),str(SPLIT.date())],"holdout_window":[str(SPLIT.date()),str(VAL_END.date())],
      "selection":{"total_ret_pct":round(float((1+bh_sel).prod()-1)*100,1),"sharpe":round(sharpe(bh_sel.values),3),"maxdd":round(maxdd((1+bh_sel).cumprod().values),3)},
      "holdout(BULL)":{"total_ret_pct":round(float((1+bh_hold).prod()-1)*100,1),"sharpe":round(sharpe(bh_hold.values),3),"maxdd":round(maxdd((1+bh_hold).cumprod().values),3)}}
    (1+ret[ret.index>=win_start]).cumprod().to_csv(OUT/"eq_buyhold.csv")
    rh=router_eq[router_eq.index>=SPLIT]
    res["router_total_ret_holdout_pct"]=round(float((rh.iloc[-1]/rh.iloc[0]-1)*100),1) if len(rh) else None

    # ---------- HINDSIGHT best-of (weekly). ISOLATED: reads component streams only; never writes router ----------
    w=compute_weights(px,None,MacroConfig(ema_fast=20,ema_slow=100,mom_lookback=252,use_macro=True))["weight"]
    trend_wk=(w.shift(1).fillna(0)*pc.pct_change().fillna(0)).resample("W").sum()
    def comp_wk(setup):
        d=router[router["setup"]==setup]
        return pd.Series(RISK*d["R1"].values,index=d["exit_ts"].dt.tz_convert(None)).groupby(pd.Grouper(freq="D")).sum().resample("W").sum()
    comp=pd.concat({"trend":trend_wk,"FVG":comp_wk("FVG"),"NY":comp_wk("NY")},axis=1).fillna(0.0)
    comp=comp[(comp.index>=win_start)&(comp.index<VAL_END)]
    best=comp.max(axis=1); hind_eq=(1+best).cumprod(); hind_eq.to_csv(OUT/"eq_hindsight.csv")
    def wk_sharpe(x): x=x.dropna(); return 0.0 if (len(x)<8 or x.std()==0) else float(x.mean()/x.std()*math.sqrt(52))
    res["HINDSIGHT_bestof"]={"components":["trend","FVG","NY"],"weekly_sharpe_full":round(wk_sharpe(best),2),
      "weekly_sharpe_holdout":round(wk_sharpe(best[best.index>=SPLIT]),2),
      "total_ret_full_pct":round(float((hind_eq.iloc[-1]/hind_eq.iloc[0]-1)*100),1),
      "weeks_positive_pct":round(float((best>0).mean()*100),1),
      "honest_avg_component_weekly_sharpe":round(float(np.mean([wk_sharpe(comp[c]) for c in comp.columns])),2),
      "isolation":"router metrics computed BEFORE this block; hindsight reads component R streams only, never mutates router"}

    # ---------- RANDOM-side benchmark ----------
    m15=pd.read_csv(ROOT/"data"/"candles"/"XAU_USD_M15.csv",parse_dates=["time"]).set_index("time").sort_index()
    if m15.index.tz is None: m15.index=m15.index.tz_localize("UTC")
    mi=m15.index.values; hh=m15["high"].values; ll=m15["low"].values; oo=m15["open"].values; H=288
    hold=router[(router["exit_ts"].dt.tz_convert(None)>=SPLIT)&(router["exit_ts"].dt.tz_convert(None)<VAL_END)].copy()
    def bracket_R(i0,s,risk,rr):
        entry=oo[i0]; stop=entry-s*risk; tgt=entry+s*rr*risk
        for j in range(i0,min(i0+H,len(oo))):
            if s==1:
                if ll[j]<=stop: return (-risk-COST_RT)/risk
                if hh[j]>=tgt:  return (rr*risk-COST_RT)/risk
            else:
                if hh[j]>=stop: return (-risk-COST_RT)/risk
                if ll[j]<=tgt:  return (rr*risk-COST_RT)/risk
        return 0.0
    Rl=[];Rs=[];sides=[]
    for _,r in hold.iterrows():
        i=int(np.searchsorted(mi,np.datetime64(r["entry_ts"].tz_convert(None)),"right"))
        if i>=len(oo): continue
        rr=RRmap.get(r["setup"],2.5); risk=float(r["risk_price"])
        Rl.append(bracket_R(i,1,risk,rr)); Rs.append(bracket_R(i,-1,risk,rr)); sides.append(int(r["side"]))
    Rl=np.array(Rl);Rs=np.array(Rs);sides=np.array(sides)
    router_sim=float(np.where(sides==1,Rl,Rs).mean())
    rng=np.random.default_rng(7)
    seeds=np.array([np.where(rng.integers(0,2,len(Rl))==1,Rl,Rs).mean() for _ in range(1000)])
    res["RANDOM_side_benchmark_holdout"]={"method":"SAME entry timestamps as router; SAME per-trade risk_price; SAME RR by setup (FVG 2.5, NY 3.0); SAME cost 0.40; SAME simplified bracket (stop=risk, target=RR*risk, hold cap H=288 M15 bars ~3 trading days); ONLY the side is coin-flipped. 1000 seeds.",
      "n_entries":int(len(Rl)),"same_trade_count":True,
      "router_sim_expectancy_R":round(router_sim,4),
      "router_engine_expectancy_R":round(float(hold["R1"].mean()),4),
      "note_engine_vs_sim":"engine R (0.213) vs sim R (this) differ because the sim omits BE moves/swing stops; both sides use the SAME sim so the percentile is apples-to-apples",
      "random_mean_R":round(float(seeds.mean()),4),"random_p05_R":round(float(np.percentile(seeds,5)),4),
      "random_p95_R":round(float(np.percentile(seeds,95)),4),
      "router_percentile_vs_random":round(float((seeds<router_sim).mean()*100),1)}

    # ---------- VERIFICATION diagnostics (the six concerns) ----------
    # #5 no-lookahead proof: for sample trades, show the daily bar date supplying the side.
    samp=[]
    raw_idx=raw.index
    for _,r in router.head(6).iterrows():
        D=pd.Timestamp(r["entry_ts"]).tz_convert(None).normalize()
        prior=raw_idx[raw_idx< D]                     # strictly BEFORE entry day
        src=prior[-1] if len(prior) else None
        samp.append({"entry_day":str(D.date()),"side_source_daily_bar":str(src.date()) if src is not None else None,
                     "allowed_side_used":int(r["allowed_side"]),
                     "equals_sign_of_prior_posdir":bool(int(r["allowed_side"])==int(raw.loc[src])) if src is not None else None})
    verify={
      "1_report_artifacts":{"trade_log":"router_trade_log.csv","equity_curves":["eq_router.csv","eq_buyhold.csv","eq_hindsight.csv"],
                            "chart":"reports/router_vs_hindsight_2026-07-25.png","all_metrics":"analysis.json"},
      "2_random_benchmark":res["RANDOM_side_benchmark_holdout"],
      "3_sharpe":{"formula":"mean(daily_equity_return)/std(daily_equity_return)*sqrt(252)","risk_free":0.0,
                  "frequency":"DAILY equity returns (RISK*R summed by trade EXIT date)","annualization":"sqrt(252)",
                  "hindsight_uses":"WEEKLY returns * sqrt(52) (labelled separately)"},
      "4_buy_hold":res["BUY_HOLD_gold"],
      "5_momentum_no_lookahead":{"rule":"allowed_side = sign(pos_dir).shift(1) => uses PRIOR daily close",
                                 "mom_lookback":"px/px.shift(252)-1 (all past)","emas":"causal ewm(adjust=False)",
                                 "samples":samp},
      "6_hindsight_isolation":res["HINDSIGHT_bestof"]["isolation"]}
    res["VERIFICATION"]=verify

    (OUT/"analysis.json").write_text(json.dumps(res,indent=2,default=str))
    (OUT/"verification.json").write_text(json.dumps(verify,indent=2,default=str))
    print("WROTE router_trade_log.csv (%d rows), analysis.json, verification.json"%len(log))
    print("router selection 1x:",res["HONEST_ROUTER"]["selection_1x"]["sharpe"],"holdout 1x:",res["HONEST_ROUTER"]["holdout_1x"]["sharpe"])
    print("gate:",res["GATE_validation_1x"]["PASS"],"| buyhold hold sharpe:",res["BUY_HOLD_gold"]["holdout(BULL)"]["sharpe"])
    print("random percentile:",res["RANDOM_side_benchmark_holdout"]["router_percentile_vs_random"])
    print("no-lookahead sample:",json.dumps(samp[:3]))

if __name__=="__main__": main()
