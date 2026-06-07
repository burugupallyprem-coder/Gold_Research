"""
coach_email.py
==============
EMAIL version of the Quant Coach (no Slack). Sends one detailed lesson in the
morning and the matching interview drill in the evening, by email, via Gmail
SMTP. Designed to run on GitHub Actions — fully in the cloud, so it works even
with your laptop closed.

It reuses the 15-day curriculum and progress tracking from quant_coach.py;
nothing here touches Slack.

Environment (set as GitHub Secrets):
  GMAIL_ADDRESS        the Gmail address you send FROM (e.g. burugupallyprem@gmail.com)
  GMAIL_APP_PASSWORD   a 16-character Google App Password (NOT your normal password)
  COACH_TO_EMAIL       optional; where to send. Defaults to GMAIL_ADDRESS.

Time: on GitHub Actions the clock is UTC. The workflow fires at 12:00 UTC
(~8 AM US Eastern) for the lesson and 00:00 UTC (~8 PM Eastern) for the drill.
"""

from __future__ import annotations

import os
import smtplib
import ssl
import sys
from datetime import datetime, date, timezone
from email.message import EmailMessage
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

# Curriculum + state come from the existing coach module (no Slack is called).
from quant_coach import DAILY, load_state, save_state  # noqa: E402

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()
TO_EMAIL = os.getenv("COACH_TO_EMAIL", GMAIL_ADDRESS or "burugupallyprem@gmail.com").strip()


def to_plain(text: str) -> str:
    """Strip Slack markdown markers (*bold*, _italic_) for a clean email body."""
    return text.replace("*", "").replace("_", "")


def send_email(subject: str, body: str) -> bool:
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("[email:dry] GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set — printing instead.\n")
        print(f"SUBJECT: {subject}\n\n{body}\n")
        return False
    msg = EmailMessage()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = TO_EMAIL
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
            s.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            s.send_message(msg)
        print(f"Emailed: {subject} -> {TO_EMAIL}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[email:error] {exc}")
        return False


def main() -> int:
    # Cloud runs in UTC: 12:00 UTC -> morning lesson; 00:00 UTC -> evening drill.
    hour = datetime.now(timezone.utc).hour
    morning = 6 <= hour < 18

    state = load_state()
    today = date.today().isoformat()
    if today not in state.get("streak_days", []):
        state.setdefault("streak_days", []).append(today)
        state["streak_days"] = state["streak_days"][-365:]
    state["total_sessions"] = state.get("total_sessions", 0) + 1

    day = state.get("day_index", 0) % len(DAILY)
    entry = DAILY[day]
    streak = len(set(state.get("streak_days", [])))

    if morning:
        subject = f"Quant Coach — Day {day + 1} of {len(DAILY)}: {entry['title']}"
        body = (to_plain(entry["lesson"]) +
                f"\n\n(Daily streak: {streak} days. Tonight: the matching interview drill.)")
    else:
        subject = f"Quant Coach — Day {day + 1} Drill: {entry['title']}"
        body = to_plain(entry["drill"])
        state["day_index"] = day + 1     # advance after the evening drill

    save_state(state)
    return 0 if send_email(subject, body) else 1


if __name__ == "__main__":
    sys.exit(main())
