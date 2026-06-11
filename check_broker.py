"""
check_broker.py
---------------
Read-only OANDA practice-account diagnostic. Run on your own machine:

    python check_broker.py

Checks (no orders placed):
  1. Credentials work (account summary).
  2. XAU_USD is tradeable on this account (US-division accounts often can't
     trade metals -- that alone causes 400 rejects on every order).
  3. Current pricing status (shows if the market is halted right now).
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from config import SETTINGS  # noqa: E402

H = {"Authorization": f"Bearer {SETTINGS.oanda_api_key}"}
BASE = f"{SETTINGS.oanda_base_url}/v3/accounts/{SETTINGS.oanda_account_id}"
INST = SETTINGS.instrument


def main() -> None:
    if not SETTINGS.oanda_api_key or not SETTINGS.oanda_account_id:
        print("Missing OANDA_API_KEY / OANDA_ACCOUNT_ID in .env"); return

    # 1. Credentials / account
    r = requests.get(f"{BASE}/summary", headers=H, timeout=30)
    if not r.ok:
        print(f"[FAIL] account summary: HTTP {r.status_code} {r.text[:300]}"); return
    a = r.json()["account"]
    print(f"[OK] account {a['id']} | NAV {a['NAV']} {a['currency']} "
          f"| open positions: {a['openPositionCount']}")

    # 2. Instrument availability
    r = requests.get(f"{BASE}/instruments", headers=H,
                     params={"instruments": INST}, timeout=30)
    instruments = r.json().get("instruments", []) if r.ok else []
    if not instruments:
        print(f"[FAIL] {INST} is NOT available on this account.")
        print("       This rejects every order with 400. Likely a region "
              "restriction (e.g. US accounts can't trade metals CFDs).")
        print("       Fix: open a practice sub-account in a division that "
              "offers XAU_USD, or switch INSTRUMENT in .env.")
        return
    i = instruments[0]
    print(f"[OK] {INST} tradeable | min units {i.get('minimumTradeSize')} "
          f"| margin rate {i.get('marginRate')}")

    # 3. Live pricing / halt status
    r = requests.get(f"{BASE}/pricing", headers=H,
                     params={"instruments": INST}, timeout=30)
    if r.ok and r.json().get("prices"):
        p = r.json()["prices"][0]
        print(f"[{'OK' if p.get('tradeable') else 'HALTED'}] pricing status="
              f"{p.get('status', 'n/a')} tradeable={p.get('tradeable')} "
              f"bid={p['bids'][0]['price'] if p.get('bids') else 'n/a'}")
        if not p.get("tradeable"):
            print("       Market halted right now (gold breaks daily 5-6pm "
                  "New York; closed weekends). Orders sent now get 400 "
                  "MARKET_HALTED.")
    else:
        print(f"[WARN] pricing check failed: HTTP {r.status_code} {r.text[:200]}")


if __name__ == "__main__":
    main()
