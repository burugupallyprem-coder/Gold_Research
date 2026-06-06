"""
backtest/core.py
----------------
Event-driven, bar-by-bar backtester. Honest by construction:

  * NO LOOK-AHEAD. The signal on bar i uses bars [.. i] (closed data only).
    The fill happens at bar i+1's OPEN, never on the signal bar.
  * REALISTIC COSTS. Half-spread + adverse slippage on every entry and exit,
    plus optional flat commission per trade.
  * PESSIMISTIC INTRABAR FILLS. If one bar touches BOTH stop and target, the
    STOP fills first.
  * BREAK-EVEN MOVE at +1.5R, effective on SUBSEQUENT bars only.
  * DAILY TRADE CAP + flat-only entries, matching the live bot.

Reuses strategy.evaluate() verbatim so backtest and live share one signal impl.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from zoneinfo import ZoneInfo

import pandas as pd

from strategy.strategy import StrategyConfig, evaluate
from strategy.risk import RiskConfig
from strategy.confidence import MacroBias, score_intent

ET = ZoneInfo("America/New_York")


@dataclass
class CostModel:
    spread_usd: float = 0.30        # full spread; half applied per side
    slippage_usd: float = 0.10      # adverse, per fill
    commission_per_trade: float = 0.0

    def entry_fill(self, side: str, ref_price: float) -> float:
        adj = self.spread_usd / 2 + self.slippage_usd
        return ref_price + adj if side == "buy" else ref_price - adj

    def exit_fill(self, side: str, ref_price: float) -> float:
        adj = self.spread_usd / 2 + self.slippage_usd
        return ref_price - adj if side == "buy" else ref_price + adj


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp | None
    side: str
    qty: float
    entry: float
    stop: float
    target: float
    exit_price: float | None = None
    exit_reason: str = ""
    reason: str = ""
    confidence: float = 0.0
    r_planned: float = 0.0
    r_multiple: float = 0.0
    pnl: float = 0.0
    be_moved: bool = False


@dataclass
class BacktestConfig:
    lookback: int = 300
    htf_lookback: int = 180
    starting_equity: float = 100_000.0
    confidence_threshold: float = 60.0
    be_trigger_r: float = 1.5
    use_confidence_gate: bool = True
    use_macro: bool = False


@dataclass
class BacktestResult:
    trades: list = field(default_factory=list)
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)
    config: dict = field(default_factory=dict)


def _et_day(ts: pd.Timestamp) -> date:
    return ts.tz_convert(ET).date()


def run_backtest(df, htf, strat_cfg=None, risk_cfg=None, bt_cfg=None, cost=None):
    strat_cfg = strat_cfg or StrategyConfig()
    risk_cfg = risk_cfg or RiskConfig()
    bt_cfg = bt_cfg or BacktestConfig()
    cost = cost or CostModel()

    if df.index.tz is None:
        df = df.tz_localize("UTC")
    if htf is not None and htf.index.tz is None:
        htf = htf.tz_localize("UTC")

    equity = bt_cfg.starting_equity
    trades = []
    open_trade = None
    pending = None
    trades_today = 0
    cur_day = None

    eq_times, eq_vals = [], []
    n = len(df)
    htf_times = htf.index if htf is not None else None

    for i in range(n):
        bar = df.iloc[i]
        ts = df.index[i]
        d = _et_day(ts)
        if d != cur_day:
            cur_day = d
            trades_today = 0

        # 1) Fill a pending entry at THIS bar's open
        if pending is not None and open_trade is None:
            side = pending.side
            fill = cost.entry_fill(side, float(bar["open"]))
            open_trade = Trade(
                entry_time=ts, exit_time=None, side=side, qty=pending.qty,
                entry=fill, stop=pending.stop_price, target=pending.target_price,
                reason=pending.reason, confidence=pending.confidence or 0.0,
                r_planned=abs(fill - pending.stop_price),
            )
            trades_today += 1
            pending = None

        # 2) Manage open trade against THIS bar
        if open_trade is not None:
            t = open_trade
            hi, lo = float(bar["high"]), float(bar["low"])
            risk = t.r_planned if t.r_planned > 0 else abs(t.entry - t.stop)

            exit_price = exit_reason = None
            if t.side == "buy":
                if lo <= t.stop:
                    exit_price = cost.exit_fill("buy", t.stop)
                    exit_reason = "be_stop" if t.be_moved and t.stop >= t.entry else "stop"
                elif hi >= t.target:
                    exit_price = cost.exit_fill("buy", t.target)
                    exit_reason = "target"
            else:
                if hi >= t.stop:
                    exit_price = cost.exit_fill("sell", t.stop)
                    exit_reason = "be_stop" if t.be_moved and t.stop <= t.entry else "stop"
                elif lo <= t.target:
                    exit_price = cost.exit_fill("sell", t.target)
                    exit_reason = "target"

            if exit_price is None and not t.be_moved and risk > 0:
                if t.side == "buy" and hi >= t.entry + bt_cfg.be_trigger_r * risk:
                    t.stop = max(t.stop, t.entry)
                    t.be_moved = True
                elif t.side == "sell" and lo <= t.entry - bt_cfg.be_trigger_r * risk:
                    t.stop = min(t.stop, t.entry)
                    t.be_moved = True

            if exit_price is not None:
                gross = ((exit_price - t.entry) if t.side == "buy"
                         else (t.entry - exit_price)) * t.qty
                t.exit_price = exit_price
                t.exit_time = ts
                t.exit_reason = exit_reason
                t.pnl = gross - cost.commission_per_trade
                t.r_multiple = (t.pnl / (risk * t.qty)) if risk > 0 and t.qty > 0 else 0.0
                equity += t.pnl
                trades.append(t)
                open_trade = None

        # 3) New signal when flat (fills next bar)
        if open_trade is None and pending is None and i + 1 < n:
            lo_i = max(0, i - bt_cfg.lookback + 1)
            window = df.iloc[lo_i:i + 1]
            htf_window = None
            if htf is not None:
                hmask = htf_times <= ts
                if hmask.any():
                    htf_window = htf[hmask].iloc[-bt_cfg.htf_lookback:]
            intents = evaluate(window, htf_window, equity, trades_today,
                               strat_cfg, risk_cfg)
            if intents:
                intent = intents[0]
                bias = MacroBias() if not bt_cfg.use_macro else None
                conf = score_intent(intent, bias)
                intent.confidence = conf.score
                if (not bt_cfg.use_confidence_gate) or conf.passes(bt_cfg.confidence_threshold):
                    pending = intent

        eq_times.append(ts)
        eq_vals.append(equity)

    equity_curve = pd.DataFrame({"equity": eq_vals}, index=pd.DatetimeIndex(eq_times))
    cfg = {
        "lookback": bt_cfg.lookback,
        "starting_equity": bt_cfg.starting_equity,
        "confidence_threshold": bt_cfg.confidence_threshold,
        "spread_usd": cost.spread_usd,
        "slippage_usd": cost.slippage_usd,
        "commission_per_trade": cost.commission_per_trade,
        "displacement_atr_mult": strat_cfg.displacement_atr_mult,
        "rr_target": risk_cfg.rr_target,
        "ny_opening_rr": risk_cfg.ny_opening_rr,
    }
    return BacktestResult(trades=trades, equity_curve=equity_curve, config=cfg)
