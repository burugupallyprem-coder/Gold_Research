# Advanced Price Action (3-drives + falling wedge + long-bar breakout) — XAU_USD
_Run 2026-07-23 on real cached M15 gold data (2019-01 → 2026-06). RESEARCH ONLY. Nothing deploys._

Operationalized faithfully (uptrend context → contracting falling-wedge pullback that
held support as a higher low → long bullish breakout bar above the wedge → next-bar entry,
stop at wedge low, 1:2-ish target). Grid = {M15 scalp, H1 intraday} × breakout_atr {1.5,2.5}
× rr {1.5,2.5} × wedge_len {12,20}. Cost 0.40/side (1×), stressed 3×. Train ≤2023-12,
validation 2024-01→2026-06. **Buy-and-hold gold over validation: +109.7%.**

## All 16 combos (train | validation | validation @3× cost)

### M15 (scalp)
| breakout_atr | rr | wedge | train | val | val @3× |
|---|---|---|---|---|---|
| 1.5 | 1.5 | 12 | 122t −0.280R | 42t +0.185R | +0.046R |
| 1.5 | 1.5 | 20 | 96t −0.107R | 41t +0.512R | +0.403R |
| 1.5 | 2.5 | 12 | 121t −0.169R | 42t +0.270R | +0.131R |
| 1.5 | 2.5 | 20 | 96t −0.181R | 39t +0.541R | +0.433R |
| 2.5 | 1.5 | 12 | 40t −0.223R | 8t +0.423R | +0.311R |
| 2.5 | 1.5 | 20 | 37t −0.097R | 20t +0.627R | +0.521R |
| 2.5 | 2.5 | 12 | 40t −0.097R | 8t +0.701R | +0.589R |
| 2.5 | 2.5 | 20 | 37t −0.149R | 20t +0.524R | +0.418R |

### H1 (intraday)
| breakout_atr | rr | wedge | train | val | val @3× |
|---|---|---|---|---|---|
| 1.5 | 1.5 | 12 | 23t +0.149R | 15t −0.015R | −0.063R |
| 1.5 | 1.5 | 20 | 21t −0.133R | 9t −0.441R | −0.479R |
| 1.5 | 2.5 | 12 | 23t +0.133R | 15t −0.113R | −0.161R |
| 1.5 | 2.5 | 20 | 21t −0.041R | 9t −0.330R | −0.368R |
| 2.5 | 1.5 | 12 | 8t +0.694R | 6t +0.098R | +0.030R |
| 2.5 | 1.5 | 20 | 12t +0.173R | 3t −0.193R | −0.246R |
| 2.5 | 2.5 | 12 | 8t +0.619R | 6t +0.269R | +0.201R |
| 2.5 | 2.5 | 20 | 12t +0.250R | 3t +0.140R | +0.088R |

## Verdict: FAIL (informational). Nothing earns even a paper trial.

Three independent reasons, any one of which is disqualifying:

1. **Too rare to trade — fails the sample gate outright.** The gate needs ≥100 validation
   trades. The *most* any combo produced is **42** (and the higher-quality-filter combos got
   3–20). Over 2.5 years and 174,659 M15 bars, this pattern fires a few dozen times. You
   cannot run a "scalp" or "intraday" strategy that trades ~15×/year, and you can't trust
   any expectancy measured on 8–42 samples — variance dominates completely.

2. **Negative on train wherever it trades enough to matter.** Every M15 combo with a real
   sample (96–122 trades) is **negative on train** (−0.10R to −0.28R). The only positive
   train numbers come from H1 combos with 8–23 trades — i.e. noise.

3. **The validation "wins" are gold beta, not edge.** Gold rose **+109.7%** over the
   validation window. A long-only pattern in a market that more than doubled will print
   positive validation R almost regardless of whether the signal predicts anything. The
   expectancy swinging from −0.44R to +0.70R between neighbouring parameter settings on
   tiny samples confirms there is no stable signal underneath — just a long-beta tailwind
   sampled a few dozen times.

## Honest read
The pattern is real and looks compelling on a hand-picked chart precisely because the eye
selects the clean instances and skips the failures. Measured mechanically over 7 years it is
(a) far too infrequent to be an intraday/scalp system and (b) indistinguishable from "be long
gold during a gold bull market." That is the same lesson every discretionary chart pattern in
this project has returned. A good backtest that says *no* — cheaply, before any capital — is
the apparatus working as designed (see VERDICT.md).
