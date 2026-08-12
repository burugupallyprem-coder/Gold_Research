"""Gold ORB (intraday NY opening-range breakout) under APEX $50k - in the GOLD repo, on MGC economics.

Ports the stock/forex ORB idea to gold M15 and evaluates it with the SAME verified Apex engine this
repo already uses (apex.ACCOUNTS / DPP / COMMISSION_SIDE): $50k target +$3,000, trailing DD $2,500 that
locks at +$100, max 10 contracts, $10/point, $1.50/side commission. OANDA M15 reaches back to 2019, so
this INCLUDES the COVID crash. Long AND short (a crash can pay the short side).

Sizing: contracts chosen to risk ~a target $ per trade (swept), capped at 10 - the Apex analog of the
stock risk_pct sweep. NOTE: like the repo's Apex sim, drawdown is checked on CLOSED-trade equity, so
bust% is optimistic vs real intraday trailing. RESEARCH ONLY - nothing here trades.
Run: python -m mgc_prop.orb_apex
"""

import os
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .apex import ACCOUNTS, DPP, COMMISSION_SIDE

INSTRUMENT = "XAU_USD"
HALF_SPREAD = 0.175          # ~0.35 gold spread / 2, in price
NY_OPEN_UTC = (13, 30)       # NY equity open
OR_BARS = 2                  # 2 x M15 = 30-min opening range
CUTOFF_UTC = (17, 30)        # no new entries after
FLAT_UTC = (20, 45)          # flat by
TARGET_R = 2.0               # big-target breakout (gold needs fewer, larger captures)
RISKS = [100.0, 150.0, 200.0, 250.0]   # target $ risk per trade
ACCOUNT = "50k"


def _fetch_m15():
    key = os.environ["OANDA_API_KEY"]
    env = os.environ.get("OANDA_ENV", "practice")
    base = "https://api-fxtrade.oanda.com" if env == "live" else "https://api-fxpractice.oanda.com"
    url = f"{base}/v3/instruments/{INSTRUMENT}/candles"
    headers = {"Authorization": f"Bearer {key}"}
    import requests
    frm = pd.Timestamp("2019-01-01", tz="UTC"); rows = []; sess = requests.Session()
    for _ in range(6000):
        params = {"granularity": "M15", "price": "M", "count": 5000,
                  "from": frm.strftime("%Y-%m-%dT%H:%M:%SZ")}
        r = sess.get(url, params=params, headers=headers, timeout=60)
        if r.status_code == 429:
            time.sleep(2); continue
        r.raise_for_status()
        cs = r.json().get("candles", [])
        if not cs:
            break
        for c in cs:
            if c.get("complete"):
                m = c["mid"]
                rows.append((pd.Timestamp(c["time"]), float(m["o"]), float(m["h"]),
                             float(m["l"]), float(m["c"])))
        last = pd.Timestamp(cs[-1]["time"])
        if last <= frm or len(cs) < 2:
            break
        frm = last + pd.Timedelta(seconds=1)
    df = pd.DataFrame(rows, columns=["ts", "o", "h", "l", "c"])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)


def _orb_trades(df):
    """NY opening-range breakout on M15, long+short, one/day. Returns list of (r_multiple, stop_pts)."""
    df = df.copy()
    df["date"] = df["ts"].dt.date
    df["min"] = df["ts"].dt.hour * 60 + df["ts"].dt.minute
    nyo = NY_OPEN_UTC[0] * 60 + NY_OPEN_UTC[1]
    cut = CUTOFF_UTC[0] * 60 + CUTOFF_UTC[1]
    flat = FLAT_UTC[0] * 60 + FLAT_UTC[1]
    trades = []
    for _, day in df.groupby("date"):
        day = day.reset_index(drop=True)
        orb = day[(day["min"] >= nyo)].reset_index(drop=True)
        if len(orb) < OR_BARS + 2:
            continue
        rng = orb.iloc[:OR_BARS]
        rh, rl = float(rng["h"].max()), float(rng["l"].min())
        if rh <= rl:
            continue
        pos = None
        for i in range(OR_BARS, len(orb) - 1):
            b = orb.iloc[i]; m = int(b["min"])
            if pos is None and m < cut:
                sidedir = 1 if float(b["c"]) > rh else (-1 if float(b["c"]) < rl else 0)
                if sidedir != 0:
                    nb = orb.iloc[i + 1]
                    entry = float(nb["o"]) + sidedir * HALF_SPREAD
                    stop = rl if sidedir == 1 else rh
                    risk = (entry - stop) * sidedir
                    if risk > 0:
                        pos = {"d": sidedir, "entry": entry, "stop": stop,
                               "target": entry + sidedir * TARGET_R * risk, "risk": risk, "j": i + 1}
                    continue
            if pos is not None:
                d = pos["d"]
                hi, lo = float(b["h"]), float(b["l"])
                if m >= flat:
                    px = float(b["o"]); trades.append(((px - pos["entry"]) * d / pos["risk"], pos["risk"])); pos = None; break
                if (d == 1 and lo <= pos["stop"]) or (d == -1 and hi >= pos["stop"]):
                    trades.append((-1.0, pos["risk"])); pos = None
                elif (d == 1 and hi >= pos["target"]) or (d == -1 and lo <= pos["target"]):
                    trades.append((TARGET_R, pos["risk"])); pos = None
        if pos is not None:
            last = orb.iloc[-1]
            trades.append(((float(last["c"]) - pos["entry"]) * pos["d"] / pos["risk"], pos["risk"]))
    return trades


