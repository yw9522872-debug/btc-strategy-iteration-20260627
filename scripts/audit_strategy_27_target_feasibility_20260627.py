from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import audit_strategy_16_new_family_probe_20260627 as probe16
import audit_strategy_22_hard_target_bottleneck_20260627 as probe22


STRATEGY_ID = "strategy_27_target_feasibility_audit_20260627"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
SOURCE_22 = ROOT / "artifacts" / "strategy_22_hard_target_bottleneck_20260627"
SOURCE_23_SUMMARY = ROOT / "artifacts" / "strategy_23_funding_rate_upper_bound_20260627" / "summary.json"
SOURCE_24_SUMMARY = ROOT / "artifacts" / "strategy_24_funding_rate_strict_selector_20260627" / "summary.json"
SOURCE_26_SUMMARY = ROOT / "artifacts" / "strategy_26_intrabar_1m_upper_bound_20260627" / "summary.json"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _patch_probe22_month_requirements()
    candidate_monthly = pd.read_csv(SOURCE_22 / "candidate_monthly_base.csv")
    candidate_meta = pd.read_csv(SOURCE_22 / "candidate_pool_summary.csv")

    target_grid = _target_grid(candidate_monthly, candidate_meta)
    gate_relaxation = _gate_relaxation(target_grid)
    source_context = _source_context(target_grid)
    summary = _make_summary(candidate_meta, target_grid, gate_relaxation, source_context)

    target_grid.to_csv(OUT_DIR / "target_grid_summary.csv", index=False)
    gate_relaxation.to_csv(OUT_DIR / "gate_relaxation_summary.csv", index=False)
    source_context.to_csv(OUT_DIR / "source_family_context.csv", index=False)
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _patch_probe22_month_requirements() -> None:
    def month_fail_array(return_pct: np.ndarray, requirement: str) -> np.ndarray:
        if requirement == "allow_any":
            return np.zeros_like(return_pct, dtype=bool)
        if requirement == "return_ge_minus2":
            return return_pct < -2.0
        if requirement == "return_ge_minus1":
            return return_pct < -1.0
        if requirement == "return_gt_0":
            return return_pct <= 0.0
        raise ValueError(requirement)

    def month_fail_flag(return_pct: pd.Series, requirement: str) -> pd.Series:
        if requirement == "allow_any":
            return pd.Series(False, index=return_pct.index)
        if requirement == "return_ge_minus2":
            return return_pct < -2.0
        if requirement == "return_ge_minus1":
            return return_pct < -1.0
        if requirement == "return_gt_0":
            return return_pct <= 0.0
        raise ValueError(requirement)

    # ponytail: reuse Strategy 22 grid code; this patch only adds the -2% monthly gate for this audit.
    probe22._month_fail_array = month_fail_array
    probe22._month_fail_flag = month_fail_flag


