# MGC Gold-Trend Prop Strategy — Full Technical Review

*Prepared for external mentor review. Everything below is research / paper-simulation only.
No real capital has been deployed. Real-money funding is intentionally gated (see §12).*

**Version:** 2026-08-02 · **Instrument:** Micro Gold futures (MGC) · **Target account:** Apex Trader Funding $50k, EOD-trailing

---

## 0. One-paragraph summary

We take a **single, independently-validated edge — a medium-term trend-following signal on gold** — and wrap it in a **drawdown-aware execution overlay** sized specifically to survive the risk rules of an **Apex $50k evaluation** traded on Micro Gold (MGC). On real MGC data (Databento), a rolling backtest of ~200 historical combine attempts passes roughly **44% clean / ~38–42% after realistic fills** on the $50k account, median ~16–20 days to pass. This is a **modest, positive-expectancy grind, not a reliable income** — most individual attempts fail, and the tested period was a gold bull market that flatters trend strategies. The strategy is presented for critique; the two open gates before any real money are (a) confirming the ~40% forward on the live contract and (b) an immigration-attorney opinion on F-1 eligibility.

---

## 1. Objective

Convert a real (if modest) market edge into a **rule-survival strategy** for a prop-firm evaluation. In a prop combine, *not breaking the rules* matters as much as *making money* — the account fails on a drawdown-rule violation regardless of edge. So the design problem is two-part:
1. **Signal** — a positive-expectancy directional edge on gold.
2. **Overlay** — position sizing and stops that keep the simulated account inside Apex's trailing-drawdown rule long enough to hit the profit target.

---

## 2. The edge (signal) and how it was validated

### 2.1 The signal
- **Definition:** an EMA trend cross on **daily** gold. Long when `EMA(20) > EMA(100)`, short when `EMA(20) < EMA(100)`. Formally the position is `sign(EMA_fast − EMA_slow)`.
- **Timing:** the position is computed from data up to and including day *t−1* and applied to day *t* (`signal.shift(1)`). **No look-ahead** — we never trade on a bar we used to compute the signal.

### 2.2 How we found it (honest process)
- We ran a **combination hunt**: 24 candidate strategies (trend at several speeds, time-series momentum, RSI, Bollinger, MACD, plus confluences and regime-gated combos), each cost-stressed on 7 years of gold, scored on a selection window with a **held-out year**.
- We applied the **Deflated Sharpe Ratio** (Bailey & López de Prado) across all 24 tries to correct for multiple testing. **Result: the single best combo's DSR was 0.50 — right at the "luckiest of 24 tries" line. No brand-new alpha cleared the strict bar.** We are not claiming a novel alpha.
- What the hunt *did* establish: **every top performer was trend/momentum; every mean-reversion indicator (RSI, Bollinger) was flat or negative** (RSI-revert held a −0.68 Sharpe out-of-sample). Trend is the only thing that works on gold.

### 2.3 Why we use the 20/100 trend specifically (robustness)
The 20/100 (faster) trend beat the classic 50/200 (slower) trend. We stress-tested *that specific comparison* three ways — this is a parameter choice inside an already-known-good family, not a fresh data-mine:
- **Year-by-year:** faster won or tied 4 of 7 years, and cut the choppy-2021 drawdown from −3.1 to −0.9 Sharpe.
- **Block bootstrap** (2,000 resamples of the paired daily-return difference): **P(faster > slower) = 98.2%**, 90% CI **[+0.000066, +0.000617]** — clears zero.
- **Parameter stability:** the neighborhood (fast 15–25, slow 80–120) all scores ~0.6–0.84 full-sample Sharpe — a **stable plateau, not a lucky spike**. Overfit peaks don't have plateaus around them.

### 2.4 What did NOT work (stated plainly)
- Mean-reversion (RSI, Bollinger revert) — negative out-of-sample on gold.
- Any brand-new combination clearing the deflated-Sharpe bar — none did (best DSR 0.50).
- Intraday equity strategies (separate research track) — six families, all failed the same bar.

### 2.5 Honest status of the edge
A **modest, real, trend-following premium on gold** (~0.5–0.7 annualized Sharpe unlevered), well-documented in the literature, better-tuned than the standard 50/200. It is **not** a proprietary or high-Sharpe alpha. Its recent strength is inflated by gold's 2023–2026 bull run; the honest expectation is a slow, volatile, modest edge.

---

## 3. The instrument — Micro Gold (MGC)

