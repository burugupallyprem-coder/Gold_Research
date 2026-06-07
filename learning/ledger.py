"""
learning/ledger.py
------------------
Records the paper bot's OWN positions each day, with the decision features that
produced them, and turns that log into a daily mark-to-market P&L series.

This is the raw material the self-learning loop reads: the bot literally writes
down what it did and why, so a later job can judge how it actually performed on
the live paper account (not just in backtests).

File (committed to git, so memory survives stateless cloud runs):
  memory/trade_ledger.json   append-only list of daily position snapshots
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER_FILE = ROOT / "memory" / "trade_ledger.json"


def _clean(x):
    """Coerce to a JSON-safe float, turning NaN/inf/bad values into None."""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):  # NaN or inf
        return None
    return f


def load_ledger() -> list[dict]:
    if LEDGER_FILE.exists():
        try:
            return json.loads(LEDGER_FILE.read_text())
        except Exception:  # noqa: BLE001
            return []
    return []


def append_entry(*, instrument, price, nav, weight, prev_units, delta,
                 held_units, champion, mode, features) -> dict:
    """Append one daily position snapshot and return it. Never raises."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "instrument": instrument,
        "price": _clean(price),
        "nav": _clean(nav),
        "weight": _clean(weight),
        "prev_units": _clean(prev_units),
        "delta": _clean(delta),
        "held_units": _clean(held_units),
        "champion": champion,
        "mode": mode,
        "features": {k: _clean(v) for k, v in (features or {}).items()},
    }
    data = load_ledger()
    data.append(entry)
    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_FILE.write_text(json.dumps(data, indent=2))
    return entry


def build_daily_returns(ledger: list[dict] | None = None) -> list[dict]:
    """
    Convert the position log into a daily return series. The position held going
    INTO day t is marked against the price move from t-1 to t:

        pnl_t = held_units[t-1] * (price[t] - price[t-1])
        ret_t = pnl_t / nav[t-1]

    Returns a list of {date, pnl, ret, position} dicts (one per consecutive pair
    of valid rows). Honest and simple: it measures the actual paper position, not
    idealized round-trip trades.
    """
    rows = sorted(
        [r for r in (ledger if ledger is not None else load_ledger())
         if r.get("price") and r.get("nav")],
        key=lambda r: r["ts"])
    out = []
    for prev, cur in zip(rows, rows[1:]):
        held = prev.get("held_units") or 0.0
        nav = prev.get("nav") or 0.0
        if nav <= 0:
            continue
        pnl = held * (cur["price"] - prev["price"])
        out.append({"date": cur["date"], "pnl": pnl, "ret": pnl / nav,
                    "position": held})
    return out
