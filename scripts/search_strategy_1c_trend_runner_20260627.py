from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import search_monthly_profit_lock_20260627 as lock_search
import search_online_expert_pool_20260627 as source_pool
import search_strategy_1_candidate_20260627 as strategy_1a
import validate_profit_lock_overfit_20260627 as overfit


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_1c_trend_runner_20260627"
STRATEGY_ID = "strategy_1c_trend_runner_20260627"

TREND_GAP_BPS = 350.0
TREND_ADX_MIN = 30.0
RUNNER_LEVERAGE = 0.25


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = source_pool._load_features(source_pool.FEATURE_FRAME)
    features = source_pool._add_features(source)
    market = source_pool._market(features)
    experts = source_pool._expert_pool(features)
    expert_index = overfit._find_fixed_expert(experts)
    side = experts[expert_index].target
    selections = pd.read_csv(ROOT / "artifacts" / "strategy_1b_expanded_controls_20260627" / "strategy_1b_selections.csv")
    trend_side = _trend_side(features)

    equity = _simulate(side, trend_side, market, selections, cost_per_side=lock_search.COST_PER_SIDE)
    strategy_1a._assert_signal_timing(equity)
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)
    row = _result_row(equity, monthly, yearly)
    signals = strategy_1a._signals(equity)
    signals["candidate_version"] = STRATEGY_ID

    stress = pd.DataFrame(
        [
            _stress_row(side, trend_side, market, selections, cost_per_side=0.001, extra_delay_bars=0),
            _stress_row(side, trend_side, market, selections, cost_per_side=0.0015, extra_delay_bars=0),
            _stress_row(side, trend_side, market, selections, cost_per_side=0.002, extra_delay_bars=0),
            _stress_row(side, trend_side, market, selections, cost_per_side=0.001, extra_delay_bars=1),
            _stress_row(side, trend_side, market, selections, cost_per_side=0.0015, extra_delay_bars=1),
        ]
    )

    selections.to_csv(OUT_DIR / "strategy_1c_selections.csv", index=False)
    signals.to_csv(OUT_DIR / "strategy_1c_signals.csv", index=False)
    equity.to_csv(OUT_DIR / "strategy_1c_equity.csv", index=False)
    monthly.to_csv(OUT_DIR / "strategy_1c_monthly.csv", index=False)
    yearly.to_csv(OUT_DIR / "strategy_1c_yearly.csv", index=False)
    stress.to_csv(OUT_DIR / "strategy_1c_stress.csv", index=False)

    summary = {
        "status": "strategy_1c_trend_runner_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "strict_no_future_function": True,
        "base": "strategy_1b_expanded_controls_20260627",
        "change": (
            "After the monthly lock is reached, do not always stay flat. If a strong trend is visible "
            "using closed-bar trend_gap/adx data, keep a small 0.25x trend-runner position."
        ),
        "trend_runner": {
            "trend_gap_bps": TREND_GAP_BPS,
            "trend_adx_min": TREND_ADX_MIN,
            "runner_leverage": RUNNER_LEVERAGE,
            "timing": "trend side is computed from closed bar t data and participates from bar t+1 via active_position",
        },
        "expert": experts[expert_index].params,
        "cost_model": {
            "cost_per_side": lock_search.COST_PER_SIDE,
            "round_trip_open_close": lock_search.COST_PER_SIDE * 2,
        },
        "row": lock_search._json_ready(row),
        "yearly": lock_search._json_ready(yearly.to_dict("records")),
        "monthly": lock_search._json_ready(
            monthly[["month", "return_pct", "orders", "drawdown_pct"]].to_dict("records")
        ),
        "stress": lock_search._json_ready(stress.to_dict("records")),
        "risk_flags": {
            "fixed_signal_still_from_prior_research": True,
            "uses_strategy_1b_selected_controls": True,
            "posthoc_runner_choice": True,
            "not_a_live_guarantee": True,
        },
        "hashes": {
            "script_sha256": lock_search._sha256(Path(__file__)),
            "feature_frame_sha256": lock_search._sha256(source_pool.FEATURE_FRAME),
            "signals_sha256": lock_search._sha256(OUT_DIR / "strategy_1c_signals.csv"),
        },
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "selections": _relpath(OUT_DIR / "strategy_1c_selections.csv"),
            "signals": _relpath(OUT_DIR / "strategy_1c_signals.csv"),
            "equity": _relpath(OUT_DIR / "strategy_1c_equity.csv"),
            "monthly": _relpath(OUT_DIR / "strategy_1c_monthly.csv"),
            "yearly": _relpath(OUT_DIR / "strategy_1c_yearly.csv"),
            "stress": _relpath(OUT_DIR / "strategy_1c_stress.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _trend_side(features: pd.DataFrame) -> np.ndarray:
    trend_gap = features["trend_close_ema_gap_bps_60"].to_numpy(float)
    adx = features["trend_adx_30"].to_numpy(float)
    side = np.zeros(len(features), dtype=np.int8)
    side[(trend_gap >= TREND_GAP_BPS) & (adx >= TREND_ADX_MIN)] = 1
    side[(trend_gap <= -TREND_GAP_BPS) & (adx >= TREND_ADX_MIN)] = -1
    return side


def _simulate(
    side: np.ndarray,
    trend_side: np.ndarray,
    market: dict[str, Any],
    selections: pd.DataFrame,
    cost_per_side: float,
    extra_delay_bars: int = 0,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    previous_position = 0.0
    previous_side = 0
    timestamp = market["timestamp"].reset_index(drop=True)
    selection_map = {row["eval_month"]: row for _, row in selections.iterrows()}
    for start, end in zip(market["month_starts"], np.r_[market["month_starts"][1:], len(side)]):
        month = str(market["month"][start])
        if month not in selection_map:
            continue
        params = selection_map[month]
        month_log = 0.0
        month_orders = 0
        halted = False
        quota_mode = False
        for index in range(start, end):
            signal_index = index - extra_delay_bars
            if halted:
                current_side = int(trend_side[signal_index]) if signal_index >= 0 else 0
                current_leverage = RUNNER_LEVERAGE if current_side else 0.0
            else:
                current_side = int(side[signal_index]) if signal_index >= 0 else 0
                quota_leverage = _none_if_nan(params["quota_leverage"])
                current_leverage = (
                    float(quota_leverage)
                    if quota_mode and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS and quota_leverage is not None
                    else float(params["leverage"])
                )
            current_position = current_side * current_leverage
            current_turnover = abs(current_position - previous_position)
            current_orders = abs(current_side - previous_side)
            current_lr = previous_position * market["raw_return"][index] - current_turnover * cost_per_side
            records.append(
                {
                    "timestamp": timestamp.iloc[index],
                    "close": market["close"][index],
                    "position": current_position,
                    "active_position": previous_position,
                    "turnover": current_turnover,
                    "order_count": current_orders,
                    "strategy_log_return": current_lr,
                }
            )

            month_log += current_lr
            month_orders += current_orders
            previous_position = current_position
            previous_side = current_side

            if not halted:
                quota_arm = _none_if_nan(params["quota_arm_log"])
                quota_leverage = _none_if_nan(params["quota_leverage"])
                if (
                    quota_arm is not None
                    and quota_leverage is not None
                    and not quota_mode
                    and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS
                    and month_log >= float(quota_arm)
                ):
                    quota_mode = True
                if month_orders >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS and month_log >= float(params["lock_log"]):
                    halted = True

    equity = pd.DataFrame(records)
    equity["equity"] = np.exp(equity["strategy_log_return"].cumsum())
    equity["drawdown"] = equity["equity"] / equity["equity"].cummax() - 1.0
    return equity


def _stress_row(
    side: np.ndarray,
    trend_side: np.ndarray,
    market: dict[str, Any],
    selections: pd.DataFrame,
    cost_per_side: float,
    extra_delay_bars: int,
) -> dict[str, Any]:
    equity = _simulate(side, trend_side, market, selections, cost_per_side, extra_delay_bars)
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)
    row = _result_row(equity, monthly, yearly)
    return {
        "cost_per_side": cost_per_side,
        "round_trip_cost": cost_per_side * 2,
        "extra_delay_bars": extra_delay_bars,
        **row,
    }


def _result_row(equity: pd.DataFrame, monthly: pd.DataFrame, yearly: pd.DataFrame) -> dict[str, Any]:
    year_map = dict(zip(yearly["year"].astype(str), yearly["compounded_return_pct"]))
    y2025 = float(year_map.get("2025", -999.0))
    y2026 = float(year_map.get("2026", -999.0))
    eval_monthly = monthly.loc[monthly["month"].str[:4].isin(lock_search.EVAL_YEARS)]
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
        "exposure_pct": float((equity["active_position"].abs() > 0).mean() * 100.0),
        "turnover": float(equity["turnover"].sum()),
        "orders": int(equity["order_count"].sum()),
    }


def _none_if_nan(value: Any) -> Any:
    return None if pd.isna(value) else value


def _render_report(summary: dict[str, Any]) -> str:
    row = summary["row"]
    return "\n".join(
        [
            "# Strategy 1C Trend Runner",
            "",
            f"- strategy_id: `{summary['strategy_id']}`",
            f"- strict_no_future_function: `{summary['strict_no_future_function']}`",
            f"- hard_pass: `{row['hard_pass']}`",
            f"- return_2025_pct: `{row['return_2025_pct']}`",
            f"- return_2026_pct: `{row['return_2026_pct']}`",
            f"- min_monthly_return_pct: `{row['min_monthly_return_pct']}`",
            f"- min_monthly_orders: `{row['min_monthly_orders']}`",
            f"- max_drawdown_pct: `{row['max_drawdown_pct']}`",
            "",
            "## Change",
            "",
            "After monthly lock, keep a small 0.25x position only when trend_gap >= 350 bps and ADX >= 30.",
        ]
    ) + "\n"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
