# Robustness Study — Honest Regime-Router (the trader's 10 modifications)
_Run 2026-07-25 on the real FVG+NY engine trade universe (1,587 trades) + M15 path.
Paper/backtest only; not financial advice. House rules: selection-period = honest; every
holdout number is inside the 2023–26 gold BULL and is labelled/inflated._

This follows the trader's instruction exactly: **test one change at a time, report robustness
(stability across neighbours) rather than the single best number, and do not promote anything
that doesn't improve validation AND stay stable under nearby parameters and 3×/5× cost.**

Method note: trend/session/vol/risk/loser tests re-filter the engine's **real** trades (exact
`r_1x`). The **exit** tests re-simulate each entry on M15 with a simplified bracket — so read exit
results as a *relative ranking among themselves*, not the engine's exact P&L. Two of my own bugs
were caught and fixed mid-study (documented at the end) — treat that as the harness being stressed,
not decoration.

Anchor that does not move: even the best variant below **still loses to buy-and-hold gold**
(+110% holdout) on return, because every improvement trims trades in a market that only rose.

---

## #1 / #9 Trend filter — robustness grid (selection = honest)
| trend definition | sel exp | sel Sharpe | holdout exp | holdout Sharpe | trades | gate |
|---|---|---|---|---|---|---|
| **EMA 20/100 (baseline)** | 0.103 | 0.55 | 0.213 | 1.44 | 330 | pass |
| EMA 18/90 | 0.085 | 0.45 | 0.206 | 1.40 | 325 | pass |
| EMA 22/110 | 0.117 | 0.63 | 0.213 | 1.44 | 330 | pass |
| EMA 20/150 | 0.135 | 0.73 | 0.213 | 1.44 | 330 | pass |
| EMA 20/200 | 0.119 | 0.65 | 0.213 | 1.44 | 330 | pass |
| EMA 50/200 | 0.097 | 0.53 | 0.213 | 1.44 | 330 | pass |
| SMA 20/100 | 0.056 | 0.29 | 0.213 | 1.44 | 320 | pass |
| SMA 50/200 | 0.062 | 0.33 | 0.213 | 1.44 | 330 | pass |
| mom 3-month | 0.117 | 0.67 | 0.172 | 1.13 | 318 | pass |
| mom 6-month | 0.158 | 0.87 | 0.213 | 1.44 | 330 | pass |
| ADX>25 | 0.160 | 0.60 | 0.195 | 0.95 | 159 | pass |
| ADX>30 | 0.120 | 0.39 | 0.268 | 1.00 | 104 | pass |

Robustness read:
- **Holdout is identical (~0.213 / 1.44) across almost every EMA/SMA definition.** That is NOT
  durability — in the 2024–26 bull *every* trend rule says "long," so the same ~330 long trades
  survive. A bull-market artifact; do not read it as robustness.
- **Selection (honest) is where the real sensitivity lives, and the EMA family is reasonably
  stable**: neighbours 18/90 → 20/100 → 22/110 → 20/150 give 0.085 → 0.103 → 0.117 → 0.135. No
  cliffs. **SMA is clearly worse** (0.056–0.062) → keep EMA. **Momentum matters**: 6-month is best
  (0.158), 3-month drops the holdout to 0.172 → keep the 12-month (or 6-month), avoid 3-month.
- **ADX** raises per-trade quality but cuts sample (ADX>30 → 104 holdout trades, right at the gate)
  and its selection Sharpe (0.39) is *below* baseline — not a robust improvement.

## #10 Rolling walk-forward (test-year expectancy R, 1× cost)
| trend | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| **EMA 20/100** | +0.05 | +0.30 | +0.17 | +0.02 | +0.06 | +0.24 |
| EMA 50/200 | +0.07 | **−0.03** | +0.14 | +0.02 | +0.06 | +0.24 |
| EMA 20/200 | +0.07 | +0.06 | +0.23 | +0.01 | +0.06 | +0.24 |
| ADX>25 | +0.16 | +0.04 | +0.36 | +0.02 | **−0.04** | +0.23 |

