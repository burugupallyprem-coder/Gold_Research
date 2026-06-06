"""
strategy/calendar_events.py
---------------------------
High-impact US macro event calendar for the pre-trade stand-down. On these ET
dates the strategy does not take new trades (mirrors what desks do around FOMC,
CPI, and NFP). This is the ROBUST, backtestable version of the live news gate:
fixed dates instead of fragile keyword sentiment.

NFP is rule-based (first Friday of each month). FOMC decision days and CPI
release days are hardcoded lists — VERIFY/UPDATE these against the official
calendars (federalreserve.gov, bls.gov) as new dates are published; wrong dates
only mildly affect the backtest (trade/skip one day either way).
"""

from __future__ import annotations

from datetime import date

# FOMC decision days (rate announcements). Approximate; verify each year.
FOMC = {
    # 2024
    (2024, 1, 31), (2024, 3, 20), (2024, 5, 1), (2024, 6, 12),
    (2024, 7, 31), (2024, 9, 18), (2024, 11, 7), (2024, 12, 18),
    # 2025
    (2025, 1, 29), (2025, 3, 19), (2025, 5, 7), (2025, 6, 18),
    (2025, 7, 30), (2025, 9, 17), (2025, 10, 29), (2025, 12, 10),
    # 2026 (projected; verify)
    (2026, 1, 28), (2026, 3, 18), (2026, 4, 29), (2026, 6, 17),
    (2026, 7, 29), (2026, 9, 16), (2026, 10, 28), (2026, 12, 9),
}

# CPI release days (BLS). Approximate; verify.
CPI = {
    (2024, 1, 11), (2024, 2, 13), (2024, 3, 12), (2024, 4, 10),
    (2024, 5, 15), (2024, 6, 12), (2024, 7, 11), (2024, 8, 14),
    (2024, 9, 11), (2024, 10, 10), (2024, 11, 13), (2024, 12, 11),
    (2025, 1, 15), (2025, 2, 12), (2025, 3, 12), (2025, 4, 10),
    (2025, 5, 13), (2025, 6, 11), (2025, 7, 15), (2025, 8, 12),
    (2025, 9, 11), (2025, 10, 15), (2025, 11, 13), (2025, 12, 10),
    (2026, 1, 13), (2026, 2, 11), (2026, 3, 11), (2026, 4, 10),
    (2026, 5, 12), (2026, 6, 10), (2026, 7, 14), (2026, 8, 12),
}


def _is_nfp(d: date) -> bool:
    """Non-farm payrolls: first Friday of the month."""
    return d.weekday() == 4 and d.day <= 7


def is_event_day(d: date) -> bool:
    key = (d.year, d.month, d.day)
    return key in FOMC or key in CPI or _is_nfp(d)


def event_label(d: date) -> str:
    key = (d.year, d.month, d.day)
    tags = []
    if key in FOMC:
        tags.append("FOMC")
    if key in CPI:
        tags.append("CPI")
    if _is_nfp(d):
        tags.append("NFP")
    return "+".join(tags) if tags else ""
