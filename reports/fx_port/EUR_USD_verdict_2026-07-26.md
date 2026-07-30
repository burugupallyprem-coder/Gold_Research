# FX Port — EUR/USD Verdict: **NO-GO**
_Run 2026-07-26 on real OANDA EUR/USD M15, 2021-07-30 → 2026-07-29 (124,363 bars). Paper/backtest
only. Not financial advice. Honest number = selection period; recent-only holdout = single regime,
label inflated._

**Verdict: the intraday SMC stack does not transfer to EUR/USD. The honest (selection-period) edge is
flat-to-zero, it fails the promotion gate, and the gold-tuned daily-trend filter actively *hurts* it.
Do not paper-deploy. The infrastructure ported perfectly; the edge did not — exactly the rule.**

## Results (cost = 1.5 pip round-trip, the realistic 1× assumption)
| config | window | trades | exp (R) | PF | Sharpe | quarters + | gate |
|---|---|---|---|---|---|---|---|
| RAW FVG+NY | all | 951 | +0.073 | 1.12 | 0.56 | 62% | ❌ (PF) |
| RAW FVG+NY | **selection (honest)** | 666 | **+0.046** | 1.08 | 0.37 | 53% | ❌ |
| RAW FVG+NY | holdout (recent 30%) | 285 | +0.135 | 1.22 | 0.98 | 71% | ✅* |
| + daily-trend filter | all | 331 | +0.089 | 1.15 | 0.41 | 67% | ❌ (PF 1.145) |
| + daily-trend filter | **selection (honest)** | 204 | **−0.003** | 0.99 | −0.01 | 58% | ❌ |
| + daily-trend filter | holdout (recent 30%) | 127 | +0.237 | 1.39 | 1.04 | 71% | ✅* |

\*The holdout passes, but it's one recent window (~late-2025 → 2026). Same inflation caveat as gold's
bull run — a single regime is not evidence. The per-year line proves the point.

## Why it's a NO-GO (three independent reasons)
1. **The honest number is flat.** Selection-period expectancy is **+0.046R raw / −0.003R filtered**,
   PF ≈ 1.0, Sharpe ≈ 0. On the data the optimizer can't peek at, there is essentially no edge.
2. **It fails the gate even on the full sample at 1× cost** — PF 1.12 (raw) / 1.145 (filtered), both
   under the 1.15 bar. FX majors are efficient and low-vol; at 3×/5× cost this only gets worse, so
   cost-stress wasn't even the deciding factor — it fails before that.
3. **Inconsistent across years** (filtered): 2022 +0.04, 2023 +0.17, **2024 −0.14**, 2025 +0.20,
   2026 +0.28. A negative year in the middle and a strong recent tail = the "recent window flatters
   it" pattern, not a stable edge.

## The one genuinely interesting difference from gold (honest, both ways)
EUR/USD trades came out **two-sided: 182 long / 149 short** — not the 87–90% long book gold produced.
So on FX this is *not* a hidden directional beta bet; if a real edge existed here it would be more
trustworthy than gold's. But no honest edge exists on the selection metric, so it's an interesting
structural property attached to a strategy that doesn't work — worth remembering, not acting on.

## A finding that matters for the whole project
**The gold-tuned daily-trend filter degrades EUR/USD.** It cut the raw selection expectancy from
**+0.046 → −0.003**. The layer that was gold's biggest lever is a net negative here. This is the
"edge does not generalize" rule in miniature: you cannot carry a gold-fit component onto another
market and assume it helps — each world needs its own validation.

## What to do
- **Nothing to deploy on EUR/USD.** No pre-registration, no paper track. A negative result is a real result.
- If you want to keep exploring FX, the honest options are: (a) test one or two more majors
  (GBP/USD, AUD/USD) for completeness — but expect similar, and don't mine pairs until one "passes";
  or (b) accept that this *particular* intraday stack doesn't carry to efficient FX majors, and if FX
  is still interesting, test a **different, FX-native hypothesis** (e.g. a London/NY session-open
  breakout, or a carry/trend overlay) as a fresh idea with its own validation — not this port.
- Keep it isolated: this stays a research result under `reports/fx_port/`; it never touches the gold
  champion or any paper track.

## Infra scorecard (the part that DID transfer)
The engine ran unchanged on 124k FX bars, produced 951 well-formed trades with correct two-sided
fills and scale-invariant R metrics, and the fetch → backtest → gate pipeline worked first try. The
machinery generalizes cleanly; that's the reusable asset. The edge is what has to be re-earned per
market, and on EUR/USD it wasn't there.
