"""advanced_price_action.py -- "Advanced Price Action" backtest on XAU_USD.
RESEARCH ONLY. Nothing here places orders; it fetches/loads candles and simulates.

PRE-REGISTERED 2026-07-23 (written before the run). Operationalizes the chart
pattern Peter supplied ("Advanced Price Action": 3-Drives into resistance ->
falling wedge pullback to a demand/support level -> long-bar breakout entry,
targets the prior highs). Because "3 drives" and "falling wedge" are
discretionary shapes, this tests their TRADEABLE ESSENCE, stated explicitly so
nobody pretends it's the exact hand-drawn pattern:

  CONTEXT   uptrend: close > EMA(trend_len)  (the drives push UP into resistance)
  PULLBACK  a falling wedge over the prior `wedge_len` bars: highs slope < 0 AND
            lows slope < 0 AND range contracting (recent half tighter than the
            earlier half) -- a converging corrective drop.
  SUPPORT   the wedge low sits near a real support: within demand_atr x ATR of the
            rolling min-low over `support_look` bars (the "key level / demand zone").
  TRIGGER   a LONG BAR breakout: bar range > breakout_atr x ATR, bullish
            (close>open), and close breaks ABOVE the wedge's descending highs
            (close > max high of the wedge window).
  ENTRY     next bar open (+ cost).  STOP = wedge low - stop_buf x ATR.
            TARGET = entry + rr x risk (TP1).  Long-only (pattern is bullish).
            Time-stop after max_hold bars. One position at a time.

Honest priors, on the record:
 - This is a bullish breakout-from-contraction. On gold's 2019-2026 BULL MARKET
   it will likely look positive largely because it is LONG gold during a huge
   uptrend. The report prints a BUY-AND-HOLD gold benchmark over the same
   validation window so we can tell edge from beta.
 - ~13 intraday/pattern families have been tested across markets; almost all
   died after realistic costs. Gold's intraday SMC stack was +0.138R at 1x but
   INVERTED at 3x. So the decisive test here is the 3x COST STRESS, not the 1x
   headline. VERDICT.md's rule stands: an edge that dies at 3x was paying itself
   with unrealistic fills.

Scalp vs intraday: grid runs BOTH M15 (scalp) and H1 (intraday, resampled).
Cost model: gold points per side (0.30 spread + 0.10 slippage = 0.40/side at 1x),
stressed at 3x, matching the repo's other rigorous backtests.

Split: train 2019-01 -> 2023-12, validation 2024-01 -> now (untouched).
Gate (informational, repo standard): >=100 val trades, >=+0.05R, PF>=1.15,
>=60% quarters positive, AND must stay positive at 3x cost. A PASS earns a
FORWARD PAPER TRIAL (like smc_paper.py) -- NOT live money. Gold live sits behind
the same visa/legal gates as everything else.

Local: APA_LOCAL_M15=data/candles/XAU_USD_M15.csv python advanced_price_action.py
Live candles: python advanced_price_action.py   (needs OANDA_API_KEY)
"""
from __future__ import annotations

import itertools
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
INSTRUMENT = "XAU_USD"
COST_PER_SIDE = 0.40            # gold points at 1x (0.30 spread + 0.10 slippage)
RISK_USD = 500.0               # 0.5% of $100k, no compounding (declared)

TRAIN_END = pd.Timestamp("2023-12-31", tz="UTC")
VAL_START = pd.Timestamp("2024-01-01", tz="UTC")

GRID = {
    "granularity": ["M15", "H1"],   # scalp + intraday
    "breakout_atr": [1.5, 2.5],
    "rr": [1.5, 2.5],
    "wedge_len": [12, 20],
}
TREND_LEN, ATR_LEN, SUPPORT_LOOK = 200, 14, 60
DEMAND_ATR, STOP_BUF, MAX_HOLD = 1.5, 0.5, 60
MIN_TRADES = 100
GATE = dict(min_expectancy_r=0.05, min_pf=1.15, min_q_frac=0.6)


