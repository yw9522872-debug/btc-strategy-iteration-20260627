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

import search_online_expert_pool_20260627 as source_pool


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "monthly_profit_lock_20260627"
BOUNDS_DIR = ROOT / "artifacts" / "expert_pool_bounds_20260627"

COST_PER_SIDE = 0.001
REQUIRED_RETURN_PCT = 100.0
REQUIRED_MIN_MONTHLY_ORDERS = 10
EVAL_YEARS = {"2025", "2026"}
LEVERAGES = [1.0, 2.0, 4.0, 8.0]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = source_pool._load_features(source_pool.FEATURE_FRAME)
    features = source_pool._add_features(source)
    market = source_pool._market(features)
    experts = source_pool._expert_pool(features)
    target_matrix = np.vstack([expert.target for expert in experts]).astype(np.int8)

    unit_indexes = _candidate_unit_indexes()
    if not unit_indexes:
        unit_indexes = list(range(len(experts) * len(LEVERAGES)))

    rows: list[dict[str, Any]] = []
    best_payload: dict[str, Any] | None = None
    for unit_index in unit_indexes:
        expert_index = unit_index // len(LEVERAGES)
        leverage = LEVERAGES[unit_index % len(LEVERAGES)]
        if expert_index >= len(experts):
            continue
        side = target_matrix[expert_index]
        if _raw_min_eval_orders(side, market) < REQUIRED_MIN_MONTHLY_ORDERS:
            continue
        for lock_log in [0.0, 0.002, 0.005, 0.01, 0.02, 0.04, 0.08, 0.12]:
            for stop_log in [None, -0.03, -0.06, -0.10]:
                row, arrays = _simulate(side, leverage, lock_log, stop_log, None, None, market)
                row.update(
                    {
                        "expert_index": expert_index,
                        "expert_name": experts[expert_index].name,
                        "unit_index": unit_index,
                        "leverage": leverage,
                        "lock_log": lock_log,
                        "stop_log": stop_log,
                        "quota_arm_log": None,
                        "quota_leverage": None,
                        "params_json": json.dumps(
                            {
                                "expert": experts[expert_index].params,
                                "lock_log": lock_log,
                                "stop_log": stop_log,
                                "quota_arm_log": None,
                                "quota_leverage": None,
                                "leverage": leverage,
                                "monthly_lock_after_orders": REQUIRED_MIN_MONTHLY_ORDERS,
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    }
                )
                rows.append(row)
                if best_payload is None or _sort_key(row) > _sort_key(best_payload["row"]):
                    best_payload = _payload(row, arrays, market, experts[expert_index])

    seed_rows = _quota_seed_rows(pd.DataFrame(rows))
    for _, seed in seed_rows.iterrows():
        expert_index = int(seed["expert_index"])
        leverage = float(seed["leverage"])
        side = target_matrix[expert_index]
        for lock_log in [0.02, 0.04]:
            for quota_arm_log in [0.04, 0.08, 0.12]:
                for quota_leverage in [0.1, 0.25, 0.5, 1.0, 2.0]:
                    row, arrays = _simulate(side, leverage, lock_log, None, quota_arm_log, quota_leverage, market)
                    row.update(
                        {
                            "expert_index": expert_index,
                            "expert_name": experts[expert_index].name,
                            "unit_index": int(seed["unit_index"]),
                            "leverage": leverage,
                            "lock_log": lock_log,
                            "stop_log": None,
                            "quota_arm_log": quota_arm_log,
                            "quota_leverage": quota_leverage,
                            "params_json": json.dumps(
                                {
                                    "expert": experts[expert_index].params,
                                    "lock_log": lock_log,
                                    "stop_log": None,
                                    "quota_arm_log": quota_arm_log,
                                    "quota_leverage": quota_leverage,
                                    "leverage": leverage,
                                    "monthly_lock_after_orders": REQUIRED_MIN_MONTHLY_ORDERS,
                                },
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                        }
                    )
                    rows.append(row)
                    if best_payload is None or _sort_key(row) > _sort_key(best_payload["row"]):
                        best_payload = _payload(row, arrays, market, experts[expert_index])

    scan = pd.DataFrame(rows).sort_values(_sort_columns(), ascending=_sort_ascending()).reset_index(drop=True)
    scan.to_csv(OUT_DIR / "scan.csv", index=False)
    if best_payload:
        best_payload["signals"].to_csv(OUT_DIR / "best_signals.csv", index=False)
        best_payload["equity"].to_csv(OUT_DIR / "best_equity.csv", index=False)
        best_payload["monthly"].to_csv(OUT_DIR / "best_monthly.csv", index=False)
        best_payload["yearly"].to_csv(OUT_DIR / "best_yearly.csv", index=False)

    summary = {
        "status": "monthly_profit_lock_search_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "strict_no_future_function": True,
        "posthoc_parameter_selection": True,
        "notes": (
            "This scans fixed expert rules with a causal monthly lock: after a month has at least "
            "10 real orders and current month net log return reaches the lock threshold, the strategy "
            "goes flat for the rest of that month. A second causal quota-completion mode may reduce "
            "notional exposure after the month is already profitable but before the 10-order quota is met. "
            "Candidate parameters are still selected after this research scan, so this is not a live guarantee."
        ),
        "cost_model": {"cost_per_side": COST_PER_SIDE, "round_trip_open_close": COST_PER_SIDE * 2},
        "candidate_units": len(unit_indexes),
        "scan_rows": int(len(scan)),
        "hard_pass_rows": int(scan["hard_pass"].fillna(False).sum()) if not scan.empty else 0,
        "best_candidate": _json_ready(best_payload["row"] if best_payload else {}),
        "best_monthly": _json_ready(best_payload["monthly"].to_dict("records") if best_payload else []),
        "best_yearly": _json_ready(best_payload["yearly"].to_dict("records") if best_payload else []),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "source_pool_script_sha256": _sha256(ROOT / "scripts" / "search_online_expert_pool_20260627.py"),
            "feature_frame_sha256": _sha256(source_pool.FEATURE_FRAME),
            "best_signals_sha256": _sha256(OUT_DIR / "best_signals.csv") if best_payload else None,
        },
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "scan": _relpath(OUT_DIR / "scan.csv"),
            "best_signals": _relpath(OUT_DIR / "best_signals.csv") if best_payload else None,
            "best_equity": _relpath(OUT_DIR / "best_equity.csv") if best_payload else None,
            "best_monthly": _relpath(OUT_DIR / "best_monthly.csv") if best_payload else None,
            "best_yearly": _relpath(OUT_DIR / "best_yearly.csv") if best_payload else None,
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _candidate_unit_indexes() -> list[int]:
    indexes: set[int] = set()
    choices_path = BOUNDS_DIR / "monthly_posthoc_best_oracle_choices.csv"
    if choices_path.exists():
        choices = pd.read_csv(choices_path)
        indexes.update(int(value) for value in choices["unit_index"].dropna().astype(int))
        for expert_index in choices["expert_index"].dropna().astype(int).unique():
            for leverage_index in range(len(LEVERAGES)):
                indexes.add(int(expert_index) * len(LEVERAGES) + leverage_index)

    static_path = BOUNDS_DIR / "static_single_expert_scan.csv"
    if static_path.exists():
        static = pd.read_csv(static_path)
        static = static.sort_values(
            ["losing_eval_months", "min_monthly_return_pct", "min_required_year_return_pct"],
            ascending=[True, False, False],
        )
        top_static = static.head(240)
        indexes.update(int(value) for value in top_static["unit_index"].dropna().astype(int))
        for expert_index in top_static["expert_index"].dropna().astype(int).unique():
            for leverage_index in range(len(LEVERAGES)):
                indexes.add(int(expert_index) * len(LEVERAGES) + leverage_index)

    return sorted(indexes)


def _quota_seed_rows(scan: pd.DataFrame) -> pd.DataFrame:
    if scan.empty:
        return scan
    strong = scan.loc[
        (scan["return_2025_pct"] > REQUIRED_RETURN_PCT)
        & (scan["return_2026_pct"] > REQUIRED_RETURN_PCT)
        & (scan["losing_eval_months"] <= 3)
        & (scan["min_monthly_orders"] >= REQUIRED_MIN_MONTHLY_ORDERS)
    ]
    near = scan.sort_values(
        ["losing_eval_months", "min_monthly_return_pct", "min_required_year_return_pct"],
        ascending=[True, False, False],
    ).head(40)
    seeds = pd.concat([strong, near], ignore_index=True)
    return seeds.drop_duplicates(["unit_index", "leverage"]).reset_index(drop=True)


def _raw_min_eval_orders(side: np.ndarray, market: dict[str, Any]) -> int:
    orders = np.abs(side.astype(int) - np.r_[0, side[:-1]].astype(int))
    month_orders = np.add.reduceat(orders, market["month_starts"])
    eval_orders = month_orders[market["eval_month_mask"]]
    return int(eval_orders.min()) if len(eval_orders) else 0


def _simulate(
    side: np.ndarray,
    leverage: float,
    lock_log: float,
    stop_log: float | None,
    quota_arm_log: float | None,
    quota_leverage: float | None,
    market: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    n = len(side)
    target = np.zeros(n, dtype=np.int8)
    position = np.zeros(n, dtype=float)
    active_position = np.zeros(n, dtype=float)
    turnover = np.zeros(n, dtype=float)
    order_count = np.zeros(n, dtype=int)
    strategy_log_return = np.zeros(n, dtype=float)

    raw_return = market["raw_return"]
    previous_position = 0.0
    previous_side = 0
    for start, end in zip(market["month_starts"], np.r_[market["month_starts"][1:], n]):
        month_log = 0.0
        month_orders = 0
        halted = False
        quota_mode = False
        for index in range(start, end):
            current_side = 0 if halted else int(side[index])
            effective_leverage = (
                float(quota_leverage)
                if quota_mode and month_orders < REQUIRED_MIN_MONTHLY_ORDERS and quota_leverage is not None
                else leverage
            )
            current_position = current_side * effective_leverage
            current_turnover = abs(current_position - previous_position)
            current_orders = abs(current_side - previous_side)
            current_lr = previous_position * raw_return[index] - current_turnover * COST_PER_SIDE

            target[index] = current_side
            position[index] = current_position
            active_position[index] = previous_position
            turnover[index] = current_turnover
            order_count[index] = current_orders
            strategy_log_return[index] = current_lr

            month_log += current_lr
            month_orders += current_orders
            previous_position = current_position
            previous_side = current_side

            if (
                quota_arm_log is not None
                and quota_leverage is not None
                and not halted
                and not quota_mode
                and month_orders < REQUIRED_MIN_MONTHLY_ORDERS
                and month_log >= quota_arm_log
            ):
                quota_mode = True
            if not halted and month_orders >= REQUIRED_MIN_MONTHLY_ORDERS and month_log >= lock_log:
                halted = True
            if stop_log is not None and not halted and month_orders >= REQUIRED_MIN_MONTHLY_ORDERS and month_log <= stop_log:
                halted = True

    equity = np.exp(np.cumsum(strategy_log_return))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    row = _row(strategy_log_return, order_count, turnover, active_position, drawdown, equity, market)
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


def _row(
    strategy_log_return: np.ndarray,
    order_count: np.ndarray,
    turnover: np.ndarray,
    active_position: np.ndarray,
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
    active_returns = returns[np.abs(active_position) > 0]
    losses = float(active_returns[active_returns < 0].sum())
    gains = float(active_returns[active_returns > 0].sum())
    return {
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
        "win_rate_pct": float(0.0 if active_returns.empty else (active_returns > 0).mean() * 100.0),
        "profit_factor": float("inf") if losses == 0 and gains > 0 else float(gains / abs(losses) if losses != 0 else 0.0),
    }


def _payload(row: dict[str, Any], arrays: dict[str, np.ndarray], market: dict[str, Any], expert: source_pool.Expert) -> dict[str, Any]:
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
            "component": np.where(arrays["target"] != 0, expert.name, "flat"),
            "candidate_version": "monthly_profit_lock",
        }
    )
    return {"row": row, "signals": signals, "equity": equity, "monthly": monthly, "yearly": yearly}


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
            min_monthly_orders=("orders", "min"),
            orders_sum=("orders", "sum"),
            max_drawdown_pct=("drawdown_pct", "min"),
        )
        .reset_index()
    )


def _sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        bool(row.get("hard_pass")),
        -int(row.get("losing_eval_months") if row.get("losing_eval_months") is not None else 999),
        float(row.get("min_monthly_return_pct") or -999.0),
        float(row.get("min_required_year_return_pct") or -999.0),
        int(row.get("min_monthly_orders") or 0),
    )


