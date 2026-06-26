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
ARTIFACTS = ROOT / "artifacts"
OUT_DIR = ARTIFACTS / "ultimate_monthly_search_20260626"
FEATURE_FRAME = ARTIFACTS / "event_entry_fullscan" / "event_entry_best_signals.csv"

BACKTEST_START = "2024-01-01"
COST_PER_SIDE = 0.001  # 0.1% each side, 0.2% open+close.
REQUIRED_RETURN_PCT = 100.0
REQUIRED_MIN_MONTHLY_ORDERS = 10
EVAL_YEARS = {"2025", "2026"}

FORBIDDEN_INPUT_COLUMNS = {
    "target_position",
    "component",
    "event_entry_reason",
    "exit_overlay_reason",
    "time_stop_reason",
    "entry_reason",
    "exit_reason",
    "action",
    "confidence",
}


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    kind: str
    target: np.ndarray
    leverage: float
    params: dict[str, Any]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = _load_features(FEATURE_FRAME)
    features = _add_features(source)
    market = _market(features)

    rows: list[dict[str, Any]] = []
    best_payload: dict[str, Any] | None = None
    for candidate in _candidate_stream(features):
        row, arrays = _evaluate_fast(candidate, market)
        rows.append(row)
        if _better(row, best_payload["row"] if best_payload else None):
            best_payload = _payload_from_arrays(candidate, row, arrays, market)

    scan = pd.DataFrame(rows).sort_values(_sort_columns(), ascending=_sort_ascending()).reset_index(drop=True)
    scan.to_csv(OUT_DIR / "scan.csv", index=False)

    summary = _summary(source, scan, best_payload)
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")

    if best_payload:
        best_payload["signals"].to_csv(OUT_DIR / "best_signals.csv", index=False)
        best_payload["equity"].to_csv(OUT_DIR / "best_equity.csv", index=False)
        best_payload["monthly"].to_csv(OUT_DIR / "best_monthly.csv", index=False)
        best_payload["yearly"].to_csv(OUT_DIR / "best_yearly.csv", index=False)

    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_features(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.loc[frame["timestamp"].notna()].sort_values("timestamp").reset_index(drop=True)
    frame = frame.loc[frame["timestamp"] >= pd.Timestamp(BACKTEST_START, tz="UTC")].reset_index(drop=True)
    dropped = [column for column in frame.columns if column in FORBIDDEN_INPUT_COLUMNS]
    out = frame[[column for column in frame.columns if column not in FORBIDDEN_INPUT_COLUMNS]].copy()
    out.attrs["dropped_forbidden_columns"] = dropped
    for column in out.columns:
        if column != "timestamp":
            out[column] = pd.to_numeric(out[column], errors="coerce")
    required = {
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "natr_30",
        "trend_close_ema_gap_bps_60",
        "trend_adx_30",
        "trend_donchian_pos_30",
        "ema20",
        "ema50",
        "ema100",
        "rsi14",
        "bbu",
        "bbl",
    }
    missing = required.difference(out.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    return out


def _add_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    close = out["close"].astype(float)
    for bars in [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 384, 672]:
        out[f"ret_{bars}_bps"] = close.pct_change(bars) * 10_000.0
    for span in [20, 50, 100]:
        out[f"close_ema{span}_gap_bps"] = (close / out[f"ema{span}"].replace(0, np.nan) - 1.0) * 10_000.0
    band = (out["bbu"] - out["bbl"]).replace(0, np.nan)
    out["bb_pos"] = (close - out["bbl"]) / band
    out["hour"] = out["timestamp"].dt.hour.astype(int)
    out["weekday"] = out["timestamp"].dt.weekday.astype(int)
    return out.replace([np.inf, -np.inf], np.nan)


def _market(frame: pd.DataFrame) -> dict[str, Any]:
    timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    raw_return = np.log(frame["close"].astype(float)).diff().fillna(0.0).to_numpy(float)
    month = timestamp.dt.strftime("%Y-%m").to_numpy()
    year = timestamp.dt.year.astype(str).to_numpy()
    month_starts = np.r_[0, np.flatnonzero(month[1:] != month[:-1]) + 1]
    year_starts = np.r_[0, np.flatnonzero(year[1:] != year[:-1]) + 1]
    month_labels = month[month_starts]
    year_labels = year[year_starts]
    return {
        "timestamp": timestamp,
        "close": frame["close"].astype(float).to_numpy(float),
        "raw_return": raw_return,
        "month": month,
        "year": year,
        "month_starts": month_starts,
        "month_labels": month_labels,
        "eval_month_mask": np.array([label[:4] in EVAL_YEARS for label in month_labels]),
        "year_starts": year_starts,
        "year_labels": year_labels,
    }


def _candidate_stream(features: pd.DataFrame):
    trend_defs = _trend_defs(features)
    leverage_grid = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]
    hold_grid = [2, 4, 8, 16]
    profit_locks = [None]

    for trend_name, trend_side, trend_params in trend_defs:
        for trigger_name, long_trigger, short_trigger, trigger_params in _trigger_defs(features):
            event = np.zeros(len(features), dtype=np.int8)
            event[(trend_side >= 0) & long_trigger] = 1
            event[(trend_side <= 0) & short_trigger] = -1
            if np.count_nonzero(event) < 50:
                continue
            for hold_bars in hold_grid:
                base_target = _fixed_hold_target(event, hold_bars)
                if np.count_nonzero(base_target) == 0:
                    continue
                for leverage in leverage_grid:
                    for profit_lock in profit_locks:
                        params = {
                            "trend": trend_params,
                            "trigger": trigger_params,
                            "hold_bars": hold_bars,
                            "monthly_profit_lock_log": profit_lock,
                        }
                        target = base_target
                        kind = f"{trend_name}_{trigger_name}"
                        digest = hashlib.sha1(
                            json.dumps(_json_ready({**params, "leverage": leverage}), sort_keys=True).encode("utf-8")
                        ).hexdigest()[:10]
                        yield Candidate(
                            candidate_id=f"ultimate_{kind}_{digest}_lev{leverage}",
                            kind=kind,
                            target=target,
                            leverage=leverage,
                            params=params,
                        )


def _trend_defs(features: pd.DataFrame):
    n = len(features)
    yield "no_trend", np.zeros(n, dtype=np.int8), {"family": "none"}
    gap = features["trend_close_ema_gap_bps_60"]
    adx = features["trend_adx_30"]
    for gap_min, adx_min in [(25.0, 24.0), (50.0, 30.0), (50.0, 36.0), (100.0, 30.0), (200.0, 24.0)]:
        long = gap.ge(gap_min) & adx.ge(adx_min)
        short = gap.le(-gap_min) & adx.ge(adx_min)
        yield "gap_adx_state", _state_from(long, short), {
            "family": "gap_adx_state",
            "gap_min": gap_min,
            "adx_min": adx_min,
        }
    for window in [384, 672]:
        ret = features[f"ret_{window}_bps"]
        for threshold in [100.0, 350.0]:
            yield "long_return_state", _state_from(ret.ge(threshold), ret.le(-threshold)), {
                "family": "long_return_state",
                "window": window,
                "threshold_bps": threshold,
            }


def _trigger_defs(features: pd.DataFrame):
    for window in [2, 4, 8, 16, 32, 96]:
        ret = features[f"ret_{window}_bps"]
        for threshold in [50.0, 100.0, 200.0]:
            yield "ret_momentum", ret.ge(threshold).fillna(False).to_numpy(bool), ret.le(-threshold).fillna(False).to_numpy(bool), {
                "family": "ret_momentum",
                "window": window,
                "threshold_bps": threshold,
            }
            yield "ret_fade", ret.le(-threshold).fillna(False).to_numpy(bool), ret.ge(threshold).fillna(False).to_numpy(bool), {
                "family": "ret_fade",
                "window": window,
                "threshold_bps": threshold,
            }
    rsi = features["rsi14"]
    for low, high in [(30.0, 70.0), (40.0, 60.0)]:
        yield "rsi_pullback", rsi.le(low).fillna(False).to_numpy(bool), rsi.ge(high).fillna(False).to_numpy(bool), {
            "family": "rsi_pullback",
            "low": low,
            "high": high,
        }
        yield "rsi_momentum", rsi.ge(high).fillna(False).to_numpy(bool), rsi.le(low).fillna(False).to_numpy(bool), {
            "family": "rsi_momentum",
            "low": low,
            "high": high,
        }
    bb = features["bb_pos"]
    for low, high in [(0.20, 0.80), (0.40, 0.60)]:
        yield "bb_pullback", bb.le(low).fillna(False).to_numpy(bool), bb.ge(high).fillna(False).to_numpy(bool), {
            "family": "bb_pullback",
            "low": low,
            "high": high,
        }
        yield "bb_breakout", bb.ge(high).fillna(False).to_numpy(bool), bb.le(low).fillna(False).to_numpy(bool), {
            "family": "bb_breakout",
            "low": low,
            "high": high,
        }
    don = features["trend_donchian_pos_30"]
    for low, high in [(0.20, 0.80), (0.40, 0.60)]:
        yield "don_pullback", don.le(low).fillna(False).to_numpy(bool), don.ge(high).fillna(False).to_numpy(bool), {
            "family": "don_pullback",
            "low": low,
            "high": high,
        }
        yield "don_breakout", don.ge(high).fillna(False).to_numpy(bool), don.le(low).fillna(False).to_numpy(bool), {
            "family": "don_breakout",
            "low": low,
            "high": high,
        }


def _state_from(long_condition: pd.Series, short_condition: pd.Series) -> np.ndarray:
    long_values = long_condition.fillna(False).to_numpy(bool)
    short_values = short_condition.fillna(False).to_numpy(bool)
    target = np.zeros(len(long_values), dtype=np.int8)
    active_side = 0
    for index, (long_hit, short_hit) in enumerate(zip(long_values, short_values)):
        if long_hit:
            active_side = 1
        elif short_hit:
            active_side = -1
        target[index] = active_side
    return target


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


def _evaluate(candidate: Candidate, market: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    target, equity = _apply_monthly_controller(candidate, market)
    monthly = _monthly_breakdown(equity)
    yearly = _yearly_breakdown(monthly)
    row = _row(candidate, target, equity, monthly, yearly)
    signals = pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "close": equity["close"],
            "target_position": target.astype(float),
            "component": np.where(target != 0, candidate.kind, "flat"),
            "candidate_version": candidate.candidate_id,
        }
    )
    return row, {"row": row, "signals": signals, "equity": equity, "monthly": monthly, "yearly": yearly}


