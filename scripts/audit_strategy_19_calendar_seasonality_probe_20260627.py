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


STRATEGY_ID = "strategy_19_calendar_seasonality_probe_20260627"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
BASELINE_15_SUMMARY = ROOT / "artifacts" / "strategy_15_unified_data_baseline_20260627" / "summary.json"

MODEL_START_MONTH = "2021-01"
TRAIN_SCORE_START_MONTH = "2021-01"
EVAL_START_MONTH = "2023-01"
EVAL_END_EXCLUSIVE = "2026-06"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    baseline = json.loads(BASELINE_15_SUMMARY.read_text(encoding="utf-8"))
    ohlc_path = ROOT / baseline["input_files"]["combined_ohlc"]
    market = probe16._load_market(ohlc_path)
    candidates = _candidate_library()

    monthly_rows: list[pd.DataFrame] = []
    target_cache: dict[str, np.ndarray] = {}
    for candidate in candidates:
        target = _calendar_target(candidate, market)
        target_cache[candidate["candidate_id"]] = target
        equity = probe16._simulate_target(market, target)
        monthly = probe16._monthly_breakdown(equity)
        monthly = monthly.loc[(monthly["month"] >= TRAIN_SCORE_START_MONTH) & (monthly["month"] < EVAL_END_EXCLUSIVE)].copy()
        monthly.insert(0, "candidate_id", candidate["candidate_id"])
        monthly.insert(1, "bucket_family", candidate["bucket_family"])
        monthly.insert(2, "leverage", candidate["leverage"])
        monthly_rows.append(monthly)

    candidate_monthly = pd.concat(monthly_rows, ignore_index=True)
    selector_specs = [("all_calendar", None)] + [
        (f"{bucket}_only", bucket) for bucket in ["session", "weekday", "hour", "hour_week"]
    ]

    selector_rows: list[dict[str, Any]] = []
    selection_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    yearly_frames: list[pd.DataFrame] = []
    for selector_id, bucket_family in selector_specs:
        selections = _select_months(candidate_monthly, candidates, selector_id, bucket_family)
        selected_target = np.zeros(len(market["timestamp"]), dtype=float)
        for row in selections:
            mask = market["month"] == row["eval_month"]
            selected_target[mask] = target_cache[row["candidate_id"]][mask]
        equity = probe16._simulate_target(market, selected_target)
        equity = equity.loc[(equity["month"] >= EVAL_START_MONTH) & (equity["month"] < EVAL_END_EXCLUSIVE)].copy()
        monthly = probe16._monthly_breakdown(equity)
        yearly = probe16._yearly_breakdown(monthly)
        summary = {
            "selector_id": selector_id,
            "bucket_family_filter": bucket_family or "all",
            "selected_candidate_count": int(pd.DataFrame(selections)["candidate_id"].nunique()),
            **probe16._result_summary(monthly, yearly),
        }
        selector_rows.append(summary)
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
    selected_params = pd.concat(selection_frames, ignore_index=True)
    selector_monthly = pd.concat(monthly_frames, ignore_index=True)
    selector_yearly = pd.concat(yearly_frames, ignore_index=True)
    candidate_scan = _candidate_scan(candidate_monthly, candidates)
    best = selector_summary.iloc[0].to_dict()

    summary = {
        "status": "strategy_19_calendar_seasonality_probe_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Probe a calendar/time-of-week seasonality family on the Strategy 15 USD-M futures baseline. This is intentionally different from ret_state and simple price-indicator rules.",
        "data": {
            "baseline_15_summary": _rel(BASELINE_15_SUMMARY),
            "combined_ohlc": _rel(ohlc_path),
            "model_start_month": MODEL_START_MONTH,
            "train_score_start_month": TRAIN_SCORE_START_MONTH,
            "eval_start_month": EVAL_START_MONTH,
            "eval_end_exclusive": EVAL_END_EXCLUSIVE,
            "complete_eval_years_for_annual_threshold": probe16.COMPLETE_EVAL_YEARS,
            "partial_eval_year_recorded_not_annual_threshold": probe16.PARTIAL_EVAL_YEAR,
        },
        "strict_no_future": {
            "signals_use_only_calendar_bucket_and_prior_month_training": True,
            "position_participates_from_bar_t_plus_1": True,
            "monthly_selection_uses_only_months_before_eval_month": True,
        },
        "cost_model": {
            "cost_per_side": probe16.COST_PER_SIDE,
            "round_trip_open_close": probe16.ROUND_TRIP_COST,
        },
        "candidate_grid": _candidate_grid_summary(candidates),
        "selector_summary": probe16._json_ready(selector_summary.to_dict("records")),
        "best_selector": probe16._json_ready(best),
        "best_dynamic_candidate": probe16._json_ready(candidate_scan.iloc[0].to_dict()),
        "decision": _decision(best),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "baseline_15_summary_sha256": _sha256(BASELINE_15_SUMMARY),
            "combined_ohlc_sha256": _sha256(ohlc_path),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "selector_summary": _rel(OUT_DIR / "selector_summary.csv"),
            "selector_monthly": _rel(OUT_DIR / "selector_monthly.csv"),
            "selector_yearly": _rel(OUT_DIR / "selector_yearly.csv"),
            "selected_params_by_month": _rel(OUT_DIR / "selected_params_by_month.csv"),
            "candidate_scan": _rel(OUT_DIR / "candidate_scan.csv"),
        },
    }

    selector_summary.to_csv(OUT_DIR / "selector_summary.csv", index=False)
    selector_monthly.to_csv(OUT_DIR / "selector_monthly.csv", index=False)
    selector_yearly.to_csv(OUT_DIR / "selector_yearly.csv", index=False)
    selected_params.to_csv(OUT_DIR / "selected_params_by_month.csv", index=False)
    candidate_scan.to_csv(OUT_DIR / "candidate_scan.csv", index=False)
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(probe16._json_ready(summary), indent=2, ensure_ascii=False))


