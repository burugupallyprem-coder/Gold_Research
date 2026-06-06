"""
backtest/wf.py
--------------
Walk-forward analysis (corrected aggregate). Optimize parameters in-sample,
apply to the next out-of-sample slice, concatenate OOS results. A large
in-sample vs out-of-sample gap = curve-fitting.

Note: each fold sizes positions off the same starting equity, so the stitched
OOS equity curve / drawdown is approximate; expectancy_R, win rate, and profit
factor (which are size-independent) are the metrics to trust here.

Usage:
    python backtest/wf.py --folds 5 --train 4000 --test 1000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import SETTINGS                                       # noqa: E402
from strategy.strategy import StrategyConfig                      # noqa: E402
from strategy.risk import RiskConfig                              # noqa: E402
from backtest.core import BacktestConfig, CostModel               # noqa: E402
from backtest.engine_final import run_backtest_fast              # noqa: E402
from backtest.metrics import compute_metrics                      # noqa: E402

CANDLES = ROOT / "data" / "candles"
REPORTS = ROOT / "reports"
DISP_GRID = [1.0, 1.2, 1.4, 1.6]
THRESH_GRID = [60.0, 70.0]


def load(tf):
    p = CANDLES / f"{SETTINGS.instrument}_{tf}.csv"
    if not p.exists():
        sys.exit(f"Missing {p}. Run: python data/fetch_oanda.py")
    df = pd.read_csv(p, parse_dates=["time"]).set_index("time").sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


def _run(df, htf, disp, thresh):
    sc = StrategyConfig(displacement_atr_mult=disp)
    rc = RiskConfig()
    bt = BacktestConfig(starting_equity=SETTINGS.starting_equity,
                        confidence_threshold=thresh, use_confidence_gate=True)
    cost = CostModel(spread_usd=SETTINGS.spread_usd, slippage_usd=SETTINGS.slippage_usd,
                     commission_per_trade=SETTINGS.commission_per_trade)
    res = run_backtest_fast(df, htf, sc, rc, bt, cost=cost)
    return res, compute_metrics(res.trades, res.equity_curve, bt.starting_equity)


def _pf(m):
    pf = m.get("profit_factor", 0)
    return float("inf") if pf == "inf" else (pf or 0)


def build_equity(trades, start):
    rows, eq = [], start
    for t in sorted(trades, key=lambda x: x.exit_time or x.entry_time):
        eq += t.pnl
        rows.append((t.exit_time or t.entry_time, eq))
    if not rows:
        return pd.DataFrame({"equity": [start]}, index=pd.DatetimeIndex([pd.Timestamp.utcnow()]))
    return pd.DataFrame({"equity": [r[1] for r in rows]},
                        index=pd.DatetimeIndex([r[0] for r in rows]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--train", type=int, default=4000)
    ap.add_argument("--test", type=int, default=1000)
    args = ap.parse_args()

    df, htf = load(SETTINGS.entry_tf), load(SETTINGS.htf_tf)
    n = len(df)
    if n < args.train + args.test:
        args.train = max(1000, int(n * 0.6))
        args.test = max(300, (n - args.train) // max(1, args.folds))
    print(f"{n} bars; train={args.train} test={args.test} folds={args.folds}")

    oos_trades, fold_rows, start = [], [], 0
    for k in range(args.folds):
        tr_lo, tr_hi = start, start + args.train
        te_hi = tr_hi + args.test
        if te_hi > n:
            break
        train_df, test_df = df.iloc[tr_lo:tr_hi], df.iloc[tr_hi:te_hi]
        tr_htf = htf[htf.index <= train_df.index[-1]]
        te_htf = htf[htf.index <= test_df.index[-1]]

        best = None
        for disp in DISP_GRID:
            for th in THRESH_GRID:
                _, m = _run(train_df, tr_htf, disp, th)
                s = _pf(m)
                if best is None or s > best[0]:
                    best = (s, disp, th, m)
        _, disp, th, train_m = best
        res, test_m = _run(test_df, te_htf, disp, th)
        oos_trades.extend(res.trades)
        fold_rows.append({
            "fold": k + 1,
            "train": f"{train_df.index[0].date()}..{train_df.index[-1].date()}",
            "test": f"{test_df.index[0].date()}..{test_df.index[-1].date()}",
            "chosen_disp": disp, "chosen_threshold": th,
            "in_sample_PF": train_m.get("profit_factor"),
            "oos_PF": test_m.get("profit_factor"),
            "oos_trades": test_m.get("trades"),
            "oos_expectancy_R": test_m.get("expectancy_R"),
            "oos_return_pct": test_m.get("total_return_pct"),
        })
        print(f"  fold {k+1}: disp={disp} th={th} | IS PF={train_m.get('profit_factor')} "
              f"-> OOS PF={test_m.get('profit_factor')} ({test_m.get('trades')} tr, "
              f"exp {test_m.get('expectancy_R')}R)")
        start += args.test

    agg = (compute_metrics(oos_trades, build_equity(oos_trades, SETTINGS.starting_equity),
                           SETTINGS.starting_equity) if oos_trades else {"trades": 0})
    out = {"folds": fold_rows, "aggregate_out_of_sample": agg}
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "walkforward.json").write_text(json.dumps(out, indent=2, default=str))
    print("\n=== AGGREGATE OUT-OF-SAMPLE (size-independent metrics are the trustworthy ones) ===")
    print(json.dumps({k: agg.get(k) for k in
                      ("trades", "win_rate", "profit_factor", "expectancy_R",
                       "max_losing_streak")}, indent=2, default=str))
    print("Wrote reports/walkforward.json")


if __name__ == "__main__":
    main()
