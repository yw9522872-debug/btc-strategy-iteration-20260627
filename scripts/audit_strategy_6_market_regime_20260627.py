from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE_5B = ROOT / "artifacts" / "strategy_5b_three_way_audit_20260627"
OUT_DIR = ROOT / "artifacts" / "strategy_6_market_regime_audit_20260627"
LABEL_RULE_VERSION = "5b_month_return_5pct_shock_15pct"

CANDIDATE_MONTHLY = {
    "2C": ROOT / "artifacts" / "strategy_2c_lock_cap_20260627" / "strategy_2c_monthly.csv",
    "3": ROOT / "artifacts" / "strategy_3_trend_coverage_20260627" / "strategy_3_monthly.csv",
    "4": ROOT / "artifacts" / "strategy_4_entry_confirm_20260627" / "strategy_4_monthly.csv",
}
CANDIDATE_EQUITY = {
    "2C": ROOT / "artifacts" / "strategy_2c_lock_cap_20260627" / "strategy_2c_equity.csv",
    "3": ROOT / "artifacts" / "strategy_3_trend_coverage_20260627" / "strategy_3_equity.csv",
    "4": ROOT / "artifacts" / "strategy_4_entry_confirm_20260627" / "strategy_4_equity.csv",
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    market_state = _load_market_state()
    candidate_state = _load_candidate_state(market_state)
    failure_map = _load_failure_map(market_state)
    state_summary = _state_summary(candidate_state)
    failure_summary = _failure_summary(failure_map)
    threshold_sensitivity = _threshold_sensitivity(market_state)
    weakness_check = _weakness_check(failure_map)

    market_state.to_csv(OUT_DIR / "market_state_monthly.csv", index=False)
    candidate_state.to_csv(OUT_DIR / "candidate_state_monthly.csv", index=False)
    failure_map.to_csv(OUT_DIR / "state_failure_map.csv", index=False)
    state_summary.to_csv(OUT_DIR / "candidate_state_summary.csv", index=False)
    failure_summary.to_csv(OUT_DIR / "state_failure_summary.csv", index=False)
    threshold_sensitivity.to_csv(OUT_DIR / "state_threshold_sensitivity.csv", index=False)

    summary = {
        "status": "strategy_6_market_regime_audit_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "does_not_overwrite": [
            "artifacts/strategy_2c_lock_cap_20260627",
            "artifacts/strategy_3_trend_coverage_20260627",
            "artifacts/strategy_4_entry_confirm_20260627",
        ],
        "no_parameter_search": True,
        "state_rules_fixed_before_scoring": True,
        "uses_posthoc_month_labels": True,
        "label_rule_version": LABEL_RULE_VERSION,
        "pass_fail_standard": "base_month_pass = strategy_return_pct > 0 and strategy_orders >= 10; stress failure reasons are losing_month, orders_below_10, or both.",
        "risk_flags": {
            "posthoc_state_label": True,
            "small_sample_17_complete_months": True,
            "not_live_signal": True,
            "not_live_guarantee": True,
            "candidate_overfit_risk": True,
            "candidate_family_non_independence": True,
            "partial_2026_06_month": True,
        },
        "data_end_utc": str(market_state["data_end_utc"].iloc[0]),
        "partial_months": _records(market_state.loc[market_state["partial_month"], ["month", "market_regime"]]),
        "state_counts": _records(
            market_state.groupby("market_regime", as_index=False).agg(
                months=("month", "size"),
                complete_months=("complete_month", "sum"),
                partial_months=("partial_month", "sum"),
            )
        ),
        "complete_month_state_counts": _records(
            market_state.loc[market_state["complete_month"]].groupby("market_regime", as_index=False).size()
        ),
        "shock_counts": _records(market_state.groupby(["market_regime", "shock_month"], as_index=False).size()),
        "candidate_state_summary": _records(state_summary),
        "stress_failure_summary": _records(failure_summary),
        "state_threshold_sensitivity": _records(threshold_sensitivity),
        "weakness_check": weakness_check,
        "decision": {
            "promote_to_strategy": False,
            "reason": "6号只是历史体检表；市场状态是整个月结束后才知道的事后标签，不能当实时交易信号。",
        },
        "input_files": {
            "market_state_source": _rel(BASE_5B / "regime_base_monthly.csv"),
            "cost_delay_failures": _rel(BASE_5B / "failure_months.csv"),
            "order_miss_monthly": _rel(BASE_5B / "order_miss_monthly.csv"),
            "order_miss_stress": _rel(BASE_5B / "order_miss_stress.csv"),
            "candidate_monthly": {name: _rel(path) for name, path in CANDIDATE_MONTHLY.items()},
        },
        "files": {
            "market_state_monthly": _rel(OUT_DIR / "market_state_monthly.csv"),
            "candidate_state_monthly": _rel(OUT_DIR / "candidate_state_monthly.csv"),
            "state_failure_map": _rel(OUT_DIR / "state_failure_map.csv"),
            "candidate_state_summary": _rel(OUT_DIR / "candidate_state_summary.csv"),
            "state_failure_summary": _rel(OUT_DIR / "state_failure_summary.csv"),
            "state_threshold_sensitivity": _rel(OUT_DIR / "state_threshold_sensitivity.csv"),
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
        },
    }

    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_market_state() -> pd.DataFrame:
    source = pd.read_csv(BASE_5B / "regime_base_monthly.csv")
    columns = [
        "month",
        "market_return_pct",
        "market_max_drawdown_pct",
        "market_max_runup_pct",
        "market_regime",
        "shock_month",
    ]
    market = source[columns].drop_duplicates("month").sort_values("month").reset_index(drop=True)
    market["shock_month"] = market["shock_month"].map(_to_bool)
    data_end = _shared_data_end()
    month_start = pd.to_datetime(market["month"] + "-01", utc=True)
    complete_cutoff = month_start + pd.offsets.MonthBegin(1) - pd.Timedelta(minutes=15)
    market["complete_month"] = complete_cutoff <= data_end
    market["partial_month"] = ~market["complete_month"]
    market["data_end_utc"] = data_end.isoformat()
    market["label_rule_version"] = LABEL_RULE_VERSION
    market["is_posthoc_label"] = True
    return market[
        [
            "month",
            "market_return_pct",
            "market_max_drawdown_pct",
            "market_max_runup_pct",
            "market_regime",
            "shock_month",
            "complete_month",
            "partial_month",
            "data_end_utc",
            "label_rule_version",
            "is_posthoc_label",
        ]
    ]


