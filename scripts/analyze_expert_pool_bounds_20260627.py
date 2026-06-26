from __future__ import annotations

import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import search_online_expert_pool_20260627 as source_pool  # noqa: E402


OUT_DIR = ROOT / "artifacts" / "expert_pool_bounds_20260627"
LEVERAGES = [1.0, 2.0, 4.0, 8.0]
TRAILING_WINDOWS = [1, 2, 3, 6, 12]
CALIBRATION_DAYS = [7, 10, 14, 15]

COST_PER_SIDE = source_pool.COST_PER_SIDE
REQUIRED_RETURN_PCT = source_pool.REQUIRED_RETURN_PCT
REQUIRED_MIN_MONTHLY_ORDERS = source_pool.REQUIRED_MIN_MONTHLY_ORDERS
EVAL_YEARS = source_pool.EVAL_YEARS


@dataclass(frozen=True)
class Unit:
    unit_index: int
    unit_id: str
    expert_index: int
    expert_name: str
    leverage: float
    params: dict[str, Any]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    source = source_pool._load_features(source_pool.FEATURE_FRAME)
    features = source_pool._add_features(source)
    market = source_pool._market(features)
    experts = source_pool._expert_pool(features)
    target_matrix = np.vstack([expert.target for expert in experts]).astype(np.int8)
    units = _build_units(experts)

    precomputed = _precompute_units(units, target_matrix, market)
    static_scan = pd.DataFrame(precomputed["static_rows"]).sort_values(
        _sort_columns(), ascending=_sort_ascending()
    )
    static_scan.to_csv(OUT_DIR / "static_single_expert_scan.csv", index=False)

    best_static_unit = int(static_scan.iloc[0]["unit_index"])
    static_payload = _payload_for_unit(
        "static_single_expert_best",
        units[best_static_unit],
        target_matrix,
        market,
        strict_no_future=True,
        posthoc_selection=True,
    )
    _write_payload("static_single_expert_best", static_payload)

    oracle_choices = _monthly_oracle_choices(
        precomputed["month_log_reset"],
        precomputed["month_orders_reset"],
    )
    oracle_payload = _payload_for_choices(
        "monthly_posthoc_best_oracle",
        "monthly_posthoc_best_oracle",
        oracle_choices,
        units,
        target_matrix,
        market,
        strict_no_future=False,
        posthoc_selection=True,
        notes="Each month chooses the best expert+leverage after seeing that month.",
    )
    _write_payload("monthly_posthoc_best_oracle", oracle_payload)

    selector_rows: list[dict[str, Any]] = [oracle_payload["row"]]
    best_strict_payload: dict[str, Any] | None = None
    for window in TRAILING_WINDOWS:
        for require_past_orders in [False, True]:
            choices = _trailing_winner_choices(
                precomputed["month_log_reset"],
                precomputed["month_orders_reset"],
                window,
                require_past_orders,
            )
            selector_id = (
                f"strict_trailing_{window}m_winner"
                + ("_past_orders10" if require_past_orders else "")
            )
            payload = _payload_for_choices(
                selector_id,
                "strict_trailing_winner",
                choices,
                units,
                target_matrix,
                market,
                strict_no_future=True,
                posthoc_selection=False,
                notes=(
                    f"Uses only the previous {window} month(s); "
                    f"past order gate={require_past_orders}."
                ),
            )
            selector_rows.append(payload["row"])
            if _is_better(payload["row"], best_strict_payload["row"] if best_strict_payload else None):
                best_strict_payload = payload

    for days in CALIBRATION_DAYS:
        choices = _calibration_choices(precomputed["calibration_log"][days])
        selector_id = f"strict_first_{days}d_calibrate_trade_rest"
        payload = _payload_for_choices(
            selector_id,
            "strict_first_days_calibration",
            choices,
            units,
            target_matrix,
            market,
            strict_no_future=True,
            posthoc_selection=False,
            trade_after_day=days,
            notes=f"Chooses after the first {days} calendar day(s), then trades the rest of that month.",
        )
        selector_rows.append(payload["row"])
        if _is_better(payload["row"], best_strict_payload["row"] if best_strict_payload else None):
            best_strict_payload = payload

    selector_scan = pd.DataFrame(selector_rows).sort_values(_sort_columns(), ascending=_sort_ascending())
    selector_scan.to_csv(OUT_DIR / "selector_bounds_scan.csv", index=False)

    if best_strict_payload is not None:
        _write_payload("best_strict_tradeable", best_strict_payload)

    summary = _summary(
        source=source,
        experts=experts,
        units=units,
        static_payload=static_payload,
        oracle_payload=oracle_payload,
        best_strict_payload=best_strict_payload,
        selector_scan=selector_scan,
    )
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _build_units(experts: list[source_pool.Expert]) -> list[Unit]:
    units: list[Unit] = []
    for expert_index, expert in enumerate(experts):
        for leverage in LEVERAGES:
            unit_index = len(units)
            unit_id = f"expert_{expert_index:04d}_{expert.name}_lev{leverage:g}"
            units.append(
                Unit(
                    unit_index=unit_index,
                    unit_id=unit_id,
                    expert_index=expert_index,
                    expert_name=expert.name,
                    leverage=leverage,
                    params=expert.params,
                )
            )
    return units


