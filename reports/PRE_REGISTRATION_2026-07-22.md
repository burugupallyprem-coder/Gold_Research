# Pre-Registration — Two Parallel Paper Tracks (locked 2026-07-22)

This document is locked BEFORE forward paper trading begins so results cannot be
cherry-picked later. Both tracks are paper/simulation only. No real capital. A human
approves anything beyond paper. Not financial advice.

## The two strategies, running in parallel
| | Track 1 — Macro daily | Track 2 — Intraday stack |
|---|---|---|
| Logic | 50/200 EMA trend + 12m momentum + 10% vol target (real-yield filter inert until DFII10 added) | FVG + NY-Opening entries, confidence gate ON, filtered to trade only with the daily 50/200-EMA+mom trend |
| Clock | Daily decision | M15 entries, every 4h check |
| Runner | `paper_trader.py` (existing) | `intraday_stack_paper.py` (new) |
| Schedule | `paper_trade.yml` 21:30 UTC Mon–Fri | `intraday_stack_paper.yml` every 4h Mon–Fri |
| State (isolated) | `memory/sim_account.json` | `memory/intraday_stack_state.json`, `reports/intraday_stack_trades.csv` |
| Places real orders? | No (sim fills, practice) | No (simulation only, no broker code) |

The tracks are fully isolated — neither can touch the other's state or the champion file.

## Backtest on record (what we're testing against)
From `reports/rigorous_backtest_2026-07-22.md`:
- **Track 1 (fast_trend variant):** full-period Sharpe 0.62–0.73, survives 5× costs, maxDD −26%,
  selection-Sharpe 0.46. Trend-follower: wins in trending years, loses in chop (2017, 2021–2023).
- **Track 2:** +0.138 R/trade at 1× cost (positive 7/8 years) but **−0.035 R/trade at 3× cost**
  (negative 6/8 years); **90% of trades were long**, short side barely tested.

## Pre-registered hypotheses (the bar to clear)
- **Track 1** — passes if forward selection-Sharpe stays ≈ 0.4–0.6 over the trial. Losing
  calendar quarters in choppy gold regimes are expected and do NOT count as failure.
- **Track 2** — passes ONLY if realized net expectancy is positive after live costs across
  ≥ 30 closed trades AND it is not profitable *only* while gold rises. Fails if avg R < 0 after
  30 trades, or if removing the winning long-trend months makes it negative.

## Judgment gates (no moving them)
- Minimum **30 closed trades** per track before any verdict (~2–6 months for Track 2).
- Formal **6-month checkpoint** review.
- Any promotion beyond paper → months more data + Prem's explicit approval via `apply_change.py`.

## Open item flagged before start
- The daily **real-yield macro filter is inert** (no `data/daily/DFII10.csv`). Both tracks
  currently use pure trend for direction. Adding FRED DFII10 would change Track 1 and the
  Track 2 filter; if added mid-trial, that resets the trial (it's a different strategy).

## To activate (owner action)
1. Confirm GitHub secrets exist: `OANDA_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`.
2. Commit `intraday_stack_paper.py` + `.github/workflows/intraday_stack_paper.yml`.
3. First scheduled run auto-initializes Track 2 and posts an `[INTRADAY-STACK]` init message.
   Track 1 already runs. Both then report independently to Slack.
4. (Optional, separate approval) Promote Track 1's daily champion from `baseline` to
   `fast_trend` via `apply_change.py` — it won the daily bake-off on every metric.
