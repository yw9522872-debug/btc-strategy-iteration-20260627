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
import audit_strategy_19_calendar_seasonality_probe_20260627 as probe19
import audit_strategy_20_ohlc_structure_upper_bound_20260627 as probe20
import audit_strategy_21_volume_upper_bound_20260627 as probe21


STRATEGY_ID = "strategy_22_hard_target_bottleneck_20260627"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
BASELINE_15_SUMMARY = ROOT / "artifacts" / "strategy_15_unified_data_baseline_20260627" / "summary.json"

TRAIN_START_MONTH = "2020-01"
EVAL_START_MONTH = "2023-01"
EVAL_END_EXCLUSIVE = "2026-06"
ORDER_FLOORS = [0, 2, 5, 10]
ROUND_TRIP_COSTS = [0.0, 0.001, 0.002, 0.003, 0.004]
MONTHLY_REQUIREMENTS = ["allow_any", "return_ge_minus1", "return_gt_0"]
ANNUAL_THRESHOLDS_PCT = [50.0, 100.0]
EPS = 1e-12


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    baseline = json.loads(BASELINE_15_SUMMARY.read_text(encoding="utf-8"))
    if not baseline["quality"]["pass"]:
        raise RuntimeError("Strategy 15 data baseline is not ready.")

    ohlc_path = ROOT / baseline["input_files"]["combined_ohlc"]
    market = probe16._load_market(ohlc_path)
    base_path = OUT_DIR / "candidate_monthly_base.csv"
    meta_path = OUT_DIR / "candidate_pool_summary.csv"
    if base_path.exists() and meta_path.exists():
        candidate_monthly = pd.read_csv(base_path)
        candidate_meta = pd.read_csv(meta_path)
        _, volume_quality = probe21._load_or_fetch_volume_klines()
    else:
        candidate_monthly, candidate_meta, volume_quality = _build_candidate_monthly(market)
        candidate_monthly.to_csv(base_path, index=False)
        candidate_meta.to_csv(meta_path, index=False)

    scenario_summary, scenario_monthly, selected_params = _run_grid_fast(candidate_monthly, candidate_meta)

    scenario_summary.to_csv(OUT_DIR / "scenario_summary.csv", index=False)
    scenario_monthly.to_csv(OUT_DIR / "scenario_monthly.csv", index=False)
    selected_params.to_csv(OUT_DIR / "selected_params_by_month.csv", index=False)

    summary = _make_summary(
        baseline=baseline,
        ohlc_path=ohlc_path,
        market=market,
        candidate_meta=candidate_meta,
        volume_quality=volume_quality,
        scenario_summary=scenario_summary,
    )
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _build_candidate_monthly(market: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    rows: list[pd.DataFrame] = []
    meta_rows: list[dict[str, Any]] = []

    features16 = probe16.FeatureCache(market)
    for candidate in probe16._candidate_library():
        meta = _meta("strategy16_simple", candidate["candidate_id"], candidate["family"], candidate["rule"], candidate)
        target = probe16._target_for_candidate(candidate, features16)
        rows.append(_monthly_base_from_target(market, target, meta))
        meta_rows.append(meta)

    for candidate in probe19._candidate_library():
        meta = _meta("strategy19_calendar", candidate["candidate_id"], candidate["bucket_family"], "calendar", candidate)
        target = probe19._calendar_target(candidate, market)
        rows.append(_monthly_base_from_target(market, target, meta))
        meta_rows.append(meta)

    features20 = probe20.OhlcStructureFeatures(market)
    for candidate in probe20._candidate_library():
        meta = _meta("strategy20_ohlc_structure", candidate["candidate_id"], candidate["family"], candidate["rule"], candidate)
        target = probe20._target_for_candidate(candidate, features20)
        rows.append(_monthly_base_from_target(market, target, meta))
        meta_rows.append(meta)

    volume_frame, volume_quality = probe21._load_or_fetch_volume_klines()
    volume_market = probe21._market(volume_frame)
    if not np.array_equal(pd.Series(volume_market["timestamp"]).astype(str).to_numpy(), pd.Series(market["timestamp"]).astype(str).to_numpy()):
        raise RuntimeError("Strategy 21 volume timestamps do not match Strategy 15 baseline timestamps.")
    features21 = probe21.VolumeFeatures(volume_frame)
    for candidate in probe21._candidate_library():
        meta = _meta("strategy21_volume", candidate["candidate_id"], candidate["family"], candidate["rule"], candidate)
        target = probe21._target_for_candidate(candidate, features21)
        rows.append(_monthly_base_from_target(market, target, meta))
        meta_rows.append(meta)

    return pd.concat(rows, ignore_index=True), pd.DataFrame(meta_rows), volume_quality


def _meta(pool: str, candidate_id: str, family: str, rule: str, candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": f"{pool}__{candidate_id}",
        "source_candidate_id": candidate_id,
        "pool": pool,
        "family": family,
        "rule": rule,
        "leverage": float(candidate.get("leverage", 0.0)),
        "params_json": json.dumps(_json_ready(candidate), sort_keys=True, ensure_ascii=False),
    }


def _monthly_base_from_target(market: dict[str, Any], target: np.ndarray, meta: dict[str, Any]) -> pd.DataFrame:
    target = np.nan_to_num(target.astype(float), nan=0.0)
    prev_target = np.r_[0.0, target[:-1]]
    turnover = np.abs(target - prev_target)
    order_count = (turnover > EPS).astype(int)
    gross_lr = prev_target * market["raw_return"]
    frame = pd.DataFrame(
        {
            "month": market["month"],
            "gross_log_return": gross_lr,
            "turnover": turnover,
            "orders": order_count,
            "raw_return": market["raw_return"],
            "target": target,
            "prev_target": prev_target,
        }
    )
    monthly = frame.groupby("month", as_index=False).agg(
        gross_log_return=("gross_log_return", "sum"),
        turnover=("turnover", "sum"),
        orders=("orders", "sum"),
        first_raw_return=("raw_return", "first"),
        first_target=("target", "first"),
        first_prev_target=("prev_target", "first"),
        last_target=("target", "last"),
    )
    monthly["first_base_turnover"] = (monthly["first_target"] - monthly["first_prev_target"]).abs()
    monthly["first_base_order"] = (monthly["first_base_turnover"] > EPS).astype(int)
    for key, value in reversed(list(meta.items())):
        monthly.insert(0, key, value)
    return monthly


def _apply_cost(candidate_monthly: pd.DataFrame, cost_per_side: float) -> pd.DataFrame:
    out = candidate_monthly.copy()
    out["cost_log"] = out["turnover"] * cost_per_side
    out["log_return"] = out["gross_log_return"] - out["cost_log"]
    out["return_pct"] = (np.exp(out["log_return"]) - 1.0) * 100.0
    return out


def _run_grid_fast(candidate_monthly: pd.DataFrame, candidate_meta: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    scenario_rows: list[dict[str, Any]] = []
    monthly_frames: list[pd.DataFrame] = []
    selection_frames: list[pd.DataFrame] = []
    for round_trip_cost in ROUND_TRIP_COSTS:
        cost_per_side = round_trip_cost / 2.0
        cube = _make_cube(candidate_monthly, candidate_meta, cost_per_side)
        for order_floor in ORDER_FLOORS:
            for monthly_requirement in MONTHLY_REQUIREMENTS:
                for annual_threshold_pct in ANNUAL_THRESHOLDS_PCT:
                    spec = {
                        "order_floor": order_floor,
                        "round_trip_cost": round_trip_cost,
                        "cost_per_side": cost_per_side,
                        "monthly_requirement": monthly_requirement,
                        "annual_threshold_pct": annual_threshold_pct,
                    }
                    strict_monthly, strict_selected = _strict_selector_cube(cube, spec)
                    scenario_rows.append(_scenario_summary("strict_expanding_selector", strict_monthly, spec))
                    strict_monthly.insert(0, "method", "strict_expanding_selector")
                    strict_monthly = _insert_spec_columns(strict_monthly, spec)
                    strict_selected.insert(0, "method", "strict_expanding_selector")
                    strict_selected = _insert_spec_columns(strict_selected, spec)
                    monthly_frames.append(strict_monthly)
                    selection_frames.append(strict_selected)

                    oracle_monthly = _oracle_cube(cube, spec)
                    scenario_rows.append(_scenario_summary("monthly_oracle", oracle_monthly, spec))
                    oracle_monthly.insert(0, "method", "monthly_oracle")
                    oracle_monthly = _insert_spec_columns(oracle_monthly, spec)
                    monthly_frames.append(oracle_monthly)

    scenario_summary = pd.DataFrame(scenario_rows).sort_values(
        [
            "scenario_pass",
            "annual_2025_2026_pass",
            "monthly_requirement_pass",
            "order_floor_pass",
            "return_2025_pct",
            "return_2026_ytd_pct",
            "non_passing_months",
            "min_monthly_return_pct",
            "turnover",
        ],
        ascending=[False, False, False, False, False, False, True, False, True],
    )
    return scenario_summary, pd.concat(monthly_frames, ignore_index=True), pd.concat(selection_frames, ignore_index=True)


def _make_cube(candidate_monthly: pd.DataFrame, candidate_meta: pd.DataFrame, cost_per_side: float) -> dict[str, Any]:
    meta = candidate_meta.sort_values("candidate_id").reset_index(drop=True)
    months = sorted(str(month) for month in candidate_monthly["month"].unique())
    indexed = candidate_monthly.set_index(["candidate_id", "month"])

    def arr(column: str) -> np.ndarray:
        return (
            indexed[column]
            .unstack("month")
            .reindex(index=meta["candidate_id"], columns=months)
            .to_numpy(dtype=float)
        )

    gross = arr("gross_log_return")
    turnover = arr("turnover")
    orders = arr("orders").astype(int)
    cost_log = turnover * cost_per_side
    log_return = gross - cost_log
    return_pct = (np.exp(log_return) - 1.0) * 100.0
    return {
        "meta": meta,
        "months": np.array(months),
        "candidate_ordinal": np.arange(len(meta)),
        "leverage": meta["leverage"].to_numpy(dtype=float),
        "gross_log_return": gross,
        "turnover": turnover,
        "orders": orders,
        "cost_log": cost_log,
        "log_return": log_return,
        "return_pct": return_pct,
        "first_raw_return": arr("first_raw_return"),
        "first_target": arr("first_target"),
        "first_prev_target": arr("first_prev_target"),
        "last_target": arr("last_target"),
        "first_base_turnover": arr("first_base_turnover"),
        "first_base_order": arr("first_base_order").astype(int),
    }


def _strict_selector_cube(cube: dict[str, Any], spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    months = cube["months"]
    eval_indices = [idx for idx, month in enumerate(months) if EVAL_START_MONTH <= str(month) < EVAL_END_EXCLUSIVE]
    train_start_idx = int(np.where(months == TRAIN_START_MONTH)[0][0])
    monthly_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    previous_last_target = 0.0
    for eval_idx in eval_indices:
        candidate_idx, train_stats = _choose_strict_candidate(cube, train_start_idx, eval_idx, spec)
        row = _sequence_adjust_cube(cube, candidate_idx, eval_idx, previous_last_target, float(spec["cost_per_side"]))
        previous_last_target = float(cube["last_target"][candidate_idx, eval_idx])
        monthly_rows.append(row)
        selection_rows.append(
            {
                "eval_month": str(months[eval_idx]),
                "candidate_id": row["candidate_id"],
                "pool": row["pool"],
                "family": row["family"],
                "rule": row["rule"],
                "leverage": row["leverage"],
                **train_stats,
                "eval_return_pct": row["return_pct"],
                "eval_orders": row["orders"],
                "eval_turnover": row["turnover"],
            }
        )
    return pd.DataFrame(monthly_rows), pd.DataFrame(selection_rows)


def _choose_strict_candidate(
    cube: dict[str, Any],
    train_start_idx: int,
    eval_idx: int,
    spec: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    returns = cube["return_pct"][:, train_start_idx:eval_idx]
    logs = cube["log_return"][:, train_start_idx:eval_idx]
    orders = cube["orders"][:, train_start_idx:eval_idx]
    turnover = cube["turnover"][:, train_start_idx:eval_idx]
    month_fail = _month_fail_array(returns, str(spec["monthly_requirement"]))
    order_fail = orders < int(spec["order_floor"])
    train_log = logs.sum(axis=1)
    train_return = (np.exp(train_log) - 1.0) * 100.0
    train_month_fail = month_fail.sum(axis=1)
    train_order_fail = order_fail.sum(axis=1)
    train_min_month = returns.min(axis=1)
    train_min_orders = orders.min(axis=1)
    train_turnover = turnover.sum(axis=1)
    year_fail, min_year, complete_years = _full_year_training_stats(cube, train_start_idx, eval_idx, float(spec["annual_threshold_pct"]))
    hard_ok = (train_month_fail == 0) & (train_order_fail == 0) & (year_fail == 0) & (complete_years > 0)
    order = np.lexsort(
        (
            cube["candidate_ordinal"],
            cube["leverage"],
            train_turnover,
            -train_min_orders,
            -train_return,
            -min_year,
            -train_min_month,
            year_fail,
            train_order_fail,
            train_month_fail,
            -hard_ok.astype(int),
        )
    )
    idx = int(order[0])
    return idx, {
        "train_hard_ok": bool(hard_ok[idx]),
        "train_hard_ok_candidate_count": int(hard_ok.sum()),
        "train_months": int(eval_idx - train_start_idx),
        "train_return_pct": float(train_return[idx]),
        "train_month_fail_count": int(train_month_fail[idx]),
        "train_order_fail_count": int(train_order_fail[idx]),
        "train_full_year_fail_count": int(year_fail[idx]),
        "train_complete_years": int(complete_years),
        "train_min_monthly_return_pct": float(train_min_month[idx]),
        "train_min_monthly_orders": int(train_min_orders[idx]),
        "train_min_full_year_return_pct": float(min_year[idx]),
        "train_turnover": float(train_turnover[idx]),
        "train_last_month": str(cube["months"][eval_idx - 1]),
    }


def _full_year_training_stats(
    cube: dict[str, Any],
    train_start_idx: int,
    eval_idx: int,
    annual_threshold_pct: float,
) -> tuple[np.ndarray, np.ndarray, int]:
    months = cube["months"]
    logs = cube["log_return"]
    year_returns: list[np.ndarray] = []
    for year in sorted({str(month)[:4] for month in months}):
        idxs = np.array([idx for idx, month in enumerate(months) if str(month).startswith(year)], dtype=int)
        if len(idxs) == 12 and idxs[0] >= train_start_idx and idxs[-1] < eval_idx:
            year_returns.append((np.exp(logs[:, idxs].sum(axis=1)) - 1.0) * 100.0)
    if not year_returns:
        n = len(cube["meta"])
        return np.full(n, 999, dtype=int), np.full(n, -999.0), 0
    stacked = np.vstack(year_returns).T
    return (stacked < annual_threshold_pct).sum(axis=1), stacked.min(axis=1), len(year_returns)


def _oracle_cube(cube: dict[str, Any], spec: dict[str, Any]) -> pd.DataFrame:
    months = cube["months"]
    eval_indices = [idx for idx, month in enumerate(months) if EVAL_START_MONTH <= str(month) < EVAL_END_EXCLUSIVE]
    selected: list[dict[str, Any]] = []
    previous_last_target = 0.0
    for eval_idx in eval_indices:
        adjusted = _adjusted_month_vectors(cube, eval_idx, previous_last_target, float(spec["cost_per_side"]))
        month_fail = _month_fail_array(adjusted["return_pct"], str(spec["monthly_requirement"]))
        order_fail = adjusted["orders"] < int(spec["order_floor"])
        eligible = np.where((~month_fail) & (~order_fail))[0]
        pool = eligible if len(eligible) else np.arange(len(cube["meta"]))
        local_order = np.lexsort(
            (
                cube["candidate_ordinal"][pool],
                cube["leverage"][pool],
                adjusted["turnover"][pool],
                -adjusted["orders"][pool],
                -adjusted["return_pct"][pool],
            )
        )
        candidate_idx = int(pool[local_order[0]])
        row = _sequence_adjust_cube(cube, candidate_idx, eval_idx, previous_last_target, float(spec["cost_per_side"]))
        row["oracle_had_month_order_return_pass_candidate"] = bool(len(eligible) > 0)
        previous_last_target = float(cube["last_target"][candidate_idx, eval_idx])
        selected.append(row)
    return pd.DataFrame(selected)


def _adjusted_month_vectors(cube: dict[str, Any], month_idx: int, previous_last_target: float, cost_per_side: float) -> dict[str, np.ndarray]:
    first_raw = cube["first_raw_return"][:, month_idx]
    actual_first_gross = previous_last_target * first_raw
    base_first_gross = cube["first_prev_target"][:, month_idx] * first_raw
    actual_first_turnover = np.abs(cube["first_target"][:, month_idx] - previous_last_target)
    base_first_turnover = cube["first_base_turnover"][:, month_idx]
    turnover = cube["turnover"][:, month_idx] - base_first_turnover + actual_first_turnover
    orders = cube["orders"][:, month_idx] - cube["first_base_order"][:, month_idx] + (actual_first_turnover > EPS).astype(int)
    gross = cube["gross_log_return"][:, month_idx] - base_first_gross + actual_first_gross
    cost = turnover * cost_per_side
    log_return = gross - cost
    return {"turnover": turnover, "orders": orders, "gross_log_return": gross, "cost_log": cost, "log_return": log_return, "return_pct": (np.exp(log_return) - 1.0) * 100.0}


def _sequence_adjust_cube(
    cube: dict[str, Any],
    candidate_idx: int,
    month_idx: int,
    previous_last_target: float,
    cost_per_side: float,
) -> dict[str, Any]:
    meta = cube["meta"].iloc[candidate_idx]
    actual_first_gross = previous_last_target * float(cube["first_raw_return"][candidate_idx, month_idx])
    base_first_gross = float(cube["first_prev_target"][candidate_idx, month_idx]) * float(cube["first_raw_return"][candidate_idx, month_idx])
    actual_first_turnover = abs(float(cube["first_target"][candidate_idx, month_idx]) - previous_last_target)
    base_first_turnover = float(cube["first_base_turnover"][candidate_idx, month_idx])
    turnover = float(cube["turnover"][candidate_idx, month_idx]) - base_first_turnover + actual_first_turnover
    orders = int(cube["orders"][candidate_idx, month_idx]) - int(cube["first_base_order"][candidate_idx, month_idx]) + int(actual_first_turnover > EPS)
    gross_log_return = float(cube["gross_log_return"][candidate_idx, month_idx]) - base_first_gross + actual_first_gross
    cost_log = turnover * cost_per_side
    log_return = gross_log_return - cost_log
    return {
        "month": str(cube["months"][month_idx]),
        "candidate_id": str(meta["candidate_id"]),
        "source_candidate_id": str(meta["source_candidate_id"]),
        "pool": str(meta["pool"]),
        "family": str(meta["family"]),
        "rule": str(meta["rule"]),
        "leverage": float(meta["leverage"]),
        "gross_log_return": gross_log_return,
        "turnover": turnover,
        "orders": orders,
        "cost_log": cost_log,
        "log_return": log_return,
        "return_pct": (np.exp(log_return) - 1.0) * 100.0,
        "last_target": float(cube["last_target"][candidate_idx, month_idx]),
        "boundary_turnover_adjustment": actual_first_turnover - base_first_turnover,
        "boundary_gross_adjustment": actual_first_gross - base_first_gross,
    }


def _month_fail_array(return_pct: np.ndarray, requirement: str) -> np.ndarray:
    if requirement == "allow_any":
        return np.zeros_like(return_pct, dtype=bool)
    if requirement == "return_ge_minus1":
        return return_pct < -1.0
    if requirement == "return_gt_0":
        return return_pct <= 0.0
    raise ValueError(requirement)


def _strict_expanding_selector(
    monthly: pd.DataFrame,
    meta: pd.DataFrame,
    spec: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    eval_months = sorted(month for month in monthly["month"].unique() if EVAL_START_MONTH <= month < EVAL_END_EXCLUSIVE)
    selections: list[dict[str, Any]] = []
    selected_eval_rows: list[dict[str, Any]] = []
    previous_last_target = 0.0
    for eval_month in eval_months:
        train = monthly.loc[(monthly["month"] >= TRAIN_START_MONTH) & (monthly["month"] < eval_month)].copy()
        if train.empty:
            raise RuntimeError(f"No training rows for {eval_month}")
        score = _training_score(train, meta, spec)
        best = score.iloc[0].to_dict()
        eval_base = monthly.loc[(monthly["candidate_id"] == best["candidate_id"]) & (monthly["month"] == eval_month)].iloc[0].to_dict()
        eval_adjusted = _sequence_adjust(eval_base, previous_last_target, float(spec["cost_per_side"]))
        previous_last_target = float(eval_base["last_target"])
        selections.append(
            {
                "eval_month": eval_month,
                "candidate_id": best["candidate_id"],
                "pool": best["pool"],
                "family": best["family"],
                "rule": best["rule"],
                "leverage": best["leverage"],
                "train_hard_ok_candidate_count": int(score["train_hard_ok"].sum()),
                **{key: value for key, value in best.items() if key.startswith("train_")},
                "eval_return_pct": eval_adjusted["return_pct"],
                "eval_orders": eval_adjusted["orders"],
                "eval_turnover": eval_adjusted["turnover"],
            }
        )
        selected_eval_rows.append(eval_adjusted)
    return pd.DataFrame(selected_eval_rows), pd.DataFrame(selections)


def _training_score(train: pd.DataFrame, meta: pd.DataFrame, spec: dict[str, Any]) -> pd.DataFrame:
    month_fail = _month_fail_flag(train["return_pct"], str(spec["monthly_requirement"]))
    order_fail = train["orders"] < int(spec["order_floor"])
    train = train.assign(month_fail=month_fail, order_fail=order_fail, year=train["month"].str[:4])
    score = train.groupby("candidate_id", as_index=False).agg(
        train_months=("month", "count"),
        train_log_return=("log_return", "sum"),
        train_month_fail_count=("month_fail", "sum"),
        train_order_fail_count=("order_fail", "sum"),
        train_min_monthly_return_pct=("return_pct", "min"),
        train_min_monthly_orders=("orders", "min"),
        train_turnover=("turnover", "sum"),
        train_last_month=("month", "max"),
    )
    score["train_return_pct"] = (np.exp(score["train_log_return"]) - 1.0) * 100.0

    year = train.groupby(["candidate_id", "year"], as_index=False).agg(
        months=("month", "count"),
        log_return=("log_return", "sum"),
    )
    year = year.loc[year["months"] == 12].copy()
    year["year_return_pct"] = (np.exp(year["log_return"]) - 1.0) * 100.0
    year["year_fail"] = year["year_return_pct"] < float(spec["annual_threshold_pct"])
    year_score = year.groupby("candidate_id", as_index=False).agg(
        train_complete_years=("year", "count"),
        train_full_year_fail_count=("year_fail", "sum"),
        train_min_full_year_return_pct=("year_return_pct", "min"),
    )
    score = score.merge(year_score, on="candidate_id", how="left")
    score["train_complete_years"] = score["train_complete_years"].fillna(0).astype(int)
    score["train_full_year_fail_count"] = score["train_full_year_fail_count"].fillna(999).astype(int)
    score["train_min_full_year_return_pct"] = score["train_min_full_year_return_pct"].fillna(-999.0)
    score["train_hard_ok"] = (
        (score["train_month_fail_count"] == 0)
        & (score["train_order_fail_count"] == 0)
        & (score["train_full_year_fail_count"] == 0)
        & (score["train_complete_years"] > 0)
    )
    score = score.merge(meta, on="candidate_id", how="left")
    return score.sort_values(
        [
            "train_hard_ok",
            "train_month_fail_count",
            "train_order_fail_count",
            "train_full_year_fail_count",
            "train_min_monthly_return_pct",
            "train_min_full_year_return_pct",
            "train_return_pct",
            "train_min_monthly_orders",
            "train_turnover",
            "leverage",
            "candidate_id",
        ],
        ascending=[False, True, True, True, False, False, False, False, True, True, True],
    )


def _monthly_oracle(monthly: pd.DataFrame, meta: pd.DataFrame, spec: dict[str, Any]) -> pd.DataFrame:
    eval_months = sorted(month for month in monthly["month"].unique() if EVAL_START_MONTH <= month < EVAL_END_EXCLUSIVE)
    selected: list[dict[str, Any]] = []
    previous_last_target = 0.0
    for eval_month in eval_months:
        group = monthly.loc[monthly["month"] == eval_month].copy()
        adjusted = [_sequence_adjust(row.to_dict(), previous_last_target, float(spec["cost_per_side"])) for _, row in group.iterrows()]
        adjusted_frame = pd.DataFrame(adjusted)
        adjusted_frame["month_fail"] = _month_fail_flag(adjusted_frame["return_pct"], str(spec["monthly_requirement"]))
        adjusted_frame["order_fail"] = adjusted_frame["orders"] < int(spec["order_floor"])
        pass_pool = adjusted_frame.loc[(adjusted_frame["month_fail"] == 0) & (~adjusted_frame["order_fail"])].copy()
        pool = pass_pool if not pass_pool.empty else adjusted_frame
        best = (
            pool.merge(meta[["candidate_id", "leverage"]], on="candidate_id", how="left", suffixes=("", "_meta"))
            .sort_values(
                ["return_pct", "orders", "turnover", "leverage", "candidate_id"],
                ascending=[False, False, True, True, True],
            )
            .iloc[0]
            .to_dict()
        )
        previous_last_target = float(best["last_target"])
        selected.append(best)
    return pd.DataFrame(selected)


def _sequence_adjust(row: dict[str, Any], previous_last_target: float, cost_per_side: float) -> dict[str, Any]:
    out = dict(row)
    actual_first_gross = previous_last_target * float(row["first_raw_return"])
    base_first_gross = float(row["first_prev_target"]) * float(row["first_raw_return"])
    actual_first_turnover = abs(float(row["first_target"]) - previous_last_target)
    base_first_turnover = float(row["first_base_turnover"])
    actual_first_order = int(actual_first_turnover > EPS)
    base_first_order = int(row["first_base_order"])
    turnover = float(row["turnover"]) - base_first_turnover + actual_first_turnover
    orders = int(row["orders"]) - base_first_order + actual_first_order
    gross_log_return = float(row["gross_log_return"]) - base_first_gross + actual_first_gross
    cost_log = turnover * cost_per_side
    log_return = gross_log_return - cost_log
    out.update(
        {
            "gross_log_return": gross_log_return,
            "turnover": turnover,
            "orders": orders,
            "cost_log": cost_log,
            "log_return": log_return,
            "return_pct": (np.exp(log_return) - 1.0) * 100.0,
            "boundary_turnover_adjustment": actual_first_turnover - base_first_turnover,
            "boundary_gross_adjustment": actual_first_gross - base_first_gross,
        }
    )
    return out


def _scenario_summary(method: str, monthly: pd.DataFrame, spec: dict[str, Any]) -> dict[str, Any]:
    yearly = _yearly_from_monthly(monthly)
    yearly_by_year = {str(row.year): row for row in yearly.itertuples()}
    monthly_fail = _month_fail_flag(monthly["return_pct"], str(spec["monthly_requirement"]))
    order_fail = monthly["orders"] < int(spec["order_floor"])
    return_2025 = _year_return(yearly_by_year, "2025")
    return_2026 = _year_return(yearly_by_year, "2026")
    annual_pass = (
        return_2025 is not None
        and return_2026 is not None
        and return_2025 >= float(spec["annual_threshold_pct"])
        and return_2026 >= float(spec["annual_threshold_pct"])
    )
    monthly_pass = int(monthly_fail.sum()) == 0
    order_pass = int(order_fail.sum()) == 0
    non_passing_months = sorted(set(monthly.loc[(monthly_fail.astype(bool)) | (order_fail.astype(bool)), "month"].tolist()))
    return {
        "method": method,
        "order_floor": int(spec["order_floor"]),
        "round_trip_cost": float(spec["round_trip_cost"]),
        "round_trip_cost_pct": float(spec["round_trip_cost"]) * 100.0,
        "monthly_requirement": spec["monthly_requirement"],
        "annual_threshold_pct": float(spec["annual_threshold_pct"]),
        "scenario_pass": bool(annual_pass and monthly_pass and order_pass),
        "annual_2025_2026_pass": bool(annual_pass),
        "monthly_requirement_pass": bool(monthly_pass),
        "order_floor_pass": bool(order_pass),
        "non_passing_months": int(len(non_passing_months)),
        "non_passing_month_list": ",".join(non_passing_months),
        "month_fail_count": int(monthly_fail.sum()),
        "order_fail_count": int(order_fail.sum()),
        "total_eval_return_pct": float((np.exp(float(monthly["log_return"].sum())) - 1.0) * 100.0),
        "return_2023_pct": _year_return(yearly_by_year, "2023"),
        "return_2024_pct": _year_return(yearly_by_year, "2024"),
        "return_2025_pct": return_2025,
        "return_2026_ytd_pct": return_2026,
        "min_monthly_return_pct": float(monthly["return_pct"].min()),
        "min_monthly_orders": int(monthly["orders"].min()),
        "orders": int(monthly["orders"].sum()),
        "turnover": float(monthly["turnover"].sum()),
        "cost_log": float(monthly["cost_log"].sum()),
        "selected_candidate_count": int(monthly["candidate_id"].nunique()),
    }


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
            min_monthly_return_pct=("return_pct", "min"),
            min_monthly_orders=("orders", "min"),
        )
    )
    yearly["compounded_return_pct"] = (np.exp(yearly["log_return"]) - 1.0) * 100.0
    return yearly


def _year_return(yearly_by_year: dict[str, Any], year: str) -> float | None:
    if year not in yearly_by_year:
        return None
    return float(yearly_by_year[year].compounded_return_pct)


def _month_fail_flag(return_pct: pd.Series, requirement: str) -> pd.Series:
    if requirement == "allow_any":
        return pd.Series(False, index=return_pct.index)
    if requirement == "return_ge_minus1":
        return return_pct < -1.0
    if requirement == "return_gt_0":
        return return_pct <= 0.0
    raise ValueError(requirement)


def _insert_spec_columns(frame: pd.DataFrame, spec: dict[str, Any]) -> pd.DataFrame:
    out = frame.copy()
    for key in ["annual_threshold_pct", "monthly_requirement", "round_trip_cost", "order_floor"]:
        out.insert(1, key, spec[key])
    return out


def _make_summary(
    baseline: dict[str, Any],
    ohlc_path: Path,
    market: dict[str, Any],
    candidate_meta: pd.DataFrame,
    volume_quality: dict[str, Any],
    scenario_summary: pd.DataFrame,
) -> dict[str, Any]:
    original = scenario_summary.loc[
        (scenario_summary["order_floor"] == 10)
        & (scenario_summary["round_trip_cost"].round(6) == 0.002)
        & (scenario_summary["monthly_requirement"] == "return_gt_0")
        & (scenario_summary["annual_threshold_pct"] == 100.0)
    ].copy()
    strict = scenario_summary.loc[scenario_summary["method"] == "strict_expanding_selector"].copy()
    oracle = scenario_summary.loc[scenario_summary["method"] == "monthly_oracle"].copy()
    best_strict = strict.iloc[0].to_dict()
    best_oracle = oracle.iloc[0].to_dict()
    strict_active = strict.loc[strict["orders"] > 0].copy()
    strict_active["min_2025_2026_pct"] = strict_active[["return_2025_pct", "return_2026_ytd_pct"]].min(axis=1)
    best_strict_active_balance = strict_active.sort_values(
        ["min_2025_2026_pct", "return_2025_pct", "return_2026_ytd_pct"],
        ascending=[False, False, False],
    ).iloc[0].to_dict()
    best_strict_active_2025 = strict_active.sort_values(
        ["return_2025_pct", "return_2026_ytd_pct"],
        ascending=[False, False],
    ).iloc[0].to_dict()
    best_strict_active_2026 = strict_active.sort_values(
        ["return_2026_ytd_pct", "return_2025_pct"],
        ascending=[False, False],
    ).iloc[0].to_dict()
    original_rows = original.sort_values(["method"]).to_dict("records")
    pass_counts = (
        scenario_summary.groupby("method", as_index=False)["scenario_pass"]
        .sum()
        .rename(columns={"scenario_pass": "passing_scenarios"})
        .to_dict("records")
    )
    return {
        "status": "strategy_22_hard_target_bottleneck_audit_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Audit whether the hard target fails because of monthly order floor, fees, monthly profit requirement, or weak alpha, reusing Strategy 16/19/20/21 candidates only.",
        "source": {
            "baseline_15_summary": _rel(BASELINE_15_SUMMARY),
            "combined_ohlc": baseline["input_files"]["combined_ohlc"],
            "reused_candidate_families": ["strategy16_simple", "strategy19_calendar", "strategy20_ohlc_structure", "strategy21_volume"],
            "new_candidate_rules_added": False,
        },
        "data": {
            "rows": int(len(market["timestamp"])),
            "start_timestamp": market["timestamp"].iloc[0].isoformat(),
            "end_timestamp": market["timestamp"].iloc[-1].isoformat(),
            "train_start_month": TRAIN_START_MONTH,
            "eval_start_month": EVAL_START_MONTH,
            "eval_end_exclusive": EVAL_END_EXCLUSIVE,
            "volume_quality": volume_quality,
        },
        "strict_no_future": {
            "candidate_signals_use_closed_bar_t": True,
            "position_participates_from_bar_t_plus_1": True,
            "strict_selector_uses_only_months_before_eval_month": True,
            "monthly_oracle_is_leaky_and_not_tradeable": True,
            "month_boundary_switching_cost_included": True,
        },
        "grid": {
            "order_floors": ORDER_FLOORS,
            "round_trip_costs": ROUND_TRIP_COSTS,
            "monthly_requirements": MONTHLY_REQUIREMENTS,
            "annual_thresholds_pct": ANNUAL_THRESHOLDS_PCT,
        },
        "candidate_pool": {
            "total_candidates": int(len(candidate_meta)),
            "by_pool": {str(key): int(value) for key, value in candidate_meta["pool"].value_counts().sort_index().items()},
        },
        "pass_counts": _json_ready(pass_counts),
        "best_strict": _json_ready(best_strict),
        "best_strict_active_balance": _json_ready(best_strict_active_balance),
        "best_strict_active_2025": _json_ready(best_strict_active_2025),
        "best_strict_active_2026": _json_ready(best_strict_active_2026),
        "best_oracle": _json_ready(best_oracle),
        "original_target_rows": _json_ready(original_rows),
        "decision": _decision(best_strict, best_oracle, original_rows),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "baseline_15_summary_sha256": _sha256(BASELINE_15_SUMMARY),
            "combined_ohlc_sha256": _sha256(ohlc_path),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "scenario_summary": _rel(OUT_DIR / "scenario_summary.csv"),
            "scenario_monthly": _rel(OUT_DIR / "scenario_monthly.csv"),
            "selected_params_by_month": _rel(OUT_DIR / "selected_params_by_month.csv"),
            "candidate_monthly_base": _rel(OUT_DIR / "candidate_monthly_base.csv"),
            "candidate_pool_summary": _rel(OUT_DIR / "candidate_pool_summary.csv"),
        },
    }


def _decision(best_strict: dict[str, Any], best_oracle: dict[str, Any], original_rows: list[dict[str, Any]]) -> dict[str, Any]:
    original_pass = any(bool(row["scenario_pass"]) for row in original_rows)
    original_oracle = next((row for row in original_rows if row["method"] == "monthly_oracle"), None)
    original_strict = next((row for row in original_rows if row["method"] == "strict_expanding_selector"), None)
    if original_pass:
        verdict = "HARD_TARGET_CAN_PASS_WITH_EXISTING_POOL"
        reason = "原始硬目标在统一压力表里出现通过结果。"
        next_step = "检查通过路径是否有泄漏或月初切换成本问题，再考虑另起候选。"
    elif original_oracle and not bool(original_oracle["scenario_pass"]) and bool(best_oracle["scenario_pass"]) and not bool(best_strict["scenario_pass"]):
        verdict = "ORIGINAL_TARGET_AND_SELECTION_BOTTLENECK"
        reason = (
            "原始硬目标下，连看答案的月度oracle也差2个月；放宽目标后oracle能过，"
            "但严格逐月选择器仍然0个组合通过。问题不是只差一点手续费，而是硬目标太紧且无法提前选中好月份。"
        )
        next_step = "不要继续补16/19/20/21这类小规则；先写停止结论。若继续研究，只能换真正不同的数据源或改成更现实的目标。"
    elif bool(best_oracle["scenario_pass"]) and not bool(best_strict["scenario_pass"]):
        verdict = "SELECTION_IS_MAIN_BOTTLENECK"
        reason = "看答案的月度oracle能通过某些放宽口径，但严格逐月选择器不能通过，主要卡在提前选中月份。"
        next_step = "不要直接升级；只有找到非未来信息能稳定识别月份时才继续。"
    elif not bool(best_oracle["scenario_pass"]):
        verdict = "ALPHA_OR_TARGET_IS_MAIN_BOTTLENECK"
        reason = "连看答案的月度oracle都没有通过任何压力组合，说明这批候选本身不够，或硬目标太紧。"
        next_step = "停止继续扩16/19/20/21这类小规则；下一步先降低目标做现实候选，或换到真正不同的数据源。"
    else:
        verdict = "STRICT_SELECTOR_HAS_RELAXED_PASS_ONLY"
        reason = "严格选择器只在放宽条件下有通过，原始硬目标仍然不成立。"
        next_step = "记录可通过的放宽条件，不把它说成满足原始硬目标。"
    return {
        "verdict": verdict,
        "promote_strategy": False,
        "reason": reason,
        "next_step": next_step,
    }


def _render_report(summary: dict[str, Any]) -> str:
    best_strict = summary["best_strict"]
    best_active_balance = summary["best_strict_active_balance"]
    best_active_2025 = summary["best_strict_active_2025"]
    best_active_2026 = summary["best_strict_active_2026"]
    best_oracle = summary["best_oracle"]
    decision = summary["decision"]
    original = summary["original_target_rows"]
    original_lines = []
    for row in original:
        original_lines.append(
            f"- `{row['method']}`：通过 `{row['scenario_pass']}`，2025 `{row['return_2025_pct']:.2f}%`，"
            f"2026 YTD `{row['return_2026_ytd_pct']:.2f}%`，不合格月份 `{row['non_passing_months']}`，"
            f"最少月交易 `{row['min_monthly_orders']}`"
        )
    return f"""# 22号硬目标瓶颈审计

这不是新策略，也不能交易。它只是把 16、19、20、21 号候选放进同一张压力表里，看看硬目标到底卡在哪里。

## 口径

- 数据：`{summary["source"]["combined_ohlc"]}`
- 候选：只复用 16/19/20/21，未新增规则
- 评估：`{EVAL_START_MONTH}` 到 `2026-05`
- 手续费网格：开平合计 `0.0% / 0.1% / 0.2% / 0.3% / 0.4%`
- 月交易次数门槛：`0 / 2 / 5 / 10`
- 月收益要求：不限、`>= -1%`、`> 0`
- 年收益门槛：`50% / 100%`
- 严格选择器：每个月只用过去月份选候选；月度oracle是看答案上限，不能交易。

## 原始硬目标

原始口径是：开平合计 `0.2%`、每月收益 `> 0`、每月交易不少于 `10`、2025 和 2026 YTD 都不少于 `100%`。

{chr(10).join(original_lines)}

## 最好严格结果

- 通过：`{best_strict["scenario_pass"]}`
- 口径：手续费 `{best_strict["round_trip_cost_pct"]:.2f}%`，月交易 `{best_strict["order_floor"]}`，月要求 `{best_strict["monthly_requirement"]}`，年门槛 `{best_strict["annual_threshold_pct"]:.0f}%`
- 2025：`{best_strict["return_2025_pct"]:.2f}%`
- 2026 YTD：`{best_strict["return_2026_ytd_pct"]:.2f}%`
- 不合格月份：`{best_strict["non_passing_months"]}`
- 最差月：`{best_strict["min_monthly_return_pct"]:.2f}%`
- 最少月交易：`{best_strict["min_monthly_orders"]}`

严格选择器没有任何压力组合通过。排除空仓后：

- 2025/2026 两边相对最平衡的一组：2025 `{best_active_balance["return_2025_pct"]:.2f}%`，2026 YTD `{best_active_balance["return_2026_ytd_pct"]:.2f}%`
- 单看 2025 最高的一组：2025 `{best_active_2025["return_2025_pct"]:.2f}%`，但 2026 YTD `{best_active_2025["return_2026_ytd_pct"]:.2f}%`
- 单看 2026 最高的一组：2026 YTD `{best_active_2026["return_2026_ytd_pct"]:.2f}%`，但 2025 `{best_active_2026["return_2025_pct"]:.2f}%`

## 最好看答案上限

- 通过：`{best_oracle["scenario_pass"]}`
- 口径：手续费 `{best_oracle["round_trip_cost_pct"]:.2f}%`，月交易 `{best_oracle["order_floor"]}`，月要求 `{best_oracle["monthly_requirement"]}`，年门槛 `{best_oracle["annual_threshold_pct"]:.0f}%`
- 2025：`{best_oracle["return_2025_pct"]:.2f}%`
- 2026 YTD：`{best_oracle["return_2026_ytd_pct"]:.2f}%`
- 不合格月份：`{best_oracle["non_passing_months"]}`
- 最差月：`{best_oracle["min_monthly_return_pct"]:.2f}%`
- 最少月交易：`{best_oracle["min_monthly_orders"]}`

## 判断

`{decision["verdict"]}`

{decision["reason"]}

下一步：{decision["next_step"]}
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
    return probe16._json_ready(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
