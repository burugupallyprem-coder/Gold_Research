# Self-Learning Loop (human-in-the-loop)

This document explains the autonomous self-improvement layer that sits on top of
the Gold Macro-Trend paper bot. Its defining rule: **nothing changes the live
strategy or its risk without a human approving it.** The loop watches, measures,
and *proposes*; a person *applies*.

## The four moving parts

1. **Record (`learning/ledger.py`).** Every weekday, after `paper_trader.py`
   reconciles the OANDA practice position, it appends one snapshot to
   `memory/trade_ledger.json`: the price, account NAV, target weight, the units
   actually held, and the decision features that produced them (trend direction,
   real-yield momentum, realized volatility). This is the bot writing down what
   it did and why.

2. **Review (`learning/monitor.py`).** Once a week the monitor turns that ledger
   into a real performance record. It marks the position held into each day
   against the next day's price move to build a live daily P&L series, then
   computes live Sharpe, drawdown, hit-rate, and cumulative return, and compares
   them to the strategy's backtest expectation. Results are written to
   `memory/live_stats.json`.

3. **Propose (`learning/proposals.py`).** If live results breach a guardrail, or
   the research lab has a challenger that passed every historical gate, the
   monitor files a proposal in `memory/pending_change.json` and emails a warning
   (reusing the Quant Coach's Gmail credentials). It never applies the change.
   Proposal types:
   - `halt` -- live drawdown breached the limit; recommend standing down.
   - `derisk` -- live Sharpe has been negative over a real sample; recommend
     cutting the volatility target.
   - `promote` -- a challenger beat the champion and confirmed on the permanent
     holdout for the required streak.

4. **Apply (`apply_change.py`, manual).** You approve by running the
   `oanda-apply-change` GitHub Action (or `python apply_change.py`). Only then is
   anything written: a `promote` rewrites `research/champion.json`; a `derisk` or
   `halt` writes `memory/guards.json`, which the paper trader reads and obeys on
   its next run. Running with `--dismiss` discards the proposals unchanged.

## Why it can't fool itself

- **Small-sample discipline.** This is a daily strategy, so trades accrue
  slowly. Until `MIN_DAYS_TO_LEARN` (default 30) position-days exist, the monitor
  only reports and will never propose a strategy swap on a handful of trades.
- **History confirms, live only flags.** A strategy change still has to pass the
  research lab's existing gauntlet -- a permanent 1-year holdout, a 3-week
  confirmation streak, and 5x cost stress -- before it can even be proposed. Live
  results can trigger de-risking and veto aggression, but they do not re-optimize
  the strategy on their own.
- **Human gate.** The research lab no longer auto-promotes. Every strategy change
  waits for your explicit approval via the manual workflow.

## The weekly clock (UTC)

| When | Workflow | What it does |
|---|---|---|
| Mon-Fri 21:30 | `oanda-paper-trader` | reconcile position; append to the ledger |
| Sunday 04:00 | `oanda-research-lab` | propose a promotion if a challenger passed all gates |
| Sunday 05:00 | `oanda-learn` | review live results; email a warning if a change is proposed |
| on demand | `oanda-apply-change` | you approve and apply pending proposals |

## Tunable thresholds (GitHub repo variables, optional)

| Variable | Default | Meaning |
|---|---|---|
| `MIN_DAYS_TO_LEARN` | 30 | position-days required before a strategy-affecting proposal |
| `MAX_LIVE_DD` | 0.25 | live drawdown that triggers a `halt` proposal |
| `LIVE_SHARPE_FLOOR` | 0.0 | live Sharpe below this (with enough days) triggers a `derisk` proposal |
| `DERISK_VOL_FLOOR` | 0.05 | the reduced target volatility a `derisk` applies |

## Files written by the loop (committed to git, so state survives cloud runs)

- `memory/trade_ledger.json` -- the bot's own daily positions + features
- `memory/live_stats.json` -- latest live performance vs expectation
- `memory/pending_change.json` -- proposals awaiting approval + applied history
- `memory/guards.json` -- approved risk overrides the paper trader obeys

## Honest expectation

For the first few months this loop mostly logs and, at worst, de-risks. The
"learn from its own track record" phase only becomes meaningful once a real
sample of trades exists -- and even then, history (not a lucky week of live
trades) is what confirms any change. That is the difference between disciplined
self-improvement and overfitting to noise.
