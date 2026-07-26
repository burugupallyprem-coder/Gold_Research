# START HERE — Gold Trading Bot (OANDA)

_New chat? Read this first, then `CLAUDE.md` (full router). Recovered & confirmed 2026-06-21._

## What this project is
Autonomous, self-validating quant trading system for spot gold (XAU/USD) on
OANDA **practice** — research → backtest → walk-forward → validate → paper-trade
→ self-review, running in the cloud (GitHub Actions), with a human approving
every strategy change.

## Status as of last work (June 19, 2026)
- Champion strategy = `baseline` (macro-trend: momentum + real-yield/TIPS filter
  + volatility targeting). Validated on ~10y real data: Sharpe ~0.54, max
  drawdown ~36%, survives 5x costs. `target_vol = 0.10`.
- Live on OANDA practice. Plain-English Slack messages on every trade are wired.

## The one task that was in progress
Flip paper execution from `DRY` → `LIVE-paper` so practice orders actually
register — by adding the `OANDA_ACCOUNT_ID` secret in GitHub.

## What's next (from MILESTONES.md)
1. Finish DRY → LIVE-paper.
2. Accumulate a months-long live-paper track record; let the self-learning loop run.
3. Build the H4 confirmation layer (real logic + real-data backtest) as a human-approved caution filter.
4. Cross-asset confirmation (silver, commodities); a live dashboard.

## Key files
- Strategy: `strategy/macro_trend.py` · Execution: `paper_trader.py`, `execution/oanda_broker.py`
- Validation/research: `backtest/`, `research_lab.py`, `validate_run.py`, `macro_run.py`
- State: `research/champion.json`, `reports/`, `memory/`
- Full map & rules: `CLAUDE.md`

## Rules (non-negotiable)
Honesty over hype · paper only · validate before deploy · human-in-the-loop ·
infra generalizes, edge does NOT.