def _evaluate_fast(candidate: Candidate, market: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    target = candidate.target.astype(np.int8)
    leverage = float(candidate.leverage)
    raw_return = market["raw_return"]
    position = target.astype(float) * leverage
    active_position = np.r_[0.0, position[:-1]]
    turnover = np.abs(np.diff(position, prepend=0.0))
    previous_side = np.r_[0, target[:-1]]
    order_count = np.abs(target.astype(int) - previous_side.astype(int))
    strategy_log_return = active_position * raw_return - turnover * COST_PER_SIDE
    equity = np.exp(np.cumsum(strategy_log_return))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0

    month_log = np.add.reduceat(strategy_log_return, market["month_starts"])
    month_orders = np.add.reduceat(order_count, market["month_starts"])
    eval_log = month_log[market["eval_month_mask"]]
    eval_orders = month_orders[market["eval_month_mask"]]
    year_log = np.add.reduceat(strategy_log_return, market["year_starts"])
    year_map = {
        str(label): float((np.exp(log_value) - 1.0) * 100.0)
        for label, log_value in zip(market["year_labels"], year_log)
    }
    y2025 = year_map.get("2025")
    y2026 = year_map.get("2026")
    monthly_return_pct = (np.exp(eval_log) - 1.0) * 100.0 if len(eval_log) else np.array([])
    hard_pass = bool(
        y2025 is not None
        and y2026 is not None
        and y2025 > REQUIRED_RETURN_PCT
        and y2026 > REQUIRED_RETURN_PCT
        and len(monthly_return_pct) > 0
        and float(monthly_return_pct.min()) > 0.0
        and int(eval_orders.min()) >= REQUIRED_MIN_MONTHLY_ORDERS
    )
    returns = pd.Series(strategy_log_return)
    return_std = float(returns.std())
    active_returns = returns[np.abs(active_position) > 0]
    losses = float(active_returns[active_returns < 0].sum())
    gains = float(active_returns[active_returns > 0].sum())
    row = {
        "candidate_id": candidate.candidate_id,
        "kind": candidate.kind,
        "leverage": candidate.leverage,
        "hard_pass": hard_pass,
        "total_return_pct": float((equity[-1] - 1.0) * 100.0),
        "return_2025_pct": y2025,
        "return_2026_pct": y2026,
        "min_required_year_return_pct": min(y2025 if y2025 is not None else -999.0, y2026 if y2026 is not None else -999.0),
        "min_monthly_return_pct": float(monthly_return_pct.min()) if len(monthly_return_pct) else None,
        "losing_eval_months": int((monthly_return_pct <= 0).sum()) if len(monthly_return_pct) else None,
        "min_monthly_orders": int(eval_orders.min()) if len(eval_orders) else None,
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "annualized_sharpe": float(0.0 if return_std == 0 else returns.mean() / return_std * math.sqrt(365 * 24 * 4)),
        "exposure_pct": float((np.abs(active_position) > 0).mean() * 100.0),
        "turnover": float(turnover.sum()),
        "orders": int(order_count.sum()),
        "segments": int(_segment_count(target)),
        "win_rate_pct": float(0.0 if active_returns.empty else (active_returns > 0).mean() * 100.0),
        "profit_factor": float("inf") if losses == 0 and gains > 0 else float(gains / abs(losses) if losses != 0 else 0.0),
        "params_json": json.dumps(_json_ready(candidate.params), ensure_ascii=False, sort_keys=True),
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


def _payload_from_arrays(
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
    monthly = _monthly_breakdown(equity)
    yearly = _yearly_breakdown(monthly)
    signals = pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "close": market["close"],
            "target_position": arrays["target"].astype(float),
            "component": np.where(arrays["target"] != 0, candidate.kind, "flat"),
            "candidate_version": candidate.candidate_id,
        }
    )
    return {"row": row, "signals": signals, "equity": equity, "monthly": monthly, "yearly": yearly}


def _apply_monthly_controller(candidate: Candidate, market: dict[str, Any]) -> tuple[np.ndarray, pd.DataFrame]:
    base = candidate.target.astype(np.int8)
    raw_return = market["raw_return"]
    month = market["month"]
    leverage = float(candidate.leverage)
    profit_lock = candidate.params.get("monthly_profit_lock_log")
    if profit_lock is None:
        target = base.copy()
        position = target.astype(float) * leverage
        active_position = np.r_[0.0, position[:-1]]
        turnover = np.abs(np.diff(position, prepend=0.0))
        previous_side = np.r_[0, target[:-1]]
        order_count = np.abs(target.astype(int) - previous_side.astype(int))
        strategy_log_return = active_position * raw_return - turnover * COST_PER_SIDE
        equity = pd.DataFrame(
            {
                "timestamp": market["timestamp"],
                "close": market["close"],
                "raw_log_return": raw_return,
                "position": position,
                "active_position": active_position,
                "turnover": turnover,
                "order_count": order_count,
                "cost": turnover * COST_PER_SIDE,
                "strategy_log_return": strategy_log_return,
            }
        )
        equity["equity"] = np.exp(np.cumsum(strategy_log_return))
        equity["drawdown"] = equity["equity"] / equity["equity"].cummax() - 1.0
        return target, equity

    target = np.zeros(len(base), dtype=np.int8)
    position = np.zeros(len(base), dtype=float)
    active_position = np.zeros(len(base), dtype=float)
    turnover = np.zeros(len(base), dtype=float)
    order_count = np.zeros(len(base), dtype=int)
    strategy_log_return = np.zeros(len(base), dtype=float)
    month_log = 0.0
    month_orders = 0
    halted = False
    active_month = None
    previous_position = 0.0
    previous_side = 0
    for index, month_value in enumerate(month):
        if month_value != active_month:
            active_month = month_value
            month_log = 0.0
            month_orders = 0
            halted = False
        side = 0 if halted else int(base[index])
        pos = side * leverage
        turn = abs(pos - previous_position)
        orders = abs(side - previous_side)
        lr = previous_position * raw_return[index] - turn * COST_PER_SIDE
        target[index] = side
        position[index] = pos
        active_position[index] = previous_position
        turnover[index] = turn
        order_count[index] = orders
        strategy_log_return[index] = lr
        month_log += lr
        month_orders += orders
        previous_position = pos
        previous_side = side
        if profit_lock is not None and month_orders >= REQUIRED_MIN_MONTHLY_ORDERS and month_log >= float(profit_lock):
            halted = True
    equity = pd.DataFrame({"timestamp": market["timestamp"], "close": market["close"]})
    equity["raw_log_return"] = raw_return
    equity["position"] = position
    equity["active_position"] = active_position
    equity["turnover"] = turnover
    equity["order_count"] = order_count
    equity["cost"] = turnover * COST_PER_SIDE
    equity["strategy_log_return"] = strategy_log_return
    equity["equity"] = np.exp(np.cumsum(strategy_log_return))
    equity["drawdown"] = equity["equity"] / equity["equity"].cummax() - 1.0
    return target, equity


def _monthly_breakdown(equity: pd.DataFrame) -> pd.DataFrame:
    eq = equity.copy()
    eq["month"] = pd.to_datetime(eq["timestamp"], utc=True).dt.strftime("%Y-%m")
    monthly = eq.groupby("month").agg(
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
    return out.groupby("year").agg(
        log_return=("log_return", "sum"),
        compounded_return_pct=("log_return", lambda values: (np.exp(values.sum()) - 1.0) * 100.0),
        months=("month", "count"),
        losing_months=("return_pct", lambda values: int((values <= 0).sum())),
        min_monthly_return_pct=("return_pct", "min"),
        orders_min=("orders", "min"),
        orders_sum=("orders", "sum"),
        max_drawdown_pct=("drawdown_pct", "min"),
    ).reset_index()


def _row(
    candidate: Candidate,
    target: np.ndarray,
    equity: pd.DataFrame,
    monthly: pd.DataFrame,
    yearly: pd.DataFrame,
) -> dict[str, Any]:
    eval_monthly = monthly.loc[monthly["month"].str[:4].isin(EVAL_YEARS)]
    year_map = {str(row["year"]): float(row["compounded_return_pct"]) for _, row in yearly.iterrows()}
    y2025 = year_map.get("2025")
    y2026 = year_map.get("2026")
    hard_pass = bool(
        y2025 is not None
        and y2026 is not None
        and y2025 > REQUIRED_RETURN_PCT
        and y2026 > REQUIRED_RETURN_PCT
        and not eval_monthly.empty
        and float(eval_monthly["return_pct"].min()) > 0.0
        and int(eval_monthly["orders"].min()) >= REQUIRED_MIN_MONTHLY_ORDERS
    )
    returns = equity["strategy_log_return"]
    return_std = returns.std()
    active_returns = returns[equity["active_position"].abs() > 0]
    losses = active_returns[active_returns < 0].sum()
    gains = active_returns[active_returns > 0].sum()
    return {
        "candidate_id": candidate.candidate_id,
        "kind": candidate.kind,
        "leverage": candidate.leverage,
        "hard_pass": hard_pass,
        "total_return_pct": float((equity["equity"].iloc[-1] - 1.0) * 100.0),
        "return_2025_pct": y2025,
        "return_2026_pct": y2026,
        "min_required_year_return_pct": min(y2025 if y2025 is not None else -999.0, y2026 if y2026 is not None else -999.0),
        "min_monthly_return_pct": float(eval_monthly["return_pct"].min()) if not eval_monthly.empty else None,
        "losing_eval_months": int((eval_monthly["return_pct"] <= 0).sum()) if not eval_monthly.empty else None,
        "min_monthly_orders": int(eval_monthly["orders"].min()) if not eval_monthly.empty else None,
        "max_drawdown_pct": float(equity["drawdown"].min() * 100.0),
        "annualized_sharpe": float(0.0 if return_std == 0 else returns.mean() / return_std * math.sqrt(365 * 24 * 4)),
        "exposure_pct": float((equity["active_position"].abs() > 0).mean() * 100.0),
        "turnover": float(equity["turnover"].sum()),
        "orders": int(equity["order_count"].sum()),
        "segments": int(_segment_count(target)),
        "win_rate_pct": float(0.0 if active_returns.empty else (active_returns > 0).mean() * 100.0),
        "profit_factor": float("inf") if losses == 0 and gains > 0 else float(gains / abs(losses) if losses != 0 else 0.0),
        "params_json": json.dumps(_json_ready(candidate.params), ensure_ascii=False, sort_keys=True),
    }


def _better(row: dict[str, Any], best: dict[str, Any] | None) -> bool:
    if best is None:
        return True
    return _sort_key(row) > _sort_key(best)


def _sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        bool(row.get("hard_pass")),
        float(row.get("min_monthly_return_pct") or -999.0),
        float(row.get("min_required_year_return_pct") or -999.0),
        -float(abs(row.get("max_drawdown_pct") or 999.0)),
        -float(row.get("leverage") or 999.0),
    )


def _sort_columns() -> list[str]:
    return [
        "hard_pass",
        "min_monthly_return_pct",
        "min_required_year_return_pct",
        "max_drawdown_pct",
        "annualized_sharpe",
    ]


def _sort_ascending() -> list[bool]:
    return [False, False, False, False, False]


def _segment_count(target: np.ndarray) -> int:
    active = target != 0
    previous_active = np.r_[False, active[:-1]]
    previous_target = np.r_[0, target[:-1]]
    return int((active & (~previous_active | (np.sign(target) != np.sign(previous_target)))).sum())


def _summary(source: pd.DataFrame, scan: pd.DataFrame, best_payload: dict[str, Any] | None) -> dict[str, Any]:
    hard = scan.loc[scan["hard_pass"].fillna(False)] if not scan.empty else pd.DataFrame()
    best = best_payload["row"] if best_payload else {}
    return {
        "status": "ultimate_monthly_search_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "execution_ready": False,
        "orders_generated": False,
        "orders_submitted": False,
        "live_actions_taken": False,
        "cost_model": {
            "cost_per_side": COST_PER_SIDE,
            "round_trip_open_close": COST_PER_SIDE * 2,
            "note": "0.1% open + 0.1% close = 0.2% round trip; flips cost two sides.",
        },
        "no_future_function_claim": (
            "Signals use only timestamp and closed-bar OHLC/indicator columns. Strategy return uses the prior "
            "bar's target position, so a signal at bar t participates from bar t+1."
        ),
        "dropped_forbidden_columns": source.attrs.get("dropped_forbidden_columns", []),
        "scan_rows": int(len(scan)),
        "hard_pass_rows": int(len(hard)),
        "best_candidate": _json_ready(best),
        "best_yearly": _json_ready(best_payload["yearly"].to_dict("records") if best_payload else []),
        "best_monthly": _json_ready(best_payload["monthly"].to_dict("records") if best_payload else []),
        "requirements": {
            "return_2025_pct_gt": REQUIRED_RETURN_PCT,
            "return_2026_pct_gt": REQUIRED_RETURN_PCT,
            "every_eval_month_return_gt_0": True,
            "min_monthly_orders": REQUIRED_MIN_MONTHLY_ORDERS,
            "eval_note": "2026 means available 2026 data in the file.",
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
    best = summary["best_candidate"]
    lines = [
        "# Ultimate Monthly Search",
        "",
        f"- Status: `{summary['status']}`",
        f"- Scan rows: `{summary['scan_rows']}`",
        f"- Hard pass rows: `{summary['hard_pass_rows']}`",
        f"- Cost: `0.1% open + 0.1% close = 0.2% round trip`",
        "",
        "## Best Candidate",
        "",
        f"- Candidate: `{best.get('candidate_id')}`",
        f"- Kind: `{best.get('kind')}`",
        f"- Hard pass: `{best.get('hard_pass')}`",
        f"- Leverage: `{best.get('leverage')}`",
        f"- 2025 return: `{best.get('return_2025_pct')}`",
        f"- 2026 return: `{best.get('return_2026_pct')}`",
        f"- Min monthly return: `{best.get('min_monthly_return_pct')}`",
        f"- Losing eval months: `{best.get('losing_eval_months')}`",
        f"- Min monthly orders: `{best.get('min_monthly_orders')}`",
        f"- Max drawdown: `{best.get('max_drawdown_pct')}`",
        "",
        "## Guard",
        "",
        "- Research only; no orders generated or submitted.",
        "- Forbidden historical answer columns were dropped before signal generation.",
        "- Signal at bar t only participates in return from bar t+1.",
        "",
    ]
    return "\n".join(lines)


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
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
