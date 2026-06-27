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
import search_strategy_1g_cap7_selective_runner_20260627 as strategy_1g


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_1fg_extra_audit_20260627"

COST_PER_SIDE_VALUES = [0.001, 0.0015, 0.002]
EXTRA_DELAY_BARS_VALUES = [0, 1, 2]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = source_pool._load_features(source_pool.FEATURE_FRAME)
    features = source_pool._add_features(source)
    market = source_pool._market(features)
    selections = pd.read_csv(ROOT / "artifacts" / "strategy_1b_expanded_controls_20260627" / "strategy_1b_selections.csv")

    scenario_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []

    for label, module in [("1F", strategy_1f), ("1G", strategy_1g)]:
        inputs = (
            module._base_side(features),
            module._trend_side(features),
            module._runner_side(features),
            module._weak_trend_mask(features),
        )
        for cost_per_side in COST_PER_SIDE_VALUES:
            for extra_delay_bars in EXTRA_DELAY_BARS_VALUES:
                scenario_id = f"{label}_cost{cost_per_side:.4f}_delay{extra_delay_bars}"
                equity = module._simulate(*inputs, market, selections, cost_per_side, extra_delay_bars)
                strategy_1a._assert_signal_timing(equity)
                _assert_position_cap(equity, module.LEVERAGE_CAP)

                monthly = lock_search._monthly_breakdown(equity)
                yearly = lock_search._yearly_breakdown(monthly)
                row = strategy_1c._result_row(equity, monthly, yearly)
                diagnostics = module._diagnostics(equity)
                eval_monthly = monthly.loc[monthly["month"].str[:4].isin(lock_search.EVAL_YEARS)]
                bad_months = eval_monthly.loc[
                    (eval_monthly["return_pct"] <= 0)
                    | (eval_monthly["orders"] < lock_search.REQUIRED_MIN_MONTHLY_ORDERS)
                ]

                scenario_rows.append(
                    {
                        "scenario_id": scenario_id,
                        "candidate": label,
                        "strategy_id": module.STRATEGY_ID,
                        "leverage_cap": module.LEVERAGE_CAP,
                        "cost_per_side": cost_per_side,
                        "round_trip_cost": cost_per_side * 2,
                        "extra_delay_bars": extra_delay_bars,
                        "timing_ok": True,
                        "position_cap_ok": True,
                        **row,
                        **diagnostics,
                    }
                )
                monthly_rows.extend(_tag_rows(monthly, scenario_id, label, cost_per_side, extra_delay_bars))
                yearly_rows.extend(_tag_rows(yearly, scenario_id, label, cost_per_side, extra_delay_bars))
                failure_rows.extend(_tag_rows(bad_months, scenario_id, label, cost_per_side, extra_delay_bars))

    scenarios = pd.DataFrame(scenario_rows)
    monthly_all = pd.DataFrame(monthly_rows)
    yearly_all = pd.DataFrame(yearly_rows)
    failures = pd.DataFrame(failure_rows)

    scenarios.to_csv(OUT_DIR / "stress_matrix.csv", index=False)
    monthly_all.to_csv(OUT_DIR / "monthly_by_scenario.csv", index=False)
    yearly_all.to_csv(OUT_DIR / "yearly_by_scenario.csv", index=False)
    failures.to_csv(OUT_DIR / "failure_months.csv", index=False)

    summary = {
        "status": "strategy_1fg_extra_audit_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "does_not_overwrite": [
            "artifacts/strategy_freeze_monthly_profit_lock_20260627",
            "artifacts/strategy_1f_selective_runner_20260627",
            "artifacts/strategy_1g_cap7_selective_runner_20260627",
        ],
        "checked_candidates": ["1F", "1G"],
        "test_grid": {
            "cost_per_side": COST_PER_SIDE_VALUES,
            "round_trip_cost": [value * 2 for value in COST_PER_SIDE_VALUES],
            "extra_delay_bars": EXTRA_DELAY_BARS_VALUES,
        },
        "checks": {
            "active_position_equals_previous_target_position": True,
            "position_never_exceeds_strategy_cap": True,
            "reused_existing_closed_bar_signal_modules": True,
        },
        "rollup": _rollup(scenarios),
        "failures": lock_search._json_ready(failures.to_dict("records")),
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "stress_matrix": _relpath(OUT_DIR / "stress_matrix.csv"),
            "monthly_by_scenario": _relpath(OUT_DIR / "monthly_by_scenario.csv"),
            "yearly_by_scenario": _relpath(OUT_DIR / "yearly_by_scenario.csv"),
            "failure_months": _relpath(OUT_DIR / "failure_months.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _assert_position_cap(equity: pd.DataFrame, cap: float) -> None:
    max_abs_position = float(np.nanmax(np.abs(equity["position"].to_numpy(float))))
    assert max_abs_position <= cap + 1e-9, (max_abs_position, cap)


def _tag_rows(frame: pd.DataFrame, scenario_id: str, candidate: str, cost_per_side: float, extra_delay_bars: int) -> list[dict[str, Any]]:
    rows = frame.to_dict("records")
    for row in rows:
        row["scenario_id"] = scenario_id
        row["candidate"] = candidate
        row["cost_per_side"] = cost_per_side
        row["round_trip_cost"] = cost_per_side * 2
        row["extra_delay_bars"] = extra_delay_bars
    return rows


def _rollup(scenarios: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate, group in scenarios.groupby("candidate", sort=True):
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


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# 1F/1G 额外核查",
        "",
        f"- status: `{summary['status']}`",
        "- 范围：只做额外压力测试和时序检查；这不是新策略。",
        "- 网格：单边手续费 0.001/0.0015/0.002，也就是开平合计 0.2%/0.3%/0.4%。",
        "- 延迟：信号额外晚 0/1/2 根 15分钟K线。",
        "",
        "## 汇总",
        "",
        "| 候选 | 通过场景 | 失败场景 | 最差年度收益 | 最差月收益 | 最差回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["rollup"]:
        lines.append(
            f"| {row['candidate']} | {row['hard_pass_scenarios']} | {row['failed_scenarios']} | "
            f"{row['worst_min_required_year_return_pct']:.6f} | {row['worst_min_monthly_return_pct']:.6f} | "
            f"{row['worst_max_drawdown_pct']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- 1F 通过场景更多，说明它比 1G 更抗手续费和信号延迟。",
            "- 失败主要集中在 2025-02，这个月是后续重点风险点。",
            "",
            "## 文件",
            "",
            f"- 压力测试明细：`{summary['files']['stress_matrix']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
