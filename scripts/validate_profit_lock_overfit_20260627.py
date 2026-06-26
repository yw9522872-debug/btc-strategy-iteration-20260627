from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import search_monthly_profit_lock_20260627 as lock_search
import search_online_expert_pool_20260627 as source_pool


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "profit_lock_overfit_validation_20260627"

FIXED = {
    "expert_family": "ret_state",
    "window": 64,
    "threshold_bps": 100.0,
    "leverage": 8.0,
    "lock_log": 0.04,
    "quota_arm_log": 0.12,
    "quota_leverage": 0.1,
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = source_pool._load_features(source_pool.FEATURE_FRAME)
    features = source_pool._add_features(source)
    market = source_pool._market(features)
    experts = source_pool._expert_pool(features)
    expert_index = _find_fixed_expert(experts)
    side = experts[expert_index].target

    fixed_row, fixed_arrays = lock_search._simulate(
        side,
        FIXED["leverage"],
        FIXED["lock_log"],
        None,
        FIXED["quota_arm_log"],
        FIXED["quota_leverage"],
        market,
    )
    fixed_payload = lock_search._payload(
        {**fixed_row, "params_json": json.dumps(FIXED, sort_keys=True)},
        fixed_arrays,
        market,
        experts[expert_index],
    )

    selected = _select_params_on_2024(side, market)
    selected_row, selected_arrays = lock_search._simulate(
        side,
        selected["leverage"],
        selected["lock_log"],
        None,
        selected["quota_arm_log"],
        selected["quota_leverage"],
        market,
    )
    selected_payload = lock_search._payload(
        {**selected_row, "params_json": json.dumps(selected, sort_keys=True)},
        selected_arrays,
        market,
        experts[expert_index],
    )

    latest = _latest_binance_validation(source)

    fixed_payload["monthly"].to_csv(OUT_DIR / "fixed_monthly.csv", index=False)
    fixed_payload["yearly"].to_csv(OUT_DIR / "fixed_yearly.csv", index=False)
    selected_payload["monthly"].to_csv(OUT_DIR / "selected_on_2024_monthly.csv", index=False)
    selected_payload["yearly"].to_csv(OUT_DIR / "selected_on_2024_yearly.csv", index=False)
    if latest.get("monthly") is not None:
        latest["monthly"].to_csv(OUT_DIR / "latest_combined_monthly.csv", index=False)
    if latest.get("new_segment") is not None:
        pd.DataFrame([latest["new_segment"]]).to_csv(OUT_DIR / "latest_new_segment.csv", index=False)

    summary = {
        "status": "profit_lock_overfit_validation_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "fixed_params": FIXED,
        "cost_model": {"cost_per_side": lock_search.COST_PER_SIDE, "round_trip_open_close": lock_search.COST_PER_SIDE * 2},
        "fixed_full_history": _pack_result(fixed_row, fixed_payload),
        "within_expert_selected_on_2024": {
            "selected_params": selected,
            "selection_note": "Only the fixed ret_state expert was considered; lock/quota parameters were selected by 2024 metrics, then evaluated on 2025/2026.",
            "result": _pack_result(selected_row, selected_payload),
        },
        "latest_binance_validation": _json_ready({k: v for k, v in latest.items() if k not in {"monthly"}}),
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "fixed_monthly": _relpath(OUT_DIR / "fixed_monthly.csv"),
            "fixed_yearly": _relpath(OUT_DIR / "fixed_yearly.csv"),
            "selected_on_2024_monthly": _relpath(OUT_DIR / "selected_on_2024_monthly.csv"),
            "selected_on_2024_yearly": _relpath(OUT_DIR / "selected_on_2024_yearly.csv"),
            "latest_combined_monthly": _relpath(OUT_DIR / "latest_combined_monthly.csv") if latest.get("monthly") is not None else None,
            "latest_new_segment": _relpath(OUT_DIR / "latest_new_segment.csv") if latest.get("new_segment") is not None else None,
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _find_fixed_expert(experts: list[source_pool.Expert]) -> int:
    for index, expert in enumerate(experts):
        params = expert.params
        if (
            expert.name == FIXED["expert_family"]
            and int(params.get("window", -1)) == FIXED["window"]
            and float(params.get("threshold_bps", -1.0)) == FIXED["threshold_bps"]
        ):
            return index
    raise RuntimeError("Fixed expert not found")


def _select_params_on_2024(side: np.ndarray, market: dict[str, Any]) -> dict[str, Any]:
    best: tuple[Any, dict[str, Any]] | None = None
    for leverage in [2.0, 4.0, 5.0, 6.0, 8.0]:
        for lock_log in [0.0, 0.002, 0.005, 0.01, 0.02, 0.04]:
            for quota_arm_log in [None, 0.04, 0.08, 0.12]:
                qlevs = [None] if quota_arm_log is None else [0.0, 0.1, 0.25, 0.5, 1.0, 2.0]
                for quota_leverage in qlevs:
                    row, arrays = lock_search._simulate(side, leverage, lock_log, None, quota_arm_log, quota_leverage, market)
                    monthly = _arrays_to_monthly(arrays, market)
                    score = _year_score(monthly, "2024")
                    params = {
                        "leverage": leverage,
                        "lock_log": lock_log,
                        "quota_arm_log": quota_arm_log,
                        "quota_leverage": quota_leverage,
                        "selection_2024": score,
                    }
                    key = (
                        score["return_pct"] > 100.0 and score["losing_months"] == 0 and score["min_orders"] >= 10,
                        -score["losing_months"],
                        score["min_month_return_pct"],
                        score["return_pct"],
                        score["min_orders"],
                    )
                    if best is None or key > best[0]:
                        best = (key, params)
    if best is None:
        raise RuntimeError("No 2024 selection candidate")
    return best[1]


def _year_score(monthly: pd.DataFrame, year: str) -> dict[str, Any]:
    subset = monthly.loc[monthly["month"].str[:4] == year]
    log_return = float(subset["log_return"].sum())
    return {
        "return_pct": float((np.exp(log_return) - 1.0) * 100.0),
        "losing_months": int((subset["return_pct"] <= 0).sum()),
        "min_month_return_pct": float(subset["return_pct"].min()),
        "min_orders": int(subset["orders"].min()),
    }


def _pack_result(row: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    eval_monthly = payload["monthly"].loc[payload["monthly"]["month"].str[:4].isin(lock_search.EVAL_YEARS)]
    return {
        "row": _json_ready(row),
        "yearly": _json_ready(payload["yearly"].to_dict("records")),
        "eval_months": _json_ready(eval_monthly[["month", "return_pct", "orders"]].to_dict("records")),
    }


def _latest_binance_validation(local_source: pd.DataFrame) -> dict[str, Any]:
    local_ohlc = local_source[["timestamp", "open", "high", "low", "close"]].copy()
    local_end = pd.to_datetime(local_ohlc["timestamp"], utc=True).max()
    fetch_start = pd.Timestamp("2026-06-01T00:00:00Z")
    fetched = _fetch_binance_15m(fetch_start)
    if fetched.empty:
        return {"status": "fetch_empty_or_failed", "source": "Binance public klines", "local_end": local_end.isoformat()}

    combined = (
        pd.concat([local_ohlc, fetched], ignore_index=True)
        .drop_duplicates("timestamp", keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    combined = combined.loc[combined["timestamp"] >= fetch_start].reset_index(drop=True)
    market = _market_from_ohlc(combined)
    side = _ret_state_side(combined["close"].astype(float), FIXED["window"], FIXED["threshold_bps"])
    row, arrays = lock_search._simulate(
        side,
        FIXED["leverage"],
        FIXED["lock_log"],
        None,
        FIXED["quota_arm_log"],
        FIXED["quota_leverage"],
        market,
    )
    monthly = _arrays_to_monthly(arrays, market)
    after_mask = pd.to_datetime(market["timestamp"], utc=True) > local_end
    if bool(after_mask.any()):
        new_log = float(arrays["strategy_log_return"][after_mask].sum())
        new_orders = int(arrays["order_count"][after_mask].sum())
        new_start = pd.to_datetime(market["timestamp"], utc=True)[after_mask].min().isoformat()
        new_end = pd.to_datetime(market["timestamp"], utc=True)[after_mask].max().isoformat()
        new_bars = int(after_mask.sum())
    else:
        new_log = 0.0
        new_orders = 0
        new_start = None
        new_end = None
        new_bars = 0
    return {
        "status": "ok",
        "source": "https://api.binance.com/api/v3/klines or https://data-api.binance.vision/api/v3/klines",
        "local_end": local_end.isoformat(),
        "fetched_rows": int(len(fetched)),
        "combined_rows_from_2026_06_01": int(len(combined)),
        "latest_timestamp": pd.to_datetime(combined["timestamp"], utc=True).max().isoformat(),
        "june_combined_return_pct": float(monthly.loc[monthly["month"] == "2026-06", "return_pct"].iloc[0]) if (monthly["month"] == "2026-06").any() else None,
        "june_combined_orders": int(monthly.loc[monthly["month"] == "2026-06", "orders"].iloc[0]) if (monthly["month"] == "2026-06").any() else None,
        "new_segment": {
            "start": new_start,
            "end": new_end,
            "bars": new_bars,
            "log_return": new_log,
            "return_pct": float((np.exp(new_log) - 1.0) * 100.0),
            "orders": new_orders,
        },
        "monthly": monthly,
        "row": _json_ready(row),
    }


def _fetch_binance_15m(start: pd.Timestamp) -> pd.DataFrame:
    endpoints = [
        "https://api.binance.com/api/v3/klines",
        "https://data-api.binance.vision/api/v3/klines",
    ]
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = int(start.timestamp() * 1000)
    rows: list[list[Any]] = []
    last_error = None
    for endpoint in endpoints:
        rows.clear()
        cursor = start_ms
        try:
            while cursor < now_ms:
                query = urllib.parse.urlencode({"symbol": "BTCUSDT", "interval": "15m", "startTime": cursor, "limit": 1000})
                with urllib.request.urlopen(f"{endpoint}?{query}", timeout=20) as response:
                    chunk = json.loads(response.read().decode("utf-8"))
                if not chunk:
                    break
                closed = [item for item in chunk if int(item[6]) <= now_ms]
                rows.extend(closed)
                next_cursor = int(chunk[-1][0]) + 15 * 60 * 1000
                if next_cursor <= cursor:
                    break
                cursor = next_cursor
                if len(chunk) < 1000:
                    break
            if rows:
                break
        except Exception as exc:  # pragma: no cover - diagnostic path
            last_error = repr(exc)
            rows.clear()
            continue
    if not rows:
        if last_error:
            (OUT_DIR / "latest_fetch_error.txt").write_text(last_error, encoding="utf-8")
        return pd.DataFrame()
    out = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore"])
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(out["open_time"], unit="ms", utc=True),
            "open": pd.to_numeric(out["open"], errors="coerce"),
            "high": pd.to_numeric(out["high"], errors="coerce"),
            "low": pd.to_numeric(out["low"], errors="coerce"),
            "close": pd.to_numeric(out["close"], errors="coerce"),
        }
    ).dropna()


def _ret_state_side(close: pd.Series, window: int, threshold_bps: float) -> np.ndarray:
    ret = close.pct_change(window) * 10_000.0
    side = np.zeros(len(close), dtype=np.int8)
    active = 0
    for index, value in enumerate(ret):
        if pd.notna(value) and value >= threshold_bps:
            active = 1
        elif pd.notna(value) and value <= -threshold_bps:
            active = -1
        side[index] = active
    return side


def _market_from_ohlc(frame: pd.DataFrame) -> dict[str, Any]:
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
        "year": year,
        "month_starts": month_starts,
        "month_labels": month[month_starts],
        "eval_month_mask": np.array([label[:4] in lock_search.EVAL_YEARS for label in month[month_starts]]),
        "year_starts": year_starts,
        "year_labels": year[year_starts],
    }


def _arrays_to_monthly(arrays: dict[str, np.ndarray], market: dict[str, Any]) -> pd.DataFrame:
    equity = pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "close": market["close"],
            "position": arrays["position"],
            "active_position": arrays["active_position"],
            "turnover": arrays["turnover"],
            "order_count": arrays["order_count"],
            "strategy_log_return": arrays["strategy_log_return"],
            "equity": arrays["equity"],
            "drawdown": arrays["drawdown"],
        }
    )
    return lock_search._monthly_breakdown(equity)


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
    if isinstance(value, np.ndarray):
        return [_json_ready(item) for item in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value):
            return None
        if np.isposinf(value):
            return "Infinity"
        if np.isneginf(value):
            return "-Infinity"
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
    return value


if __name__ == "__main__":
    main()
