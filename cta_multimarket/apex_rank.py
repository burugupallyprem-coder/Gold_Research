"""Rank Apex-tradeable MICRO futures as vehicles for the trend + drawdown-overlay strategy.
Same Apex $50k EOD rules, but each market uses (a) its micro contract $/point and (b) an
ADAPTIVE volatility-scaled stop (ATR-based) so the risk fits each instrument's scale.
Answers: gold vs S&P vs Nasdaq vs Bitcoin - which is the best Apex vehicle? RESEARCH ONLY.

Price series come from the full continuous contract (GC/ES/NQ/BTC); P&L uses the MICRO
$/point (MGC/MES/MNQ/MBT) since Apex is traded in micros. Costs on turnover."""

from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
TARGET, TRAIL, CAP, HORIZON = 3000.0, 2500.0, 10, 180
COMMISSION_SIDE = 1.5

# root -> (micro $/point, micro name, sector). Price data uses the full continuous root.
APEX_MICROS = {
    "GC":  (10.0,  "MGC Micro Gold",     "metals"),
    "ES":  (5.0,   "MES Micro S&P 500",  "equity"),
    "NQ":  (2.0,   "MNQ Micro Nasdaq",   "equity"),
    "BTC": (0.10,  "MBT Micro Bitcoin",  "crypto"),
    "CL":  (100.0, "MCL Micro Crude",    "energy"),
    "6E":  (12500.0, "M6E Micro EUR/USD","fx"),
}


def _atr(h, l, c, n=14):
    pc = c.shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def combine(close, high, low, sig, atr, start_i, dpp, atr_mult=1.5, safety=1.5,
            base=3, slip_frac=0.0004, stopslip_frac=0.001):
    """One Apex $50k EOD combine with an adaptive ATR stop. Returns (passed, days)."""
    bal = 0.0; peak = 0.0; floor = -TRAIL; locked = False; sprev = 0.0
    end = min(len(close), start_i + HORIZON)
    for k in range(max(1, start_i), end):
        stop_pts = atr[k] * atr_mult
        if not np.isfinite(stop_pts) or stop_pts <= 0:
            continue
        risk = stop_pts * dpp
        room = bal - floor
        c = max(0, min(base, int(room / (risk * safety)), CAP))
        signed = sig[k] * c
        turn = abs(signed - sprev)
        slip_pts = slip_frac * close[k - 1]         # slippage scales with price level
        tcost = turn * (COMMISSION_SIDE + slip_pts * dpp)
        if signed == 0:
            real = -tcost; imin = bal - tcost; stopped = False
        else:
            pc = close[k - 1]
            if signed > 0: adv = max(pc - low[k], 0.0); pcl = close[k] - pc
            else:          adv = max(high[k] - pc, 0.0); pcl = pc - close[k]
            n = abs(signed); stopped = adv >= stop_pts
            ss = stopslip_frac * pc if stopped else 0.0
            gp = (-stop_pts if stopped else pcl)
            real = (gp * dpp - ss * dpp) * n - tcost
            imin = bal + (-(min(adv, stop_pts) * dpp + ss * dpp)) * n - tcost
        if imin < floor:
            return (0, k - start_i + 1)
        bal += real; sprev = 0.0 if stopped else signed
        if not locked:
            peak = max(peak, bal); floor = peak - TRAIL
            if peak >= TRAIL + 100: locked = True; floor = 100.0
        if bal >= TARGET:
            return (1, k - start_i + 1)
    return (0, end - start_i)


def rank_market(ohlc, dpp, step=10):
    close = ohlc["close"]; high = ohlc["high"]; low = ohlc["low"]
    # LONG-ONLY trend (clip short side) - the honest validated config. Causal: shift(1).
    sig = np.sign(close.ewm(span=20, adjust=False).mean()
                  - close.ewm(span=100, adjust=False).mean()).clip(lower=0).shift(1).fillna(0.0).values
    atr = _atr(high, low, close).shift(1).values
    cv, hv, lv = close.values, high.values, low.values
    outs = [combine(cv, hv, lv, sig, atr, s, dpp) for s in range(120, len(cv) - 30, step)]
    passes = [o for o, _ in outs]
    days = [d for o, d in outs if o]
    n = len(passes)
    return dict(attempts=n, pass_rate=round(100 * sum(passes) / n, 1) if n else 0.0,
                median_days=int(np.median(days)) if days else None)


def build_report(ohlc_by_root):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = [f"[APEX-RANK] {ts} - RESEARCH ONLY (no real money)",
         "LONG-ONLY trend + adaptive-ATR-stop overlay, Apex $50k EOD, per micro contract:",
         ""]
    rows = []
    for root, (dpp, name, sec) in APEX_MICROS.items():
        if root not in ohlc_by_root:
            L.append(f"  {name:20} [{sec:6}] - no data"); continue
        r = rank_market(ohlc_by_root[root], dpp)
        rows.append((name, sec, r))
    for name, sec, r in sorted(rows, key=lambda x: -x[2]["pass_rate"]):
        L.append(f"  {name:20} [{sec:6}] pass {r['pass_rate']:5.1f}%  median {r['median_days']}d  ({r['attempts']} attempts)")
    L += ["", "NOTE: optimistic (daily bars, modeled fills); crypto's volatility makes its number the least reliable.",
          "Overlapping windows -> wide true CI (see STRATEGY_REVIEW 14.1). Rank, not a guarantee."]
    return "\n".join(L)


def main():
    from .data import load_markets_ohlc
    roots = list(APEX_MICROS)
    ohlc = load_markets_ohlc(roots=roots)
    report = build_report(ohlc)
    print(report)
    out = ROOT / "reports"; out.mkdir(exist_ok=True)
    (out / f"apex_rank_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.md").write_text(report, encoding="utf-8")
    try:
        import sys; sys.path.insert(0, str(ROOT.parent))
        from execution import notifier; notifier.post(report)
    except Exception:
        pass


if __name__ == "__main__":
    main()
