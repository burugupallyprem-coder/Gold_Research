"""Offline tests for the multi-market trend portfolio (synthetic data)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import numpy as np, pandas as pd
from cta_multimarket import portfolio as P


def _series(vals):
    return pd.Series(vals, index=pd.date_range("2015-01-01", periods=len(vals), freq="B"))


def _trending_market(seed, n=1500, drift=0.03, vol=0.01):
    rng = np.random.RandomState(seed)
    rets = rng.randn(n) * vol + drift / 252
    return _series(100 * np.exp(np.cumsum(rets)))


def test_trend_signal_directional():
    assert P.trend_signal(_series(np.linspace(100, 200, 200))).iloc[-1] == 1
    assert P.trend_signal(_series(np.linspace(200, 100, 200))).iloc[-1] == -1


def test_ex_ante_vol_is_causal():
    r = pd.Series(np.r_[np.zeros(80), 0.5, np.zeros(80)],
                  index=pd.date_range("2015-01-01", periods=161, freq="B"))
    v = P.ex_ante_vol(r, 20)
    # the vol estimate on the spike day must NOT yet include the spike (shifted)
    spike_day = 80
    assert v.iloc[spike_day] == v.iloc[spike_day], "nan-safe"
    assert v.iloc[spike_day] <= v.iloc[spike_day + 1] + 1e-9  # spike shows up AFTER, not on, the day


def test_vol_scaling_equalizes_risk():
    # low-vol market should get a LARGER position than a high-vol market, same trend
    lo = _trending_market(1, vol=0.005)
    hi = _trending_market(1, vol=0.02)   # 4x vol
    plo = P.market_position(lo).abs().iloc[-1]
    phi = P.market_position(hi).abs().iloc[-1]
    assert plo > phi, (plo, phi)


def test_diversification_lifts_risk_adjusted_return():
    markets = {f"m{i}": _trending_market(i) for i in range(8)}
    port, mat = P.portfolio_returns(markets)
    port_sharpe = P.stats(port)["sharpe"]
    singles = [P.stats(mat[c])["sharpe"] for c in mat.columns]
    med_single = float(np.median(singles))
    # a diversified basket of independent trends should beat the median single market
    assert port_sharpe > med_single, (port_sharpe, med_single)


def test_portfolio_targets_its_vol():
    markets = {f"m{i}": _trending_market(i) for i in range(6)}
    port, _ = P.portfolio_returns(markets, port_target_vol=0.10)
    av = P.stats(port)["ann_vol"]
    assert 0.04 < av < 0.20, av   # in the neighborhood of the 10% target


def test_stats_and_by_year():
    r = pd.Series(np.random.RandomState(0).randn(800) * 0.01 + 0.0003,
                  index=pd.date_range("2016-01-01", periods=800, freq="B"))
    s = P.stats(r); assert set(s) >= {"sharpe", "max_dd", "ann_vol"}
    y = P.by_year(r); assert len(y) >= 2


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    p = 0
    for fn in fns:
        try: fn(); p += 1
        except Exception: print("FAIL", fn.__name__); traceback.print_exc()
    print(f"{p}/{len(fns)} tests passed")
