# CLAUDE.md -- Router & Master Index (Gold Quant Lab -> Trading OS)

Read this FIRST in any new session. It says who I am, what I'm building, where
everything lives, and the rules you must follow. This is the routing tree.

## Who / goal
I'm Prem. I'm building an autonomous, self-validating quant trading system --
starting with spot gold (XAU/USD) on OANDA practice -- and growing it into a
multi-symbol "Trading OS" (gold today; equities like TSLA and other majors
later). Everything runs in the cloud, with a human approving every real change.

## Non-negotiable rules (the ethos)
1. Honesty over hype. Report real numbers. If something has no edge, say so.
2. Paper only. No real capital until months of validated paper results AND an
   explicit human decision.
3. Validate before deploy. Every strategy/symbol must pass the backtest +
   walk-forward + cost-stress gauntlet on REAL data before it trades.
4. Human-in-the-loop. The bot proposes; Prem approves. Nothing changes the live
   strategy or risk without approval (see apply_change.py).
5. Infra generalizes; edge does NOT. A new symbol needs its own validated
   strategy -- never assume the gold strategy works on another market.

## Where everything lives (the map)
- Strategy:           strategy/macro_trend.py (validated champion), strategy/*.py
- Execution:          paper_trader.py, execution/oanda_broker.py, execution/notifier.py
- Research/backtest:  backtest/, research_lab.py, macro_run.py, validate_run.py
- Self-learning:      learning/ (ledger, monitor, proposals, emailer), apply_change.py
- Diagnostics:        analysis/ (anomaly_scan.py, intraday_backtest.py)
- Data:               data/fetch_daily.py, data/fetch_oanda.py -> data/daily, data/candles
- State (git memory): memory/, research/champion.json, reports/
- Cloud schedule:     .github/workflows/*.yml
- Config / secrets:   config.py (reads .env -- NEVER commit .env)
- Docs:               README.md (overview), LEARNING.md (self-learning loop),
                      MILESTONES.md (journey), OPERATIONS.md (runbook), this file (router)

## How the cloud runs (cadence, all UTC)
- paper trade:   Mon-Fri 21:30  (5:30 PM ET) -- the live decision
- backtest:      Mon-Fri 22:00  (+ Fri 22:30 weekly review)
- validate:      Sat 02:00   |   macro: Sat 03:00
- research lab:  Sun 04:00   |   self-learning: Sun 05:00
- coach email:   daily 12:00 and 00:00
- apply-change:  manual only (human approval)

## Current status
Gold champion = `baseline` (macro-trend): trend + real-yield filter + vol target.
Validated on ~10y real data: Sharpe ~0.54, max drawdown ~36%, survives 5x costs.
Live on OANDA practice. target_vol = 0.10 (chosen by Prem). Flipping DRY ->
LIVE-paper by adding the OANDA_ACCOUNT_ID secret in GitHub.

## Expanding to a multi-symbol Trading OS ("other worlds")
Each symbol is its own isolated "world" that REUSES the same infrastructure:
1. Pick a symbol + a hypothesis with real rationale (not "gold strategy on X").
2. Fetch its real history; run the backtest + walk-forward + cost-stress gauntlet.
3. Only if it passes: add it as its own config/branch with its own champion file.
4. Deploy on the same cloud cadence; self-learning loop + human approval apply.
Keep symbols isolated so one bad strategy can never touch another.

## How to start a session
Read this file, then check research/champion.json (current strategy) and reports/
(latest results). Don't re-read full chat history. Confirm what Prem wants,
propose, get approval, then act. Verify your own work before calling it done.
