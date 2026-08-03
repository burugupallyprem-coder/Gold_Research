"""Forward PAPER tracker for one ongoing Apex $50k combine on MGC. SIMULATION ONLY -
tracks a virtual account so we can see the real pass rate before any eval fee or real
money. It NEVER places an order and NEVER touches a real prop account. Real-money
funding stays gated behind the F-1 steps (attorney + DSO + approval)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .strategy import trend_signal, trend_position, DEFAULTS
from .apex import run_forward
from .data import load_prices

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state" / "mgc_paper.json"


def _load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"account": "50k", "combine_start": None, "cfg": {}, "history": []}


def _save_state(st):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2, default=str))


def run(prefer_mgc=True):
    st = _load_state()
    cfg = {**DEFAULTS, **st.get("cfg", {})}
    ohlc, source = load_prices(prefer_mgc=prefer_mgc)
    dates = list(ohlc.index)
    latest_bar = str(pd.to_datetime(dates[-1]).date())
    # DEDUP: many staggered triggers fire (GitHub cron is late); only the FIRST run per
    # new daily bar should act. Redundant same-bar runs exit without posting or committing.
    if st.get("combine_start") is not None and st.get("last_bar_processed") == latest_bar:
        print(f"[MGC-PAPER] dedup: bar {latest_bar} already processed this cycle - "
              f"skipping (no Slack, no commit).")
        return {"status": "dedup_skip", "bar": latest_bar}
    if st["combine_start"] is None:      # first run -> start a fresh combine at the latest bar
        st["combine_start"] = str(pd.to_datetime(dates[-1]).date())
    cstart = pd.to_datetime(st["combine_start"])
    start_i = next((i for i, d in enumerate(dates) if pd.to_datetime(d) >= cstart), len(dates) - 1)
    # LONG-ONLY trend, exit on flip. (Chandelier + re-entry were tested and did NOT survive
    # causal validation - the earlier gain was a look-ahead artifact; see MENTOR docs.)
    sig = trend_signal(ohlc["close"], cfg["ema_fast"], cfg["ema_slow"]).clip(lower=0).shift(1).fillna(0.0).values
    s = run_forward(ohlc["close"].values, ohlc["high"].values, ohlc["low"].values, sig,
                    start_i, st["account"], cfg["stop_pts"], cfg["base_contracts"], cfg["safety"])
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st["last_run"] = ts; st["last_status"] = s; st["source"] = source
    st["last_bar_processed"] = latest_bar
    st.setdefault("history", []).append({"utc": ts, "status": s["status"], "balance": s["balance"], "days": s["days"]})
    _save_state(st)

    line = (f"[MGC-PAPER] {ts} | Apex {st['account']} combine (SIMULATION, no real money) | "
            f"source: {source}\nstatus: {s['status'].upper()} on day {s['days']} | "
            f"balance ${s['balance']} | floor ${s['floor']} | "
            f"{'LOCKED' if s['locked'] else 'trailing'} | today: {int(s['today_contracts'])} MGC "
            f"{'long' if s['today_signal']>0 else 'short' if s['today_signal']<0 else 'flat'}")
    if s["status"] == "passed":
        line += f"\nPASSED the paper combine in {s['days']} days -- a real eval would be worth considering AFTER the F-1 gate."
    elif s["status"] == "failed":
        line += f"\nFAILED ({s['reason']}) -- reset the combine to start a fresh paper attempt."
    print(line)
    try:
        from execution import notifier
        notifier.post(line)
    except Exception:
        pass
    return s


if __name__ == "__main__":
    run()