def _precompute_units(
    units: list[Unit],
    target_matrix: np.ndarray,
    market: dict[str, Any],
) -> dict[str, Any]:
    month_count = len(market["month_starts"])
    unit_count = len(units)
    month_log_reset = np.zeros((unit_count, month_count), dtype=np.float64)
    month_orders_reset = np.zeros((unit_count, month_count), dtype=np.int32)
    calibration_log = {
        days: np.zeros((unit_count, month_count), dtype=np.float64) for days in CALIBRATION_DAYS
    }

    starts = market["month_starts"]
    timestamp = pd.to_datetime(market["timestamp"], utc=True)
    day_of_month = timestamp.dt.day.to_numpy()
    calibration_masks = {days: day_of_month <= days for days in CALIBRATION_DAYS}

    static_rows: list[dict[str, Any]] = []
    for unit in units:
        target = target_matrix[unit.expert_index]
        position = target.astype(np.float64) * unit.leverage

        arrays = _arrays_from_position(position, market["raw_return"])
        row = _row_from_arrays(
            "static_single_expert",
            "static_single_expert",
            arrays,
            market,
            strict_no_future=True,
            posthoc_selection=True,
            unit=unit,
            notes="Single expert+leverage held for the whole backtest; best row is selected after the scan.",
        )
        static_rows.append(row)

        reset_arrays = _arrays_from_position(position, market["raw_return"], reset_indexes=starts)
        month_log_reset[unit.unit_index] = np.add.reduceat(reset_arrays["strategy_log_return"], starts)
        month_orders_reset[unit.unit_index] = np.add.reduceat(reset_arrays["order_count"], starts)
        for days, mask in calibration_masks.items():
            calibration_log[days][unit.unit_index] = np.add.reduceat(
                np.where(mask, reset_arrays["strategy_log_return"], 0.0), starts
            )

    return {
        "static_rows": static_rows,
        "month_log_reset": month_log_reset,
        "month_orders_reset": month_orders_reset,
        "calibration_log": calibration_log,
    }


def _monthly_oracle_choices(month_log_reset: np.ndarray, month_orders_reset: np.ndarray) -> np.ndarray:
    choices = np.zeros(month_log_reset.shape[1], dtype=np.int32)
    for month_index in range(month_log_reset.shape[1]):
        valid = month_orders_reset[:, month_index] >= REQUIRED_MIN_MONTHLY_ORDERS
        scores = month_log_reset[:, month_index]
        if valid.any():
            valid_indexes = np.flatnonzero(valid)
            choices[month_index] = int(valid_indexes[np.argmax(scores[valid_indexes])])
        else:
            choices[month_index] = int(np.argmax(scores))
    return choices


