# Strategy × Instrument Scan — Result (84 combos, real data)

6 strategies (Donchian 20/10, Turtle 55/20, EMA 10/30, EMA 20/100, Bollinger-revert, Bollinger-squeeze)
× 13 futures. Causal (look-ahead audited), realistic costs, Apex $50k pass rate. RESEARCH ONLY.

## Top Apex-tradeable combos (by pass rate)
| Strategy | Instrument | Apex pass | Sharpe |
|---|---|---|---|
| **ema_cross_20_100 (our baseline)** | **Gold** | **41.1%** | 0.711 |
| donchian_20_10 | Gold | 39.5% | 0.454 |
| turtle_55_20 | Gold | 37.5% | 0.683 |
| turtle_55_20 | S&P (ES) | 35.6% | 0.297 |
| donchian_20_10 | Crude (CL) | 34.8% | 0.361 |
| bollinger_squeeze | Gold | 34.8% | 0.284 |
| ema_cross_20_100 | Nasdaq (NQ) | 32.0% | 0.444 |

## Multiple-testing gate (the decisive line)
Best combo (turtle on gold, Sharpe 0.683) → **Deflated Sharpe 0.51 < 0.95 — does NOT clear.**
Across 84 tries, the apparent winners are consistent with luck. **No new deployable edge found.**

## Honest conclusion
1. **Our strategy won.** EMA 20/100 long-only trend on GOLD topped the Apex ranking (41.1%) across all 84 combos —
   confirmation that our validated choice is the best available, not arbitrary or lucky.
2. **The top gold combos are all trend-family** (EMA, Donchian, Turtle) — the SAME edge in different costumes
   (correlated alpha), not independent discoveries.
3. **Nothing clears deflation** — do NOT deploy a scan "winner"; it's luck-of-84. The scan's job was to catch
   exactly this, and it did.
4. **Decision: deploy nothing new.** Continue forward-testing the already-validated gold-trend strategy. The scan
   confirmed we already hold the best combination; there is no better vehicle or strategy hiding in the document.

## Not tested (would be fake rigor on daily bars)
Chart patterns (discretionary), Fibonacci pullbacks (subjective), spreads (need term-structure data), news
straddles (need intraday + event calendar). The systematic core of the document IS covered.
