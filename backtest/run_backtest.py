"""
backtest/run_backtest.py
------------------------
Load cached OANDA candles, run the event-driven backtest, print metrics,
and write a trade blotter + summary to reports/.

Usage:
    python backtest/run_backtest.py
    python backtest/run_backtest.py --disp 1.4 --threshold 70 --no-gate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import SETTINGS                                  # noqa: E402
from strategy.strategy import StrategyConfig                 # noqa: E402
from strategy.risk import RiskConfig                         # noqa: E402
from backtest.core import BacktestConfig, CostModel, run_backtest  # noqa: E402
from backtest.metrics import compute_metrics, trades_to_frame  # noqa: E402

CANDLES = ROOT / "data" / "candles"
REPORTS = ROOT / "reports"


def load_candles(instrument: str, tf: str) -> pd.DataFrame:
    path = CANDLES / f"{instrument}_{tf}.csv"
    if not path.exists():
        sys.exit(f"Missing {path}. Run:  python data/fetch_oanda.py")
    df = pd.read_csv(path, parse_dates=["time"]).set_index("time").sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--disp", type=float, default=1.2, help="displacement_atr_mult")
    ap.add_argument("--threshold", type=float, default=SETTINGS.confidence_threshold)
    ap.add_argument("--no-gate", action="store_true", help="disable confidence gate")
    ap.add_argument("--spread", type=float, default=SETTINGS.spread_usd)
    ap.add_argument("--slippage", type=float, default=SETTINGS.slippage_usd)
    ap.add_argument("--tag", default="base")
    args = ap.parse_args()

    df = load_candles(SETTINGS.instrument, SETTINGS.entry_tf)
    htf = load_candles(SETTINGS.instrument, SETTINGS.htf_tf)
    print(f"Loaded {len(df)} {SETTINGS.entry_tf} bars, {len(htf)} {SETTINGS.htf_tf} bars "
          f"({df.index[0].date()} -> {df.index[-1].date()})")

    strat_cfg = StrategyConfig(displacement_atr_mult=args.disp)
    risk_cfg = RiskConfig()
    bt_cfg = BacktestConfig(
        starting_equity=SETTINGS.starting_equity,
        confidence_threshold=args.threshold,
        use_confidence_gate=not args.no_gate,
    )

    cost = CostModel(spread_usd=args.spread, slippage_usd=args.slippage,
                     commission_per_trade=SETTINGS.commission_per_trade)
    result = run_backtest(df, htf, strat_cfg, risk_cfg, bt_cfg, cost=cost)
    metrics = compute_metrics(result.trades, result.equity_curve,
                              bt_cfg.starting_equity)

    print("\n=== BACKTEST METRICS ===")
    print(json.dumps(metrics, indent=2, default=str))

    REPORTS.mkdir(exist_ok=True)
    blotter = trades_to_frame(result.trades)
    blotter.to_csv(REPORTS / f"blotter_{args.tag}.csv", index=False)
    result.equity_curve.to_csv(REPORTS / f"equity_{args.tag}.csv")
    (REPORTS / f"summary_{args.tag}.json").write_text(
        json.dumps({"config": result.config, "metrics": metrics}, indent=2, default=str))
    print(f"\nWrote reports/blotter_{args.tag}.csv, equity_{args.tag}.csv, summary_{args.tag}.json")


if __name__ == "__main__":
    main()