| Property | Value |
|---|---|
| Contract | CME Micro Gold (MGC) |
| Size | 10 troy ounces |
| Point value | **$10 per 1.0 point** (a $1.00 move in gold) |
| Tick | 0.10 point = **$1.00** |
| Data source | Databento `GLBX.MDP3`, continuous front month `MGC.v.0`, daily (`ohlcv-1d`) |
| Proxy (offline) | OANDA `XAU_USD` spot — tracks MGC tightly for a daily trend hold |

---

## 4. The prop firm — Apex Trader Funding (verified 2026-08-02)

Target: **$50,000 account, EOD-trailing** variant.

| Rule | $50k | $100k |
|---|---|---|
| Profit target (6%) | **$3,000** | $6,000 |
| Trailing max drawdown | **$2,500** | $3,000 |
| Daily loss limit | **None** | None |
| Contract cap | 10 MGC | 14 MGC |
| Consistency (50%) | payout-only, **not in the eval** | same |
| Min trading days | none | none |

**Key mechanics we exploit:**
- **No daily loss limit** — unlike TopStep; removes one whole failure mode.
- **Trailing floor LOCKS** to *start + $100* once end-of-day balance reaches *start + trailing + $100* (i.e. +$2,600 on a $50k). After the lock, the floor is static — the last push to the $3,000 target is low-risk. **The entire battle is the first ~$2,600.**
- **EOD-trailing chosen over intraday-trailing** deliberately: the EOD floor does not ratchet up on intraday spikes, so a trend position can breathe through pullbacks. (On the raw edge, EOD passed 49% vs intraday 40%.)

*Sources: Apex Trader Funding help-center (intraday trailing drawdown page), QuantVPS PA-account rules, QuantCrawler Apex rules 2026.*

---

## 5. Strategy mechanics (full detail)

### 5.1 Signal
`EMA_fast = EMA(close, 20)`, `EMA_slow = EMA(close, 100)`, `position_raw = sign(EMA_fast − EMA_slow)`, then `position = position_raw.shift(1)` (applied next day).

### 5.2 The drawdown overlay
Two components on top of the raw ±1 signal:

**(a) Hard stop — 12 points ($120 / contract).** If a day's adverse excursion (prior close → intraday low for a long; → high for a short) reaches 12 points, the position is stopped out at −12 points for that day and goes flat.

**(b) Dynamic position sizing** — the core risk rule. Each day:

```
room       = balance − trailing_floor            # $ distance to failure
risk/contract = stop_pts × $10 × safety          # = 12 × 10 × 1.5 = $180
contracts  = min( base(=3),  floor(room / risk_per_contract),  cap(=10) )
```

So the position is sized such that **even a full stop-out cannot push the account through the trailing floor** (with a 1.5× safety cushion). When the buffer is small, size shrinks — to **zero** if necessary (the strategy stands down rather than risk a breach). When the buffer is large (after the lock), it scales up toward the base/cap to reach the target faster.

**Tuned parameters (fixed in advance):** `ema_fast=20, ema_slow=100, stop_pts=12, base_contracts=3, safety=1.5, contract_cap=10`.

### 5.3 The lock interaction
Because sizing scales with `room`, and `room` jumps once Apex locks the floor at +$100, the strategy naturally sizes up in the safe "post-lock" phase and coasts the final ~$400 to target.

---

## 6. Cost & friction model

Charged on **turnover only** (you pay when you trade, not for holding):

| Component | Value |
|---|---|
| Commission | $1.50 per contract, per side |
| Slippage (normal) | 0.4 point round-trip (≈ $4 / contract) |
| Extra slippage on stop-outs | +1.0 point (fast-market fills) |

We report **two numbers every run: "clean" (no slippage) and "with real fills"** so the friction drag is explicit, never hidden.

---

## 7. Backtest methodology (the simulator)

