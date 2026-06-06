"""
research_lab.py
---------------
Autonomous, self-improving research loop for the Gold Macro-Trend strategy —
with hard anti-overfitting guardrails. It runs weekly with no human input and
can promote a better strategy ON THE PAPER TRACK ONLY. It never touches real
money.

How it avoids fooling itself (this is the whole point):

  1. PERMANENT HOLDOUT — the most recent `HOLDOUT_DAYS` of data are reserved.
     Challengers are *selected* using only the data BEFORE the holdout. The
     holdout is used ONLY to confirm the single chosen pick — never to search.
  2. SELECTION vs CONFIRMATION are separated, so the multiple-testing happens on
     the selection slice and the holdout sees just one comparison.
  3. CONFIRMATION STREAK — a challenger must beat the champion on the holdout for
     `CONSEC_WEEKS` consecutive weekly runs before it is promoted.
  4. COST-STRESSED metrics (5x costs) are used for every decision.
  5. SMALL, PRE-REGISTERED challenger set — no open-ended data mining.

State persists in research/champion.json (committed to git), so the loop has
memory across stateless cloud runs. Every run appends to research/research_log.md
and posts a digest to Slack.

    python research_lab.py            # one weekly cycle (dry Slack if no token)
    python research_lab.py --commit   # + git push state
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import SETTINGS                              # noqa: E402
from strategy.macro_trend import MacroConfig, compute_weights, ANN  # noqa: E402
from execution import notifier                           # noqa: E402

DAILY = ROOT / "data" / "daily"
RESEARCH = ROOT / "research"
CHAMPION_FILE = RESEARCH / "champion.json"
LOG_FILE = RESEARCH / "research_log.md"

# ── Guardrails ────────────────────────────────────────────────────────────
HOLDOUT_DAYS = 252          # ~1 year held out, never used for selection
CONSEC_WEEKS = 3            # weekly holdout wins required before promotion
COST_BPS = 10.0            # stressed cost for all decisions
MIN_HOLDOUT_SHARPE = 0.30   # challenger must clear this on the holdout
SELECT_BEAT_MARGIN = 0.10   # and beat champion by this on the selection slice

# ── Pre-registered challenger set (small on purpose) ────────────────────────
BASELINE = {"ema_fast": 50, "ema_slow": 200, "mom_lookback": 252,
            "ry_mom_lookback": 60, "target_vol": 0.10, "use_macro": True}
CHALLENGERS = {
    "baseline":      {},
    "fast_trend":    {"ema_fast": 20, "ema_slow": 100},
    "slow_trend":    {"ema_fast": 100, "ema_slow": 300},
    "vol_15":        {"target_vol": 0.15},
    "vol_07":        {"target_vol": 0.07},
    "ry_120":        {"ry_mom_lookback": 120},
    "mom_126":       {"mom_lookback": 126},
    "no_macro":      {"use_macro": False},
}


def _cfg(params: dict) -> MacroConfig:
    merged = {**BASELINE, **params}
    return MacroConfig(**merged)


def _pnl(prices, ry, cfg, cost_bps):
    w = compute_weights(prices, ry, cfg)["weight"]
    ret = prices["close"].astype(float).pct_change().fillna(0.0)
    pos = w.shift(1).fillna(0.0)
    turn = (pos - pos.shift(1)).abs().fillna(0.0)
    return (pos * ret - turn * cost_bps / 1e4)


def _sharpe(r: pd.Series) -> float:
    r = r.dropna()
    if len(r) < 30 or r.std() == 0:
        return 0.0
    return round(float(r.mean() / r.std() * math.sqrt(ANN)), 3)


def _load_data():
    p = DAILY / f"{SETTINGS.instrument}_D.csv"
    if not p.exists():
        return None, None
    px = pd.read_csv(p, parse_dates=["time"]).set_index("time").sort_index()
    ryp = DAILY / "DFII10.csv"
    ry = None
    if ryp.exists():
        ry = pd.read_csv(ryp, parse_dates=["time"]).set_index("time").sort_index()["dfii10"]
    return px, ry


def _load_state():
    if CHAMPION_FILE.exists():
        return json.loads(CHAMPION_FILE.read_text())
    return {"champion": {"name": "baseline", "params": {}}, "pending": None, "history": []}


def _save_state(state):
    RESEARCH.mkdir(exist_ok=True)
    CHAMPION_FILE.write_text(json.dumps(state, indent=2, default=str))


def run_cycle():
    prices, ry = _load_data()
    if prices is None or len(prices) < HOLDOUT_DAYS + 400:
        return {"error": "insufficient daily data — run data/fetch_daily.py"}

    state = _load_state()
    champ_name = state["champion"]["name"]
    champ_params = state["champion"]["params"]

    # Evaluate every candidate: compute full causal pnl, then slice.
    rows = {}
    for name, params in CHALLENGERS.items():
        r = _pnl(prices, ry, _cfg(params), COST_BPS)
        sel = r.iloc[:-HOLDOUT_DAYS]
        hold = r.iloc[-HOLDOUT_DAYS:]
        rows[name] = {"selection_sharpe": _sharpe(sel), "holdout_sharpe": _sharpe(hold)}

    # Champion's own scores (champion may be a named challenger or custom params)
    champ_r = _pnl(prices, ry, _cfg(champ_params), COST_BPS)
    champ_sel = _sharpe(champ_r.iloc[:-HOLDOUT_DAYS])
    champ_hold = _sharpe(champ_r.iloc[-HOLDOUT_DAYS:])

    # SELECTION: pick the best challenger by selection-slice Sharpe (NOT holdout)
    best = max(rows.items(), key=lambda kv: kv[1]["selection_sharpe"])
    best_name, best_scores = best

    decision = "hold"
    promoted = False
    pending = state.get("pending")

    selection_wins = best_scores["selection_sharpe"] >= champ_sel + SELECT_BEAT_MARGIN
    holdout_confirms = (best_scores["holdout_sharpe"] >= MIN_HOLDOUT_SHARPE
                        and best_scores["holdout_sharpe"] > champ_hold)

    if best_name != champ_name and selection_wins and holdout_confirms:
        # maintain / start the confirmation streak for this specific challenger
        if pending and pending.get("name") == best_name:
            pending["streak"] += 1
        else:
            pending = {"name": best_name, "params": CHALLENGERS[best_name], "streak": 1}
        decision = f"challenger '{best_name}' confirming ({pending['streak']}/{CONSEC_WEEKS})"
        if pending["streak"] >= CONSEC_WEEKS:
            state["champion"] = {"name": best_name, "params": CHALLENGERS[best_name]}
            state["history"].append({
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "action": "promote", "from": champ_name, "to": best_name,
                "holdout_sharpe": best_scores["holdout_sharpe"]})
            pending = None
            promoted = True
            decision = f"PROMOTED '{best_name}' -> champion (paper track)"
    else:
        # streak broken — reset
        if pending:
            decision = f"streak reset (no qualifying challenger this week)"
        pending = None

    state["pending"] = pending
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    _save_state(state)

    out = {
        "champion": state["champion"]["name"],
        "champion_selection_sharpe": champ_sel,
        "champion_holdout_sharpe": champ_hold,
        "best_challenger": best_name,
        "best_selection_sharpe": best_scores["selection_sharpe"],
        "best_holdout_sharpe": best_scores["holdout_sharpe"],
        "decision": decision,
        "promoted": promoted,
        "candidates": rows,
        "period": f"{prices.index[0].date()}..{prices.index[-1].date()}",
        "holdout_days": HOLDOUT_DAYS,
    }
    _append_log(out)
    return out


def _append_log(out):
    RESEARCH.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"\n## Research cycle — {stamp}",
             f"- Champion: **{out['champion']}** (sel {out['champion_selection_sharpe']} / "
             f"holdout {out['champion_holdout_sharpe']}, 5x-cost Sharpe)",
             f"- Best challenger: **{out['best_challenger']}** (sel {out['best_selection_sharpe']} / "
             f"holdout {out['best_holdout_sharpe']})",
             f"- Decision: {out['decision']}",
             "- All candidates (selection / holdout Sharpe):"]
    for n, s in out["candidates"].items():
        lines.append(f"    - {n}: {s['selection_sharpe']} / {s['holdout_sharpe']}")
    prev = LOG_FILE.read_text() if LOG_FILE.exists() else "# Research log — autonomous cycles\n"
    LOG_FILE.write_text(prev + "\n".join(lines) + "\n")


def slack_text(out):
    if out.get("error"):
        return f"[RESEARCH] {out['error']}"
    head = "🏆 PROMOTION" if out["promoted"] else "🔬 research cycle"
    return "\n".join([
        f"[RESEARCH] {head} — champion: *{out['champion']}*  ({out['period']})",
        f"Champion holdout Sharpe (5x cost): {out['champion_holdout_sharpe']}",
        f"Best challenger: {out['best_challenger']} "
        f"(sel {out['best_selection_sharpe']} / holdout {out['best_holdout_sharpe']})",
        f"Decision: {out['decision']}",
        "_Paper track only — no real capital is ever traded. Holdout-confirmed, "
        f"{CONSEC_WEEKS}-week streak required to promote._",
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    notifier.start("research")
    out = run_cycle()
    text = slack_text(out)
    notifier.post(text)
    print(text)

    if args.commit:
        msg = f"research: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC"
        for cmd in (["git", "-C", str(ROOT), "add", "research", "reports", "memory"],
                    ["git", "-C", str(ROOT), "commit", "-m", msg],
                    ["git", "-C", str(ROOT), "push"]):
            subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