def _trailing_winner_choices(
    month_log_reset: np.ndarray,
    month_orders_reset: np.ndarray,
    window: int,
    require_past_orders: bool,
) -> np.ndarray:
    month_count = month_log_reset.shape[1]
    choices = np.full(month_count, -1, dtype=np.int32)
    for month_index in range(month_count):
        start = max(0, month_index - window)
        if start == month_index:
            continue
        scores = month_log_reset[:, start:month_index].sum(axis=1)
        if require_past_orders:
            valid = (month_orders_reset[:, start:month_index] >= REQUIRED_MIN_MONTHLY_ORDERS).all(axis=1)
            if valid.any():
                valid_indexes = np.flatnonzero(valid)
                choices[month_index] = int(valid_indexes[np.argmax(scores[valid_indexes])])
                continue
        choices[month_index] = int(np.argmax(scores))
    return choices


def _calibration_choices(calibration_log: np.ndarray) -> np.ndarray:
    return np.argmax(calibration_log, axis=0).astype(np.int32)


def _payload_for_unit(
    selector_id: str,
    unit: Unit,
    target_matrix: np.ndarray,
    market: dict[str, Any],
    strict_no_future: bool,
    posthoc_selection: bool,
) -> dict[str, Any]:
    target = target_matrix[unit.expert_index].copy()
    leverage = np.full(len(target), unit.leverage, dtype=np.float64)
    arrays = _arrays_from_position(target.astype(np.float64) * leverage, market["raw_return"])
    arrays["target"] = target
    arrays["leverage"] = leverage
    arrays["selected_unit"] = np.full(len(target), unit.unit_index, dtype=np.int32)
    row = _row_from_arrays(
        selector_id,
        "static_single_expert",
        arrays,
        market,
        strict_no_future=strict_no_future,
        posthoc_selection=posthoc_selection,
        unit=unit,
        notes="Best static expert+leverage selected after the full historical scan.",
    )
    return _payload(selector_id, row, arrays, market, [unit.unit_index], None)


def _payload_for_choices(
    selector_id: str,
    family: str,
    choices: np.ndarray,
    units: list[Unit],
    target_matrix: np.ndarray,
    market: dict[str, Any],
    strict_no_future: bool,
    posthoc_selection: bool,
    notes: str,
    trade_after_day: int | None = None,
) -> dict[str, Any]:
    target, leverage, selected_unit = _target_from_choices(
        choices, units, target_matrix, market, trade_after_day=trade_after_day
    )
    arrays = _arrays_from_position(target.astype(np.float64) * leverage, market["raw_return"])
    arrays["target"] = target
    arrays["leverage"] = leverage
    arrays["selected_unit"] = selected_unit
    row = _row_from_arrays(
        selector_id,
        family,
        arrays,
        market,
        strict_no_future=strict_no_future,
        posthoc_selection=posthoc_selection,
        unit=None,
        notes=notes,
    )
    choices_frame = _choices_frame(choices, units, market, trade_after_day)
    return _payload(selector_id, row, arrays, market, choices, choices_frame)