def _target_grid(candidate_monthly: pd.DataFrame, candidate_meta: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    specs = []
    for cost in [0.002]:
        for order_floor in [0, 5, 10]:
            for monthly_requirement in ["allow_any", "return_ge_minus2", "return_ge_minus1", "return_gt_0"]:
                for annual_threshold_pct in [30.0, 50.0, 80.0, 100.0]:
                    specs.append(_spec(cost, order_floor, monthly_requirement, annual_threshold_pct))
    specs.append(_spec(0.0, 10, "return_gt_0", 100.0))

    for cost in sorted({float(spec["round_trip_cost"]) for spec in specs}):
        cube = probe22._make_cube(candidate_monthly, candidate_meta, cost / 2.0)
        for spec in [spec for spec in specs if float(spec["round_trip_cost"]) == cost]:
            strict_monthly, _ = probe22._strict_selector_cube(cube, spec)
            rows.append(probe22._scenario_summary("strict_expanding_selector", strict_monthly, spec))
            oracle_monthly = probe22._oracle_cube(cube, spec)
            rows.append(probe22._scenario_summary("monthly_oracle", oracle_monthly, spec))
    return pd.DataFrame(rows).sort_values(
        ["round_trip_cost", "method", "order_floor", "monthly_requirement", "annual_threshold_pct"]
    )


def _spec(cost: float, order_floor: int, monthly_requirement: str, annual_threshold_pct: float) -> dict[str, Any]:
    return {
        "order_floor": int(order_floor),
        "round_trip_cost": float(cost),
        "cost_per_side": float(cost) / 2.0,
        "monthly_requirement": monthly_requirement,
        "annual_threshold_pct": float(annual_threshold_pct),
    }


def _gate_relaxation(target_grid: pd.DataFrame) -> pd.DataFrame:
    scenarios = [
        ("original", 0.002, 10, "return_gt_0", 100.0),
        ("annual_80_only", 0.002, 10, "return_gt_0", 80.0),
        ("annual_50_only", 0.002, 10, "return_gt_0", 50.0),
        ("annual_30_only", 0.002, 10, "return_gt_0", 30.0),
        ("allow_month_minus1_only", 0.002, 10, "return_ge_minus1", 100.0),
        ("allow_month_minus2_only", 0.002, 10, "return_ge_minus2", 100.0),
        ("order_floor_5_only", 0.002, 5, "return_gt_0", 100.0),
        ("order_floor_0_only", 0.002, 0, "return_gt_0", 100.0),
        ("combined_50_minus1_order5", 0.002, 5, "return_ge_minus1", 50.0),
        ("combined_30_minus2_order5", 0.002, 5, "return_ge_minus2", 30.0),
        ("no_fee_original_gates", 0.0, 10, "return_gt_0", 100.0),
    ]
    rows = []
    for scenario_id, cost, order_floor, monthly_requirement, annual_threshold_pct in scenarios:
        subset = target_grid.loc[
            (target_grid["round_trip_cost"].round(6) == round(cost, 6))
            & (target_grid["order_floor"] == order_floor)
            & (target_grid["monthly_requirement"] == monthly_requirement)
            & (target_grid["annual_threshold_pct"] == annual_threshold_pct)
        ].copy()
        for row in subset.to_dict("records"):
            row["scenario_id"] = scenario_id
            rows.append(row)
    return pd.DataFrame(rows)


def _source_context(target_grid: pd.DataFrame) -> pd.DataFrame:
    s23 = _read_json(SOURCE_23_SUMMARY)
    s24 = _read_json(SOURCE_24_SUMMARY)
    s26 = _read_json(SOURCE_26_SUMMARY)
    original = target_grid.loc[
        (target_grid["round_trip_cost"].round(6) == 0.002)
        & (target_grid["order_floor"] == 10)
        & (target_grid["monthly_requirement"] == "return_gt_0")
        & (target_grid["annual_threshold_pct"] == 100.0)
    ]
    strict_original = original.loc[original["method"] == "strict_expanding_selector"].iloc[0]
    oracle_original = original.loc[original["method"] == "monthly_oracle"].iloc[0]
    return pd.DataFrame(
        [
            {
                "source": "16/19/20/21 composite micro-rules",
                "test_type": "strict selector",
                "best_known_result": f"original target pass={bool(strict_original['scenario_pass'])}; 2025={strict_original['return_2025_pct']:.2f}%; 2026={strict_original['return_2026_ytd_pct']:.2f}%",
                "decision": "fails even under relaxed target grid",
            },
            {
                "source": "16/19/20/21 composite micro-rules",
                "test_type": "monthly oracle",
                "best_known_result": f"original target pass={bool(oracle_original['scenario_pass'])}; non-passing months={int(oracle_original['non_passing_months'])}",
                "decision": "oracle can pass only after relaxing targets; not tradeable",
            },
            {
                "source": "23 funding rate",
                "test_type": "monthly oracle",
                "best_known_result": _brief_result(s23["best_oracle"]),
                "decision": s23["decision"]["verdict"],
            },
            {
                "source": "24 funding rate",
                "test_type": "strict selector",
                "best_known_result": _brief_result(s24["best_selector"]),
                "decision": s24["decision"]["verdict"],
            },
            {
                "source": "26 1m intrabar",
                "test_type": "monthly oracle",
                "best_known_result": _brief_result(s26["best_oracle"]),
                "decision": s26["decision"]["verdict"],
            },
        ]
    )


def _brief_result(row: dict[str, Any]) -> str:
    return (
        f"2023={row['return_2023_pct']:.2f}%; 2024={row['return_2024_pct']:.2f}%; "
        f"2025={row['return_2025_pct']:.2f}%; 2026={row['return_2026_ytd_pct']:.2f}%; "
        f"losing_months={row['losing_eval_months']}; min_orders={row['min_monthly_orders']}"
    )


def _make_summary(
    candidate_meta: pd.DataFrame,
    target_grid: pd.DataFrame,
    gate_relaxation: pd.DataFrame,
    source_context: pd.DataFrame,
) -> dict[str, Any]:
    strict = target_grid.loc[target_grid["method"] == "strict_expanding_selector"].copy()
    oracle = target_grid.loc[target_grid["method"] == "monthly_oracle"].copy()
    strict_pass_count = int(strict["scenario_pass"].sum())
    oracle_pass_count = int(oracle["scenario_pass"].sum())
    original_rows = gate_relaxation.loc[gate_relaxation["scenario_id"] == "original"].sort_values("method")
    strict_best_active = strict.loc[strict["orders"] > 0].copy()
    strict_best_active["min_2025_2026_pct"] = strict_best_active[["return_2025_pct", "return_2026_ytd_pct"]].min(axis=1)
    best_active = strict_best_active.sort_values(
        ["min_2025_2026_pct", "monthly_requirement_pass", "order_floor_pass", "return_2025_pct"],
        ascending=[False, False, False, False],
    ).iloc[0].to_dict()
    oracle_pass = oracle.loc[oracle["scenario_pass"]].copy()
    oracle_pass["monthly_strictness_rank"] = oracle_pass["monthly_requirement"].map(
        {"allow_any": 0, "return_ge_minus2": 1, "return_ge_minus1": 2, "return_gt_0": 3}
    )
    main_cost_oracle_pass = oracle_pass.loc[oracle_pass["round_trip_cost"].round(6) == 0.002].copy()
    best_oracle_pass = main_cost_oracle_pass.sort_values(
        ["annual_threshold_pct", "order_floor", "monthly_strictness_rank"],
        ascending=[False, False, False],
    )
    return {
        "status": "strategy_27_target_feasibility_audit_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Audit whether changing the target, rather than adding more micro-rules, creates a realistic research target.",
        "source": {
            "strategy_22_candidate_monthly_base": _rel(SOURCE_22 / "candidate_monthly_base.csv"),
            "strategy_22_candidate_pool_summary": _rel(SOURCE_22 / "candidate_pool_summary.csv"),
            "strategy_23_summary": _rel(SOURCE_23_SUMMARY),
            "strategy_24_summary": _rel(SOURCE_24_SUMMARY),
            "strategy_26_summary": _rel(SOURCE_26_SUMMARY),
            "new_candidate_rules_added": False,
        },
        "grid": {
            "main_round_trip_cost": 0.002,
            "extra_no_fee_original_gate_check": True,
            "order_floors": [0, 5, 10],
            "monthly_requirements": ["allow_any", "return_ge_minus2", "return_ge_minus1", "return_gt_0"],
            "annual_thresholds_pct": [30.0, 50.0, 80.0, 100.0],
            "methods": ["strict_expanding_selector", "monthly_oracle"],
        },
        "candidate_pool": {
            "total_candidates_from_16_19_20_21": int(len(candidate_meta)),
            "by_pool": {str(k): int(v) for k, v in candidate_meta["pool"].value_counts().sort_index().items()},
        },
        "results": {
            "strict_pass_count": strict_pass_count,
            "strict_scenario_count": int(len(strict)),
            "oracle_pass_count": oracle_pass_count,
            "oracle_scenario_count": int(len(oracle)),
            "original_rows": _json_ready(original_rows.to_dict("records")),
            "best_strict_active_balance": _json_ready(best_active),
            "best_main_cost_oracle_passing_row": _json_ready(best_oracle_pass.iloc[0].to_dict()) if len(best_oracle_pass) else None,
        },
        "source_context": _json_ready(source_context.to_dict("records")),
        "decision": _decision(strict_pass_count, oracle_pass_count, best_active, source_context),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "strategy_22_candidate_monthly_base_sha256": _sha256(SOURCE_22 / "candidate_monthly_base.csv"),
            "strategy_23_summary_sha256": _sha256(SOURCE_23_SUMMARY),
            "strategy_24_summary_sha256": _sha256(SOURCE_24_SUMMARY),
            "strategy_26_summary_sha256": _sha256(SOURCE_26_SUMMARY),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "target_grid_summary": _rel(OUT_DIR / "target_grid_summary.csv"),
            "gate_relaxation_summary": _rel(OUT_DIR / "gate_relaxation_summary.csv"),
            "source_family_context": _rel(OUT_DIR / "source_family_context.csv"),
        },
    }