def _sort_columns() -> list[str]:
    return ["hard_pass", "losing_eval_months", "min_monthly_return_pct", "min_required_year_return_pct", "min_monthly_orders"]


def _sort_ascending() -> list[bool]:
    return [False, True, False, False, False]


def _render_report(summary: dict[str, Any]) -> str:
    best = summary.get("best_candidate") or {}
    return "\n".join(
        [
            "# Monthly Profit Lock Search",
            "",
            f"- status: `{summary['status']}`",
            f"- strict_no_future_function: `{summary['strict_no_future_function']}`",
            f"- posthoc_parameter_selection: `{summary['posthoc_parameter_selection']}`",
            f"- candidate_units: `{summary['candidate_units']}`",
            f"- scan_rows: `{summary['scan_rows']}`",
            f"- hard_pass_rows: `{summary['hard_pass_rows']}`",
            "",
            "## Best Candidate",
            "",
            f"- hard_pass: `{best.get('hard_pass')}`",
            f"- return_2025_pct: `{best.get('return_2025_pct')}`",
            f"- return_2026_pct: `{best.get('return_2026_pct')}`",
            f"- min_monthly_return_pct: `{best.get('min_monthly_return_pct')}`",
            f"- losing_eval_months: `{best.get('losing_eval_months')}`",
            f"- min_monthly_orders: `{best.get('min_monthly_orders')}`",
        ]
    ) + "\n"


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
