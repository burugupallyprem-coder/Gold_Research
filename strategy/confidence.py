"""
strategy/confidence.py
----------------------
0-100 confidence gate. Faithful port of intelligence/confidence.py.

Factor weights (max 100):
  Entry trigger fired ......... +30
  HTF trend aligned ........... +20
  Volume confirmed ............ +15
  NY Opening setup ............ +10
  Macro bias alignment ........ +/-25

In the backtest, macro defaults to NEUTRAL (0) unless a macro series is
supplied. The mentor's review flagged the slow daily macro signal as more
noise than alpha intraday, so neutral-by-default keeps the backtest honest
and isolates the price-action edge. Macro can be switched on later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class MacroBias:
    direction: Literal["bullish", "bearish", "neutral"] = "neutral"
    score: float = 0.0


@dataclass
class Confidence:
    score: float
    factors: list = field(default_factory=list)

    def passes(self, threshold: float) -> bool:
        return self.score >= threshold


def _macro_aligns(side: str, bias: MacroBias):
    if bias.direction == "neutral":
        return (0.0, f"Macro neutral (score {bias.score:+.2f}) - no contribution")
    aligned = (side == "buy" and bias.direction == "bullish") or \
              (side == "sell" and bias.direction == "bearish")
    if aligned:
        return (25.0, f"Macro {bias.direction} aligns with {side.upper()}")
    return (-25.0, f"Macro {bias.direction} OPPOSES {side.upper()}")


def score_intent(intent, bias: MacroBias | None = None) -> Confidence:
    bias = bias or MacroBias()
    factors: list = []
    score = 0.0

    score += 30
    factors.append(f"Entry trigger fired: {intent.reason}")

    score += 20
    factors.append("HTF trend aligned")

    score += 15
    factors.append("Volume above 20-bar MA x multiplier")

    if intent.is_ny_opening:
        score += 10
        factors.append("NY Opening 2-candle play")

    macro_pts, macro_txt = _macro_aligns(intent.side, bias)
    score += macro_pts
    factors.append(macro_txt)

    score = max(0.0, min(100.0, score))
    return Confidence(score=score, factors=factors)
