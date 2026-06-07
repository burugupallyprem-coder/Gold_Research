"""
learning/proposals.py
---------------------
Shared HUMAN-IN-THE-LOOP proposal store. Nothing in the trading system changes
strategy or risk on its own. Both the live monitor and the research lab write
*proposals* here; a human applies them later via apply_change.py (a manual,
human-triggered GitHub Action). This is the safety gate the owner asked for.

File: memory/pending_change.json
  {
    "pending":  [ {id, created, source, type, reason, details, status} ],
    "history":  [ ...applied / dismissed proposals... ],
    "updated":  iso
  }

Proposal types:
  "promote"  details={"name":..., "params":{...}}   change the champion strategy
  "derisk"   details={"target_vol": 0.05}           shrink position sizing
  "halt"     details={}                             stand down (soft kill switch)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PENDING_FILE = ROOT / "memory" / "pending_change.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load() -> dict:
    if PENDING_FILE.exists():
        try:
            d = json.loads(PENDING_FILE.read_text())
            d.setdefault("pending", [])
            d.setdefault("history", [])
            return d
        except Exception:  # noqa: BLE001
            pass
    return {"pending": [], "history": [], "updated": _now()}


def save(d: dict) -> None:
    d["updated"] = _now()
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDING_FILE.write_text(json.dumps(d, indent=2, default=str))


def add_proposal(source: str, ptype: str, reason: str, details: dict) -> dict | None:
    """Add a proposal unless an identical (source, type) one is already pending."""
    d = load()
    for p in d["pending"]:
        if p["source"] == source and p["type"] == ptype:
            return None  # already pending — don't spam the inbox
    proposal = {
        "id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "created": _now(),
        "source": source,
        "type": ptype,
        "reason": reason,
        "details": details or {},
        "status": "pending",
    }
    d["pending"].append(proposal)
    save(d)
    return proposal


def list_pending() -> list[dict]:
    return load()["pending"]
