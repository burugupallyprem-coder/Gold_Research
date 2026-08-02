"""Reproducible Apex combine backtest for the MGC gold-trend + overlay strategy.
Starts a fresh combine every `step` days and reports the honest pass-rate + median
days-to-pass. Numbers are OPTIMISTIC (spot proxy, daily bars, perfect stop fills):
haircut to real expectations before risking an eval fee."""

import numpy as np
from .strategy import trend_signal, DEFAULTS
from .apex import simulate_combine


def run_backtest(ohlc, account="50k", step=10, horizon=180, cfg=None):
    cfg = {**DEFAULTS, **(cfg or {})}
    close = ohlc["close"].values; high = ohlc["high"].values; low = ohlc["low"].values
    sig = trend_signal(ohlc["close"], cfg["ema_fast"], cfg["ema_slow"]).shift(1).fillna(0.0).values
    passes = 0; total = 0; days = []; reasons = {}
    for s in range(0, len(close) - 30, step):
        ok, d, why = simulate_combine(close, high, low, sig, s, account,
                                      cfg["stop_pts"], cfg["base_contracts"],
                                      cfg["safety"], horizon)
        total += 1; passes += ok
        if ok: days.append(d)
        reasons[why] = reasons.get(why, 0) + 1
    return dict(account=account, attempts=total, pass_rate=round(100 * passes / total, 1),
                median_days=int(np.median(days)) if days else None, reasons=reasons, cfg=cfg)


if __name__ == "__main__":
    from .data import load_ohlc
    ohlc = load_ohlc()
    for acct in ("50k", "100k"):
        r = run_backtest(ohlc, acct)
        print(f"Apex {acct}: pass {r['pass_rate']}%  median {r['median_days']}d  "
              f"over {r['attempts']} attempts  | {r['reasons']}")
