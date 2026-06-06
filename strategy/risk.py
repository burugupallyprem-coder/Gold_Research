"""
strategy/risk.py
----------------
Position sizing, stop placement, and target logic.

Faithful port of the Alpaca repo's execution/risk_manager.py, with two
backtest-friendly changes:
  * The per-day trade counter is NOT file-based here. The backtest engine
    tracks trades-per-day in memory and passes the count in, so the same
    logic works deterministically across a replay.
  * `whole_units` is configurable. GLD needed whole shares; OANDA XAU/USD
    supports fractional units, so the backtest can size precisely.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class RiskConfig:
    atr_sl_mult: float = 1.5
    rr_target: float = 2.5
    ny_opening_rr: float = 3.0
    risk_per_trade_pct: float = 1.0
    max_trades_per_day: int = 3
    use_swing_stops: bool = True
    swing_min_atr: float = 0.5
    swing_max_atr: float = 4.0
    max_position_usd: float = 1000.0
    whole_units: bool = False          # XAU/USD allows fractional units

    @classmethod
    def from_settings(cls, s) -> "RiskConfig":
        return cls(
            risk_per_trade_pct=s.risk_per_trade_pct,
            max_trades_per_day=s.max_trades_per_day,
            max_position_usd=s.max_position_usd,
        )


def can_trade_today(cfg: RiskConfig, trades_today: int) -> bool:
    return trades_today < cfg.max_trades_per_day


def long_stop_price(entry: float, atr: float, last_swing_low: Optional[float],
                    cfg: RiskConfig) -> float:
    atr_stop = entry - atr * cfg.atr_sl_mult
    if not cfg.use_swing_stops or last_swing_low is None:
        return atr_stop
    dist = entry - last_swing_low
    if dist < atr * cfg.swing_min_atr or dist > atr * cfg.swing_max_atr:
        return atr_stop
    return last_swing_low - atr * 0.1


def short_stop_price(entry: float, atr: float, last_swing_high: Optional[float],
                     cfg: RiskConfig) -> float:
    atr_stop = entry + atr * cfg.atr_sl_mult
    if not cfg.use_swing_stops or last_swing_high is None:
        return atr_stop
    dist = last_swing_high - entry
    if dist < atr * cfg.swing_min_atr or dist > atr * cfg.swing_max_atr:
        return atr_stop
    return last_swing_high + atr * 0.1


def target_price(entry: float, stop: float, rr: float, side: str) -> float:
    risk = abs(entry - stop)
    return entry + risk * rr if side == "buy" else entry - risk * rr


def position_size(equity: float, entry: float, stop: float, cfg: RiskConfig) -> float:
    """Risk-based size in units. Honors both % risk and the max-USD cap."""
    risk_dollars = equity * (cfg.risk_per_trade_pct / 100.0)
    stop_dist = abs(entry - stop)
    if stop_dist <= 0:
        return 0.0
    raw_qty = risk_dollars / stop_dist
    if cfg.max_position_usd > 0:
        max_qty_by_usd = cfg.max_position_usd / entry
        raw_qty = min(raw_qty, max_qty_by_usd)
    if cfg.whole_units:
        return float(max(int(raw_qty), 0))
    return max(round(raw_qty, 4), 0.0)
