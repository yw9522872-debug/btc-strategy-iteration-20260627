from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import search_monthly_profit_lock_20260627 as lock_search
import search_online_expert_pool_20260627 as source_pool
import validate_profit_lock_overfit_20260627 as overfit


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_11_true_2024_walkforward_20260627"
TRAIN_START_MONTH = "2023-01"
EVAL_YEAR = "2024"
STRATEGY_ID = "strategy_11_true_2024_walkforward_20260627"

FEATURE_2023 = ROOT / "artifacts" / "strategy_10_pre2024_data_probe_20260627" / "btc_15m_2023_feature_probe.csv"
FEATURE_2024 = ROOT / "artifacts" / "event_entry_fullscan" / "event_entry_best_signals.csv"

FIXED_WINDOW = 64
FIXED_THRESHOLD_BPS = 100.0
SELECTOR_WINDOWS = [32, 64, 96]
SELECTOR_THRESHOLDS = [50.0, 100.0, 200.0]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    features = _load_combined_features()
    market = source_pool._market(features)
    variants = [
        _run_fixed_variant(features, market),
        _run_selector_variant(features, market),
    ]

    summary_rows = []
    for result in variants:
        prefix = result["variant_id"]
        result["selections"].to_csv(OUT_DIR / f"{prefix}_selections.csv", index=False)
        result["equity"].to_csv(OUT_DIR / f"{prefix}_equity.csv", index=False)
        result["monthly"].to_csv(OUT_DIR / f"{prefix}_monthly.csv", index=False)
        result["yearly"].to_csv(OUT_DIR / f"{prefix}_yearly.csv", index=False)
        summary_rows.append(result["summary_row"])

    comparison = pd.DataFrame(summary_rows).sort_values(
        ["hard_pass_2024", "return_2024_pct", "min_monthly_return_pct"], ascending=[False, False, False]
    )
    comparison.to_csv(OUT_DIR / "comparison.csv", index=False)

    summary = {
        "status": "strategy_11_true_2024_walkforward_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "not_live_trading": True,
        "strict_no_future_selection": True,
        "purpose": "Use 2023 public data to select before each 2024 month, then evaluate 2024 without reusing 2025+ saved controls.",
        "data": {
            "train_start_month": TRAIN_START_MONTH,
            "eval_year": EVAL_YEAR,
            "feature_2023": _rel(FEATURE_2023),
            "feature_2024": _rel(FEATURE_2024),
            "uses_strategy_10_calendar_filled_rows": True,
        },
        "cost_model": {
            "cost_per_side": lock_search.COST_PER_SIDE,
            "round_trip_open_close": lock_search.COST_PER_SIDE * 2,
        },
        "variants": lock_search._json_ready(comparison.to_dict("records")),
        "decision": _decision(comparison),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "comparison": _rel(OUT_DIR / "comparison.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _load_combined_features() -> pd.DataFrame:
    required = [
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
    ]
    f2023 = pd.read_csv(FEATURE_2023, usecols=lambda column: column in required, low_memory=False)
    f2024 = pd.read_csv(FEATURE_2024, usecols=lambda column: column in required, low_memory=False)
    out = pd.concat([f2023, f2024], ignore_index=True)
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    out = out.loc[out["timestamp"].notna()].sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    out = out.loc[(out["timestamp"] >= "2023-01-01") & (out["timestamp"] < "2025-01-01")].reset_index(drop=True)
    for column in out.columns:
        if column != "timestamp":
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return source_pool._add_features(out)


def _run_fixed_variant(features: pd.DataFrame, market: dict[str, Any]) -> dict[str, Any]:
    side = _ret_state_side(features, FIXED_WINDOW, FIXED_THRESHOLD_BPS)
    candidates = _candidate_results(side, market, _small_param_grid())
    selections = [_select_for_month(month, candidates, {"window": FIXED_WINDOW, "threshold_bps": FIXED_THRESHOLD_BPS}) for month in _eval_months(market)]
    _assert_no_future(selections)
    equity = _simulate_walkforward(side, market, {row["eval_month"]: row for row in selections})
    _assert_signal_timing(equity)
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)
    row = _result_row("fixed_ret_state_64_100", equity, monthly, yearly)
    return {"variant_id": "fixed_ret_state_64_100", "selections": pd.DataFrame(selections), "equity": equity, "monthly": monthly, "yearly": yearly, "summary_row": row}


def _run_selector_variant(features: pd.DataFrame, market: dict[str, Any]) -> dict[str, Any]:
    experts = [
        {"window": window, "threshold_bps": threshold, "side": _ret_state_side(features, window, threshold)}
        for window in SELECTOR_WINDOWS
        for threshold in SELECTOR_THRESHOLDS
    ]
    candidates = []
    for expert_index, expert in enumerate(experts):
        for candidate in _candidate_results(expert["side"], market, _small_param_grid()):
            candidates.append({**candidate, "expert_index": expert_index, "expert": expert})
    selections = [_select_selector_for_month(month, candidates) for month in _eval_months(market)]
    _assert_no_future(selections)
    equity = _simulate_selector_walkforward(experts, market, {row["eval_month"]: row for row in selections})
    _assert_signal_timing(equity)
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)
    row = _result_row("ret_state_selector", equity, monthly, yearly)
    return {"variant_id": "ret_state_selector", "selections": pd.DataFrame(selections), "equity": equity, "monthly": monthly, "yearly": yearly, "summary_row": row}


