from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import search_monthly_profit_lock_20260627 as lock_search
import search_online_expert_pool_20260627 as source_pool
import search_strategy_1_candidate_20260627 as strategy_1a
import search_strategy_1c_trend_runner_20260627 as strategy_1c
import search_strategy_1f_selective_runner_20260627 as strategy_1f


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_2_damage_stop_20260627"
STRATEGY_ID = "strategy_2_damage_stop_20260627"

DAMAGE_ARM_LOG = -0.06
DAMAGE_MAX_SHOCKS = 2
DAMAGE_LEVERAGE = 0.10


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = source_pool._load_features(source_pool.FEATURE_FRAME)
    features = source_pool._add_features(source)
    market = source_pool._market(features)
    base_side = strategy_1f._base_side(features)
    trend_side = strategy_1f._trend_side(features)
    runner_side = strategy_1f._runner_side(features)
    weak_trend = strategy_1f._weak_trend_mask(features)
    selections = pd.read_csv(ROOT / "artifacts" / "strategy_1b_expanded_controls_20260627" / "strategy_1b_selections.csv")

    equity = _simulate(base_side, trend_side, runner_side, weak_trend, market, selections, lock_search.COST_PER_SIDE)
    strategy_1a._assert_signal_timing(equity)
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)
    row = strategy_1c._result_row(equity, monthly, yearly)
    diagnostics = _diagnostics(equity)
    signals = strategy_1a._signals(equity)
    signals["candidate_version"] = STRATEGY_ID

    stress = pd.DataFrame(
        [
            _stress_row(base_side, trend_side, runner_side, weak_trend, market, selections, cost, delay)
            for cost in [0.001, 0.0015, 0.002]
            for delay in [0, 1, 2]
        ]
    )

    signals.to_csv(OUT_DIR / "strategy_2_signals.csv", index=False)
    equity.to_csv(OUT_DIR / "strategy_2_equity.csv", index=False)
    monthly.to_csv(OUT_DIR / "strategy_2_monthly.csv", index=False)
    yearly.to_csv(OUT_DIR / "strategy_2_yearly.csv", index=False)
    stress.to_csv(OUT_DIR / "strategy_2_stress.csv", index=False)

    summary = {
        "status": "strategy_2_damage_stop_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "base": "strategy_1f_selective_runner_20260627",
        "strict_no_future_function": True,
        "change": "Add a month-level damage stop to Strategy 1F: after heavy monthly damage or repeated adverse shocks, shrink to 0.10x until the 10-order quota is complete, then stay flat for the month.",
        "damage_stop": {
            "damage_arm_log": DAMAGE_ARM_LOG,
            "damage_max_shocks": DAMAGE_MAX_SHOCKS,
            "damage_leverage": DAMAGE_LEVERAGE,
            "rule": "uses only current-month realized closed-bar PnL and adverse shocks already observed at bar close",
        },
        "cost_model": {
            "cost_per_side": lock_search.COST_PER_SIDE,
            "round_trip_open_close": lock_search.COST_PER_SIDE * 2,
        },
        "row": lock_search._json_ready(row),
        "diagnostics": lock_search._json_ready(diagnostics),
        "yearly": lock_search._json_ready(yearly.to_dict("records")),
        "monthly": lock_search._json_ready(monthly[["month", "return_pct", "orders", "drawdown_pct"]].to_dict("records")),
        "stress": lock_search._json_ready(stress.to_dict("records")),
        "risk_flags": {
            "fixed_signal_still_from_prior_research": True,
            "uses_strategy_1b_selected_controls": True,
            "damage_stop_is_posthoc_after_2025_02_review": True,
            "not_a_live_guarantee": True,
        },
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "signals": _relpath(OUT_DIR / "strategy_2_signals.csv"),
            "equity": _relpath(OUT_DIR / "strategy_2_equity.csv"),
            "monthly": _relpath(OUT_DIR / "strategy_2_monthly.csv"),
            "yearly": _relpath(OUT_DIR / "strategy_2_yearly.csv"),
            "stress": _relpath(OUT_DIR / "strategy_2_stress.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _simulate(
    base_side: np.ndarray,
    trend_side: np.ndarray,
    runner_side: np.ndarray,
    weak_trend: np.ndarray,
    market: dict[str, Any],
    selections: pd.DataFrame,
    cost_per_side: float,
    extra_delay_bars: int = 0,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    previous_position = 0.0
    previous_side = 0
    shock_cooldown = 0
    timestamp = market["timestamp"].reset_index(drop=True)
    selection_map = {row["eval_month"]: row for _, row in selections.iterrows()}

    for start, end in zip(market["month_starts"], np.r_[market["month_starts"][1:], len(base_side)]):
        month = str(market["month"][start])
        if month not in selection_map:
            continue
        params = selection_map[month]
        month_log = 0.0
        month_orders = 0
        halted = False
        damage_mode = False
        damage_halted = False
        quota_mode = False
        adverse_shocks = 0
        for index in range(start, end):
            signal_index = index - extra_delay_bars
            current_base_side = int(base_side[signal_index]) if signal_index >= 0 else 0
            current_trend_side = int(trend_side[signal_index]) if signal_index >= 0 else 0
            is_weak_trend = bool(weak_trend[signal_index]) if signal_index >= 0 else False
            guard_reason = "main"

            if damage_halted:
                current_side = 0
                current_leverage = 0.0
                guard_reason = "damage_stop_flat"
            elif halted:
                current_side = int(runner_side[signal_index]) if signal_index >= 0 else 0
                current_leverage = strategy_1f.RUNNER_LEVERAGE if current_side else 0.0
                guard_reason = "post_lock_runner" if current_side else "post_lock_flat"
            else:
                current_side = current_base_side
                quota_leverage = _none_if_nan(params["quota_leverage"])
                current_leverage = (
                    min(float(quota_leverage), strategy_1f.LEVERAGE_CAP)
                    if quota_mode
                    and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS
                    and quota_leverage is not None
                    else min(float(params["leverage"]), strategy_1f.LEVERAGE_CAP)
                )
                if damage_mode and current_side:
                    current_leverage = min(current_leverage, DAMAGE_LEVERAGE)
                    guard_reason = "damage_mode_small"

                conflicts_with_strong_trend = bool(
                    current_trend_side and current_base_side and current_base_side == -current_trend_side
                )
                if conflicts_with_strong_trend:
                    if month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS:
                        current_side = current_trend_side
                        current_leverage = min(strategy_1f.CONFLICT_FILLER_LEVERAGE, current_leverage)
                        guard_reason = "strong_conflict_small_trend"
                    else:
                        current_side = 0
                        current_leverage = 0.0
                        guard_reason = "strong_conflict_flat"
                elif is_weak_trend and current_base_side != previous_side and current_side:
                    current_leverage = min(current_leverage, strategy_1f.WEAK_NEW_ORDER_LEVERAGE)
                    guard_reason = "weak_new_order_small"

                if shock_cooldown > 0 and current_side:
                    current_leverage = min(current_leverage, strategy_1f.SHOCK_COOLDOWN_LEVERAGE)
                    guard_reason = "shock_cooldown_small"

            current_position = current_side * current_leverage
            current_turnover = abs(current_position - previous_position)
            current_orders = abs(current_side - previous_side)
            current_lr = previous_position * market["raw_return"][index] - current_turnover * cost_per_side

            adverse_shock = (
                previous_position != 0
                and previous_position * market["raw_return"][index] <= -strategy_1f.ADVERSE_SHOCK_LOSS_LOG
            )
            if adverse_shock:
                adverse_shocks += 1
                if not halted and not damage_halted and current_base_side and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS:
                    current_side = current_base_side
                    current_leverage = min(strategy_1f.SHOCK_COOLDOWN_LEVERAGE, DAMAGE_LEVERAGE if damage_mode else strategy_1f.SHOCK_COOLDOWN_LEVERAGE)
                else:
                    current_side = 0
                    current_leverage = 0.0
                guard_reason = "adverse_shock_cut"
                shock_cooldown = strategy_1f.SHOCK_COOLDOWN_BARS
                current_position = current_side * current_leverage
                current_turnover = abs(current_position - previous_position)
                current_orders = abs(current_side - previous_side)
                current_lr = previous_position * market["raw_return"][index] - current_turnover * cost_per_side
            elif shock_cooldown > 0:
                shock_cooldown -= 1

            records.append(
                {
                    "timestamp": timestamp.iloc[index],
                    "close": market["close"][index],
                    "position": current_position,
                    "active_position": previous_position,
                    "turnover": current_turnover,
                    "order_count": current_orders,
                    "strategy_log_return": current_lr,
                    "base_side": current_base_side,
                    "trend_side": current_trend_side,
                    "weak_trend": is_weak_trend,
                    "guard_reason": guard_reason,
                    "damage_mode": damage_mode,
                    "damage_halted": damage_halted,
                    "adverse_shocks": adverse_shocks,
                }
            )

            month_log += current_lr
            month_orders += current_orders
            previous_position = current_position
            previous_side = current_side

            if not halted and not damage_halted:
                if not damage_mode and (month_log <= DAMAGE_ARM_LOG or adverse_shocks >= DAMAGE_MAX_SHOCKS):
                    damage_mode = True
                if damage_mode and month_orders >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS:
                    damage_halted = True
                quota_arm = _none_if_nan(params["quota_arm_log"])
                quota_leverage = _none_if_nan(params["quota_leverage"])
                if (
                    quota_arm is not None
                    and quota_leverage is not None
                    and not quota_mode
                    and not damage_mode
                    and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS
                    and month_log >= float(quota_arm)
                ):
                    quota_mode = True
                if (
                    not damage_mode
                    and month_orders >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS
                    and month_log >= float(params["lock_log"])
                ):
                    halted = True

    equity = pd.DataFrame(records)
    equity["equity"] = np.exp(equity["strategy_log_return"].cumsum())
    equity["drawdown"] = equity["equity"] / equity["equity"].cummax() - 1.0
    return equity


def _stress_row(
    base_side: np.ndarray,
    trend_side: np.ndarray,
    runner_side: np.ndarray,
    weak_trend: np.ndarray,
    market: dict[str, Any],
    selections: pd.DataFrame,
    cost_per_side: float,
    extra_delay_bars: int,
) -> dict[str, Any]:
    equity = _simulate(base_side, trend_side, runner_side, weak_trend, market, selections, cost_per_side, extra_delay_bars)
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)
    row = strategy_1c._result_row(equity, monthly, yearly)
    return {
        "cost_per_side": cost_per_side,
        "round_trip_cost": cost_per_side * 2,
        "extra_delay_bars": extra_delay_bars,
        **row,
        **_diagnostics(equity),
    }


def _diagnostics(equity: pd.DataFrame) -> dict[str, Any]:
    return {
        **strategy_1f._diagnostics(equity),
        "damage_mode_bars": int(equity["damage_mode"].sum()),
        "damage_halted_bars": int(equity["damage_halted"].sum()),
        "damage_stop_flat_bars": int((equity["guard_reason"] == "damage_stop_flat").sum()),
    }


def _none_if_nan(value: Any) -> Any:
    return None if pd.isna(value) else value


def _render_report(summary: dict[str, Any]) -> str:
    row = summary["row"]
    stress = summary["stress"]
    hard_pass_count = sum(1 for item in stress if item["hard_pass"])
    return "\n".join(
        [
            "# 2号实验：Damage Stop",
            "",
            f"- strategy_id: `{summary['strategy_id']}`",
            "- 这是研究实验，不是固化版。",
            f"- 基础结果 hard_pass: `{row['hard_pass']}`",
            f"- 2025收益: `{row['return_2025_pct']}`",
            f"- 2026收益: `{row['return_2026_pct']}`",
            f"- 最差月份: `{row['min_monthly_return_pct']}`",
            f"- 压力场景通过: `{hard_pass_count}/9`",
            "",
            "## 改动",
            "",
            "- 基于 1F。",
            "- 如果月内净对数收益跌到 -0.06，或月内 adverse_shock_cut 达到 2 次，就进入 damage mode。",
            "- damage mode 只允许 0.10x 小仓；补够 10 次交易后本月停手。",
            "",
            "## 风险",
            "",
            "- 这个规则是看过 2025-02 后加的，有事后优化风险。",
            "- 如果它不能明显改善压力测试，就不应继续包装成候选。",
        ]
    ) + "\n"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
