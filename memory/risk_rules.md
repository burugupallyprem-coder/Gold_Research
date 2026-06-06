# Risk rules (English)

- Risk per trade: 1% of equity.
- Max 3 trades per day. Flat-only: never more than one open position at a time.
- Stop: swing-based when the nearest swing is 0.5–4×ATR away; otherwise 1.5×ATR.
- Target: 2.5× risk (3.0× for NY Opening setups).
- Break-even: once a trade reaches +1.5R, the stop is moved to entry.
- Position size capped by MAX_POSITION_USD.
- Kill switch: a file named STOP at repo root halts every routine.

## Backtest cost model (honesty knobs)
- Spread: half-spread applied per side (default 0.30 USD full).
- Slippage: 0.10 USD adverse per fill.
- Commission: 0 by default (OANDA spot gold is spread-only).
- Pessimistic intrabar: if a bar touches both stop and target, the STOP fills first.
