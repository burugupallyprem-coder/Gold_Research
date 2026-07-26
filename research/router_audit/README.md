# router_audit — reproducible honest-router backtest

Everything behind `reports/honest_router_vs_hindsight_2026-07-25.md`, committed so it can be
inspected and re-run. Paper/backtest only.

## Files
- `collect_trades.py` — STEP 1. Runs the production engine (`backtest/engine_final.py`) for
  FVG+NY (Displacement off, gate 60) at 0.40 round-trip cost; writes per-window
  `reports/backtest_data_2026-07-25/trades_*.csv`. Saves each trade's ORIGINAL planned risk
  (`r_planned`) so cost stress is exact. Documents the break-even/`risk=0` bug that was fixed.
- `analyze.py` — STEP 2 (fast, no engine). Applies the `fast_trend` 20/100 prior-close side
  filter, splits train/validation, computes every metric, both equity curves, benchmarks, the
  gate, and a VERIFICATION block. Writes `analysis.json`, `verification.json`,
  `router_trade_log.csv`, `eq_*.csv`.

## Reproduce
```
# STEP 1 (slow; per half-year to fit the sandbox time limit). Full set already saved.
python research/router_audit/collect_trades.py 2024
python research/router_audit/collect_trades.py 2021a 2021-01-01 2021-07-01   # ...etc
# STEP 2 (seconds)
python research/router_audit/analyze.py
```
`analyze.py` is deterministic; re-running on the saved `trades_*.csv` reproduces the report
numbers exactly (selection Sharpe 0.549, holdout 1.44, gate PASS, random pct 100).

## Inspect
- Per-trade audit: `reports/backtest_data_2026-07-25/router_trade_log.csv`
- Six-concern diagnostics: `reports/backtest_data_2026-07-25/verification.json`
- Full methodology write-up: `reports/verification_methodology_2026-07-25.md`
