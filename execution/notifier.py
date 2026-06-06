"""
execution/notifier.py
---------------------
Slack notifier (Web API, bot token) — same pattern as the Alpaca bot's
notifier so the cloud workflow can post autonomously. Errors are swallowed as
warnings so a slow/failed Slack call never kills a backtest run. If no token is
configured it prints to stdout instead (handy for local/dry runs).

Event tags (mirrors the Alpaca bot):
  [START]   routine kickoff
  [BACKTEST] metrics summary
  [WALKFWD] walk-forward summary
  [ROUTINE] weekly review
  [INFO]    non-fatal info
  [ERROR]   exception caught
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import SETTINGS  # noqa: E402

import os  # noqa: E402

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
    post(f"[START] {SETTINGS.instrument} backtest bot — routine: {routine}")


def backtest_summary(metrics: dict, tag: str):
    m = metrics
    if m.get("trades", 0) == 0:
        post(f"[BACKTEST] ({tag}) no trades generated.")
        return
    post(
        f"[BACKTEST] ({tag}) trades={m['trades']} | win={m['win_rate']*100:.1f}% | "
        f"PF={m['profit_factor']} | exp={m['expectancy_R']}R | "
        f"DD={m['max_drawdown_pct']}% | ret={m['total_return_pct']}% | "
        f"Sharpe~{m['sharpe_annual_est']}")


def walkforward_summary(text: str):
    post(f"[WALKFWD] {text}")


def weekly(text: str):
    post(f"[ROUTINE] Weekly review\n{text}")


def info(text: str):
    post(f"[INFO] {text}")


def error(text: str):
    post(f"[ERROR] {text}")
