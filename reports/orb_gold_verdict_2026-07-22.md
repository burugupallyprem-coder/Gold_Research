# ORB on Gold — Rigorous Test & Verdict: **NO-GO**
_Run 2026-07-22 on real XAU_USD M15 data (2019–2026, 2,299 sessions). Paper/backtest only. Not financial advice._

**Verdict: the Opening-Range-Breakout does not transfer to gold. Every configuration
loses money, fails the strategy's own promotion gate, and shows no edge even with all
costs removed. Do not paper-trade it. Keep ORB in the stock repo.**

This is exactly what your own portability spec predicted: on a single instrument the
biggest edge driver — `rs_topk` (relative-strength selection across a basket) — simply
doesn't exist, leaving ORB + vol floor + session regime, i.e. the raw version that already
FAILED on stocks.

## How it was tested (faithful adaptation)
- Opening range = first 3 × M15 bars (45 min) from a session anchor (DST-aware ET).
- Entry = M15 close beyond the range before a cutoff → enter next bar's open; stop = opposite
  range extreme; target = entry ± 1.5×risk; one trade/session; flat by session end.
- Vol floor 0.4% of price; regime = daily 50/200-EMA trend (long only in up-regime).
- Costs 0.40 gold points round-trip (~0.30 spread + 0.10 slippage).
- Judged against your pre-registered gate: **≥100 trades, ≥ +0.05R expectancy, PF ≥ 1.15,
  ≥ 60% of quarters positive.**

## Results — all configurations FAIL
| Config | Trades | Exp (R) | PF | Win% | Quarters + | Gate |
|---|---|---|---|---|---|---|
| Raw NY-open (no filters, long) | 807 | −0.072 | 0.85 | 44% | 30% | ❌ |
| + Vol floor (long) | 307 | −0.023 | 0.94 | 47% | 50% | ❌ |
| + Vol + regime (filtered, long) | 260 | −0.035 | 0.91 | 45% | 43% | ❌ |
| Filtered, London open (long) | 64 | −0.084 | 0.84 | 44% | 20% | ❌ |
| Filtered, long **and** short | 291 | −0.046 | 0.88 | 44% | 47% | ❌ |

Every profit factor is **below 1.0** (net loser) and every expectancy is **negative**. The
filters help in the right direction (raw −0.072R → filtered −0.035R) but cannot cross zero —
precisely because the filter that carried the stock edge (`rs_topk`) has no meaning for one
instrument.

## It's an absence of edge, not a cost problem
Filtered NY-open, varying only cost:
| Cost (round-trip) | Expectancy | PF |
|---|---|---|
| 0.00 (frictionless) | −0.006 R | 0.984 |
| 0.20 | −0.020 R | 0.946 |
| 0.40 (realistic) | −0.035 R | 0.909 |

At **zero cost it's still ~breakeven-negative.** A parameter search (RR 1.0, 3h cutoff,
frictionless) found the best-case variant at only +0.028R / PF 1.09 — still under the gate,
still frictionless, and that number is already flattered by multiple-testing. Real costs push
it back negative.

## Regime dependence (filtered, per-year expectancy R)
| 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| +0.10 | −0.21 | −0.32 | +0.02 | +0.32 | +0.06 | −0.10 | −0.08 |

Only 3 of 8 years positive, no persistence — the opposite of a stable edge.

## Why it breaks on gold (the mechanism)
1. **No real "open."** Gold trades ~23h/day; the 09:30 ET flow concentration that makes the
   equity open meaningful doesn't exist. An imposed London/NY session anchor is a much weaker
   signal — and the London variant was the *worst* result (PF 0.84).
2. **No cross-section.** `rs_topk` and a proper regime gate need a basket to rank. One
   instrument strips out the filter that separated the passing stock config from the failing one.
3. So gold ORB ≈ the raw breakout, and raw breakout has no edge here.

## What to do instead
Nothing to deploy. Gold already has two better-supported approaches in this repo, both of
which beat ORB on the same honest gate:
- **Daily macro-trend** (`fast_trend`): ~0.6 Sharpe, survives 5× costs.
- **Intraday SMC stack** (FVG+NY + daily-trend filter): +0.14R/trade at realistic cost (though
  cost-fragile — see `rigorous_backtest_2026-07-22.md`).

Per your standing rule: **passing on stocks told us nothing about gold, and the data says it
doesn't transfer.** ORB stays in the stock repo. This is the discipline working as intended —
it caught a no-edge port before a single paper trade.
