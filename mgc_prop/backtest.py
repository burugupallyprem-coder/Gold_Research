"""Reproducible Apex combine backtest for the MGC gold-trend + overlay strategy.
Starts a fresh combine every `step` days and reports the honest pass-rate + median
days-to-pass. Numbers are OPTIMISTIC (spot proxy, daily bars, perfect stop fills):
haircut to real expectations before risking an eval fee."""

import numpy as np
from .strategy import trend_signal, trend_position, DEFAULTS
from .apex import simulate_combine


def run_backtest(ohlc, account="50k", step=10, horizon=180, cfg=None,
                 slippage_pts=0.0, stop_slip_pts=0.0):
    cfg = {**DEFAULTS, **(cfg or {})}
    close = ohlc["close"].values; high = ohlc["high"].values; low = ohlc["low"].values
    # LONG-ONLY trend, exit on flip. (Chandelier + re-entry were tested and did NOT survive
    # causal validation - the earlier gain was a look-ahead artifact; see MENTOR docs.)
    sig = trend_signal(ohlc["close"], cfg["ema_fast"], cfg["ema_slow"]).clip(lower=0).shift(1).fillna(0.0).values
    passes = 0; total = 0; days = []; reasons = {}
    for s in range(0, len(close) - 30, step):
        ok, d, why = simulate_combine(close, high, low, sig, s, account,
                                      cfg["stop_pts"], cfg["base_contracts"],
                                      cfg["safety"], horizon,
                                      slippage_pts, stop_slip_pts)
        total += 1; passes += ok
        if ok: days.append(d)
        reasons[why] = reasons.get(why, 0) + 1
    return dict(account=account, attempts=total, pass_rate=round(100 * passes / total, 1),
                median_days=int(np.median(days)) if days else None, reasons=reasons, cfg=cfg)


def main():
    from datetime import datetime, timezone
    from pathlib import Path
    from .data import load_prices
    ohlc, source = load_prices(prefer_mgc=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    span = f"{ohlc.index[0].date()}..{ohlc.index[-1].date()} ({len(ohlc)} bars)"
    lines = [f"[MGC-BACKTEST] {ts} - RESEARCH ONLY (no real money)",
             f"data source: {source} | {span}",
             "rolling Apex combine attempts (fresh start every 10 trading days):"]
    # realistic MGC friction: ~0.4pt round-trip slippage, +1.0pt worse fills on stop-outs
    SLIP, STOP_SLIP = 0.4, 1.0
    for acct in ("50k", "100k"):
        clean = run_backtest(ohlc, acct)
        stressed = run_backtest(ohlc, acct, slippage_pts=SLIP, stop_slip_pts=STOP_SLIP)
        lines.append(f"  Apex {acct}: pass {clean['pass_rate']}% clean  ->  "
                     f"{stressed['pass_rate']}% with real fills  "
                     f"(median {stressed['median_days']}d, {clean['attempts']} attempts)")
    lines.append(f"friction modelled: {SLIP}pt round-trip slippage + {STOP_SLIP}pt extra on stop-outs")
    haircut = ("NOTE: even on real MGC this is optimistic (daily bars can't see every intraday "
               "spike; stops assumed to fill). Treat it as a ceiling, not a promise.")
    lines.append(haircut)
    out = "\n".join(lines)
    print(out)
    rep = Path(__file__).resolve().parent / "reports"
    rep.mkdir(exist_ok=True)
    (rep / f"mgc_backtest_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.md").write_text(out, encoding="utf-8")
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from execution import notifier
        notifier.post(out)
    except Exception:
        pass


if __name__ == "__main__":
    main()
