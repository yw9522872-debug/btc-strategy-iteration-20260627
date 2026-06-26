from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
OUT_DIR = ARTIFACTS / "zscore_rsi_trend_20260627"
FEATURE_FRAME = ARTIFACTS / "event_entry_fullscan" / "event_entry_best_signals.csv"

BACKTEST_START = "2024-01-01"
COST_PER_SIDE = 0.001  # 0.1% each side, 0.2% open+close.
REQUIRED_RETURN_PCT = 100.0
REQUIRED_MIN_MONTHLY_ORDERS = 10
EVAL_YEARS = {"2025", "2026"}
BARS_PER_YEAR = 365 * 24 * 4

Z_WINDOWS = [48, 96, 192]
Z_THRESHOLDS = [1.0, 1.5, 2.0]
RSI_PAIRS = [(35.0, 65.0), (40.0, 60.0)]
HOLD_BARS = [2, 4, 8, 16]
LEVERAGE_GRID = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    family: str
    target: np.ndarray
    leverage: float
    params: dict[str, Any]


def main() -> None:
    _self_check()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = _load_features(FEATURE_FRAME)
    features = _add_zscore_features(source)
    market = _market(features)

    rows: list[dict[str, Any]] = []
    best_payload: dict[str, Any] | None = None
    for candidate in _candidate_stream(features):
        row, arrays = _evaluate(candidate, market)
        rows.append(row)
        if _better(row, best_payload["row"] if best_payload else None):
            best_payload = _payload(candidate, row, arrays, market)

    scan = pd.DataFrame(rows).sort_values(_sort_columns(), ascending=_sort_ascending()).reset_index(drop=True)
    scan.to_csv(OUT_DIR / "scan.csv", index=False)

    if best_payload:
        _assert_allowed_columns(best_payload["signals"])
        _assert_allowed_columns(best_payload["equity"])
        best_payload["signals"].to_csv(OUT_DIR / "best_signals.csv", index=False)
        best_payload["equity"].to_csv(OUT_DIR / "best_equity.csv", index=False)
        best_payload["monthly"].to_csv(OUT_DIR / "best_monthly.csv", index=False)
        best_payload["yearly"].to_csv(OUT_DIR / "best_yearly.csv", index=False)

    summary = _summary(source, scan, best_payload)
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_features(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.loc[frame["timestamp"].notna()].sort_values("timestamp").reset_index(drop=True)
    frame = frame.loc[frame["timestamp"] >= pd.Timestamp(BACKTEST_START, tz="UTC")].reset_index(drop=True)
    dropped = [column for column in frame.columns if _is_forbidden_column(column)]
    out = frame[[column for column in frame.columns if column not in dropped]].copy()
    out.attrs["dropped_forbidden_columns"] = dropped
    for column in out.columns:
        if column != "timestamp":
            out[column] = pd.to_numeric(out[column], errors="coerce")
    required = {"timestamp", "close", "rsi14", "trend_close_ema_gap_bps_60", "trend_adx_30"}
    missing = required.difference(out.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    return out.replace([np.inf, -np.inf], np.nan)


def _add_zscore_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    close = out["close"].astype(float)
    for window in Z_WINDOWS:
        median = close.rolling(window, min_periods=window).median()
        scale = close.rolling(window, min_periods=window).std(ddof=0).replace(0.0, np.nan)
        out[f"z_close_median_{window}"] = (close - median) / scale
    return out.replace([np.inf, -np.inf], np.nan)


def _market(frame: pd.DataFrame) -> dict[str, Any]:
    timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    close = frame["close"].astype(float).to_numpy(float)
    raw_return = np.log(frame["close"].astype(float)).diff().fillna(0.0).to_numpy(float)
    month = timestamp.dt.strftime("%Y-%m").to_numpy()
    year = timestamp.dt.year.astype(str).to_numpy()
    month_starts = np.r_[0, np.flatnonzero(month[1:] != month[:-1]) + 1]
    year_starts = np.r_[0, np.flatnonzero(year[1:] != year[:-1]) + 1]
    return {
        "timestamp": timestamp,
        "close": close,
        "raw_return": raw_return,
        "month": month,
        "month_starts": month_starts,
        "month_labels": month[month_starts],
        "eval_month_mask": np.array([label[:4] in EVAL_YEARS for label in month[month_starts]]),
        "year_starts": year_starts,
        "year_labels": year[year_starts],
    }


def _candidate_stream(features: pd.DataFrame):
    for trend_name, long_ok, short_ok, trend_params in _trend_filters(features):
        for family, long_trigger, short_trigger, trigger_params in _trigger_defs(features):
            event = np.zeros(len(features), dtype=np.int8)
            event[long_trigger & long_ok] = 1
            event[short_trigger & short_ok] = -1
            if np.count_nonzero(event) < 30:
                continue
            for hold in HOLD_BARS:
                target = _fixed_hold_target(event, hold)
                if np.count_nonzero(target) == 0:
                    continue
                for leverage in LEVERAGE_GRID:
                    params = {**trigger_params, "trend": trend_params, "hold_bars": hold, "leverage": leverage}
                    digest = hashlib.sha1(json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()[:10]
                    yield Candidate(
                        candidate_id=f"zscore_rsi_{family}_{trend_name}_{digest}_lev{leverage:g}",
                        family=family,
                        target=target,
                        leverage=leverage,
                        params=params,
                    )


def _trend_filters(features: pd.DataFrame):
    n = len(features)
    all_ok = np.ones(n, dtype=bool)
    yield "no_filter", all_ok, all_ok, {"mode": "none"}

    gap = features["trend_close_ema_gap_bps_60"].astype(float)
    adx = features["trend_adx_30"].astype(float)
    for gap_min in [50.0]:
        yield (
            f"ema_gap_{gap_min:g}",
            gap.ge(gap_min).fillna(False).to_numpy(bool),
            gap.le(-gap_min).fillna(False).to_numpy(bool),
            {"mode": "ema_gap", "gap_min_bps": gap_min, "adx_min": None},
        )
    for gap_min, adx_min in [(25.0, 18.0), (50.0, 24.0)]:
        long_ok = (gap.ge(gap_min) & adx.ge(adx_min)).fillna(False).to_numpy(bool)
        short_ok = (gap.le(-gap_min) & adx.ge(adx_min)).fillna(False).to_numpy(bool)
        yield (
            f"ema_gap_{gap_min:g}_adx_{adx_min:g}",
            long_ok,
            short_ok,
            {"mode": "ema_gap_adx", "gap_min_bps": gap_min, "adx_min": adx_min},
        )


def _trigger_defs(features: pd.DataFrame):
    rsi = features["rsi14"].astype(float)
    for window in Z_WINDOWS:
        z = features[f"z_close_median_{window}"].astype(float)
        for threshold in Z_THRESHOLDS:
            for low, high in RSI_PAIRS:
                below = z.le(-threshold)
                above = z.ge(threshold)
                rsi_low = rsi.le(low)
                rsi_high = rsi.ge(high)
                yield (
                    "mean_reversion",
                    (below & rsi_low).fillna(False).to_numpy(bool),
                    (above & rsi_high).fillna(False).to_numpy(bool),
                    {"family": "mean_reversion", "z_window": window, "z_threshold": threshold, "rsi_low": low, "rsi_high": high},
                )
                yield (
                    "breakout",
                    (above & rsi_high).fillna(False).to_numpy(bool),
                    (below & rsi_low).fillna(False).to_numpy(bool),
                    {"family": "breakout", "z_window": window, "z_threshold": threshold, "rsi_low": low, "rsi_high": high},
                )


def _fixed_hold_target(event: np.ndarray, hold_bars: int) -> np.ndarray:
    target = np.zeros(len(event), dtype=np.int8)
    side = 0
    remaining = 0
    for index, signal in enumerate(event):
        signal = int(signal)
        if remaining <= 0:
            side = signal
            remaining = hold_bars if signal else 0
        elif signal and signal != side:
            side = signal
            remaining = hold_bars
        if remaining > 0:
            target[index] = side
            remaining -= 1
    return target


def _evaluate(candidate: Candidate, market: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    target = candidate.target.astype(np.int8)
    position = target.astype(float) * float(candidate.leverage)
    active_position = np.r_[0.0, position[:-1]]
    turnover = np.abs(np.diff(position, prepend=0.0))
    previous_side = np.r_[0, target[:-1]]
    order_count = np.abs(target.astype(int) - previous_side.astype(int))
    strategy_log_return = active_position * market["raw_return"] - turnover * COST_PER_SIDE
    equity = np.exp(np.cumsum(strategy_log_return))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0

    month_log = np.add.reduceat(strategy_log_return, market["month_starts"])
    month_orders = np.add.reduceat(order_count, market["month_starts"])
    eval_log = month_log[market["eval_month_mask"]]
    eval_orders = month_orders[market["eval_month_mask"]]
    eval_monthly_return_pct = (np.exp(eval_log) - 1.0) * 100.0 if len(eval_log) else np.array([])

    year_log = np.add.reduceat(strategy_log_return, market["year_starts"])
    year_map = {
        str(label): float((np.exp(log_value) - 1.0) * 100.0)
        for label, log_value in zip(market["year_labels"], year_log)
    }
    y2025 = year_map.get("2025")
    y2026 = year_map.get("2026")
    yearly_return_gate_pass = bool(y2025 is not None and y2026 is not None and y2025 > REQUIRED_RETURN_PCT and y2026 > REQUIRED_RETURN_PCT)
    monthly_profit_gate_pass = bool(len(eval_monthly_return_pct) > 0 and float(eval_monthly_return_pct.min()) > 0.0)
    monthly_order_gate_pass = bool(len(eval_orders) > 0 and int(eval_orders.min()) >= REQUIRED_MIN_MONTHLY_ORDERS)
    hard_pass = bool(yearly_return_gate_pass and monthly_profit_gate_pass and monthly_order_gate_pass)

    returns = pd.Series(strategy_log_return)
    return_std = float(returns.std())
    active_returns = returns[np.abs(active_position) > 0]
    losses = float(active_returns[active_returns < 0].sum())
    gains = float(active_returns[active_returns > 0].sum())
    row = {
        "candidate_id": candidate.candidate_id,
        "family": candidate.family,
        "hard_pass": hard_pass,
        "yearly_return_gate_pass": yearly_return_gate_pass,
        "monthly_profit_gate_pass": monthly_profit_gate_pass,
        "monthly_order_gate_pass": monthly_order_gate_pass,
        "leverage": candidate.leverage,
        "return_2025_pct": y2025,
        "return_2026_pct": y2026,
        "min_required_year_return_pct": min(y2025 if y2025 is not None else -999.0, y2026 if y2026 is not None else -999.0),
        "min_monthly_return_pct": float(eval_monthly_return_pct.min()) if len(eval_monthly_return_pct) else None,
        "losing_eval_months": int((eval_monthly_return_pct <= 0).sum()) if len(eval_monthly_return_pct) else None,
        "min_monthly_orders": int(eval_orders.min()) if len(eval_orders) else None,
        "total_return_pct": float((equity[-1] - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "annualized_sharpe": float(0.0 if return_std == 0.0 else returns.mean() / return_std * math.sqrt(BARS_PER_YEAR)),
        "exposure_pct": float((np.abs(active_position) > 0).mean() * 100.0),
        "turnover": float(turnover.sum()),
        "orders": int(order_count.sum()),
        "segments": int(_segment_count(target)),
        "win_rate_pct": float(0.0 if active_returns.empty else (active_returns > 0).mean() * 100.0),
        "profit_factor": float("inf") if losses == 0.0 and gains > 0.0 else float(gains / abs(losses) if losses != 0.0 else 0.0),
        "params_json": json.dumps(_json_ready(candidate.params), ensure_ascii=False, sort_keys=True),
    }
    arrays = {
        "target": target,
        "position": position,
        "active_position": active_position,
        "turnover": turnover,
        "order_count": order_count,
        "strategy_log_return": strategy_log_return,
        "equity": equity,
        "drawdown": drawdown,
    }
    return row, arrays


def _payload(
    candidate: Candidate,
    row: dict[str, Any],
    arrays: dict[str, np.ndarray],
    market: dict[str, Any],
) -> dict[str, Any]:
    equity = pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "close": market["close"],
            "raw_log_return": market["raw_return"],
            "desired_position": arrays["position"],
            "active_position": arrays["active_position"],
            "turnover": arrays["turnover"],
            "order_count": arrays["order_count"],
            "cost": arrays["turnover"] * COST_PER_SIDE,
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
            "signal_side": arrays["target"].astype(int),
            "desired_position": arrays["position"],
            "candidate_id": candidate.candidate_id,
        }
    )
    return {"row": row, "signals": signals, "equity": equity, "monthly": monthly, "yearly": yearly}


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
            orders_min=("orders", "min"),
            orders_sum=("orders", "sum"),
            max_drawdown_pct=("drawdown_pct", "min"),
        )
        .reset_index()
    )


def _summary(source: pd.DataFrame, scan: pd.DataFrame, best_payload: dict[str, Any] | None) -> dict[str, Any]:
    hard = scan.loc[scan["hard_pass"].fillna(False)] if not scan.empty else pd.DataFrame()
    order_pass = scan.loc[scan["monthly_order_gate_pass"].fillna(False)] if not scan.empty else pd.DataFrame()
    best = best_payload["row"] if best_payload else {}
    return {
        "status": "zscore_rsi_trend_search_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "orders_generated": False,
        "orders_submitted": False,
        "cost_model": {
            "cost_per_side": COST_PER_SIDE,
            "round_trip_open_close": COST_PER_SIDE * 2,
            "note": "0.1% per side; a flip from long to short counts as close+open.",
        },
        "no_future_function_claim": (
            "Rolling median and z-score use pandas rolling windows ending at the current closed bar. "
            "The chosen signal at bar t is applied as active position from bar t+1."
        ),
        "dropped_forbidden_columns": source.attrs.get("dropped_forbidden_columns", []),
        "forbidden_columns_policy": "Dropped input columns matching target_position/component/*reason*/action/confidence and avoided them in outputs.",
        "scan_rows": int(len(scan)),
        "hard_pass_rows": int(len(hard)),
        "monthly_order_gate_pass_rows": int(len(order_pass)),
        "best_candidate": _json_ready(best),
        "best_monthly": _json_ready(best_payload["monthly"].to_dict("records") if best_payload else []),
        "best_yearly": _json_ready(best_payload["yearly"].to_dict("records") if best_payload else []),
        "requirements": {
            "return_2025_pct_gt": REQUIRED_RETURN_PCT,
            "return_2026_pct_gt": REQUIRED_RETURN_PCT,
            "every_eval_month_return_gt_0": True,
            "min_monthly_orders": REQUIRED_MIN_MONTHLY_ORDERS,
            "eval_note": "2026 means available 2026 data in the file.",
        },
        "grid": {
            "z_windows": Z_WINDOWS,
            "z_thresholds": Z_THRESHOLDS,
            "rsi_pairs": RSI_PAIRS,
            "hold_bars": HOLD_BARS,
            "leverage_grid": LEVERAGE_GRID,
            "families": ["mean_reversion", "breakout"],
            "trend_filters": ["none", "ema_gap", "ema_gap_adx"],
        },
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "feature_frame_sha256": _sha256(FEATURE_FRAME),
            "best_signals_sha256": _sha256(OUT_DIR / "best_signals.csv") if best_payload else None,
        },
        "files": {
            "summary": str(OUT_DIR / "summary.json"),
            "report": str(OUT_DIR / "report.md"),
            "scan": str(OUT_DIR / "scan.csv"),
            "best_signals": str(OUT_DIR / "best_signals.csv") if best_payload else None,
            "best_equity": str(OUT_DIR / "best_equity.csv") if best_payload else None,
            "best_monthly": str(OUT_DIR / "best_monthly.csv") if best_payload else None,
            "best_yearly": str(OUT_DIR / "best_yearly.csv") if best_payload else None,
        },
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary.get("best_candidate") or {}
    lines = [
        "# Z-score RSI Trend Search",
        "",
        f"- status: `{summary['status']}`",
        f"- scan_rows: `{summary['scan_rows']}`",
        f"- hard_pass_rows: `{summary['hard_pass_rows']}`",
        f"- monthly_order_gate_pass_rows: `{summary['monthly_order_gate_pass_rows']}`",
        "- fee: `0.1% open + 0.1% close = 0.2% round trip`",
        "- timing: `signal at bar t participates from bar t+1`",
        "",
        "## Best Candidate",
        "",
        f"- candidate_id: `{best.get('candidate_id')}`",
        f"- family: `{best.get('family')}`",
        f"- hard_pass: `{best.get('hard_pass')}`",
        f"- monthly_order_gate_pass: `{best.get('monthly_order_gate_pass')}`",
        f"- yearly_return_gate_pass: `{best.get('yearly_return_gate_pass')}`",
        f"- leverage: `{best.get('leverage')}`",
        f"- return_2025_pct: `{best.get('return_2025_pct')}`",
        f"- return_2026_pct: `{best.get('return_2026_pct')}`",
        f"- min_monthly_return_pct: `{best.get('min_monthly_return_pct')}`",
        f"- losing_eval_months: `{best.get('losing_eval_months')}`",
        f"- min_monthly_orders: `{best.get('min_monthly_orders')}`",
        f"- max_drawdown_pct: `{best.get('max_drawdown_pct')}`",
        "",
    ]
    return "\n".join(lines)


def _better(row: dict[str, Any], best: dict[str, Any] | None) -> bool:
    if best is None:
        return True
    return _sort_key(row) > _sort_key(best)


def _sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        bool(row.get("hard_pass")),
        bool(row.get("monthly_order_gate_pass")),
        bool(row.get("yearly_return_gate_pass")),
        -int(row.get("losing_eval_months") if row.get("losing_eval_months") is not None else 999),
        float(row.get("min_monthly_return_pct") or -999.0),
        float(row.get("min_required_year_return_pct") or -999.0),
        -float(abs(row.get("max_drawdown_pct") or 999.0)),
        float(row.get("annualized_sharpe") or -999.0),
    )


def _sort_columns() -> list[str]:
    return [
        "hard_pass",
        "monthly_order_gate_pass",
        "yearly_return_gate_pass",
        "losing_eval_months",
        "min_monthly_return_pct",
        "min_required_year_return_pct",
        "max_drawdown_pct",
        "annualized_sharpe",
    ]


def _sort_ascending() -> list[bool]:
    return [False, False, False, True, False, False, False, False]


def _segment_count(target: np.ndarray) -> int:
    previous = np.r_[0, target[:-1]]
    return int(((target != 0) & (target != previous)).sum())


def _is_forbidden_column(column: str) -> bool:
    lowered = column.lower()
    return lowered in {"target_position", "component", "action", "confidence"} or "reason" in lowered


def _assert_allowed_columns(frame: pd.DataFrame) -> None:
    forbidden = [column for column in frame.columns if _is_forbidden_column(column)]
    if forbidden:
        raise ValueError(f"Forbidden output columns: {forbidden}")


def _self_check() -> None:
    target = _fixed_hold_target(np.array([0, 1, 0, -1, 0], dtype=np.int8), 2)
    assert target.tolist() == [0, 1, 1, -1, -1]
    active = np.r_[0.0, target.astype(float)[:-1]]
    assert active.tolist() == [0.0, 0.0, 1.0, 1.0, -1.0]
    assert _is_forbidden_column("target_position")
    assert _is_forbidden_column("entry_reason")
    assert not _is_forbidden_column("signal_side")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
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
    if isinstance(value, np.generic):
        return _json_ready(value.item())
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
    return value


if __name__ == "__main__":
    main()
