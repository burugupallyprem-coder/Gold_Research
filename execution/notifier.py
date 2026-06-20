"""
execution/notifier.py
---------------------
Slack notifier (Web API, bot token). Errors are swallowed as warnings so a
slow/failed Slack call never kills a run. If no token is configured it prints
to stdout instead (handy for local/dry runs).

Event tags that DO post to Slack:
  [BACKTEST] metrics summary
  [WALKFWD]  walk-forward summary
  [ROUTINE]  weekly review
  [INFO]     non-fatal info
  [ERROR]    exception caught
  (plus [MACRO]/[VALIDATE]/[RESEARCH]/[PAPER]/[LEARN] posted by their modules)

NOTE: [START] kickoff messages are intentionally NOT posted to Slack anymore --
they were pure noise (one per routine run). start() now only logs locally.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import SETTINGS  # noqa: E402

SLACK_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL_ID", "C0B88CUAZPD")
TIMEOUT = 30


def post(text: str) -> bool:
    """Post to Slack. Returns True on success. Never raises."""
    if not SLACK_TOKEN:
        print(f"[slack:dry] {text}")
        return False
    try:
        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {SLACK_TOKEN}",
                     "Content-Type": "application/json; charset=utf-8"},
            json={"channel": SLACK_CHANNEL, "text": text},
            timeout=TIMEOUT)
        ok = r.json().get("ok", False)
        if not ok:
            print(f"[slack:warn] {r.text[:200]}")
        return ok
    except Exception as e:  # noqa: BLE001
        print(f"[slack:warn] {e}")
        return False


def start(routine: str):
    # [START] messages were Slack noise (one per routine run). Log locally only.
    print(f"[start] {SETTINGS.instrument} routine: {routine}")


def backtest_summary(metrics: dict, tag: str):
    m = metrics
    if m.get("trades", 0) == 0:
        post(f"[BACKTEST] ({tag}) no trades generated.")
        return

    pf = float(m.get("profit_factor", 0))
    sharpe = float(m.get("sharpe_annual_est", 0))
    win = float(m.get("win_rate", 0)) * 100

    # Plain-English verdict
    if pf >= 1.3 and sharpe >= 1.0:
        verdict = "✅ Edge is solid — strategy is performing well"
    elif pf >= 1.1:
        verdict = "⚠️ Edge is modest but positive — keep monitoring"
    else:
        verdict = "🔴 Edge is weak or gone — human review needed"

    explanation = "\n".join([
        "─" * 40,
        "📊 *What this means in plain English:*",
        f"• Win rate {win:.1f}% — that's normal for trend-following (big wins, small losses)",
        f"• Profit factor {pf:.3f} — for every $1 lost, strategy makes ${pf:.2f}  (need >1.0 to profit)",
        f"• Sharpe {sharpe:.2f} — risk-adjusted return  (>1.0 is good, >1.5 is strong)",
        f"• {verdict}",
        "─" * 40,
    ])

    post(
        f"[BACKTEST] ({tag}) trades={m['trades']} | win={win:.1f}% | "
        f"PF={pf} | exp={m['expectancy_R']}R | "
        f"DD={m['max_drawdown_pct']}% | ret={m['total_return_pct']}% | "
        f"Sharpe~{sharpe}"
        f"\n\n{explanation}"
    )


def walkforward_summary(text: str):
    post(f"[WALKFWD] {text}")


def weekly(text: str):
    post(f"[ROUTINE] Weekly review\n{text}")


def info(text: str):
    post(f"[INFO] {text}")


def error(text: str):
    post(f"[ERROR] {text}")
