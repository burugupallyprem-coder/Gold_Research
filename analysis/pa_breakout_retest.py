"""
analysis/pa_breakout_retest.py -- STANDALONE test of the "Advanced Price Action"
breakout+retest idea on gold. READ-ONLY: imports nothing from and modifies
nothing in the live bot (same rule as analysis/intraday_backtest.py).

WHAT THIS IS
------------
Peter sent a screenshot ("Advanced Price Action": 3-drives top + falling wedge +
demand zone + breakout + retest). We agreed to test the *tradable core* stripped
to its engine: **break a resistance level, retest it, enter on the reclaim.**
Long-only (matches the bullish illustration and the project's long-or-flat ethos).

HONEST FRAME (do not skip)
--------------------------
A single winning screenshot is selection bias, not evidence. This is the same
family as SMC, which this project already tested and KILLED. Gold's spread +
slippage is exactly what eats intraday/scalp edges. So this file's whole job is
to show GROSS vs NET through an honest gauntlet and let the data decide:

  1. headline vs buy-and-hold gold
  2. RANDOM-ENTRY CONTROL (decisive: does the retest timing beat a coin flip?)
  3. cost stress 1x/3x/5x
  4. sensitivity grid (context only, never for picking a winner)
  5. sealed last-12-months holdout (--holdout, one-shot)

House rules enforced in code: entry = next-bar open; STOP-FIRST when a bar
straddles both stop and target; costs charged both sides; no look-ahead (levels
and ATR use only past bars).

Usage:
    python analysis/pa_breakout_retest.py                 # in-sample (M15)
    python analysis/pa_breakout_retest.py --tf H4
    python analysis/pa_breakout_retest.py --holdout
    python analysis/pa_breakout_retest.py --seeds 1000
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config import SETTINGS  # noqa: E402

CANDLES = ROOT / "data" / "candles"


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
def load(tf: str) -> pd.DataFrame:
    p = CANDLES / f"{SETTINGS.instrument}_{tf}.csv"
    if not p.exists():
        sys.exit(f"No candles at {p}\nFetch first: python data/fetch_oanda.py --tf {tf}")
    st = p.stat()
    key = hashlib.md5(f"{p}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()[:16]
    cache = Path(tempfile.gettempdir()) / f"pa_{tf}_{key}.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    df = pd.read_csv(p, dtype={"volume": "int64"})
    df["time"] = pd.to_datetime(df["time"], utc=True, format="ISO8601")
    df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    df["date"] = df["time"].dt.tz_convert("UTC").dt.date
    try:
        df.to_pickle(cache)
    except Exception:
        pass
    return df


def atr(df: pd.DataFrame, n: int = 14) -> np.ndarray:
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    prev = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum.reduce([h - l, np.abs(h - prev), np.abs(l - prev)])
    # trailing SMA of TR, shifted so bar i uses only bars < i
    out = np.full(len(tr), np.nan)
    csum = np.cumsum(tr)
    for i in range(n, len(tr)):
        out[i] = (csum[i - 1] - csum[i - 1 - n]) / n
    return out


def swing_highs(high: np.ndarray, low: np.ndarray, w: int) -> np.ndarray:
    """Confirmed fractal swing highs. Bar i is a swing high if its high is the
    max of [i-w, i+w] and strictly greater on the left. Confirmed only at i+w."""
    n = len(high)
    sh = np.zeros(n, bool)
    if n < 2 * w + 1:
        return sh
    swv = np.lib.stride_tricks.sliding_window_view
    hw = swv(high, 2 * w + 1)
    c = slice(w, n - w)
    sh[c] = (high[c] > hw[:, :w].max(axis=1)) & (high[c] >= hw[:, w + 1:].max(axis=1))
    return sh


# ---------------------------------------------------------------------------
# parameters
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PAParams:
    pivot_w: int = 6            # fractal half-width for resistance swings
    break_margin: float = 0.5  # close must exceed level by this many ATRs
    retest_max: int = 20       # bars after breakout to allow a retest
    retest_tol: float = 0.5    # retest low must come within this many ATRs of level
    fail_buf: float = 1.0      # close this many ATRs below level => failed break, cancel
    stop_buf: float = 0.5      # stop this many ATRs below the retest low
    target_r: float = 2.0      # take-profit in R multiples
    max_hold: int = 40         # bars; exit if neither stop nor target hit
    level_max_age: int = 200   # ignore resistance older than this many bars
    require_reclaim: bool = True   # entry needs a bullish bar closing back above level

    def label(self) -> str:
        return (f"w{self.pivot_w}/brk{self.break_margin:g}/rt{self.retest_max}"
                f"/tol{self.retest_tol:g}/tgt{self.target_r:g}R/hold{self.max_hold}")


@dataclass
class Setup:
    entry_idx: int
    entry_px: float
    stop_px: float
    r_pts: float
    level: float
    break_idx: int
    retest_idx: int


# ---------------------------------------------------------------------------
# signal generation -- one linear pass, no look-ahead
# ---------------------------------------------------------------------------
def generate(df: pd.DataFrame, p: PAParams):
    o = df["open"].to_numpy(); h = df["high"].to_numpy()
    l = df["low"].to_numpy(); c = df["close"].to_numpy()
    a = atr(df, 14)
    sh = swing_highs(h, l, p.pivot_w)
    n = len(df)

    # resistance levels become "known" only when confirmed (index + pivot_w).
    # Kept in a plain list with a left pointer `head` that drops levels older
    # than level_max_age, so the active-scan stays O(recent), not O(all-history).
    from collections import deque
    levels: deque[tuple[int, float]] = deque()     # (confirm_idx, level_price)
    setups: list[Setup] = []
    funnel = {"breakouts": 0, "retested": 0, "reclaimed": 0, "SETUP": 0, "failed_break": 0}

    i = p.pivot_w + 1
    while i < n - 1:
        ai = a[i]
        if not np.isfinite(ai) or ai <= 0:
            i += 1
            continue

        # register any swing high that becomes confirmed at bar i (pivot at i-w)
        pj = i - p.pivot_w
        if pj >= 0 and sh[pj]:
            levels.append((i, h[pj]))
        # prune levels that have aged out
        while levels and i - levels[0][0] > p.level_max_age:
            levels.popleft()

        # breakout: nearest active resistance whose break margin is cleared
        broke = None
        cprev = c[i - 1]
        thresh = p.break_margin * ai
        for (ci, lv) in levels:
            if lv > cprev and c[i] > lv + thresh:
                broke = lv
                break
        if broke is None:
            i += 1
            continue

        funnel["breakouts"] += 1
        level = broke
        break_idx = i

        # walk forward for the retest, then the reclaim entry
        retest_idx = -1
        entry_idx = -1
        j = i + 1
        end = min(n - 1, i + p.retest_max)
        while j <= end:
            aj = a[j] if np.isfinite(a[j]) and a[j] > 0 else ai
            # failed breakout: decisive close back below the level
            if c[j] < level - p.fail_buf * aj:
                funnel["failed_break"] += 1
                break
            # retest: bar dips to within tol ATRs of the level from above
            if retest_idx < 0 and l[j] <= level + p.retest_tol * aj:
                retest_idx = j
            # entry: after a retest, a bullish reclaim bar closing above the level
            if retest_idx >= 0 and j > retest_idx:
                reclaim = (c[j] > o[j] and c[j] > level) if p.require_reclaim else True
                if reclaim:
                    entry_idx = j + 1
                    break
            j += 1

        if retest_idx >= 0:
            funnel["retested"] += 1
        if entry_idx > 0 and entry_idx < n:
            funnel["reclaimed"] += 1
            retest_low = float(l[retest_idx:entry_idx].min())
            entry_px = float(o[entry_idx])
            aj = a[entry_idx] if np.isfinite(a[entry_idx]) and a[entry_idx] > 0 else ai
            stop_px = retest_low - p.stop_buf * aj
            r_pts = entry_px - stop_px
            if r_pts > 0:
                setups.append(Setup(entry_idx, entry_px, stop_px, r_pts,
                                    level, break_idx, retest_idx))
                funnel["SETUP"] += 1
            i = entry_idx + 1
            continue

        i = (retest_idx if retest_idx > 0 else break_idx) + 1

    return setups, funnel, {"o": o, "h": h, "l": l, "c": c}


# ---------------------------------------------------------------------------
# simulation
# ---------------------------------------------------------------------------
def sim_one(entry_idx, entry_px, stop_px, r_pts, arr, target_mult, cost_side,
            max_hold) -> tuple[float, str]:
    h, l, c = arr["h"], arr["l"], arr["c"]
    n = len(c)
    target = entry_px + target_mult * r_pts
    last = min(n - 1, entry_idx + max_hold)
    exit_px, reason = float(c[last]), "max_hold"
    for k in range(entry_idx, last + 1):
        if l[k] <= stop_px:                 # STOP FIRST
            exit_px, reason = stop_px, "stop"
            break
        if h[k] >= target:
            exit_px, reason = target, "target"
            break
    net_r = ((exit_px - entry_px) - 2.0 * cost_side) / r_pts
    return net_r, reason


def run(setups, arr, target_mult, cost_side, max_hold, day_of):
    rs, reasons, days = [], [], []
    for s in setups:
        nr, why = sim_one(s.entry_idx, s.entry_px, s.stop_px, s.r_pts, arr,
                          target_mult, cost_side, max_hold)
        rs.append(nr); reasons.append(why); days.append(day_of[s.entry_idx])
    return np.array(rs), reasons, days


def metrics(rs, reasons, days, all_days, risk_pct=0.01):
    if len(rs) == 0:
        return {"trades": 0}
    pos = {d: i for i, d in enumerate(all_days)}
    daily = np.zeros(len(all_days))
    for r, d in zip(rs, days):
        if d in pos:
            daily[pos[d]] += r
    rets = daily * risk_pct
    eq = np.cumprod(1 + rets)
    peak = np.maximum.accumulate(eq)
    dd = float((eq / peak - 1).min())
    sd = rets.std(ddof=1)
    sharpe = float(rets.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0
    wins = rs[rs > 0]; losses = rs[rs <= 0]
    pf = float(wins.sum() / -losses.sum()) if losses.sum() < 0 else np.inf
    return {
        "trades": len(rs), "win_rate": float((rs > 0).mean()),
        "avg_r": float(rs.mean()), "total_r": float(rs.sum()),
        "profit_factor": pf, "sharpe": sharpe, "maxdd": dd,
        "target": reasons.count("target"), "stop": reasons.count("stop"),
        "maxhold": reasons.count("max_hold"),
        "gross_r": float(rs.sum() + 0),  # net already; gross shown separately in caller
    }


def buy_hold(df, all_days):
    closes = df.groupby("date")["close"].last().reindex(all_days).ffill()
    ret = closes.pct_change().fillna(0).to_numpy()
    eq = np.cumprod(1 + ret); peak = np.maximum.accumulate(eq)
    yrs = max(len(all_days) / 252, 1e-9)
    sd = ret.std(ddof=1)
    return {"sharpe": float(ret.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0,
            "maxdd": float((eq / peak - 1).min()),
            "cagr": float(eq[-1] ** (1 / yrs) - 1)}


def random_control(setups, arr, target_mult, cost_side, max_hold, day_of,
                   all_days, seeds, window, risk_pct=0.01, rng_seed=7):
    """Same breakouts, same R geometry & bracket, but enter at a RANDOM bar in
    the [breakout+1, breakout+window] band instead of at the reclaim."""
    rng = np.random.default_rng(rng_seed)
    n = len(arr["c"])
    cand = [(s, s.break_idx + 1, min(n - 1, s.break_idx + window)) for s in setups]
    pos = {d: i for i, d in enumerate(all_days)}
    totals, sharpes = [], []
    for _ in range(seeds):
        daily = np.zeros(len(all_days))
        tot = 0.0; any_t = False
        for s, lo, hi in cand:
            if hi <= lo:
                continue
            ei = int(rng.integers(lo, hi + 1))
            entry = float(arr["o"][ei])
            nr, _ = sim_one(ei, entry, entry - s.r_pts, s.r_pts, arr,
                            target_mult, cost_side, max_hold)
            tot += nr; any_t = True
            d = day_of[ei]
            if d in pos:
                daily[pos[d]] += nr
        if not any_t:
            continue
        totals.append(tot)
        rets = daily * risk_pct
        sd = rets.std(ddof=1)
        sharpes.append(float(rets.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0)
    return {"total_r": np.array(totals), "sharpe": np.array(sharpes)}


def pct_rank(v, d):
    return float((d < v).mean() * 100) if len(d) else np.nan


def show(name, m):
    if not m.get("trades"):
        print(f"  {name:<34} NO TRADES"); return
    print(f"  {name:<34} n={m['trades']:>4}  win={m['win_rate']*100:>5.1f}%  "
          f"avgR={m['avg_r']:>+6.3f}  totR={m['total_r']:>+8.1f}  "
          f"PF={m['profit_factor']:>5.2f}  Sharpe={m['sharpe']:>+6.2f}  DD={m['maxdd']*100:>6.1f}%")


def line(ch="-", n=80):
    print(ch * n)


def sensitivity(base):
    out = [base]
    for tr in (1.0, 1.5, 3.0):
        out.append(replace(base, target_r=tr))
    for bm in (0.25, 1.0):
        out.append(replace(base, break_margin=bm))
    for rt in (10, 40):
        out.append(replace(base, retest_max=rt))
    for w in (3, 10):
        out.append(replace(base, pivot_w=w))
    out.append(replace(base, require_reclaim=False))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="M15")
    ap.add_argument("--spread", type=float, default=SETTINGS.spread_usd)
    ap.add_argument("--slippage", type=float, default=SETTINGS.slippage_usd)
    ap.add_argument("--seeds", type=int, default=1000)
    ap.add_argument("--holdout", action="store_true")
    ap.add_argument("--split", default="2025-06-05", help="in-sample/holdout boundary")
    args = ap.parse_args()

    cost_side = args.spread + args.slippage
    base = PAParams()
    df_all = load(args.tf)
    split = pd.to_datetime(args.split).date()

    if args.holdout:
        df = df_all[df_all["date"] >= split].reset_index(drop=True)
        tag = "SEALED HOLDOUT (last 12m)"
    else:
        df = df_all[df_all["date"] < split].reset_index(drop=True)
        tag = "IN-SAMPLE"

    print(f"\nADVANCED PRICE ACTION -- breakout+retest engine | {SETTINGS.instrument} {args.tf}")
    print(f"  cost {cost_side:.2f}/side ({2*cost_side:.2f} round-trip) | {base.label()}")
    print(f"{tag}: {df['time'].min():%Y-%m-%d} -> {df['time'].max():%Y-%m-%d}  ({len(df):,} bars)")
    if args.holdout:
        print("  *** one-shot test of the sealed period ***")
    print()

    all_days = sorted(df["date"].unique())
    day_of = df["date"].to_numpy()

    line("="); print("1. HEADLINE"); line()
    setups, funnel, arr = generate(df, base)
    rs, reasons, days = run(setups, arr, base.target_r, cost_side, base.max_hold, day_of)
    m = metrics(rs, reasons, days, all_days)
    # gross (no costs) for the cost-drag line
    gross_rs, _, _ = run(setups, arr, base.target_r, 0.0, base.max_hold, day_of)
    show("PA breakout+retest", m)
    bh = buy_hold(df, all_days)
    print(f"  {'buy-and-hold gold':<34} Sharpe={bh['sharpe']:>+6.2f}  DD={bh['maxdd']*100:>6.1f}%  CAGR={bh['cagr']*100:>5.1f}%")
    if m.get("trades"):
        print(f"\n  exits: target {m['target']} | stop {m['stop']} | max-hold {m['maxhold']}")
        print(f"  gross totR {gross_rs.sum():+.1f} -> net totR {m['total_r']:+.1f}   "
              f"(costs ate {gross_rs.sum()-m['total_r']:.1f}R)")
        med_r = np.median([s.r_pts for s in setups])
        print(f"  median R = {med_r:.2f} pts;  round-trip {2*cost_side:.2f} = "
              f"{2*cost_side/med_r*100:.1f}% of R")
    print("\n  funnel:", {k: v for k, v in funnel.items()})

    line("="); print(f"2. RANDOM-ENTRY CONTROL ({args.seeds} seeds) -- decisive"); line()
    if len(setups):
        ctl = random_control(setups, arr, base.target_r, cost_side, base.max_hold,
                             day_of, all_days, args.seeds, base.retest_max)
        for key, act in (("total_r", m["total_r"]), ("sharpe", m["sharpe"])):
            d = ctl[key]
            if len(d):
                print(f"  {key:<9} PA={act:>+8.2f} | random mean={d.mean():>+8.2f} "
                      f"p5={np.percentile(d,5):>+7.2f} p95={np.percentile(d,95):>+7.2f} "
                      f"| PA pct {pct_rank(act,d):>5.1f}")
        pr = pct_rank(m["total_r"], ctl["total_r"])
        print()
        if np.isnan(pr):
            print("  VERDICT: no comparable control.")
        elif pr >= 95:
            print("  VERDICT: PA beats 95%+ of random entries -- the retest timing may carry information.")
        elif pr >= 80:
            print("  VERDICT: above most random entries but inside the noise band. Weak.")
        else:
            print("  VERDICT: PA sits INSIDE the random-entry distribution -- the retest timing")
            print("           adds nothing over a random entry after the same breakout.")

    line("="); print("3. SENSITIVITY (context only -- NOT for picking a winner)"); line()
    for v in sensitivity(base):
        vs, _, va = generate(df, v)
        vr, vre, vd = run(vs, va, v.target_r, cost_side, v.max_hold, day_of)
        show(v.label(), metrics(vr, vre, vd, all_days))

    line("="); print("4. COST STRESS"); line()
    for mult in (1, 3, 5):
        cr, cre, cd = run(setups, arr, base.target_r, cost_side * mult, base.max_hold, day_of)
        show(f"{mult}x cost ({cost_side*mult:.2f}/side)", metrics(cr, cre, cd, all_days))

    line("=")
    print("Reminder: one instrument, gold's 2019-2026 bull regime. Beating buy-hold is not")
    print("sufficient -- clearing the random-entry control is. Paper-only, human-in-the-loop.")
    line("=")


if __name__ == "__main__":
    main()