def _load_candidate_state(market_state: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for candidate, path in CANDIDATE_MONTHLY.items():
        frame = pd.read_csv(path)
        frame["candidate"] = candidate
        frame = frame.rename(
            columns={
                "return_pct": "strategy_return_pct",
                "orders": "strategy_orders",
                "drawdown_pct": "strategy_drawdown_pct",
            }
        )
        merged = frame.merge(
            market_state[["month", "market_regime", "shock_month", "complete_month", "partial_month"]],
            on="month",
            how="left",
        )
        merged["base_month_pass"] = (merged["strategy_return_pct"] > 0.0) & (merged["strategy_orders"] >= 10)
        rows.append(
            merged[
                [
                    "candidate",
                    "month",
                    "market_regime",
                    "shock_month",
                    "complete_month",
                    "partial_month",
                    "strategy_return_pct",
                    "strategy_orders",
                    "strategy_drawdown_pct",
                    "base_month_pass",
                ]
            ]
        )
    return pd.concat(rows, ignore_index=True).sort_values(["candidate", "month"]).reset_index(drop=True)


def _load_failure_map(market_state: pd.DataFrame) -> pd.DataFrame:
    cost_delay = pd.read_csv(BASE_5B / "failure_months.csv")
    cost_delay["test_family"] = "cost_delay"
    cost_delay["miss_rate"] = pd.NA
    cost_delay["seed"] = pd.NA

    order_miss = pd.read_csv(BASE_5B / "order_miss_monthly.csv")
    order_meta = pd.read_csv(BASE_5B / "order_miss_stress.csv")[
        ["scenario_id", "cost_per_side", "round_trip_cost"]
    ].drop_duplicates("scenario_id")
    order_miss = order_miss.merge(order_meta, on="scenario_id", how="left")
    order_miss = order_miss[(order_miss["return_pct"] <= 0.0) | (order_miss["orders"] < 10)].copy()
    order_miss["test_family"] = "order_miss"
    order_miss["extra_delay_bars"] = pd.NA

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        combined = pd.concat([cost_delay, order_miss], ignore_index=True, sort=False)
    if combined.empty:
        return pd.DataFrame(
            columns=[
                "test_family",
                "candidate",
                "scenario_id",
                "month",
                "market_regime",
                "shock_month",
                "complete_month",
                "partial_month",
                "failure_reason",
                "return_pct",
                "orders",
                "cost_per_side",
                "round_trip_cost",
                "extra_delay_bars",
                "miss_rate",
                "seed",
            ]
        )

    combined["failure_reason"] = combined.apply(_failure_reason, axis=1)
    combined = combined.merge(
        market_state[["month", "market_regime", "shock_month", "complete_month", "partial_month"]],
        on="month",
        how="left",
    )
    columns = [
        "test_family",
        "candidate",
        "scenario_id",
        "month",
        "market_regime",
        "shock_month",
        "complete_month",
        "partial_month",
        "failure_reason",
        "return_pct",
        "orders",
        "cost_per_side",
        "round_trip_cost",
        "extra_delay_bars",
        "miss_rate",
        "seed",
    ]
    return combined[columns].sort_values(["test_family", "candidate", "scenario_id", "month"]).reset_index(drop=True)


def _state_summary(candidate_state: pd.DataFrame) -> pd.DataFrame:
    grouped = candidate_state.groupby(["candidate", "market_regime"], as_index=False).agg(
        months=("month", "nunique"),
        complete_months=("complete_month", "sum"),
        partial_months=("partial_month", "sum"),
        pass_months=("base_month_pass", "sum"),
        avg_return_pct=("strategy_return_pct", "mean"),
        min_return_pct=("strategy_return_pct", "min"),
        avg_orders=("strategy_orders", "mean"),
        min_orders=("strategy_orders", "min"),
        worst_drawdown_pct=("strategy_drawdown_pct", "min"),
    )
    grouped["fail_months"] = grouped["months"] - grouped["pass_months"]
    grouped["sample_note"] = grouped["complete_months"].map(
        lambda months: "sample_ok_for_rough_read" if months >= 6 else "sample_too_small"
    )
    return grouped.sort_values(["candidate", "market_regime"]).reset_index(drop=True)


def _threshold_sensitivity(market_state: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for return_threshold in [3.0, 5.0, 7.0]:
        for shock_threshold in [10.0, 15.0, 20.0]:
            frame = market_state.copy()
            frame["test_regime"] = "sideways"
            frame.loc[frame["market_return_pct"] >= return_threshold, "test_regime"] = "up"
            frame.loc[frame["market_return_pct"] <= -return_threshold, "test_regime"] = "down"
            frame["test_shock_month"] = (
                frame["market_max_drawdown_pct"].abs().ge(shock_threshold)
                | frame["market_max_runup_pct"].abs().ge(shock_threshold)
            )
            for regime, group in frame.groupby("test_regime", sort=True):
                rows.append(
                    {
                        "return_threshold_pct": return_threshold,
                        "shock_threshold_pct": shock_threshold,
                        "market_regime": regime,
                        "months": int(len(group)),
                        "complete_months": int(group["complete_month"].sum()),
                        "shock_months": int(group["test_shock_month"].sum()),
                    }
                )
    return pd.DataFrame(rows)


def _failure_summary(failure_map: pd.DataFrame) -> pd.DataFrame:
    if failure_map.empty:
        return pd.DataFrame(
            columns=[
                "test_family",
                "candidate",
                "market_regime",
                "failures",
                "unique_scenarios",
                "unique_months",
                "losing_month",
                "orders_below_10",
                "both",
            ]
        )
    pivot = pd.crosstab(
        [failure_map["test_family"], failure_map["candidate"], failure_map["market_regime"]],
        failure_map["failure_reason"],
    ).reset_index()
    for column in ["losing_month", "orders_below_10", "both"]:
        if column not in pivot.columns:
            pivot[column] = 0
    totals = failure_map.groupby(["test_family", "candidate", "market_regime"], as_index=False).agg(
        failures=("scenario_id", "size"),
        unique_scenarios=("scenario_id", "nunique"),
        unique_months=("month", "nunique"),
    )
    return totals.merge(pivot, on=["test_family", "candidate", "market_regime"], how="left").sort_values(
        ["test_family", "candidate", "market_regime"]
    )


def _weakness_check(failure_map: pd.DataFrame) -> dict[str, Any]:
    if failure_map.empty:
        return {
            "qualified_weakness_found": False,
            "reason": "No stress failure rows found.",
            "rule": "A confirmed weakness needs complete months only, at least 2 distinct months, both stress families, and each family must affect at least 2 candidates in the same market regime.",
        }

    eligible_failures = failure_map.loc[~failure_map["partial_month"].fillna(False)].copy()
    rows = []
    for regime, group in eligible_failures.groupby("market_regime"):
        families = sorted(group["test_family"].dropna().unique().tolist())
        candidates = sorted(group["candidate"].dropna().unique().tolist())
        family_details = []
        for family, family_group in group.groupby("test_family"):
            family_candidates = sorted(family_group["candidate"].dropna().unique().tolist())
            family_details.append(
                {
                    "test_family": family,
                    "candidate_count": len(family_candidates),
                    "unique_scenarios": int(family_group["scenario_id"].nunique()),
                    "unique_months": int(family_group["month"].nunique()),
                    "candidates": family_candidates,
                }
            )
        has_both_families = {"cost_delay", "order_miss"}.issubset(set(families))
        each_family_broad = has_both_families and all(detail["candidate_count"] >= 2 for detail in family_details)
        enough_months = group["month"].nunique() >= 2
        rows.append(
            {
                "market_regime": regime,
                "failures": int(len(group)),
                "candidate_count": len(candidates),
                "test_family_count": len(families),
                "candidates": candidates,
                "test_families": families,
                "family_details": family_details,
                "qualified": len(candidates) >= 2 and each_family_broad and enough_months,
            }
        )
    qualified = [row for row in rows if row["qualified"]]
    return {
        "qualified_weakness_found": bool(qualified),
        "qualified_regimes": qualified,
        "all_regime_failure_counts": rows,
        "conservative_observation": _conservative_observation(failure_map),
        "rule": "A confirmed weakness needs complete months only, at least 2 distinct months, both stress families, and each family must affect at least 2 candidates in the same market regime.",
    }


def _conservative_observation(failure_map: pd.DataFrame) -> list[str]:
    observations = []
    cost_down = failure_map[
        (failure_map["test_family"] == "cost_delay") & (failure_map["market_regime"] == "down")
    ]
    if cost_down["candidate"].nunique() >= 2:
        observations.append("手续费/延迟压力的亏损主要集中在下跌月，尤其是 2026-01")
    miss_sideways = failure_map[
        (failure_map["test_family"] == "order_miss") & (failure_map["market_regime"] == "sideways")
    ]
    if miss_sideways["candidate"].nunique() >= 2:
        observations.append("漏成交压力的问题主要集中在震荡月，尤其是 2025-03")
    up_cost = failure_map[
        (failure_map["test_family"] == "cost_delay") & (failure_map["market_regime"] == "up")
    ]
    if up_cost["candidate"].nunique() >= 2:
        observations.append("上涨月也有手续费压力失败，但目前只来自一类压力，证据不够")
    return observations


def _failure_reason(row: pd.Series) -> str:
    losing = float(row["return_pct"]) <= 0.0
    low_orders = int(row["orders"]) < 10
    if losing and low_orders:
        return "both"
    if low_orders:
        return "orders_below_10"
    return "losing_month"


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# 6号市场状态体检表",
        "",
        "这不是新策略，也不是实盘信号。它只回答一个问题：2C、3号、4号的历史弱点，是否集中在某类市场月份。",
        "",
        "## 状态口径",
        "",
        "- 月涨幅 >= +5%：上涨月。",
        "- 月跌幅 <= -5%：下跌月。",
        "- 中间：震荡月。",
        "- 月内最大回撤 >= 15% 或最大上涨 >= 15%：冲击月。",
        "- 这些都是整个月结束后才知道的事后标签，不能在月初拿来交易。",
        f"- 当前数据到 `{summary['data_end_utc']}`；`2026-06` 是未完整月份，所以完整月统计不能说成 18 个整月。",
        "",
        "## 市场月份数量",
        "",
        "| 市场状态 | 总月数 | 完整月 | 未完整月 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in summary["state_counts"]:
        lines.append(
            f"| {row['market_regime']} | {row['months']} | {row['complete_months']} | {row['partial_months']} |"
        )

    lines.extend(
        [
            "",
            "## 候选按状态表现",
            "",
            "| 候选 | 状态 | 月数 | 完整月 | 未完整月 | 通过月数 | 最差收益 | 最低交易数 | 最差回撤 |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in summary["candidate_state_summary"]:
        lines.append(
            f"| {row['candidate']} | {row['market_regime']} | {row['months']} | {row['complete_months']} | "
            f"{row['partial_months']} | {row['pass_months']} | "
            f"{row['min_return_pct']:.2f} | {row['min_orders']} | {row['worst_drawdown_pct']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## 压力失败集中情况",
            "",
            "| 压力类型 | 候选 | 状态 | 失败行数 | 场景数 | 月数 | 亏损月 | 交易不足 | 两者都有 |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in summary["stress_failure_summary"]:
        lines.append(
            f"| {row['test_family']} | {row['candidate']} | {row['market_regime']} | {row['failures']} | "
            f"{row['unique_scenarios']} | {row['unique_months']} | {row['losing_month']} | "
            f"{row['orders_below_10']} | {row['both']} |"
        )

    weakness = summary["weakness_check"]
    if weakness["qualified_weakness_found"]:
        regimes = ", ".join(row["market_regime"] for row in weakness["qualified_regimes"])
        weakness_text = f"压力失败在这些状态有较明显集中：{regimes}。"
    else:
        weakness_text = "没有达到“至少两个候选、两类压力都集中”的弱点确认标准。"
    observations = weakness.get("conservative_observation") or ["暂无额外集中线索。"]

    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"- 是否升级成策略：`{summary['decision']['promote_to_strategy']}`。",
            f"- 历史弱点判断：{weakness_text}",
            f"- 保守观察：{'；'.join(observations)}。",
            "- 本审计仍然只看 2025/2026，完整月份只有 17 个，样本很少。",
            "- 2C、3号、4号来自同一策略家族，不能当成三个完全独立证据。",
            "- 2C、3号、4号本身都有事后研究和过拟合风险。",
            "- 6号不能证明未来有效，也不能用于实盘下单建议。",
        ]
    )
    return "\n".join(lines) + "\n"


def _shared_data_end() -> pd.Timestamp:
    ends = []
    for path in CANDIDATE_EQUITY.values():
        timestamps = pd.read_csv(path, usecols=["timestamp"], parse_dates=["timestamp"])
        ends.append(pd.to_datetime(timestamps["timestamp"], utc=True).max())
    return min(ends)


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return _json_ready(frame.to_dict("records"))


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
