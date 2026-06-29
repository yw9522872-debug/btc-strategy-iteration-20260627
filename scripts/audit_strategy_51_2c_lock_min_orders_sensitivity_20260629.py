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
import search_strategy_2c_lock_cap_20260627 as strategy_2c


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_51_2c_lock_min_orders_sensitivity_20260629"
STRATEGY_ID = "strategy_51_2c_lock_min_orders_sensitivity_20260629"
LOCK_MIN_ORDERS = [10, 20, 30, 50, 100, None]
QUOTA_MIN_ORDERS = 10


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = source_pool._load_features(source_pool.FEATURE_FRAME)
    features = source_pool._add_features(source)
    market = source_pool._market(features)
    base_side = strategy_1f._base_side(features)
    trend_side = strategy_1f._trend_side(features)
    runner_side = strategy_1f._runner_side(features)
    weak_trend = strategy_1f._weak_trend_mask(features)
    selections = strategy_2c._selections()

    rows: list[dict[str, Any]] = []
    yearly_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    for min_orders in LOCK_MIN_ORDERS:
        variant_id = f"lock_after_{min_orders}_orders" if min_orders is not None else "no_monthly_lock"
        equity = _simulate(
            base_side,
            trend_side,
            runner_side,
            weak_trend,
            market,
            selections,
            lock_search.COST_PER_SIDE,
            min_lock_orders=min_orders,
        )
        strategy_1a._assert_signal_timing(equity)
        monthly = lock_search._monthly_breakdown(equity)
        yearly = lock_search._yearly_breakdown(monthly)
        row = strategy_1c._result_row(equity, monthly, yearly)
        diagnostics = strategy_1f._diagnostics(equity)
        rows.append(
            {
                "variant_id": variant_id,
                "min_lock_orders": min_orders,
                "quota_min_orders_kept_at": QUOTA_MIN_ORDERS,
                **row,
                **diagnostics,
            }
        )
        monthly.insert(0, "variant_id", variant_id)
        yearly.insert(0, "variant_id", variant_id)
        monthly_frames.append(monthly)
        yearly_frames.append(yearly)

    scan = pd.DataFrame(rows)
    monthly_all = pd.concat(monthly_frames, ignore_index=True)
    yearly_all = pd.concat(yearly_frames, ignore_index=True)
    scan.to_csv(OUT_DIR / "strategy_51_scan.csv", index=False)
    monthly_all.to_csv(OUT_DIR / "strategy_51_monthly.csv", index=False)
    yearly_all.to_csv(OUT_DIR / "strategy_51_yearly.csv", index=False)

    summary = {
        "status": "strategy_51_2c_lock_min_orders_sensitivity_done",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "base": "strategy_2c_lock_cap_20260627",
        "strict_no_future_function": True,
        "change": "Keep Strategy 2C mostly unchanged, but require more monthly trades before monthly profit lock can halt trading.",
        "cost_model": {
            "cost_per_side": lock_search.COST_PER_SIDE,
            "round_trip_open_close": lock_search.COST_PER_SIDE * 2,
        },
        "quota_min_orders_kept_at": QUOTA_MIN_ORDERS,
        "scan": lock_search._json_ready(scan.to_dict("records")),
        "decision": _decision(scan),
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "scan": _relpath(OUT_DIR / "strategy_51_scan.csv"),
            "monthly": _relpath(OUT_DIR / "strategy_51_monthly.csv"),
            "yearly": _relpath(OUT_DIR / "strategy_51_yearly.csv"),
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
    *,
    min_lock_orders: int | None,
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
            current_base_side = int(base_side[index])
            current_trend_side = int(trend_side[index])
            is_weak_trend = bool(weak_trend[index])
            guard_reason = "main"

            if halted:
                current_side = int(runner_side[index])
                current_leverage = strategy_1f.RUNNER_LEVERAGE if current_side else 0.0
                guard_reason = "post_lock_runner" if current_side else "post_lock_flat"
            else:
                current_side = current_base_side
                quota_leverage = strategy_1f._none_if_nan(params["quota_leverage"])
                current_leverage = (
                    min(float(quota_leverage), strategy_1f.LEVERAGE_CAP)
                    if quota_mode and month_orders < QUOTA_MIN_ORDERS and quota_leverage is not None
                    else min(float(params["leverage"]), strategy_1f.LEVERAGE_CAP)
                )
                conflicts_with_strong_trend = bool(
                    current_trend_side and current_base_side and current_base_side == -current_trend_side
                )
                if conflicts_with_strong_trend:
                    if month_orders < QUOTA_MIN_ORDERS:
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

                if shock_cooldown > 0 and current_side:
                    current_leverage = min(current_leverage, strategy_1f.SHOCK_COOLDOWN_LEVERAGE)
                    guard_reason = "shock_cooldown_small"

            current_position = current_side * current_leverage
            current_turnover = abs(current_position - previous_position)
            current_orders = abs(current_side - previous_side)
            current_lr = previous_position * market["raw_return"][index] - current_turnover * cost_per_side

            adverse_shock = previous_position != 0 and previous_position * market["raw_return"][index] <= -strategy_1f.ADVERSE_SHOCK_LOSS_LOG
            if adverse_shock:
                if not halted and current_base_side and month_orders < QUOTA_MIN_ORDERS:
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
                    and month_orders < QUOTA_MIN_ORDERS
                    and month_log >= float(quota_arm)
                ):
                    quota_mode = True
                if min_lock_orders is not None and month_orders >= min_lock_orders and month_log >= float(params["lock_log"]):
                    halted = True

    equity = pd.DataFrame(records)
    equity["equity"] = np.exp(equity["strategy_log_return"].cumsum())
    equity["drawdown"] = equity["equity"] / equity["equity"].cummax() - 1.0
    return equity


def _decision(scan: pd.DataFrame) -> dict[str, Any]:
    pass_rows = scan.loc[scan["hard_pass"]]
    beyond_10 = pass_rows.loc[pass_rows["min_lock_orders"].fillna(999999) > 10]
    return {
        "verdict": "TEN_TRADE_MONTHLY_LOCK_IS_A_FRAGILE_PART_OF_2C",
        "hard_pass_variants": pass_rows["variant_id"].tolist(),
        "hard_pass_after_more_than_10_orders": beyond_10["variant_id"].tolist(),
        "reason": "2C的好结果依赖很早的月度锁利。只要要求锁利前多做一些交易，原始信号弱的问题就暴露出来，回撤很快变成灾难级。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Strategy 51：2C 锁利前交易次数敏感性审计",
        "",
        f"- strategy_id: `{summary['strategy_id']}`",
        "- 这是研究审计，不是固化版。",
        "- 目的：检查2C是不是太依赖每月10笔后锁利。",
        f"- 手续费：开平合计 `{summary['cost_model']['round_trip_open_close']}`",
        "",
        "| 版本 | 2025 | 2026 | 最差月 | 亏损月 | 最少月交易 | 最大回撤 | hard_pass |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary["scan"]:
        lines.append(
            f"| `{row['variant_id']}` | {row['return_2025_pct']:.2f}% | {row['return_2026_pct']:.2f}% | "
            f"{row['min_monthly_return_pct']:.2f}% | {row['losing_eval_months']} | "
            f"{row['min_monthly_orders']} | {row['max_drawdown_pct']:.2f}% | `{row['hard_pass']}` |"
        )
    lines += [
        "",
        "## 结论",
        "",
        f"- `{summary['decision']['verdict']}`",
        f"- {summary['decision']['reason']}",
    ]
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