- **Rolling combine attempts:** start a fresh simulated combine every **10 trading days** across the whole history; each attempt runs up to a **180-trading-day horizon** (a real eval isn't run forever).
- **Per-day loop (EOD-trailing):** size the position (§5.2); compute the day's P&L from the position held (prior close → close), using the day's **high/low to capture the intraday drawdown extreme**; subtract turnover cost; **check the intraday minimum against the trailing floor → fail on breach**; update balance; raise the EOD peak and floor; apply the **+$2,600 lock**; **pass when balance ≥ target**.
- **Outcome per attempt:** `pass` (hit target), `fail` (breached trailing drawdown), or `horizon_expired` (ran out of days).
- **Reported metrics:** pass rate, median days-to-pass, attempt count, failure-reason breakdown.
- **Unit-tested:** signal direction/causality, sizing respects floor and cap, a winning combine locks and passes, a real breach is detected, and the overlay prevents a breach by de-risking. (8 tests, all passing.)

---

## 8. Results

Rolling combine, every 10 days, 180-day horizon, ~174–202 attempts.

| Data / account | Pass rate (clean) | Pass rate (real fills) | Median days |
|---|---|---|---|
| Spot proxy — $50k | 52.9% | 42.5% | 16 |
| Spot proxy — $100k | 45.4% | 31.0% | 50 |
| **Real MGC (Databento) — $50k** | 50.5% | **38.1%** | 19 |
| Real MGC — $100k | 42.1% | 31.7% | 49 |

Real MGC run: 2020-01-01 .. 2026-07-31, 2,046 daily bars, 202 rolling attempts, corrected turnover-cost model.

**Headline: ~38% realistic (real-fill) pass rate on the $50k REAL contract — roughly 2 passes in 5 attempts.**

---

## 9. Honest limitations & risks (please scrutinize)

1. **Daily bars.** We use daily H/L (which *do* capture intraday extremes for the drawdown check), but the intraday *order* of moves is idealized, and multiple intraday trades aren't modeled.
2. **Fill assumptions.** Stops are modeled with 0.4pt + 1.0pt friction; real fast-market slippage on gold could be worse.
3. **Regime flattery.** 2020–2026 includes gold's strong bull trend. Trend strategies are flattered by trends; a sideways/whipsaw gold market lowers the pass rate materially. This is the single biggest risk.
4. **Overlapping samples.** ~200 rolling attempts over 6 years are **heavily overlapping and NOT independent** — the effective sample is far smaller, so the pass rate has wide real uncertainty.
5. **Proxy vs contract.** Spot ≠ futures exactly (roll, session, basis); real MGC (already ~7pts lower than proxy) is the number that counts.
6. **Sim-feed differences.** Apex evaluations run on a sim data feed that may differ slightly from Databento.
7. **The edge is modest.** ~0.5–0.7 Sharpe. This is not a high-conviction alpha; it's a tuned trend premium.

---

## 10. Validation pipeline

| Stage | Status |
|---|---|
| Find & validate the edge (hunt, bootstrap, plateau, DSR) | **Done** |
| Design + tune the drawdown overlay vs Apex rules | **Done** |
| Rolling backtest on **real MGC** (Databento) | **Done** (turnover-cost re-run queued) |
| Forward **paper** on real MGC (track one live combine over weeks) | **In progress** (`mgc-paper` workflow) |
| Independent mentor review | **This document** |
| Immigration-attorney opinion (F-1) | **Not started — required** |
| Real evaluation | **Blocked** on the two gates above |

---

## 11. Economics / expectancy (rough)

At ~40% pass and a ~$20 eval fee: **~$50 in fees per funded account** on average (≈2.5 attempts). A funded account then carries the **same trailing-drawdown risk** (it can be blown), and Apex takes a share of payouts. Net: a legitimate positive-expectancy activity **contingent on the funded-account payout value**, not a salary. Variance is high; expect losing streaks.

---

## 12. Legal / regulatory gate (context for the mentor)

The trader is on an **F-1 student visa**. Trading a funded prop account for performance-based payouts is plausibly **unauthorized self-employment** under F-1 rules — genuinely ambiguous, and the downside is immigration status, not the $20 fee. **No real evaluation will be funded without a written opinion from an immigration attorney and, if applicable, DSO sign-off.** All work to date is paper/simulation, which does not implicate this.

---

## 13. Open questions for the mentor

1. Is the **overlay sizing** (stop 12pt, safety 1.5×, base 3) sound, or is there a better risk allocation for a trailing-drawdown regime?
2. Are we **fooling ourselves on the trend edge** given the bull-market period? What out-of-sample or cross-asset test would convince you it isn't regime-luck?
3. Is the **friction model** (0.4pt + 1.0pt stop) realistic for MGC, or too kind?
4. Given overlapping samples, how would you **estimate the true confidence interval** on the ~40% pass rate?
5. Is a ~40% pass, modest-Sharpe grind **worth attempting** at $20/eval, in your judgment — or is the expectancy too thin once payout-splits and funded-account mortality are included?
6. Anything structural we're missing about how Apex evaluations behave in practice vs this model?

---

## Appendix A — Parameter table

| Parameter | Value | Meaning |
|---|---|---|
| `ema_fast` / `ema_slow` | 20 / 100 | trend EMAs (daily) |
| `stop_pts` | 12 | hard stop, points ($120/contract) |
| `base_contracts` | 3 | baseline size |
| `safety` | 1.5 | sizing cushion vs floor |
| `contract_cap` | 10 | Apex $50k limit |
| commission | $1.50/side | per contract |
| slippage / stop-slip | 0.4 / +1.0 pt | friction model |
| horizon | 180 td | max days per attempt |
| step | 10 td | rolling attempt spacing |

## Appendix B — Code map (repo: gold research project, `mgc_prop/`)

- `strategy.py` — trend signal + overlay sizing (pure, tested)
- `apex.py` — Apex rules engine + combine simulator + forward tracker
- `data.py` — real MGC (Databento) loader + spot-proxy fallback
- `backtest.py` — rolling combine backtest (clean vs friction)
- `paper.py` — forward paper account tracker (one live combine)
- `tests/` — 8 unit tests · `PRE_REGISTRATION.md` — pre-committed hypothesis & falsifiers

---

## 14. Response to mentor review — follow-up analysis (2026-08-02)

We ran the tests the review demanded, on real data. Results are honest, including where they hurt.

### 14.1 Overlapping samples quantified (the "biggest statistical weakness")
Re-running with **non-overlapping, sequential** combines (truly independent attempts):

| Sampling | Attempts | Pass rate | Honest 90% CI |
|---|---|---|---|
| Overlapping (step 10) — the headline | ~174 | 42.5% | (understated) |
| **Independent (non-overlapping)** | **~14** | **35.7%** | **[18.6%, 57.5%]** |

The effective independent sample is **~14 combines — even smaller than the 40–60 guess** — and the honest 90% CI is **enormous ([~19%, ~58%])**. The true pass rate is *far* less certain than the headline. This lowers, not raises, confidence. Now quantified.

### 14.2 Overlay optimality tested (dynamic vs alternatives)
| Sizing rule | Pass rate |
|---|---|
| Dynamic (ours) | 42.5% |
| Fixed 1 contract | 42.0% |
| **Fixed 2 contracts** | **44.8%** |
| Fixed 3 contracts | 40.8% |
| Volatility-targeted | 28.2% |

**Fixed-2 matches or beats the dynamic overlay on pass rate.** The dynamic overlay's real value is **ruin-protection** — it de-risks to flat and *cannot* breach the floor, which matters for surviving a *funded* account, not for eval pass rate. Honest correction: it is optimal for *not blowing up*, not uniquely optimal for *passing*.

### 14.3 Multi-factor tested (does adding orthogonal factors help?)
Gating trend with real-yield / seasonality / volatility-regime:

| Variant | Full pass | By time-third | Regime spread |
|---|---|---|---|
| Trend only | 42.5% | 24 / 34 / 66% | 42 pts |
| + real-yield filter | 38.5% | 20 / 25 / 66% | 47 pts |
| + seasonality | 44.8% | 20 / 46 / 64% | 45 pts |
| + volatility-regime | 47.1% | 20 / 42 / 62% | 43 pts |
| + RY + vol-regime | 43.1% | 15 / 32 / 66% | 51 pts |

Every variant shows a **~42–51 point spread across time-thirds** (early ~15–24%, recent ~62–66%). **Performance is dominated by regime; factor-gating does not fix it.** The bull-market critique, confirmed and measured.

### 14.4 What we hypothesized would move the lagging scores
- **Originality (45) / robustness (72) / persistence (70):** hypothesis — a **multi-market trend portfolio** (the CTA approach) would diversify the single crowded gold signal. **Tested in §14.5 below — it did NOT work.**
- **Ready for real capital (35):** cannot be raised by code; needs a forward, out-of-sample track record over time (the "years of evidence" standard). Not faked.
### 14.5 Multi-market diversification — tested on real data, and it FAILED (honest)
We built a diversified 13-market trend portfolio (metals, energy, equity index, rates, FX, ags) on real Databento data, 2010–2026, and compared it head-to-head with single-gold:

| Portfolio | Sharpe | Max drawdown | Yearly-Sharpe spread |
|---|---|---|---|
| Diversified (13 markets) | **0.15** | **−38%** | 3.91 |
| Single gold | **0.59** | −29% | 3.92 |

**Diversification made it worse, not better.** Per-market trend Sharpes: gold +0.49, yen +0.38, equities ~+0.3, but silver, copper, euro, corn, soybeans and natgas were all **negative**. The by-year path shows a brutal trend decade (2011 −0.15, 2012 −1.07, 2015 −1.17, 2017 −1.0).

**Why (the key lesson):** a multi-*market* trend portfolio is still a single-*factor* bet — every market is wagering that trend works. When the trend factor has a bad decade, all markets lose *together*, so market-diversification gives almost no protection; it merely averages a good-trend market (gold) down toward the weak ones. This **confirms the review's "still single-factor" critique** on real data.

**Implications, stated plainly:**
- The multi-market build does **not** raise originality / robustness / persistence — empirically it underperforms. Those scores stand as the mentor gave them.
- Genuine robustness requires **orthogonal factors** (carry, mean-reversion, volatility/carry premia) that pay when trend doesn't — a multi-*factor* program, deferred.
- Single-gold's edge is partly that **gold happened to be one of the few markets where trend worked this window** — a mild winner's-curse caveat that should slightly *lower*, not raise, confidence in the gold strategy.
- **Decision:** proceed with the modest single-gold trend as the honest edge, without overselling it.


### 14.6 Vehicle ranking — which Apex micro is the best (real data, 2018–2026)
Trend + adaptive-ATR-stop overlay run as an Apex $50k EOD combine on the four tradeable micros:

| Micro | Market | Pass rate | Median days |
|---|---|---|---|
| **MGC** | **Gold** | **41.3%** | 26 |
| MNQ | Nasdaq-100 | 32.0% | 26 |
| MBT | Bitcoin | 28.7% | 37 |
| MES | S&P 500 | 28.1% | 26 |

**Gold wins — and it was the pre-committed choice, so this is confirmation, not cherry-picking.** Crypto disappointed: it trends hardest but its volatility fights the tight $2,500 drawdown, so the adaptive stop sizes it to near-nothing. Equity indices are real but weaker vehicles inside a short combine window. Conclusion: concentrate on gold. (The adaptive ATR stop also answers the review's "why not adaptive?" point.)

### 14.7 Direction & regime dependence — the deepest caveat (please read)
Question raised: is the 41% just gold's 2-year bull run, and does the algorithm catch DOWN-trends too? The signal is symmetric (long above trend, **short** below), so mechanically it trades both ways. But decomposing long vs short P&L on gold (2019–2026) is sobering:

| Year | Gold move | Algo return | Regime | P&L while SHORT |
|---|---|---|---|---|
| 2020 | +24% | +13% | UP | −5.6% |
| 2021 | −6% | **−11%** | DOWN | −4.2% |
| 2022 | +1% | +7% | chop | +3.1% |
| 2023 | +12% | +3% | UP | −5.0% |
| 2024 | +27% | +25% | UP | 0 |
| 2025 | +63% | +52% | UP | 0 |
| 2026 | −6% | +15% | DOWN | +9.5% |

**Whole period: LONG positions +105%, SHORT positions −3.2%.** Nearly all the profit came from riding gold UP; the short side is a **net loser** over the sample. In the one grinding downtrend (2021) the algo **lost 11%** and its shorts lost money (whipsawed); in a clean decline (2026) shorts worked (+9.5%).

**Honest conclusion:** the 41% pass rate is **substantially bull-dependent.** If gold enters a multi-year bear, the algo flips short automatically — but the evidence says its short side is weak-to-unproven: it can profit from a *smooth* decline but gets whipsawed in a *choppy* one. Trend-following's true enemy is not direction, it is **sideways chop.** This is the single biggest risk in the strategy and materially qualifies every pass-rate number in this document.


### 14.8 Can combining a filter add edge? (tested — no free lunch)
Tested a trend-STRENGTH filter: only take the trend when the EMAs are meaningfully separated; stand flat when tangled (chop is the proven enemy, §14.7).

| Variant | Pass rate | 2021 chop-year return | % days in market |
|---|---|---|---|
| Trend only (base) | 42.6% | −11.3% | 100% |
| + strength > 0.015 | 42.6% | −10.8% | 69% |
| + strength > 0.02 | 38.3% | −8.1% | 61% |
| + strength > 0.03 | 40.7% | **−3.2%** | 47% |

**Finding:** the filter **reduces the chop-year loss** (2021: −11.3% → −3.2%) but does **not** improve the combine pass rate — tighter filters lower it. It trades pass-rate for chop-robustness; there is **no free edge**. Consistent with the earlier indicator search (which found nothing): **no indicator combination adds net edge to this strategy.** A trend-strength filter is a legitimate *robustness* tool for the funded phase (if a gold bear/chop regime worries you), not an edge booster. The forward test runs the FROZEN base strategy; the filter is a documented candidate, not bolted on mid-test.
