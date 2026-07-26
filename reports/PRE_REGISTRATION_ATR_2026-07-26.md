# Pre-Registration — Track 3: ATR-volatility-gated intraday stack (locked 2026-07-26)

Locked BEFORE forward paper trading so results cannot be cherry-picked later. Paper/simulation
only. No real capital. A human approves anything beyond paper. Not financial advice.

## Why this variant (and only this one)
From `reports/robustness_study_2026-07-25.md`: of every modification tested (trend variants, ADX,
exit changes, session windows, weekday filters, risk caps), the **ATR≥rolling-median volatility
gate was the only change that improved the honest selection period AND the holdout AND survived
5× cost.** It is theory-backed (ATR-bucket expectancy is monotonic — the edge concentrates in
volatile sessions), not a curve-fit. Everything else was neutral, harmful, or overfitting and was
rejected.

## Exact strategy (frozen — no parameter changes mid-trial)
- **Entries:** FVG + NY-Opening (Displacement OFF), confidence gate ON (threshold 60).
  `StrategyConfig(use_displacement=False, use_fvg=True, enable_ny_opening=True)`.
- **Direction filter (daily):** `fast_trend` = EMA 20/100 + 12-month momentum, read as-of the
  prior daily close; trade only in the allowed side.
- **Volatility gate (M15):** take the trade only if ATR-at-entry ≥ its rolling median.
  ATR = 56-bar mean of true range (~14h); median window = 2000 bars (min 200). Both causal.
- **Risk/exits (unchanged engine):** RR 2.5 / NY 3.0, break-even at 1.5R, 1% risk/trade.
- **Costs:** 0.30 spread + 0.10 slippage (engine `CostModel()`), applied at real OANDA fills.
- **Runner:** `atr_filter_paper.py`. **Schedule:** `.github/workflows/atr_filter_paper.yml`
  (every 2h weekdays, offset). **State (isolated):** `memory/atr_filter_state.json`,
  `reports/atr_filter_trades.csv`. Places **no** orders — simulation only.

## Backtest on record (what we are testing against)
| | selection ≤2023 (honest) | holdout 2024–26 (BULL) | holdout 5× cost |
|---|---|---|---|
| baseline router | +0.103R / Sharpe 0.55 | +0.213R / 1.44 | +0.015R |
| **ATR≥median** | **+0.178R / 0.64** | **+0.295R / 1.30** | **+0.122R** |

## Pre-registered hypothesis (the bar to clear)
Passes only if, across **≥ 30 forward closed trades**, realized net expectancy is **positive after
costs** AND it is **not profitable only while gold rises** (direction is logged, so a long-only
bull artifact is detectable). Expected forward ≈ +0.10 to +0.20 R/trade *if* live fills match the
backtest.

## Honest limitations locked in advance (so they can't be waved away later)
1. It **halves the trade count** (~65 trades/yr backtest) — ≥30 trades ≈ 5–6 months.
2. It sits **just past a soft parameter edge**: thresholds *below* the median degrade below
   baseline. The forward test uses exactly `1.0× rolling median`, fixed.
3. It **still did not beat buy-and-hold gold on return** in the bull (fewer trades ⇒ lower total
   return). The claim under test is *risk-adjusted / cost-robustness*, not beating passive gold.
4. Entire backtest is one bull regime; forward data (esp. any non-bull stretch) is the real judge.

## Judgment gates (no moving them)
- **≥ 30 closed trades** before any verdict. Formal **6-month checkpoint**.
- Any promotion beyond paper → months more data + Prem's explicit approval via `apply_change.py`.

## To activate (owner action)
1. Confirm GitHub secrets: `OANDA_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`.
2. Commit `atr_filter_paper.py` + `.github/workflows/atr_filter_paper.yml` (+ this doc).
3. First scheduled run auto-initializes Track 3 and posts an `[ATR-STACK]` init message. It then
   reports independently alongside baseline and Track 2. The live `baseline` champion is untouched.
