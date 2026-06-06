"""
validate_run.py
---------------
Cloud entrypoint for the validation pack. Runs the honest tests (regime + event
gates + partial profits, cost-stress, walk-forward OOS, long/short), posts the
verdict to Slack, and writes reports/validation.json + memory/validation.json.

    python validate_run.py
    python validate_run.py --commit     # git add/commit/push reports + memory
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backtest import validate                  # noqa: E402
from execution import notifier                 # noqa: E402

MEMORY = ROOT / "memory"
STOP_FILE = ROOT / "STOP"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    if STOP_FILE.exists():
        print("STOP file present — skipping.")
        return

    notifier.start("validate")
    try:
        out = validate.run()
    except Exception as e:  # noqa: BLE001
        notifier.error(f"validate failed: {e}")
        raise

    text = validate.slack_text(out)
    notifier.post(text)
    print(text)

    MEMORY.mkdir(exist_ok=True)
    snap = {"updated": datetime.now(timezone.utc).isoformat(),
            "decision": out.get("decision"), "period": out.get("period"),
            "bars": out.get("bars")}
    (MEMORY / "validation.json").write_text(json.dumps(snap, indent=2, default=str))

    if args.commit:
        msg = f"validate: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC"
        for cmd in (["git", "-C", str(ROOT), "add", "memory", "reports"],
                    ["git", "-C", str(ROOT), "commit", "-m", msg],
                    ["git", "-C", str(ROOT), "push"]):
            subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
