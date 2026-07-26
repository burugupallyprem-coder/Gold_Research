# Advanced Price Action — Breakout+Retest Engine on Gold — Verdict: **NO-GO**

_Run 2026-07-25 on real XAU_USD M15 (2019-01→2026-06, 174,659 bars). Standalone,
read-only; touches nothing in the live bot. Paper/backtest only. Not financial advice._

**This corroborates the earlier NO-GO** in
`reports/advanced_price_action_gold_2026-07-22.md` with a *different*
implementation and one test that writeup didn't run (a random-entry control).
Two independent encodings of the screenshot now reach the same conclusion.

---

## What was tested

Peter chose the **breakout+retest engine only** — the tradable core stripped of
the 3-drives topping context: *break a confirmed resistance level → pull back and
retest it → enter long on the bullish reclaim bar → stop below the retest low →
fixed-R target.* Long-only (matches the bullish illustration and the project's
long-or-flat ethos). ATR-normalized thresholds, entry on next-bar open, stop-first
intrabar, costs both sides (gold 0.40/side, 0.80 round-trip). Last 12 months sealed.

This differs from the 2026-07-22 test, which encoded the fuller "demand-zone +
falling-wedge + long bar" pattern. Same idea, different mechanization — a useful
robustness check on the conclusion.

---

## Results

| | In-sample (2019→2025-06) | Sealed holdout (last 12m) |
|---|---|---|
| Trades | 3,217 | 498 |
| Win rate | 36.1% | 37.8% |
| Avg R (net) | −0.270 | −0.040 |
| Total R (net) | **−867.6** | **−19.7** |
| Profit factor | **0.66** | **0.94** |
| **Gross total R (no costs)** | **+70.4** | **+22.7** |
| Buy-and-hold gold Sharpe | +0.94 | +0.96 |

Read the two bold rows together — they are the whole story:

**Before costs, there is almost no edge.** +70.4R across 3,217 trades is
**+0.022R per trade** gross. The holdout is +0.046R gross. The 2026-07-22 test
measured the same thing independently: **+0.020R** expectancy at M15. Three
encodings, one answer: the gross edge is ~+0.02R/trade — statistically a rounding
error.

**Costs then bury it.** Median R is 3.36 points in-sample, so the 0.80-point
round-trip is **23.8% of risk on every trade**. A +0.02R gross edge cannot survive
a 0.24R toll. Net expectancy goes to −0.27R and the equity curve is destroyed.

---

## The random-entry control (new vs the 2026-07-22 test)

Same breakouts, same R geometry and bracket, but enter at a **random bar** in the
retest window instead of at the reclaim. 300 seeds:

| | PA | Random mean | PA percentile |
|---|---|---|---|
| In-sample total R | −867.6 | −894.8 | 66 |
| Holdout total R | −19.7 | −24.5 | 58 |

PA is a hair better than random (66th / 58th percentile) but **both are heavily
negative and PA sits inside the random distribution.** The "retest timing" — the
supposed skill in the screenshot — adds no usable information. You are not being
paid for the pattern; you're paying spread to trade a coin flip after a breakout.

---

## Cost stress and sensitivity

- **Cost stress** (in-sample): 1× PF 0.66 → 3× PF 0.28 → 5× PF 0.12. Monotonic
  collapse — costs are unambiguously the mechanism of death.
- **Sensitivity:** all 11 variants negative. The widest break margin (fewest,
  highest-quality trades: n=1201) is the "best" at PF 0.72, Sharpe −1.85 — still a
  clear loser. Bigger targets, longer retest windows, different pivot widths: every
  knob stays underwater. This is not a tuning problem; there is nothing to tune
  toward.

---

## Why it fails (mechanism)

1. **No persistent edge.** "Break, retest, reclaim" is obvious in a curated
   screenshot after the fact. As a mechanical rule the gross expectancy is ~+0.02R
   — indistinguishable from zero, and indistinguishable from random entry.
2. **Gold's microstructure eats it.** At M15 the per-trade edge is far smaller than
   the spread+slippage you pay to capture it. This is the identical failure that
   killed the SMC stack and the raw ORB on this instrument.
3. **Long-biased by construction.** Whatever tiny positive gross exists leans on
   gold's 2019–2026 uptrend, not on the pattern.

---

## Honest limits

- 3,217 in-sample trades is a large, trustworthy sample — the opposite of the
  H4-with-38-trades trap in the 2026-07-22 writeup. The negative verdict here is
  well-powered.
- One instrument, one bull regime. But the failure is a *cost/no-edge* failure, and
  a friendlier regime wouldn't manufacture a gross edge that isn't there.
- This is the breakout+retest core, not the full 3-drives stack. The 2026-07-22
  test covered the fuller pattern and also failed, so both ends of the fidelity
  range are now checked.

---

## Verdict

**NO-GO. Do not paper-deploy.** It fails the same gate that already rejected raw
ORB, VWAP/momentum, the gold ORB port, SMC, and (on 2026-07-22) this very pattern.

The project's two defensible gold approaches are unchanged and remain the only
things with a real (if modest) edge:
- **Daily macro-trend** (`baseline`/`fast_trend`): ~0.5–0.6 Sharpe, survives 5× costs.
- keep everything else in the research bin.

This is the discipline working exactly as intended: a great-looking chart pattern,
tested honestly with enough trades to believe the answer, shows no edge on gold —
and the random-entry control proves the "skill" in the setup is illusory.

Artifacts: `analysis/pa_breakout_retest.py`, `reports/pa_breakout_insample.txt`,
`reports/pa_breakout_holdout.txt`.