def _target_from_choices(
    choices: np.ndarray,
    units: list[Unit],
    target_matrix: np.ndarray,
    market: dict[str, Any],
    trade_after_day: int | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(market["raw_return"])
    target = np.zeros(n, dtype=np.int8)
    leverage = np.zeros(n, dtype=np.float64)
    selected_unit = np.full(n, -1, dtype=np.int32)
    starts = market["month_starts"]
    ends = np.r_[starts[1:], n]
    days = pd.to_datetime(market["timestamp"], utc=True).dt.day.to_numpy()

    for month_index, (start, end) in enumerate(zip(starts, ends)):
        unit_index = int(choices[month_index])
        if unit_index < 0:
            continue
        unit = units[unit_index]
        indexes = np.arange(start, end)
        if trade_after_day is not None:
            indexes = indexes[days[start:end] > trade_after_day]
        if len(indexes) == 0:
            continue
        target[indexes] = target_matrix[unit.expert_index, indexes]
        leverage[indexes] = unit.leverage
        selected_unit[indexes] = unit.unit_index
    return target, leverage, selected_unit


def _arrays_from_position(
    position: np.ndarray,
    raw_return: np.ndarray,
    reset_indexes: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    previous_position = np.r_[0.0, position[:-1]]
    if reset_indexes is not None:
        previous_position = previous_position.copy()
        previous_position[reset_indexes] = 0.0
    turnover = np.abs(position - previous_position)
    order_count = _order_count(previous_position, position)
    strategy_log_return = previous_position * raw_return - turnover * COST_PER_SIDE
    cumulative_log_return = np.cumsum(strategy_log_return)
    equity = np.exp(np.clip(cumulative_log_return, -745.0, 700.0))
    drawdown = np.exp(np.clip(cumulative_log_return - np.maximum.accumulate(cumulative_log_return), -745.0, 0.0)) - 1.0
    return {
        "position": position,
        "active_position": previous_position,
        "turnover": turnover,
        "order_count": order_count,
        "strategy_log_return": strategy_log_return,
        "cumulative_log_return": cumulative_log_return,
        "equity": equity,
        "drawdown": drawdown,
    }


def _order_count(previous_position: np.ndarray, position: np.ndarray) -> np.ndarray:
    changed = ~np.isclose(previous_position, position)
    previous_sign = np.sign(previous_position)
    current_sign = np.sign(position)
    same_side_or_flat = (previous_sign == current_sign) | (previous_sign == 0) | (current_sign == 0)
    orders = np.zeros(len(position), dtype=np.int32)
    orders[changed & same_side_or_flat] = 1
    orders[changed & ~same_side_or_flat] = 2
    return orders


def _row_from_arrays(
    selector_id: str,
    family: str,
    arrays: dict[str, np.ndarray],
    market: dict[str, Any],
    strict_no_future: bool,
    posthoc_selection: bool,
    unit: Unit | None,
    notes: str,
) -> dict[str, Any]:
    month_log = np.add.reduceat(arrays["strategy_log_return"], market["month_starts"])
    month_orders = np.add.reduceat(arrays["order_count"], market["month_starts"])
    eval_log = month_log[market["eval_month_mask"]]
    eval_orders = month_orders[market["eval_month_mask"]]
    year_log = np.add.reduceat(arrays["strategy_log_return"], market["year_starts"])
    year_map = {
        str(label): _return_pct(log_value)
        for label, log_value in zip(market["year_labels"], year_log)
    }
    y2025 = year_map.get("2025")
    y2026 = year_map.get("2026")
    monthly_return_pct = np.array([_return_pct(value) for value in eval_log]) if len(eval_log) else np.array([])
    hard_pass = bool(
        y2025 is not None
        and y2026 is not None
        and y2025 > REQUIRED_RETURN_PCT
        and y2026 > REQUIRED_RETURN_PCT
        and len(monthly_return_pct) > 0
        and float(np.nanmin(monthly_return_pct)) > 0.0
        and int(eval_orders.min()) >= REQUIRED_MIN_MONTHLY_ORDERS
    )
    returns = arrays["strategy_log_return"]
    return_std = float(np.std(returns, ddof=1))
    active_returns = returns[np.abs(arrays["active_position"]) > 0]
    losses = float(active_returns[active_returns < 0].sum())
    gains = float(active_returns[active_returns > 0].sum())
    selected = arrays.get("selected_unit")
    unique_units = int(len(set(int(value) for value in selected if value >= 0))) if selected is not None else 1
    return {
        "selector_id": selector_id,
        "family": family,
        "strict_no_future": strict_no_future,
        "posthoc_selection": posthoc_selection,
        "hard_pass": hard_pass,
        "return_2025_pct": y2025,
        "return_2026_pct": y2026,
        "min_required_year_return_pct": min(y2025 if y2025 is not None else -999.0, y2026 if y2026 is not None else -999.0),
        "min_monthly_return_pct": float(np.nanmin(monthly_return_pct)) if len(monthly_return_pct) else None,
        "losing_eval_months": int((monthly_return_pct <= 0).sum()) if len(monthly_return_pct) else None,
        "min_monthly_orders": int(eval_orders.min()) if len(eval_orders) else None,
        "total_return_pct": _return_pct(float(arrays["cumulative_log_return"][-1])),
        "max_drawdown_pct": float(np.nanmin(arrays["drawdown"]) * 100.0),
        "annualized_sharpe": float(0.0 if return_std == 0 else returns.mean() / return_std * math.sqrt(365 * 24 * 4)),
        "exposure_pct": float((np.abs(arrays["active_position"]) > 0).mean() * 100.0),
        "turnover": float(arrays["turnover"].sum()),
        "orders": int(arrays["order_count"].sum()),
        "unique_units_used": unique_units,
        "unit_index": unit.unit_index if unit else None,
        "unit_id": unit.unit_id if unit else None,
        "expert_index": unit.expert_index if unit else None,
        "expert_name": unit.expert_name if unit else None,
        "leverage": unit.leverage if unit else None,
        "win_rate_pct": float(0.0 if len(active_returns) == 0 else (active_returns > 0).mean() * 100.0),
        "profit_factor": float("inf") if losses == 0 and gains > 0 else float(gains / abs(losses) if losses != 0 else 0.0),
        "notes": notes,
    }


def _payload(
    selector_id: str,
    row: dict[str, Any],
    arrays: dict[str, np.ndarray],
    market: dict[str, Any],
    choices: Any,
    choices_frame: pd.DataFrame | None,
) -> dict[str, Any]:
    equity = _equity_frame(arrays, market)
    monthly = _monthly_frame(arrays, market)
    yearly = _yearly_frame(monthly)
    signals = pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "close": market["close"],
            "target_position": arrays["target"].astype(float),
            "leverage": arrays["leverage"],
            "selected_unit": arrays["selected_unit"],
            "candidate_version": selector_id,
        }
    )
    return {
        "row": row,
        "equity": equity,
        "monthly": monthly,
        "yearly": yearly,
        "signals": signals,
        "choices": choices_frame,
    }


