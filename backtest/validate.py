"""
backtest/validate.py
--------------------
The validation pack — runs the honest tests and produces a verdict:

  1. Base run (regime + event gates + partial profits ON).
  2. Cost-stress run (wider spread + slippage).
  3. Walk-forward out-of-sample (optimize in-sample, test OOS).
  4. Long vs short split (is the edge real, or just long-beta in a gold uptrend?).

Returns a structured dict (also written to reports/validation.json) and a
plain-English verdict. The thresholds are deliberately strict — the goal is to
catch a fake edge, not to flatter it.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))

from config import SETTINGS                                  # noqa: E402
from strategy.strategy import StrategyConfig                 # noqa: E402
from strategy.risk import RiskConfig                         # noqa: E402
from strategy.signals_v2 import RegimeConfig                 # noqa: E402
from backtest.core import BacktestConfig, CostModel          # noqa: E402
from backtest.engine_v2 import run_backtest_v2               # noqa: E402
from backtest.metrics2 import compute_metrics2               # noqa: E402

CANDLES = ROOT / "data" / "candles"
REPORTS = ROOT / "reports"
DISP_GRID = [1.2, 1.4]
THRESH_GRID = [60.0, 70.0]


def _load(tf):
    p = CANDLES / f"{SETTINGS.instrument}_{tf}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["time"]).set_index("time").sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df


def _pf(m):
    pf = m.get("profit_factor", 0)
    return float("inf") if pf == "inf" else (pf or 0)


def _run(df, htf, disp, thresh, spread, slippage):
    sc = StrategyConfig(displacement_atr_mult=disp)
    rc = RiskConfig()
    rg = RegimeConfig()
    bt = BacktestConfig(starting_equity=SETTINGS.starting_equity,
                        confidence_threshold=thresh, use_confidence_gate=True)
    cost = CostModel(spread_usd=spread, slippage_usd=slippage,
                     commission_per_trade=SETTINGS.commission_per_trade)
    res = run_backtest_v2(df, htf, sc, rc, bt, rg, cost=cost)
    return res, compute_metrics2(res.trades, res.equity_curve, bt.starting_equity)


def _build_equity(trades, start):
    rows, eq = [], start
    for t in sorted(trades, key=lambda x: x.exit_time or x.entry_time):
        eq += t.pnl
        rows.append((t.exit_time or t.entry_time, eq))
    if not rows:
        return pd.DataFrame({"equity": [start]}, index=pd.DatetimeIndex([pd.Timestamp.utcnow()]))
    return pd.DataFrame({"equity": [r[1] for r in rows]},
                        index=pd.DatetimeIndex([r[0] for r in rows]))


def walk_forward(df, htf, folds, train, test):
    n = len(df)
    if n < train + test:
        train = max(1000, int(n * 0.6))
        test = max(300, (n - train) // max(1, folds))
    oos, rows, start = [], [], 0
    for k in range(folds):
        tr_lo, tr_hi, te_hi = start, start + train, start + train + test
        if te_hi > n:
            break
        tr, te = df.iloc[tr_lo:tr_hi], df.iloc[tr_hi:te_hi]
        tr_h = htf[htf.index <= tr.index[-1]] if htf is not None else None
        te_h = htf[htf.index <= te.index[-1]] if htf is not None else None
        best = None
        for disp in DISP_GRID:
            for th in THRESH_GRID:
                _, m = _run(tr, tr_h, disp, th, SETTINGS.spread_usd, SETTINGS.slippage_usd)
                s = _pf(m)
                if best is None or s > best[0]:
                    best = (s, disp, th)
        _, disp, th = best
        res, m = _run(te, te_h, disp, th, SETTINGS.spread_usd, SETTINGS.slippage_usd)
        oos.extend(res.trades)
        rows.append({"fold": k + 1, "disp": disp, "thresh": th,
                     "oos_PF": m.get("profit_factor"), "oos_trades": m.get("trades"),
                     "oos_expectancy_R": m.get("expectancy_R")})
        start += test
    agg = compute_metrics2(oos, _build_equity(oos, SETTINGS.starting_equity),
                           SETTINGS.starting_equity) if oos else {"trades": 0}
    return {"folds": rows, "aggregate": agg}


def _verdict(base, stress, oos):
    oos_pf = _pf(oos.get("aggregate", {})) if oos else 0
    oos_exp = oos.get("aggregate", {}).get("expectancy_R", 0) or 0
    stress_pf = _pf(stress)
    bd = base.get("by_direction", {})
    long_pf = _pf(bd.get("long", {}))
    short_pf = _pf(bd.get("short", {}))
    both_sides = long_pf > 1.0 and short_pf > 1.0
    n_oos = oos.get("aggregate", {}).get("trades", 0)

    if n_oos < 30:
        branch = "INSUFFICIENT DATA"
        verdict = ("Not enough out-of-sample trades to judge. Fetch more history "
                   "(--days) and re-run before drawing any conclusion.")
    elif oos_pf >= 1.15 and oos_exp > 0.05 and stress_pf >= 1.05 and both_sides:
        branch = "ROBUST-ISH (rare)"
        verdict = ("Out-of-sample edge survives costs AND shows on both long and "
                   "short. Treat with continued skepticism; consider a small live "
                   "paper loop. Re-confirm on more history first.")
    elif oos_pf > 1.0 and stress_pf > 1.0:
        branch = "MARGINAL / REGIME-DEPENDENT"
        verdict = ("A thin out-of-sample edge that does not clearly survive stress "
                   "or appear on both sides. Do NOT deploy capital. Keep it as a "
                   "research/learning asset; investigate which setups/regimes carry it.")
    else:
        branch = "NO EDGE AFTER COSTS"
        verdict = ("Out-of-sample performance is at or below break-even after costs. "
                   "This is the most common and honest outcome. The project's value "
                   "is the rigor, not the P&L. Do not risk money on it.")
    return {
        "branch": branch, "verdict": verdict,
        "oos_PF": oos_pf, "oos_expectancy_R": oos_exp, "oos_trades": n_oos,
        "stress_PF": stress_pf, "long_PF": long_pf, "short_PF": short_pf,
        "both_sides_positive": both_sides,
    }


def run(folds=4, train=4000, test=1000):
    df, htf = _load(SETTINGS.entry_tf), _load(SETTINGS.htf_tf)
    if df is None or htf is None:
        return {"error": "no candles — run data/fetch_oanda.py"}

    _, base = _run(df, htf, 1.2, SETTINGS.confidence_threshold,
                   SETTINGS.spread_usd, SETTINGS.slippage_usd)
    _, stress = _run(df, htf, 1.2, SETTINGS.confidence_threshold, 0.6, 0.3)
    oos = walk_forward(df, htf, folds, train, test)
    decision = _verdict(base, stress, oos)

    out = {
        "instrument": SETTINGS.instrument,
        "bars": {"M15": len(df), "H4": len(htf)},
        "period": f"{df.index[0].date()}..{df.index[-1].date()}",
        "base": base, "cost_stress": stress, "walk_forward": oos,
        "decision": decision,
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "validation.json").write_text(json.dumps(out, indent=2, default=str))
    return out


def slack_text(out):
    if out.get("error"):
        return f"[VALIDATE] {out['error']}"
    d = out["decision"]
    b = out["base"]
    bd = b.get("by_direction", {})
    lines = [
        f"[VALIDATE] {out['instrument']} {out['period']} — VERDICT: *{d['branch']}*",
        f"Out-of-sample: PF={d['oos_PF']:.3f}  exp={d['oos_expectancy_R']}R  trades={d['oos_trades']}",
        f"Cost-stress PF={d['stress_PF']:.3f}  (wide spread/slippage)",
        f"Long PF={d['long_PF']:.3f} ({bd.get('long', {}).get('trades', 0)} tr)  |  "
        f"Short PF={d['short_PF']:.3f} ({bd.get('short', {}).get('trades', 0)} tr)",
        f"Base (in-sample): trades={b.get('trades')} win={b.get('win_rate')} "
        f"PF={b.get('profit_factor')} exp={b.get('expectancy_R')}R",
        d["verdict"],
    ]
    return "\n".join(lines)
