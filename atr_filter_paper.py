"""atr_filter_paper.py -- Track 3 FORWARD PAPER TRIAL. Simulation only.

PRE-REGISTERED 2026-07-26 (see reports/PRE_REGISTRATION_ATR_2026-07-26.md).
Settles, with forward data, whether adding a VOLATILITY GATE to the intraday stack
  FVG + NY-Opening entries (Displacement dropped), confidence gate ON,
  filtered to the daily 20/100-EMA + 12-month-momentum trend (fast_trend),
  AND taken ONLY when M15 ATR-at-entry >= its rolling median
improves the honest edge and its cost-robustness on XAU_USD.

Why this variant earned a trial (see reports/robustness_study_2026-07-25.md):
  It was the ONLY modification in the robustness study that improved BOTH the honest
  selection period AND the holdout AND survived 5x cost (selection Sharpe 0.55->0.64;
  holdout 5x expectancy +0.122R vs the baseline's fragile +0.015R). The ATR-bucket
  relationship is monotonic (edge concentrates in volatile sessions), so it is
  theory-backed, not curve-fit. HONEST CAVEATS on the record: it halves the trade
  count, sits just past a soft parameter edge (below-median thresholds degrade below
  baseline), and it STILL does not beat buy-and-hold gold on return in the 2023-26 bull.
  It is on PAPER to see if the improvement survives forward, out-of-sample fills.

Judgment gates (pre-registered, no moving): >= 30 closed trades before any verdict.
6-month checkpoint. "Alive" = positive net expectancy after costs AND not profitable
only while gold rises (direction is logged). Any step beyond paper needs months more
data + Prem's explicit approval. NEVER places orders -- fetches candles and simulates
via the validated backtest.engine_final. Fully isolated from baseline / Track 2.

Test mode (no network):
  ATRF_LOCAL_M15=data/candles/XAU_USD_M15.csv ATRF_LOCAL_H4=data/candles/XAU_USD_H4.csv \
  ATRF_LOCAL_D=data/daily/XAU_USD_D.csv ATRF_ASOF=2026-06-05 python atr_filter_paper.py
Run (live practice candles): python atr_filter_paper.py
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
sys.path.insert(0, str(ROOT))

from strategy.macro_trend import MacroConfig, compute_weights          # noqa: E402
from strategy.strategy import StrategyConfig                           # noqa: E402
from strategy.risk import RiskConfig                                   # noqa: E402
from backtest.core import BacktestConfig, CostModel                    # noqa: E402
from backtest.engine_final import run_backtest_fast                    # noqa: E402
from execution import notifier                                         # noqa: E402

INSTRUMENT = "XAU_USD"
STATE_PATH = Path(os.environ.get("ATRF_STATE", ROOT / "memory" / "atr_filter_state.json"))
LOG_PATH = Path(os.environ.get("ATRF_TRADELOG", ROOT / "reports" / "atr_filter_trades.csv"))

RISK_USD = 1000.0            # 1% of $100k, no compounding
M15_DAYS = 150
D_DAYS = 420
WARMUP_DAYS = 30
VERDICT_TRADES = 30

# FROZEN definition (pre-registered)
STRAT = StrategyConfig(use_displacement=False, use_fvg=True, enable_ny_opening=True)
COST = CostModel()                     # 0.30 spread + 0.10 slippage
BT = BacktestConfig(use_confidence_gate=True)
TREND = MacroConfig(ema_fast=20, ema_slow=100, mom_lookback=252, use_macro=True)  # fast_trend
ATR_LEN = 56                           # ~14h ATR on M15 (session volatility proxy)
ATR_MED_WIN = 2000                     # rolling-median window (bars); >= this used
ATR_MED_MINP = 200                     # min periods for the median


def _fetch(gran, days, price="M"):
    key = os.environ["OANDA_API_KEY"]
    env = os.environ.get("OANDA_ENV", "practice")
    base = "https://api-fxtrade.oanda.com" if env == "live" else "https://api-fxpractice.oanda.com"
    url = f"{base}/v3/instruments/{INSTRUMENT}/candles"
    headers = {"Authorization": f"Bearer {key}"}
    frm = datetime.now(timezone.utc) - timedelta(days=days)
    rows, sess = [], requests.Session()
    for _ in range(80):
        params = {"granularity": gran, "price": price, "count": 5000,
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
                             float(m["l"]), float(m["c"]), float(c.get("volume", 0))))
        last = pd.Timestamp(cs[-1]["time"])
        if last <= pd.Timestamp(frm) or len(cs) < 2:
            break
        frm = last.to_pydatetime() + timedelta(seconds=1)
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df.drop_duplicates("time").set_index("time").sort_index()


def _local(path, asof):
    df = pd.read_csv(path, parse_dates=["time"]).set_index("time").sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    if "volume" not in df.columns:
        df["volume"] = 1000.0
    if asof:
        df = df[df.index <= pd.Timestamp(asof, tz="UTC")]
    return df


def load_data():
    lm = os.environ.get("ATRF_LOCAL_M15")
    asof = os.environ.get("ATRF_ASOF")
    if lm:
        m15 = _local(lm, asof)
        m15 = m15[m15.index >= m15.index[-1] - pd.Timedelta(days=M15_DAYS)]
        return m15, _local(os.environ["ATRF_LOCAL_H4"], asof), _local(os.environ["ATRF_LOCAL_D"], asof)
    return _fetch("M15", M15_DAYS), _fetch("H4", M15_DAYS + 30), _fetch("D", D_DAYS)


def daily_dir(d1):
    px = d1.copy()
    px.index = pd.DatetimeIndex(px.index).tz_localize(None) if px.index.tz else pd.DatetimeIndex(px.index)
    md = np.sign(compute_weights(px, None, TREND)["pos_dir"]).astype(float)
    md.index = pd.DatetimeIndex(md.index)
    return md


def atr_gate(m15):
    """Returns (atr, atr_median) series on the M15 index. Both causal (past-only)."""
    h, l, c = m15["high"], m15["low"], m15["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(ATR_LEN).mean()
    med = atr.rolling(ATR_MED_WIN, min_periods=ATR_MED_MINP).median()
    return atr, med


def simulate():
    m15, h4, d1 = load_data()
    res = run_backtest_fast(m15, h4, STRAT, RiskConfig(), BT, COST)
    md = daily_dir(d1)
    atr, med = atr_gate(m15)
    mi = m15.index.values
    out = []
    for t in res.trades:
        if t.exit_time is None:
            continue
        # daily-trend filter
        ent = pd.Timestamp(t.entry_time).tz_localize(None)
        d = md.reindex(md.index.union([ent])).ffill().reindex([ent]).values[0]
        if np.isnan(d) or d != (1 if t.side == "buy" else -1):
            continue
        # ATR volatility gate (ATR at the entry bar >= its rolling median)
        i = int(np.searchsorted(mi, np.datetime64(pd.Timestamp(t.entry_time)), "right")) - 1
        if i < 0 or i >= len(atr):
            continue
        a = atr.values[i]; mm = med.values[i]
        if np.isnan(a) or np.isnan(mm) or a < mm:
            continue
        out.append(dict(entry_ts=str(t.entry_time), exit_ts=str(t.exit_time),
                        side=t.side, entry=round(float(t.entry), 3),
                        exit_reason=t.exit_reason, net_r=round(float(t.r_multiple), 3),
                        atr=round(float(a), 3)))
    data_end = m15.index[-1]
    warm_edge = data_end - pd.Timedelta(days=M15_DAYS - WARMUP_DAYS)
    return out, str(data_end), warm_edge


def load_state():
    return json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else None
def save_state(st):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True); STATE_PATH.write_text(json.dumps(st, indent=2))
def log_trade(row):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG_PATH.exists()
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        if new: fh.write("entry_ts,exit_ts,side,entry,exit_reason,net_R,atr,nav\n")
        fh.write(",".join(str(x) for x in row) + "\n")


def main():
    closed, data_end, warm_edge = simulate()
    st = load_state()
    if st is None:
        st = dict(initialized_at=data_end, last_exit_ts=data_end, nav=100000.0, n_trades=0, sum_R=0.0, longs=0, shorts=0)
        save_state(st)
        notifier.post(
            f"*[ATR-STACK]* Track 3 forward paper trial initialized {data_end} UTC -- {INSTRUMENT} "
            f"FVG+NY, fast_trend(20/100) filtered, + ATR>=median volatility gate, $1k risk/trade, paper only.\n"
            f"Pre-registered: >={VERDICT_TRADES} closed trades before any verdict; 6-month checkpoint. "
            f"It was the only robustness-study change that improved validation AND survived 5x cost -- "
            f"but it still didn't beat buy-and-hold in the bull. Forward fills are the test. No real capital, ever.")
        print("initialized"); return

    init = pd.Timestamp(st["initialized_at"]); last = pd.Timestamp(st["last_exit_ts"]); msgs = []
    for c in closed:
        ets, xts = pd.Timestamp(c["entry_ts"]), pd.Timestamp(c["exit_ts"])
        if xts <= last or ets <= init or ets < warm_edge:
            continue
        st["n_trades"] += 1; st["sum_R"] += c["net_r"]; st["nav"] += c["net_r"] * RISK_USD
        st["longs" if c["side"] == "buy" else "shorts"] += 1
        log_trade([c["entry_ts"], c["exit_ts"], c["side"], c["entry"], c["exit_reason"], c["net_r"], c["atr"], round(st["nav"], 2)])
        exp = st["sum_R"] / st["n_trades"]; side = "LONG" if c["side"] == "buy" else "SHORT"
        msgs.append(
            f"*[ATR-STACK]* CLOSED {side} {INSTRUMENT} -- {c['exit_reason'].upper()} -> {c['net_r']:+.2f}R "
            f"(${c['net_r']*RISK_USD:+,.0f})\nEntered {c['entry_ts']} @ {c['entry']:.2f}, exited {c['exit_ts']}.\n"
            f"Trial: {st['n_trades']} trades ({st['longs']}L/{st['shorts']}S), avg {exp:+.3f}R, "
            f"NAV ${st['nav']:,.0f}. Verdict needs >={VERDICT_TRADES} -- {max(0, VERDICT_TRADES-st['n_trades'])} to go. Paper only.")

    st["last_exit_ts"] = data_end; save_state(st)
    for m in msgs: notifier.post(m)

    now = datetime.now(timezone.utc)
    if not msgs and now.weekday() == 4 and 17 <= now.hour <= 21:
        exp = (st["sum_R"] / st["n_trades"]) if st["n_trades"] else 0.0
        notifier.post(
            f"*[ATR-STACK]* weekly heartbeat -- {st['n_trades']} trades ({st['longs']}L/{st['shorts']}S), "
            f"avg {exp:+.3f}R, NAV ${st['nav']:,.0f} | {max(0, VERDICT_TRADES-st['n_trades'])} trades until verdict. Paper only.")
    print(f"run ok: {len(msgs)} new closed trades; nav {st['nav']:.0f}")


if __name__ == "__main__":
    main()