def _equity_frame(arrays: dict[str, np.ndarray], market: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "close": market["close"],
            "position": arrays["position"],
            "active_position": arrays["active_position"],
            "turnover": arrays["turnover"],
            "order_count": arrays["order_count"],
            "cost": arrays["turnover"] * COST_PER_SIDE,
            "strategy_log_return": arrays["strategy_log_return"],
            "equity": arrays["equity"],
            "drawdown": arrays["drawdown"],
            "target_position": arrays["target"],
            "leverage": arrays["leverage"],
            "selected_unit": arrays["selected_unit"],
        }
    )


def _monthly_frame(arrays: dict[str, np.ndarray], market: dict[str, Any]) -> pd.DataFrame:
    starts = market["month_starts"]
    monthly = pd.DataFrame(
        {
            "month": market["month_labels"],
            "log_return": np.add.reduceat(arrays["strategy_log_return"], starts),
            "turnover": np.add.reduceat(arrays["turnover"], starts),
            "orders": np.add.reduceat(arrays["order_count"], starts),
            "cost": np.add.reduceat(arrays["turnover"] * COST_PER_SIDE, starts),
            "min_drawdown": np.minimum.reduceat(arrays["drawdown"], starts),
        }
    )
    monthly["return_pct"] = monthly["log_return"].map(_return_pct)
    monthly["drawdown_pct"] = monthly["min_drawdown"] * 100.0
    return monthly


def _yearly_frame(monthly: pd.DataFrame) -> pd.DataFrame:
    out = monthly.copy()
    out["year"] = out["month"].str[:4]
    return (
        out.groupby("year")
        .agg(
            log_return=("log_return", "sum"),
            compounded_return_pct=("log_return", lambda values: _return_pct(float(values.sum()))),
            months=("month", "count"),
            losing_months=("return_pct", lambda values: int((values <= 0).sum())),
            min_monthly_return_pct=("return_pct", "min"),
            orders_min=("orders", "min"),
            orders_sum=("orders", "sum"),
            max_drawdown_pct=("drawdown_pct", "min"),
            cost_sum=("cost", "sum"),
            turnover_sum=("turnover", "sum"),
        )
        .reset_index()
    )


