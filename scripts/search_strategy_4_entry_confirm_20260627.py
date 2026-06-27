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
OUT_DIR = ROOT / "artifacts" / "strategy_4_entry_confirm_20260627"
STRATEGY_ID = "strategy_4_entry_confirm_20260627"

LOCK_LOG_CAP = 0.04
RUNNER_GAP_BPS = 350.0
RUNNER_CONFIRM_BARS = 8
RUNNER_LEVERAGE = 0.10
ENTRY_CONFIRM_BARS = 4


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    old_runner = (strategy_1f.RUNNER_GAP_BPS, strategy_1f.RUNNER_CONFIRM_BARS, strategy_1f.RUNNER_LEVERAGE)
    try:
        strategy_1f.RUNNER_GAP_BPS = RUNNER_GAP_BPS
        strategy_1f.RUNNER_CONFIRM_BARS = RUNNER_CONFIRM_BARS
        strategy_1f.RUNNER_LEVERAGE = RUNNER_LEVERAGE
        summary = _run()
    finally:
        strategy_1f.RUNNER_GAP_BPS, strategy_1f.RUNNER_CONFIRM_BARS, strategy_1f.RUNNER_LEVERAGE = old_runner

    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _run() -> dict[str, Any]:
    source = source_pool._load_features(source_pool.FEATURE_FRAME)
    features = source_pool._add_features(source)
    market = source_pool._market(features)
    base_side = strategy_1f._base_side(features)
    trend_side = strategy_1f._trend_side(features)
    runner_side = strategy_1f._runner_side(features)
    weak_trend = strategy_1f._weak_trend_mask(features)
    base_streak = _side_streak(base_side)
    selections = _selections()

    equity = _simulate(
        base_side,
        trend_side,
        runner_side,
        weak_trend,
        base_streak,
        market,
        selections,
        lock_search.COST_PER_SIDE,
    )
    strategy_1a._assert_signal_timing(equity)
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)
    row = strategy_1c._result_row(equity, monthly, yearly)
    diagnostics = {
        **strategy_1f._diagnostics(equity),
        **_coverage_diagnostics(equity),
        **_entry_quality_diagnostics(equity),
    }
    signals = strategy_1a._signals(equity)
    signals["candidate_version"] = STRATEGY_ID

    stress = pd.DataFrame(
        [
            _stress_row(base_side, trend_side, runner_side, weak_trend, base_streak, market, selections, cost, delay)
            for cost in [0.001, 0.0015, 0.002]
            for delay in [0, 1, 2]
        ]
    )

    selections.to_csv(OUT_DIR / "strategy_4_selections.csv", index=False)
    signals.to_csv(OUT_DIR / "strategy_4_signals.csv", index=False)
    equity.to_csv(OUT_DIR / "strategy_4_equity.csv", index=False)
    monthly.to_csv(OUT_DIR / "strategy_4_monthly.csv", index=False)
    yearly.to_csv(OUT_DIR / "strategy_4_yearly.csv", index=False)
    stress.to_csv(OUT_DIR / "strategy_4_stress.csv", index=False)

    return {
        "status": "strategy_4_entry_confirm_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "base": "strategy_3_trend_coverage_20260627",
        "strict_no_future_function": True,
        "change": (
            "Keep Strategy 3 trend coverage, but require a new main base direction to persist "
            "for 4 closed 15m bars before allowing the main position to enter."
        ),
        "rules": {
            "lock_log_cap": LOCK_LOG_CAP,
            "post_lock_runner_gap_bps": RUNNER_GAP_BPS,
            "post_lock_runner_confirm_bars": RUNNER_CONFIRM_BARS,
            "post_lock_runner_leverage": RUNNER_LEVERAGE,
            "main_entry_confirm_bars": ENTRY_CONFIRM_BARS,
            "main_entry_wait_action": "flat until the new base direction has persisted",
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
            "entry_confirm_change_is_visual_review_driven": True,
            "not_a_live_guarantee": True,
        },
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "selections": _relpath(OUT_DIR / "strategy_4_selections.csv"),
            "signals": _relpath(OUT_DIR / "strategy_4_signals.csv"),
            "equity": _relpath(OUT_DIR / "strategy_4_equity.csv"),
            "monthly": _relpath(OUT_DIR / "strategy_4_monthly.csv"),
            "yearly": _relpath(OUT_DIR / "strategy_4_yearly.csv"),
            "stress": _relpath(OUT_DIR / "strategy_4_stress.csv"),
        },
    }


