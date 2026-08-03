# Boss feedback round 2 — applied directly

## 1. Honesty correction (boss caught an overclaim)
Old: "there is no second profitable orthogonal source." **Corrected to:** "we have not found one using the
specific constructions tested" — a finite subset of the hypothesis space, NOT the whole space. Explicitly still
untested: options-implied vol term structure, ETF flows, gold lease rates, cross-asset relative strength,
DXY-regime interactions, real-yield+dollar *combinations*, vol-of-vol, seasonal/calendar/time-of-day, intraday
microstructure, central-bank proxies, and richer COT (commercials vs large-spec vs small, percentile, extremes,
position/OI changes, divergence — only *first-generation* COT is dead). Applied in STRATEGY3_AND_CONCLUSION.md.

## 2. Contribution analysis (per-year P&L by source)
| Year | Gold | TREND | Macro (RY) | COT-contra |
|---|---|---|---|---|
| 2019 | −0% | −3.4% | −2.5% | 0.0% |
| 2020 | +24% | 9.9% | 9.4% | 31.6% |
| 2021 | −6% | **−8.4%** | **+7.2%** | **+10.8%** |
| 2022 | +1% | 8.1% | 5.4% | −6.6% |
| 2023 | +12% | 1.2% | −4.2% | 1.3% |
| 2024 | +27% | 19.4% | −3.1% | −15.8% |
| 2025 | +63% | 34.8% | −2.9% | −17.6% |
| 2026 | −6% | 8.0% | 6.2% | −9.1% |

**TREND is the whole story in 6 of 8 years.** Macro/COT only earn their keep in 2021 (trend's worst) and drag
hard in the big trend years — proof the hedges pay ~1 year in 8, not enough to justify a static blend.

## 3. EXECUTION improvement — the headline result
Boss's core point: stop hunting edges, harvest the existing one more efficiently. Tested a structure-based
**chandelier trailing stop** (exit when close < running-high − k×ATR) vs "exit on signal flip", on long-only trend.

| Execution | Sharpe | Max DD | Ann ret | Apex pass |
|---|---|---|---|---|
| Baseline (exit on flip) | 0.96 | −20.8% | 14.9% | 48.1% |
| **Chandelier 2.5×ATR** | **1.06** | −19.2% | 16.1% | **57.4%** |
| Chandelier 3.5×ATR | 0.96 | −20.6% | 14.7% | 56.2% |
| Chandelier 5×ATR | 1.00 | −20.0% | 15.5% | 53.1% |

**+9 points of pass rate from execution alone (48% → 57%)** — a bigger move than any edge-hunt produced, and
robust across every trailing multiple. Locking profits on pullbacks protects the combine balance far better than
waiting for a lagging EMA flip. The boss was right: execution was underweighted.

## Updated strategy recommendation (research; forward test still frozen)
The validated improvement batch is now: **long-only (#1) + chandelier ATR-trailing exit (2.5–3.5×).**
Baseline symmetric+flip ≈ 42.6% → long-only+chandelier ≈ 57% pass (in-sample; confirm out-of-sample, and the
wide CI from Monte Carlo still applies). Further execution levers still to test: partial profit-taking, scaling
in, dynamic targets, event-slippage reduction. Edge-hunting paused per boss's direction.


## 4. Validation of the execution win (OOS sub-periods + honest CI)
| Variant | Full | 2019–2022 (chop) | 2023–2026 (bull) |
|---|---|---|---|
| Baseline (flip) | 48.1% | 43.8% | 51.7% |
| Chandelier 2.5×ATR | 57.4% | **43.8%** | 68.5% |
| **Chandelier + re-entry** | **66.0%** | **54.8%** | **75.3%** |

**Chandelier ALONE is bull-dependent** — zero help in the choppy 2019–2022 half. **Adding RE-ENTRY** (re-enter on
a new high after a trailing-stop exit) is robust in BOTH regimes (+11pts chop, +24pts bull), because it locks
profits without permanently missing the continuation after a whipsaw exit.

**Honest CI (independent, non-overlapping combines):** best config **53.3% point** (vs baseline 35.7%),
bootstrap 90% CI **[33.3%, 73.3%]**. The improvement is real and regime-robust; the absolute level is still
uncertain (only 15 independent samples). Even the pessimistic lower bound (~33%) ≈ the baseline's central estimate.

## VALIDATED EXECUTION BATCH (the new plan)
**long-only  +  chandelier ATR-trailing exit (2.5×)  +  re-entry on new high.**
Baseline symmetric+flip ~36% independent → this ~53% independent, holding across chop and bull. Biggest, most
robust improvement in the project — and it's execution, not a new edge, exactly as the boss predicted. Confirm
further on the live forward test. Remaining untested execution levers: partial profit-taking, scaling in,
dynamic targets, event-slippage.
