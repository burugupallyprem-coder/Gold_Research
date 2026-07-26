"""
ops/run_once.py — idempotent "run this slot at most once" guard.

Why this exists: GitHub Actions cron is best-effort and frequently late or dropped.
The fix is to schedule EACH job with several redundant, staggered triggers so at
least one lands near the target time — but then the job must not run multiple times
per intended slot (double emails, double Slack posts, double streak counts).

This wrapper makes redundant triggers safe:
  * It derives a SLOT ID for the current run (date- or week-based).
  * If that slot is already recorded done in memory/run_slots.json, it SKIPS
    (exit 0, command not run).
  * Otherwise it runs the command. On success it records the slot done. On failure
    it does NOT record the slot, so the next staggered trigger retries it.

So: the first trigger that succeeds does the work; the rest no-op; a failure is
automatically retried by a later trigger. "Even if one fails, the other works."

Usage:
  python ops/run_once.py --slot paper --period paper-day -- python paper_trader.py
  python ops/run_once.py --slot coach-lesson --period date -- python quant_coach/coach_email.py
  python ops/run_once.py --slot research --period week -- python research_lab.py --commit

--period:
  date        -> one slot per UTC calendar day       (daily jobs that don't cross midnight)
  paper-day   -> one slot per trading day, anchored at (now-6h) so a 22:00–06:00 UTC
                 window (incl. post-midnight backups) maps to ONE slot
  week        -> one slot per ISO week                (weekly jobs)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "memory" / "run_slots.json"
KEEP = 300  # prune to the most recent N slots


def slot_id(name: str, period: str) -> str:
    now = datetime.now(timezone.utc)
    if period == "date":
        return f"{name}:{now:%Y-%m-%d}"
    if period == "paper-day":
        d = now - timedelta(hours=6)          # 18:00 UTC..06:00 UTC -> same label
        return f"{name}:{d:%Y-%m-%d}"
    if period == "week":
        return f"{name}:{now:%G-W%V}"
    raise SystemExit(f"unknown --period {period!r}")


def load() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save(data: dict) -> None:
    if len(data) > KEEP:
        data = {k: data[k] for k in list(data)[-KEEP:]}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", required=True)
    ap.add_argument("--period", required=True)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        raise SystemExit("no command after --")

    sid = slot_id(args.slot, args.period)
    data = load()
    if data.get(sid) == "done":
        print(f"[run_once] slot '{sid}' already completed — skipping (redundant trigger).")
        return 0

    print(f"[run_once] slot '{sid}' not yet done — running: {' '.join(cmd)}")
    rc = subprocess.run(cmd).returncode
    if rc == 0:
        data[sid] = "done"
        save(data)
        print(f"[run_once] slot '{sid}' completed and recorded.")
    else:
        print(f"[run_once] command FAILED (rc={rc}); slot '{sid}' NOT recorded — "
              f"a later staggered trigger will retry it.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
