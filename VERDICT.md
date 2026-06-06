# VERDICT — the honest read

This file is the whole point of the project. It gets filled in once you run the
backtest on **real** OANDA XAU/USD data. Until then, here is the framework and
the ruthless prior, so nobody fools themselves later.

## How to fill this in
1. `python data/fetch_oanda.py --days 730`
2. `python backtest/run2.py --tag base` and `python backtest/wf.py`
3. Read `reports/summary_base.json` and `reports/walkforward.json`.
4. Decide which branch below the numbers land in.

## What the numbers must clear to mean anything
- **Out-of-sample** (walk-forward) profit factor meaningfully > 1.0, not just
  in-sample. In-sample PF is nearly meaningless on its own.
- Positive **expectancy in R** out-of-sample, surviving the cost model.
- A trade count large enough to matter (rule of thumb: 100+ OOS trades before
  taking any win rate seriously).
- Performance that doesn't **collapse under the cost stress run**
  (`--spread 0.6 --slippage 0.3`). If a wider spread kills it, the "edge" was
  paying yourself with unrealistic fills.

## The three branches
**Branch 1 — No edge after costs (most likely).** Out-of-sample PF ≈ 1 or below,
expectancy ≈ 0 or negative, or results that evaporate under cost stress.
*Action:* document it plainly. This is a successful experiment — you built the
apparatus to falsify a strategy cheaply, which is exactly what the people who
actually beat markets do. It is a strong portfolio/learning outcome, not a loss.

**Branch 2 — Marginal / regime-dependent edge.** Positive OOS only in certain
folds or volatility regimes. *Action:* identify the conditions; do not deploy
broadly. Treat any live use as a small, gated experiment.

**Branch 3 — Robust edge (rare).** Consistent positive OOS expectancy across
folds, surviving cost stress, on a decent trade count. *Action:* proceed to the
live OANDA paper loop with small size and continued skepticism — a good
backtest is necessary, not sufficient.

## The ruthless prior (don't delete this)
Discretionary-style SMC concepts (displacement, FVG, NY-opening) have no
published, cost-adjusted statistical edge. A pretty TradingView curve is the
absence of evidence dressed up as evidence. Expect Branch 1. If the numbers
surprise you to the upside, be *more* suspicious, not less — check for look-ahead,
survivorship, and data quirks before believing it.

## Synthetic sanity (already done)
On synthetic random-walk data the machine runs end-to-end, the engine mechanics
pass 9/9 unit checks, and the fast signal path matches the reference
implementation bar-for-bar. Synthetic results are meaningless by construction —
they only prove the plumbing is sound, not that the strategy works.
