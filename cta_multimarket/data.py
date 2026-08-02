"""Daily bars for the diversified basket from Databento GLBX.MDP3. Needs DATABENTO_API_KEY.
Daily schema is cheap; a cost pre-flight still guards spend. Runs in CI."""

import os
from datetime import datetime, timezone, timedelta

import pandas as pd

from .instruments import ROOTS


def load_markets(start="2010-06-08", end=None, roots=None, max_cost_usd=15.0):
    """Returns {root: close Series indexed by date} for the basket."""
    import databento as db
    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        raise RuntimeError("DATABENTO_API_KEY not set - run in CI.")
    roots = roots or ROOTS
    if not end:
        end = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    client = db.Historical(key)
    syms = [f"{r}.v.0" for r in roots]
    kw = dict(dataset="GLBX.MDP3", symbols=syms, stype_in="continuous",
              schema="ohlcv-1d", start=start, end=end)
    cost = float(client.metadata.get_cost(**kw))
    if cost > max_cost_usd:
        raise RuntimeError(f"Databento cost ${cost:.2f} > cap ${max_cost_usd:.2f}; raise the cap.")
    print(f"[cta] Databento cost ${cost:.2f} for {len(syms)} markets {start}->{end}", flush=True)
    df = client.timeseries.get_range(**kw).to_df().reset_index()
    ts = "ts_event" if "ts_event" in df.columns else df.columns[0]
    df["date"] = pd.to_datetime(df[ts], utc=True).dt.tz_localize(None).dt.normalize()
    root_of = {f"{r}.v.0": r for r in roots}
    df["root"] = df["symbol"].map(lambda x: root_of.get(x, str(x).split(".")[0]))
    out = {}
    for r, g in df.groupby("root"):
        s = g.set_index("date")["close"].astype(float).sort_index()
        s = s[~s.index.duplicated(keep="last")]
        if len(s) > 300:
            out[r] = s
    return out


def load_markets_ohlc(start="2018-01-01", end=None, roots=None, max_cost_usd=15.0):
    """Like load_markets but returns {root: DataFrame[open,high,low,close]} (needs H/L
    for ATR + intraday drawdown). Crypto (BTC) starts ~2018, hence the default start."""
    import databento as db
    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        raise RuntimeError("DATABENTO_API_KEY not set - run in CI.")
    from datetime import datetime, timezone, timedelta
    roots = roots or ROOTS
    if not end:
        end = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    client = db.Historical(key)
    syms = [f"{r}.v.0" for r in roots]
    kw = dict(dataset="GLBX.MDP3", symbols=syms, stype_in="continuous",
              schema="ohlcv-1d", start=start, end=end)
    cost = float(client.metadata.get_cost(**kw))
    if cost > max_cost_usd:
        raise RuntimeError(f"Databento cost ${cost:.2f} > cap ${max_cost_usd:.2f}.")
    print(f"[cta] OHLC cost ${cost:.2f} for {len(syms)} markets {start}->{end}", flush=True)
    df = client.timeseries.get_range(**kw).to_df().reset_index()
    ts = "ts_event" if "ts_event" in df.columns else df.columns[0]
    df["date"] = pd.to_datetime(df[ts], utc=True).dt.tz_localize(None).dt.normalize()
    root_of = {f"{r}.v.0": r for r in roots}
    df["root"] = df["symbol"].map(lambda x: root_of.get(x, str(x).split(".")[0]))
    out = {}
    for r, g in df.groupby("root"):
        d = g.set_index("date")[["open", "high", "low", "close"]].astype(float).sort_index()
        d = d[~d.index.duplicated(keep="last")]
        if len(d) > 300:
            out[r] = d
    return out
