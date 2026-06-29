from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OLD_ROOT = Path(r"C:\Users\WHR\Documents\BTC多因子研究_20260626")

OUT_DIR = ROOT / "artifacts" / "strategy_35_old_btc_3m_inspiration_review_20260629"

OLD_BEAM_DIR = OLD_ROOT / "artifacts" / "btc_ultimate_capital_aware_beam_search_20260626"
OLD_MTM_DIR = OLD_ROOT / "artifacts" / "btc_ultimate_candidate_mtm_validation_20260626"
OLD_PRE2025_DIR = OLD_ROOT / "artifacts" / "btc_pre2025_locked_rule_forward_20260627"
OLD_ML_DIR = OLD_ROOT / "artifacts" / "btc_pre2025_locked_rule_ml_router_20260627"
OLD_FEATURE_DIR = OLD_ROOT / "artifacts" / "btc_multitimeframe_feature_store_20260626"
OLD_LABEL_DIR = OLD_ROOT / "artifacts" / "btc_event_label_store_20260626"

CURRENT_33_DIR = ROOT / "artifacts" / "strategy_33_multisymbol_free_futures_strict_selector_20260629"
CURRENT_34_DIR = ROOT / "artifacts" / "strategy_34_multisymbol_failure_root_cause_20260629"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    old = _load_old_project()
    current = _load_current_project()
    summary = _build_summary(old, current)

    files = {
        "summary": OUT_DIR / "summary.json",
        "report": OUT_DIR / "report.md",
        "old_best_rules": OUT_DIR / "old_project_best_7_rules.csv",
        "comparison_metrics": OUT_DIR / "comparison_metrics.csv",
    }

    files["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    files["report"].write_text(_report(summary), encoding="utf-8")
    old["best_rules"].to_csv(files["old_best_rules"], index=False, encoding="utf-8-sig")
    _comparison_table(summary).to_csv(files["comparison_metrics"], index=False, encoding="utf-8-sig")

    _self_check(summary, files)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "strategy_id": summary["strategy_id"],
                "verdict": summary["decision"]["verdict"],
                "report": str(files["report"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _load_old_project() -> dict[str, Any]:
    _require_files(
        [
            OLD_BEAM_DIR / "data_checks.json",
            OLD_BEAM_DIR / "exact_replay_scores.csv",
            OLD_BEAM_DIR / "candidate_pool.csv",
            OLD_BEAM_DIR / "best_exact_rules.csv",
            OLD_MTM_DIR / "summary.csv",
            OLD_PRE2025_DIR / "forward_scores.csv",
            OLD_ML_DIR / "scores.csv",
            OLD_FEATURE_DIR / "feature_manifest.json",
            OLD_LABEL_DIR / "label_manifest.json",
        ]
    )

    beam_checks = _read_json(OLD_BEAM_DIR / "data_checks.json")
    exact_scores = pd.read_csv(OLD_BEAM_DIR / "exact_replay_scores.csv")
    candidate_pool = pd.read_csv(OLD_BEAM_DIR / "candidate_pool.csv")
    best_rules = pd.read_csv(OLD_BEAM_DIR / "best_exact_rules.csv")
    mtm_summary = pd.read_csv(OLD_MTM_DIR / "summary.csv")
    pre2025_scores = pd.read_csv(OLD_PRE2025_DIR / "forward_scores.csv")
    ml_scores = pd.read_csv(OLD_ML_DIR / "scores.csv")
    feature_manifest = _read_json(OLD_FEATURE_DIR / "feature_manifest.json")
    label_manifest = _read_json(OLD_LABEL_DIR / "label_manifest.json")

    exact_pass_count = int(exact_scores["hard_task_pass"].astype(bool).sum())
    best_exact = (
        exact_scores.loc[exact_scores["hard_task_pass"].astype(bool)]
        .sort_values(["gross_cap", "min_year_bps", "net_sum_bps"], ascending=[True, False, False])
        .iloc[0]
        .to_dict()
    )

    task_mtm = mtm_summary.loc[mtm_summary["window"] == "task_2025_2026"].iloc[0].to_dict()
    stress_2024 = mtm_summary.loc[mtm_summary["window"] == "stress_2024_fixed_rules"].iloc[0].to_dict()

    pre2025_pass_count = int(pre2025_scores["test_hard_pass"].astype(bool).sum())
    best_pre2025 = (
        pre2025_scores.sort_values(
            ["test_min_year_bps", "test_positive_months", "test_min_month_bps"],
            ascending=[False, False, False],
        )
        .iloc[0]
        .to_dict()
    )

    ml_pass_count = int(ml_scores["hard_pass"].astype(bool).sum())
    best_ml = (
        ml_scores.sort_values(["min_year_bps", "positive_months", "min_month_bps"], ascending=[False, False, False])
        .iloc[0]
        .to_dict()
    )

    feature_quality = feature_manifest.get("quality", {})
    label_quality = label_manifest.get("quality", {})

    return {
        "beam_checks": beam_checks,
        "candidate_pool_rows": int(len(candidate_pool)),
        "candidate_pool_unique_features": int(candidate_pool["feature"].nunique()),
        "candidate_pool_horizons": [int(x) for x in sorted(candidate_pool["horizon"].unique().tolist())],
        "candidate_pool_sides": {str(k): int(v) for k, v in candidate_pool["side"].value_counts().to_dict().items()},
        "exact_pass_count": exact_pass_count,
        "best_exact": best_exact,
        "best_rules": best_rules,
        "task_mtm": task_mtm,
        "stress_2024": stress_2024,
        "pre2025_pass_count": pre2025_pass_count,
        "best_pre2025": best_pre2025,
        "ml_pass_count": ml_pass_count,
        "best_ml": best_ml,
        "feature_store": {
            "rows": int(feature_manifest.get("rows", 0)),
            "feature_count": int(feature_manifest.get("feature_count", 0)),
            "causality_violations": int(feature_quality.get("causality_violations", 0)),
        },
        "label_store": {
            "rows": int(label_manifest.get("rows", 0)),
            "label_count": int(label_manifest.get("label_count", 0)),
            "entry_policy": label_manifest.get("label_policy", {}).get("entry_time"),
            "entry_time_lte_decision_time_violations": int(
                label_quality.get("entry_time_lte_decision_time_violations", 0)
            ),
            "dropped_tail_rows_for_future_horizon": int(label_quality.get("dropped_tail_rows_for_future_horizon", 0)),
        },
    }


def _load_current_project() -> dict[str, Any]:
    _require_files([CURRENT_33_DIR / "summary.json", CURRENT_34_DIR / "summary.json"])
    s33 = _read_json(CURRENT_33_DIR / "summary.json")
    s34 = _read_json(CURRENT_34_DIR / "summary.json")
    return {
        "strategy_33": {
            "candidate_count": int(s33["candidate_grid"]["candidate_count"]),
            "static_hard_pass_original_target_count": int(s33["static_hard_pass_original_target_count"]),
            "oracle_order10_passes": bool(s33["best_order10_oracle"]["hard_pass_original_2025_2026_ytd"]),
            "best_selector": s33["best_selector"],
            "decision": s33["decision"],
        },
        "strategy_34": {
            "headline": s34["headline"],
            "selection_gap": s34["selection_gap"],
            "strict_selector_summary": s34["strict_selector_summary"],
            "previous_oracle_follow_summary": s34["previous_oracle_follow_summary"],
            "decision": s34["decision"],
        },
    }


def _build_summary(old: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    best_rules = old["best_rules"]
    selected_features = best_rules["feature"].astype(str).tolist()

    return {
        "status": "strategy_35_old_btc_3m_inspiration_review_ready",
        "strategy_id": "strategy_35_old_btc_3m_inspiration_review_20260629",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "does_not_overwrite_existing_strategies": True,
        "source_project": str(OLD_ROOT),
        "purpose": "复盘旧 BTC 3m 多因子项目，提炼能借鉴的框架，避免把样本内高收益误当成可交易结论。",
        "old_project_in_sample_success": {
            "window": "2025-2026 sample-in",
            "selection_warning": old["beam_checks"].get("warning"),
            "candidate_rules": old["beam_checks"].get("candidate_rules"),
            "candidate_pool_rows": old["candidate_pool_rows"],
            "candidate_pool_unique_features": old["candidate_pool_unique_features"],
            "candidate_pool_horizons": old["candidate_pool_horizons"],
            "candidate_pool_sides": old["candidate_pool_sides"],
            "exact_pass_rows": old["exact_pass_count"],
            "best_combo_id": _to_int(old["best_exact"].get("combo_id")),
            "best_candidate_ids": old["best_exact"].get("candidate_ids"),
            "best_rule_count": _to_int(old["best_exact"].get("rule_count")),
            "best_gross_cap": _to_float(old["best_exact"].get("gross_cap")),
            "best_weight_per_lot": _to_float(old["best_exact"].get("weight_per_lot")),
            "trade_count": _to_int(old["best_exact"].get("trade_count")),
            "net_2025_bps": _to_float(old["best_exact"].get("net_2025_bps")),
            "net_2026_bps": _to_float(old["best_exact"].get("net_2026_bps")),
            "min_month_net_bps": _to_float(old["best_exact"].get("min_month_net_bps")),
            "min_month_trades": _to_int(old["best_exact"].get("min_month_trades")),
            "positive_months": _to_int(old["best_exact"].get("positive_months")),
            "selected_features": selected_features,
        },
        "old_project_accounting_validation": {
            "label_price_diff_max_bps": _to_float(old["task_mtm"].get("max_abs_label_price_net_diff_bps")),
            "task_mtm_max_drawdown_bps": _to_float(old["task_mtm"].get("mtm_max_drawdown_bps")),
            "task_max_gross_exposure": _to_float(old["task_mtm"].get("max_gross_exposure")),
            "task_max_abs_net_exposure": _to_float(old["task_mtm"].get("max_abs_net_exposure")),
            "stress_2024_net_bps": _to_float(old["stress_2024"].get("net_2024_bps")),
            "stress_2024_positive_months": _to_int(old["stress_2024"].get("positive_months")),
            "stress_2024_months": _to_int(old["stress_2024"].get("months")),
            "stress_2024_mtm_max_drawdown_bps": _to_float(old["stress_2024"].get("mtm_max_drawdown_bps")),
        },
        "old_project_no_future_checks": {
            "feature_rows": old["feature_store"]["rows"],
            "feature_count": old["feature_store"]["feature_count"],
            "feature_causality_violations": old["feature_store"]["causality_violations"],
            "label_rows": old["label_store"]["rows"],
            "label_count": old["label_store"]["label_count"],
            "entry_policy": old["label_store"]["entry_policy"],
            "entry_time_lte_decision_time_violations": old["label_store"]["entry_time_lte_decision_time_violations"],
            "dropped_tail_rows_for_future_horizon": old["label_store"]["dropped_tail_rows_for_future_horizon"],
        },
        "old_project_out_of_sample_failure": {
            "pre2025_locked_pass_rows": old["pre2025_pass_count"],
            "best_pre2025_locked": {
                "test_net_2025_bps": _to_float(old["best_pre2025"].get("test_net_2025_bps")),
                "test_net_2026_bps": _to_float(old["best_pre2025"].get("test_net_2026_bps")),
                "test_min_year_bps": _to_float(old["best_pre2025"].get("test_min_year_bps")),
                "test_min_month_bps": _to_float(old["best_pre2025"].get("test_min_month_bps")),
                "test_min_month_trades": _to_int(old["best_pre2025"].get("test_min_month_trades")),
                "test_positive_months": _to_int(old["best_pre2025"].get("test_positive_months")),
                "test_months": _to_int(old["best_pre2025"].get("test_months")),
                "test_hard_pass": bool(old["best_pre2025"].get("test_hard_pass")),
            },
            "pre2025_ml_router_pass_rows": old["ml_pass_count"],
            "best_pre2025_ml_router": {
                "config_id": old["best_ml"].get("config_id"),
                "gross_cap": _to_float(old["best_ml"].get("gross_cap")),
                "net_2025_bps": _to_float(old["best_ml"].get("net_2025_bps")),
                "net_2026_bps": _to_float(old["best_ml"].get("net_2026_bps")),
                "min_year_bps": _to_float(old["best_ml"].get("min_year_bps")),
                "min_month_bps": _to_float(old["best_ml"].get("min_month_bps")),
                "min_month_trades": _to_int(old["best_ml"].get("min_month_trades")),
                "positive_months": _to_int(old["best_ml"].get("positive_months")),
                "months": _to_int(old["best_ml"].get("months")),
                "hard_pass": bool(old["best_ml"].get("hard_pass")),
            },
        },
        "current_project_context": current,
        "inspiration": {
            "worth_borrowing": [
                "用多周期 3m/15m/1h/4h 特征和 funding/premium 可用时间约束，而不是只扫单一 BTC 3m 小规则。",
                "把许多弱事件组成事件池，再用资金占用、最大暴露和逐 K 盯市来重放。",
                "先证明选择器能提前选规则，再谈收益；看答案 oracle 只能说明市场里有碎片机会。",
            ],
            "do_not_borrow": [
                "不要照搬旧项目 7 条规则、阈值和 10x 毛暴露。",
                "不要把 2025-2026 样本内 beam search 结果说成样本外策略。",
                "不要因为旧项目有高收益表格，就跳过 2024 压力、pre-2025 锁参和 walk-forward 检查。",
            ],
        },
        "decision": {
            "verdict": "OLD_BTC_3M_GIVES_FRAMEWORK_NOT_DEPLOYABLE_RULES",
            "promote_strategy": False,
            "reason": "旧项目证明更丰富的事件池和资金重放能拼出样本内高收益，但 2024 压力和 pre-2025 锁参都失败，不能直接交易。",
            "next_step": "36号已先用33号候选做便宜组合检查且失败；若继续，另起37号做真正新的3m/多周期事件池严格走步选择器上限审计，只借框架，不借旧参数。",
        },
    }


def _report(summary: dict[str, Any]) -> str:
    old = summary["old_project_in_sample_success"]
    acc = summary["old_project_accounting_validation"]
    no_future = summary["old_project_no_future_checks"]
    fail = summary["old_project_out_of_sample_failure"]
    current_33 = summary["current_project_context"]["strategy_33"]
    current_34 = summary["current_project_context"]["strategy_34"]

    lines = [
        "# Strategy 35 Old BTC 3m Inspiration Review 20260629",
        "",
        "## Plain Conclusion",
        "",
        "- 这一步只做研究和复盘，不碰实盘、不读密钥、不下单。",
        "- 我查到的旧项目保存结果里，确实有一条 2025-2026 样本内高收益线；但它是用 2025-2026 标签挑出来的，不是样本外证明。",
        f"- 旧项目样本内最佳：2025 `{_bps_to_pct(old['net_2025_bps']):.2f}%`，2026 YTD `{_bps_to_pct(old['net_2026_bps']):.2f}%`，18个月全正，最少月交易 `{old['min_month_trades']}`。",
        f"- 旧项目会计验证：标签收益和独立 3m 价格重放差异 `{acc['label_price_diff_max_bps']:.6g}` bps；这说明账算得对，但不代表选参不看未来。",
        f"- 同一组规则压到 2024：总收益 `{_bps_to_pct(acc['stress_2024_net_bps']):.2f}%`，正收益月份 `{acc['stress_2024_positive_months']}/{acc['stress_2024_months']}`，所以不能直接照搬。",
        f"- pre-2025 锁参再测 2025-2026：通过行数 `{fail['pre2025_locked_pass_rows']}`；简单机器学习路由通过行数 `{fail['pre2025_ml_router_pass_rows']}`。",
        "- 结论：旧项目给我们的不是现成赚钱参数，而是一个更好的研究框架。",
        "",
        "## What Was Different",
        "",
        f"- 旧项目候选池：`{old['candidate_pool_rows']}` 条规则，`{old['candidate_pool_unique_features']}` 个特征，持仓周期 `{old['candidate_pool_horizons']}` 根3m K线。",
        f"- 当前32号 BTC 3m 只是单币小规则上限；旧项目用的是多周期、多特征、事件池和 beam search 组合。",
        f"- 当前33号多币种 15m 有看答案机会，但严格选择器失败：最佳选择器 2025 `{current_33['best_selector']['return_2025_pct']:.2f}%`，2026 YTD `{current_33['best_selector']['return_2026_ytd_pct']:.2f}%`。",
        f"- 当前34号根因：41个月里每个月都有看答案正收益候选，但当月赢家在月初训练排序中位名次 `{current_34['selection_gap']['median_oracle_hard_rank_before_month']}`，排进前10的月份 `{current_34['selection_gap']['oracle_top10_hard_rank_months']}`。",
        "",
        "## Causality Notes",
        "",
        f"- 旧项目 feature store 行数 `{no_future['feature_rows']}`，特征数 `{no_future['feature_count']}`，特征因果违规 `{no_future['feature_causality_violations']}`。",
        f"- 旧项目 label store 入口规则：`{no_future['entry_policy']}`；entry_time <= decision_time 违规 `{no_future['entry_time_lte_decision_time_violations']}`。",
        "- 问题不在特征时间戳明显穿越，而在“规则选择用到了未来标签”。老人家可以理解成：菜本身没坏，但我们是看完考试答案才选菜谱。",
        "",
        "## Borrow",
        "",
        "- 借：多周期特征、funding/premium 可用时间、事件池、资金占用、逐K盯市验证。",
        "- 不借：旧的7条规则、旧阈值、10x毛暴露、2025-2026样本内选择结果。",
        "",
        "## Decision",
        "",
        f"- Verdict: `{summary['decision']['verdict']}`",
        f"- Promote strategy: `{summary['decision']['promote_strategy']}`",
        f"- Reason: {summary['decision']['reason']}",
        f"- Next step: {summary['decision']['next_step']}",
    ]
    return "\n".join(lines) + "\n"


def _comparison_table(summary: dict[str, Any]) -> pd.DataFrame:
    old = summary["old_project_in_sample_success"]
    acc = summary["old_project_accounting_validation"]
    fail = summary["old_project_out_of_sample_failure"]
    current_33 = summary["current_project_context"]["strategy_33"]["best_selector"]
    current_34 = summary["current_project_context"]["strategy_34"]["previous_oracle_follow_summary"]

    rows = [
        {
            "case": "old_project_sample_in_2025_2026",
            "selection": "uses_2025_2026_labels",
            "pass": True,
            "net_2025_pct": _bps_to_pct(old["net_2025_bps"]),
            "net_2026_pct": _bps_to_pct(old["net_2026_bps"]),
            "positive_months": old["positive_months"],
            "months": 18,
            "note": "Accounting replay passes, but selection is sample-in.",
        },
        {
            "case": "old_project_same_rules_2024_stress",
            "selection": "fixed_after_sample_in",
            "pass": False,
            "net_2025_pct": None,
            "net_2026_pct": None,
            "positive_months": acc["stress_2024_positive_months"],
            "months": acc["stress_2024_months"],
            "note": f"2024 net {_bps_to_pct(acc['stress_2024_net_bps']):.2f}%.",
        },
        {
            "case": "old_project_pre2025_locked_forward",
            "selection": "rules_locked_before_2025",
            "pass": False,
            "net_2025_pct": _bps_to_pct(fail["best_pre2025_locked"]["test_net_2025_bps"]),
            "net_2026_pct": _bps_to_pct(fail["best_pre2025_locked"]["test_net_2026_bps"]),
            "positive_months": fail["best_pre2025_locked"]["test_positive_months"],
            "months": fail["best_pre2025_locked"]["test_months"],
            "note": "Best locked row still fails.",
        },
        {
            "case": "current_strategy_33_best_strict_selector",
            "selection": "monthly_walk_forward",
            "pass": False,
            "net_2025_pct": current_33["return_2025_pct"],
            "net_2026_pct": current_33["return_2026_ytd_pct"],
            "positive_months": None,
            "months": None,
            "note": "Multisymbol 15m strict selector fails.",
        },
        {
            "case": "current_strategy_34_follow_previous_oracle",
            "selection": "previous_month_oracle",
            "pass": False,
            "net_2025_pct": current_34["return_2025_pct"],
            "net_2026_pct": current_34["return_2026_ytd_pct"],
            "positive_months": None,
            "months": None,
            "note": "Shows hindsight winners do not persist.",
        },
    ]
    return pd.DataFrame(rows)


def _require_files(paths: list[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required files:\n" + "\n".join(missing))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _to_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def _bps_to_pct(value: float | None) -> float:
    if value is None:
        return float("nan")
    return float(value) / 100.0


def _self_check(summary: dict[str, Any], files: dict[str, Path]) -> None:
    for path in files.values():
        if not path.exists() or path.stat().st_size <= 0:
            raise AssertionError(f"Output missing or empty: {path}")
    if not summary["research_only"] or summary["orders_generated"] or summary["orders_submitted"]:
        raise AssertionError("Safety flags are wrong")
    if summary["old_project_accounting_validation"]["label_price_diff_max_bps"] != 0.0:
        raise AssertionError("Old validation label/price mismatch is not zero")
    if summary["old_project_out_of_sample_failure"]["pre2025_locked_pass_rows"] != 0:
        raise AssertionError("Expected pre-2025 locked route to fail")
    if summary["decision"]["promote_strategy"]:
        raise AssertionError("This review must not promote a strategy")


if __name__ == "__main__":
    main()
