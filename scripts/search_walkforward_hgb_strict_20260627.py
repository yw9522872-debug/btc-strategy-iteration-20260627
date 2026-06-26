from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
OUT_DIR = ARTIFACTS / "walkforward_hgb_strict_20260627"
FEATURE_FRAME = ARTIFACTS / "event_entry_fullscan" / "event_entry_best_signals.csv"

BACKTEST_START = "2024-01-01"
COST_PER_SIDE = 0.001
REQUIRED_RETURN_PCT = 100.0
REQUIRED_MIN_MONTHLY_ORDERS = 10
EVAL_YEARS = {"2025", "2026"}
HORIZONS = [8, 16, 32, 64]
THRESHOLD_QUANTILES = [0.50, 0.65, 0.80, 0.90]
LEVERAGES = [1.0, 2.0, 4.0, 6.0, 8.0]
MIN_TRAIN_ROWS = 90 * 24 * 4
FORBIDDEN_INPUT_TOKENS = ("target_position", "component", "reason", "action", "confidence")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = _load_source(FEATURE_FRAME)
    features, feature_columns = _features(source)
    market = _market(source)
    _assert_15m(market)

    rows: list[dict[str, Any]] = []
    fold_rows: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    for horizon in HORIZONS:
        walk = _walkforward_predict(features, market, horizon)
        fold_rows.extend(walk["folds"])
        for threshold_quantile in THRESHOLD_QUANTILES:
            threshold = walk["thresholds"][threshold_quantile]
            target = _fixed_hold_target(walk["prediction"], threshold, horizon)
            for leverage in LEVERAGES:
                row, arrays = _evaluate(target, walk["prediction"], threshold, market, horizon, threshold_quantile, leverage)
                rows.append(row)
                if _better(row, best["row"] if best else None):
                    best = {"row": row, "arrays": arrays}

    scan = pd.DataFrame(rows).sort_values(_sort_columns(), ascending=_sort_ascending()).reset_index(drop=True)
    scan.to_csv(OUT_DIR / "scan.csv", index=False)
    pd.DataFrame(fold_rows).to_csv(OUT_DIR / "folds.csv", index=False)

    payload = _payload(best, market) if best else None
    if payload:
        payload["signals"].to_csv(OUT_DIR / "best_signals.csv", index=False)
        payload["equity"].to_csv(OUT_DIR / "best_equity.csv", index=False)
        payload["monthly"].to_csv(OUT_DIR / "best_monthly.csv", index=False)
        payload["yearly"].to_csv(OUT_DIR / "best_yearly.csv", index=False)

    summary = {
        "status": "walkforward_hgb_strict_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "strict_no_future_function": True,
        "strict_training_rule": (
            "For each prediction month, training uses only rows i where i+horizon <= month_start_index, "
            "so each future-return label is already fully known at decision time."
        ),
        "signal_timing": "Prediction at bar t uses bar-t closed features; position participates from bar t+1.",
        "threshold_rule": "Each threshold is a quantile of that fold's training prediction distribution only.",
        "train_mode": "monthly_expanding_walk_forward",
        "cost_model": {
            "cost_per_side": COST_PER_SIDE,
            "round_trip_open_close": COST_PER_SIDE * 2,
        },
        "grid": {
            "horizons": HORIZONS,
            "threshold_quantiles": THRESHOLD_QUANTILES,
            "leverages": LEVERAGES,
        },
        "required": {
            "return_2025_pct_gt": REQUIRED_RETURN_PCT,
            "return_2026_pct_gt": REQUIRED_RETURN_PCT,
            "monthly_return_pct_gt": 0.0,
            "monthly_orders_gte": REQUIRED_MIN_MONTHLY_ORDERS,
        },
        "dropped_forbidden_columns": source.attrs.get("dropped_forbidden_columns", []),
        "feature_columns": feature_columns,
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
            "folds": str(OUT_DIR / "folds.csv"),
            "best_signals": str(OUT_DIR / "best_signals.csv") if payload else None,
            "best_equity": str(OUT_DIR / "best_equity.csv") if payload else None,
            "best_monthly": str(OUT_DIR / "best_monthly.csv") if payload else None,
            "best_yearly": str(OUT_DIR / "best_yearly.csv") if payload else None,
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_source(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.loc[frame["timestamp"].notna()].sort_values("timestamp").reset_index(drop=True)
    frame = frame.loc[frame["timestamp"] >= pd.Timestamp(BACKTEST_START, tz="UTC")].reset_index(drop=True)
    dropped = [column for column in frame.columns if _forbidden_input(column)]
    out = frame[[column for column in frame.columns if column not in dropped]].copy()
    out.attrs["dropped_forbidden_columns"] = dropped
    for column in out.columns:
        if column != "timestamp":
            out[column] = pd.to_numeric(out[column], errors="coerce")
    required = {"timestamp", "open", "high", "low", "close"}
    missing = required.difference(out.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    return out


def _forbidden_input(column: str) -> bool:
    lower = column.lower()
    return any(token in lower for token in FORBIDDEN_INPUT_TOKENS)


def _features(frame: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    out = pd.DataFrame(index=frame.index)
    for column in frame.columns:
        if column != "timestamp" and not _forbidden_input(column):
            out[column] = frame[column]

    close = frame["close"].astype(float)
    ret_1 = close.pct_change() * 10_000.0
    for window in [1, 2, 4, 8, 16, 32, 64, 96, 192, 384, 672]:
        out[f"ret_{window}_bps"] = close.pct_change(window) * 10_000.0
    for window in [16, 64, 192]:
        out[f"vol_{window}_bps"] = ret_1.rolling(window).std()
    for span in [20, 50, 100]:
        column = f"ema{span}"
        if column in frame:
            out[f"close_ema{span}_gap_bps"] = (close / frame[column].replace(0, np.nan) - 1.0) * 10_000.0
    if {"high", "low"}.issubset(frame.columns):
        out["bar_range_bps"] = (frame["high"] / frame["low"].replace(0, np.nan) - 1.0) * 10_000.0
    if {"open", "close"}.issubset(frame.columns):
        out["bar_close_open_bps"] = (frame["close"] / frame["open"].replace(0, np.nan) - 1.0) * 10_000.0
    if {"bbu", "bbl"}.issubset(frame.columns):
        out["bb_pos"] = (close - frame["bbl"]) / (frame["bbu"] - frame["bbl"]).replace(0, np.nan)
    timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    out["hour_sin"] = np.sin(2.0 * np.pi * timestamp.dt.hour / 24.0)
    out["hour_cos"] = np.cos(2.0 * np.pi * timestamp.dt.hour / 24.0)
    out["dow_sin"] = np.sin(2.0 * np.pi * timestamp.dt.weekday / 7.0)
    out["dow_cos"] = np.cos(2.0 * np.pi * timestamp.dt.weekday / 7.0)

    bad = [column for column in out.columns if _forbidden_input(column)]
    if bad:
        raise ValueError(f"Forbidden input columns survived: {bad}")
    out = out.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return out.to_numpy(np.float32), list(out.columns)


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
        "year": year,
        "year_labels": year[year_starts],
        "year_starts": year_starts,
    }


def _assert_15m(market: dict[str, Any]) -> None:
    seconds = market["timestamp"].diff().dropna().dt.total_seconds()
    median = float(seconds.median())
    if abs(median - 900.0) > 1.0:
        raise ValueError(f"Expected BTC 15m bars, got median interval {median} seconds")


def _walkforward_predict(features: np.ndarray, market: dict[str, Any], horizon: int) -> dict[str, Any]:
    close = market["close"]
    n = len(close)
    label = np.full(n, np.nan, dtype=float)
    label[:-horizon] = np.log(close[horizon:] / close[:-horizon])
    prediction = np.full(n, np.nan, dtype=float)
    thresholds = {quantile: np.full(n, np.nan, dtype=float) for quantile in THRESHOLD_QUANTILES}
    ends = np.r_[market["month_starts"][1:], n]
    folds: list[dict[str, Any]] = []

    for fold_index, (start, end, month_label) in enumerate(zip(market["month_starts"], ends, market["month_labels"])):
        train_end = int(start - horizon)
        if train_end < MIN_TRAIN_ROWS:
            continue
        y_train = label[: train_end + 1]
        valid = np.isfinite(y_train)
        if int(valid.sum()) < MIN_TRAIN_ROWS:
            continue
        x_train = features[: train_end + 1][valid]
        y_train = y_train[valid]
        model = HistGradientBoostingRegressor(
            max_iter=60,
            max_leaf_nodes=15,
            learning_rate=0.08,
            l2_regularization=0.01,
            early_stopping=False,
            random_state=10_000 + horizon,
        )
        model.fit(x_train, y_train)
        train_prediction = model.predict(x_train)
        period_prediction = model.predict(features[start:end])
        prediction[start:end] = period_prediction
        abs_train_prediction = np.abs(train_prediction)
        fold_thresholds: dict[str, float] = {}
        for quantile in THRESHOLD_QUANTILES:
            value = float(np.quantile(abs_train_prediction, quantile))
            thresholds[quantile][start:end] = value
            fold_thresholds[f"threshold_q{int(quantile * 100)}"] = value
        folds.append(
            {
                "horizon": horizon,
                "fold_index": fold_index,
                "predict_month": str(month_label),
                "train_rows": int(len(y_train)),
                "train_last_feature_timestamp": market["timestamp"].iloc[train_end].isoformat(),
                "train_labels_known_through": market["timestamp"].iloc[train_end + horizon].isoformat(),
                "predict_start": market["timestamp"].iloc[start].isoformat(),
                "predict_end": market["timestamp"].iloc[end - 1].isoformat(),
                **fold_thresholds,
            }
        )
    return {"prediction": prediction, "thresholds": thresholds, "folds": folds}


def _fixed_hold_target(prediction: np.ndarray, threshold: np.ndarray, horizon: int) -> np.ndarray:
    target = np.zeros(len(prediction), dtype=np.int8)
    side = 0
    remaining = 0
    for index, value in enumerate(prediction):
        if remaining <= 0:
            side = 0
            if np.isfinite(value) and np.isfinite(threshold[index]):
                if value > threshold[index]:
                    side = 1
                    remaining = horizon
                elif value < -threshold[index]:
                    side = -1
                    remaining = horizon
        if remaining > 0:
            target[index] = side
            remaining -= 1
    return target


def _evaluate(
    target: np.ndarray,
    prediction: np.ndarray,
    threshold: np.ndarray,
    market: dict[str, Any],
    horizon: int,
    threshold_quantile: float,
    leverage: float,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    position = target.astype(float) * leverage
    active_position = np.r_[0.0, position[:-1]]
    turnover = np.abs(position - np.r_[0.0, position[:-1]])
    order_count = np.abs(target.astype(int) - np.r_[0, target[:-1]].astype(int))
    cost = turnover * COST_PER_SIDE
    strategy_log_return = active_position * market["raw_return"] - cost
    equity = np.exp(np.cumsum(strategy_log_return))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0

    month_log = np.add.reduceat(strategy_log_return, market["month_starts"])
    month_orders = np.add.reduceat(order_count, market["month_starts"])
    eval_log = month_log[market["eval_month_mask"]]
    eval_orders = month_orders[market["eval_month_mask"]]
    month_return_pct = (np.exp(eval_log) - 1.0) * 100.0 if len(eval_log) else np.array([])
    year_log = np.add.reduceat(strategy_log_return, market["year_starts"])
    year_map = {
        str(label): float((np.exp(log_value) - 1.0) * 100.0)
        for label, log_value in zip(market["year_labels"], year_log)
    }
    y2025 = year_map.get("2025")
    y2026 = year_map.get("2026")
    hard_pass = bool(
        y2025 is not None
        and y2026 is not None
        and y2025 > REQUIRED_RETURN_PCT
        and y2026 > REQUIRED_RETURN_PCT
        and len(month_return_pct) > 0
        and float(month_return_pct.min()) > 0.0
        and int(eval_orders.min()) >= REQUIRED_MIN_MONTHLY_ORDERS
    )
    returns = pd.Series(strategy_log_return)
    active_returns = returns[np.abs(active_position) > 0]
    losses = float(active_returns[active_returns < 0].sum())
    gains = float(active_returns[active_returns > 0].sum())
    params = {
        "horizon": horizon,
        "threshold_quantile": threshold_quantile,
        "leverage": leverage,
        "model": "HistGradientBoostingRegressor",
        "train_mode": "monthly_expanding_walk_forward",
    }
    digest = hashlib.sha1(json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()[:10]
    row = {
        "candidate_id": f"walk_hgb_strict_{digest}_h{horizon}_q{int(threshold_quantile * 100)}_lev{leverage:g}",
        "hard_pass": hard_pass,
        "horizon": horizon,
        "threshold_quantile": threshold_quantile,
        "leverage": leverage,
        "return_2025_pct": y2025,
        "return_2026_pct": y2026,
        "min_required_year_return_pct": min(y2025 if y2025 is not None else -999.0, y2026 if y2026 is not None else -999.0),
        "min_monthly_return_pct": float(month_return_pct.min()) if len(month_return_pct) else None,
        "losing_eval_months": int((month_return_pct <= 0).sum()) if len(month_return_pct) else None,
        "min_monthly_orders": int(eval_orders.min()) if len(eval_orders) else None,
        "total_return_pct": float((equity[-1] - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "annualized_sharpe": float(0.0 if returns.std() == 0 else returns.mean() / returns.std() * math.sqrt(365 * 24 * 4)),
        "exposure_pct": float((np.abs(active_position) > 0).mean() * 100.0),
        "orders": int(order_count.sum()),
        "turnover": float(turnover.sum()),
        "cost_log_return_sum": float(cost.sum()),
        "win_rate_pct": float(0.0 if active_returns.empty else (active_returns > 0).mean() * 100.0),
        "profit_factor": float("inf") if losses == 0 and gains > 0 else float(gains / abs(losses) if losses != 0 else 0.0),
        "params_json": json.dumps(params, ensure_ascii=False, sort_keys=True),
    }
    return row, {
        "target": target,
        "prediction": prediction,
        "threshold": threshold,
        "position": position,
        "active_position": active_position,
        "turnover": turnover,
        "order_count": order_count,
        "cost": cost,
        "strategy_log_return": strategy_log_return,
        "equity": equity,
        "drawdown": drawdown,
    }


def _payload(best: dict[str, Any], market: dict[str, Any]) -> dict[str, pd.DataFrame]:
    row = best["row"]
    arrays = best["arrays"]
    equity = pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "close": market["close"],
            "model_prediction": arrays["prediction"],
            "entry_threshold": arrays["threshold"],
            "target_side": arrays["target"],
            "position": arrays["position"],
            "active_position": arrays["active_position"],
            "turnover": arrays["turnover"],
            "order_count": arrays["order_count"],
            "cost": arrays["cost"],
            "strategy_log_return": arrays["strategy_log_return"],
            "equity": arrays["equity"],
            "drawdown": arrays["drawdown"],
        }
    )
    monthly = _monthly_breakdown(equity)
    yearly = _yearly_breakdown(monthly)
    signals = pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "close": market["close"],
            "target_position": arrays["target"].astype(float),
            "leverage": row["leverage"],
            "component": np.where(arrays["target"] == 0, "flat", "walkforward_hgb_strict"),
            "candidate_version": row["candidate_id"],
        }
    )
    return {"signals": signals, "equity": equity, "monthly": monthly, "yearly": yearly}


def _monthly_breakdown(equity: pd.DataFrame) -> pd.DataFrame:
    out = equity.copy()
    out["month"] = pd.to_datetime(out["timestamp"], utc=True).dt.strftime("%Y-%m")
    monthly = out.groupby("month").agg(
        log_return=("strategy_log_return", "sum"),
        first_equity=("equity", "first"),
        last_equity=("equity", "last"),
        min_drawdown=("drawdown", "min"),
        turnover=("turnover", "sum"),
        orders=("order_count", "sum"),
        cost_log_return_sum=("cost", "sum"),
    )
    monthly["return_pct"] = (np.exp(monthly["log_return"]) - 1.0) * 100.0
    monthly["drawdown_pct"] = monthly["min_drawdown"] * 100.0
    return monthly.reset_index()


def _yearly_breakdown(monthly: pd.DataFrame) -> pd.DataFrame:
    out = monthly.copy()
    out["year"] = out["month"].str[:4]
    return (
        out.groupby("year")
        .agg(
            log_return=("log_return", "sum"),
            compounded_return_pct=("log_return", lambda values: (np.exp(values.sum()) - 1.0) * 100.0),
            months=("month", "count"),
            losing_months=("return_pct", lambda values: int((values <= 0).sum())),
            min_monthly_return_pct=("return_pct", "min"),
            min_monthly_orders=("orders", "min"),
            orders_sum=("orders", "sum"),
            turnover_sum=("turnover", "sum"),
            cost_log_return_sum=("cost_log_return_sum", "sum"),
            max_drawdown_pct=("drawdown_pct", "min"),
        )
        .reset_index()
    )


def _better(row: dict[str, Any], best: dict[str, Any] | None) -> bool:
    if best is None:
        return True
    return _sort_key(row) > _sort_key(best)


def _sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        bool(row.get("hard_pass")),
        -int(row.get("losing_eval_months") if row.get("losing_eval_months") is not None else 999),
        float(row.get("min_monthly_return_pct") or -999.0),
        float(row.get("min_required_year_return_pct") or -999.0),
        -float(abs(row.get("max_drawdown_pct") or 999.0)),
    )


def _sort_columns() -> list[str]:
    return ["hard_pass", "losing_eval_months", "min_monthly_return_pct", "min_required_year_return_pct", "max_drawdown_pct"]


def _sort_ascending() -> list[bool]:
    return [False, True, False, False, False]


def _report(summary: dict[str, Any]) -> str:
    best = summary.get("best_candidate") or {}
    return "\n".join(
        [
            "# Walk-Forward HGB Strict Search",
            "",
            f"- status: `{summary['status']}`",
            f"- strict_no_future_function: `{summary['strict_no_future_function']}`",
            f"- scan_rows: `{summary['scan_rows']}`",
            f"- hard_pass_rows: `{summary['hard_pass_rows']}`",
            f"- fee: `{summary['cost_model']['round_trip_open_close']:.4f}` round trip",
            "",
            "## Best Candidate",
            "",
            f"- candidate_id: `{best.get('candidate_id')}`",
            f"- hard_pass: `{best.get('hard_pass')}`",
            f"- return_2025_pct: `{best.get('return_2025_pct')}`",
            f"- return_2026_pct: `{best.get('return_2026_pct')}`",
            f"- min_monthly_return_pct: `{best.get('min_monthly_return_pct')}`",
            f"- losing_eval_months: `{best.get('losing_eval_months')}`",
            f"- min_monthly_orders: `{best.get('min_monthly_orders')}`",
            f"- max_drawdown_pct: `{best.get('max_drawdown_pct')}`",
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
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return [_json_ready(item) for item in value.tolist()]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if np.isnan(value):
            return None
        if np.isposinf(value):
            return "Infinity"
        if np.isneginf(value):
            return "-Infinity"
        return float(value)
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
