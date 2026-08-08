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


def load_mgc_databento(start="2020-01-01", end=None, max_cost_usd=5.0):
    """Real Micro Gold (MGC) DAILY bars from Databento GLBX.MDP3 (CME). Needs
    DATABENTO_API_KEY. Daily bars are cheap; a cost pre-flight still guards spend.
    Returns the same [open, high, low, close] frame as load_ohlc, indexed by date."""
    import os
    from datetime import datetime, timezone, timedelta
    import databento as db
    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        raise RuntimeError("DATABENTO_API_KEY not set - run in CI or export the key.")
    if not end:   # GLBX has a short embargo on the most recent day
        end = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    client = db.Historical(key)
    sym = ["MGC.v.0"]           # continuous front-month micro gold
    # GLBX embargoes the most recent 1-2 days; asking past the dataset's available end
    # returns HTTP 422 (data_end_after_available_end) - which then fell through to a
    # spot-proxy CSV that is gitignored/absent in CI and crashed the run. Clamp `end`
    # to what is actually available so the real-MGC path just works.
    try:
        rng = client.metadata.get_dataset_range(dataset="GLBX.MDP3")
        avail_end = rng.get("end") or rng.get("available_end") or rng.get("end_date")
        if avail_end is not None:
            avail_end = str(pd.to_datetime(avail_end).date())
            if end > avail_end:
                end = avail_end
    except Exception:
        pass
    kw = dict(dataset="GLBX.MDP3", symbols=sym, stype_in="continuous",
              schema="ohlcv-1d", start=start, end=end)
    cost = float(client.metadata.get_cost(**kw))
    if cost > max_cost_usd:
        raise RuntimeError(f"Databento cost ${cost:.2f} > cap ${max_cost_usd:.2f}; raise the cap to proceed.")
    df = client.timeseries.get_range(**kw).to_df().reset_index()
    ts = "ts_event" if "ts_event" in df.columns else df.columns[0]
    df["date"] = pd.to_datetime(df[ts], utc=True).dt.date
    out = df.set_index("date")[["open", "high", "low", "close"]].astype(float).sort_index()
    out.index = pd.to_datetime(out.index)
    return out


def load_prices(prefer_mgc=True, **kw):
    """Prefer real MGC bars; fall back to the free spot proxy if Databento is unavailable
    (no key / offline). Returns (ohlc, source_label) so the report can state which it used."""
    if prefer_mgc:
        try:
            return load_mgc_databento(**kw), "MGC (Databento GLBX.MDP3)"
        except Exception as e:
            print(f"[mgc_prop] real MGC unavailable ({e}); trying spot proxy.", flush=True)
    try:
        return load_ohlc(), "XAU_USD spot proxy"
    except Exception as e:
        # The spot-proxy CSV (data/daily/XAU_USD_D.csv) is gitignored and absent in a
        # fresh CI checkout. If BOTH sources are unavailable, signal 'no data' so the
        # caller can skip cleanly instead of crashing the whole job.
        raise RuntimeError(f"no price data available (MGC failed and spot-proxy CSV missing: {e})")