def _choices_frame(
    choices: np.ndarray,
    units: list[Unit],
    market: dict[str, Any],
    trade_after_day: int | None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for month, unit_index in zip(market["month_labels"], choices):
        if int(unit_index) < 0:
            rows.append({"month": month, "unit_index": None, "unit_id": "flat", "trade_after_day": trade_after_day})
            continue
        unit = units[int(unit_index)]
        rows.append(
            {
                "month": month,
                "unit_index": unit.unit_index,
                "unit_id": unit.unit_id,
                "expert_index": unit.expert_index,
                "expert_name": unit.expert_name,
                "leverage": unit.leverage,
                "trade_after_day": trade_after_day,
                "params_json": json.dumps(_json_ready(unit.params), ensure_ascii=False, sort_keys=True),
            }
        )
    return pd.DataFrame(rows)


def _write_payload(prefix: str, payload: dict[str, Any]) -> None:
    payload["signals"].to_csv(OUT_DIR / f"{prefix}_signals.csv", index=False)
    payload["equity"].to_csv(OUT_DIR / f"{prefix}_equity.csv", index=False)
    payload["monthly"].to_csv(OUT_DIR / f"{prefix}_monthly.csv", index=False)
    payload["yearly"].to_csv(OUT_DIR / f"{prefix}_yearly.csv", index=False)
    if payload["choices"] is not None:
        payload["choices"].to_csv(OUT_DIR / f"{prefix}_choices.csv", index=False)


def _summary(
    source: pd.DataFrame,
    experts: list[source_pool.Expert],
    units: list[Unit],
    static_payload: dict[str, Any],
    oracle_payload: dict[str, Any],
    best_strict_payload: dict[str, Any] | None,
    selector_scan: pd.DataFrame,
) -> dict[str, Any]:
    strict_scan = selector_scan.loc[selector_scan["strict_no_future"].fillna(False)]
    strict_pass = strict_scan.loc[strict_scan["hard_pass"].fillna(False)]
    return {
        "status": "expert_pool_bounds_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "orders_generated": False,
        "orders_submitted": False,
        "live_actions_taken": False,
        "cost_model": {
            "cost_per_side": COST_PER_SIDE,
            "round_trip_open_close": COST_PER_SIDE * 2,
            "note": "0.1% per side; flat-to-position costs one side, close costs one side, flip costs two sides; cost is multiplied by leverage turnover.",
        },
        "requirements": {
            "return_2025_pct_gt": REQUIRED_RETURN_PCT,
            "return_2026_pct_gt": REQUIRED_RETURN_PCT,
            "every_eval_month_return_gt_0": True,
            "min_monthly_orders": REQUIRED_MIN_MONTHLY_ORDERS,
            "eval_years": sorted(EVAL_YEARS),
        },
        "dropped_forbidden_columns": source.attrs.get("dropped_forbidden_columns", []),
        "expert_count": len(experts),
        "unit_count": len(units),
        "leverages": LEVERAGES,
        "static_single_expert_best": _json_ready(static_payload["row"]),
        "monthly_posthoc_oracle": _json_ready(oracle_payload["row"]),
        "best_strict_tradeable": _json_ready(best_strict_payload["row"] if best_strict_payload else {}),
        "theoretical_upper_bound_pass": bool(oracle_payload["row"]["hard_pass"]),
        "strict_tradeable_pass": bool(len(strict_pass) > 0),
        "strict_pass_rows": int(len(strict_pass)),
        "selector_rows": int(len(selector_scan)),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "source_pool_script_sha256": _sha256(SCRIPTS / "search_online_expert_pool_20260627.py"),
            "feature_frame_sha256": _sha256(source_pool.FEATURE_FRAME),
        },
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "static_scan": _relpath(OUT_DIR / "static_single_expert_scan.csv"),
            "selector_scan": _relpath(OUT_DIR / "selector_bounds_scan.csv"),
            "monthly_oracle_yearly": _relpath(OUT_DIR / "monthly_posthoc_best_oracle_yearly.csv"),
            "monthly_oracle_monthly": _relpath(OUT_DIR / "monthly_posthoc_best_oracle_monthly.csv"),
            "best_strict_yearly": _relpath(OUT_DIR / "best_strict_tradeable_yearly.csv") if best_strict_payload else None,
            "best_strict_monthly": _relpath(OUT_DIR / "best_strict_tradeable_monthly.csv") if best_strict_payload else None,
        },
    }


