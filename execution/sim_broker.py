"""
execution/sim_broker.py
-----------------------
Simulated paper broker. Same interface as OandaBroker (nav, position_units,
market_order) but fills orders internally at the real OANDA price the trader
passes in, charging the same spread/slippage costs the backtest assumes.

Why this exists: OANDA US-division accounts cannot trade metals (every
XAU_USD order is rejected with HTTP 400), so live paper trading runs against
this simulator instead. Prices are real; only the fill is simulated.

State lives in memory/sim_account.json (committed to git by the workflow),
so the account survives across daily GitHub Actions runs:

    {"cash": 100000.0, "positions": {"XAU_USD": 11}, "fills": [...]}

Honesty rules: fills cost half-spread + slippage per unit (from config), NAV
is marked to the latest real close. No hindsight, no free fills.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import SETTINGS  # noqa: E402

STATE_FILE = ROOT / "memory" / "sim_account.json"
MAX_FILLS_KEPT = 500  # keep the json small; full history is in git anyway


class SimBroker:
    """Drop-in replacement for OandaBroker, filling orders in simulation."""

    dry = False  # paper_trader checks this to label the run

    def __init__(self, price: float, instrument: str | None = None,
                 state_file: Path = STATE_FILE):
        if price <= 0:
            raise ValueError(f"SimBroker needs a positive mark price, got {price}")
        self.price = float(price)
        self.instrument = instrument or SETTINGS.instrument
        self.state_file = state_file
        self.actions: list[str] = []
        self.state = self._load()

    # -- state ---------------------------------------------------------------
    def _load(self) -> dict:
        if self.state_file.exists():
            try:
                s = json.loads(self.state_file.read_text())
                if "cash" in s and "positions" in s:
                    return s
            except Exception:  # noqa: BLE001
                pass
        return {"cash": float(SETTINGS.starting_equity), "positions": {}, "fills": []}

    def _save(self) -> None:
        self.state["fills"] = self.state.get("fills", [])[-MAX_FILLS_KEPT:]
        self.state_file.parent.mkdir(exist_ok=True)
        self.state_file.write_text(json.dumps(self.state, indent=2))

    # -- broker interface ------------------------------------------------------
    def nav(self) -> float:
        units = float(self.state["positions"].get(self.instrument, 0))
        return float(self.state["cash"]) + units * self.price

    def position_units(self, instrument: str) -> float:
        return float(self.state["positions"].get(instrument, 0))

    def market_order(self, instrument: str, units: int) -> dict:
        if units == 0:
            return {"status": "skip", "reason": "zero units"}
        # Same cost model as the backtest: pay half the spread plus slippage,
        # in the direction of the trade.
        cost_per_unit = SETTINGS.spread_usd / 2 + SETTINGS.slippage_usd
        fill = self.price + (cost_per_unit if units > 0 else -cost_per_unit)
        self.state["cash"] = float(self.state["cash"]) - units * fill \
            - SETTINGS.commission_per_trade
        pos = self.state["positions"]
        pos[instrument] = int(pos.get(instrument, 0)) + int(units)
        record = {"ts": datetime.now(timezone.utc).isoformat(),
                  "instrument": instrument, "units": int(units),
                  "fill_price": round(fill, 4), "mark_price": self.price,
                  "cash_after": round(self.state["cash"], 2),
                  "units_after": pos[instrument]}
        self.state.setdefault("fills", []).append(record)
        self._save()
        self.actions.append(f"SIM fill {instrument} {units:+d} @ {fill:.2f}")
        return {"status": "sim_filled", **record}