def _selections() -> pd.DataFrame:
    selections = pd.read_csv(ROOT / "artifacts" / "strategy_1b_expanded_controls_20260627" / "strategy_1b_selections.csv")
    selections = selections.copy()
    selections["original_lock_log"] = selections["lock_log"]
    selections["lock_log"] = selections["lock_log"].clip(upper=LOCK_LOG_CAP)
    return selections


def _side_streak(side: np.ndarray) -> np.ndarray:
    out = np.zeros(len(side), dtype=np.int16)
    running_side = 0
    running_bars = 0
    for index, current_side in enumerate(side):
        if current_side and current_side == running_side:
            running_bars += 1
        else:
            running_side = int(current_side)
            running_bars = 1 if current_side else 0
        out[index] = running_bars
    return out


def _simulate(
    base_side: np.ndarray,
    trend_side: np.ndarray,
    runner_side: np.ndarray,
    weak_trend: np.ndarray,
    base_streak: np.ndarray,
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
        quota_mode = False

        for index in range(start, end):
            signal_index = index - extra_delay_bars
            current_base_side = int(base_side[signal_index]) if signal_index >= 0 else 0
            current_trend_side = int(trend_side[signal_index]) if signal_index >= 0 else 0
            current_runner_side = int(runner_side[signal_index]) if signal_index >= 0 else 0
            is_weak_trend = bool(weak_trend[signal_index]) if signal_index >= 0 else False
            current_base_streak = int(base_streak[signal_index]) if signal_index >= 0 else 0
            guard_reason = "main"

            if halted:
                current_side = current_runner_side
                current_leverage = RUNNER_LEVERAGE if current_side else 0.0
                guard_reason = "post_lock_runner" if current_side else "post_lock_flat"
            else:
                current_side = current_base_side
                quota_leverage = strategy_1f._none_if_nan(params["quota_leverage"])
                current_leverage = (
                    min(float(quota_leverage), strategy_1f.LEVERAGE_CAP)
                    if quota_mode
                    and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS
                    and quota_leverage is not None
                    else min(float(params["leverage"]), strategy_1f.LEVERAGE_CAP)
                )

                conflicts_with_strong_trend = bool(
                    current_trend_side and current_base_side and current_base_side == -current_trend_side
                )
                if conflicts_with_strong_trend:
                    if month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS:
                        current_side = current_trend_side
                        current_leverage = strategy_1f.CONFLICT_FILLER_LEVERAGE
                        guard_reason = "strong_conflict_small_trend"
                    else:
                        current_side = 0
                        current_leverage = 0.0
                        guard_reason = "strong_conflict_flat"
                elif is_weak_trend and current_base_side != previous_side and current_side:
                    current_leverage = min(current_leverage, strategy_1f.WEAK_NEW_ORDER_LEVERAGE)
                    guard_reason = "weak_new_order_small"

                if current_side and current_side != previous_side and current_base_streak < ENTRY_CONFIRM_BARS:
                    current_side = 0
                    current_leverage = 0.0
                    guard_reason = "entry_confirm_wait"

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
                if not halted and current_base_side and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS:
                    current_side = current_base_side
                    current_leverage = strategy_1f.SHOCK_COOLDOWN_LEVERAGE
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
                }
            )

            month_log += current_lr
            month_orders += current_orders
            previous_position = current_position
            previous_side = current_side

            if not halted:
                quota_arm = strategy_1f._none_if_nan(params["quota_arm_log"])
                quota_leverage = strategy_1f._none_if_nan(params["quota_leverage"])
                if (
                    quota_arm is not None
                    and quota_leverage is not None
                    and not quota_mode
                    and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS
                    and month_log >= float(quota_arm)
                ):
                    quota_mode = True
                if month_orders >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS and month_log >= float(params["lock_log"]):
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
    base_streak: np.ndarray,
    market: dict[str, Any],
    selections: pd.DataFrame,
    cost_per_side: float,
    extra_delay_bars: int,
) -> dict[str, Any]:
    equity = _simulate(
        base_side,
        trend_side,
        runner_side,
        weak_trend,
        base_streak,
        market,
        selections,
        cost_per_side,
        extra_delay_bars,
    )
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)
    row = strategy_1c._result_row(equity, monthly, yearly)
    return {
        "cost_per_side": cost_per_side,
        "round_trip_cost": cost_per_side * 2,
        "extra_delay_bars": extra_delay_bars,
        **row,
        **strategy_1f._diagnostics(equity),
        **_coverage_diagnostics(equity),
        **_entry_quality_diagnostics(equity),
    }