def _candidate_results(side: np.ndarray, market: dict[str, Any], params_grid: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for candidate_id, params in enumerate(params_grid):
        _, arrays = lock_search._simulate(side, params["leverage"], params["lock_log"], None, params["quota_arm_log"], params["quota_leverage"], market)
        out.append({"candidate_id": candidate_id, "params": params, "monthly": overfit._arrays_to_monthly(arrays, market)})
    return out


def _small_param_grid() -> list[dict[str, Any]]:
    return [
        {"leverage": leverage, "lock_log": lock_log, "quota_arm_log": quota_arm_log, "quota_leverage": quota_leverage}
        for leverage in [4.0, 6.0, 8.0]
        for lock_log in [0.02, 0.04]
        for quota_arm_log, quota_leverage in [(None, None), (0.04, 0.25), (0.04, 1.0), (0.08, 0.25), (0.08, 1.0)]
    ]


def _select_for_month(eval_month: str, candidates: list[dict[str, Any]], expert: dict[str, Any]) -> dict[str, Any]:
    best = _best_candidate(eval_month, candidates)
    return {"eval_month": eval_month, "train_start_month": TRAIN_START_MONTH, "window": expert["window"], "threshold_bps": expert["threshold_bps"], **best}


def _select_selector_for_month(eval_month: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    best = _best_candidate(eval_month, candidates)
    expert = best.pop("expert")
    return {"eval_month": eval_month, "train_start_month": TRAIN_START_MONTH, "expert_index": best.pop("expert_index"), "window": expert["window"], "threshold_bps": expert["threshold_bps"], **best}


def _best_candidate(eval_month: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    best_key = None
    best_row = None
    for candidate in candidates:
        score = _score_before_month(candidate["monthly"], eval_month)
        key = (
            score["return_pct"] > lock_search.REQUIRED_RETURN_PCT and score["losing_months"] == 0 and score["min_orders"] >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS,
            -score["losing_months"],
            score["min_month_return_pct"],
            score["return_pct"],
            score["min_orders"],
        )
        if best_key is None or key > best_key:
            best_key = key
            params = candidate["params"]
            best_row = {
                "train_end_month": score["last_month"],
                "candidate_id": candidate["candidate_id"],
                **params,
                **{f"train_{key}": value for key, value in score.items() if key != "last_month"},
            }
            if "expert_index" in candidate:
                best_row["expert_index"] = candidate["expert_index"]
                best_row["expert"] = candidate["expert"]
    if best_row is None:
        raise RuntimeError(f"No candidate selected for {eval_month}")
    return best_row


def _score_before_month(monthly: pd.DataFrame, eval_month: str) -> dict[str, Any]:
    train = monthly.loc[(monthly["month"] >= TRAIN_START_MONTH) & (monthly["month"] < eval_month)]
    if train.empty:
        return {"months": 0, "last_month": None, "return_pct": -999.0, "losing_months": 999, "min_month_return_pct": -999.0, "min_orders": 0}
    log_return = float(train["log_return"].sum())
    return {
        "months": int(len(train)),
        "last_month": str(train["month"].iloc[-1]),
        "return_pct": float((np.exp(log_return) - 1.0) * 100.0),
        "losing_months": int((train["return_pct"] <= 0).sum()),
        "min_month_return_pct": float(train["return_pct"].min()),
        "min_orders": int(train["orders"].min()),
    }


def _simulate_walkforward(side: np.ndarray, market: dict[str, Any], selections: dict[str, dict[str, Any]]) -> pd.DataFrame:
    return _simulate_by_month(lambda params: side, market, selections)


def _simulate_selector_walkforward(experts: list[dict[str, Any]], market: dict[str, Any], selections: dict[str, dict[str, Any]]) -> pd.DataFrame:
    return _simulate_by_month(lambda params: experts[int(params["expert_index"])]["side"], market, selections)


def _simulate_by_month(side_for_params, market: dict[str, Any], selections: dict[str, dict[str, Any]]) -> pd.DataFrame:
    records = []
    previous_position = 0.0
    previous_side = 0
    timestamp = market["timestamp"].reset_index(drop=True)
    for start, end in zip(market["month_starts"], np.r_[market["month_starts"][1:], len(market["close"])]):
        month = str(market["month"][start])
        params = selections.get(month)
        if params is None:
            continue
        side = side_for_params(params)
        month_log = 0.0
        month_orders = 0
        halted = False
        quota_mode = False
        for index in range(start, end):
            current_side = 0 if halted else int(side[index])
            effective_leverage = (
                float(params["quota_leverage"])
                if quota_mode and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS and params["quota_leverage"] is not None
                else float(params["leverage"])
            )
            current_position = current_side * effective_leverage
            turnover = abs(current_position - previous_position)
            orders = abs(current_side - previous_side)
            lr = previous_position * market["raw_return"][index] - turnover * lock_search.COST_PER_SIDE
            records.append(
                {
                    "timestamp": timestamp.iloc[index],
                    "close": market["close"][index],
                    "position": current_position,
                    "active_position": previous_position,
                    "turnover": turnover,
                    "order_count": orders,
                    "strategy_log_return": lr,
                    "window": params["window"],
                    "threshold_bps": params["threshold_bps"],
                }
            )
            month_log += lr
            month_orders += orders
            previous_position = current_position
            previous_side = current_side
            if params["quota_arm_log"] is not None and params["quota_leverage"] is not None and not quota_mode and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS and month_log >= float(params["quota_arm_log"]):
                quota_mode = True
            if not halted and month_orders >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS and month_log >= float(params["lock_log"]):
                halted = True
    equity = pd.DataFrame(records)
    equity["equity"] = np.exp(equity["strategy_log_return"].cumsum())
    equity["drawdown"] = equity["equity"] / equity["equity"].cummax() - 1.0
    return equity


def _result_row(variant_id: str, equity: pd.DataFrame, monthly: pd.DataFrame, yearly: pd.DataFrame) -> dict[str, Any]:
    year_map = dict(zip(yearly["year"], yearly["compounded_return_pct"]))
    y2024 = float(year_map.get(EVAL_YEAR, -999.0))
    eval_monthly = monthly.loc[monthly["month"].str[:4] == EVAL_YEAR]
    returns = equity["strategy_log_return"]
    active_returns = returns[equity["active_position"].abs() > 0]
    losses = float(active_returns[active_returns < 0].sum())
    gains = float(active_returns[active_returns > 0].sum())
    std = float(returns.std())
    min_orders = int(eval_monthly["orders"].min()) if not eval_monthly.empty else 0
    min_month = float(eval_monthly["return_pct"].min()) if not eval_monthly.empty else -999.0
    losing = int((eval_monthly["return_pct"] <= 0).sum())
    return {
        "variant_id": variant_id,
        "hard_pass_2024": bool(y2024 > lock_search.REQUIRED_RETURN_PCT and min_month > 0 and min_orders >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS),
        "return_2024_pct": y2024,
        "min_monthly_return_pct": min_month,
        "losing_months": losing,
        "min_monthly_orders": min_orders,
        "max_drawdown_pct": float(equity["drawdown"].min() * 100.0),
        "orders": int(equity["order_count"].sum()),
        "turnover": float(equity["turnover"].sum()),
        "exposure_pct": float((equity["active_position"].abs() > 0).mean() * 100.0),
        "annualized_sharpe": float(0.0 if std == 0 else returns.mean() / std * math.sqrt(365 * 24 * 4)),
        "win_rate_pct": float(0.0 if active_returns.empty else (active_returns > 0).mean() * 100.0),
        "profit_factor": float("inf") if losses == 0 and gains > 0 else float(gains / abs(losses) if losses != 0 else 0.0),
    }


def _ret_state_side(features: pd.DataFrame, window: int, threshold_bps: float) -> np.ndarray:
    ret = features[f"ret_{window}_bps"]
    return source_pool._state_from(ret.ge(threshold_bps), ret.le(-threshold_bps)).astype(np.int8)


def _eval_months(market: dict[str, Any]) -> list[str]:
    return [str(month) for month in market["month_labels"] if str(month).startswith(EVAL_YEAR)]


def _assert_no_future(selections: list[dict[str, Any]]) -> None:
    for row in selections:
        assert row["train_end_month"] < row["eval_month"], row


def _assert_signal_timing(equity: pd.DataFrame) -> None:
    active = equity["active_position"].to_numpy(float)
    position = equity["position"].to_numpy(float)
    assert active[0] == 0.0
    assert np.allclose(active[1:], position[:-1])


def _decision(comparison: pd.DataFrame) -> dict[str, Any]:
    best = comparison.iloc[0].to_dict()
    return {
        "best_variant": str(best["variant_id"]),
        "promote_strategy": False,
        "reason": "11号只是2024样本外审计。通过也只能说明多一个历史检验，失败则说明过拟合风险更大。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# 11号真正 2024 Walk-Forward 审计",
        "",
        "这不是新策略，只检查：只用 2023 和当月以前的数据选参数，拿 2024 做样本外测试。",
        "",
        "## 结果",
        "",
        "| 版本 | 2024收益 | 最差月 | 亏损月 | 最少月交易 | 通过 |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary["variants"]:
        lines.append(
            f"| {row['variant_id']} | {row['return_2024_pct']:.2f}% | {row['min_monthly_return_pct']:.2f}% | "
            f"{row['losing_months']} | {row['min_monthly_orders']} | {row['hard_pass_2024']} |"
        )
    lines.extend(
        [
            "",
            "## 判断",
            "",
            f"- 暂不升级策略：`{summary['decision']['promote_strategy']}`。",
            f"- 原因：{summary['decision']['reason']}",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
