# Gold Bot — Strategy Bake-off & Recommended Layered Stack
_Run 2026-07-22 on the real repo data. Paper/backtest only. Not financial advice._

I ran every strategy in the repo head-to-head on the actual cached data, then tested
layering them. Below is the honest scoreboard and the one stack I'd actually forward-test.
Read the caveats — they matter more than the top-line numbers.

## What I found in one line
The single most valuable move is **not a new strategy — it's a layer**: gating the
intraday SMC setups by the *daily trend direction* roughly **doubled risk-adjusted return**
(Sharpe 1.2 → 1.9), and dropping the weakest setup (Displacement) on top pushed it higher.
But every intraday number is measured inside gold's 2023–2026 bull run, so treat the
absolute Sharpes as flattered, not real.

---

## Family A — Macro-trend daily (8 variants, 2016–2026, 5× stressed cost)
Selection Sharpe is the honest number; holdout (~1.6) is inflated by the bull run.

| variant | sel Sharpe | hold Sharpe | full Sharpe | maxDD | CAGR |
|---|---|---|---|---|---|
| baseline (50/200) | 0.248 | 1.63 | 0.416 | −39% | 3.7% |
| **fast_trend (20/100)** | **0.458** | 1.82 | **0.624** | **−26%** | **5.6%** |
| slow_trend (100/300) | 0.407 | 1.63 | 0.553 | −32% | 5.1% |
| vol_15 | 0.252 | 1.63 | 0.420 | −53% | 5.2% |
| vol_07 | 0.248 | 1.63 | 0.416 | −29% | 2.6% |
| ry_120 | 0.248 | 1.63 | 0.416 | −39% | 3.7% |
| mom_126 | 0.187 | 1.63 | 0.353 | −36% | 3.2% |
| no_macro | 0.248 | 1.63 | 0.416 | −39% | 3.7% |

Two hard facts fall out of this table:

1. **The real-yield "macro" filter is currently inert.** `baseline`, `vol_07`, `vol_15`,
   `ry_120` and `no_macro` are byte-for-byte identical because there is **no `DFII10.csv`
   in `data/daily/`**. The documented champion premium ("50/200 + real-yield filter,
   Sharpe ~0.54") cannot be reproduced from the data on disk — right now the bot is running
   pure trend + vol-targeting. Fix before trusting the macro story: drop a FRED DFII10 CSV
   into `data/daily/`.
2. **`fast_trend` (20/100 EMA) genuinely beats `baseline`** on the honest selection Sharpe
   (0.458 vs 0.248) *and* has a smaller drawdown (−26% vs −39%). The research loop already
   saw this (fast_trend confirmed 2/3 weeks in June). It's a legitimate standalone upgrade
   to the daily champion.

## Family B — SMC intraday (M15, real costs 0.3 spread + 0.1 slip, conf-gate 60)

| config | trades | win% | exp (R) | PF | Sharpe | window |
|---|---|---|---|---|---|---|
| Displacement only | 562 | 30% | 0.132 | 1.20 | 0.77 | 2023–26 |
| FVG only | 516 | 31% | 0.168 | 1.33 | 1.13 | 2023–26 |
| NY-Opening only | 339 | 27% | 0.190 | 1.53 | 1.25 | 2023–26 |
| All setups, gate ON | 844 | 29% | 0.143 | 1.26 | 1.21 | 2023–26 |
| All setups, gate OFF | 532 | 28% | 0.139 | 1.27 | 1.26 | 2024–26* |
| FVG + NY (no Displacement) | 710 | 29% | 0.163 | 1.32 | 1.32 | 2023–26 |
| **All + daily-trend filter** | 514 | 27% | 0.104 | 1.33 | **1.93** | 2023–26 |
| **FVG+NY + daily-trend filter** | 378 | 30% | 0.200 | 1.57 | **3.11** | 2023–26* |

\*gate-OFF and the FVG+NY-filter rows use a slightly shorter window (time-limit),
so compare their Sharpes as "same ballpark," not to the third decimal.

Read-out:
- **Displacement is the drag** (Sharpe 0.77). It fires the most and adds the least. Cutting it improves every combined metric.
- **NY-Opening is the strongest single setup** (PF 1.53).
- **The confidence gate barely earns its keep** here (gate ON 1.21 vs OFF 1.26). It's cheap insurance, not alpha — keep it, don't rely on it.
- **The daily-trend filter is the real lever.** Only taking intraday trades that agree with the daily 50/200-EMA + 12-month-momentum direction removes the counter-trend chop and lifts Sharpe the most.

## Family C — SMC swing (`smc_paper.py`)
Pre-registered forward trial. Its own author put it on the record as *expected to fail*
(+0.24R on 32 validation trades, and the same engine went **negative** across a 9-instrument
basket). It needs ≥30 forward trades before any verdict. **Not in the "works" column yet** —
leave it running as a falsification test, nothing more.

---

## Recommended stack — "what actually works, layered"
Build the direction and the entry on different clocks, then gate hard:

1. **Regime / direction (daily):** 50/200 EMA + 12-month momentum → gives the *allowed side*
   only (long in uptrend, short in downtrend, flat otherwise). Upgrade the EMAs to **20/100
   (`fast_trend`)**, which won the daily bake-off. Vol-target this overlay at 10%.
2. **Entry setups (M15):** **FVG + NY-Opening**. Drop **Displacement**.
3. **Quality gates:** keep the confidence gate at 60, plus the existing volume and HTF-trend
   checks. Cheap insurance.
4. **Risk (unchanged):** ATR/swing stop, RR 2.5 (NY 3.0), 1% risk/trade, break-even at 1.5R.

In the backtest this stack was the top risk-adjusted performer (Sharpe ~3, PF 1.57, exp 0.20R,
max drawdown a fraction of 1% of equity). It's essentially the current SMC engine with one
setup removed and one daily filter added — a small, low-risk change to code you already trust.

## The caveats that decide whether this is real
- **The bull-run problem.** Every intraday Sharpe here lives inside gold's 2023–2026 rally.
  "Trade only with the daily trend" is easy money when the trend is a two-year moon-shot.
  A Sharpe of 3 will not survive a sideways or falling gold regime. This is the same
  inflation the house rules flag on the macro holdout — I'm flagging it just as loudly here.
- **The macro filter isn't wired.** Until `DFII10.csv` exists, the "real-yield edge" is a
  claim, not a result.
- **Don't trust the backtest — forward-test it.** The right next step isn't to promote this
  on the strength of a 2023–26 fit. It's to **pre-register the stack as a second paper track**
  running beside `baseline`, and let months of forward data judge it — exactly how
  `smc_paper.py` was handled. That's the project's whole discipline.
- Paper only. A human approves anything live. I am not a financial advisor.

## Concrete next actions
1. Add `data/daily/DFII10.csv` (FRED) so the macro filter is real, then re-run the daily bake-off.
2. Promote `fast_trend` as the daily direction layer via the normal `apply_change.py` /
   research-loop path (let it re-confirm; don't hand-force it).
3. Pre-register the **FVG+NY + daily-trend-filter** intraday stack as a new forward paper
   trial with fixed gates (≥30 trades before any verdict), parallel to the champion.
