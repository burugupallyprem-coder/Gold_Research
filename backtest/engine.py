"""
backtest/engine.py
------------------
Compatibility shim. The implementation lives in backtest/core.py.
Import from either path:  `from backtest.core import run_backtest`.
"""

from backtest.core import (  # noqa: F401
    CostModel, Trade, BacktestConfig, BacktestResult, run_backtest, _et_day,
)