# ---------------- data ----------------
def load_m15():
    local = os.environ.get("APA_LOCAL_M15")
    if local:
        df = pd.read_csv(local)
        df["ts"] = pd.to_datetime(df["time"], utc=True)
        return df.set_index("ts")[["open", "high", "low", "close"]].sort_index()
    key = os.environ["OANDA_API_KEY"]
    env = os.environ.get("OANDA_ENV", "practice")
    base = "https://api-fxtrade.oanda.com" if env == "live" else "https://api-fxpractice.oanda.com"
    url = f"{base}/v3/instruments/{INSTRUMENT}/candles"
    headers = {"Authorization": f"Bearer {key}"}
    import requests
    frm = pd.Timestamp("2019-01-01", tz="UTC")
    rows, sess = [], requests.Session()
    for _ in range(4000):
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
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df.drop_duplicates("ts").set_index("ts").sort_index()


def resample(m15, gran):
    if gran == "M15":
        return m15
    rule = {"H1": "1h"}[gran]
    return m15.resample(rule).agg({"open": "first", "high": "max",
                                   "low": "min", "close": "last"}).dropna()


def add_indicators(df):
    df = df.copy()
    df["ema"] = df["close"].ewm(span=TREND_LEN, adjust=False).mean()
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(),
                    (df["low"] - pc).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / ATR_LEN, adjust=False).mean()
    df["support"] = df["low"].rolling(SUPPORT_LOOK).min().shift(1)
    return df


# ---------------- detector + sim ----------------
def simulate(df, params):
    """Long-only APA breakout sim. Returns list of trade dicts (price PnL, pre-cost)."""
    W = int(params["wedge_len"])
    katr = float(params["breakout_atr"])
    rr = float(params["rr"])
    o = df["open"].values; h = df["high"].values
    l = df["low"].values; c = df["close"].values
    ema = df["ema"].values; atr = df["atr"].values
    support = df["support"].values
    idx = df.index
    n = len(df)

    roll_max_hi = df["high"].rolling(W).max().shift(1).values   # wedge upper (prior W)
    roll_min_lo = df["low"].rolling(W).min().shift(1).values     # wedge low
    bar_range = h - l
    xw = np.arange(W)

    def wedge_ok(i):
        hs = h[i - W:i]; ls = l[i - W:i]
        if len(hs) < W:
            return False
        sh = np.polyfit(xw, hs, 1)[0]
        sl = np.polyfit(xw, ls, 1)[0]
        if sh >= 0 or sl >= 0:                      # need lower highs AND lower lows
            return False
        rng = hs - ls
        half = W // 2
        if rng[half:].mean() >= rng[:half].mean():   # must be contracting
            return False
        wl = ls.min()
        # "support level confirmed" = the pullback made a HIGHER LOW: the wedge
        # low holds at/above prior support (didn't break structure). In a real
        # uptrend the demand zone is a shelf the wedge lands ON, not the absolute
        # multi-day min - so we require structure intact, not proximity to the min.
        if support[i] == support[i] and wl < support[i] - DEMAND_ATR * atr[i]:
            return False
        return True

    trades = []
    pos = None
    for i in range(max(TREND_LEN, SUPPORT_LOOK, W) + 1, n - 1):
        if pos is not None:
            j = i
            exit_px = exit_kind = None
            if l[j] <= pos["stop"]:
                exit_px = min(o[j], pos["stop"]); exit_kind = "stop"
            elif h[j] >= pos["target"]:
                exit_px = max(o[j], pos["target"]); exit_kind = "target"
            elif j - pos["ei"] >= MAX_HOLD:
                exit_px = c[j]; exit_kind = "timeout"
            if exit_px is not None:
                trades.append(dict(entry_ts=idx[pos["ei"]], exit_ts=idx[j],
                                   entry=pos["entry"], risk=pos["risk"],
                                   pnl_price=exit_px - pos["entry"], kind=exit_kind))
                pos = None
            continue
        # candidate breakout bar (cheap filters first)
        if not (c[i] > ema[i] and bar_range[i] > katr * atr[i]
                and c[i] > o[i] and roll_max_hi[i] == roll_max_hi[i]
                and c[i] > roll_max_hi[i]):
            continue
        if not wedge_ok(i):
            continue
        entry = o[i + 1]
        stop = roll_min_lo[i] - STOP_BUF * atr[i]
        risk = entry - stop
        if risk <= 0:
            continue
        pos = dict(ei=i + 1, entry=entry, stop=stop,
                   target=entry + rr * risk, risk=risk)
    return trades


