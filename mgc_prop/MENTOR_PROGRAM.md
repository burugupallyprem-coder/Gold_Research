# Mentor Improvement Program — running log

Your mentor's 7-step program to pressure-test the edge. Each test logged honestly as we go,
including where it hurts. Research/validation only; the live forward test is noted separately.

Core premise (agreed): the only edge is "gold trends." Everything else is engineering. The
biggest weakness is a SINGLE return source (trend). The real prize is an ORTHOGONAL source
that pays when trend doesn't — pursued after these diagnostics.

---

## #1 — Long-only vs short-only vs symmetric  ✅ DONE
Gold, 2019–2026, turnover cost + friction.

| Variant | Ann ret | Sharpe | Max DD | % in mkt | Apex pass |
|---|---|---|---|---|---|
| **Long-only** | 14.9% | **0.96** | **−20.1%** | 70% | **48.1%** |
| Short-only | −0.5% | −0.06 | −17.6% | 30% | 12.3% |
| Symmetric (current) | 14.5% | 0.83 | −28.3% | 100% | 42.6% |

**Result:** long-only dominates — higher Sharpe, shallower drawdown, +6-pt Apex pass, less trading.
Shorts are a confirmed money-loser and (contrary to the "shorts reduce drawdown" prior) they
*deepened* drawdown, because gold's structural uptrend meant short trades just bled in pullbacks.

**Decision:** adopt **long-only**. Clear structural win, not a curve-fit threshold.

**Honest caveat:** long-only *sharpens* bull-dependence. In a multi-year gold BEAR it simply sits
flat (0 position when trend is down) — it won't bleed like symmetric, but it earns nothing, and an
Apex eval in a bear window would rarely reach the +$3,000 target. So this improves the current
regime and preserves capital in a bear, but does NOT solve the one-factor problem. That remains the
orthogonal-source work. Long-only should still be confirmed cross-market in #5.

---
## #2 — Adaptive (vol-scaled) trend lookback  ✅ DONE
| Variant | Signal flips | Sharpe | maxDD | 2021 | Apex pass |
|---|---|---|---|---|---|
| **Fixed 20/100 (base)** | 18 | **0.83** | **−28.3%** | −11.3% | **42.6%** |
| Vol-scaled fast | 18 | 0.77 | −33.7% | −11.8% | 40.1% |
| KAMA(10,2,30) | 25 | 0.47 | −37.2% | −25.6% | 38.9% |

**Result:** adaptive does NOT help. KAMA whipsawed MORE (25 flips vs 18) and hurt every metric; vol-scaling was slightly worse. The 100-day slow EMA already dampens whipsaws; adaptive fast logic just adds noise. **Decision:** keep fixed 20/100; do not fish for a magic adaptive config (overfitting trap).
## #3 — ATR-multiple exits  ✅ DONE
| Stop rule | Apex pass | Median days |
|---|---|---|
| Fixed 12pt (base) | 42.6% | 16d |
| **ATR ×1.5** | **45.7%** | 24d |
| ATR ×2.0 | 45.1% | 35d |
| ATR ×2.5 | 42.0% | 48d |

