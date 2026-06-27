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


STRATEGY_ID = "strategy_17_simple_family_upper_bound_20260627"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
SOURCE_16_SUMMARY = ROOT / "artifacts" / "strategy_16_new_family_probe_20260627" / "summary.json"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source16 = json.loads(SOURCE_16_SUMMARY.read_text(encoding="utf-8"))
    ohlc_path = ROOT / source16["data"]["combined_ohlc"]
    market = probe16._load_market(ohlc_path)
    features = probe16.FeatureCache(market)
    candidates = probe16._candidate_library()
    candidate_monthly = _candidate_monthly(candidates, market, features)

    oracle_specs = [
        ("monthly_oracle_best_return", None, False),
        ("monthly_oracle_best_return_order10", None, True),
        ("trend_monthly_oracle_order10", "trend", True),
        ("mean_reversion_monthly_oracle_order10", "mean_reversion", True),
        ("volatility_breakout_monthly_oracle_order10", "volatility_breakout", True),
    ]

    oracle_monthly_frames: list[pd.DataFrame] = []
    oracle_yearly_frames: list[pd.DataFrame] = []
    oracle_rows: list[dict[str, Any]] = []
    for oracle_id, family, require_order_floor in oracle_specs:
        selected = _select_oracle_months(candidate_monthly, oracle_id, family, require_order_floor)
        yearly = _yearly_from_monthly(selected)
        summary = {
            "oracle_id": oracle_id,
            "family_filter": family or "all",
            "leaky_oracle": True,
            "requires_monthly_orders_ge_10_at_selection": require_order_floor,
            "months_without_order_floor_candidate": int(selected["no_order_floor_candidate"].sum()),
            **_summary_from_monthly(selected, yearly),
        }
        oracle_rows.append(summary)
        if "oracle_id" not in selected.columns:
            selected.insert(0, "oracle_id", oracle_id)
        yearly.insert(0, "oracle_id", oracle_id)
        oracle_monthly_frames.append(selected)
        oracle_yearly_frames.append(yearly)

    oracle_summary = pd.DataFrame(oracle_rows).sort_values(
        ["hard_pass_complete_years", "losing_eval_months", "min_monthly_return_pct", "min_complete_year_return_pct"],
        ascending=[False, True, False, False],
    )
    oracle_monthly = pd.concat(oracle_monthly_frames, ignore_index=True)
    oracle_yearly = pd.concat(oracle_yearly_frames, ignore_index=True)
    best_oracle = oracle_summary.iloc[0].to_dict()

    summary = {
        "status": "strategy_17_simple_family_upper_bound_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Measure a leaky monthly oracle upper bound for Strategy 16 simple non-ret_state candidates. This proves whether the candidate menu itself has enough in-sample monthly pieces.",
        "source": {
            "strategy_16_summary": _rel(SOURCE_16_SUMMARY),
            "strategy_16_decision": source16["decision"],
            "combined_ohlc": source16["data"]["combined_ohlc"],
        },
        "data": {
            "eval_start_month": probe16.EVAL_START_MONTH,
            "eval_end_exclusive": probe16.EVAL_END_EXCLUSIVE,
            "complete_eval_years_for_annual_threshold": probe16.COMPLETE_EVAL_YEARS,
            "partial_eval_year_recorded_not_annual_threshold": probe16.PARTIAL_EVAL_YEAR,
        },
        "cost_model": source16["cost_model"],
        "candidate_grid": source16["candidate_grid"],
        "oracle_warning": {
            "strict_no_future": False,
            "tradeable": False,
            "reason": "The monthly oracle chooses the best candidate after seeing the evaluated month.",
            "month_boundary_switching_cost_included": False,
        },
        "oracle_summary": _json_ready(oracle_summary.to_dict("records")),
        "best_oracle": _json_ready(best_oracle),
        "decision": _decision(best_oracle),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "strategy_16_summary_sha256": _sha256(SOURCE_16_SUMMARY),
            "strategy_16_script_sha256": _sha256(SCRIPTS / "audit_strategy_16_new_family_probe_20260627.py"),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "oracle_summary": _rel(OUT_DIR / "oracle_summary.csv"),
            "oracle_monthly": _rel(OUT_DIR / "oracle_monthly.csv"),
            "oracle_yearly": _rel(OUT_DIR / "oracle_yearly.csv"),
        },
    }

    oracle_summary.to_csv(OUT_DIR / "oracle_summary.csv", index=False)
    oracle_monthly.to_csv(OUT_DIR / "oracle_monthly.csv", index=False)
    oracle_yearly.to_csv(OUT_DIR / "oracle_yearly.csv", index=False)
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _candidate_monthly(candidates: list[dict[str, Any]], market: dict[str, Any], features: probe16.FeatureCache) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for candidate in candidates:
        target = probe16._target_for_candidate(candidate, features)
        equity = probe16._simulate_target(market, target)
        monthly = probe16._monthly_breakdown(equity)
        monthly = monthly.loc[(monthly["month"] >= probe16.EVAL_START_MONTH) & (monthly["month"] < probe16.EVAL_END_EXCLUSIVE)].copy()
        monthly.insert(0, "candidate_id", candidate["candidate_id"])
        monthly.insert(1, "family", candidate["family"])
        monthly.insert(2, "rule", candidate["rule"])
        monthly.insert(3, "leverage", candidate["leverage"])
        rows.append(monthly)
    return pd.concat(rows, ignore_index=True)


