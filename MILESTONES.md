# Gold Quant Lab -- Build Journey & Milestones

A running record of what this project became, and the milestones cleared on the
way to a fully autonomous, self-validating gold trading bot running in the cloud.

Built solo, with an AI pair-builder, by someone who refused to ship hype.

---

## What this is, in one breath

An autonomous quant system for spot gold (XAU/USD) that researches, backtests,
validates, paper-trades on OANDA, and reviews its own results -- unattended, in
the cloud, with a human approving every strategy change. Its proudest feature is
that it tells the truth, even when the truth is "this idea has no edge."

---

## Milestones cleared

- [x] **Ported a real strategy faithfully.** Took a popular TradingView "Gold SMC
  v8" intraday system and re-implemented it in Python, end to end.
- [x] **Built an honest backtester.** Event-driven engine with no look-ahead,
  realistic spread/slippage, and cost-stress -- plus a vectorized path proven
  bar-for-bar equivalent to the reference.
- [x] **Falsified my own first idea.** Walk-forward + out-of-sample testing over
  5+ years showed the SMC strategy has NO EDGE after costs. Killed it instead of
  fooling myself. (This is the milestone most people skip.)
- [x] **Found a real, documented edge.** Pivoted to a Macro-Trend strategy:
  time-series momentum + a real-yield (TIPS) filter + volatility targeting.
- [x] **Validated it on 7-10 years of real gold data.** Modest but genuine:
  out-of-sample Sharpe that survives 5x costs; full-sample Sharpe ~0.5 with a
  ~36% max drawdown -- reported honestly, no cherry-picking.
- [x] **Went fully cloud-autonomous.** GitHub Actions runs data refresh,
  backtests, validation, research, and paper execution on a schedule -- laptop
  closed, nothing left running on my machine.
- [x] **Built a self-improving research lab.** A champion/challenger loop with a
  permanent holdout and a 3-week confirmation streak, engineered specifically to
  resist overfitting -- and it never promotes a strategy without my approval.
- [x] **Built a self-learning loop (human-in-the-loop).** The bot records its own
  trades, reviews how the live paper account actually performs vs the backtest,
  and emails a warning proposing any change -- which only takes effect when I
  approve it.
- [x] **Added an anomaly stand-down filter.** Flags genuinely abnormal days
  (0.8% of all days) and can sit them out; validated across 10 years.
- [x] **Tested intraday -- and honestly rejected it.** Backtested H4 and M15
  versions; costs destroyed the edge (M15 net Sharpe -1.6). Knowing what NOT to
  ship is its own win.
- [x] **First end-to-end live paper decision.** The bot connected to OANDA,
  priced gold, ran the champion, and produced a real position decision in the
  cloud:

  ```
  [PAPER] champion `baseline` on XAU_USD
  Target weight +0.49 | price 4259.97 | NAV 100000
  Current units +0 -> target +11 (order +11, rebalance)
  Cap: 1x NAV. Practice account only -- no real capital.
  ```

---

## Where it stands right now

- The full research + validation + paper pipeline runs autonomously in the cloud.
- The strategy is validated and live on the OANDA **practice** account.
- Final step in progress: flipping paper execution from simulated (`DRY`) to
  `LIVE-paper` by wiring the OANDA account credential into the cloud, so orders
  actually register on the practice account.

---

## What's next

- Finish `DRY -> LIVE-paper` so practice orders register.
- Accumulate a real live-paper track record (months) and let the self-learning
  loop work on actual data.
- Build the H4 confirmation layer for real (real logic + real-data backtest),
  then attach it as a human-approved pre-trade caution filter.
- Cross-asset confirmation (silver, broad commodities) for robustness.
- A live dashboard to make the whole system visible at a glance.

---

## The honest disclaimer

Educational research on a **paper** account. **Not financial advice.** No
strategy here is promised to be profitable; the entire point of the system is to
test that claim rigorously -- and to say so plainly when the answer is no. The
value is the engineering and the discipline, not a guaranteed return.

*Built with a bias toward truth over hope.*
