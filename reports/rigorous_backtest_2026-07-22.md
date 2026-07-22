# Rigorous Backtest — Two Tracks Before Parallel Paper Trial
_Run 2026-07-22 on real cached data. Paper/backtest only. Not financial advice._

Two strategies are going to run in parallel on paper. This is the honest, regime-by-regime,
cost-stressed backtest of each **before** a single simulated trade is placed. The headline:
one track is robust and cost-insensitive; the other has a real but thin edge that dies under
cost stress and is heavily long-biased. Both deserve forward paper testing — for opposite reasons.

---

## Track 1 — Macro-trend daily (`fast_trend` 20/100 EMA + momentum + 10% vol target)
Data: XAU_USD daily, 2016-06 → 2026-06 (2,596 bars). Real-yield filter is **inert** (no
`DFII10.csv` on disk), so this is pure trend + vol-targeting today.

### Cost stress (full period)
| cost | Sharpe | CAGR | maxDD | total return |
|---|---|---|---|---|
| 1× | 0.73 | 6.7% | −22% | +94% |
| 3× | 0.68 | 6.1% | −24% | +84% |
| 5× | 0.62 | 5.6% | −26% | +75% |

Low turnover ⇒ **barely dented by costs** (Sharpe 0.73 → 0.62 from 1× to 5×). This is the
strategy's biggest structural advantage.

### Out-of-sample by year (5× cost Sharpe) — the regime test
| year | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|---|---|---|---|
| **fast_trend** | −1.69 | −0.09 | 0.70 | 1.40 | −1.17 | −0.24 | −0.08 | 1.84 | **3.26** | 0.26 |
| baseline | −0.94 | −0.71 | 1.45 | 1.58 | −2.81 | −0.51 | −0.70 | 1.84 | 3.26 | −0.09 |

Honest read: it's a **trend-follower**. It wins in trending years (2019, 2020, 2024, 2025)
and loses in choppy/mean-reverting years (2017, 2021, 2022, 2023). Roughly half the calendar
years are negative; the edge comes from the winners being much bigger than the losers.
`fast_trend` beats `baseline` on full-period Sharpe (0.62 vs 0.42 at 5×) and drawdown
(−26% vs −39%) — so if Track 1 is promoted, it should be `fast_trend`, via the normal
`apply_change.py` approval path. Selection-period Sharpe (the un-flattered number): **0.46**.

---

## Track 2 — Intraday SMC stack (FVG + NY-Opening, conf-gate ON, filtered by daily trend)
Data: XAU_USD M15, 2019-01 → 2026-06. Costs = 0.30 spread + 0.10 slippage per fill (1×).
Trades counted per calendar year, entry-year attribution, 20-day indicator warm-up.

### Per-year at realistic (1×) cost
| year | trades | win% | exp (R) | PF | total R |
|---|---|---|---|---|---|
| 2019 | 98 | 35% | +0.248 | 1.37 | +24.3 |
| 2020 | 139 | 25% | +0.046 | 1.12 | +6.4 |
| 2021 | 49 | 27% | **−0.066** | 0.80 | −3.2 |
| 2022 | 90 | 27% | +0.138 | 1.43 | +12.4 |
| 2023 | 104 | 26% | +0.020 | 1.07 | +2.1 |
| 2024 | 133 | 24% | +0.043 | 1.26 | +5.7 |
| 2025 | 161 | 32% | +0.248 | 1.64 | +40.0 |
| 2026* | 37 | 41% | +0.656 | 2.60 | +24.3 |
| **Aggregate** | **811** | **28%** | **+0.138** | — | **+112 R** |

Positive in 7 of 8 years at real costs. That's a genuine result — not nothing.

### Cost stress — this is where it breaks
| cost | aggregate avg | total R | positive years |
|---|---|---|---|
| 1× | +0.138 R | +112 R | 7 / 8 |
| **3×** | **−0.035 R** | **−28 R** | **2 / 8** |

At 3× costs (a realistic stress for gold during news spikes / thin liquidity) the edge
**inverts** — six of eight years go negative. Unlike Track 1, this strategy has almost no
cost cushion. Its per-trade edge (~0.14 R ≈ a few gold dollars) is the same order of
magnitude as the spread it pays. **Live fill quality will make or break it** — which is
exactly why it must be forward-paper-tested at real OANDA prices, not trusted from a backtest.

### Long/short split — the hidden directional bet
| side | trades | total R (1×) | avg |
|---|---|---|---|
| long | 727 (90%) | +95.6 R | +0.131 |
| short | 84 (10%) | +16.4 R | +0.195 |

The daily-trend filter kept the book **90% long** because gold trended up for essentially
the whole sample. So Track 2's backtest is largely *"buy gold intraday during a multi-year
gold bull market."* The short side is barely tested (84 trades, only in 2021–2022). In a
sustained gold **downtrend** the stack would flip mostly short into a regime it has almost
no evidence on. The 2021 long book (−0.56 R) is a preview of how it behaves when the daily
filter stays long into chop.

\*2026 is a partial year (through June).

---

## Verdict
- **Track 1 (daily `fast_trend`)** — robust, cost-insensitive, ~0.6 Sharpe trend edge that is
  honestly regime-dependent (loses in chop). The safer track. Survives 5× costs.
- **Track 2 (intraday stack)** — real but **thin and cost-fragile** edge (+0.14 R/trade at 1×,
  negative at 3×), and **90% a long-gold bet** with an untested short side. High variance,
  high upside in trending years, but its live viability hinges entirely on fill quality.

They are worth running **in parallel** because they are complementary (slow trend vs intraday)
and because forward paper is the only fair judge — decisively so for the cost-fragile Track 2.
Neither result justifies real capital. Pre-registered gates and months of forward data come first.

## Pre-registered expectations (lock these before the trial starts)
- Track 1 expected forward selection-Sharpe ≈ 0.4–0.6; losing calendar years are normal, not a failure.
- Track 2 expected forward ≈ +0.10 to +0.15 R/trade **only if** live spreads stay near backtest
  assumptions; if realized avg R is < 0 after 30+ trades, or if it is only profitable while gold
  rises, it fails.
- Verdict window: ≥ 30 closed trades per track (~2–6 months) before any judgement; 6-month checkpoint.
