"""smc_paper.py -- SMC swing strategy FORWARD PAPER TRIAL. Simulation only.

PRE-REGISTERED 2026-07-21. This file exists to settle, with forward data, whether
the SMC multi-TF swing strategy (Daily HH/HL bias -> H4 sweep + MSS + 50% discount
-> H1 grab + stop-entry, stop at sweep extreme, TP 1:2) has a real edge on XAU_USD.

Honest context, on the record: the gold backtest showed net +0.37R train / +0.24R
validation -- but on only 32 validation trades, as the 13th hypothesis on the same
window, and the identical engine FAILED (-0.067R, 150 trades) when scaled to a
9-instrument basket. The weight of evidence says this trial will fail. It runs
because forward data is the only court that can overrule that -- and because paper
costs nothing.

Judgment gates (pre-registered, no moving): trial needs >= 30 closed trades
(~2 years at ~15/yr) before any verdict. Checkpoint review at 6 months. "Alive"
requires positive net expectancy AND both directions not catastrophically split.
Any promotion beyond paper requires months more, plus Prem's explicit approval,
plus the legal/visa clearance gates. This bot NEVER places orders anywhere --
it fetches candles and simulates. There is no broker order code in this file.

Mechanics: engine parameters FROZEN from the prototype (k=2 fractals, 60-H4-bar
setup expiry, 120-H1-bar trigger window, 720-H1-bar max hold, RR 1:2). Fills at
the H1 stop-trigger level; cost = 0.35 round trip charged at close. $500 risk per
trade (0.5% of $100k, no compounding). Runs every 4h via GitHub Actions; each run
re-simulates a trailing 180-day window deterministically, ignores the 90-day
warmup, and reports only NEW events since the last run (state in memory/).

Test mode (no network): SMC_PAPER_LOCAL_CSV=<m15 csv> SMC_PAPER_ASOF=YYYY-MM-DD
Optional state/log path overrides: SMC_PAPER_STATE, SMC_PAPER_TRADELOG.
Run: python smc_paper.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
STATE_PATH = Path(os.environ.get("SMC_PAPER_STATE", ROOT / "memory" / "smc_paper_state.json"))
LOG_PATH = Path(os.environ.get("SMC_PAPER_TRADELOG", ROOT / "reports" / "smc_paper_trades.csv"))

INSTRUMENT = "XAU_USD"
SPREAD = 0.35            # round trip, gold points
RISK_USD = 500.0         # 0.5% of $100k, no compounding (declared)
WINDOW_DAYS, WARMUP_DAYS = 180, 90
K, EXP_H4, WIN_H1, HOLD_H1, RR = 2, 60, 120, 720, 2.0   # FROZEN


# ---------- data ----------
def fetch_m15():
    local = os.environ.get("SMC_PAPER_LOCAL_CSV")
    if local:
        df = pd.read_csv(local, parse_dates=["time"]).set_index("time").sort_index()
        df = df[~df.index.duplicated(keep="last")]
        asof = os.environ.get("SMC_PAPER_ASOF")
        if asof:
            df = df[df.index <= pd.Timestamp(asof, tz="UTC")]
        return df[df.index >= df.index[-1] - pd.Timedelta(days=WINDOW_DAYS)]
    key = os.environ["OANDA_API_KEY"]
    env = os.environ.get("OANDA_ENV", "practice")
    base = "https://api-fxtrade.oanda.com" if env == "live" else "https://api-fxpractice.oanda.com"
    url = f"{base}/v3/instruments/{INSTRUMENT}/candles"
    headers = {"Authorization": f"Bearer {key}"}
    frm = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    rows = []
    sess = requests.Session()
    for _ in range(60):
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
        if last <= pd.Timestamp(frm):
            break
        frm = last.to_pydatetime() + timedelta(seconds=1)
        if len(cs) < 2:
            break
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close"])
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df.drop_duplicates("time").set_index("time").sort_index()


# ---------- frozen engine (validated against the gold prototype) ----------
def resample(m15, rule):
    return m15.resample(rule).agg({"open": "first", "high": "max",
                                   "low": "min", "close": "last"}).dropna()


def fractals(h, l, k=K):
    hs, ls = [], []
    for i in range(k, len(h) - k):
        wh, wl = h[i-k:i+k+1], l[i-k:i+k+1]
        if h[i] == wh.max() and (wh == h[i]).sum() == 1: hs.append((i + k, h[i]))
        if l[i] == wl.min() and (wl == l[i]).sum() == 1: ls.append((i + k, l[i]))
    return hs, ls


def simulate(m15):
    """Returns (closed_trades, open_pos). closed: (entry_ts, exit_ts, entry, exit_kind,
    pnl_price, risk, dir). open_pos: dict or None."""
    H1, H4, D1 = resample(m15, "1h"), resample(m15, "4h"), resample(m15, "1D")
    dh, dl = D1["high"].values, D1["low"].values
    dhs, dls = fractals(dh, dl)
    bias_vals = np.zeros(len(D1), int)
    hi_h, lo_h = [], []; ei = ej = 0; bias = 0
    for di in range(len(D1)):
        while ei < len(dhs) and dhs[ei][0] <= di: hi_h.append(dhs[ei][1]); ei += 1
        while ej < len(dls) and dls[ej][0] <= di: lo_h.append(dls[ej][1]); ej += 1
        if len(hi_h) >= 2 and len(lo_h) >= 2:
            if hi_h[-1] > hi_h[-2] and lo_h[-1] > lo_h[-2]: bias = 1
            elif hi_h[-1] < hi_h[-2] and lo_h[-1] < lo_h[-2]: bias = -1
        bias_vals[di] = bias
    bias_known = (D1.index + pd.Timedelta(days=1)).asi8
    idx4 = np.searchsorted(bias_known, H4.index.asi8, side="right") - 1
    h4_bias = np.where(idx4 >= 0, bias_vals[np.clip(idx4, 0, None)], 0)
    h4h, h4l, h4c = H4["high"].values, H4["low"].values, H4["close"].values
    h4hs, h4ls = fractals(h4h, h4l)
    h1o, h1h, h1l, h1c = (H1[x].values for x in ["open", "high", "low", "close"])
    h1hs, h1ls = fractals(h1h, h1l)
    t_times = H1.index
    n1 = len(h1c)

    def h1_pos(ts):
        return int(np.searchsorted(t_times, ts, side="right"))

    closed = []; open_pos = None
    state = None; ei = ej = 0; lastH4hi = lastH4lo = None
    for t in range(len(H4)):
        while ei < len(h4hs) and h4hs[ei][0] <= t: lastH4hi = h4hs[ei][1]; ei += 1
        while ej < len(h4ls) and h4ls[ej][0] <= t: lastH4lo = h4ls[ej][1]; ej += 1
        ts = H4.index[t]; b = int(h4_bias[t])
        if state is None:
            if b == 1 and lastH4lo is not None and h4l[t] < lastH4lo:
                state = dict(d=1, sweep=h4l[t], phase="swept", t0=t, leghi=h4h[t])
            elif b == -1 and lastH4hi is not None and h4h[t] > lastH4hi:
                state = dict(d=-1, sweep=h4h[t], phase="swept", t0=t, leglo=h4l[t])
            continue
        if t - state["t0"] > EXP_H4: state = None; continue
        d = state["d"]
        if d == 1:
            state["sweep"] = min(state["sweep"], h4l[t]); state["leghi"] = max(state["leghi"], h4h[t])
            if state["phase"] == "swept" and lastH4hi is not None and h4c[t] > lastH4hi:
                state["phase"] = "mss"; state["mid"] = (state["sweep"] + state["leghi"]) / 2
            elif state["phase"] == "mss" and h4l[t] <= state["mid"]:
                state["phase"] = "h1"; state["h1start"] = h1_pos(ts)
        else:
            state["sweep"] = max(state["sweep"], h4h[t]); state["leglo"] = min(state["leglo"], h4l[t])
            if state["phase"] == "swept" and lastH4lo is not None and h4c[t] < lastH4lo:
                state["phase"] = "mss"; state["mid"] = (state["sweep"] + state["leglo"]) / 2
            elif state["phase"] == "mss" and h4h[t] >= state["mid"]:
                state["phase"] = "h1"; state["h1start"] = h1_pos(ts)
        if state.get("phase") != "h1": continue
        s0 = state["h1start"]; d = state["d"]; sweep = state["sweep"]
        hi_i = [x for x in h1hs if x[0] <= s0]; lo_i = [x for x in h1ls if x[0] <= s0]
        ph = [x for x in h1hs if x[0] > s0]; pl = [x for x in h1ls if x[0] > s0]
        lastHi = hi_i[-1][1] if hi_i else None; lastLo = lo_i[-1][1] if lo_i else None
        grab = False; trigger = None; entry_i = None
        j = s0; pi = qi = 0
        while j < min(s0 + WIN_H1, n1):
            while pi < len(ph) and ph[pi][0] <= j: lastHi = ph[pi][1]; pi += 1
            while qi < len(pl) and pl[qi][0] <= j: lastLo = pl[qi][1]; qi += 1
            if d == 1:
                if h1l[j] < sweep: break
                if not grab and lastLo is not None and h1l[j] < lastLo: grab = True
                elif grab and trigger is None and lastHi is not None: trigger = lastHi
                elif trigger is not None and h1h[j] >= trigger: entry_i = j; break
            else:
                if h1h[j] > sweep: break
                if not grab and lastHi is not None and h1h[j] > lastHi: grab = True
                elif grab and trigger is None and lastLo is not None: trigger = lastLo
                elif trigger is not None and h1l[j] <= trigger: entry_i = j; break
            j += 1
        state = None
        if entry_i is None: continue
        entry = trigger; risk = (entry - sweep) if d == 1 else (sweep - entry)
        if risk <= 0: continue
        stop = sweep; tgt = entry + RR * risk * d if d == 1 else entry - RR * risk
        end_i = min(entry_i + HOLD_H1, n1)
        pnl = None; kind = None; k2 = entry_i
        for k2 in range(entry_i, end_i):
            if d == 1:
                if h1l[k2] <= stop:
                    pnl = (min(h1o[k2], stop) if k2 > entry_i else stop) - entry; kind = "stop"; break
                if h1h[k2] >= entry + RR * risk:
                    pnl = RR * risk; kind = "target"; break
            else:
                if h1h[k2] >= stop:
                    pnl = entry - (max(h1o[k2], stop) if k2 > entry_i else stop); kind = "stop"; break
                if h1l[k2] <= entry - RR * risk:
                    pnl = RR * risk; kind = "target"; break
        if pnl is None:
            if end_i < n1:   # timeout hit inside data -> closed
                k2 = end_i - 1
                pnl = (h1c[k2] - entry) * d; kind = "timeout"
            else:            # data ended -> STILL OPEN (live position)
                open_pos = dict(entry_ts=str(t_times[entry_i]), dir=int(d),
                                entry=round(float(entry), 3), stop=round(float(stop), 3),
                                target=round(float(tgt), 3), risk=round(float(risk), 3))
                break
        closed.append((t_times[entry_i], t_times[k2], float(entry), kind, float(pnl), float(risk), int(d)))
    return closed, open_pos


# ---------- slack ----------
def slack(text):
    tok = os.environ.get("SLACK_BOT_TOKEN"); ch = os.environ.get("SLACK_CHANNEL_ID")
    if not (tok and ch):
        print(text); return
    r = requests.post("https://slack.com/api/chat.postMessage",
                      headers={"Authorization": f"Bearer {tok}"},
                      json={"channel": ch, "text": text}, timeout=15)
    r.raise_for_status()


# ---------- state ----------
def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return None


def save_state(st):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(st, indent=2))


def log_trade(row):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG_PATH.exists()
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        if new:
            fh.write("entry_ts,exit_ts,dir,entry,exit_kind,net_R,nav\n")
        fh.write(",".join(str(x) for x in row) + "\n")


def main():
    m15 = fetch_m15()
    if len(m15) < 96 * (WARMUP_DAYS + 10):
        print(f"insufficient data ({len(m15)} bars); no-op"); return
    closed, open_pos = simulate(m15)
    data_end = str(m15.index[-1])
    warm_edge = m15.index[-1] - pd.Timedelta(days=WINDOW_DAYS - WARMUP_DAYS)

    st = load_state()
    first_run = st is None
    if first_run:
        st = dict(initialized_at=data_end, last_event_ts=data_end, nav=100000.0,
                  n_trades=0, sum_R=0.0, open=open_pos)
        save_state(st)
        slack(f"*[SMC-PAPER]* trial initialized {data_end} UTC -- {INSTRUMENT} swing "
              f"strategy, paper only, $500 risk/trade.\nPre-registered gates: >=30 closed "
              f"trades before any verdict; 6-month checkpoint. Expected ~15 trades/yr. "
              f"No real capital, ever, from this trial alone.")
        print("initialized"); return

    last = pd.Timestamp(st["last_event_ts"])
    init = pd.Timestamp(st["initialized_at"])
    msgs = []
    for ets, xts, entry, kind, pnl, risk, d in closed:
        if xts <= last or ets <= init or ets < warm_edge:
            continue
        net_r = (pnl - SPREAD) / risk
        st["n_trades"] += 1; st["sum_R"] += net_r; st["nav"] += net_r * RISK_USD
        log_trade([ets, xts, d, round(entry, 3), kind, round(net_r, 3), round(st["nav"], 2)])
        side = "LONG" if d == 1 else "SHORT"
        exp = st["sum_R"] / st["n_trades"]
        msgs.append(
            f"*[SMC-PAPER]* CLOSED {side} {INSTRUMENT} -- {kind.upper()} -> {net_r:+.2f}R "
            f"(${net_r*RISK_USD:+,.0f})\nEntered {ets} @ {entry:.2f}, exited {xts}.\n"
            f"Trial so far: {st['n_trades']} trades, avg {exp:+.3f}R, NAV ${st['nav']:,.0f}.\n"
            f"Verdict needs >=30 trades -- {max(0, 30-st['n_trades'])} to go. Paper only.")
    prev_open = st.get("open")
    if open_pos and (not prev_open or open_pos["entry_ts"] != prev_open.get("entry_ts")):
        if pd.Timestamp(open_pos["entry_ts"]) > init:
            side = "LONG" if open_pos["dir"] == 1 else "SHORT"
            msgs.append(
                f"*[SMC-PAPER]* OPENED {side} {INSTRUMENT} @ {open_pos['entry']:.2f}\n"
                f"Stop {open_pos['stop']:.2f} | Target {open_pos['target']:.2f} "
                f"(1:2) | risking $500 (0.5%). Simulated fill at real OANDA prices -- "
                f"no real money.")
    st["open"] = open_pos
    st["last_event_ts"] = data_end
    save_state(st)
    for m in msgs:
        slack(m)
    now = datetime.now(timezone.utc)
    if not msgs and now.weekday() == 4 and 17 <= now.hour <= 21:
        exp = (st["sum_R"] / st["n_trades"]) if st["n_trades"] else 0.0
        pos = "holding " + ("LONG" if (open_pos or {}).get("dir") == 1 else "SHORT") if open_pos else "flat"
        slack(f"*[SMC-PAPER]* weekly heartbeat -- {pos} | {st['n_trades']} trades, "
              f"avg {exp:+.3f}R, NAV ${st['nav']:,.0f} | {max(0,30-st['n_trades'])} trades "
              f"until verdict. Paper only.")
    print(f"run ok: {len(msgs)} events; nav {st['nav']:.0f}")


if __name__ == "__main__":
    main()