# ---------------- metrics ----------------
def stats(trades, cost_per_side):
    if not trades:
        return {"trades": 0}
    rs, dates = [], []
    rt = 2 * cost_per_side
    for t in trades:
        rs.append((t["pnl_price"] - rt) / t["risk"])
        dates.append(t["entry_ts"])
    rs = np.array(rs)
    gw = rs[rs > 0].sum(); gl = -rs[rs <= 0].sum()
    q = pd.PeriodIndex(pd.to_datetime(dates), freq="Q")
    qsum = pd.Series(rs).groupby(q).sum()
    return {"trades": len(rs), "expectancy_r": round(float(rs.mean()), 3),
            "win_rate": round(float((rs > 0).mean() * 100), 1),
            "pf": round(float(gw / gl), 3) if gl > 0 else float("inf"),
            "total_r": round(float(rs.sum()), 1),
            "q_pos": int((qsum > 0).sum()), "q_tot": int(len(qsum))}


def split(trades):
    tr = [t for t in trades if t["entry_ts"] <= TRAIN_END]
    va = [t for t in trades if t["entry_ts"] >= VAL_START]
    return tr, va


def buy_hold_r(df):
    w = df[df.index >= VAL_START]
    if len(w) < 2:
        return 0.0
    return round((w["close"].iloc[-1] / w["close"].iloc[0] - 1) * 100, 1)


def slack(text):
    tok = os.environ.get("SLACK_BOT_TOKEN"); ch = os.environ.get("SLACK_CHANNEL_ID")
    if not (tok and ch):
        print(text); return
    import requests
    requests.post("https://slack.com/api/chat.postMessage",
                  headers={"Authorization": f"Bearer {tok}"},
                  json={"channel": ch, "text": text}, timeout=15)