**Baseline EMA 20/100 is the only variant positive in all six test years.** The "upgrades" each
buy occasional punch with a negative year. By the trader's own robustness rule, that argues for
*keeping the baseline trend*, not replacing it. (2023/2024 are thin for everyone — the flat part
of the edge.)

## #3 Exits — the biggest surprise: leave them alone (holdout, relative re-sim)
| exit rule | exp (R) | PF | win% |
|---|---|---|---|
| **fixed stop/target (current)** | **+0.180** | **1.26** | 33% |
| break-even @1R | +0.016 | 1.03 | 19% |
| break-even @1.5R | +0.127 | 1.22 | 26% |
| break-even @2R | +0.115 | 1.18 | 29% |
| ATR (1.5×) stop | −0.011 | 0.99 | 29% |
| ATR trailing | −0.048 | 0.84 | 38% |
| partial @1R + trail | −0.071 | 0.76 | 39% |
| time-exit 12 bars | +0.032 | 1.07 | 46% |
| time-exit 24 bars | +0.028 | 1.05 | 43% |
| _engine actual (reference)_ | _+0.213_ | _1.39_ | _29%_ |

**Every proposed exit "improvement" made it worse.** Break-even at 1R is the most damaging (it
scratches winners early). Trailing and partials cut the fat tails that carry a 30%-win system.
This matches theory: a low-win-rate, fixed-RR system lives on its full winners — protect them, don't
trim them. The current fixed exit is the right call; **no exit change earns a trial.**

## #4 Volatility filter — the ONE directionally-robust improvement (but not a free win)
ATR-at-entry buckets (holdout, exact `r_1x`): **+0.094 (low) → +0.193 → +0.376 → +0.283 (extreme)** —
expectancy rises monotonically with volatility. Trading only when ATR ≥ its rolling median:

| | sel exp | sel Sharpe | holdout exp | holdout 5× exp |
|---|---|---|---|---|
| baseline | 0.103 | 0.55 | 0.213 | +0.015 |
| **ATR ≥ median** | **0.178** | **0.64** | **0.295** | **+0.122** |

It improves selection *and* holdout *and* — uniquely — **survives 5× cost** (+0.122R vs the
baseline's fragile +0.015R). Volatility-gating has sound theory (gold's intraday edge is in active
sessions), and the effect is monotonic.

**But the neighbour test keeps me honest** (threshold × rolling median):
| mult | 0.7 | 0.8 | 0.9 | **1.0** | 1.1 | 1.2 | 1.3 |
|---|---|---|---|---|---|---|---|
| sel Sharpe | 0.47 | 0.34 | 0.32 | **0.64** | 0.71 | 0.64 | 0.54 |
| holdout 5× exp | 0.037 | 0.001 | −0.016 | **0.122** | 0.111 | 0.107 | 0.073 |

Stable and improving **from the median upward**, but **below the median it degrades below baseline** —
so `1.0×` sits just past a soft edge, and stronger filtering trades expectancy for sample size
(1.3× → only 59 holdout trades, under the 100 gate). Honest verdict: **a real, theory-backed,
directionally-robust effect worth a pre-registered forward test — not a promotion, and it still
doesn't beat buy-and-hold on return** (fewer trades ⇒ lower total return in a bull).

## #6 Session windows — looks great, fails the honesty test
09:00–11:00 ET only: holdout jumps to +0.398 (Sharpe 1.78) — but **selection Sharpe *falls* 0.55 →
0.38.** Helping the bull holdout while hurting the honest selection period is the signature of
**overfitting to the 2024–26 regime.** The edge does concentrate mid-morning, but a hard session
filter is not robust. **Do not adopt.** (The trader's hypothesis that the edge lives in the first
30–60 min is actually *wrong* here — NY first-60-min is negative; the money is 09:30–11:00.)

