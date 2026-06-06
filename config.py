"""
config.py
---------
Single source of truth for configuration. Reads from environment / .env.
No secrets are hardcoded here. `.env` is gitignored.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Best-effort .env loader (no hard dependency on python-dotenv).
def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.split("#", 1)[0].strip()
        os.environ.setdefault(key, val)


_load_dotenv(ROOT / ".env")


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


def _i(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)


@dataclass
class Settings:
    # OANDA
    oanda_api_key: str = os.getenv("OANDA_API_KEY", "")
    oanda_account_id: str = os.getenv("OANDA_ACCOUNT_ID", "")
    oanda_env: str = os.getenv("OANDA_ENV", "practice")

    # Instrument / data
    instrument: str = os.getenv("INSTRUMENT", "XAU_USD")
    entry_tf: str = os.getenv("ENTRY_TF", "M15")
    htf_tf: str = os.getenv("HTF_TF", "H4")
    history_days: int = _i("HISTORY_DAYS", 730)

    # Strategy / risk
    confidence_threshold: float = _f("CONFIDENCE_THRESHOLD", 60)
    risk_per_trade_pct: float = _f("RISK_PER_TRADE_PCT", 1.0)
    max_trades_per_day: int = _i("MAX_TRADES_PER_DAY", 3)
    max_position_usd: float = _f("MAX_POSITION_USD", 1000)

    # Backtest cost model
    spread_usd: float = _f("SPREAD_USD", 0.30)
    slippage_usd: float = _f("SLIPPAGE_USD", 0.10)
    commission_per_trade: float = _f("COMMISSION_PER_TRADE", 0.0)

    # Account
    starting_equity: float = _f("STARTING_EQUITY", 100_000.0)

    @property
    def oanda_base_url(self) -> str:
        return ("https://api-fxpractice.oanda.com"
                if self.oanda_env == "practice"
                else "https://api-fxtrade.oanda.com")


SETTINGS = Settings()
