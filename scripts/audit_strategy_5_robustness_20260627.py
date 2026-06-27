from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

import search_monthly_profit_lock_20260627 as lock_search
import search_online_expert_pool_20260627 as source_pool
import search_strategy_1_candidate_20260627 as strategy_1a
import search_strategy_1c_trend_runner_20260627 as strategy_1c
import search_strategy_1f_selective_runner_20260627 as strategy_1f
import search_strategy_2c_lock_cap_20260627 as strategy_2c
import search_strategy_4_entry_confirm_20260627 as strategy_4


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_5_robustness_audit_20260627"

COST_PER_SIDE_VALUES = [0.001, 0.0015, 0.002, 0.0025]
EXTRA_DELAY_BARS_VALUES = [0, 1, 2, 3]
MISS_RATES = [0.02, 0.05, 0.10]
MISS_SEEDS = [1, 2, 3]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    features = source_pool._add_features(source_pool._load_features(source_pool.FEATURE_FRAME))
    market = source_pool._market(features)
    candidates = _candidates(features, market)

    stress_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    miss_rows: list[dict[str, Any]] = []
    miss_monthly_rows: list[dict[str, Any]] = []
    regime_rows: list[dict[str, Any]] = []

    for candidate in candidates:
        for cost_per_side in COST_PER_SIDE_VALUES:
            for extra_delay_bars in EXTRA_DELAY_BARS_VALUES:
                equity = candidate["simulate"](cost_per_side, extra_delay_bars)
                strategy_1a._assert_signal_timing(equity)
                monthly = lock_search._monthly_breakdown(equity)
                yearly = lock_search._yearly_breakdown(monthly)
                row = strategy_1c._result_row(equity, monthly, yearly)
                scenario_id = f"{candidate['label']}_cost{cost_per_side:.4f}_delay{extra_delay_bars}"
                stress_rows.append(
                    {
                        "scenario_id": scenario_id,
                        "candidate": candidate["label"],
                        "cost_per_side": cost_per_side,
                        "round_trip_cost": cost_per_side * 2,
                        "extra_delay_bars": extra_delay_bars,
                        **row,
                    }
                )
                monthly_rows.extend(_tag_monthly(monthly, scenario_id, candidate["label"], cost_per_side, extra_delay_bars))
                failure_rows.extend(
                    _tag_monthly(_bad_months(monthly), scenario_id, candidate["label"], cost_per_side, extra_delay_bars)
                )

        base_equity = candidate["simulate"](lock_search.COST_PER_SIDE, 0)
        base_monthly = lock_search._monthly_breakdown(base_equity)
        regime_rows.extend(_regime_rows(base_equity, base_monthly, candidate["label"]))
        for miss_rate in MISS_RATES:
            for seed in MISS_SEEDS:
                missed = _apply_order_miss_stress(base_equity, lock_search.COST_PER_SIDE, miss_rate, seed)
                monthly = lock_search._monthly_breakdown(missed)
                yearly = lock_search._yearly_breakdown(monthly)
                row = strategy_1c._result_row(missed, monthly, yearly)
                scenario_id = f"{candidate['label']}_miss{miss_rate:.2f}_seed{seed}"
                miss_rows.append(
                    {
                        "scenario_id": scenario_id,
                        "candidate": candidate["label"],
                        "miss_rate": miss_rate,
                        "seed": seed,
                        "cost_per_side": lock_search.COST_PER_SIDE,
                        "round_trip_cost": lock_search.COST_PER_SIDE * 2,
                        **row,
                    }
                )
                miss_monthly_rows.extend(_tag_miss_monthly(monthly, scenario_id, candidate["label"], miss_rate, seed))

    stress = pd.DataFrame(stress_rows)
    monthly = pd.DataFrame(monthly_rows)
    failures = pd.DataFrame(failure_rows)
    miss = pd.DataFrame(miss_rows)
    miss_monthly = pd.DataFrame(miss_monthly_rows)
    regime = pd.DataFrame(regime_rows)

    stress.to_csv(OUT_DIR / "stress_matrix.csv", index=False)
    monthly.to_csv(OUT_DIR / "monthly_by_scenario.csv", index=False)
    failures.to_csv(OUT_DIR / "failure_months.csv", index=False)
    miss.to_csv(OUT_DIR / "order_miss_stress.csv", index=False)
    miss_monthly.to_csv(OUT_DIR / "order_miss_monthly.csv", index=False)
    regime.to_csv(OUT_DIR / "regime_base_monthly.csv", index=False)

    summary = {
        "status": "strategy_5_robustness_audit_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "does_not_overwrite": [
            "artifacts/strategy_2c_lock_cap_20260627",
            "artifacts/strategy_4_entry_confirm_20260627",
        ],
        "checked_candidates": [item["label"] for item in candidates],
        "stress_grid": {
            "round_trip_cost": [value * 2 for value in COST_PER_SIDE_VALUES],
            "extra_delay_bars": EXTRA_DELAY_BARS_VALUES,
        },
        "order_miss_grid": {"miss_rate": MISS_RATES, "seeds": MISS_SEEDS},
        "stress_rollup": _rollup(stress),
        "order_miss_rollup": _rollup(miss),
        "base_regime_rollup": _regime_rollup(regime),
        "decision": _decision(stress, miss),
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "stress_matrix": _relpath(OUT_DIR / "stress_matrix.csv"),
            "monthly_by_scenario": _relpath(OUT_DIR / "monthly_by_scenario.csv"),
            "failure_months": _relpath(OUT_DIR / "failure_months.csv"),
            "order_miss_stress": _relpath(OUT_DIR / "order_miss_stress.csv"),
            "order_miss_monthly": _relpath(OUT_DIR / "order_miss_monthly.csv"),
            "regime_base_monthly": _relpath(OUT_DIR / "regime_base_monthly.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _candidates(features: pd.DataFrame, market: dict[str, Any]) -> list[dict[str, Any]]:
    base_side = strategy_1f._base_side(features)
    trend_side = strategy_1f._trend_side(features)
    weak_trend = strategy_1f._weak_trend_mask(features)

    runner_2c = strategy_1f._runner_side(features)
    selections_2c = strategy_2c._selections()

    old_runner = (strategy_1f.RUNNER_GAP_BPS, strategy_1f.RUNNER_CONFIRM_BARS, strategy_1f.RUNNER_LEVERAGE)
    try:
        strategy_1f.RUNNER_GAP_BPS = strategy_4.RUNNER_GAP_BPS
        strategy_1f.RUNNER_CONFIRM_BARS = strategy_4.RUNNER_CONFIRM_BARS
        strategy_1f.RUNNER_LEVERAGE = strategy_4.RUNNER_LEVERAGE
        runner_4 = strategy_1f._runner_side(features)
    finally:
        strategy_1f.RUNNER_GAP_BPS, strategy_1f.RUNNER_CONFIRM_BARS, strategy_1f.RUNNER_LEVERAGE = old_runner

    base_streak = strategy_4._side_streak(base_side)
    selections_4 = strategy_4._selections()

    return [
        {
            "label": "2C",
            "simulate": lambda cost, delay: strategy_1f._simulate(
                base_side, trend_side, runner_2c, weak_trend, market, selections_2c, cost, delay
            ),
        },
        {
            "label": "4",
            "simulate": lambda cost, delay: strategy_4._simulate(
                base_side, trend_side, runner_4, weak_trend, base_streak, market, selections_4, cost, delay
            ),
        },
    ]


def _apply_order_miss_stress(equity: pd.DataFrame, cost_per_side: float, miss_rate: float, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    raw_return = np.log(equity["close"].astype(float)).diff().fillna(0.0).to_numpy(float)
    desired = equity["position"].to_numpy(float)
    executed = 0.0
    previous_side = 0
    rows: list[dict[str, Any]] = []

    for index, row in equity.reset_index(drop=True).iterrows():
        before = executed
        missed = abs(desired[index] - before) > 1e-12 and rng.random() < miss_rate
        if not missed:
            executed = float(desired[index])
        side = 0 if abs(executed) < 1e-12 else int(np.sign(executed))
        turnover = abs(executed - before)
        orders = abs(side - previous_side)
        rows.append(
            {
                "timestamp": row["timestamp"],
                "close": row["close"],
                "position": executed,
                "active_position": before,
                "turnover": turnover,
                "order_count": orders,
                "strategy_log_return": before * raw_return[index] - turnover * cost_per_side,
                "base_side": row.get("base_side", 0),
                "trend_side": row.get("trend_side", 0),
                "weak_trend": row.get("weak_trend", False),
                "guard_reason": "missed_order" if missed else row.get("guard_reason", "main"),
            }
        )
        previous_side = side

    out = pd.DataFrame(rows)
    out["equity"] = np.exp(out["strategy_log_return"].cumsum())
    out["drawdown"] = out["equity"] / out["equity"].cummax() - 1.0
    strategy_1a._assert_signal_timing(out)
    return out


def _bad_months(monthly: pd.DataFrame) -> pd.DataFrame:
    eval_monthly = monthly.loc[monthly["month"].str[:4].isin(lock_search.EVAL_YEARS)]
    return eval_monthly.loc[
        (eval_monthly["return_pct"] <= 0) | (eval_monthly["orders"] < lock_search.REQUIRED_MIN_MONTHLY_ORDERS)
    ]


def _tag_monthly(
    monthly: pd.DataFrame,
    scenario_id: str,
    candidate: str,
    cost_per_side: float,
    extra_delay_bars: int,
) -> list[dict[str, Any]]:
    rows = monthly.to_dict("records")
    for row in rows:
        row["scenario_id"] = scenario_id
        row["candidate"] = candidate
        row["cost_per_side"] = cost_per_side
        row["round_trip_cost"] = cost_per_side * 2
        row["extra_delay_bars"] = extra_delay_bars
    return rows


def _tag_miss_monthly(monthly: pd.DataFrame, scenario_id: str, candidate: str, miss_rate: float, seed: int) -> list[dict[str, Any]]:
    rows = monthly.to_dict("records")
    for row in rows:
        row["scenario_id"] = scenario_id
        row["candidate"] = candidate
        row["miss_rate"] = miss_rate
        row["seed"] = seed
    return rows


def _regime_rows(equity: pd.DataFrame, monthly: pd.DataFrame, candidate: str) -> list[dict[str, Any]]:
    frame = equity.copy()
    frame["month"] = pd.to_datetime(frame["timestamp"]).dt.strftime("%Y-%m")
    rows = []
    for row in monthly.to_dict("records"):
        month_frame = frame.loc[frame["month"] == row["month"]]
        if month_frame.empty:
            continue
        close = month_frame["close"].to_numpy(float)
        market_return_pct = (close[-1] / close[0] - 1.0) * 100.0
        drawdown_pct = (close / np.maximum.accumulate(close) - 1.0).min() * 100.0
        runup_pct = (close / np.minimum.accumulate(close) - 1.0).max() * 100.0
        regime = "up" if market_return_pct >= 5.0 else "down" if market_return_pct <= -5.0 else "sideways"
        shock = abs(drawdown_pct) >= 15.0 or runup_pct >= 15.0
        rows.append(
            {
                "candidate": candidate,
                "month": row["month"],
                "market_regime": regime,
                "shock_month": bool(shock),
                "market_return_pct": market_return_pct,
                "market_max_drawdown_pct": drawdown_pct,
                "market_max_runup_pct": runup_pct,
                "strategy_return_pct": row["return_pct"],
                "strategy_orders": row["orders"],
                "strategy_drawdown_pct": row["drawdown_pct"],
            }
        )
    return rows


def _rollup(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for candidate, group in frame.groupby("candidate", sort=True):
        rows.append(
            {
                "candidate": candidate,
                "scenarios": int(len(group)),
                "hard_pass_scenarios": int(group["hard_pass"].sum()),
                "failed_scenarios": int((~group["hard_pass"]).sum()),
                "worst_min_required_year_return_pct": float(group["min_required_year_return_pct"].min()),
                "worst_min_monthly_return_pct": float(group["min_monthly_return_pct"].min()),
                "worst_max_drawdown_pct": float(group["max_drawdown_pct"].min()),
            }
        )
    return lock_search._json_ready(rows)


def _regime_rollup(regime: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for (candidate, market_regime), group in regime.groupby(["candidate", "market_regime"], sort=True):
        rows.append(
            {
                "candidate": candidate,
                "market_regime": market_regime,
                "months": int(len(group)),
                "min_strategy_return_pct": float(group["strategy_return_pct"].min()),
                "avg_strategy_return_pct": float(group["strategy_return_pct"].mean()),
                "min_orders": int(group["strategy_orders"].min()),
            }
        )
    return lock_search._json_ready(rows)


def _decision(stress: pd.DataFrame, miss: pd.DataFrame) -> dict[str, Any]:
    combined = pd.concat(
        [
            stress.assign(test_family="cost_delay"),
            miss.assign(test_family="order_miss", extra_delay_bars=np.nan),
        ],
        ignore_index=True,
        sort=False,
    )
    scores = []
    for candidate, group in combined.groupby("candidate", sort=True):
        scores.append(
            {
                "candidate": candidate,
                "total_hard_pass": int(group["hard_pass"].sum()),
                "total_scenarios": int(len(group)),
                "worst_min_monthly_return_pct": float(group["min_monthly_return_pct"].min()),
                "worst_min_required_year_return_pct": float(group["min_required_year_return_pct"].min()),
            }
        )
    scores = sorted(scores, key=lambda row: (row["total_hard_pass"], row["worst_min_monthly_return_pct"]), reverse=True)
    miss_profit = []
    for candidate, group in miss.groupby("candidate", sort=True):
        miss_profit.append(
            {
                "candidate": candidate,
                "order_miss_scenarios": int(len(group)),
                "order_miss_no_losing_month_scenarios": int((group["losing_eval_months"] == 0).sum()),
                "worst_order_miss_min_monthly_return_pct": float(group["min_monthly_return_pct"].min()),
            }
        )
    miss_profit = sorted(
        miss_profit,
        key=lambda row: (row["order_miss_no_losing_month_scenarios"], row["worst_order_miss_min_monthly_return_pct"]),
        reverse=True,
    )
    return {
        "strict_hard_pass_preference": scores[0]["candidate"] if scores else None,
        "order_miss_profit_preference": miss_profit[0]["candidate"] if miss_profit else None,
        "scoreboard": lock_search._json_ready(scores),
        "order_miss_profit_scoreboard": lock_search._json_ready(miss_profit),
        "note": "This is an audit, not a new strategy. 4 wins the strict pass count; 2C is cleaner if order-miss profitability is weighted above the monthly order-count rule.",
    }


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# 5号鲁棒性审计",
        "",
        "- 范围：只比较 2C 和 4号；不改策略规则。",
        "- 手续费/延迟：开平合计 0.2%/0.3%/0.4%/0.5%，额外晚 0/1/2/3 根K线。",
        "- 漏成交：基础手续费下，随机漏掉 2%/5%/10% 调仓指令，各跑 3 个固定种子。",
        "",
        "## 手续费/延迟",
        "",
        "| 候选 | 通过 | 失败 | 最差年度收益 | 最差月收益 | 最差回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["stress_rollup"]:
        lines.append(
            f"| {row['candidate']} | {row['hard_pass_scenarios']} | {row['failed_scenarios']} | "
            f"{row['worst_min_required_year_return_pct']:.2f} | {row['worst_min_monthly_return_pct']:.2f} | "
            f"{row['worst_max_drawdown_pct']:.2f} |"
        )
    lines.extend(["", "## 漏成交", "", "| 候选 | 通过 | 失败 | 最差年度收益 | 最差月收益 | 最差回撤 |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for row in summary["order_miss_rollup"]:
        lines.append(
            f"| {row['candidate']} | {row['hard_pass_scenarios']} | {row['failed_scenarios']} | "
            f"{row['worst_min_required_year_return_pct']:.2f} | {row['worst_min_monthly_return_pct']:.2f} | "
            f"{row['worst_max_drawdown_pct']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"- 严格硬指标通过数偏向：`{summary['decision']['strict_hard_pass_preference']}`。",
            f"- 漏成交后只看是否亏月，偏向：`{summary['decision']['order_miss_profit_preference']}`。",
            "- 注意：漏成交测试是执行层压力测试，不重新运行月内锁利选择逻辑。",
            "",
            "## 文件",
            "",
            f"- 压力矩阵：`{summary['files']['stress_matrix']}`",
            f"- 漏成交测试：`{summary['files']['order_miss_stress']}`",
            f"- 市场状态月表：`{summary['files']['regime_base_monthly']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
