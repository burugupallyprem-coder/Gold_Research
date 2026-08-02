"""Backtest the diversified multi-market trend portfolio and compare it head-to-head
with the single-gold trend - to show the diversified premium is smoother and less
regime-dependent (the mentor's robustness/persistence point). RESEARCH ONLY."""

from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import portfolio as P
from .instruments import NAME, SECTOR

ROOT = Path(__file__).resolve().parent


def build_report(closes):
    port, mat = P.portfolio_returns(closes)
    ps = P.stats(port); pyr = P.by_year(port)
    # single-gold benchmark (GC alone), same construction
    gc = {"GC": closes["GC"]} if "GC" in closes else {list(closes)[0]: list(closes.values())[0]}
    g_port, _ = P.portfolio_returns(gc)
    gs = P.stats(g_port); gyr = P.by_year(g_port)

    def spread(yr):  # regime-dependence proxy: spread of yearly Sharpes
        v = list(yr.values()); return round(max(v) - min(v), 2) if v else 0.0

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = [f"[CTA-MULTIMARKET] {ts} - RESEARCH ONLY (no real money)",
         f"basket: {len(mat.columns)} markets across sectors, {ps['n']} days",
         "",
         "DIVERSIFIED trend portfolio vs SINGLE-GOLD trend (same signal, same construction):",
         f"  diversified : Sharpe {ps['sharpe']}  maxDD {ps['max_dd']}  vol {ps['ann_vol']}  "
         f"| yearly-Sharpe spread {spread(pyr)}",
         f"  single gold : Sharpe {gs['sharpe']}  maxDD {gs['max_dd']}  vol {gs['ann_vol']}  "
         f"| yearly-Sharpe spread {spread(gyr)}",
         "",
         "Read: a LOWER yearly-Sharpe spread and shallower maxDD = less regime-dependent = more robust.",
         "",
         "Per-market standalone Sharpe (trend, vol-scaled):"]
    per = sorted(((c, P.stats(mat[c])["sharpe"]) for c in mat.columns), key=lambda x: -x[1])
    for c, sh in per:
        L.append(f"  {c:4} {NAME.get(c,c):12} [{SECTOR.get(c,'?'):6}] Sharpe {sh}")
    L.append("")
    L.append("Diversified by-year Sharpe: " + ", ".join(f"{y}:{s}" for y, s in sorted(pyr.items())))
    return "\n".join(L), dict(diversified=ps, single_gold=gs)


def main():
    from .data import load_markets
    closes = load_markets()
    report, _ = build_report(closes)
    print(report)
    out = ROOT / "reports"; out.mkdir(exist_ok=True)
    (out / f"cta_backtest_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.md").write_text(report, encoding="utf-8")
    try:
        import sys
        sys.path.insert(0, str(ROOT.parent))
        from execution import notifier
        notifier.post(report)
    except Exception:
        pass


if __name__ == "__main__":
    main()
