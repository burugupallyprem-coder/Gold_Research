# OANDA_Backtesting_bot — XAU/USD Gold SMC v8

A backtesting ecosystem for the Gold SMC v8 strategy on **OANDA spot gold
(XAU/USD)**, built as the rigorous research counterpart to the live GLD/Alpaca
bot. Same strategy logic, ported faithfully; different purpose: instead of
placing live paper trades, this replays years of historical XAU/USD data
through the strategy with realistic costs and tells you — honestly — whether
there is any edge.

It mirrors the Alpaca bot's shape: code + memory live in this Git repo, a
GitHub Actions workflow runs on a schedule, results are committed back, Slack
(`#`, channel `C0B88CUAZPD`) is the notification channel, and every Friday a
weekly review is appended to `memory/lessons.md`.

## Why a backtester first (read this)

The whole reason this project exists is the mentor review: the live bot had **no
way to test a parameter change short of waiting a month of live data.** This
repo is that missing "truth machine." It is built to be honest, not flattering:

- **No look-ahead.** A signal on bar *i* is computed from closed bars only; the
  fill happens at bar *i+1*'s open.
- **Realistic costs.** Half-spread + adverse slippage on every entry and exit.
- **Pessimistic intrabar fills.** If a bar touches both stop and target, the
  stop fills first.
- **Walk-forward.** Parameters are chosen in-sample and judged out-of-sample, so
  curve-fitting shows up instead of hiding.

Set expectations accordingly: the single most likely result of an honest
backtest of a discretionary-style SMC strategy, after costs, is **little or no
statistically significant edge.** That is not failure — it is the apparatus
doing its job. See `VERDICT.md`.

## Canonical files

```
config.py                     Settings from .env (no secrets committed)
data/fetch_oanda.py           Pull XAU/USD candles from OANDA v20 -> data/candles/*.csv  (RUN ON YOUR MACHINE / CI)
strategy/strategy.py          Reference signal logic (ported from Alpaca, broker-decoupled)
strategy/risk.py              Sizing, stops, targets
strategy/confidence.py        0-100 confidence gate
strategy/signals.py           Vectorized precompute + decide_at (fast path; PARITY-PROVEN vs strategy.py)
backtest/core.py              Event-driven engine mechanics (entry/exit/BE/costs) — unit-tested
backtest/engine_final.py      Production engine = core mechanics + signals fast path
backtest/metrics.py           Sharpe, PF, drawdown, R-multiples, by-setup breakdown
backtest/run2.py              Single backtest run + reports (CLI: --disp --threshold --spread ...)
backtest/wf.py                Walk-forward analysis (in-sample optimize -> out-of-sample test)
main.py                       Orchestrator: routines backtest / walkforward / weekly_review / all
execution/notifier.py         Slack Web API client (dry-prints if no token)
.github/workflows/backtest.yml  Scheduled cloud runner
memory/                       strategy.md, risk_rules.md, lessons.md, results.json (committed state)
reports/                      blotter, equity curve, summary (gitignored CSVs; summary committed)
tests/                        test_engine.py (mechanics) + parity_final2.py (signal parity)
```

Some earlier scratch files (`engine.py` shim, `feat.py`, `fastcore*.py`,
`run.py`, `run_backtest.py`, `test_parity*.py`) are superseded and safe to
delete; the canonical entrypoints are `main.py`, `backtest/run2.py`,
`backtest/wf.py`.

## Quick start (your machine)

```bash
pip install -r requirements.txt
cp .env.example .env            # fill OANDA_API_KEY + OANDA_ACCOUNT_ID
python data/fetch_oanda.py      # downloads XAU/USD M15 + H4 into data/candles/
python backtest/run2.py         # full backtest + metrics
python backtest/wf.py           # walk-forward
python main.py --routine weekly_review   # appends to memory/lessons.md
```

See `OPERATIONS.md` for the cloud/GitHub-Actions setup and the secrets list.

## Status

Engine mechanics: unit-tested (9/9). Signal fast-path: parity-proven against the
reference implementation (0 mismatches). End-to-end pipeline verified on
synthetic data. **Real-data verdict pending** your first `fetch_oanda.py` run.