def _decision(strict_pass_count: int, oracle_pass_count: int, best_active: dict[str, Any], source_context: pd.DataFrame) -> dict[str, Any]:
    if strict_pass_count:
        verdict = "RELAXED_TARGET_CAN_PASS_STRICT_SELECTOR"
        reason = "放宽后严格选择器出现通过目标。"
        next_step = "围绕最小放宽口径做独立样本和执行压力复查。"
    elif oracle_pass_count:
        verdict = "TARGET_RELAXATION_HELPS_ORACLE_NOT_SELECTOR"
        reason = "放宽目标能让看答案上限通过，但严格逐月选择仍0个通过；真正卡点是提前选择能力。"
        next_step = "不要继续加免费K线小规则；若不拿新数据，应把研究目标降到影子跟踪/低年化验证，而不是继续追每月盈利。"
    else:
        verdict = "TESTED_FEATURES_FAIL_EVEN_RELAXED_TARGETS"
        reason = "连看答案上限都没有通过放宽目标。"
        next_step = "停止这些特征，换数据或大幅降低目标。"
    return {
        "verdict": verdict,
        "promote_strategy": False,
        "reason": reason,
        "next_step": next_step,
        "best_strict_active_2025_pct": float(best_active["return_2025_pct"]),
        "best_strict_active_2026_ytd_pct": float(best_active["return_2026_ytd_pct"]),
        "source_context_note": "Funding has oracle pieces but strict selector failed; 1m intrabar oracle failed.",
    }


