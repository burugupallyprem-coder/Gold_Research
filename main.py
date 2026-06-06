"""
main.py
-------
Orchestrator for the OANDA XAU/USD backtesting bot. Mirrors the Alpaca bot's
shape (routines + memory + Slack + git commit) but the "work" is backtesting,
not live trading.

Routines:
    backtest        Run the full-history backtest, write reports + memory,
                    post a Slack summary. (The recurring "keep the board fresh"
                    job — run after each data refresh.)
    walkforward     Run walk-forward analysis, write report, post summary.
    weekly_review   Friday: walk-forward + per-setup breakdown appended to
                    memory/lessons.md, post summary.
    all             backtest + walkforward + weekly_review.

CLI:
    python main.py --routine backtest
    python main.py --routine weekly_review --commit

The kill switch is a file named STOP at repo root (gitignored). If present,
every routine exits immediately.
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

from config import SETTINGS                                       # noqa: E402
from strategy.strategy import StrategyConfig                      # noqa: E402
from strategy.risk import RiskConfig                              # noqa: E402
from backtest.core import BacktestConfig, CostModel               # noqa: E402
from backtest.engine_final import run_backtest_fast              # noqa: E402
from backtest.metrics import compute_metrics, trades_to_frame     # noqa: E402
from backtest.wf import load as wf_load                           # noqa: E402
from execution import notifier                                    # noqa: E402

CANDLES = ROOT / "data" / "candles"
REPORTS = ROOT / "reports"
MEMORY = ROOT / "memory"
STOP_FILE = ROOT / "STOP"


def _load(tf):
    p = CANDLES / f"{SETTINGS.instrument}_{tf}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["time"]).set_index("time").sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


def _full_backtest():
    df, htf = _load(SETTINGS.entry_tf), _load(SETTINGS.htf_tf)
    if df is None or htf is None:
        return None, None
    sc = StrategyConfig()
    rc = RiskConfig()
    bt = BacktestConfig(starting_equity=SETTINGS.starting_equity,
                        confidence_threshold=SETTINGS.confidence_threshold)
    cost = CostModel(spread_usd=SETTINGS.spread_usd, slippage_usd=SETTINGS.slippage_usd,
                     commission_per_trade=SETTINGS.commission_per_trade)
    res = run_backtest_fast(df, htf, sc, rc, bt, cost=cost)
    metrics = compute_metrics(res.trades, res.equity_curve, bt.starting_equity)
    return res, metrics


def routine_backtest():
    notifier.start("backtest")
    res, metrics = _full_backtest()
    if res is None:
        notifier.info("No candles found. Run data/fetch_oanda.py first.")
        return
    REPORTS.mkdir(exist_ok=True)
    MEMORY.mkdir(exist_ok=True)
    trades_to_frame(res.trades).to_csv(REPORTS / "blotter_latest.csv", index=False)
    res.equity_curve.to_csv(REPORTS / "equity_latest.csv")
    snapshot = {"updated": datetime.now(timezone.utc).isoformat(),
                "config": res.config, "metrics": metrics}
    (MEMORY / "results.json").write_text(json.dumps(snapshot, indent=2, default=str))
    (REPORTS / "summary_latest.json").write_text(json.dumps(snapshot, indent=2, default=str))
    notifier.backtest_summary(metrics, "full-history")
    print(json.dumps(metrics, indent=2, default=str))


def routine_walkforward():
    notifier.start("walkforward")
    df = _load(SETTINGS.entry_tf)
    if df is None:
        notifier.info("No candles found. Run data/fetch_oanda.py first.")
        return
    # Delegate to the wf module via subprocess to reuse its CLI exactly.
    r = subprocess.run([sys.executable, str(ROOT / "backtest" / "wf.py"),
                        "--folds", "5", "--train", "4000", "--test", "1000"],
                       capture_output=True, text=True)
    print(r.stdout[-2000:])
    wf_path = REPORTS / "walkforward.json"
    if wf_path.exists():
        agg = json.loads(wf_path.read_text()).get("aggregate_out_of_sample", {})
        notifier.walkforward_summary(
            f"OOS trades={agg.get('trades')} PF={agg.get('profit_factor')} "
            f"exp={agg.get('expectancy_R')}R win={agg.get('win_rate')}")


def routine_weekly_review():
    notifier.start("weekly_review")
    res, metrics = _full_backtest()
    if res is None:
        notifier.info("No candles found. Run data/fetch_oanda.py first.")
        return
    MEMORY.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    by = metrics.get("by_setup", {})
    lines = [f"\n## Weekly review — {stamp}",
             f"- Trades: {metrics.get('trades')}, win rate {metrics.get('win_rate')}, "
             f"PF {metrics.get('profit_factor')}, expectancy {metrics.get('expectancy_R')}R",
             f"- Max drawdown {metrics.get('max_drawdown_pct')}%, "
             f"longest losing streak {metrics.get('max_losing_streak')}",
             "- By setup:"]
    for k, v in by.items():
        lines.append(f"    - {k}: n={v['n']} win={v['win_rate']} avgR={v['avg_r']} pnl={v['pnl']}")
    lessons = MEMORY / "lessons.md"
    prev = lessons.read_text() if lessons.exists() else "# Lessons — weekly reviews append here\n"
    lessons.write_text(prev + "\n".join(lines) + "\n")
    notifier.weekly("\n".join(lines))
    print("\n".join(lines))


def git_commit(message: str):
    try:
        subprocess.run(["git", "-C", str(ROOT), "add", "memory", "reports"], check=False)
        subprocess.run(["git", "-C", str(ROOT), "commit", "-m", message], check=False)
        subprocess.run(["git", "-C", str(ROOT), "push"], check=False)
    except Exception as e:  # noqa: BLE001
        print(f"[git:warn] {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--routine", default="backtest",
                    choices=["backtest", "walkforward", "weekly_review", "all"])
    ap.add_argument("--commit", action="store_true", help="git add/commit/push memory + reports")
    args = ap.parse_args()

    if STOP_FILE.exists():
        print("STOP file present — exiting.")
        notifier.info("STOP file present — routine skipped.")
        return

    try:
        if args.routine in ("backtest", "all"):
            routine_backtest()
        if args.routine in ("walkforward", "all"):
            routine_walkforward()
        if args.routine in ("weekly_review", "all"):
            routine_weekly_review()
    except Exception as e:  # noqa: BLE001
        notifier.error(f"{args.routine} failed: {e}")
        raise

    if args.commit:
        git_commit(f"{args.routine}: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")


if __name__ == "__main__":
    main()
