"""
data/fetch_daily.py
-------------------
Fetch the inputs for the Gold Macro-Trend strategy (runs where there is real
network — your machine or GitHub Actions):

  * OANDA XAU/USD DAILY candles -> data/daily/XAU_USD_D.csv
  * FRED DFII10 (10y real yield) -> data/daily/DFII10.csv   (free, no key)

Usage:
    python data/fetch_daily.py --days 2500
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import SETTINGS  # noqa: E402

OUT = ROOT / "data" / "daily"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10"


def fetch_oanda_daily(instrument: str, days: int) -> list[dict]:
    if not SETTINGS.oanda_api_key:
        sys.exit("ERROR: OANDA_API_KEY missing.")
    url = f"{SETTINGS.oanda_base_url}/v3/instruments/{instrument}/candles"
    headers = {"Authorization": f"Bearer {SETTINGS.oanda_api_key}",
               "Accept-Datetime-Format": "RFC3339"}
    start = datetime.now(timezone.utc) - timedelta(days=days)
    now = datetime.now(timezone.utc)
    rows, cursor = [], start
    sess = requests.Session()
    step = timedelta(days=4500)            # ~5000 daily candles cap per request
    while cursor < now:
        to = min(cursor + step, now)
        params = {"granularity": "D", "price": "M",
                  "from": cursor.isoformat().replace("+00:00", "Z"),
                  "to": to.isoformat().replace("+00:00", "Z")}
        r = sess.get(url, headers=headers, params=params, timeout=30)
        if r.status_code != 200:
            print(f"  ! {r.status_code} {r.text[:160]}")
            if r.status_code in (401, 403):
                sys.exit("Auth failed — check OANDA_API_KEY.")
            cursor = to
            continue
        for c in r.json().get("candles", []):
            if not c.get("complete", False):
                continue
            m = c["mid"]
            rows.append({"time": c["time"][:10], "open": float(m["o"]),
                         "high": float(m["h"]), "low": float(m["l"]),
                         "close": float(m["c"]), "volume": int(c.get("volume", 0))})
        cursor = to
        time.sleep(0.15)
    seen, out = set(), []
    for row in sorted(rows, key=lambda x: x["time"]):
        if row["time"] in seen:
            continue
        seen.add(row["time"]); out.append(row)
    return out


def fetch_fred() -> list[dict]:
    r = requests.get(FRED_URL, timeout=30)
    r.raise_for_status()
    out = []
    for row in csv.DictReader(StringIO(r.text)):
        date = row.get("DATE") or row.get("observation_date")
        val = row.get("DFII10", ".")
        if not date or val in (".", "", None):
            continue
        try:
            out.append({"time": date, "dfii10": float(val)})
        except ValueError:
            continue
    return out


def write_csv(rows, path, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)
    print(f"  wrote {len(rows)} rows -> {path.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", default=SETTINGS.instrument)
    ap.add_argument("--days", type=int, default=2500)
    args = ap.parse_args()
    print(f"OANDA daily {args.instrument} ({args.days}d) + FRED DFII10")
    gold = fetch_oanda_daily(args.instrument, args.days)
    write_csv(gold, OUT / f"{args.instrument}_D.csv",
              ["time", "open", "high", "low", "close", "volume"])
    try:
        ry = fetch_fred()
        write_csv(ry, OUT / "DFII10.csv", ["time", "dfii10"])
    except Exception as e:  # noqa: BLE001
        print(f"  ! FRED fetch failed ({e}); strategy will run without macro filter.")
    print("Done. Now run:  python macro_run.py")


if __name__ == "__main__":
    main()
