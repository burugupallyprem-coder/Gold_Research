"""
tests/test_paper_trader.py
--------------------------
Unit tests for the pure order-decision logic (no network). Run:
    python tests/test_paper_trader.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from paper_trader import decide_order

results = []


def check(name, cond):
    results.append(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")


# NAV 100k, price 2000, weight +1.0, flat -> target = 100000/2000 = 50 units long
o = decide_order(1.0, 2000.0, 100_000, 0, max_leverage=1.0)
check("long target units = 50", o["target_units"] == 50)
check("long order delta = 50", o["delta"] == 50)

# Notional cap: weight 3.0 but max_leverage 1.0 -> capped at 1x NAV = 50 units
o = decide_order(3.0, 2000.0, 100_000, 0, max_leverage=1.0)
check("leverage capped at 1x (50 units, not 150)", o["target_units"] == 50)

# Short target: weight -1.0 -> -50 units
o = decide_order(-1.0, 2000.0, 100_000, 0, max_leverage=1.0)
check("short target units = -50", o["target_units"] == -50)

# Reconcile from an existing position: already long 50, target 50 -> no trade
o = decide_order(1.0, 2000.0, 100_000, 50, max_leverage=1.0)
check("already at target -> no order", o["delta"] == 0)

# Reconcile: long 50 but target now flat (weight 0) -> sell 50
o = decide_order(0.0, 2000.0, 100_000, 50, max_leverage=1.0)
check("flatten -> delta -50", o["delta"] == -50)

# Flip: short 50 -> target long 50 -> buy 100
o = decide_order(1.0, 2000.0, 100_000, -50, max_leverage=1.0)
check("flip short->long -> delta +100", o["delta"] == 100)

# Within tolerance: target 50 vs current 50 (tiny weight change) -> no churn
o = decide_order(1.001, 2000.0, 100_000, 50, max_leverage=1.0, min_trade=1)
check("sub-unit change -> no churn", o["delta"] == 0)

# Bad inputs guarded
o = decide_order(1.0, 0.0, 100_000, 0)
check("bad price guarded", o["delta"] == 0)


if __name__ == "__main__":
    n, ok = len(results), sum(results)
    print(f"\n{ok}/{n} checks passed")
    sys.exit(0 if ok == n else 1)
