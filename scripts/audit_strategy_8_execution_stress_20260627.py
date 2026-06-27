from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

import audit_strategy_5_robustness_20260627 as audit5
import audit_strategy_5b_three_way_20260627 as audit5b
import search_monthly_profit_lock_20260627 as lock_search
import search_online_expert_pool_20260627 as source_pool
import search_strategy_1_candidate_20260627 as strategy_1a
import search_strategy_1c_trend_runner_20260627 as strategy_1c


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_8_execution_stress_20260627"
BASE_COST = lock_search.COST_PER_SIDE


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    features = source_pool._add_features(source_pool._load_features(source_pool.FEATURE_FRAME))
    market = source_pool._market(features)
    candidates = audit5b._candidates(features, market)
    scenarios = _scenarios()

    stress_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []

    for candidate in candidates:
        base = candidate["simulate"](BASE_COST, 0)
        strategy_1a._assert_signal_timing(base)
        for scenario_id, description, apply in scenarios:
            stressed = apply(base)
            strategy_1a._assert_signal_timing(stressed)
            monthly = lock_search._monthly_breakdown(stressed)
            yearly = lock_search._yearly_breakdown(monthly)
            row = strategy_1c._result_row(stressed, monthly, yearly)
            stress_rows.append({"scenario_id": scenario_id, "candidate": candidate["label"], "description": description, **row})
            monthly_rows.extend(_tag_monthly(monthly, scenario_id, candidate["label"]))
            failure_rows.extend(_tag_monthly(audit5._bad_months(monthly), scenario_id, candidate["label"]))

    stress = pd.DataFrame(stress_rows)
    monthly = pd.DataFrame(monthly_rows)
    failures = pd.DataFrame(failure_rows)
    _self_check(stress, scenarios, candidates)

    stress.to_csv(OUT_DIR / "execution_stress.csv", index=False)
    monthly.to_csv(OUT_DIR / "execution_stress_monthly.csv", index=False)
    failures.to_csv(OUT_DIR / "execution_stress_failures.csv", index=False)

    summary = {
        "status": "strategy_8_execution_stress_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "does_not_overwrite": [
            "artifacts/strategy_2c_lock_cap_20260627",
            "artifacts/strategy_3_trend_coverage_20260627",
            "artifacts/strategy_4_entry_confirm_20260627",
        ],
        "checked_candidates": [item["label"] for item in candidates],
        "scenario_count": len(scenarios),
        "stress_rollup": audit5._rollup(stress),
        "failure_months": lock_search._json_ready(failures.to_dict("records")),
        "decision": _decision(stress),
        "files": {
            "execution_stress": _rel(OUT_DIR / "execution_stress.csv"),
            "execution_stress_monthly": _rel(OUT_DIR / "execution_stress_monthly.csv"),
            "execution_stress_failures": _rel(OUT_DIR / "execution_stress_failures.csv"),
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _scenarios() -> list[tuple[str, str, Callable[[pd.DataFrame], pd.DataFrame]]]:
    return [
        ("vol_slip_10pct_cap20bps", "每次调仓额外滑点 = 15m波动的10%，单边最多20bps", lambda base: _dynamic_cost(base, 0.10, 0.002)),
        ("vol_slip_20pct_cap40bps", "每次调仓额外滑点 = 15m波动的20%，单边最多40bps", lambda base: _dynamic_cost(base, 0.20, 0.004)),
        ("funding_1bp_8h", "每8小时按持仓名义扣1bp资金费", lambda base: _funding(base, 0.0001)),
        ("funding_3bp_8h", "每8小时按持仓名义扣3bp资金费", lambda base: _funding(base, 0.0003)),
        ("miss_top5pct_rebalance", "专门漏掉换手最大的5%调仓", lambda base: _miss_mask(base, _top_turnover_mask(base, 0.05))),
        ("outage_top3vol_4bars", "最大3次波动附近各停摆4根15m K线", lambda base: _miss_mask(base, _top_vol_outage_mask(base, 3, 4))),
    ]


def _dynamic_cost(equity: pd.DataFrame, factor: float, cap: float) -> pd.DataFrame:
    out = equity.copy()
    raw_return = np.log(out["close"].astype(float)).diff().fillna(0.0).to_numpy(float)
    extra = np.minimum(np.abs(raw_return) * factor, cap)
    out["strategy_log_return"] = out["active_position"].astype(float) * raw_return - out["turnover"].astype(float) * (BASE_COST + extra)
    return _finish(out)


def _funding(equity: pd.DataFrame, funding_per_8h: float) -> pd.DataFrame:
    out = equity.copy()
    raw_return = np.log(out["close"].astype(float)).diff().fillna(0.0)
    per_bar = funding_per_8h / 32.0
    out["strategy_log_return"] = (
        out["active_position"].astype(float) * raw_return
        - out["turnover"].astype(float) * BASE_COST
        - out["active_position"].astype(float).abs() * per_bar
    )
    return _finish(out)


def _miss_mask(equity: pd.DataFrame, miss_mask: np.ndarray) -> pd.DataFrame:
    raw_return = np.log(equity["close"].astype(float)).diff().fillna(0.0).to_numpy(float)
    desired = equity["position"].to_numpy(float)
    executed = 0.0
    previous_side = 0
    rows = []
    for index, row in equity.reset_index(drop=True).iterrows():
        before = executed
        if not miss_mask[index]:
            executed = float(desired[index])
        side = 0 if abs(executed) < 1e-12 else int(np.sign(executed))
        turnover = abs(executed - before)
        order_count = abs(side - previous_side)
        rows.append(
            {
                **row.to_dict(),
                "position": executed,
                "active_position": before,
                "turnover": turnover,
                "order_count": order_count,
                "strategy_log_return": before * raw_return[index] - turnover * BASE_COST,
                "guard_reason": "execution_stress_miss" if miss_mask[index] else row.get("guard_reason", "main"),
            }
        )
        previous_side = side
    return _finish(pd.DataFrame(rows))


def _top_turnover_mask(equity: pd.DataFrame, fraction: float) -> np.ndarray:
    turnover = equity["turnover"].to_numpy(float)
    changed = np.flatnonzero(turnover > 1e-12)
    mask = np.zeros(len(equity), dtype=bool)
    count = max(1, int(np.ceil(len(changed) * fraction)))
    if len(changed):
        mask[changed[np.argsort(turnover[changed])[-count:]]] = True
    return mask


def _top_vol_outage_mask(equity: pd.DataFrame, top_n: int, bars: int) -> np.ndarray:
    raw = np.abs(np.log(equity["close"].astype(float)).diff().fillna(0.0).to_numpy(float))
    mask = np.zeros(len(equity), dtype=bool)
    for index in np.argsort(raw)[-top_n:]:
        mask[index : min(len(mask), index + bars)] = True
    return mask


def _finish(out: pd.DataFrame) -> pd.DataFrame:
    out["equity"] = np.exp(out["strategy_log_return"].cumsum())
    out["drawdown"] = out["equity"] / out["equity"].cummax() - 1.0
    return out


def _tag_monthly(monthly: pd.DataFrame, scenario_id: str, candidate: str) -> list[dict[str, Any]]:
    rows = monthly.to_dict("records")
    for row in rows:
        row["scenario_id"] = scenario_id
        row["candidate"] = candidate
    return rows


def _decision(stress: pd.DataFrame) -> dict[str, Any]:
    rollup = audit5._rollup(stress)
    best = sorted(rollup, key=lambda row: (row["hard_pass_scenarios"], row["worst_min_monthly_return_pct"]), reverse=True)[0]
    return {
        "best_execution_stress_candidate": best["candidate"],
        "promote_strategy": False,
        "reason": "这是执行层压力审计，不是新策略；用于找真实交易摩擦下谁更抗打。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# 8号执行压力审计",
        "",
        "这不是新策略，只检查 2C、3号、4号在更坏执行条件下是否容易坏。",
        "",
        "## 压力项",
        "",
        "- 波动越大滑点越大：两档。",
        "- 持仓资金费：每8小时 1bp / 3bp 两档。",
        "- 专门漏掉换手最大的 5% 调仓。",
        "- 最大 3 次波动附近各停摆 4 根 15m K线。",
        "",
        "## 汇总",
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
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"- 执行压力下暂时最抗打：`{summary['decision']['best_execution_stress_candidate']}`。",
            "- 这不改变策略规则，也不代表可以实盘。",
            "- 如果某候选在这里失败，要先看失败月份，不要马上补规则。",
        ]
    )
    return "\n".join(lines) + "\n"


def _self_check(stress: pd.DataFrame, scenarios: list[Any], candidates: list[dict[str, Any]]) -> None:
    assert len(stress) == len(scenarios) * len(candidates)
    assert set(stress["candidate"]) == {item["label"] for item in candidates}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
