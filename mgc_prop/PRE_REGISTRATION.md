# Pre-registration - MGC gold-trend prop strategy (Apex $50k)

_Registered 2026-08-02. Written BEFORE any live evaluation so results can't be rationalized after the fact._

## Hypothesis
A faster gold trend (20/100 EMA) carries a modest, real edge (validated separately: it beats
the 50/200 champion with 98% block-bootstrap confidence and sits on a stable parameter plateau,
not a lucky spike). A drawdown-aware execution overlay can convert that edge into a positive
pass rate on an **Apex Trader Funding $50k EOD-trailing** evaluation traded on Micro Gold (MGC).

## Strategy (fixed in advance)
- **Signal:** 20/100 EMA trend on daily gold; long above, short below. Position applied next day (no look-ahead).
- **Overlay:** hard **12-point stop** per trade; **dynamic sizing** so even a full stop-out stays above the
  trailing floor (1.5x safety); base **3 MGC**, capped at Apex's 10-contract limit; size scales up only as the buffer grows.
- **Account:** Apex **$50k, EOD-trailing** (chosen because the floor doesn't ratchet on intraday spikes).

## Rules modelled (verified 2026-08-02)
Target $3,000 (6%); trailing drawdown $2,500; NO daily loss limit; consistency is payout-only (not in eval);
trailing floor locks to +$100 once balance reaches +$2,600. MGC = $10/point, ~$3 round-trip cost.

## Pre-registered expectation
- **Optimistic backtest (spot proxy, daily bars, perfect stop fills): ~51% pass rate, median ~19 days.**
- **Honest real-world expectation after haircut: ~35-45%.** The proxy can't see every intraday spike, and
  stops won't fill perfectly. This is a *favourable-odds, expect-variance* play, NOT a sure thing.

## What would FALSIFY this (pre-committed)
- Forward paper on the **real MGC contract** passes < ~30% over a meaningful number of attempts -> abandon.
- The underlying gold trend edge dies: the `fast_pure` challenger stops beating the champion in the gold
  research lab, or its deflated Sharpe stays < 0.90 -> the whole premise is gone.
- Stops slip materially worse than modelled -> re-cost and re-test before trusting any number.

## Hard constraints
Paper / simulation only. Real-money funding of an Apex evaluation stays gated behind the F-1 steps
(written immigration-attorney opinion + DSO sign-off + explicit approval). Building and paper-validating
does not touch that line; funding an account does.
