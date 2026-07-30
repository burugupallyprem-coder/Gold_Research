# FX port — testing the intraday SMC stack on Forex

Ports the gold intraday stack (FVG + NY-Opening, confidence gate, `fast_trend` 20/100 daily-trend
filter) to a forex major and judges it on the **same honest gauntlet** used for gold. Reuses the
exact production engine (`backtest/engine_final.py`). Paper/backtest only; not financial advice.

**The prior, stated honestly:** infrastructure ports for free; edge does not. Gold's own intraday
stack was real but thin, cost-fragile, and lost to buy-and-hold in a bull. FX majors are highly
efficient and lower-vol, so the session/price-action edge may well be thinner still. Assume it does
**not** transfer until the data says otherwise — that discipline is what caught ORB and the
price-action pattern.

## Why it runs on your machine / CI, not the cloud sandbox
A full 5-year FX M15 history is ~120k+ bars; the engine's per-bar loop exceeds the sandbox's short
shell limit. Run it where there's no limit (your laptop or a GitHub Action). The logic is
smoke-tested and engine-consistent.

## Steps
```powershell
cd C:\Users\Prem\Desktop\prem\OANDA

# 1. Fetch 5y of candles (needs your OANDA creds in .env; ~5y so the daily trend filter warms up)
python data/fetch_oanda.py --instrument EUR_USD --days 1825

# 2. Run the honest backtest (prints the verdict; saves reports/fx_port/EUR_USD_result.json)
python research/fx_port/fx_backtest.py EUR_USD
```

Swap `EUR_USD` for `GBP_USD`, `AUD_USD`, `USD_JPY`, etc. Cost defaults are per-instrument
(~1.5 pip round-trip for majors) and overridable: `--spread 0.00010 --slippage 0.000025`.

## What it reports (same as gold)
- **RAW FVG+NY** and **+ daily-trend filter**, each split selection (older 70%) vs holdout (recent 30%).
- Per trade: expectancy (R), profit factor, win%, Sharpe, % quarters positive, and the **gate**
  (≥100 trades, ≥+0.05R, PF ≥1.15, ≥60% quarters+). Long/short split. Per-year expectancy.
- **Selection-period is the honest number.** A recent-only holdout sits in one regime — label it
  inflated, exactly like gold's 2023–26 bull.

## Reading the verdict honestly
- **GATE FAIL / negative selection** → no edge to port; stop (a real result, like ORB/APA on gold).
- **GATE PASS** → still not a green light: check it beats buy-and-hold of the pair, survives 3×/5×
  cost, isn't 90% one-sided, and holds across the per-year walk-forward. Only then does it earn a
  *pre-registered forward paper trial* in its own isolated world (never mixed with gold).

## Notes / limitations
- The daily-trend filter needs ≥~300 daily bars to warm up (EMA100 + 252-day momentum); fetch ≥5y
  or the filter will silently pass too few trades.
- No real-yield leg here — that's a gold-specific fundamental; FX direction uses pure trend+momentum.
- Costs are the main port-specific unknown; the built-in 3×/5× mindset applies — if the edge only
  survives at 1× it's not real.
- Keep each instrument isolated (own result file, own future champion). Crypto/stocks stay in their
  own repos per the house rules.