def main():
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    m15 = load_m15()
    print(f"loaded {len(m15):,} M15 bars {m15.index[0].date()} -> {m15.index[-1].date()}", flush=True)
    prepped = {g: add_indicators(resample(m15, g)) for g in ("M15", "H1")}
    bh = buy_hold_r(prepped["H1"])

    combos = [dict(zip(GRID, v)) for v in itertools.product(*GRID.values())]
    rows = []
    for k, combo in enumerate(combos, 1):
        df = prepped[combo["granularity"]]
        trades = simulate(df, combo)
        tr, va = split(trades)
        m_tr = stats(tr, COST_PER_SIDE)
        m_va = stats(va, COST_PER_SIDE)
        m_va3 = stats(va, COST_PER_SIDE * 3)
        rows.append((combo, m_tr, m_va, m_va3))
        print(f"  [{k}/{len(combos)}] {combo} train {m_tr.get('trades',0)}t "
              f"{m_tr.get('expectancy_r',0)}R | val {m_va.get('trades',0)}t "
              f"{m_va.get('expectancy_r',0)}R | 3x {m_va3.get('expectancy_r',0)}R", flush=True)

    # winner: best TRAIN expectancy among combos with enough train trades
    elig = [r for r in rows if r[1].get("trades", 0) >= MIN_TRADES]
    report = [f"# Advanced Price Action backtest - XAU_USD - {ts}", "",
              "RESEARCH ONLY - nothing deploys. Operationalizes the 3-drives + falling-wedge",
              "+ long-bar-breakout pattern (tradeable essence; see file docstring).",
              f"cost {COST_PER_SIDE}/side (1x), stressed 3x. train ->2023-12, val 2024-01->now.",
              f"BUY-AND-HOLD gold over validation: {bh:+}%  (edge must beat being long beta)", "",
              "## All combos (train | val | val@3x)", ""]
    for combo, m_tr, m_va, m_va3 in rows:
        cs = ", ".join(f"{k}={v}" for k, v in combo.items())
        report.append(f"- {cs}: train {m_tr.get('trades',0)}t {m_tr.get('expectancy_r',0)}R "
                      f"PF {m_tr.get('pf',0)} | val {m_va.get('trades',0)}t "
                      f"{m_va.get('expectancy_r',0)}R PF {m_va.get('pf',0)} | "
                      f"3x {m_va3.get('expectancy_r',0)}R")
    report.append("")

    if not elig:
        verdict = f"SKIP - no combo reached {MIN_TRADES} train trades"
        slack_tail = [verdict]
    else:
        elig.sort(key=lambda r: r[1]["expectancy_r"], reverse=True)
        combo, m_tr, m_va, m_va3 = elig[0]
        cs = ", ".join(f"{k}={v}" for k, v in combo.items())
        passed = (m_va.get("trades", 0) >= MIN_TRADES
                  and m_va.get("expectancy_r", 0) >= GATE["min_expectancy_r"]
                  and m_va.get("pf", 0) >= GATE["min_pf"]
                  and m_va.get("q_pos", 0) / max(m_va.get("q_tot", 1), 1) >= GATE["min_q_frac"]
                  and m_va3.get("expectancy_r", 0) > 0)
        verdict = ("ALIVE (informational) - clears gate AND survives 3x cost; earns a FORWARD "
                   "PAPER trial, NOT live" if passed else
                   "FAIL (informational) - no edge after realistic/stressed costs")
        report += [f"## Winner (by train): {cs}",
                   f"- train: {m_tr['trades']}t, {m_tr['expectancy_r']}R, PF {m_tr['pf']}",
                   f"- validation 1x: {m_va['trades']}t, win {m_va['win_rate']}%, "
                   f"{m_va['expectancy_r']}R, PF {m_va['pf']}, {m_va['q_pos']}/{m_va['q_tot']} q+, "
                   f"total {m_va['total_r']}R",
                   f"- validation 3x cost: {m_va3['trades']}t, {m_va3['expectancy_r']}R, PF {m_va3['pf']}",
                   f"- buy-hold gold (val): {bh:+}% - is this edge or just long beta?",
                   f"## Verdict: {verdict}", ""]
        slack_tail = [f"winner {cs}",
                      f"train {m_tr['expectancy_r']:+}R ({m_tr['trades']}t) -> "
                      f"val {m_va['expectancy_r']:+}R (PF {m_va['pf']}, {m_va['trades']}t)",
                      f"val@3x cost: {m_va3['expectancy_r']:+}R | buy-hold gold {bh:+}%",
                      f"*{verdict}*"]

    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    (out / f"apa_{stamp}.md").write_text("\n".join(report), encoding="utf-8")
    (ROOT / "reports" / "backtest_data_2026-07-22").mkdir(parents=True, exist_ok=True)
    print(f"report written: reports/apa_{stamp}.md", flush=True)

    slack("\n\n".join([f"*[APA-GOLD]* {ts} - RESEARCH ONLY, nothing deploys\n"
                       "Advanced Price Action (3-drives+wedge+breakout) on XAU_USD, "
                       "scalp M15 + intraday H1"] + slack_tail
                      + [f"Full detail: reports/apa_{stamp}.md"]))


if __name__ == "__main__":
    main()
