"""
paper_trader.py
---------------
PAPER trading loop for the validated Gold Macro-Trend champion. Runs once per
session: compute the champion's target position, reconcile it against the
current OANDA practice position, and submit the difference as a market order.

This is the ONLY component that places orders -- and only on the OANDA *practice*
account. It is locked to the validated champion in research/champion.json; it
will never trade the research lab's unconfirmed challengers.

Safety rails (all enforced before any order):
  * STOP file at repo root  -> stand down.
  * Stale data guard        -> if the latest daily bar is older than
                               MAX_BAR_AGE_DAYS, stand down (no trading on stale data).
  * Notional cap            -> position notional capped at PAPER_MAX_LEVERAGE x NAV
                               (default 1x -- no leverage on paper).
  * Halt guard              -> human-approved guards.json can pause trading.
  * DRY_RUN / missing creds -> simulate and log instead of placing orders.
  * Any broker/API error    -> caught, posted to Slack, no action taken.

    python paper_trader.py
    DRY_RUN=true python paper_trader.py
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import SETTINGS                                  # noqa: E402
from strategy.macro_trend import MacroConfig, compute_weights  # noqa: E402
from execution import notifier                               # noqa: E402
from execution.oanda_broker import OandaBroker               # noqa: E402
from learning import ledger                                  # noqa: E402

DAILY = ROOT / "data" / "daily"
RESEARCH = ROOT / "research"
REPORTS = ROOT / "reports"
STOP_FILE = ROOT / "STOP"
GUARDS_FILE = ROOT / "memory" / "guards.json"

MAX_BAR_AGE_DAYS = int(os.getenv("MAX_BAR_AGE_DAYS", "5"))
PAPER_MAX_LEVERAGE = float(os.getenv("PAPER_MAX_LEVERAGE", "1.0"))
MIN_TRADE_UNITS = int(os.getenv("MIN_TRADE_UNITS", "1"))
BASELINE = {"ema_fast": 50, "ema_slow": 200, "mom_lookback": 252,
            "ry_mom_lookback": 60, "target_vol": 0.10, "use_macro": True}


def decide_order(weight: float, price: float, nav: float, current_units: float,
                 max_leverage: float = 1.0, min_trade: int = 1) -> dict:
    """Pure, testable order decision. Caps notional at max_leverage x NAV."""
    if price <= 0 or nav <= 0:
        return {"target_units": int(current_units), "delta": 0, "reason": "bad price/nav"}
    target_notional = weight * nav
    cap = max_leverage * nav
    if abs(target_notional) > cap:
        target_notional = math.copysign(cap, target_notional)
    target_units = int(round(target_notional / price))
    delta = target_units - int(round(current_units))
    if abs(delta) < min_trade:
        return {"target_units": target_units, "delta": 0, "reason": "within tolerance"}
    return {"target_units": target_units, "delta": delta, "reason": "rebalance"}


def _load_guards() -> dict:
    """Human-approved guards (written ONLY by apply_change.py). Missing = no guards."""
    if GUARDS_FILE.exists():
        try:
            return json.loads(GUARDS_FILE.read_text())
        except Exception:  # noqa: BLE001
            pass
    return {"target_vol_override": None, "halt": False}


def _champion_cfg():
    f = RESEARCH / "champion.json"
    params = {}
    name = "baseline"
    if f.exists():
        try:
            data = json.loads(f.read_text())
            name = data.get("champion", {}).get("name", "baseline")
            params = data.get("champion", {}).get("params", {})
        except Exception:  # noqa: BLE001
            pass
    return name, MacroConfig(**{**BASELINE, **params})


def _load_data():
    p = DAILY / f"{SETTINGS.instrument}_D.csv"
    if not p.exists():
        return None, None
    px = pd.read_csv(p, parse_dates=["time"]).set_index("time").sort_index()
    ryp = DAILY / "DFII10.csv"
    ry = (pd.read_csv(ryp, parse_dates=["time"]).set_index("time").sort_index()["dfii10"]
          if ryp.exists() else None)
    return px, ry


def run():
    if STOP_FILE.exists():
        notifier.info("Paper trader: STOP file present -- standing down.")
        return {"status": "stopped"}

    prices, ry = _load_data()
    if prices is None or len(prices) < 300:
        notifier.info("Paper trader: no daily data -- run data/fetch_daily.py.")
        return {"status": "no_data"}

    last_bar = prices.index[-1].to_pydatetime().replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - last_bar).days
    if age > MAX_BAR_AGE_DAYS:
        notifier.info(f"Paper trader: latest bar is {age}d old (>{MAX_BAR_AGE_DAYS}) "
                      f"-- standing down on stale data.")
        return {"status": "stale"}

    champ_name, cfg = _champion_cfg()

    # Human-approved guards (written only by apply_change.py). The bot never
    # changes its own risk -- it only obeys guards a human has approved.
    guards = _load_guards()
    if guards.get("halt"):
        notifier.info("Paper trader: halt guard engaged (human-approved) -- standing down.")
        return {"status": "halted"}
    if guards.get("target_vol_override"):
        cfg.target_vol = float(guards["target_vol_override"])

    fw = compute_weights(prices, ry, cfg)
    wrow = fw.iloc[-1]
    weight = float(wrow["weight"])
    price = float(prices["close"].iloc[-1])

    broker = OandaBroker()
    try:
        nav = broker.nav()
        current = broker.position_units(SETTINGS.instrument)
        order = decide_order(weight, price, nav, current, PAPER_MAX_LEVERAGE, MIN_TRADE_UNITS)
        result = broker.market_order(SETTINGS.instrument, order["delta"]) if order["delta"] else {"status": "no change"}
    except Exception as e:  # noqa: BLE001
        notifier.error(f"Paper trader broker error: {e} -- no action taken.")
        return {"status": "broker_error", "error": str(e)}

    mode = "DRY" if broker.dry else "LIVE-paper"
    msg = "\n".join([
        f"[PAPER] {mode} -- champion `{champ_name}` on {SETTINGS.instrument}",
        f"Target weight {weight:+.2f} | price {price:.2f} | NAV {nav:.0f}",
        f"Current units {current:+.0f} -> target {order['target_units']:+.0f} "
        f"(order {order['delta']:+d}, {order['reason']})",
        f"Cap: {PAPER_MAX_LEVERAGE:g}x NAV. _Practice account only -- no real capital._",
    ])
    notifier.post(msg)
    print(msg)
    if broker.actions:
        print("\n".join(broker.actions))

    # Record this day's position + decision features so the self-learning loop
    # can later judge how the live paper account actually performed.
    try:
        ledger.append_entry(
            instrument=SETTINGS.instrument, price=price, nav=nav, weight=weight,
            prev_units=current, delta=order["delta"],
            held_units=current + order["delta"], champion=champ_name, mode=mode,
            features={"direction": wrow.get("direction"), "pos_dir": wrow.get("pos_dir"),
                      "ry_mom": wrow.get("ry_mom"), "realized_vol": wrow.get("realized_vol")})
    except Exception as e:  # noqa: BLE001
        print(f"[ledger:warn] {e}")

    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "paper_last.json").write_text(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(), "mode": mode,
        "champion": champ_name, "weight": weight, "price": price, "nav": nav,
        "current_units": current, "order": order, "result": result}, indent=2, default=str))
    return {"status": "ok", "order": order, "mode": mode}


if __name__ == "__main__":
    run()
