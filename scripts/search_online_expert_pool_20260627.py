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
OUT_DIR = ARTIFACTS / "online_expert_pool_20260627"
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
class Expert:
    name: str
    target: np.ndarray
    params: dict[str, Any]


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    leverage: float
    hold_winner_bars: int
    switch_margin_log: float
    default_expert: int
    quota_mode: str
    params: dict[str, Any]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = _load_features(FEATURE_FRAME)
    features = _add_features(source)
    market = _market(features)
    experts = _expert_pool(features)
    target_matrix = np.vstack([expert.target for expert in experts]).astype(np.int8)
    expert_score_base = _monthly_expert_score_base(target_matrix, market)

    rows: list[dict[str, Any]] = []
    best_payload: dict[str, Any] | None = None
    for candidate in _candidate_stream(experts):
        row, arrays = _run_online_selector(candidate, target_matrix, expert_score_base, market)
        rows.append(row)
        if _better(row, best_payload["row"] if best_payload else None):
            best_payload = _payload(candidate, row, arrays, market, experts)

    scan = pd.DataFrame(rows).sort_values(_sort_columns(), ascending=_sort_ascending()).reset_index(drop=True)
    scan.to_csv(OUT_DIR / "scan.csv", index=False)

    if best_payload:
        best_payload["signals"].to_csv(OUT_DIR / "best_signals.csv", index=False)
        best_payload["equity"].to_csv(OUT_DIR / "best_equity.csv", index=False)
        best_payload["monthly"].to_csv(OUT_DIR / "best_monthly.csv", index=False)
        best_payload["yearly"].to_csv(OUT_DIR / "best_yearly.csv", index=False)
        best_payload["expert_usage"].to_csv(OUT_DIR / "best_expert_usage.csv", index=False)

    summary = {
        "status": "online_expert_pool_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "strict_no_future_function": True,
        "signal_timing": "At bar t close, only bar-t-or-earlier features and current-month realized virtual PnL are used; target participates from bar t+1.",
        "training_or_selection_note": "The expert pool is fixed rule logic. Candidate selector settings are scanned on the historical file, so this is research/backtest selection, not a live guarantee.",
        "cost_model": {
            "cost_per_side": COST_PER_SIDE,
            "round_trip_open_close": COST_PER_SIDE * 2,
        },
        "dropped_forbidden_columns": source.attrs.get("dropped_forbidden_columns", []),
        "expert_count": len(experts),
        "scan_rows": int(len(scan)),
        "hard_pass_rows": int(scan["hard_pass"].fillna(False).sum()),
        "best_candidate": _json_ready(best_payload["row"] if best_payload else {}),
        "best_monthly": _json_ready(best_payload["monthly"].to_dict("records") if best_payload else []),
        "best_yearly": _json_ready(best_payload["yearly"].to_dict("records") if best_payload else []),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "feature_frame_sha256": _sha256(FEATURE_FRAME),
            "best_signals_sha256": _sha256(OUT_DIR / "best_signals.csv") if best_payload else None,
        },
        "files": {
            "summary": str(OUT_DIR / "summary.json"),
            "scan": str(OUT_DIR / "scan.csv"),
            "best_signals": str(OUT_DIR / "best_signals.csv") if best_payload else None,
            "best_equity": str(OUT_DIR / "best_equity.csv") if best_payload else None,
            "best_monthly": str(OUT_DIR / "best_monthly.csv") if best_payload else None,
            "best_yearly": str(OUT_DIR / "best_yearly.csv") if best_payload else None,
            "best_expert_usage": str(OUT_DIR / "best_expert_usage.csv") if best_payload else None,
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
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
    return {
        "timestamp": timestamp,
        "close": frame["close"].astype(float).to_numpy(float),
        "raw_return": raw_return,
        "month": month,
        "year": year,
        "month_starts": month_starts,
        "month_labels": month[month_starts],
        "eval_month_mask": np.array([label[:4] in EVAL_YEARS for label in month[month_starts]]),
        "year_starts": year_starts,
        "year_labels": year[year_starts],
    }


def _expert_pool(features: pd.DataFrame) -> list[Expert]:
    experts: list[Expert] = []
    n = len(features)

    def add(name: str, target: np.ndarray, params: dict[str, Any]) -> None:
        target = target.astype(np.int8)
        if np.count_nonzero(target) == 0:
            return
        if any(np.array_equal(target, expert.target) for expert in experts):
            return
        experts.append(Expert(name=name, target=target, params=params))

    add("always_long", np.ones(n, dtype=np.int8), {"family": "always_long"})
    add("always_short", -np.ones(n, dtype=np.int8), {"family": "always_short"})

    for window in [4, 8, 16, 32, 64, 96, 192, 384, 672]:
        ret = features[f"ret_{window}_bps"]
        for threshold in [25.0, 50.0, 100.0, 200.0, 350.0]:
            state = _state_from(ret.ge(threshold), ret.le(-threshold))
            add("ret_state", state, {"family": "ret_state", "window": window, "threshold_bps": threshold})
            add("ret_state_flip", -state, {"family": "ret_state_flip", "window": window, "threshold_bps": threshold})

    trend_gap = features["trend_close_ema_gap_bps_60"]
    adx = features["trend_adx_30"]
    for gap_min in [25.0, 50.0, 100.0, 200.0]:
        for adx_min in [18.0, 24.0, 30.0, 36.0]:
            state = _state_from(trend_gap.ge(gap_min) & adx.ge(adx_min), trend_gap.le(-gap_min) & adx.ge(adx_min))
            add("gap_adx_state", state, {"family": "gap_adx_state", "gap_min": gap_min, "adx_min": adx_min})
            add("gap_adx_state_flip", -state, {"family": "gap_adx_state_flip", "gap_min": gap_min, "adx_min": adx_min})

    trigger_defs = list(_trigger_defs(features))
    for trigger_name, long_trigger, short_trigger, trigger_params in trigger_defs:
        event = np.zeros(n, dtype=np.int8)
        event[long_trigger] = 1
        event[short_trigger] = -1
        if np.count_nonzero(event) < 20:
            continue
        for hold_bars in [1, 2, 4, 8, 16, 32]:
            target = _fixed_hold_target(event, hold_bars)
            add(trigger_name, target, {**trigger_params, "hold_bars": hold_bars})
            add(f"{trigger_name}_flip", -target, {**trigger_params, "hold_bars": hold_bars, "flipped": True})

    return experts


def _trigger_defs(features: pd.DataFrame):
    for window in [1, 2, 4, 8, 16, 32, 64, 96]:
        ret = features[f"ret_{window}_bps"]
        for threshold in [25.0, 50.0, 100.0, 200.0, 350.0]:
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
    for low, high in [(20.0, 80.0), (30.0, 70.0), (40.0, 60.0), (45.0, 55.0)]:
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
    for low, high in [(0.10, 0.90), (0.20, 0.80), (0.35, 0.65), (0.45, 0.55)]:
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
    for low, high in [(0.10, 0.90), (0.20, 0.80), (0.35, 0.65), (0.45, 0.55)]:
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


def _candidate_stream(experts: list[Expert]):
    default_names = ["always_long", "always_short", "ret_state", "gap_adx_state", "ret_momentum", "ret_fade"]
    default_indexes: list[int] = []
    for default_name in default_names:
        for index, expert in enumerate(experts):
            if expert.name == default_name:
                default_indexes.append(index)
                break
    default_indexes = list(dict.fromkeys(default_indexes))
    if not default_indexes:
        default_indexes = [0]

    default_indexes = default_indexes[:2]
    for leverage in [1.0, 2.0, 4.0, 8.0]:
        for hold_winner_bars in [1, 16]:
            for switch_margin_log in [0.0, 0.005]:
                for default_expert in default_indexes:
                    for quota_mode in ["none", "last_day_alternate"]:
                        params = {
                            "leverage": leverage,
                            "hold_winner_bars": hold_winner_bars,
                            "switch_margin_log": switch_margin_log,
                            "default_expert_index": default_expert,
                            "default_expert_name": experts[default_expert].name,
                            "quota_mode": quota_mode,
                        }
                        digest = hashlib.sha1(json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()[:10]
                        yield Candidate(
                            candidate_id=f"online_expert_pool_{digest}_lev{leverage}",
                            leverage=leverage,
                            hold_winner_bars=hold_winner_bars,
                            switch_margin_log=switch_margin_log,
                            default_expert=default_expert,
                            quota_mode=quota_mode,
                            params=params,
                        )


def _run_online_selector(
    candidate: Candidate,
    target_matrix: np.ndarray,
    expert_score_base: np.ndarray,
    market: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    expert_count, n = target_matrix.shape
    raw_return = market["raw_return"]
    month = market["month"]
    month_end_index = _month_end_index(month)
    best_expert_by_bar = np.argmax(expert_score_base, axis=0).astype(np.int32)
    best_score_by_bar = expert_score_base[best_expert_by_bar, np.arange(n)]

    target = np.zeros(n, dtype=np.int8)
    selected_expert = np.full(n, candidate.default_expert, dtype=np.int32)
    position = np.zeros(n, dtype=float)
    active_position = np.zeros(n, dtype=float)
    turnover = np.zeros(n, dtype=float)
    order_count = np.zeros(n, dtype=int)
    strategy_log_return = np.zeros(n, dtype=float)

    active_month = None
    current_expert = candidate.default_expert
    hold_remaining = 0
    previous_position = 0.0
    previous_side = 0
    month_orders = 0
    quota_toggle = 1

    leverage = float(candidate.leverage)
    for index in range(n):
        if month[index] != active_month:
            active_month = month[index]
            current_expert = candidate.default_expert
            hold_remaining = 0
            month_orders = 0
            quota_toggle = 1

        if hold_remaining <= 0:
            best_expert = int(best_expert_by_bar[index])
            best_score = float(best_score_by_bar[index]) * leverage
            current_score = float(expert_score_base[current_expert, index]) * leverage
            if best_expert != current_expert and best_score > current_score + candidate.switch_margin_log:
                current_expert = best_expert
                hold_remaining = candidate.hold_winner_bars
        else:
            hold_remaining -= 1

        side = int(target_matrix[current_expert, index])
        if candidate.quota_mode == "last_day_alternate":
            bars_left = int(month_end_index[index] - index + 1)
            needed_orders = REQUIRED_MIN_MONTHLY_ORDERS - month_orders
            if needed_orders > 0 and bars_left <= needed_orders:
                side = quota_toggle
                quota_toggle *= -1

        pos = side * leverage
        turn = abs(pos - previous_position)
        orders = abs(side - previous_side)
        lr = previous_position * raw_return[index] - turn * COST_PER_SIDE

        selected_expert[index] = current_expert
        target[index] = side
        position[index] = pos
        active_position[index] = previous_position
        turnover[index] = turn
        order_count[index] = orders
        strategy_log_return[index] = lr

        month_orders += orders
        previous_position = pos
        previous_side = side

    equity = np.exp(np.cumsum(strategy_log_return))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    row = _row(candidate, target, selected_expert, strategy_log_return, turnover, order_count, drawdown, equity, market)
    return row, {
        "target": target,
        "selected_expert": selected_expert,
        "position": position,
        "active_position": active_position,
        "turnover": turnover,
        "order_count": order_count,
        "strategy_log_return": strategy_log_return,
        "equity": equity,
        "drawdown": drawdown,
    }


def _monthly_expert_score_base(target_matrix: np.ndarray, market: dict[str, Any]) -> np.ndarray:
    expert_count, n = target_matrix.shape
    score = np.zeros((expert_count, n), dtype=np.float32)
    raw_return = market["raw_return"]
    starts = market["month_starts"]
    ends = np.r_[starts[1:], n]
    for start, end in zip(starts, ends):
        target = target_matrix[:, start:end].astype(np.float32)
        previous = np.zeros_like(target)
        if target.shape[1] > 1:
            previous[:, 1:] = target[:, :-1]
        turnover = np.abs(target - previous)
        log_return = previous * raw_return[start:end].astype(np.float32) - turnover * np.float32(COST_PER_SIDE)
        score[:, start:end] = np.cumsum(log_return, axis=1)
    return score


def _month_end_index(month: np.ndarray) -> np.ndarray:
    end_index = np.zeros(len(month), dtype=np.int32)
    starts = np.r_[0, np.flatnonzero(month[1:] != month[:-1]) + 1]
    ends = np.r_[starts[1:] - 1, len(month) - 1]
    for start, end in zip(starts, ends):
        end_index[start : end + 1] = end
    return end_index


def _row(
    candidate: Candidate,
    target: np.ndarray,
    selected_expert: np.ndarray,
    strategy_log_return: np.ndarray,
    turnover: np.ndarray,
    order_count: np.ndarray,
    drawdown: np.ndarray,
    equity: np.ndarray,
    market: dict[str, Any],
) -> dict[str, Any]:
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
    active_position = np.r_[0.0, candidate.leverage * target[:-1].astype(float)]
    active_returns = returns[np.abs(active_position) > 0]
    losses = float(active_returns[active_returns < 0].sum())
    gains = float(active_returns[active_returns > 0].sum())
    unique_experts = int(len(np.unique(selected_expert)))
    return {
        "candidate_id": candidate.candidate_id,
        "hard_pass": hard_pass,
        "return_2025_pct": y2025,
        "return_2026_pct": y2026,
        "min_required_year_return_pct": min(y2025 if y2025 is not None else -999.0, y2026 if y2026 is not None else -999.0),
        "min_monthly_return_pct": float(monthly_return_pct.min()) if len(monthly_return_pct) else None,
        "losing_eval_months": int((monthly_return_pct <= 0).sum()) if len(monthly_return_pct) else None,
        "min_monthly_orders": int(eval_orders.min()) if len(eval_orders) else None,
        "total_return_pct": float((equity[-1] - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "annualized_sharpe": float(0.0 if return_std == 0 else returns.mean() / return_std * math.sqrt(365 * 24 * 4)),
        "exposure_pct": float((np.abs(active_position) > 0).mean() * 100.0),
        "turnover": float(turnover.sum()),
        "orders": int(order_count.sum()),
        "segments": int(_segment_count(target)),
        "unique_experts_used": unique_experts,
        "win_rate_pct": float(0.0 if active_returns.empty else (active_returns > 0).mean() * 100.0),
        "profit_factor": float("inf") if losses == 0 and gains > 0 else float(gains / abs(losses) if losses != 0 else 0.0),
        "params_json": json.dumps(_json_ready(candidate.params), ensure_ascii=False, sort_keys=True),
    }


def _payload(
    candidate: Candidate,
    row: dict[str, Any],
    arrays: dict[str, np.ndarray],
    market: dict[str, Any],
    experts: list[Expert],
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
            "selected_expert": arrays["selected_expert"],
            "selected_expert_name": [experts[int(index)].name for index in arrays["selected_expert"]],
        }
    )
    monthly = _monthly_breakdown(equity)
    yearly = _yearly_breakdown(monthly)
    signals = pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "close": market["close"],
            "target_position": arrays["target"].astype(float),
            "component": [experts[int(index)].name if arrays["target"][i] != 0 else "flat" for i, index in enumerate(arrays["selected_expert"])],
            "candidate_version": candidate.candidate_id,
        }
    )
    expert_usage = (
        equity.groupby("selected_expert_name")
        .agg(bars=("selected_expert_name", "size"), log_return=("strategy_log_return", "sum"), orders=("order_count", "sum"))
        .sort_values("bars", ascending=False)
        .reset_index()
    )
    return {
        "row": row,
        "signals": signals,
        "equity": equity,
        "monthly": monthly,
        "yearly": yearly,
        "expert_usage": expert_usage,
    }


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


def _segment_count(target: np.ndarray) -> int:
    previous = np.r_[0, target[:-1]]
    return int(((target != 0) & (target != previous)).sum())


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
    return [
        "hard_pass",
        "losing_eval_months",
        "min_monthly_return_pct",
        "min_required_year_return_pct",
        "max_drawdown_pct",
    ]


def _sort_ascending() -> list[bool]:
    return [False, True, False, False, False]


def _render_report(summary: dict[str, Any]) -> str:
    best = summary.get("best_candidate") or {}
    lines = [
        "# Online Expert Pool Search",
        "",
        f"- status: `{summary['status']}`",
        f"- strict_no_future_function: `{summary['strict_no_future_function']}`",
        f"- expert_count: `{summary['expert_count']}`",
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
    ]
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False), encoding="utf-8")


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
