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
import audit_strategy_23_funding_rate_upper_bound_20260627 as funding23


STRATEGY_ID = "strategy_24_funding_rate_strict_selector_20260627"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
SOURCE_23_SUMMARY = ROOT / "artifacts" / "strategy_23_funding_rate_upper_bound_20260627" / "summary.json"
BASELINE_15_SUMMARY = ROOT / "artifacts" / "strategy_15_unified_data_baseline_20260627" / "summary.json"
TRAIN_START_MONTH = "2020-01"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source23 = json.loads(SOURCE_23_SUMMARY.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE_15_SUMMARY.read_text(encoding="utf-8"))
    ohlc_path = ROOT / baseline["input_files"]["combined_ohlc"]
    market = probe16._load_market(ohlc_path)
    funding, funding_quality = funding23._load_or_fetch_funding_rates()
    features = funding23.FundingFeatures(market, funding)
    candidates = funding23._candidate_library()
    candidate_monthly = _candidate_monthly_all(candidates, market, features)

    selector_specs = [("all_funding", None)] + [(f"{family}_only", family) for family in ["funding_level", "funding_change", "funding_zscore", "funding_mean"]]
    target_cache: dict[str, np.ndarray] = {}
    selector_rows: list[dict[str, Any]] = []
    selection_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    yearly_frames: list[pd.DataFrame] = []
    for selector_id, family in selector_specs:
        selections = _select_months(candidate_monthly, candidates, selector_id, family)
        selected_target = np.zeros(len(market["timestamp"]), dtype=float)
        for row in selections:
            candidate_id = row["candidate_id"]
            if candidate_id not in target_cache:
                target_cache[candidate_id] = funding23._target_for_candidate(_candidate_by_id(candidates, candidate_id), features)
            mask = market["month"] == row["eval_month"]
            selected_target[mask] = target_cache[candidate_id][mask]
        equity = probe16._simulate_target(market, selected_target)
        equity = equity.loc[(equity["month"] >= probe16.EVAL_START_MONTH) & (equity["month"] < probe16.EVAL_END_EXCLUSIVE)].copy()
        monthly = probe16._monthly_breakdown(equity)
        yearly = probe16._yearly_breakdown(monthly)
        selector_rows.append(
            {
                "selector_id": selector_id,
                "family_filter": family or "all",
                "selected_candidate_count": int(pd.DataFrame(selections)["candidate_id"].nunique()),
                **probe16._result_summary(monthly, yearly),
            }
        )
        selected = pd.DataFrame(selections)
        selected.insert(0, "selector_id", selector_id)
        monthly.insert(0, "selector_id", selector_id)
        yearly.insert(0, "selector_id", selector_id)
        selection_frames.append(selected)
        monthly_frames.append(monthly)
        yearly_frames.append(yearly)

    selector_summary = pd.DataFrame(selector_rows).sort_values(
        ["hard_pass_complete_years", "losing_eval_months", "min_monthly_return_pct", "min_complete_year_return_pct"],
        ascending=[False, True, False, False],
    )
    best = selector_summary.iloc[0].to_dict()
    summary = {
        "status": "strategy_24_funding_rate_strict_selector_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Test whether Strategy 23 funding-rate oracle pieces can be selected with strict expanding no-future monthly selection.",
        "source": {
            "strategy_23_summary": _rel(SOURCE_23_SUMMARY),
            "strategy_23_decision": source23["decision"],
            "combined_ohlc": baseline["input_files"]["combined_ohlc"],
            "funding_rates": source23["source"]["funding_rates"],
            "new_rules_added": False,
        },
        "data": {
            "train_start_month": TRAIN_START_MONTH,
            "eval_start_month": probe16.EVAL_START_MONTH,
            "eval_end_exclusive": probe16.EVAL_END_EXCLUSIVE,
            "funding_quality": funding_quality,
        },
        "strict_no_future": {
            "funding_features_use_latest_known_funding_at_or_before_bar_t": True,
            "position_participates_from_bar_t_plus_1": True,
            "monthly_selection_uses_only_months_before_eval_month": True,
        },
        "cost_model": {"cost_per_side": probe16.COST_PER_SIDE, "round_trip_open_close": probe16.ROUND_TRIP_COST},
        "candidate_grid": probe16._candidate_grid_summary(candidates),
        "selector_summary": probe16._json_ready(selector_summary.to_dict("records")),
        "best_selector": probe16._json_ready(best),
        "decision": _decision(best),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "strategy_23_summary_sha256": _sha256(SOURCE_23_SUMMARY),
            "funding_rates_sha256": _sha256(ROOT / source23["source"]["funding_rates"]),
            "combined_ohlc_sha256": _sha256(ohlc_path),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "selector_summary": _rel(OUT_DIR / "selector_summary.csv"),
            "selector_monthly": _rel(OUT_DIR / "selector_monthly.csv"),
            "selector_yearly": _rel(OUT_DIR / "selector_yearly.csv"),
            "selected_params_by_month": _rel(OUT_DIR / "selected_params_by_month.csv"),
            "candidate_monthly": _rel(OUT_DIR / "candidate_monthly.csv"),
        },
    }

    selector_summary.to_csv(OUT_DIR / "selector_summary.csv", index=False)
    pd.concat(monthly_frames, ignore_index=True).to_csv(OUT_DIR / "selector_monthly.csv", index=False)
    pd.concat(yearly_frames, ignore_index=True).to_csv(OUT_DIR / "selector_yearly.csv", index=False)
    pd.concat(selection_frames, ignore_index=True).to_csv(OUT_DIR / "selected_params_by_month.csv", index=False)
    candidate_monthly.to_csv(OUT_DIR / "candidate_monthly.csv", index=False)
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(probe16._json_ready(summary), indent=2, ensure_ascii=False))