def _coverage_diagnostics(equity: pd.DataFrame) -> dict[str, int]:
    strong = equity["trend_side"].to_numpy(int) != 0
    active = equity["active_position"].abs().to_numpy(float) > 1e-12
    return {
        "strong_trend_flat_bars": int((strong & ~active).sum()),
        "post_lock_runner_bars": int((equity["guard_reason"] == "post_lock_runner").sum()),
        "entry_confirm_wait_bars": int((equity["guard_reason"] == "entry_confirm_wait").sum()),
    }


def _entry_quality_diagnostics(equity: pd.DataFrame) -> dict[str, Any]:
    close = equity["close"].to_numpy(float)
    position = equity["position"].to_numpy(float)
    active = equity["active_position"].to_numpy(float)
    events = 0
    adverse_events = 0

    for index in range(len(equity) - 97):
        if abs(position[index] - active[index]) < 1e-12:
            continue
        if position[index] > active[index] and position[index] > 0:
            events += 1
            adverse_4h = (close[index + 1 : index + 17].min() / close[index] - 1.0) * 100.0
            adverse_1d = (close[index + 1 : index + 97].min() / close[index] - 1.0) * 100.0
            adverse_events += int(adverse_4h <= -2.0 or adverse_1d <= -4.0)
        elif position[index] < active[index] and position[index] < 0:
            events += 1
            adverse_4h = (close[index + 1 : index + 17].max() / close[index] - 1.0) * 100.0
            adverse_1d = (close[index + 1 : index + 97].max() / close[index] - 1.0) * 100.0
            adverse_events += int(adverse_4h >= 2.0 or adverse_1d >= 4.0)

    return {
        "entry_events": events,
        "adverse_entry_events": adverse_events,
        "adverse_entry_rate_pct": adverse_events / events * 100.0 if events else 0.0,
    }


def _render_report(summary: dict[str, Any]) -> str:
    row = summary["row"]
    hard_pass_count = sum(1 for item in summary["stress"] if item["hard_pass"])
    d = summary["diagnostics"]
    return "\n".join(
        [
            "# 4号候选：Entry Confirm",
            "",
            f"- strategy_id: `{summary['strategy_id']}`",
            "- 这是研究候选，不是固化版。",
            f"- hard_pass: `{row['hard_pass']}`",
            f"- 2025收益: `{row['return_2025_pct']}`",
            f"- 2026收益: `{row['return_2026_pct']}`",
            f"- 最差月份: `{row['min_monthly_return_pct']}`",
            f"- 压力场景通过: `{hard_pass_count}/9`",
            f"- 强趋势空仓K线: `{d['strong_trend_flat_bars']}`",
            f"- 进场等待K线: `{d['entry_confirm_wait_bars']}`",
            f"- 不利进场事件: `{d['adverse_entry_events']}/{d['entry_events']}`",
            "",
            "## 改动",
            "",
            "- 基于 3号候选。",
            "- 保留锁利后 0.10x 小趋势仓。",
            "- 主方向刚切换时，如果新方向还没有连续出现 4 根 15分钟K线，就先空仓等待。",
            "- 目的：减少假突破附近的大仓位反手，降低“山顶多、山脚空”的问题。",
        ]
    ) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
