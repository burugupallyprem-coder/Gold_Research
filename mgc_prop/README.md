# mgc_prop - Gold-trend strategy vs Apex prop rules (MGC)

Turns the one validated edge (a faster 20/100 gold trend) into a drawdown-aware strategy sized
for an **Apex Trader Funding $50k EOD-trailing** evaluation on Micro Gold (MGC). Research/paper only.

## Layout
- `strategy.py` - trend signal + overlay sizing/stop (pure, causal, tuned defaults).
- `apex.py` - Apex rules engine (verified 2026) + honest EOD-trailing combine simulator.
- `data.py` - price loader: gold SPOT proxy now; seam for real MGC Databento bars (CI) later.
- `backtest.py` - reproducible pass-rate + median-days analysis.
- `tests/` - unit tests (signal, sizing, lock/pass, breach path, overlay-prevents-breach).
- `PRE_REGISTRATION.md` - the honest, pre-committed hypothesis + expectations + falsifiers.

## Run
```bash
python -m mgc_prop.backtest              # reproduce the pass-rate study on gold spot proxy
python mgc_prop/tests/test_mgc_prop.py   # unit tests
```

## Honest status
Optimistic backtest: ~51% pass on $50k (median ~19d). Real expectation ~35-45% after haircut.
**Next step:** swap the spot proxy for real MGC Databento bars and run it FORWARD as paper before
any eval fee. Real money is F-1 gated (attorney + DSO + approval) - not yet.