def _contracts(stop_pts, tgt, cap):
    if stop_pts <= 0:
        return 0
    return max(1, min(cap, round(tgt / (stop_pts * DPP))))


def _pnls(trades, tgt, cap):
    out = []
    for r, stop_pts in trades:
        c = _contracts(stop_pts, tgt, cap)
        gross = r * c * stop_pts * DPP
        out.append(gross - 2 * COMMISSION_SIDE * c)     # entry+exit commission
    return out


def _apex(pnls, start, target, trail):
    bal = 0.0; peak = 0.0; floor = -trail; locked = False
    for k in range(start, len(pnls)):
        bal += pnls[k]
        if bal <= floor:
            return ("bust", None)
        if not locked:
            peak = max(peak, bal); floor = peak - trail
            if peak >= trail + 100:
                locked = True; floor = 100.0
        if bal >= target:
            return ("pass", k - start + 1)
    return ("none", None)


def _sweep(pnls, target, trail):
    outs = [_apex(pnls, s, target, trail) for s in range(0, max(1, len(pnls) - 3), 2)]
    passed = [d for t, d in outs if t == "pass"]; n = len(outs)
    med = int(np.median(passed)) if passed else None
    return (round(100 * len(passed) / n, 1) if n else 0.0,
            round(100 * sum(1 for t, _ in outs if t == "bust") / n, 1) if n else 0.0, med)


def run():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    a = ACCOUNTS[ACCOUNT]; target, trail, cap = a["target"], a["trail"], a["cap"]
    print(f"fetching {INSTRUMENT} M15 from 2019...", flush=True)
    df = _fetch_m15()
    if df.empty:
        print("no data"); return
    trades = _orb_trades(df)
    rs = [t[0] for t in trades]
    win = 100 * np.mean([1 for r in rs if r > 0]) / 1 if rs else 0
    win = 100 * (np.array(rs) > 0).mean() if rs else 0.0
    L = [f"[GOLD-ORB-APEX] {ts} - gold ORB (M15 NY breakout, long+short) under Apex ${ACCOUNT}",
         f"data {df['ts'].min().date()}..{df['ts'].max().date()} | {len(trades)} trades | "
         f"win {win:.1f}% | avgR {np.mean(rs):+.3f} | COVID INCLUDED",
         f"Apex {ACCOUNT}: target ${target}, trail ${trail}, cap {cap} MGC, $10/pt, ${COMMISSION_SIDE}/side", "",
         f"{'RISK/trade':<11} {'~MGC':<6} passRate   median(trades~=days)  bust%"]
    for tgt in RISKS:
        pnls = _pnls(trades, tgt, cap)
        pp, bp, med = _sweep(pnls, target, trail)
        typ = int(np.median([_contracts(s, tgt, cap) for _, s in trades])) if trades else 0
        md = f"{med} (~{med/21:.1f}mo)" if med else "never"
        L.append(f"${tgt:>7.0f}   {typ:>3}    {pp:>5}%     {md:<20} {bp}%")
    L += ["", "Apex trails your PEAK and locks +$100 after +$2,600 - giving back profit can bust you. "
          "Long+short so a crash can pay. bust% optimistic (closed-equity trailing). RESEARCH ONLY - not deployed."]
    out = "\n".join(L); print(out)
    try:
        import sys, pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
        from execution import notifier
        notifier.post(out)
    except Exception as e:
        print(f"(slack skipped: {e})")


if __name__ == "__main__":
    run()
