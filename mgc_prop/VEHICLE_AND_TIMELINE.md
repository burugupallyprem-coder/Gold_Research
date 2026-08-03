# Vehicle Selection & Deployment Timeline (honest)

## Cross-instrument ranking — long-only trend, real Databento data, Apex $50k EOD
| Instrument | Sector | Pass rate | Median days |
|---|---|---|---|
| **MGC — Gold** | metals | **44.4%** | 46 |
| MES — S&P 500 | equity | 32.4% | 38 |
| MNQ — Nasdaq | equity | 32.4% | 29 |
| MBT — Bitcoin | crypto | 28.7% | 57 |
| MCL — Crude | energy | 23.0% | 53 |
| M6E — EUR/USD | fx | 7.9% | 119 |

**Decision: GOLD (MGC).** Beats the next-best (indices, 32%) by 12 points — clear even after discounting the
winner for best-of-6 multiple testing. Gold was the pre-committed choice, so this is confirmation, not
cherry-picking. Forex is unusable for this strategy (8%); crude weak; crypto/indices middling.

**Method note:** the cross-instrument test uses an ATR-scaled stop (required to compare instruments of very
different scales). Gold's *deployment* config uses the fixed 12pt stop and runs ~48% real-fills / ~62% clean — the
44.4% here is a ranking proxy, not the exact deployment number. Standard caveats apply: optimistic (daily bars,
modeled fills), wide confidence interval, overlapping windows.

## Honest deployment timeline (from today)
**1. Forward paper — ~2–3 months.** Purpose: validate the live pipeline is bug-free (this step just caught a
look-ahead bug), watch 1–3 real combines, and see behavior in the current gold regime. NOT statistical proof —
the CI is too wide for a few combines to prove the pass rate.

**2. Apex evaluation — ~3–6 months, 2–3 attempts.** At ~45% pass/attempt:
- >50% of individual attempts FAIL — expect to blow some; a 45% strategy is supposed to.
- A *passing* attempt takes a median ~6–9 weeks (26–46 trading days).
- Expected ~2–3 attempts to get one pass → ~3–6 months sequential.
- **Variance is large:** best case ~6 weeks / one attempt; worst case 6–12 months / several attempts,
  especially if gold turns choppy (pass rate drops well below 45% in non-trending regimes).

**Total to a funded account: ~5–9 months, wide band.**

## Accelerant and hard truths
- **Parallel accounts** (Apex allows many) shorten calendar time — more simultaneous shots per cycle, at more
  fees. Legitimate approach.
- **Passing ≠ getting paid.** A funded account carries the SAME trailing-drawdown risk (it can be blown) and
  reaching a payout is a further process. "Funded" is a milestone, not the finish line.
- **Real-money funding is gated by the F-1 / legal step** (attorney opinion) — the one item outside the
  strategy's control and not on this timeline.