def _select_oracle_months(
    candidate_monthly: pd.DataFrame,
    oracle_id: str,
    family: str | None,
    require_order_floor: bool,
) -> pd.DataFrame:
    subset = candidate_monthly.copy()
    if family:
        subset = subset.loc[subset["family"] == family].copy()
    selected_rows: list[dict[str, Any]] = []
    for month, group in subset.groupby("month", sort=True):
        pool = group
        no_order_floor_candidate = False
        if require_order_floor:
            order_pool = group.loc[group["orders"] >= probe16.REQUIRED_MIN_MONTHLY_ORDERS]
            if order_pool.empty:
                no_order_floor_candidate = True
            else:
                pool = order_pool
        best = pool.sort_values(["return_pct", "orders", "turnover"], ascending=[False, False, True]).iloc[0].to_dict()
        best["oracle_id"] = oracle_id
        best["no_order_floor_candidate"] = no_order_floor_candidate
        selected_rows.append(best)
    return pd.DataFrame(selected_rows)


def _yearly_from_monthly(monthly: pd.DataFrame) -> pd.DataFrame:
    out = monthly.copy()
    out["year"] = out["month"].str[:4]
    yearly = (
        out.groupby("year", as_index=False)
        .agg(
            log_return=("log_return", "sum"),
            cost_log=("cost_log", "sum"),
            turnover=("turnover", "sum"),
            orders_sum=("orders", "sum"),
            months=("month", "count"),
            losing_months=("return_pct", lambda values: int((values <= 0).sum())),
            min_monthly_return_pct=("return_pct", "min"),
            min_monthly_orders=("orders", "min"),
            max_drawdown_pct=("max_drawdown_pct", "min"),
        )
    )
    yearly["compounded_return_pct"] = (np.exp(yearly["log_return"]) - 1.0) * 100.0
    return yearly


def _summary_from_monthly(monthly: pd.DataFrame, yearly: pd.DataFrame) -> dict[str, Any]:
    yearly_by_year = {str(row.year): row for row in yearly.itertuples()}
    complete_returns = [
        float(yearly_by_year[year].compounded_return_pct)
        for year in probe16.COMPLETE_EVAL_YEARS
        if year in yearly_by_year
    ]
    min_complete_year_return = min(complete_returns) if complete_returns else -999.0
    losing_eval_months = int((monthly["return_pct"] <= 0).sum())
    min_orders = int(monthly["orders"].min())
    return {
        "hard_pass_complete_years": bool(
            len(complete_returns) == len(probe16.COMPLETE_EVAL_YEARS)
            and min_complete_year_return > probe16.REQUIRED_RETURN_PCT
            and losing_eval_months == 0
            and min_orders >= probe16.REQUIRED_MIN_MONTHLY_ORDERS
        ),
        "non_positive_months": monthly.loc[monthly["return_pct"] <= 0, "month"].tolist(),
        "total_eval_return_pct": float((np.exp(float(monthly["log_return"].sum())) - 1.0) * 100.0),
        "return_2023_pct": _year_return(yearly_by_year, "2023"),
        "return_2024_pct": _year_return(yearly_by_year, "2024"),
        "return_2025_pct": _year_return(yearly_by_year, "2025"),
        "return_2026_ytd_pct": _year_return(yearly_by_year, "2026"),
        "min_complete_year_return_pct": float(min_complete_year_return),
        "losing_eval_months": losing_eval_months,
        "min_monthly_return_pct": float(monthly["return_pct"].min()),
        "min_monthly_orders": min_orders,
        "orders": int(monthly["orders"].sum()),
        "turnover": float(monthly["turnover"].sum()),
        "cost_log": float(monthly["cost_log"].sum()),
        "worst_selected_month_drawdown_pct": float(monthly["max_drawdown_pct"].min()),
        "selected_candidate_count": int(monthly["candidate_id"].nunique()),
    }


def _year_return(yearly_by_year: dict[str, Any], year: str) -> float | None:
    if year not in yearly_by_year:
        return None
    return float(yearly_by_year[year].compounded_return_pct)


def _decision(best_oracle: dict[str, Any]) -> dict[str, Any]:
    if bool(best_oracle["hard_pass_complete_years"]):
        return {
            "verdict": "LEAKY_UPPER_BOUND_HAS_ENOUGH_MONTHLY_PIECES",
            "promote_strategy": False,
            "reason": "看答案的月度上限能过硬门槛，但它不能交易；问题在于如何不用未来信息提前选中这些月份。",
            "next_step": "做18号选择器瓶颈诊断，比较过去表现、状态标签和未来最佳之间到底有没有可预测关系。",
        }
    return {
        "verdict": "SIMPLE_FAMILY_UPPER_BOUND_FAILS",
        "promote_strategy": False,
        "reason": "即使每个月事后挑最好候选，这批简单规则也过不了硬门槛。",
        "next_step": "停止扩这批简单规则，换更不同的策略族或重新审视硬目标可行性。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_oracle"]
    decision = summary["decision"]
    return f"""# 17号简单策略族上限测试

这不是策略，不能交易。它是“看答案”的月度上限测试。

## 最好上限

- oracle：`{best["oracle_id"]}`
- 硬通过：`{best["hard_pass_complete_years"]}`
- 2023：`{best["return_2023_pct"]:.2f}%`
- 2024：`{best["return_2024_pct"]:.2f}%`
- 2025：`{best["return_2025_pct"]:.2f}%`
- 2026 YTD：`{best["return_2026_ytd_pct"]:.2f}%`
- 亏损月：`{best["losing_eval_months"]}`
- 不盈利月份：`{", ".join(best["non_positive_months"])}`
- 最差月：`{best["min_monthly_return_pct"]:.2f}%`
- 最少月交易：`{best["min_monthly_orders"]}`
- 选中过的候选数：`{best["selected_candidate_count"]}`

## 判断

`{decision["verdict"]}`

{decision["reason"]}

注意：这个测试事后知道每个月哪个候选最好，所以只能当上限，不能当真实策略。
"""


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, float):
        return None if np.isnan(value) else value
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
