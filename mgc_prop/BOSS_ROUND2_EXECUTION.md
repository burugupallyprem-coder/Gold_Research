# Boss feedback round 2 — applied (with an important self-correction)

## 0. CORRECTION — execution "improvement" was a look-ahead bug (retracted)
An earlier throwaway test suggested a chandelier-trailing + re-entry execution plan lifted the Apex pass rate to
~57–66%. **That was wrong.** The test script mixed shifted and unshifted price series, letting the exit decision
peek at the *same day's* close — a look-ahead. Re-implemented **strictly causally** in the real framework, the
execution plan does **not** help. Retracted in full. (Caught before deployment; this is why causal re-checks matter.)

## 1. Honesty correction (boss caught an overclaim) — applied
"No second profitable orthogonal source" → "we have not found one among the specific constructions tested." Full
untested list documented in STRATEGY3_AND_CONCLUSION.md.

## 2. Contribution analysis (per-year P&L by source) — valid
| Year | Gold | TREND | Macro (RY) | COT-contra |
|---|---|---|---|---|
| 2020 | +24% | 9.9% | 9.4% | 31.6% |
| 2021 | −6% | **−8.4%** | **+7.2%** | **+10.8%** |
| 2024 | +27% | 19.4% | −3.1% | −15.8% |
| 2025 | +63% | 34.8% | −2.9% | −17.6% |
TREND drives 6 of 8 years; macro/COT only earn their keep in 2021 (trend's worst). Hedges pay ~1 year in 8.

## 3. Execution tested CAUSALLY — definitive comparison (Apex $50k)
| Config (strictly causal) | Clean | Real fills |
|---|---|---|
| Symmetric trend (old live) | 53.7% | 42.6% |
| **LONG-ONLY trend (exit on flip)** | **61.1%** | **48.1%** |
| Long-only + chandelier + re-entry (the retracted bug) | 50.0% | 46.9% |

**The chandelier/re-entry execution plan does NOT beat plain long-only when tested honestly** — it is slightly
worse. The remaining execution levers (partial exits, scaling, entry timing, event filter) are untested and may
still help, but **no execution improvement has yet been demonstrated causally.**

## HONEST VALIDATED CHANGE (the only one that survives)
**LONG-ONLY trend, exit on flip.** Symmetric → long-only lifts real-fills pass ~42.6% → ~48.1% (+5.5pts), and it
CANNOT be a look-ahead artifact — it is simply clipping the short side (a net loser that deepened drawdown, per
#1). This is the single, real improvement from the whole optimization phase. The forward-test strategy is set to
this. Everything else (adaptive, ATR, vol filter, mean-reversion, macro, COT, chandelier, re-entry) was tested
and rejected.

## Honest scorecard impact
The boss's "Execution 75→92" bump was based on the buggy result and should be reverted — we have NOT demonstrated
an execution edge. What stands: a modest long-only trend edge (~48% real-fills, wide CI), rigorously validated,
with a documented trail of rejected ideas — including one we caught ourselves.
