from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
OUT_DIR = ARTIFACTS / "hgb_in_sample_upper_bound_20260626"
FEATURE_FRAME = ARTIFACTS / "event_entry_fullscan" / "event_entry_best_signals.csv"

COST_PER_SIDE = 0.001
REQUIRED_RETURN_PCT = 100.0
REQUIRED_MIN_MONTHLY_ORDERS = 10
EVAL_YEARS = {"2025", "2026"}
FORBIDDEN_INPUT_COLUMNS = {
    "target_position",
    "component",
    "event_entry_reason",
    "exit_overlay_reason",
    "time_stop_reason",
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = _load_source()
    feature_frame = _features(source)
    market = _market(source)

    rows: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    for horizon in [8, 16, 32, 64]:
        label = np.log(source["close"].shift(-horizon) / source["close"]).fillna(0.0).to_numpy(float)
        train_idx = np.arange(len(source) - horizon)
        model = HistGradientBoostingRegressor(
            max_iter=100,
            max_leaf_nodes=31,
            learning_rate=0.08,
            random_state=horizon,
        )
        model.fit(feature_frame[train_idx], label[train_idx])
        prediction = model.predict(feature_frame)
        eval_abs = np.abs(prediction[market["eval_row_mask"]])
        thresholds = np.unique(np.quantile(eval_abs, [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]))
        for threshold in thresholds:
            target = _fixed_hold_target(prediction, horizon, float(threshold))
            row, arrays = _evaluate(target, market, horizon, float(threshold))
            rows.append(row)
            if best is None or _sort_key(row) > _sort_key(best["row"]):
                best = {"row": row, "arrays": arrays, "horizon": horizon, "threshold": float(threshold)}

    scan = pd.DataFrame(rows).sort_values(_sort_columns(), ascending=_sort_ascending()).reset_index(drop=True)
    scan.to_csv(OUT_DIR / "scan.csv", index=False)

    payload = _payload(best, market) if best else None
    if payload:
        payload["signals"].to_csv(OUT_DIR / "best_signals.csv", index=False)
        payload["equity"].to_csv(OUT_DIR / "best_equity.csv", index=False)
        payload["monthly"].to_csv(OUT_DIR / "best_monthly.csv", index=False)
        payload["yearly"].to_csv(OUT_DIR / "best_yearly.csv", index=False)

    summary = {
        "status": "hgb_in_sample_upper_bound_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "strict_no_future_training": False,
        "label_leakage_warning": (
            "This upper-bound model is trained on the full 2024-2026 sample using future horizon returns, "
            "then evaluated on the same sample. It is not a valid walk-forward/no-future training result."
        ),
        "signal_timing": "Prediction at bar t uses bar-t closed features; target participates from bar t+1.",
        "cost_model": {
            "cost_per_side": COST_PER_SIDE,
            "round_trip_open_close": COST_PER_SIDE * 2,
        },
        "dropped_forbidden_columns": source.attrs.get("dropped_forbidden_columns", []),
        "scan_rows": int(len(scan)),
        "hard_pass_rows": int(scan["hard_pass"].fillna(False).sum()),
        "best_candidate": _json_ready(best["row"] if best else {}),
        "best_monthly": _json_ready(payload["monthly"].to_dict("records") if payload else []),
        "best_yearly": _json_ready(payload["yearly"].to_dict("records") if payload else []),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "feature_frame_sha256": _sha256(FEATURE_FRAME),
            "best_signals_sha256": _sha256(OUT_DIR / "best_signals.csv") if payload else None,
        },
        "files": {
            "summary": str(OUT_DIR / "summary.json"),
            "scan": str(OUT_DIR / "scan.csv"),
            "best_signals": str(OUT_DIR / "best_signals.csv") if payload else None,
            "best_equity": str(OUT_DIR / "best_equity.csv") if payload else None,
            "best_monthly": str(OUT_DIR / "best_monthly.csv") if payload else None,
            "best_yearly": str(OUT_DIR / "best_yearly.csv") if payload else None,
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_source() -> pd.DataFrame:
    frame = pd.read_csv(FEATURE_FRAME, low_memory=False)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.loc[frame["timestamp"].notna()].sort_values("timestamp").reset_index(drop=True)
    dropped = [column for column in frame.columns if column in FORBIDDEN_INPUT_COLUMNS]
    out = frame[[column for column in frame.columns if column not in FORBIDDEN_INPUT_COLUMNS]].copy()
    out.attrs["dropped_forbidden_columns"] = dropped
    for column in out.columns:
        if column != "timestamp":
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def _features(frame: pd.DataFrame) -> np.ndarray:
    close = frame["close"].astype(float)
    out = pd.DataFrame(index=frame.index)
    for window in [1, 2, 4, 8, 16, 32, 64, 96, 192, 384, 672]:
        out[f"ret_{window}"] = close.pct_change(window) * 10_000.0
    for span in [20, 50, 100]:
        out[f"gap_ema{span}"] = (close / frame[f"ema{span}"].replace(0, np.nan) - 1.0) * 10_000.0
    out["trend_gap"] = frame["trend_close_ema_gap_bps_60"]
    out["adx"] = frame["trend_adx_30"]
    out["donchian"] = frame["trend_donchian_pos_30"]
    out["rsi"] = frame["rsi14"]
    out["bb_pos"] = (close - frame["bbl"]) / (frame["bbu"] - frame["bbl"]).replace(0, np.nan)
    out["natr"] = frame["natr_30"]
    timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    out["hour_sin"] = np.sin(2.0 * np.pi * timestamp.dt.hour / 24.0)
    out["hour_cos"] = np.cos(2.0 * np.pi * timestamp.dt.hour / 24.0)
    out["dow_sin"] = np.sin(2.0 * np.pi * timestamp.dt.weekday / 7.0)
    out["dow_cos"] = np.cos(2.0 * np.pi * timestamp.dt.weekday / 7.0)
    out["day_of_month"] = timestamp.dt.day / 31.0
    return out.replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(float)


def _market(frame: pd.DataFrame) -> dict[str, Any]:
    timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    month = timestamp.dt.strftime("%Y-%m").to_numpy()
    year = timestamp.dt.year.astype(str).to_numpy()
    month_starts = np.r_[0, np.flatnonzero(month[1:] != month[:-1]) + 1]
    year_starts = np.r_[0, np.flatnonzero(year[1:] != year[:-1]) + 1]
    return {
        "timestamp": timestamp,
        "close": frame["close"].astype(float).to_numpy(float),
        "raw_return": np.log(frame["close"].astype(float)).diff().fillna(0.0).to_numpy(float),
        "month": month,
        "month_labels": month[month_starts],
        "month_starts": month_starts,
        "eval_month_mask": np.array([label[:4] in EVAL_YEARS for label in month[month_starts]]),
        "eval_row_mask": np.array([item in EVAL_YEARS for item in year]),
        "year": year,
        "year_labels": year[year_starts],
        "year_starts": year_starts,
    }


def _fixed_hold_target(prediction: np.ndarray, horizon: int, threshold: float) -> np.ndarray:
    target = np.zeros(len(prediction), dtype=np.int8)
    side = 0
    remaining = 0
    for index, value in enumerate(prediction):
        if remaining <= 0:
            if value > threshold:
                side = 1
                remaining = horizon
            elif value < -threshold:
                side = -1
                remaining = horizon
            else:
                side = 0
        if remaining > 0:
            target[index] = side
            remaining -= 1
    return target


def _evaluate(target: np.ndarray, market: dict[str, Any], horizon: int, threshold: float) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    position = target.astype(float)
    active_position = np.r_[0.0, position[:-1]]
    turnover = np.abs(np.diff(position, prepend=0.0))
    order_count = np.abs(target.astype(int) - np.r_[0, target[:-1]].astype(int))
    strategy_log_return = active_position * market["raw_return"] - turnover * COST_PER_SIDE
    equity = np.exp(np.cumsum(strategy_log_return))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    month_log = np.add.reduceat(strategy_log_return, market["month_starts"])
    month_orders = np.add.reduceat(order_count, market["month_starts"])
    eval_log = month_log[market["eval_month_mask"]]
    eval_orders = month_orders[market["eval_month_mask"]]
    year_log = np.add.reduceat(strategy_log_return, market["year_starts"])
    year_map = {label: (np.exp(value) - 1.0) * 100.0 for label, value in zip(market["year_labels"], year_log)}
    y2025 = float(year_map.get("2025", -999.0))
    y2026 = float(year_map.get("2026", -999.0))
    monthly_return_pct = (np.exp(eval_log) - 1.0) * 100.0
    hard_pass = bool(
        y2025 > REQUIRED_RETURN_PCT
        and y2026 > REQUIRED_RETURN_PCT
        and float(monthly_return_pct.min()) > 0.0
        and int(eval_orders.min()) >= REQUIRED_MIN_MONTHLY_ORDERS
    )
    row = {
        "candidate_id": f"hgb_upper_bound_h{horizon}_{hashlib.sha1(str(threshold).encode()).hexdigest()[:10]}",
        "horizon": horizon,
        "threshold": threshold,
        "hard_pass": hard_pass,
        "return_2025_pct": y2025,
        "return_2026_pct": y2026,
        "min_required_year_return_pct": min(y2025, y2026),
        "min_monthly_return_pct": float(monthly_return_pct.min()),
        "losing_eval_months": int((monthly_return_pct <= 0).sum()),
        "min_monthly_orders": int(eval_orders.min()),
        "total_return_pct": float((equity[-1] - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "orders": int(order_count.sum()),
        "turnover": float(turnover.sum()),
    }
    return row, {
        "target": target,
        "position": position,
        "active_position": active_position,
        "turnover": turnover,
        "order_count": order_count,
        "strategy_log_return": strategy_log_return,
        "equity": equity,
        "drawdown": drawdown,
    }


def _payload(best: dict[str, Any], market: dict[str, Any]) -> dict[str, pd.DataFrame]:
    arrays = best["arrays"]
    equity = pd.DataFrame(
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
        }
    )
    monthly = _monthly(equity)
    yearly = _yearly(monthly)
    signals = pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "close": market["close"],
            "target_position": arrays["target"].astype(float),
            "component": "hgb_in_sample_upper_bound",
            "candidate_version": best["row"]["candidate_id"],
        }
    )
    return {"signals": signals, "equity": equity, "monthly": monthly, "yearly": yearly}


def _monthly(equity: pd.DataFrame) -> pd.DataFrame:
    out = equity.copy()
    out["month"] = pd.to_datetime(out["timestamp"], utc=True).dt.strftime("%Y-%m")
    monthly = out.groupby("month").agg(
        log_return=("strategy_log_return", "sum"),
        orders=("order_count", "sum"),
        turnover=("turnover", "sum"),
        min_drawdown=("drawdown", "min"),
    )
    monthly["return_pct"] = (np.exp(monthly["log_return"]) - 1.0) * 100.0
    monthly["drawdown_pct"] = monthly["min_drawdown"] * 100.0
    return monthly.reset_index()


def _yearly(monthly: pd.DataFrame) -> pd.DataFrame:
    out = monthly.copy()
    out["year"] = out["month"].str[:4]
    yearly = out.groupby("year").agg(
        compounded_return_pct=("log_return", lambda value: (np.exp(value.sum()) - 1.0) * 100.0),
        months=("month", "count"),
        losing_months=("return_pct", lambda value: int((value <= 0).sum())),
        min_monthly_return_pct=("return_pct", "min"),
        min_monthly_orders=("orders", "min"),
        orders=("orders", "sum"),
        max_drawdown_pct=("drawdown_pct", "min"),
    )
    return yearly.reset_index()


def _sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        bool(row["hard_pass"]),
        float(row["min_monthly_return_pct"]),
        float(row["min_required_year_return_pct"]),
        -float(abs(row["max_drawdown_pct"])),
        -int(row["orders"]),
    )


def _sort_columns() -> list[str]:
    return ["hard_pass", "min_monthly_return_pct", "min_required_year_return_pct", "max_drawdown_pct"]


def _sort_ascending() -> list[bool]:
    return [False, False, False, False]


def _report(summary: dict[str, Any]) -> str:
    best = summary["best_candidate"]
    return "\n".join(
        [
            "# HGB In-Sample Upper Bound",
            "",
            f"- Status: `{summary['status']}`",
            f"- Strict no-future training: `{summary['strict_no_future_training']}`",
            f"- Hard pass rows: `{summary['hard_pass_rows']}`",
            f"- Best: `{best.get('candidate_id')}`",
            f"- 2025 return: `{best.get('return_2025_pct')}`",
            f"- 2026 return: `{best.get('return_2026_pct')}`",
            f"- Min monthly return: `{best.get('min_monthly_return_pct')}`",
            f"- Min monthly orders: `{best.get('min_monthly_orders')}`",
            "",
            "This is a leaky upper-bound research artifact, not a valid promotion candidate.",
            "",
        ]
    )


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
