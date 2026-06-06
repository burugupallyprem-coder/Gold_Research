"""
data/fetch_oanda.py
-------------------
Pull historical XAU/USD candles from OANDA v20 and cache them to CSV.

WHY THIS RUNS ON YOUR MACHINE (not inside the Claude sandbox):
  The build sandbox has no outbound network to OANDA. This script needs the
  live API, so you run it locally (or it runs on GitHub Actions). It writes
  plain CSVs into data/candles/, which the backtester then reads offline.

Usage:
    pip install -r requirements.txt
    python data/fetch_oanda.py                # uses .env settings
    python data/fetch_oanda.py --tf M15 --htf H4 --days 730

Output:
    data/candles/XAU_USD_M15.csv
    data/candles/XAU_USD_H4.csv
Columns: time,open,high,low,close,volume   (volume = OANDA tick volume)
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import SETTINGS  # noqa: E402

OUT_DIR = ROOT / "data" / "candles"
GRANULARITY_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "D": 86400,
}
MAX_COUNT = 5000  # OANDA per-request cap


def _headers():
    if not SETTINGS.oanda_api_key:
        sys.exit("ERROR: OANDA_API_KEY missing. Copy .env.example to .env and fill it in.")
    return {"Authorization": f"Bearer {SETTINGS.oanda_api_key}",
            "Accept-Datetime-Format": "RFC3339"}


def fetch_candles(instrument: str, granularity: str, days: int) -> list[dict]:
    """Page backward from now until `days` of history is collected."""
    base = SETTINGS.oanda_base_url
    url = f"{base}/v3/instruments/{instrument}/candles"
    step = GRANULARITY_SECONDS[granularity] * MAX_COUNT
    start = datetime.now(timezone.utc) - timedelta(days=days)
    now = datetime.now(timezone.utc)

    rows: list[dict] = []
    cursor = start
    session = requests.Session()
    while cursor < now:
        to = min(cursor + timedelta(seconds=step), now)
        params = {
            "granularity": granularity,
            "from": cursor.isoformat().replace("+00:00", "Z"),
            "to": to.isoformat().replace("+00:00", "Z"),
            "price": "M",            # midpoint candles
            "smooth": "false",
        }
        r = session.get(url, headers=_headers(), params=params, timeout=30)
        if r.status_code != 200:
            print(f"  ! {r.status_code} {r.text[:200]}")
            if r.status_code in (401, 403):
                sys.exit("Auth failed — check OANDA_API_KEY / OANDA_ENV.")
            time.sleep(2)
            cursor = to
            continue
        for c in r.json().get("candles", []):
            if not c.get("complete", False):
                continue
            m = c["mid"]
            rows.append({
                "time": c["time"],
                "open": float(m["o"]), "high": float(m["h"]),
                "low": float(m["l"]), "close": float(m["c"]),
                "volume": int(c.get("volume", 0)),
            })
        print(f"  {instrument} {granularity}: {cursor.date()} -> {to.date()}  ({len(rows)} bars)")
        cursor = to
        time.sleep(0.15)  # be gentle on the API
    # de-dup + sort
    seen, dedup = set(), []
    for row in sorted(rows, key=lambda x: x["time"]):
        if row["time"] in seen:
            continue
        seen.add(row["time"])
        dedup.append(row)
    return dedup


def write_csv(rows: list[dict], path: Path) -> None:
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["time", "open", "high", "low", "close", "volume"])
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {len(rows)} rows -> {path.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", default=SETTINGS.instrument)
    ap.add_argument("--tf", default=SETTINGS.entry_tf)
    ap.add_argument("--htf", default=SETTINGS.htf_tf)
    ap.add_argument("--days", type=int, default=SETTINGS.history_days)
    args = ap.parse_args()

    print(f"OANDA {SETTINGS.oanda_env} | {args.instrument} | {args.days} days")
    for gran in (args.tf, args.htf):
        rows = fetch_candles(args.instrument, gran, args.days)
        if not rows:
            print(f"  WARNING: no candles for {gran}")
            continue
        write_csv(rows, OUT_DIR / f"{args.instrument}_{gran}.csv")
    print("Done. Now run:  python backtest/run_backtest.py")


if __name__ == "__main__":
    main()