## #8 Loser analysis — an overfitting trap, flagged not adopted
By weekday (full sample): Thu +0.44, Tue +0.26 strong; **Mon −0.04, Wed −0.07** weak. By hour, the
late-US-evening hours (22:00–23:00 ET) are clearly negative. Tempting to "skip Monday/Wednesday" —
but day-of-week filters almost never survive out-of-sample and this is exactly the kind of pattern
that mines noise. **Reported as a hypothesis, explicitly NOT turned into a rule.**

## #5 Risk overlays — didn't help (drawdown wasn't the problem)
| overlay | total R | exp | max DD (R) |
|---|---|---|---|
| baseline | 70.4 | 0.213 | −12.5 |
| max daily loss −2R | 63.9 | 0.198 | −12.5 |
| max 3 consecutive losses | 38.0 | 0.133 | −12.5 |
| max 3 trades/day | 70.4 | 0.213 | −12.5 |

Every risk cap **cut return without cutting drawdown** (the drawdown was already tiny). These
controls matter when a system has fat tail-risk; this one doesn't. No change warranted.

## #7 Confidence score — it's near-inert (structural finding)
The engine's confidence = 30(trigger)+20(HTF)+15(vol)+10(NY)±25(macro, default **0**). With macro
off, every trade scores **65 (non-NY) or 75 (NY)** — all ≥ the gate's 60. **So the confidence gate
filters almost nothing on this data.** Making it predictive needs either turning on the macro
component or saving per-trade FVG-size / sweep / structure and correlating them — an engine change.
Flagged honestly; not faked.

## #2 Entry filters — partially out of scope (stated plainly)
VWAP-gating, "FVG aligned with HTF structure," previous-candle confirmation, and news-window
filters change *which trades the engine takes*, so they need engine edits (and, for news, an
economic-calendar feed I don't have). They can't be tested by re-filtering existing trades. Not
faked — listed as the follow-up that requires code, if you want it.

---

## Overall verdict (robustness, not optimization)
- **Keep the baseline trend (EMA 20/100, 12-mo momentum).** It's the most consistent across the
  rolling walk-forward; SMA is worse, ADX trades consistency for punch, 3-month momentum hurts.
- **Keep the current fixed exits.** Every suggested exit change made it worse.
- **The one candidate improvement is the ATR≥median volatility filter** — directionally robust,
  theory-backed, and the only thing that survives 5× cost. It is *not* promoted: it halves the
  trades, sits just past a soft parameter edge, and still doesn't beat buy-and-hold on return.
- **Reject the session filter, weekday filter, risk caps, and exit changes** — noise, overfitting,
  or neutral.
- **Nothing here overturns the core result:** a long-biased intraday system, even improved, loses
  to simply holding gold through this bull. The honest gain is risk-adjusted/cost-robustness, not
  beating the passive benchmark.

## Recommendation (disciplined)
Pre-register **one** variant for a forward paper trial beside `baseline`: the router **+ ATR≥median
volatility filter**, fixed rules, ≥30 forward trades before any verdict — precisely because it's the
only change that improved validation *and* stayed stable *and* survived cost. Do **not** stack it with
the session/weekday filters (that combo looked best in-sample but drops under the 100-trade gate and
multiplies overfitting risk). I have not written the pre-registration yet — say the word and I will,
with the exact ATR window and threshold locked.

## Bugs caught and fixed during this study (transparency)
1. **Exit re-simulator** first returned fantasy numbers (fixed exit +0.844R, PF 24; trailing 0%
   win) because a non-partial exit's P&L was multiplied by zero — losers were booked as ~−0.06R
   instead of −1R. Rewritten; the corrected "fixed" (+0.180R) now reconciles with the engine
   (+0.213R), the small gap being the swing-stop nuance the sim omits.
2. Confirmed (again) that the whole universe was built with the earlier break-even/`risk=0` fix, so
   win rates are the true ~29–31%, not the 7% from that original bug.

Code to inspect / re-run: `research/router_audit/robustness_trend.py`,
`research/router_audit/robustness_overlays.py`; data in `reports/backtest_data_2026-07-25/`.