def _render_report(summary: dict[str, Any]) -> str:
    result = summary["results"]
    decision = summary["decision"]
    original = result["original_rows"]
    original_lines = []
    for row in original:
        original_lines.append(
            f"- `{row['method']}`：通过 `{row['scenario_pass']}`，2025 `{row['return_2025_pct']:.2f}%`，"
            f"2026 YTD `{row['return_2026_ytd_pct']:.2f}%`，不合格月份 `{row['non_passing_months']}`，"
            f"最少月交易 `{row['min_monthly_orders']}`"
        )
    best_active = result["best_strict_active_balance"]
    best_oracle = result["best_main_cost_oracle_passing_row"]
    oracle_line = "无"
    if best_oracle:
        oracle_line = (
            f"手续费 `{best_oracle['round_trip_cost_pct']:.2f}%`，月交易 `{best_oracle['order_floor']}`，"
            f"月要求 `{best_oracle['monthly_requirement']}`，年门槛 `{best_oracle['annual_threshold_pct']:.0f}%`"
        )
    return f"""# 27号目标可行性审计

这不是策略，不能交易。它只回答：继续加小规则之前，原目标是不是太硬？

## 复用内容

- 复用 22号的 16/19/20/21 候选月度基础表。
- 参考 23/24 资金费率结果和 26号 1分钟内部结构结果。
- 没有新增候选规则。

## 原始目标

原始口径：开平合计 `0.2%`、每月收益 `> 0`、每月交易不少于 `10`、2025和2026 YTD 都不少于 `100%`。

{chr(10).join(original_lines)}

## 放宽后

- 严格逐月选择器通过：`{result["strict_pass_count"]}/{result["strict_scenario_count"]}`
- 看答案 oracle 通过：`{result["oracle_pass_count"]}/{result["oracle_scenario_count"]}`
- 最强可交易式严格选择器仍弱：2025 `{best_active["return_2025_pct"]:.2f}%`，2026 YTD `{best_active["return_2026_ytd_pct"]:.2f}%`
- 最宽松能通过的看答案口径：{oracle_line}

## 判断

`{decision["verdict"]}`

{decision["reason"]}

通俗说：目标放宽能让“看答案”变好，但不能让严格选择器变好。继续往免费K线小规则里加东西，意义不大。
"""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _json_ready(value: Any) -> Any:
    return probe16._json_ready(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
