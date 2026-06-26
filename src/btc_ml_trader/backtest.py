from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestStats:
    total_return_pct: float
    annualized_sharpe: float
    max_drawdown_pct: float
    exposure_pct: float
    turnover: float
    trade_count: int
    win_rate_pct: float
    profit_factor: float


def run_vector_backtest(
    signals: pd.DataFrame,
    fee_bps: float,
    slippage_bps: float,
    bars_per_year: int,
    max_leverage: float = 1.0,
) -> tuple[pd.DataFrame, BacktestStats]:
    required = {"timestamp", "close", "target_position"}
    missing = required.difference(signals.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    out = signals.sort_values("timestamp").copy()
    out["raw_log_return"] = np.log(out["close"]).diff().fillna(0.0)
    out["position"] = out["target_position"].clip(-1, 1) * max_leverage

    # Position decided at bar t participates in bar t+1 return.
    out["active_position"] = out["position"].shift(1).fillna(0.0)
    out["turnover"] = out["position"].diff().abs().fillna(out["position"].abs())
    cost_per_turnover = (fee_bps + slippage_bps) / 10_000
    out["cost"] = out["turnover"] * cost_per_turnover
    out["strategy_log_return"] = out["active_position"] * out["raw_log_return"] - out["cost"]
    out["equity"] = np.exp(out["strategy_log_return"].cumsum())
    out["drawdown"] = out["equity"] / out["equity"].cummax() - 1.0

    stats = _stats(out, bars_per_year)
    return out, stats


def _stats(out: pd.DataFrame, bars_per_year: int) -> BacktestStats:
    returns = out["strategy_log_return"]
    total_return_pct = (out["equity"].iloc[-1] - 1.0) * 100
    return_std = returns.std()
    annualized_sharpe = 0.0 if return_std == 0 else (returns.mean() / return_std) * np.sqrt(bars_per_year)
    max_drawdown_pct = out["drawdown"].min() * 100
    exposure_pct = (out["active_position"].abs() > 0).mean() * 100
    turnover = out["turnover"].sum()
    trade_count = int((out["turnover"] > 0).sum())
    trade_returns = returns[out["active_position"].abs() > 0]
    win_rate_pct = 0.0 if trade_returns.empty else (trade_returns > 0).mean() * 100
    gains = trade_returns[trade_returns > 0].sum()
    losses = trade_returns[trade_returns < 0].sum()
    profit_factor = float("inf") if losses == 0 and gains > 0 else (gains / abs(losses) if losses != 0 else 0.0)

    return BacktestStats(
        total_return_pct=float(total_return_pct),
        annualized_sharpe=float(annualized_sharpe),
        max_drawdown_pct=float(max_drawdown_pct),
        exposure_pct=float(exposure_pct),
        turnover=float(turnover),
        trade_count=trade_count,
        win_rate_pct=float(win_rate_pct),
        profit_factor=float(profit_factor),
    )

