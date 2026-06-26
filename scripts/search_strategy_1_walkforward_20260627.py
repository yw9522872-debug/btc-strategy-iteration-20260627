from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import search_monthly_profit_lock_20260627 as lock_search
import search_online_expert_pool_20260627 as source_pool
import validate_profit_lock_overfit_20260627 as overfit
import validate_profit_lock_walkforward_20260627 as wf0


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_1_walkforward_20260627"
TRAIN_START_MONTH = "2024-01"
STRATEGY_ID = "strategy_1_walkforward_ret_state_selector_20260627"

WINDOWS = {16, 32, 64, 96, 192}
THRESHOLDS = {50.0, 100.0, 200.0}
LEVERAGES = [4.0, 6.0, 8.0]
LOCK_LOGS = [0.02, 0.04, 0.08]
QUOTA_CHOICES = [(None, None), (0.04, 0.25), (0.04, 1.0), (0.04, 2.0), (0.08, 0.25), (0.08, 1.0), (0.08, 2.0)]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = source_pool._load_features(source_pool.FEATURE_FRAME)
    features = source_pool._add_features(source)
    market = source_pool._market(features)
    experts = _ret_state_experts(source_pool._expert_pool(features))
    target_matrix = np.vstack([expert.target for expert in experts]).astype(np.int8)

    candidates = _candidate_results(target_matrix, experts, market)
    eval_months = [str(month) for month in market["month_labels"] if str(month)[:4] in lock_search.EVAL_YEARS]
    selections = [_select_for_month(month, candidates, experts) for month in eval_months]
    wf0._assert_no_future(selections)

    equity = _simulate_walkforward(target_matrix, market, {row["eval_month"]: row for row in selections})
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)
    row = _result_row(equity, monthly, yearly)

    selection_frame = pd.DataFrame(selections)
    selection_frame.to_csv(OUT_DIR / "strategy_1_selections.csv", index=False)
    equity.to_csv(OUT_DIR / "strategy_1_equity.csv", index=False)
    monthly.to_csv(OUT_DIR / "strategy_1_monthly.csv", index=False)
    yearly.to_csv(OUT_DIR / "strategy_1_yearly.csv", index=False)

    summary = {
        "status": "strategy_1_walkforward_ready",
        "strategy_id": STRATEGY_ID,
        "research_only": True,
        "live_trading_enabled": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strict_no_future_selection": True,
        "not_a_freeze_yet": True,
        "selection_rule": (
            "For each evaluated month, choose ret_state window/threshold plus lock/quota/leverage "
            f"using only months from {TRAIN_START_MONTH} through the month before the evaluated month."
        ),
        "signal_pool": {
            "family": "ret_state",
            "windows": sorted(WINDOWS),
            "threshold_bps": sorted(THRESHOLDS),
            "expert_count": len(experts),
        },
        "control_pool": {
            "leverages": LEVERAGES,
            "lock_logs": LOCK_LOGS,
            "quota_choices": QUOTA_CHOICES,
        },
        "cost_model": {
            "cost_per_side": lock_search.COST_PER_SIDE,
            "round_trip_open_close": lock_search.COST_PER_SIDE * 2,
        },
        "candidate_count": len(candidates),
        "eval_month_count": len(eval_months),
        "row": lock_search._json_ready(row),
        "yearly": lock_search._json_ready(yearly.to_dict("records")),
        "monthly": lock_search._json_ready(monthly[["month", "return_pct", "orders", "drawdown_pct"]].to_dict("records")),
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "selections": _relpath(OUT_DIR / "strategy_1_selections.csv"),
            "equity": _relpath(OUT_DIR / "strategy_1_equity.csv"),
            "monthly": _relpath(OUT_DIR / "strategy_1_monthly.csv"),
            "yearly": _relpath(OUT_DIR / "strategy_1_yearly.csv"),
        },
        "risk_flags": {
            "uses_future_bars_for_signal": False,
            "monthly_selection_uses_eval_month": False,
            "posthoc_pool_design": True,
            "not_a_live_guarantee": True,
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _ret_state_experts(experts: list[source_pool.Expert]) -> list[source_pool.Expert]:
    return [
        expert
        for expert in experts
        if expert.name == "ret_state"
        and int(expert.params.get("window", -1)) in WINDOWS
        and float(expert.params.get("threshold_bps", -1.0)) in THRESHOLDS
    ]


def _candidate_results(
    target_matrix: np.ndarray,
    experts: list[source_pool.Expert],
    market: dict[str, Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for expert_index, expert in enumerate(experts):
        side = target_matrix[expert_index]
        if lock_search._raw_min_eval_orders(side, market) < lock_search.REQUIRED_MIN_MONTHLY_ORDERS:
            continue
        for params in _param_grid():
            _, arrays = lock_search._simulate(
                side,
                params["leverage"],
                params["lock_log"],
                None,
                params["quota_arm_log"],
                params["quota_leverage"],
                market,
            )
            monthly = overfit._arrays_to_monthly(arrays, market)
            candidate_id = len(out)
            out.append(
                {
                    "candidate_id": candidate_id,
                    "expert_index": expert_index,
                    "expert": expert.params,
                    "params": params,
                    "monthly": monthly,
                }
            )
    return out


def _param_grid() -> list[dict[str, Any]]:
    return [
        {"leverage": leverage, "lock_log": lock_log, "quota_arm_log": quota_arm_log, "quota_leverage": quota_leverage}
        for leverage in LEVERAGES
        for lock_log in LOCK_LOGS
        for quota_arm_log, quota_leverage in QUOTA_CHOICES
    ]


def _select_for_month(
    eval_month: str,
    candidates: list[dict[str, Any]],
    experts: list[source_pool.Expert],
) -> dict[str, Any]:
    best_key: tuple[Any, ...] | None = None
    best_row: dict[str, Any] | None = None
    for candidate in candidates:
        score = wf0._score_before_month(candidate["monthly"], eval_month)
        key = (
            score["return_pct"] > lock_search.REQUIRED_RETURN_PCT
            and score["losing_months"] == 0
            and score["min_orders"] >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS,
            -score["losing_months"],
            score["min_month_return_pct"],
            score["return_pct"],
            score["min_orders"],
        )
        if best_key is None or key > best_key:
            params = candidate["params"]
            expert = experts[candidate["expert_index"]]
            best_key = key
            best_row = {
                "eval_month": eval_month,
                "train_start_month": TRAIN_START_MONTH,
                "train_end_month": score["last_month"],
                "candidate_id": candidate["candidate_id"],
                "expert_index": candidate["expert_index"],
                "expert_family": expert.name,
                "window": expert.params["window"],
                "threshold_bps": expert.params["threshold_bps"],
                **params,
                **{f"train_{key}": value for key, value in score.items() if key != "last_month"},
            }
    if best_row is None:
        raise RuntimeError(f"No candidate selected for {eval_month}")
    return best_row


def _simulate_walkforward(
    target_matrix: np.ndarray,
    market: dict[str, Any],
    selections: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    previous_position = 0.0
    previous_side = 0
    timestamp = market["timestamp"].reset_index(drop=True)
    for start, end in zip(market["month_starts"], np.r_[market["month_starts"][1:], target_matrix.shape[1]]):
        month = str(market["month"][start])
        params = selections.get(month)
        if params is None:
            continue
        side = target_matrix[int(params["expert_index"])]
        month_log = 0.0
        month_orders = 0
        halted = False
        quota_mode = False
        for index in range(start, end):
            current_side = 0 if halted else int(side[index])
            effective_leverage = (
                float(params["quota_leverage"])
                if quota_mode
                and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS
                and params["quota_leverage"] is not None
                else float(params["leverage"])
            )
            current_position = current_side * effective_leverage
            current_turnover = abs(current_position - previous_position)
            current_orders = abs(current_side - previous_side)
            current_lr = previous_position * market["raw_return"][index] - current_turnover * lock_search.COST_PER_SIDE

            records.append(
                {
                    "timestamp": timestamp.iloc[index],
                    "close": market["close"][index],
                    "target_side": current_side,
                    "position": current_position,
                    "active_position": previous_position,
                    "turnover": current_turnover,
                    "order_count": current_orders,
                    "strategy_log_return": current_lr,
                    "candidate_id": params["candidate_id"],
                    "window": params["window"],
                    "threshold_bps": params["threshold_bps"],
                }
            )

            month_log += current_lr
            month_orders += current_orders
            previous_position = current_position
            previous_side = current_side

            if (
                params["quota_arm_log"] is not None
                and params["quota_leverage"] is not None
                and not halted
                and not quota_mode
                and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS
                and month_log >= float(params["quota_arm_log"])
            ):
                quota_mode = True
            if not halted and month_orders >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS and month_log >= float(params["lock_log"]):
                halted = True

    equity = pd.DataFrame(records)
    equity["equity"] = np.exp(equity["strategy_log_return"].cumsum())
    equity["drawdown"] = equity["equity"] / equity["equity"].cummax() - 1.0
    return equity


def _result_row(equity: pd.DataFrame, monthly: pd.DataFrame, yearly: pd.DataFrame) -> dict[str, Any]:
    year_map = dict(zip(yearly["year"], yearly["compounded_return_pct"]))
    y2025 = float(year_map.get("2025", -999.0))
    y2026 = float(year_map.get("2026", -999.0))
    eval_monthly = monthly.loc[monthly["month"].str[:4].isin(lock_search.EVAL_YEARS)]
    returns = equity["strategy_log_return"]
    active_returns = returns[equity["active_position"].abs() > 0]
    losses = float(active_returns[active_returns < 0].sum())
    gains = float(active_returns[active_returns > 0].sum())
    return_std = float(returns.std())
    min_monthly_orders = int(eval_monthly["orders"].min()) if not eval_monthly.empty else 0
    min_monthly_return = float(eval_monthly["return_pct"].min()) if not eval_monthly.empty else -999.0
    losing_months = int((eval_monthly["return_pct"] <= 0).sum())
    return {
        "hard_pass": bool(
            y2025 > lock_search.REQUIRED_RETURN_PCT
            and y2026 > lock_search.REQUIRED_RETURN_PCT
            and min_monthly_return > 0
            and min_monthly_orders >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS
        ),
        "return_2025_pct": y2025,
        "return_2026_pct": y2026,
        "min_required_year_return_pct": min(y2025, y2026),
        "min_monthly_return_pct": min_monthly_return,
        "losing_eval_months": losing_months,
        "min_monthly_orders": min_monthly_orders,
        "total_return_pct": float((equity["equity"].iloc[-1] - 1.0) * 100.0),
        "max_drawdown_pct": float(equity["drawdown"].min() * 100.0),
        "annualized_sharpe": float(0.0 if return_std == 0 else returns.mean() / return_std * math.sqrt(365 * 24 * 4)),
        "exposure_pct": float((equity["active_position"].abs() > 0).mean() * 100.0),
        "turnover": float(equity["turnover"].sum()),
        "orders": int(equity["order_count"].sum()),
        "win_rate_pct": float(0.0 if active_returns.empty else (active_returns > 0).mean() * 100.0),
        "profit_factor": float("inf") if losses == 0 and gains > 0 else float(gains / abs(losses) if losses != 0 else 0.0),
    }


def _render_report(summary: dict[str, Any]) -> str:
    row = summary["row"]
    return "\n".join(
        [
            "# Strategy 1 Walk-Forward",
            "",
            f"- strategy_id: `{summary['strategy_id']}`",
            f"- strict_no_future_selection: `{summary['strict_no_future_selection']}`",
            f"- candidate_count: `{summary['candidate_count']}`",
            f"- hard_pass: `{row['hard_pass']}`",
            f"- return_2025_pct: `{row['return_2025_pct']}`",
            f"- return_2026_pct: `{row['return_2026_pct']}`",
            f"- min_monthly_return_pct: `{row['min_monthly_return_pct']}`",
            f"- min_monthly_orders: `{row['min_monthly_orders']}`",
            f"- max_drawdown_pct: `{row['max_drawdown_pct']}`",
        ]
    ) + "\n"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
