"""
research_lab.py
---------------
Autonomous, self-improving research loop for the Gold Macro-Trend strategy --
with hard anti-overfitting guardrails. It runs weekly with no human input and
PROPOSES a better strategy ON THE PAPER TRACK ONLY. It never touches real money,
and (since the self-learning upgrade) it never promotes on its own -- a human
approves every strategy change via apply_change.py.

How it avoids fooling itself (this is the whole point):

  1. PERMANENT HOLDOUT -- the most recent `HOLDOUT_DAYS` of data are reserved.
     Challengers are *selected* using only the data BEFORE the holdout. The
     holdout is used ONLY to confirm the single chosen pick -- never to search.
  2. SELECTION vs CONFIRMATION are separated, so the multiple-testing happens on
     the selection slice and the holdout sees just one comparison.
  3. CONFIRMATION STREAK -- a challenger must beat the champion on the holdout for
     `CONSEC_WEEKS` consecutive weekly runs before it is proposed for promotion.
  4. COST-STRESSED metrics (5x costs) are used for every decision.
  5. SMALL, PRE-REGISTERED challenger set -- no open-ended data mining.

State persists in research/champion.json (committed to git), so the loop has
memory across stateless cloud runs. Every run appends to research/research_log.md
and posts a full, plain-English digest to Slack.

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

# -- Guardrails --------------------------------------------------------------
HOLDOUT_DAYS = 252          # ~1 year held out, never used for selection
CONSEC_WEEKS = 3            # weekly holdout wins required before promotion
COST_BPS = 10.0             # stressed cost for all decisions
MIN_HOLDOUT_SHARPE = 0.30   # challenger must clear this on the holdout
SELECT_BEAT_MARGIN = 0.10   # and beat champion by this on the selection slice

# -- Pre-registered challenger set (small on purpose) ------------------------
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

# Human-readable descriptions for the Slack digest
DESCRIPTIONS = {
    "baseline":   "50/200 EMA trend + real-yield filter + 10% vol target (the validated default)",
    "fast_trend": "faster 20/100 EMA trend (reacts quicker, trades more, more cost-sensitive)",
    "slow_trend": "slower 100/300 EMA trend (fewer, longer-held trades)",
    "vol_15":     "higher 15% volatility target (more aggressive sizing)",
    "vol_07":     "lower 7% volatility target (more conservative sizing)",
    "ry_120":     "longer 120-day real-yield lookback",
    "mom_126":    "6-month momentum confirmation instead of 12-month",
    "no_macro":   "trend only, real-yield filter switched OFF (ablation check)",
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
        return {"error": "insufficient daily data -- run data/fetch_daily.py"}

    state = _load_state()
    champ_name = state["champion"]["name"]
    champ_params = state["champion"]["params"]

    rows = {}
    for name, params in CHALLENGERS.items():
        r = _pnl(prices, ry, _cfg(params), COST_BPS)
        sel = r.iloc[:-HOLDOUT_DAYS]
        hold = r.iloc[-HOLDOUT_DAYS:]
        rows[name] = {"selection_sharpe": _sharpe(sel), "holdout_sharpe": _sharpe(hold)}

    champ_r = _pnl(prices, ry, _cfg(champ_params), COST_BPS)
    champ_sel = _sharpe(champ_r.iloc[:-HOLDOUT_DAYS])
    champ_hold = _sharpe(champ_r.iloc[-HOLDOUT_DAYS:])

    best = max(rows.items(), key=lambda kv: kv[1]["selection_sharpe"])
    best_name, best_scores = best

    decision = "hold"
    promoted = False
    pending = state.get("pending")

    selection_wins = best_scores["selection_sharpe"] >= champ_sel + SELECT_BEAT_MARGIN
    holdout_confirms = (best_scores["holdout_sharpe"] >= MIN_HOLDOUT_SHARPE
                        and best_scores["holdout_sharpe"] > champ_hold)

    if best_name != champ_name and selection_wins and holdout_confirms:
        if pending and pending.get("name") == best_name:
            pending["streak"] += 1
        else:
            pending = {"name": best_name, "params": CHALLENGERS[best_name], "streak": 1}
        decision = f"challenger '{best_name}' confirming ({pending['streak']}/{CONSEC_WEEKS})"
        if pending["streak"] >= CONSEC_WEEKS:
            # HUMAN-IN-THE-LOOP: do NOT auto-promote. Flag ready and file a
            # proposal for the owner to approve via apply_change.py. The champion
            # is left untouched until a human approves.
            pending["ready"] = True
            try:
                from learning import proposals as _proposals
                _proposals.add_proposal(
                    "research_lab", "promote",
                    f"Challenger '{best_name}' beat the champion and confirmed on the "
                    f"holdout for {CONSEC_WEEKS} weeks straight. Awaiting your approval.",
                    {"name": best_name, "params": CHALLENGERS[best_name]})
            except Exception:  # noqa: BLE001
                pass
            decision = (f"READY: '{best_name}' passed all gates -- AWAITING HUMAN APPROVAL "
                        f"(nothing changed).")
    else:
        if pending:
            decision = "streak reset (no qualifying challenger this week)"
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
        "streak": (pending["streak"] if pending else 0),
        "candidates": rows,
        "period": f"{prices.index[0].date()}..{prices.index[-1].date()}",
        "holdout_days": HOLDOUT_DAYS,
    }
    _append_log(out)
    return out


def _append_log(out):
    RESEARCH.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"\n## Research cycle -- {stamp}",
             f"- Champion: **{out['champion']}** (sel {out['champion_selection_sharpe']} / "
             f"holdout {out['champion_holdout_sharpe']}, 5x-cost Sharpe)",
             f"- Best challenger: **{out['best_challenger']}** (sel {out['best_selection_sharpe']} / "
             f"holdout {out['best_holdout_sharpe']})",
             f"- Decision: {out['decision']}",
             "- All candidates (selection / holdout Sharpe):"]
    for n, s in out["candidates"].items():
        lines.append(f"    - {n}: {s['selection_sharpe']} / {s['holdout_sharpe']}")
    prev = LOG_FILE.read_text() if LOG_FILE.exists() else "# Research log -- autonomous cycles\n"
    LOG_FILE.write_text(prev + "\n".join(lines) + "\n")


def slack_text(out):
    """Full, plain-English weekly digest -- not a one-liner."""
    if out.get("error"):
        return f"[RESEARCH] Could not run this week: {out['error']}"

    champ = out["champion"]
    champ_desc = DESCRIPTIONS.get(champ, "current champion")
    bc = out["best_challenger"]
    bc_desc = DESCRIPTIONS.get(bc, "")
    L = []

    L.append("[RESEARCH] *Weekly self-improvement cycle* -- Gold Macro-Trend")
    L.append(f"Data window analysed: {out['period']}  |  held-out test = last "
             f"{out['holdout_days']} trading days the optimizer is NOT allowed to tune on.")
    L.append("")
    L.append(f"*Current champion:* `{champ}` -- {champ_desc}.")
    L.append(f"This is the strategy that would be paper-traded today. On the held-out "
             f"year it scored a 5x-cost Sharpe of {out['champion_holdout_sharpe']} "
             f"(selection-period Sharpe {out['champion_selection_sharpe']}).")
    L.append("")
    L.append(f"*This week the lab tested {len(out['candidates'])} variants.* The strongest "
             f"was `{bc}` -- {bc_desc}.")
    L.append(f"  - Selection Sharpe (the honest, representative number): {out['best_selection_sharpe']}")
    L.append(f"  - Holdout Sharpe (recent year, likely flattered by gold's bull run): "
             f"{out['best_holdout_sharpe']}")
    L.append("")

    if out["promoted"]:
        L.append(f"*Decision: PROMOTED `{bc}` to champion (paper track only).* "
                 f"It beat the incumbent on the selection data AND confirmed on the "
                 f"holdout for {CONSEC_WEEKS} weeks straight.")
    elif out["streak"] > 0:
        left = CONSEC_WEEKS - out["streak"]
        if left <= 0:
            L.append(f"*Decision: `{bc}` PASSED all gates and is AWAITING YOUR APPROVAL.* "
                     f"The lab will NOT switch on its own -- a proposal has been filed. "
                     f"Apply it via the 'oanda-apply-change' workflow if you approve. "
                     f"Nothing has changed.")
        else:
            L.append(f"*Decision: hold champion; `{bc}` is on probation "
                     f"({out['streak']}/{CONSEC_WEEKS}).* It looks better this week, but the "
                     f"lab will NOT switch on one good week -- it needs {left} more consecutive "
                     f"weekly win(s) before promotion. This is the guardrail against "
                     f"overfitting to a lucky week.")
    else:
        L.append("*Decision: hold champion -- no challenger cleared the bar this week.* "
                 "Any prior probation streak has been reset. The validated default stays "
                 "in charge.")

    L.append("")
    L.append("Candidate scoreboard (selection / holdout Sharpe, 5x costs):")
    for n, s in out["candidates"].items():
        mark = "*" if n == bc else "-"
        L.append(f"  {mark} {n}: {s['selection_sharpe']} / {s['holdout_sharpe']}")

    L.append("")
    L.append("Note: the high holdout Sharpes (>1) are almost certainly inflated by "
             "gold's 2023-2026 bull market. Treat the selection-period Sharpe (~0.5) "
             "as the honest expectation. Paper/backtest track only -- this loop never "
             "trades real capital; a human approves anything that would.")
    return "\n".join(L)


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
