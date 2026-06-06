# Strategy — Gold SMC v8 (XAU/USD port)

Faithful port of the Alpaca/GLD strategy, adapted for OANDA spot gold (XAU/USD),
which trades ~24/5 so the London sessions are enabled (unlike the GLD version).

**Entry triggers (OR)**
- Displacement candle: body > 1.2×ATR(14) and body > 1.5×opposite wick
- Fair Value Gap (3-bar): gap > 0.25×ATR

**Filter gates (AND)**
- HTF trend alignment: 50-EMA on 4H bars (M15 rolling-MA fallback until ≥50 H4 bars exist)
- Volume > 1.2 × 20-bar SMA (OANDA tick volume)
- Max 3 trades/day, flat-only entries

**NY Opening 2-candle play**
- If the 8:00 ET and 8:15 ET bars close the same direction → armed that side for the day
- RSI/VWAP confirmation at entry

**Risk**
- Stop: swing-based if within 0.5–4×ATR, else 1.5×ATR
- Target: 2.5RR default, 3.0RR for NY Opening
- Size: (equity × 1%) / stop distance, capped by MAX_POSITION_USD
- Break-even: stop moved to entry once +1.5R is reached

**Confidence gate (0–100, threshold 60)**
trigger +30, HTF +20, volume +15, NY +10, macro ±25 (macro NEUTRAL in backtest
by default — see honest note in confidence.py).
