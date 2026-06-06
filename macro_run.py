"""
macro_run.py
------------
Entrypoint for the Gold Macro-Trend validation. Loads daily gold + real-yield
data, runs the base and cost-stress backtests, derives the verdict, posts it to
Slack, and writes reports/macro_validation.json + memory/macro.json.

    python macro_run.py
    python macro_run.py --commit
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import SETTINGS                          # noqa: E402
from strategy.macro_trend import MacroConfig         # noqa: E402
from backtest import macro_backtest as mb            # noqa: E402
from execution import notifier                       # noqa: E402

DAILY = ROOT / "data" / "daily"
REPORTS = ROOT / "reports"
MEMORY = ROOT / "memory"


def _load_prices():
    p = DAILY / f"{SETTINGS.instrument}_D.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["time"]).set_index("time").sort_index()
    return df


def _load_ry():
    p = DAILY / "DFII10.csv"
    if not p.exists():
        return None
    s = pd.read_csv(p, parse_dates=["time"]).set_index("time").sort_index()["dfii10"]
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    notifier.start("macro")
    prices = _load_prices()
    if prices is None or len(prices) < 300:
        notifier.info("No daily candles — run data/fetch_daily.py first.")
        return
    ry = _load_ry()
    cfg = MacroConfig()

    base = mb.run(prices, ry, cfg, cost_bps=2.0)
    stress = mb.run(prices, ry, cfg, cost_bps=10.0)
    v = mb.verdict(base, stress)
    text = mb.slack_text(base, stress, v)

    notifier.post(text)
    print(text)

    REPORTS.mkdir(exist_ok=True)
    MEMORY.mkdir(exist_ok=True)
    out = {"base": base, "cost_stress": stress, "verdict": v,
           "macro_filter_used": ry is not None}
    (REPORTS / "macro_validation.json").write_text(json.dumps(out, indent=2, default=str))
    (MEMORY / "macro.json").write_text(json.dumps(
        {"updated": datetime.now(timezone.utc).isoformat(), "verdict": v,
         "period": base["period"]}, indent=2, default=str))

    if args.commit:
        msg = f"macro: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC"
        for cmd in (["git", "-C", str(ROOT), "add", "memory", "reports"],
                    ["git", "-C", str(ROOT), "commit", "-m", msg],
                    ["git", "-C", str(ROOT), "push"]):
            subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
