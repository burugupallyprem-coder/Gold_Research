"""intraday_stack_paper.py -- Track 2 FORWARD PAPER TRIAL. Simulation only.

PRE-REGISTERED 2026-07-22. Settles, with forward data, whether the intraday stack
  FVG + NY-Opening entries (Displacement dropped), confidence gate ON,
  filtered to trade ONLY in the direction of the daily 50/200-EMA + 12-month-momentum trend
has a real edge on XAU_USD once live fill quality is priced in.

Honest context, on the record (see reports/rigorous_backtest_2026-07-22.md):
  - At realistic 1x cost the stack made +0.138 R/trade over 811 trades, positive in 7/8 years.
  - At 3x cost it INVERTS to -0.035 R/trade, negative in 6/8 years. The edge is thin and
    cost-fragile -- roughly the size of the spread it pays.
  - 90% of backtest trades were LONG; the short side (10%) is barely tested. The backtest is
    largely "buy gold intraday during a gold bull market." A sustained downtrend is untested.
The weight of evidence says live fills decide this. It runs because forward paper is the only
fair judge, and paper costs nothing.

Judgment gates (pre-registered, no moving): >= 30 closed trades before any verdict.
6-month checkpoint. "Alive" requires positive net expectancy after costs AND not being
profitable only while gold rises (the log tags trade direction so this can be checked).
Any step beyond paper needs months more data + Prem's explicit approval.

This bot NEVER places orders: it fetches candles and simulates via the validated
backtest.engine_final. There is no broker order code in this file. Reuses the SAME engine
the backtests used, so paper == backtest mechanics.

Test mode (no network):
  ISP_LOCAL_M15=data/candles/XAU_USD_M15.csv ISP_LOCAL_H4=data/candles/XAU_USD_H4.csv \
  ISP_LOCAL_D=data/daily/XAU_USD_D.csv ISP_ASOF=2026-06-05 python intraday_stack_paper.py
Run (live practice candles): python intraday_stack_paper.py
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
STATE_PATH = Path(os.environ.get("ISP_STATE", ROOT / "memory" / "intraday_stack_state.json"))
LOG_PATH = Path(os.environ.get("ISP_TRADELOG", ROOT / "reports" / "intraday_stack_trades.csv"))

RISK_USD = 1000.0            # 1% of $100k, no compounding (declared; matches RiskConfig)
M15_DAYS = 150               # trailing entry window fetched
D_DAYS = 420                 # daily history for the 200-EMA/12m-mom trend filter
WARMUP_DAYS = 30             # ignore trades entered in the warm-up lead-in
VERDICT_TRADES = 30          # pre-registered gate

# FROZEN strategy definition (the pre-registered stack)
STRAT = StrategyConfig(use_displacement=False, use_fvg=True, enable_ny_opening=True)
COST = CostModel()           # 0.30 spread + 0.10 slippage (backtest assumption)
BT = BacktestConfig(use_confidence_gate=True)


# ---------- data ----------
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
    lm = os.environ.get("ISP_LOCAL_M15")
    asof = os.environ.get("ISP_ASOF")
    if lm:
        m15 = _local(lm, asof)
        m15 = m15[m15.index >= m15.index[-1] - pd.Timedelta(days=M15_DAYS)]
        h4 = _local(os.environ["ISP_LOCAL_H4"], asof)
        d1 = _local(os.environ["ISP_LOCAL_D"], asof)
        return m15, h4, d1
    m15 = _fetch("M15", M15_DAYS)
    h4 = _fetch("H4", M15_DAYS + 30)
    d1 = _fetch("D", D_DAYS)
    return m15, h4, d1


# ---------- trend filter ----------
def daily_dir(d1):
    px = d1.copy()
    px.index = pd.DatetimeIndex(px.index).tz_localize(None) if px.index.tz else pd.DatetimeIndex(px.index)
    w = compute_weights(px, None, MacroConfig(ema_fast=50, ema_slow=200,
                                              mom_lookback=252, use_macro=True))
    md = np.sign(w["pos_dir"]).astype(float)
    md.index = pd.DatetimeIndex(md.index)
    return md


# ---------- simulate ----------
def simulate():
    m15, h4, d1 = load_data()
    res = run_backtest_fast(m15, h4, STRAT, RiskConfig(), BT, COST)
    md = daily_dir(d1)
    out = []
    for t in res.trades:
        if t.exit_time is None:
            continue
        ent = pd.Timestamp(t.entry_time).tz_localize(None)
        d = md.reindex(md.index.union([ent])).ffill().reindex([ent]).values[0]
        if np.isnan(d) or d != (1 if t.side == "buy" else -1):
            continue
        # use the engine's own R (based on ORIGINAL planned risk; correct even
        # after a break-even stop move, which zeroes entry-vs-stop distance).
        net_r = float(t.r_multiple)
        out.append(dict(entry_ts=str(t.entry_time), exit_ts=str(t.exit_time),
                        side=t.side, entry=round(float(t.entry), 3),
                        exit_reason=t.exit_reason, net_r=round(float(net_r), 3)))
    data_end = m15.index[-1]
    warm_edge = data_end - pd.Timedelta(days=M15_DAYS - WARMUP_DAYS)
    return out, str(data_end), warm_edge


# ---------- state / log ----------
def load_state():
    return json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else None


def save_state(st):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(st, indent=2))


def log_trade(row):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG_PATH.exists()
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        if new:
            fh.write("entry_ts,exit_ts,side,entry,exit_reason,net_R,nav\n")
        fh.write(",".join(str(x) for x in row) + "\n")


def main():
    closed, data_end, warm_edge = simulate()
    st = load_state()

    if st is None:
        st = dict(initialized_at=data_end, last_exit_ts=data_end, nav=100000.0,
                  n_trades=0, sum_R=0.0, longs=0, shorts=0)
        save_state(st)
        notifier.post(
            f"*[INTRADAY-STACK]* Track 2 forward paper trial initialized {data_end} UTC "
            f"-- {INSTRUMENT} FVG+NY intraday, daily-trend filtered, $1k risk/trade, paper only.\n"
            f"Pre-registered: >={VERDICT_TRADES} closed trades before any verdict; 6-month "
            f"checkpoint. Backtest was +0.14R/trade at 1x cost but NEGATIVE at 3x, and 90% long "
            f"-- so live fills and a gold downtrend are the real tests. No real capital, ever, "
            f"from this trial.")
        print("initialized"); return

    init = pd.Timestamp(st["initialized_at"])
    last = pd.Timestamp(st["last_exit_ts"])
    msgs = []
    for c in closed:
        ets, xts = pd.Timestamp(c["entry_ts"]), pd.Timestamp(c["exit_ts"])
        if xts <= last or ets <= init or ets < warm_edge:
            continue
        st["n_trades"] += 1
        st["sum_R"] += c["net_r"]
        st["nav"] += c["net_r"] * RISK_USD
        st["longs" if c["side"] == "buy" else "shorts"] += 1
        log_trade([c["entry_ts"], c["exit_ts"], c["side"], c["entry"],
                   c["exit_reason"], c["net_r"], round(st["nav"], 2)])
        exp = st["sum_R"] / st["n_trades"]
        side = "LONG" if c["side"] == "buy" else "SHORT"
        msgs.append(
            f"*[INTRADAY-STACK]* CLOSED {side} {INSTRUMENT} -- {c['exit_reason'].upper()} "
            f"-> {c['net_r']:+.2f}R (${c['net_r']*RISK_USD:+,.0f})\n"
            f"Entered {c['entry_ts']} @ {c['entry']:.2f}, exited {c['exit_ts']}.\n"
            f"Trial: {st['n_trades']} trades ({st['longs']}L/{st['shorts']}S), avg {exp:+.3f}R, "
            f"NAV ${st['nav']:,.0f}. Verdict needs >={VERDICT_TRADES} -- "
            f"{max(0, VERDICT_TRADES-st['n_trades'])} to go. Paper only.")

    st["last_exit_ts"] = data_end
    save_state(st)
    for m in msgs:
        notifier.post(m)

    now = datetime.now(timezone.utc)
    if not msgs and now.weekday() == 4 and 17 <= now.hour <= 21:
        exp = (st["sum_R"] / st["n_trades"]) if st["n_trades"] else 0.0
        notifier.post(
            f"*[INTRADAY-STACK]* weekly heartbeat -- {st['n_trades']} trades "
            f"({st['longs']}L/{st['shorts']}S), avg {exp:+.3f}R, NAV ${st['nav']:,.0f} | "
            f"{max(0, VERDICT_TRADES-st['n_trades'])} trades until verdict. Paper only.")
    print(f"run ok: {len(msgs)} new closed trades; nav {st['nav']:.0f}")


if __name__ == "__main__":
    main()