def _render_report(summary: dict[str, Any]) -> str:
    static = summary["static_single_expert_best"]
    oracle = summary["monthly_posthoc_oracle"]
    strict = summary["best_strict_tradeable"]
    lines = [
        "# Expert Pool Bounds 20260627",
        "",
        f"- status: `{summary['status']}`",
        f"- expert_count: `{summary['expert_count']}`",
        f"- unit_count: `{summary['unit_count']}`",
        f"- cost: `0.1% per side, 0.2% open+close; real turnover orders counted`",
        f"- theoretical_upper_bound_pass: `{summary['theoretical_upper_bound_pass']}`",
        f"- strict_tradeable_pass: `{summary['strict_tradeable_pass']}`",
        "",
        "## Static Single Expert Best",
        "",
        f"- hard_pass: `{static.get('hard_pass')}`",
        f"- selector: `{static.get('selector_id')}`",
        f"- unit: `{static.get('unit_id')}`",
        f"- 2025 return: `{static.get('return_2025_pct')}`",
        f"- 2026 return: `{static.get('return_2026_pct')}`",
        f"- min monthly return: `{static.get('min_monthly_return_pct')}`",
        f"- min monthly orders: `{static.get('min_monthly_orders')}`",
        "",
        "## Monthly Posthoc Oracle",
        "",
        "- strict_no_future: `false`",
        f"- hard_pass: `{oracle.get('hard_pass')}`",
        f"- 2025 return: `{oracle.get('return_2025_pct')}`",
        f"- 2026 return: `{oracle.get('return_2026_pct')}`",
        f"- min monthly return: `{oracle.get('min_monthly_return_pct')}`",
        f"- min monthly orders: `{oracle.get('min_monthly_orders')}`",
        "",
        "## Best Strict Tradeable Selector",
        "",
        f"- strict_no_future: `{strict.get('strict_no_future')}`",
        f"- selector: `{strict.get('selector_id')}`",
        f"- hard_pass: `{strict.get('hard_pass')}`",
        f"- 2025 return: `{strict.get('return_2025_pct')}`",
        f"- 2026 return: `{strict.get('return_2026_pct')}`",
        f"- min monthly return: `{strict.get('min_monthly_return_pct')}`",
        f"- losing eval months: `{strict.get('losing_eval_months')}`",
        f"- min monthly orders: `{strict.get('min_monthly_orders')}`",
    ]
    return "\n".join(lines) + "\n"


def _return_pct(log_value: float) -> float:
    if log_value > 700.0:
        return float("inf")
    if log_value < -745.0:
        return -100.0
    return float(np.expm1(log_value) * 100.0)


def _is_better(row: dict[str, Any], best: dict[str, Any] | None) -> bool:
    if best is None:
        return True
    return _sort_key(row) > _sort_key(best)


def _sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        bool(row.get("hard_pass")),
        -int(row.get("losing_eval_months") if row.get("losing_eval_months") is not None else 999),
        float(row.get("min_monthly_return_pct") or -999.0),
        float(row.get("min_required_year_return_pct") or -999.0),
        -abs(float(row.get("max_drawdown_pct") or 999.0)),
    )


def _sort_columns() -> list[str]:
    return [
        "hard_pass",
        "losing_eval_months",
        "min_monthly_return_pct",
        "min_required_year_return_pct",
        "max_drawdown_pct",
    ]


def _sort_ascending() -> list[bool]:
    return [False, True, False, False, False]


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return [_json_ready(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _json_ready(value.item())
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