def _candidate_library() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for bucket_family in ["session", "weekday", "hour", "hour_week"]:
        for lookback_months in [12, 24, None]:
            for min_abs_mean_bps in [0.0, 0.5, 1.0]:
                for min_samples in [20, 50]:
                    for leverage in [1.0, 2.0, 4.0]:
                        lookback_label = "expanding" if lookback_months is None else str(lookback_months)
                        candidates.append(
                            {
                                "candidate_id": (
                                    f"calendar_{bucket_family}_lb{lookback_label}_"
                                    f"thr{str(min_abs_mean_bps).replace('.', 'p')}_"
                                    f"min{min_samples}_lev{str(leverage).replace('.', 'p')}"
                                ),
                                "bucket_family": bucket_family,
                                "lookback_months": lookback_months,
                                "min_abs_mean_bps": min_abs_mean_bps,
                                "min_samples": min_samples,
                                "leverage": leverage,
                            }
                        )
    return candidates


def _calendar_target(candidate: dict[str, Any], market: dict[str, Any]) -> np.ndarray:
    timestamp = market["timestamp"]
    buckets = _bucket_values(timestamp, candidate["bucket_family"])
    months = pd.Series(market["month"])
    future_return = np.r_[market["raw_return"][1:], np.nan]
    target = np.zeros(len(timestamp), dtype=float)
    model_months = [month for month in sorted(months.unique()) if MODEL_START_MONTH <= month < EVAL_END_EXCLUSIVE]

    for month in model_months:
        month_start = pd.Timestamp(f"{month}-01T00:00:00Z")
        lookback_months = candidate["lookback_months"]
        train_start = pd.Timestamp("2020-01-01T00:00:00Z")
        if lookback_months is not None:
            train_start = month_start - pd.DateOffset(months=int(lookback_months))
        next_timestamp = timestamp.shift(-1)
        train_mask = (timestamp >= train_start) & (next_timestamp < month_start)
        train = pd.DataFrame(
            {
                "bucket": buckets[train_mask],
                "future_return": future_return[train_mask.to_numpy()],
            }
        ).dropna()
        means = train.groupby("bucket")["future_return"].agg(["mean", "count"])
        bucket_side: dict[int, float] = {}
        for bucket, row in means.iterrows():
            mean_bps = float(row["mean"]) * 10_000.0
            if int(row["count"]) < int(candidate["min_samples"]):
                side = 0.0
            elif mean_bps > float(candidate["min_abs_mean_bps"]):
                side = 1.0
            elif mean_bps < -float(candidate["min_abs_mean_bps"]):
                side = -1.0
            else:
                side = 0.0
            bucket_side[int(bucket)] = side

        eval_mask = (months == month).to_numpy()
        target[eval_mask] = np.array([bucket_side.get(int(bucket), 0.0) for bucket in buckets[eval_mask]], dtype=float)
        target[eval_mask] *= float(candidate["leverage"])
        month_indexes = np.flatnonzero(eval_mask)
        if len(month_indexes):
            target[month_indexes[-1]] = 0.0
    return target


