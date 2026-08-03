# Strategy #3 (Vol-Expansion) + the orthogonal-source conclusion

*Same standards as before. Gold daily, realistic costs, vol-scaled to 10%.*

## Strategy #3 — volatility-expansion breakout
Donchian breakout gated by a Bollinger-width squeeze (enter breakouts only out of low-vol
compression; exit on an opposite 10-day channel break).

| Strategy | Sharpe | Max DD | Ann return | Corr w/ trend | In market |
|---|---|---|---|---|---|
| Trend (#1) | 0.92 | −20% | 9.9% | — | — |
| **Vol-expansion (#3)** | **0.54** | −16% | 6.1% | **+0.61** | 57% |
| Mean-reversion (#2) | −0.53 | −47% | −6.6% | −0.58 | — |
| Buy & hold | 1.11 | −16% | 11.9% | — | — |

**Result:** vol-expansion MAKES money (unlike MR) but is **positively correlated with trend (+0.61)** and
lost in 2021 alongside trend. It is trend-following in disguise — not an orthogonal source. (The boss predicted
exactly this: "breakouts are still trend-following.")

## The key conclusion — orthogonality vs. profitability tradeoff
| Source | Orthogonal? | Profitable standalone? |
|---|---|---|
| Trend (#1) | — | Yes (0.92) |
| Mean-reversion (#2) | **Yes (−0.58)** | **No (−0.53)** |
| Vol-expansion (#3) | **No (+0.61)** | Yes (0.54) |

**From price-based signals on gold, you get orthogonality XOR profitability — never both.** Because gold has
been trending, anything profitable is trend-like (correlated), and anything orthogonal fades the trend and loses.
There is no price-pattern free lunch.

**Therefore the genuine orthogonal profit-source must be NON-PRICE** — the boss's own list: carry / term
structure (contango vs backwardation), macro (real yields, dollar index), COT positioning, options-implied
vol/skew. These carry different information than price, so they *can* pay when price-trend doesn't. This is the
real next frontier — and it needs different data than the daily OHLC we've used so far.

**Status:** trend strategy frozen + forward-testing (unchanged). Price-based diversification exhausted. Next
research direction = a non-price orthogonal signal (macro/carry/positioning), pending data + boss's steer.


## Strategy #4 — macro (real-yield momentum): the first NON-PRICE source
Long gold when the 10y TIPS real yield is falling.

| Signal | Sharpe | Max DD | Ann return | Corr w/ trend |
|---|---|---|---|---|
| RealYield-mom 20d | 0.15 | −25% | 1.6% | **+0.24** |
| RealYield-mom 60d | −0.23 | −38% | −2.6% | +0.24 |
| 50/50 Trend + RealYield | 0.68 | −11% | 5.8% | — |

**Result:** the MOST orthogonal source yet (corr +0.24) and it paid in 2021 (+0.65 while trend lost) — but it is
**not profitable standalone** (~0 Sharpe) and missed the 2024–25 rally (gold decoupled from real yields on
central-bank buying / geopolitics). Blending reduces drawdown but lowers Sharpe — a hedge, not an alpha. Same
story as mean-reversion.

## FINAL CONCLUSION of the orthogonal-source search
| Source | Orthogonal? | Profitable standalone? |
|---|---|---|
| Trend (price) | — | Yes (0.92) |
| Mean-reversion (price) | Yes (−0.58) | No (−0.53) |
| Vol-expansion (price) | No (+0.61) | Yes (0.54) |
| Real-yield (macro) | Yes-ish (+0.24) | No (~0) |

**Across four strategies and a non-price source, the tradeoff is robust: orthogonality XOR profitability, never
both.** On gold, with constructible signals + available data, there is NO second profitable orthogonal source —
only drawdown *hedges*. A genuine second profit-stream would require sources we cannot currently build/test
(COT positioning, futures term structure, options surfaces) and is a lower-probability, higher-effort bet.

**Honest state:** one modest, real, forward-tested edge (gold trend). Orthogonal PROFIT source: not found.
Drawdown HEDGE (small MR or real-yield sleeve): available, and prop-relevant since drawdown fails combines.


## Strategy #5 — COT positioning (non-price) + the hedge/pass-rate test
Speculator (non-commercial) positioning from CFTC, weekly, lagged to avoid look-ahead.

| Signal | Sharpe | Max DD | Ann ret | Corr w/ trend | 2021 |
|---|---|---|---|---|---|
| COT spec-momentum | −0.49 | −45% | −5.2% | +0.14 | −1.17 |
| COT contrarian-index | −0.08 | −42% | −0.9% | **−0.24** | **+1.08** |

COT-contrarian is orthogonal (−0.24) and paid the strongest of any hedge in 2021 (+1.08) — but again **not
profitable standalone**. Same wall.

**Hedge → Apex pass rate:** trend-only 42.6% → +1 MR hedge 40.7% → +2 hedge 31.5%. Hedges HURT the combine —
the overlay's dynamic sizing already prevents floor breaches, so a hedge only adds return-drag. **No hedge for
the prop combine.**

## DEFINITIVE CONCLUSION — five sources, one wall
| Source | Class | Orthogonal to trend? | Profitable standalone? |
|---|---|---|---|
| Trend | price | — | **Yes (0.92)** |
| Mean-reversion | price | Yes (−0.58) | No (−0.53) |
| Vol-expansion | price | No (+0.61) | Yes (0.54) |
| Real-yield | macro | Yes-ish (+0.24) | No (~0) |
| COT-momentum | positioning | ~ (+0.14) | No (−0.49) |
| COT-contrarian | positioning | Yes (−0.24) | No (−0.08) |

**Across the specific constructions we tested (a finite subset of the hypothesis space), the pattern is
consistent: orthogonality XOR profitability — never both.** IMPORTANT (per boss correction): this does NOT prove
a second profitable orthogonal source cannot exist. The correct claim is *"we have not yet found one using the
specific signal constructions tested."* Among what we tested, gold has one profitable edge (trend); every
orthogonal source was a drawdown hedge, and hedges HURT the prop combine.

**Explicitly NOT yet tested (could still contain a profitable orthogonal source):** options-implied vol term
structure, ETF flows, gold lease rates, cross-asset relative strength, DXY-regime interactions, real-yield +
dollar *combinations* (one macro variable isn't enough), vol-of-vol, seasonal/calendar/time-of-day effects,
intraday microstructure, central-bank-purchase proxies, and **richer COT constructions** (commercials vs large
specs vs small traders, positioning percentile, extremes, position/OI changes, divergence — only momentum &
contrarian were tested, so *first-generation* COT is dead, not COT itself).

**Honest end state:** one modest, real, forward-tested edge (gold trend), plus a rigorous, documented map of
which *specific* constructions failed and why. We stopped because the tested ideas failed — not because the
hypothesis space is exhausted. That discipline (test, fail, stop; don't overfit) is itself the deliverable.
