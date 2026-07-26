# "Advanced Price Action" on Gold — Rigorous Test & Verdict: **NO-GO**
_Run 2026-07-22 on real XAU_USD data (M15 2019–2026; H1/H4 resampled). Paper/backtest only. Not financial advice._

**Verdict: do not deploy.** The setup is either too rare to validate (looks great on H4 with
38 trades) or has no edge once there's enough data to trust it (breakeven at H1 and M15). The
apparent profits are concentrated in one or two strong-trend years and vanish in the rest — the
exact small-sample mirage your gate exists to catch.

## What was tested (the screenshot, operationalized)
The chart shows a **demand-zone retest**: price pulls back into a key support level in a
contracting **falling wedge** (lower highs), then a **large bullish "long bar" breaks the
pullback high** → enter, stop under the zone, fixed-R targets (TP1/TP2). I encoded exactly that,
plus the bearish mirror:
- Entry (long): a bar with body ≥ 1×ATR that closes above the prior *pullback* high, where the
  pullback (a) made lower highs and (b) reached down within 1×ATR of the demand zone (rolling base low).
- Stop = pullback low − 0.1×ATR. Target = entry + RR×risk. One position at a time; time-stop after
  the hold window. Cost 0.40 gold points round-trip.
- Swept a fair grid: **3 timeframes × {long, long+short} × {trend filter off/on} × RR{1.5, 2.0}** = 24 runs.
- Gate: **≥100 trades, ≥ +0.05R expectancy, PF ≥ 1.15, ≥ 60% of quarters positive.**

## Results — nothing passes
Best config per timeframe (long-only, RR 2.0):
| TF | Trades | Exp (R) | PF | Quarters + | Gate | Note |
|---|---|---|---|---|---|---|
| **H4** | 38 | +0.457 | 2.26 | 47% | ❌ | Too few trades to trust; fails on N and consistency |
| **H1** | 122 | +0.027 | 1.05 | 43% | ❌ | Edge gone at scale |
| **M15** (scalp) | 456 | +0.020 | 1.03 | 60% | ❌ | Expectancy far below +0.05 gate |

Adding shorts made every timeframe worse (gold's uptrend punishes the bearish mirror): M15
long+short ran −0.06 to −0.10R, PF < 0.92.

## Why the H4 number is a trap (per-year of the "best" config)
H4 long, RR 2.0 — 38 trades over 7 years, +0.457R average:
| 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| 9 tr, +0.99 | 5 tr, +0.46 | 3 tr, +0.98 | 3 tr, +0.79 | 9 tr, −0.02 | 1 tr, −0.92 | 7 tr, +0.31 | 1 tr, −0.19 |

The whole result rests on ~20 trades in 2019–2022. Some years have **1–3 trades**. That is not a
strategy you can size or trust — it's a handful of lucky fills. The moment you drop to H1/M15
where the sample is real, expectancy falls to ~zero.

The same concentration shows at every scale:
- **H1 long**: 2019 alone = +16.9R; 2021, 2022, 2023 each **negative** (−8, −8, −6R). Remove 2019 and it's a net loser.
- **M15 long**: 2025 alone = +22.4R; 2019, 2022, 2023 negative (2022 = −14.8R). One great trend year masks a no-edge system.

## Why it doesn't hold up (mechanism)
1. **Discretionary pattern, not a persistent edge.** "Wedge retest + long bar" is easy to see in a
   curated screenshot after the fact; as a mechanical rule its winners cluster in strong directional
   years and it chops out otherwise.
2. **Scale kills it.** Rare setups (H4) can't be validated; frequent ones (M15) get eaten by the
   spread — the per-trade edge is smaller than the cost you pay.
3. **Long-biased by construction here** — like the SMC stack, it mostly worked because gold rose.

## Recommendation
No paper deployment. It fails the same gate that already rejected raw ORB, VWAP/momentum, and the
gold ORB port. Your two gold approaches with actually-defensible (if modest) edges remain:
- **Daily macro-trend** (`fast_trend`): ~0.6 Sharpe, survives 5× costs.
- **Intraday SMC stack**: +0.14R/trade at realistic cost (cost-fragile — see `rigorous_backtest_2026-07-22.md`).

This is the discipline doing its job: a great-looking chart pattern, tested honestly across
timeframes, shows no edge on gold once you demand enough trades to believe it.