def _bucket_values(timestamp: pd.Series, bucket_family: str) -> np.ndarray:
    if bucket_family == "session":
        return (timestamp.dt.hour // 6).to_numpy()
    if bucket_family == "weekday":
        return timestamp.dt.weekday.to_numpy()
    if bucket_family == "hour":
        return timestamp.dt.hour.to_numpy()
    if bucket_family == "hour_week":
        return (timestamp.dt.weekday * 24 + timestamp.dt.hour).to_numpy()
    raise ValueError(bucket_family)


def _select_months(
    candidate_monthly: pd.DataFrame,
    candidates: list[dict[str, Any]],
    selector_id: str,
    bucket_family: str | None,
) -> list[dict[str, Any]]:
    meta = pd.DataFrame(candidates)
    if bucket_family:
        candidate_ids = set(meta.loc[meta["bucket_family"] == bucket_family, "candidate_id"])
    else:
        candidate_ids = set(meta["candidate_id"])
    subset = candidate_monthly.loc[candidate_monthly["candidate_id"].isin(candidate_ids)].copy()
    eval_months = sorted(month for month in subset["month"].unique() if EVAL_START_MONTH <= month < EVAL_END_EXCLUSIVE)
    selections: list[dict[str, Any]] = []
    for eval_month in eval_months:
        train = subset.loc[(subset["month"] >= TRAIN_SCORE_START_MONTH) & (subset["month"] < eval_month)]
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
                "bucket_family": best["bucket_family"],
                "lookback_months": best["lookback_months"],
                "min_abs_mean_bps": best["min_abs_mean_bps"],
                "min_samples": best["min_samples"],
                "leverage": best["leverage"],
                "train_hard_ok_candidate_count": int(score["train_hard_ok"].sum()),
                **{key: value for key, value in best.items() if key.startswith("train_")},
                "eval_static_return_pct": eval_row["return_pct"],
                "eval_static_orders": eval_row["orders"],
                "eval_static_turnover": eval_row["turnover"],
            }
        )
    return selections


def _candidate_scan(candidate_monthly: pd.DataFrame, candidates: list[dict[str, Any]]) -> pd.DataFrame:
    meta = pd.DataFrame(candidates)
    rows = []
    for candidate_id, monthly in candidate_monthly.groupby("candidate_id"):
        eval_monthly = monthly.loc[(monthly["month"] >= EVAL_START_MONTH) & (monthly["month"] < EVAL_END_EXCLUSIVE)].copy()
        yearly = probe16._yearly_breakdown(eval_monthly)
        rows.append({"candidate_id": candidate_id, **probe16._result_summary(eval_monthly, yearly)})
    return (
        pd.DataFrame(rows)
        .merge(meta, on="candidate_id", how="left")
        .sort_values(
            ["hard_pass_complete_years", "losing_eval_months", "min_monthly_return_pct", "min_complete_year_return_pct"],
            ascending=[False, True, False, False],
        )
    )


def _candidate_grid_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    frame = pd.DataFrame(candidates)
    return {
        "total_candidates": int(len(frame)),
        "bucket_families": {str(k): int(v) for k, v in frame["bucket_family"].value_counts().sort_index().items()},
        "lookback_months": ["expanding" if pd.isna(v) else int(v) for v in sorted(frame["lookback_months"].dropna().unique())]
        + ["expanding"],
        "min_abs_mean_bps": sorted(float(v) for v in frame["min_abs_mean_bps"].unique()),
        "min_samples": sorted(int(v) for v in frame["min_samples"].unique()),
        "leverages": sorted(float(v) for v in frame["leverage"].unique()),
    }


def _decision(best: dict[str, Any]) -> dict[str, Any]:
    hard_pass = bool(best["hard_pass_complete_years"])
    return {
        "verdict": "CALENDAR_SEASONALITY_PROMISING" if hard_pass else "CALENDAR_SEASONALITY_FAILS",
        "promote_strategy": False,
        "reason": (
            "日历季节性严格逐月选择通过硬门槛，但仍需压力测试。"
            if hard_pass
            else "日历/星期/小时季节性在严格逐月选择下没有通过硬门槛。"
        ),
        "next_step": (
            "另起审计做手续费、延迟和漏单压力测试。"
            if hard_pass
            else "不要把日历季节性升级候选；如果继续，应换到更不同的数据特征或先做可行性上限。"
        ),
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_selector"]
    decision = summary["decision"]
    return f"""# 19号日历季节性探针

这不是候选策略，只检查星期几、小时、交易时段这类日历规律有没有用。

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
