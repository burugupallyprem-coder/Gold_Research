"""
learning/monitor.py
-------------------
The self-learning loop's REVIEW step. It reads the bot's own trade ledger,
measures how the live paper account actually performed, compares that to the
backtest expectation, and — if something looks wrong, or a better strategy is
waiting — writes a human-approval PROPOSAL and emails a warning.

It NEVER changes the strategy itself. A human applies changes via apply_change.py
(the manual 'oanda-apply-change' workflow).

Honest design note: this is a DAILY strategy, so live samples grow slowly. Until
MIN_DAYS_TO_LEARN position-days exist, the monitor only reports, and will only
ever propose *de-risking* (never a strategy swap) on a small sample.

  python -m learning.monitor
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import SETTINGS                                        # noqa: E402
from strategy.macro_trend import MacroConfig, compute_weights, ANN  # noqa: E402
from execution import notifier                                     # noqa: E402
from learning import ledger, proposals                             # noqa: E402
from learning.emailer import send_email                            # noqa: E402

DAILY = ROOT / "data" / "daily"
RESEARCH = ROOT / "research"
MEM = ROOT / "memory"

# ── Tunable thresholds (override via env / GitHub repo variables) ───────────
MIN_DAYS_TO_LEARN = int(os.getenv("MIN_DAYS_TO_LEARN", "30"))
MAX_LIVE_DD = float(os.getenv("MAX_LIVE_DD", "0.25"))            # 25%
LIVE_SHARPE_FLOOR = float(os.getenv("LIVE_SHARPE_FLOOR", "0.0"))
DERISK_VOL_FLOOR = float(os.getenv("DERISK_VOL_FLOOR", "0.05"))
BASELINE = {"ema_fast": 50, "ema_slow": 200, "mom_lookback": 252,
            "ry_mom_lookback": 60, "target_vol": 0.10, "use_macro": True}


def _sharpe(rets) -> float:
    s = pd.Series(list(rets)).dropna()
    if len(s) < 5 or s.std() == 0:
        return 0.0
    return round(float(s.mean() / s.std() * math.sqrt(ANN)), 3)


def _max_drawdown(rets) -> float:
    eq = peak = 1.0
    mdd = 0.0
    for r in rets:
        eq *= (1.0 + r)
        peak = max(peak, eq)
        if peak > 0:
            mdd = min(mdd, eq / peak - 1.0)
    return round(abs(mdd), 4)


def _load_prices():
    p = DAILY / f"{SETTINGS.instrument}_D.csv"
    if not p.exists():
        return None, None
    px = pd.read_csv(p, parse_dates=["time"]).set_index("time").sort_index()
    ryp = DAILY / "DFII10.csv"
    ry = (pd.read_csv(ryp, parse_dates=["time"]).set_index("time").sort_index()["dfii10"]
          if ryp.exists() else None)
    return px, ry


def _champion():
    f = RESEARCH / "champion.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            pass
    return {"champion": {"name": "baseline", "params": {}}, "pending": None}


def _expected_sharpe(prices, ry, params) -> float | None:
    if prices is None:
        return None
    cfg = MacroConfig(**{**BASELINE, **(params or {})})
    w = compute_weights(prices, ry, cfg)["weight"]
    ret = prices["close"].astype(float).pct_change().fillna(0.0)
    live = (w.shift(1).fillna(0.0) * ret)
    return _sharpe(live.tolist())


def run():
    daily = ledger.build_daily_returns()
    rets = [d["ret"] for d in daily]
    active = [d for d in daily if d["position"]]
    n = len(active)
    live_sharpe = _sharpe(rets)
    live_dd = _max_drawdown(rets)
    cum = round((pd.Series([1.0 + r for r in rets]).prod() - 1.0) * 100, 2) if rets else 0.0
    hit = round(100.0 * sum(1 for d in active if d["pnl"] > 0) / n, 1) if n else 0.0

    champ = _champion()
    champ_name = champ["champion"]["name"]
    prices, ry = _load_prices()
    exp_sharpe = _expected_sharpe(prices, ry, champ["champion"].get("params"))

    stats = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "position_days": n,
        "live_sharpe": live_sharpe,
        "expected_sharpe": exp_sharpe,
        "live_drawdown": live_dd,
        "live_cum_return_pct": cum,
        "live_hit_rate_pct": hit,
        "champion": champ_name,
        "min_days_to_learn": MIN_DAYS_TO_LEARN,
    }
    MEM.mkdir(parents=True, exist_ok=True)
    (MEM / "live_stats.json").write_text(json.dumps(stats, indent=2))

    # ── Decide whether to PROPOSE anything (never apply) ───────────────────
    if live_dd >= MAX_LIVE_DD:
        proposals.add_proposal(
            "monitor", "halt",
            f"Live drawdown {live_dd * 100:.1f}% breached the {MAX_LIVE_DD * 100:.0f}% limit.",
            {})
    elif n >= MIN_DAYS_TO_LEARN and live_sharpe < LIVE_SHARPE_FLOOR:
        proposals.add_proposal(
            "monitor", "derisk",
            f"Over {n} position-days the live Sharpe is {live_sharpe} (below "
            f"{LIVE_SHARPE_FLOOR}); recommend cutting target vol to {DERISK_VOL_FLOOR:g}.",
            {"target_vol": DERISK_VOL_FLOOR})

    # ── Surface a research-lab promotion that is awaiting approval ──────────
    pend = champ.get("pending")
    if pend and pend.get("ready"):
        proposals.add_proposal(
            "research_lab", "promote",
            f"Challenger '{pend['name']}' passed the historical holdout for the required "
            f"streak and is awaiting your approval.",
            {"name": pend["name"], "params": pend.get("params", {})})

    _notify(stats, proposals.list_pending())
    return stats


def _digest(stats, pending) -> str:
    L = [
        "[LEARN] Weekly self-review — Gold paper account",
        f"Champion: {stats['champion']} | position-days logged: {stats['position_days']}",
        f"Live Sharpe: {stats['live_sharpe']}  (backtest expectation: {stats['expected_sharpe']})",
        f"Live return: {stats['live_cum_return_pct']}% | drawdown: "
        f"{stats['live_drawdown'] * 100:.1f}% | hit-rate: {stats['live_hit_rate_pct']}%",
    ]
    if stats["position_days"] < stats["min_days_to_learn"]:
        L.append(f"Still gathering data ({stats['position_days']}/{stats['min_days_to_learn']} "
                 f"position-days) — monitoring only; no strategy change will be proposed yet.")
    if pending:
        L.append("")
        L.append("PROPOSALS AWAITING YOUR APPROVAL (nothing has changed):")
        for p in pending:
            L.append(f"  - [{p['type']}] {p['reason']}")
        L.append("")
        L.append("To APPLY: GitHub -> Actions -> 'oanda-apply-change' -> Run workflow -> apply.")
        L.append("To IGNORE: do nothing; the bot keeps running unchanged.")
    else:
        L.append("No changes proposed. The bot continues unchanged.")
    return "\n".join(L)


def _notify(stats, pending):
    text = _digest(stats, pending)
    notifier.post(text)
    print(text)
    if pending:
        subject = f"[ACTION NEEDED] Gold bot: {len(pending)} change(s) await your approval"
        body = (text
                + "\n\nThis is a human-in-the-loop checkpoint. Nothing changes until you "
                  "run the apply step. If you approve, trigger the 'oanda-apply-change' "
                  "workflow in GitHub. If not, ignore this email and the bot runs unchanged.")
        send_email(subject, body)


if __name__ == "__main__":
    run()
