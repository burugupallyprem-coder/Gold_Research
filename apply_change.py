"""
apply_change.py
---------------
The HUMAN-IN-THE-LOOP apply step. The self-learning loop only ever *proposes*
changes (see learning/monitor.py and research_lab.py). This script is the only
thing that actually applies them — and it is run manually, by you, via the
'oanda-apply-change' GitHub Action (workflow_dispatch).

  python apply_change.py            # apply ALL pending proposals (= you approve)
  python apply_change.py --list     # just show what is pending
  python apply_change.py --dismiss  # discard all pending without applying

What "apply" does per proposal type:
  promote -> rewrites research/champion.json so the paper trader uses the new strategy
  derisk  -> writes memory/guards.json with a smaller target-vol override
  halt    -> writes memory/guards.json with halt=true (paper trader stands down)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from execution import notifier            # noqa: E402
from learning import proposals            # noqa: E402

RESEARCH = ROOT / "research"
MEM = ROOT / "memory"
CHAMPION_FILE = RESEARCH / "champion.json"
GUARDS_FILE = MEM / "guards.json"


def _load_guards() -> dict:
    if GUARDS_FILE.exists():
        try:
            return json.loads(GUARDS_FILE.read_text())
        except Exception:  # noqa: BLE001
            pass
    return {"target_vol_override": None, "halt": False}


def _save_guards(g: dict):
    g["updated"] = datetime.now(timezone.utc).isoformat()
    MEM.mkdir(parents=True, exist_ok=True)
    GUARDS_FILE.write_text(json.dumps(g, indent=2))


def _apply_one(p: dict) -> str:
    t = p["type"]
    if t == "promote":
        champ = json.loads(CHAMPION_FILE.read_text()) if CHAMPION_FILE.exists() else {}
        champ["champion"] = {"name": p["details"]["name"],
                             "params": p["details"].get("params", {})}
        champ["pending"] = None
        champ.setdefault("history", []).append(
            {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
             "action": "promote", "to": p["details"]["name"], "approved_by": "human"})
        CHAMPION_FILE.write_text(json.dumps(champ, indent=2, default=str))
        return f"Promoted champion -> {p['details']['name']}"
    if t == "derisk":
        g = _load_guards()
        g["target_vol_override"] = float(p["details"].get("target_vol", 0.05))
        g["halt"] = False
        _save_guards(g)
        return f"Set target-vol override -> {g['target_vol_override']:g}"
    if t == "halt":
        g = _load_guards()
        g["halt"] = True
        _save_guards(g)
        return "Halt engaged — paper trader will stand down until cleared."
    return f"Unknown proposal type '{t}' — skipped."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dismiss", action="store_true")
    args = ap.parse_args()

    d = proposals.load()
    pend = d["pending"]

    if args.list:
        print(json.dumps(pend, indent=2))
        return
    if not pend:
        print("No pending proposals.")
        notifier.info("[APPLY] No pending proposals to apply.")
        return

    results = []
    for p in pend:
        if args.dismiss:
            p["status"] = "dismissed"
            results.append(f"dismissed: {p['type']}")
        else:
            results.append(_apply_one(p))
            p["status"] = "applied"
        p["resolved"] = datetime.now(timezone.utc).isoformat()
        d["history"].append(p)
    d["pending"] = []
    proposals.save(d)

    head = "[APPLY] Dismissed (no change):" if args.dismiss else "[APPLY] Applied by human:"
    text = head + "\n" + "\n".join(f"  - {r}" for r in results)
    notifier.post(text)
    print(text)


if __name__ == "__main__":
    main()
