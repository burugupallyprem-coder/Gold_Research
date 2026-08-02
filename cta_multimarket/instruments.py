"""Diversified futures basket for the multi-market trend portfolio.
All trade on CME Globex (Databento GLBX.MDP3). Continuous front month = '<root>.v.0'.
Chosen for liquidity + sector diversification so the trend premium is not one bet."""

BASKET = [
    # (root, sector, description)
    ("GC", "metals",  "Gold"),
    ("SI", "metals",  "Silver"),
    ("HG", "metals",  "Copper"),
    ("CL", "energy",  "WTI Crude"),
    ("NG", "energy",  "Natural Gas"),
    ("ES", "equity",  "S&P 500"),
    ("NQ", "equity",  "Nasdaq 100"),
    ("ZN", "rates",   "10Y Note"),
    ("ZB", "rates",   "30Y Bond"),
    ("6E", "fx",      "Euro"),
    ("6J", "fx",      "Yen"),
    ("ZC", "ags",     "Corn"),
    ("ZS", "ags",     "Soybeans"),
    ("BTC","crypto",  "Bitcoin"),
]
ROOTS = [b[0] for b in BASKET]
SECTOR = {b[0]: b[1] for b in BASKET}
NAME = {b[0]: b[2] for b in BASKET}
