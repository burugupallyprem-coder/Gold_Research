"""
learning/emailer.py
-------------------
Tiny Gmail SMTP sender for self-learning WARNINGS, reusing the same Gmail App
Password secrets as the Quant Coach. Used to email the owner a proposed change
so a human can approve it. The loop never emails an *applied* change without the
human running the manual apply step.

Env (already set as GitHub Secrets for the coach):
  GMAIL_ADDRESS, GMAIL_APP_PASSWORD, COACH_TO_EMAIL (optional)
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()
TO_EMAIL = os.getenv("COACH_TO_EMAIL", GMAIL_ADDRESS or "").strip()


def send_email(subject: str, body: str) -> bool:
    """Send a plain-text email. Returns True on success; never raises."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print(f"[email:dry] {subject}\n\n{body}\n")
        return False
    msg = EmailMessage()
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = TO_EMAIL or GMAIL_ADDRESS
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
            s.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            s.send_message(msg)
        print(f"Emailed: {subject} -> {TO_EMAIL or GMAIL_ADDRESS}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[email:error] {exc}")
        return False
