"""Price data for the MGC prop backtest.

NOW: gold SPOT OHLC (OANDA XAU_USD) as a proxy - MGC futures track spot tightly for a
daily trend strategy. This lets the backtest run today with no paid data.

NEXT (real contract): swap in Micro Gold (MGC) daily bars from Databento (GLBX.MDP3,
symbol 'MGC.v.0' continuous or the front month). Same columns out, so nothing else
changes. That step needs a DATABENTO_API_KEY and is meant to run in CI, not offline."""

from pathlib import Path
import pandas as pd

# repo-relative: mgc_prop/ lives inside the OANDA project, next to data/daily/
SPOT_PROXY = str(Path(__file__).resolve().parent.parent / "data" / "daily" / "XAU_USD_D.csv")


def load_ohlc(path=SPOT_PROXY):
    df = pd.read_csv(path, parse_dates=["time"]).set_index("time").sort_index()
    return df[["open", "high", "low", "close"]].astype(float)


def load_mgc_databento(*a, **k):   # seam for the real contract - intentionally not wired offline
    raise NotImplementedError(
        "Real MGC bars require Databento (GLBX.MDP3) + DATABENTO_API_KEY; run in CI. "
        "The spot proxy (load_ohlc) is used for offline validation.")
