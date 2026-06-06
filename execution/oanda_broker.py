"""
execution/oanda_broker.py
-------------------------
Minimal OANDA v20 broker client for PAPER (practice) trading only.

Capabilities used by the paper trader:
  * nav()                         -> account Net Asset Value (float)
  * position_units(instrument)    -> current net units (long +, short -)
  * market_order(instrument, u)   -> submit a market order for `u` signed units

In DRY mode (no account id, or dry=True) it performs no writes — market_order
just records the intended action. All network errors raise, so the trader can
catch them and stand down rather than act on bad data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import SETTINGS  # noqa: E402


class OandaBroker:
    def __init__(self, dry: bool | None = None):
        self.base = SETTINGS.oanda_base_url
        self.token = SETTINGS.oanda_api_key
        self.account = SETTINGS.oanda_account_id
        # DRY if explicitly requested, or if we lack credentials to trade
        self.dry = (dry if dry is not None
                    else (not self.token or not self.account))
        self.session = requests.Session()
        self.actions: list[str] = []

    @property
    def _headers(self):
        return {"Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"}

    def _url(self, path: str) -> str:
        return f"{self.base}/v3/accounts/{self.account}{path}"

    def nav(self) -> float:
        if self.dry:
            return float(SETTINGS.starting_equity)
        r = self.session.get(self._url("/summary"), headers=self._headers, timeout=30)
        r.raise_for_status()
        return float(r.json()["account"]["NAV"])

    def position_units(self, instrument: str) -> float:
        if self.dry:
            return 0.0
        r = self.session.get(self._url(f"/positions/{instrument}"),
                             headers=self._headers, timeout=30)
        if r.status_code == 404:
            return 0.0
        r.raise_for_status()
        pos = r.json().get("position", {})
        long_u = float(pos.get("long", {}).get("units", 0) or 0)
        short_u = float(pos.get("short", {}).get("units", 0) or 0)
        return long_u + short_u            # short units are negative

    def market_order(self, instrument: str, units: int) -> dict:
        if units == 0:
            return {"status": "skip", "reason": "zero units"}
        if self.dry:
            self.actions.append(f"DRY market order {instrument} {units:+d} units")
            return {"status": "dry", "instrument": instrument, "units": units}
        body = {"order": {"type": "MARKET", "instrument": instrument,
                          "units": str(int(units)),
                          "timeInForce": "FOK", "positionFill": "DEFAULT"}}
        r = self.session.post(self._url("/orders"), headers=self._headers,
                              json=body, timeout=30)
        r.raise_for_status()
        return r.json()