**Result:** an ATR-adaptive stop (×1.5–2.0) modestly improves the pass rate (+3 pts) and is more principled (scales with volatility); ATR×1.5 is the sweet spot. **CANDIDATE for the change batch.** Must be confirmed out-of-sample (#7). ×2.5 too wide (slower, no benefit).
## #4 — Regime classification + expectancy per regime  ✅ DONE
| Regime | Days | Expectancy (bps/day) | Sharpe |
|---|---|---|---|
| **TREND + low-vol** | 346 | **12.3** | **1.99** |
| TREND + high-vol | 538 | 4.0 | 0.45 |
| RANGE + low-vol | 549 | 4.4 | 0.89 |
| RANGE + high-vol | 336 | 4.0 | 0.60 |
| Low-vol (all) | 895 | 7.4 | **1.37** |
| High-vol (all) | 874 | 4.0 | **0.49** |

**Result:** the edge is a **low-volatility, trending** phenomenon. It is NOT mainly about trend-vs-range — it's about VOLATILITY: calm days Sharpe 1.37 vs volatile days 0.49. High vol whipsaws the stops. **Actionable:** a volatility de-risk/filter (size down or stand aside in high-vol) targets exactly where the edge is absent — strong CANDIDATE for the batch. Descriptive/in-sample; confirm out-of-sample (#7).
## #5 — Cross-market robustness (unoptimized)  ✅ DONE (from the 13-market run, 2010–2026)
Same 20/100 trend, vol-scaled, run unoptimized on each market. Standalone trend Sharpe:

| Survives (positive) | Sharpe | | Fails (~0 / negative) | Sharpe |
|---|---|---|---|---|
| Gold | +0.49 | | Crude | +0.06 |
| Yen | +0.38 | | Silver | −0.03 |
| S&P (ES) | +0.30 | | Euro | −0.05 |
| Nasdaq (NQ) | +0.28 | | Copper | −0.10 |
| 10Y / 30Y | +0.18 / +0.13 | | Corn / Soy / NatGas | −0.12 / −0.27 / −0.45 |

**Result:** the edge **partially** survives — trend works on gold, equity indices, yen, and rates, but **fails** on silver, copper, euro, crude, and ags. So it is neither purely gold-specific nor universally structural: it is the classic **trend-following premium that lives in *some* markets and not others**, and gold is genuinely one of the good ones. This is real (trend is a documented cross-asset premium) but confirms it is regime/market-dependent, not a universal law.
## #6 — Monte Carlo (bootstrap CI)  ✅ DONE
Bootstrapped the 14 INDEPENDENT (non-overlapping) combine outcomes, 20k resamples.

| Metric | Value |
|---|---|
| Independent combines | 14 |
| Point pass rate | 35.7% |
| **Bootstrap 90% CI** | **[14.3%, 57.1%]** |
| P(true rate < 33%) | 0.40 |
| P(true rate > 45%) | 0.20 |

**Result:** the uncertainty is enormous — we cannot distinguish a good ~45% strategy from a poor ~20% one with this data. The ~40% headline is a point estimate with a huge error bar. **Only forward evidence (more independent samples over time) shrinks this.** This is the strongest argument against committing meaningful capital yet.
## #7 — Walk-forward recalibration (rolling)  ✅ DONE
2y-train / 1y-test, roll forward; pick best EMA in train, test OOS.

| Test window | Best (train) | OOS Sharpe | Fixed 20/100 OOS |
|---|---|---|---|
| 2021–22 | (20,100) | 0.06 | 0.06 |
| 2022–23 | (10,50) | −0.09 | 0.33 |
| 2023–24 | (30,50) | 1.39 | 1.39 |
| 2024–25 | (30,50) | 1.89 | 1.89 |
| 2025–26 | (20,100) | 1.60 | 1.60 |

**Result:** fixed 20/100 was positive OOS in **5/5** folds and **beat re-optimizing** (mean 1.05 vs 0.97). The parameters are NOT overfit — simplicity generalizes, and the trend premium persists OOS. Caveat: OOS magnitude is still bull-flattered (strong 2023–26, marginal 2021–23).
## Orthogonal return sources (vol-expansion, seasonality, COT, term structure, macro, options) — the real prize, after diagnostics

---

## PROGRAM CONCLUSION — the change batch (tested combined, not just individually)

| Config | Apex pass |
|---|---|
| BASE: symmetric + fixed 12pt (current live) | 42.6% |
| **+ #1 long-only** | **48.1%** |
| + long-only + #3 ATR×1.5 | 46.3% |
| + long-only + #3 + #4 vol de-risk | 43.2% |

**The changes are NOT additive.** Long-only ALONE is best. The ATR stop (#3) and vol de-risk (#4) each helped the *symmetric* strategy but HURT once long-only is in — they were compensating for the losing short side that long-only removes.

**Decision — the batch is a single change: adopt LONG-ONLY.**
- ADOPT: #1 long-only (42.6% → ~48% pass, better Sharpe, shallower drawdown).
- REJECT: #2 adaptive (worse), #3 ATR stop (helps symmetric only), #4 vol filter (helps symmetric only).
- KEEP: fixed 20/100, fixed 12pt stop. Simplicity wins (confirmed by #7: fixed beats re-optimizing).

**Honest limits unchanged by any of this:**
- Still ONE factor (trend); long-only *sharpens* the bull-dependence (#5 shows trend only survives on ~half of markets; #4 shows the edge is a low-vol/trend phenomenon).
- Uncertainty is huge: true pass-rate 90% CI [14%, 57%] (#6). We cannot yet distinguish a good strategy from a mediocre one.
- The real prize remains an ORTHOGONAL return source that pays when trend doesn't — the next frontier, per the mentor.

**Net:** the program produced one clean, honest improvement (long-only) and, more valuably, a precise map of where the edge lives, how uncertain it is, and why more engineering won't rescue a single-factor premium.
