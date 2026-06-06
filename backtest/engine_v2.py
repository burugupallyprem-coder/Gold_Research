"""
backtest/engine_v2.py
---------------------
Event-driven engine with PARTIAL PROFIT-TAKING + TRAILING, plus the regime and
event gates (via strategy.signals_v2). Same honesty rules as the base engine
(no look-ahead, costs on every fill, pessimistic intrabar, flat-only, daily cap).

Trade lifecycle (long; short mirrors):
  * Fill full size Q at next bar's open. risk R = entry - stop.
  * PHASE 1 (before partial): if stop hit -> full-size loss. If +1R reached ->
    book `partial_frac` of Q at +1R, move stop to entry (break-even) for the
    runner. (Partial books at most once per bar; runner handled next bar.)
  * PHASE 2 (runner): exit at the original target, or at the trailing stop
    (ratchets up by trail_atr_mult * ATR), whichever comes first; stop checked
    before target (pessimistic).
  * pnl = partial leg + runner leg - commission; r_multiple = pnl / (R * Q).

run_backtest_v2(df, htf, strat_cfg, risk_cfg, bt_cfg, regime_cfg, cost)
"""

from __future__ import annotations

import pandas as pd

from backtest.core import CostModel, Trade, BacktestConfig, BacktestResult, _et_day
from strategy.strategy import StrategyConfig
from strategy.risk import RiskConfig
from strategy.confidence import MacroBias, score_intent
from strategy.signals_v2 import RegimeConfig, precompute_v2, decide_at_v2


def run_backtest_v2(df, htf, strat_cfg=None, risk_cfg=None, bt_cfg=None,
                    regime_cfg=None, cost=None):
    strat_cfg = strat_cfg or StrategyConfig()
    risk_cfg = risk_cfg or RiskConfig()
    bt_cfg = bt_cfg or BacktestConfig()
    regime_cfg = regime_cfg or RegimeConfig()
    cost = cost or CostModel()

    if df.index.tz is None:
        df = df.tz_localize("UTC")
    if htf is not None and htf.index.tz is None:
        htf = htf.tz_localize("UTC")

    feat = precompute_v2(df, htf, strat_cfg)
    atr_col = feat["atr"].values

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

        # 1) Fill pending entry
        if pending is not None and open_trade is None:
            side = pending.side
            fill = cost.entry_fill(side, float(bar["open"]))
            risk = abs(fill - pending.stop_price)
            open_trade = {
                "t": Trade(entry_time=ts, exit_time=None, side=side, qty=pending.qty,
                           entry=fill, stop=pending.stop_price, target=pending.target_price,
                           reason=pending.reason, confidence=pending.confidence or 0.0,
                           r_planned=risk),
                "full_qty": pending.qty, "rem_qty": pending.qty,
                "risk": risk, "partial_done": False, "partial_pnl": 0.0,
                "stop": pending.stop_price, "target": pending.target_price,
            }
            trades_today += 1
            pending = None

        # 2) Manage open trade
        if open_trade is not None:
            o = open_trade
            t = o["t"]
            hi, lo = float(bar["high"]), float(bar["low"])
            risk = o["risk"]
            atr_i = atr_col[i]
            side = t.side
            entry = t.entry
            closed = False

            if not o["partial_done"]:
                partial_level = (entry + regime_cfg.partial_at_r * risk if side == "buy"
                                 else entry - regime_cfg.partial_at_r * risk)
                stop_hit = (lo <= o["stop"]) if side == "buy" else (hi >= o["stop"])
                if stop_hit:
                    px = cost.exit_fill(side, o["stop"])
                    pnl = ((px - entry) if side == "buy" else (entry - px)) * o["full_qty"]
                    _close(t, ts, px, "stop", pnl - cost.commission_per_trade, risk, o["full_qty"])
                    equity += t.pnl; trades.append(t); open_trade = None; closed = True
                else:
                    reach = (hi >= partial_level) if side == "buy" else (lo <= partial_level)
                    if reach:
                        px = cost.exit_fill(side, partial_level)
                        qty_p = o["full_qty"] * regime_cfg.partial_frac
                        o["partial_pnl"] = ((px - entry) if side == "buy" else (entry - px)) * qty_p
                        o["rem_qty"] = o["full_qty"] - qty_p
                        o["stop"] = entry          # break-even for the runner
                        o["partial_done"] = True
                        t.be_moved = True
            else:
                # PHASE 2 runner: stop (trailing) checked before target
                stop_hit = (lo <= o["stop"]) if side == "buy" else (hi >= o["stop"])
                tgt_hit = (hi >= o["target"]) if side == "buy" else (lo <= o["target"])
                if stop_hit:
                    px = cost.exit_fill(side, o["stop"])
                    rem_pnl = ((px - entry) if side == "buy" else (entry - px)) * o["rem_qty"]
                    total = o["partial_pnl"] + rem_pnl - cost.commission_per_trade
                    reason = "be_stop" if (o["stop"] == entry) else "trail_stop"
                    _close(t, ts, px, reason, total, risk, o["full_qty"])
                    equity += t.pnl; trades.append(t); open_trade = None; closed = True
                elif tgt_hit:
                    px = cost.exit_fill(side, o["target"])
                    rem_pnl = ((px - entry) if side == "buy" else (entry - px)) * o["rem_qty"]
                    total = o["partial_pnl"] + rem_pnl - cost.commission_per_trade
                    _close(t, ts, px, "target", total, risk, o["full_qty"])
                    equity += t.pnl; trades.append(t); open_trade = None; closed = True
                elif not pd.isna(atr_i) and atr_i > 0:
                    trail = regime_cfg.trail_atr_mult * float(atr_i)
                    if side == "buy":
                        o["stop"] = max(o["stop"], hi - trail)
                    else:
                        o["stop"] = min(o["stop"], lo + trail)

        # 3) New signal when flat
        if open_trade is None and pending is None and i + 1 < n:
            intents = decide_at_v2(feat, i, equity, trades_today, strat_cfg,
                                   risk_cfg, regime_cfg)
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
        "engine": "engine_v2", "partial_frac": regime_cfg.partial_frac,
        "partial_at_r": regime_cfg.partial_at_r, "trail_atr_mult": regime_cfg.trail_atr_mult,
        "require_regime": regime_cfg.require_regime, "adx_min": regime_cfg.adx_min,
        "stand_down_events": regime_cfg.stand_down_events,
        "confidence_threshold": bt_cfg.confidence_threshold,
        "spread_usd": cost.spread_usd, "slippage_usd": cost.slippage_usd,
        "displacement_atr_mult": strat_cfg.displacement_atr_mult,
        "rr_target": risk_cfg.rr_target,
        "enabled_setups": {
            "ny_opening": strat_cfg.enable_ny_opening,
            "displacement": strat_cfg.use_displacement,
            "fvg": strat_cfg.use_fvg,
            "london_am": strat_cfg.enable_london_am,
            "london_pm": strat_cfg.enable_london_pm,
        },
    }
    return BacktestResult(trades=trades, equity_curve=equity_curve, config=cfg)


def _close(t: Trade, ts, px, reason, pnl, risk, full_qty):
    t.exit_time = ts
    t.exit_price = px
    t.exit_reason = reason
    t.pnl = pnl
    t.r_multiple = (pnl / (risk * full_qty)) if (risk > 0 and full_qty > 0) else 0.0