def _candidate_monthly_all(candidates: list[dict[str, Any]], market: dict[str, Any], features: funding23.FundingFeatures) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for candidate in candidates:
        target = funding23._target_for_candidate(candidate, features)
        equity = probe16._simulate_target(market, target)
        monthly = probe16._monthly_breakdown(equity)
        monthly.insert(0, "candidate_id", candidate["candidate_id"])
        monthly.insert(1, "family", candidate["family"])
        monthly.insert(2, "rule", candidate["rule"])
        monthly.insert(3, "direction", candidate["direction"])
        monthly.insert(4, "leverage", candidate["leverage"])
        rows.append(monthly)
    return pd.concat(rows, ignore_index=True)


def _select_months(
    candidate_monthly: pd.DataFrame,
    candidates: list[dict[str, Any]],
    selector_id: str,
    family: str | None,
) -> list[dict[str, Any]]:
    meta = pd.DataFrame(candidates)
    candidate_ids = set(meta.loc[meta["family"] == family, "candidate_id"]) if family else set(meta["candidate_id"])
    subset = candidate_monthly.loc[candidate_monthly["candidate_id"].isin(candidate_ids)].copy()
    eval_months = sorted(month for month in subset["month"].unique() if probe16.EVAL_START_MONTH <= month < probe16.EVAL_END_EXCLUSIVE)
    selections: list[dict[str, Any]] = []
    for eval_month in eval_months:
        train = subset.loc[(subset["month"] >= TRAIN_START_MONTH) & (subset["month"] < eval_month)]
        score = (
            train.groupby("candidate_id", as_index=False)
            .agg(
                train_months=("month", "count"),
                train_log_return=("log_return", "sum"),
                train_losing_months=("return_pct", lambda values: int((values <= 0).sum())),
                train_min_monthly_return_pct=("return_pct", "min"),
                train_min_monthly_orders=("orders", "min"),
                train_turnover=("turnover", "sum"),
                train_last_month=("month", "max"),
            )
            .merge(meta, on="candidate_id", how="left")
        )
        score["train_return_pct"] = (np.exp(score["train_log_return"]) - 1.0) * 100.0
        score["train_hard_ok"] = (
            (score["train_return_pct"] > probe16.REQUIRED_RETURN_PCT)
            & (score["train_losing_months"] == 0)
            & (score["train_min_monthly_orders"] >= probe16.REQUIRED_MIN_MONTHLY_ORDERS)
        )
        score = score.sort_values(
            [
                "train_hard_ok",
                "train_losing_months",
                "train_min_monthly_return_pct",
                "train_return_pct",
                "train_min_monthly_orders",
                "train_turnover",
                "leverage",
                "candidate_id",
            ],
            ascending=[False, True, False, False, False, True, True, True],
        )
        best = score.iloc[0].to_dict()
        eval_row = subset.loc[(subset["candidate_id"] == best["candidate_id"]) & (subset["month"] == eval_month)].iloc[0].to_dict()
        selections.append(
            {
                "eval_month": eval_month,
                "candidate_id": best["candidate_id"],
                "family": best["family"],
                "rule": best["rule"],
                "direction": best["direction"],
                "leverage": best["leverage"],
                "train_hard_ok_candidate_count": int(score["train_hard_ok"].sum()),
                **{key: value for key, value in best.items() if key.startswith("train_")},
                "eval_static_return_pct": eval_row["return_pct"],
                "eval_static_orders": eval_row["orders"],
                "eval_static_turnover": eval_row["turnover"],
            }
        )
    return selections


def _candidate_by_id(candidates: list[dict[str, Any]], candidate_id: str) -> dict[str, Any]:
    for candidate in candidates:
        if candidate["candidate_id"] == candidate_id:
            return candidate
    raise KeyError(candidate_id)


def _decision(best: dict[str, Any]) -> dict[str, Any]:
    hard_pass = bool(best["hard_pass_complete_years"])
    return {
        "verdict": "FUNDING_RATE_STRICT_SELECTOR_PROMISING" if hard_pass else "FUNDING_RATE_STRICT_SELECTOR_FAILS",
        "promote_strategy": False,
        "reason": (
            "资金费率候选在严格逐月选择下通过硬门槛，但仍需执行压力和泄漏复查。"
            if hard_pass
            else "资金费率看答案上限很好，但严格逐月选择无法提前选中好候选。"
        ),
        "next_step": (
            "另起审计做手续费、延迟、月初切换成本和过拟合复查。"
            if hard_pass
            else "不要升级资金费率候选；若继续，应换持仓量等新数据源或调整硬目标。"
        ),
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_selector"]
    decision = summary["decision"]
    return f"""# 24号资金费率严格选择器

这不是策略，也不是固化版。它只检查 23号资金费率“看答案”月份，能不能不用未来信息提前选中。

## 最好严格选择器

- selector：`{best["selector_id"]}`
- 硬通过：`{best["hard_pass_complete_years"]}`
- 2023：`{best["return_2023_pct"]:.2f}%`
- 2024：`{best["return_2024_pct"]:.2f}%`
- 2025：`{best["return_2025_pct"]:.2f}%`
- 2026 YTD：`{best["return_2026_ytd_pct"]:.2f}%`
- 亏损月：`{best["losing_eval_months"]}`
- 最差月：`{best["min_monthly_return_pct"]:.2f}%`
- 最少月交易：`{best["min_monthly_orders"]}`
- 最大回撤：`{best["max_drawdown_pct"]:.2f}%`

## 判断

`{decision["verdict"]}`

{decision["reason"]}
"""


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(probe16._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
