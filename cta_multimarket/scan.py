"""Strategy x Instrument scan. Every strategy_zoo strategy on every basket instrument,
realistic costs, causal. Reports: annualized Sharpe + maxDD (all instruments) and the Apex
$50k pass rate (Apex-tradeable micros). Applies the DEFLATED-SHARPE multiple-testing gate -
with ~6 x 13 combos, several will look great by luck; only a deflated-Sharpe survivor counts.
RESEARCH ONLY."""

import sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))                    # repo root for backtest.multiple_testing

from .strategy_zoo import ZOO
from .apex_rank import combine, _atr, APEX_MICROS
from backtest.multiple_testing import deflated_sharpe_ratio, per_trade_sharpe

ANN = 252


def _volscale(r, tgt=0.10):
    import pandas as pd
    v = r.rolling(63).std().shift(1) * np.sqrt(ANN)
    return r * (tgt / v).clip(upper=4).fillna(0.0)


def eval_combo(ohlc, strat_fn, dpp=None):
    import pandas as pd
    close, high, low = ohlc["close"], ohlc["high"], ohlc["low"]
    pos = strat_fn(close, high, low).shift(1).fillna(0.0)
    ret = close.pct_change().fillna(0.0)
    r = _volscale(pos * ret - pos.diff().abs().fillna(0) * 2 / 1e4)
    rr = r.dropna()
    sharpe = float(rr.mean() / rr.std() * np.sqrt(ANN)) if rr.std() > 0 else 0.0
    eq = (1 + rr).cumprod(); mdd = float((eq / eq.cummax() - 1).min())
    pp = per_trade_sharpe((pos * ret).dropna().tolist())[0]     # per-period, for DSR
    apex = None
    if dpp is not None:
        cv, hv, lv = close.values, high.values, low.values
        atr = _atr(high, low, close).shift(1).values
        sig = pos.values
        outs = [combine(cv, hv, lv, sig, atr, s, dpp)[0] for s in range(120, len(cv) - 30, 10)]
        apex = round(100 * np.mean(outs), 1) if outs else 0.0
    return dict(sharpe=round(sharpe, 3), maxdd=round(mdd, 3), pp=pp, apex=apex)


def run(ohlc_by_root):
    rows = []
    for root, ohlc in ohlc_by_root.items():
        dpp = APEX_MICROS.get(root, (None,))[0]
        for sname, fn in ZOO.items():
            try:
                m = eval_combo(ohlc, fn, dpp)
            except Exception as e:
                continue
            rows.append({"inst": root, "strat": sname, **m})
    # deflated-Sharpe multiple-testing gate on the best per-period Sharpe
    pps = [r["pp"] for r in rows]
    best = max(rows, key=lambda r: r["pp"]) if rows else None
    dsr = 0.0
    if best:
        n = max(30, len((ohlc_by_root[best["inst"]])))
        dsr, sr0 = deflated_sharpe_ratio(best["pp"], n, pps)
    return rows, best, round(dsr, 4)


def report(rows, best, dsr):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    L = [f"[STRAT-SCAN] {ts} - RESEARCH ONLY (no real money)",
         f"{len(rows)} strategy x instrument combos, causal, realistic costs.", ""]
    L.append("Top 12 by annualized Sharpe (vol-scaled):")
    for r in sorted(rows, key=lambda x: -x["sharpe"])[:12]:
        a = f"{r['apex']}%" if r["apex"] is not None else "  -"
        L.append(f"  {r['strat']:18} {r['inst']:4} Sharpe {r['sharpe']:>5}  maxDD {r['maxdd']:>6}  Apex {a:>6}")
    L += ["", "Apex-tradeable combos by pass rate:"]
    ap = [r for r in rows if r["apex"] is not None]
    for r in sorted(ap, key=lambda x: -x["apex"])[:12]:
        L.append(f"  {r['strat']:18} {r['inst']:4} Apex {r['apex']:>5}%  Sharpe {r['sharpe']:>5}")
    L += ["",
          f"MULTIPLE-TESTING GATE: best combo '{best['strat']} on {best['inst']}' "
          f"(Sharpe {best['sharpe']}) -> DEFLATED Sharpe {dsr}.",
          ("  VERDICT: clears the deflation bar - worth a real look." if dsr >= 0.95 else
           f"  VERDICT: does NOT clear deflation (DSR {dsr} < 0.95). The apparent winners are "
           f"consistent with luck across {len(rows)} tries. Treat any single result with suspicion."),
          "", "Deploy ONLY combos that clear deflation AND hold on forward paper. Rank != guarantee."]
    return "\n".join(L)


def main():
    from .data import load_markets_ohlc
    from .instruments import ROOTS
    ohlc = load_markets_ohlc(roots=ROOTS)
    rows, best, dsr = run(ohlc)
    out = report(rows, best, dsr)
    print(out)
    rep = ROOT / "reports"; rep.mkdir(exist_ok=True)
    (rep / f"strat_scan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.md").write_text(out, encoding="utf-8")
    try:
        from execution import notifier; notifier.post(out)
    except Exception:
        pass


if __name__ == "__main__":
    main()
