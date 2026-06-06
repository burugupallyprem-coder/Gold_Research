"""
backtest/fastcore.py
--------------------
Same verified entry/exit/BE/cost mechanics as backtest.core, but the signal
source is strategy.features (precomputed once) instead of strategy.evaluate
(re-derived every bar). This is what makes a multi-year M15 run fast.

tests/test_parity.py proves decide_at() == evaluate() so this is a pure
speedup, not a behavior change.
"""

from __future__ import annotations

import pandas as pd

from backtest.core import CostModel, Trade, BacktestConfig, BacktestResult, _et_day
from strategy.strategy import StrategyConfig
from strategy.risk import RiskConfig
from strategy.confidence import MacroBias, score_intent
from strategy.features import precompute, decide_at


def run_backtest_fast(df, htf, strat_cfg=None, risk_cfg=None, bt_cfg=None, cost=None):
    strat_cfg = strat_cfg or StrategyConfig()
    risk_cfg = risk_cfg or RiskConfig()
    bt_cfg = bt_cfg or BacktestConfig()
    cost = cost or CostModel()

    if df.index.tz is None:
        df = df.tz_localize("UTC")
    if htf is not None and htf.index.tz is None:
        htf = htf.tz_localize("UTC")

    feat = precompute(df, htf, strat_cfg)

    equity = bt_cfg.starting_equity
    trades, open_trade, pending = [], None, None
    trades_today, cur_day = 0, None
    eq_times, eq_vals = [], []
    n = len(df)

    for i in range(n):
        bar = df.iloc[i]
        ts = df.index[i]
        d = _et_day(ts)
        if d != cur_day:
            cur_day = d
            trades_today = 0

        if pending is not None and open_trade is None:
            side = pending.side
            fill = cost.entry_fill(side, float(bar["open"]))
            open_trade = Trade(
                entry_time=ts, exit_time=None, side=side, qty=pending.qty,
                entry=fill, stop=pending.stop_price, target=pending.target_price,
                reason=pending.reason, confidence=pending.confidence or 0.0,
                r_planned=abs(fill - pending.stop_price))
            trades_today += 1
            pending = None

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
                    t.stop = max(t.stop, t.entry); t.be_moved = True
                elif t.side == "sell" and lo <= t.entry - bt_cfg.be_trigger_r * risk:
                    t.stop = min(t.stop, t.entry); t.be_moved = True

            if exit_price is not None:
                gross = ((exit_price - t.entry) if t.side == "buy"
                         else (t.entry - exit_price)) * t.qty
                t.exit_price = exit_price; t.exit_time = ts; t.exit_reason = exit_reason
                t.pnl = gross - cost.commission_per_trade
                t.r_multiple = (t.pnl / (risk * t.qty)) if risk > 0 and t.qty > 0 else 0.0
                equity += t.pnl
                trades.append(t)
                open_trade = None

        if open_trade is None and pending is None and i + 1 < n:
            intents = decide_at(feat, i, equity, trades_today, strat_cfg, risk_cfg)
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
        "engine": "fastcore", "lookback": "full-precompute",
        "starting_equity": bt_cfg.starting_equity,
        "confidence_threshold": bt_cfg.confidence_threshold,
        "spread_usd": cost.spread_usd, "slippage_usd": cost.slippage_usd,
        "commission_per_trade": cost.commission_per_trade,
        "displacement_atr_mult": strat_cfg.displacement_atr_mult,
        "rr_target": risk_cfg.rr_target, "ny_opening_rr": risk_cfg.ny_opening_rr,
    }
    return BacktestResult(trades=trades, equity_curve=equity_curve, config=cfg)
