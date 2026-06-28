from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import audit_strategy_14_pre2023_expanding_crowding_stress_20260627 as s14
import search_monthly_profit_lock_20260627 as lock_search


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ID = "strategy_28_relaxed_no_monthly_profit_audit_20260628"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
SOURCE_OHLC = s14.OUT_DIR / "btc_15m_2020_2026_05_combined_ohlc.csv"
CANDIDATE_MONTHLY = OUT_DIR / "candidate_monthly_base.csv"
CANDIDATE_META = OUT_DIR / "candidate_meta.csv"

TRAIN_START_MONTH = s14.TRAIN_START_MONTH
EVAL_START_MONTH = s14.EVAL_START_MONTH
EVAL_END_MONTH = s14.EVAL_END_EXCLUSIVE.strftime("%Y-%m")
ORDER_FLOOR = lock_search.REQUIRED_MIN_MONTHLY_ORDERS

SELECTORS = {
    "loss_control_no_positive_gate": "Fewest past losing months first, with no monthly-profit pass/fail gate.",
    "return_first": "Highest past total return first; losing months are allowed.",
    "return_first_min10_orders": "Highest past total return first, preferring candidates with at least 10 past monthly orders.",
    "worst_year_balance": "Best past worst full-year return first, then total return.",
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    combined_ohlc = _load_source_ohlc()
    features = s14._add_features(combined_ohlc)
    market = s14._market(features)
    candidate_monthly, candidate_meta, cache_status = _load_or_build_candidate_cache(features, market)

    strict_rows: list[dict[str, Any]] = []
    strict_selections: dict[str, list[dict[str, Any]]] = {}
    strict_paths: dict[str, dict[str, str]] = {}
    for selector_id in SELECTORS:
        selections = _select_months_fast(candidate_monthly, candidate_meta, selector_id)
        monthly = _monthly_from_selections_fast(candidate_monthly, selections)
        yearly = lock_search._yearly_breakdown(monthly)
        row = _monthly_summary(selector_id, "strict_expanding_selector_fast_monthly_proxy", monthly, yearly)
        strict_rows.append(row)
        strict_selections[selector_id] = selections
        strict_paths[selector_id] = _write_monthly_result_files(f"{selector_id}_fast", selections, monthly, yearly)

    strict_frame = pd.DataFrame(strict_rows).sort_values(
        ["annual_2025_2026_gt_100", "min_2025_2026_return_pct", "total_eval_return_pct"],
        ascending=[False, False, False],
    )
    best_selector_id = str(strict_frame.iloc[0]["selector_id"])
    exact_selection = strict_selections[best_selector_id]
    exact_equity = s14._simulate_walkforward(features, market, exact_selection, cost_per_side=lock_search.COST_PER_SIDE)
    s14._assert_signal_timing(exact_equity)
    exact_monthly = lock_search._monthly_breakdown(exact_equity)
    exact_yearly = lock_search._yearly_breakdown(exact_monthly)
    exact_summary = _exact_summary(best_selector_id, exact_equity, exact_monthly, exact_yearly)
    exact_paths = _write_exact_result_files(f"{best_selector_id}_exact", exact_selection, exact_equity, exact_monthly, exact_yearly)

    oracle_rows: list[dict[str, Any]] = []
    oracle_paths: dict[str, dict[str, str]] = {}
    for oracle_id, selections in [
        ("static_oracle_best_min_2025_2026", _select_static_oracle_fast(candidate_monthly, candidate_meta)),
        ("monthly_oracle_best_return_min10", _select_monthly_oracle_fast(candidate_monthly, candidate_meta, ORDER_FLOOR)),
    ]:
        monthly = _monthly_from_selections_fast(candidate_monthly, selections)
        yearly = lock_search._yearly_breakdown(monthly)
        oracle_rows.append(_monthly_summary(oracle_id, "leaky_oracle_fast_monthly_proxy", monthly, yearly))
        oracle_paths[oracle_id] = _write_monthly_result_files(oracle_id, selections, monthly, yearly)

    strict_summary_path = OUT_DIR / "strict_selector_summary.csv"
    oracle_summary_path = OUT_DIR / "oracle_diagnostic_summary.csv"
    strict_frame.to_csv(strict_summary_path, index=False)
    pd.DataFrame(oracle_rows).to_csv(oracle_summary_path, index=False)

    summary = {
        "status": "strategy_28_relaxed_no_monthly_profit_audit_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_live_trading": True,
        "not_a_freeze": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": (
            "Remove the monthly-profitable-month requirement and retest whether the "
            "strategy_14 ret_state family can produce a useful non-leaky yearly result."
        ),
        "source": {
            "source_ohlc": _rel(SOURCE_OHLC),
            "source_family": "strategy_14 ret_state 64/100 family",
            "new_market_data_added": False,
            "new_trade_rules_added": False,
            "cache_status": cache_status,
        },
        "relaxed_target": {
            "monthly_profit_required": False,
            "cost_per_side": lock_search.COST_PER_SIDE,
            "round_trip_open_close": lock_search.COST_PER_SIDE * 2,
            "main_gate_checked": "2025 and 2026 YTD both above +100%; monthly losses allowed",
        },
        "candidate_grid": {
            "total_candidates": int(candidate_meta["candidate_id"].nunique()),
            "candidate_monthly_rows": int(len(candidate_monthly)),
            "confirm_bars": s14.CONFIRM_BARS,
            "selectors": SELECTORS,
        },
        "strict_selector_fast_proxy_results": lock_search._json_ready(strict_rows),
        "best_strict_exact_result": lock_search._json_ready(exact_summary),
        "oracle_diagnostics_fast_proxy": lock_search._json_ready(oracle_rows),
        "decision": _decision(exact_summary, oracle_rows),
        "hashes": {
            "script_sha256": s14._sha256(Path(__file__)),
            "source_ohlc_sha256": s14._sha256(SOURCE_OHLC),
            "candidate_monthly_sha256": s14._sha256(CANDIDATE_MONTHLY),
            "candidate_meta_sha256": s14._sha256(CANDIDATE_META),
            "strict_selector_summary_sha256": s14._sha256(strict_summary_path),
            "oracle_diagnostic_summary_sha256": s14._sha256(oracle_summary_path),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "candidate_monthly_base": _rel(CANDIDATE_MONTHLY),
            "candidate_meta": _rel(CANDIDATE_META),
            "strict_selector_summary": _rel(strict_summary_path),
            "oracle_diagnostic_summary": _rel(oracle_summary_path),
            "strict_fast_outputs": strict_paths,
            "best_strict_exact_outputs": exact_paths,
            "oracle_outputs": oracle_paths,
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _load_source_ohlc() -> pd.DataFrame:
    frame = pd.read_csv(SOURCE_OHLC)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["timestamp", "open", "high", "low", "close"])
    return frame.sort_values("timestamp").reset_index(drop=True)


def _load_or_build_candidate_cache(
    features: pd.DataFrame,
    market: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    if CANDIDATE_MONTHLY.exists() and CANDIDATE_META.exists():
        monthly = pd.read_csv(CANDIDATE_MONTHLY)
        meta = pd.read_csv(CANDIDATE_META)
        monthly["month"] = monthly["month"].astype(str)
        return monthly, meta, "reused_existing_cache"

    candidates = s14._candidate_library(features, market)
    monthly_rows = []
    meta_rows = []
    for candidate in candidates:
        candidate_id = int(candidate["candidate_id"])
        monthly = candidate["monthly"].copy()
        monthly.insert(0, "candidate_id", candidate_id)
        monthly_rows.append(monthly)
        params = candidate["params"]
        meta_rows.append(
            {
                "candidate_id": candidate_id,
                "confirm_bars": int(candidate["confirm_bars"]),
                "leverage": float(params["leverage"]),
                "lock_log": float(params["lock_log"]),
                "quota_arm_log": params["quota_arm_log"],
                "quota_leverage": params["quota_leverage"],
            }
        )
    candidate_monthly = pd.concat(monthly_rows, ignore_index=True)
    candidate_meta = pd.DataFrame(meta_rows)
    candidate_monthly.to_csv(CANDIDATE_MONTHLY, index=False)
    candidate_meta.to_csv(CANDIDATE_META, index=False)
    return candidate_monthly, candidate_meta, "built_new_cache"


def _select_months_fast(
    candidate_monthly: pd.DataFrame,
    candidate_meta: pd.DataFrame,
    selector_id: str,
) -> list[dict[str, Any]]:
    groups = {int(candidate_id): group.copy() for candidate_id, group in candidate_monthly.groupby("candidate_id")}
    meta_map = _meta_map(candidate_meta)
    selections = []
    for eval_month in _eval_months(candidate_monthly):
        best_key = None
        best_row = None
        for candidate_id, monthly in groups.items():
            score = _score_before_month(monthly, eval_month)
            if score["months"] < 12:
                continue
            meta = meta_map[candidate_id]
            key = _selector_key(selector_id, score, meta)
            if best_key is None or key > best_key:
                best_key = key
                best_row = {
                    "selector_id": selector_id,
                    "eval_month": eval_month,
                    "train_start_month": TRAIN_START_MONTH,
                    "train_end_month": score["last_month"],
                    **_selection_params(meta),
                    **{f"train_{name}": value for name, value in score.items() if name != "last_month"},
                }
        if best_row is None:
            raise RuntimeError(f"No candidate selected for {eval_month}")
        if not (best_row["train_end_month"] < best_row["eval_month"]):
            raise AssertionError(best_row)
        selections.append(best_row)
    return selections


def _selector_key(selector_id: str, score: dict[str, Any], meta: dict[str, Any]) -> tuple[Any, ...]:
    common_tail = (
        score["min_orders"],
        -score["turnover"],
        -float(meta["leverage"]),
        -int(meta["confirm_bars"]),
    )
    if selector_id == "loss_control_no_positive_gate":
        return (-score["losing_months"], score["min_month_return_pct"], score["return_pct"], *common_tail)
    if selector_id == "return_first":
        return (score["return_pct"], -score["losing_months"], score["min_month_return_pct"], *common_tail)
    if selector_id == "return_first_min10_orders":
        return (
            score["min_orders"] >= ORDER_FLOOR,
            score["return_pct"],
            -score["losing_months"],
            score["min_month_return_pct"],
            *common_tail,
        )
    if selector_id == "worst_year_balance":
        return (
            score["full_years"],
            score["worst_full_year_return_pct"],
            score["return_pct"],
            -score["losing_months"],
            *common_tail,
        )
    raise KeyError(selector_id)


def _score_before_month(monthly: pd.DataFrame, eval_month: str) -> dict[str, Any]:
    train = monthly.loc[(monthly["month"] >= TRAIN_START_MONTH) & (monthly["month"] < eval_month)].copy()
    if train.empty:
        return {
            "months": 0,
            "last_month": None,
            "log_return": -999.0,
            "return_pct": -999.0,
            "losing_months": 999,
            "min_month_return_pct": -999.0,
            "min_orders": 0,
            "turnover": 999999.0,
            "full_years": 0,
            "worst_full_year_return_pct": -999.0,
        }
    log_return = float(train["log_return"].sum())
    yearly = lock_search._yearly_breakdown(train)
    full_years = yearly.loc[yearly["months"] >= 12].copy()
    return {
        "months": int(len(train)),
        "last_month": str(train["month"].iloc[-1]),
        "log_return": log_return,
        "return_pct": float((np.exp(log_return) - 1.0) * 100.0),
        "losing_months": int((train["return_pct"] <= 0.0).sum()),
        "min_month_return_pct": float(train["return_pct"].min()),
        "min_orders": int(train["orders"].min()),
        "turnover": float(train["turnover"].sum()),
        "full_years": int(len(full_years)),
        "worst_full_year_return_pct": (
            float(full_years["compounded_return_pct"].min()) if not full_years.empty else -999.0
        ),
    }


def _select_static_oracle_fast(candidate_monthly: pd.DataFrame, candidate_meta: pd.DataFrame) -> list[dict[str, Any]]:
    meta_map = _meta_map(candidate_meta)
    best_key = None
    best_candidate_id = None
    for candidate_id, monthly in candidate_monthly.groupby("candidate_id"):
        selected = monthly.loc[(monthly["month"] >= EVAL_START_MONTH) & (monthly["month"] < EVAL_END_MONTH)].copy()
        yearly = lock_search._yearly_breakdown(selected)
        summary = _monthly_summary("static_probe", "leaky_static_probe", selected, yearly)
        key = (
            summary["min_2025_2026_return_pct"],
            summary["total_eval_return_pct"],
            -summary["losing_eval_months"],
            summary["min_monthly_orders"],
        )
        if best_key is None or key > best_key:
            best_key = key
            best_candidate_id = int(candidate_id)
    if best_candidate_id is None:
        raise RuntimeError("No static oracle candidate selected.")
    meta = meta_map[best_candidate_id]
    return [
        {
            "selector_id": "static_oracle_best_min_2025_2026",
            "eval_month": month,
            "train_start_month": "LEAKY_FULL_EVAL",
            "train_end_month": "LEAKY_FULL_EVAL",
            **_selection_params(meta),
        }
        for month in _eval_months(candidate_monthly)
    ]


def _select_monthly_oracle_fast(
    candidate_monthly: pd.DataFrame,
    candidate_meta: pd.DataFrame,
    min_orders: int,
) -> list[dict[str, Any]]:
    meta_map = _meta_map(candidate_meta)
    selections = []
    for month in _eval_months(candidate_monthly):
        pool = candidate_monthly.loc[candidate_monthly["month"] == month].copy()
        eligible = pool.loc[pool["orders"] >= min_orders].copy()
        if eligible.empty:
            eligible = pool
        best = eligible.sort_values(["return_pct", "orders", "turnover"], ascending=[False, False, True]).iloc[0]
        meta = meta_map[int(best["candidate_id"])]
        selections.append(
            {
                "selector_id": "monthly_oracle_best_return_min10",
                "eval_month": month,
                "train_start_month": "LEAKY_MONTH",
                "train_end_month": "LEAKY_MONTH",
                "actual_month_return_pct": float(best["return_pct"]),
                "actual_month_orders": int(best["orders"]),
                **_selection_params(meta),
            }
        )
    return selections


def _monthly_from_selections_fast(candidate_monthly: pd.DataFrame, selections: list[dict[str, Any]]) -> pd.DataFrame:
    indexed = candidate_monthly.set_index(["candidate_id", "month"])
    rows = []
    for selection in selections:
        candidate_id = int(selection["candidate_id"])
        month = str(selection["eval_month"])
        base = indexed.loc[(candidate_id, month)]
        rows.append(
            {
                "month": month,
                "candidate_id": candidate_id,
                "log_return": float(base["log_return"]),
                "turnover": float(base["turnover"]),
                "orders": int(base["orders"]),
                "return_pct": float((np.exp(float(base["log_return"])) - 1.0) * 100.0),
            }
        )
    out = pd.DataFrame(rows).sort_values("month").reset_index(drop=True)
    cumulative_before = out["log_return"].cumsum().shift(fill_value=0.0)
    out["first_equity"] = np.exp(cumulative_before)
    out["last_equity"] = np.exp(cumulative_before + out["log_return"])
    out["drawdown_pct"] = (out["last_equity"] / out["last_equity"].cummax() - 1.0) * 100.0
    out["min_drawdown"] = out["drawdown_pct"] / 100.0
    return out[
        [
            "month",
            "log_return",
            "first_equity",
            "last_equity",
            "min_drawdown",
            "turnover",
            "orders",
            "return_pct",
            "drawdown_pct",
            "candidate_id",
        ]
    ]


def _monthly_summary(selector_id: str, method: str, monthly: pd.DataFrame, yearly: pd.DataFrame) -> dict[str, Any]:
    eval_monthly = monthly.loc[(monthly["month"] >= EVAL_START_MONTH) & (monthly["month"] < EVAL_END_MONTH)].copy()
    year_map = dict(zip(yearly["year"].astype(str), yearly["compounded_return_pct"]))
    total_log = float(eval_monthly["log_return"].sum()) if not eval_monthly.empty else 0.0
    return_2025 = float(year_map.get("2025", -999.0))
    return_2026 = float(year_map.get("2026", -999.0))
    return {
        "selector_id": selector_id,
        "method": method,
        "exact_backtest": False,
        "total_eval_return_pct": float((math.exp(total_log) - 1.0) * 100.0),
        "return_2023_pct": float(year_map.get("2023", -999.0)),
        "return_2024_pct": float(year_map.get("2024", -999.0)),
        "return_2025_pct": return_2025,
        "return_2026_ytd_pct": return_2026,
        "min_2025_2026_return_pct": float(min(return_2025, return_2026)),
        "annual_2025_2026_gt_100": bool(return_2025 > 100.0 and return_2026 > 100.0),
        "annual_2025_2026_gt_50": bool(return_2025 > 50.0 and return_2026 > 50.0),
        "annual_2025_2026_gt_30": bool(return_2025 > 30.0 and return_2026 > 30.0),
        "losing_eval_months": int((eval_monthly["return_pct"] <= 0.0).sum()) if not eval_monthly.empty else 999,
        "min_monthly_return_pct": float(eval_monthly["return_pct"].min()) if not eval_monthly.empty else -999.0,
        "min_monthly_orders": int(eval_monthly["orders"].min()) if not eval_monthly.empty else 0,
        "orders": int(eval_monthly["orders"].sum()) if not eval_monthly.empty else 0,
        "turnover": float(eval_monthly["turnover"].sum()) if not eval_monthly.empty else 0.0,
        "cost_log": float(eval_monthly["turnover"].sum() * lock_search.COST_PER_SIDE) if not eval_monthly.empty else 0.0,
        "max_drawdown_pct_proxy": float(eval_monthly["drawdown_pct"].min()) if not eval_monthly.empty else 0.0,
    }


def _exact_summary(
    selector_id: str,
    equity: pd.DataFrame,
    monthly: pd.DataFrame,
    yearly: pd.DataFrame,
) -> dict[str, Any]:
    row = _monthly_summary(selector_id, "strict_expanding_selector_exact_best", monthly, yearly)
    returns = equity["strategy_log_return"]
    active_returns = equity.loc[equity["active_position"].abs() > 0, "strategy_log_return"]
    losses = float(active_returns[active_returns < 0].sum()) if not active_returns.empty else 0.0
    gains = float(active_returns[active_returns > 0].sum()) if not active_returns.empty else 0.0
    std = float(returns.std())
    row.update(
        {
            "exact_backtest": True,
            "max_drawdown_pct": float(equity["drawdown"].min() * 100.0),
            "exposure_pct": float((equity["active_position"].abs() > 0).mean() * 100.0),
            "annualized_sharpe": float(0.0 if std == 0.0 else returns.mean() / std * math.sqrt(365 * 24 * 4)),
            "win_rate_pct": float(0.0 if active_returns.empty else (active_returns > 0).mean() * 100.0),
            "profit_factor": float("inf") if losses == 0.0 and gains > 0.0 else float(gains / abs(losses) if losses else 0.0),
        }
    )
    return row


def _decision(best_exact: dict[str, Any], oracle_rows: list[dict[str, Any]]) -> dict[str, Any]:
    oracle_best = max(oracle_rows, key=lambda row: row["min_2025_2026_return_pct"]) if oracle_rows else {}
    if best_exact["annual_2025_2026_gt_100"]:
        verdict = "RELAXED_STRICT_SELECTOR_FOUND"
        reason = "不要求每月盈利后，严格不看未来的选择器达到了2025和2026 YTD都超过100%。仍需继续压力测试。"
        next_step = "下一步做成本、延迟、资金费率和更长样本压力测试，不能直接升级。"
    elif best_exact["annual_2025_2026_gt_50"]:
        verdict = "RELAXED_LOW_BAR_CANDIDATE_ONLY"
        reason = "不要求每月盈利后，只出现较低门槛的研究候选，还没有达到原来的高年化目标。"
        next_step = "下一步只适合影子跟踪或低目标复核，不适合说成强策略。"
    else:
        verdict = "NO_STRICT_RELAXED_UPGRADE"
        reason = "去掉每月盈利要求后，严格不看未来的选择器仍没有做出2025和2026 YTD同时够强的结果。"
        next_step = "不要继续在这批免费K线规则里硬挤；若继续研究，应降低目标或等新数据源。"
    return {
        "verdict": verdict,
        "promote_strategy": False,
        "reason": reason,
        "next_step": next_step,
        "best_exact_selector_id": best_exact["selector_id"],
        "best_exact_2025_pct": best_exact["return_2025_pct"],
        "best_exact_2026_ytd_pct": best_exact["return_2026_ytd_pct"],
        "best_exact_losing_months": best_exact["losing_eval_months"],
        "best_exact_max_drawdown_pct": best_exact.get("max_drawdown_pct"),
        "best_oracle_min_2025_2026_pct": oracle_best.get("min_2025_2026_return_pct"),
        "oracle_note": "Oracle rows are leaky diagnostics only and cannot be traded.",
    }


def _write_monthly_result_files(
    result_id: str,
    selections: list[dict[str, Any]],
    monthly: pd.DataFrame,
    yearly: pd.DataFrame,
) -> dict[str, str]:
    selected_path = OUT_DIR / f"{result_id}_selected_params.csv"
    monthly_path = OUT_DIR / f"{result_id}_monthly.csv"
    yearly_path = OUT_DIR / f"{result_id}_yearly.csv"
    pd.DataFrame(selections).to_csv(selected_path, index=False)
    monthly.to_csv(monthly_path, index=False)
    yearly.to_csv(yearly_path, index=False)
    return {"selected_params": _rel(selected_path), "monthly": _rel(monthly_path), "yearly": _rel(yearly_path)}


def _write_exact_result_files(
    result_id: str,
    selections: list[dict[str, Any]],
    equity: pd.DataFrame,
    monthly: pd.DataFrame,
    yearly: pd.DataFrame,
) -> dict[str, str]:
    paths = _write_monthly_result_files(result_id, selections, monthly, yearly)
    equity_path = OUT_DIR / f"{result_id}_equity.csv"
    equity.to_csv(equity_path, index=False)
    paths["equity"] = _rel(equity_path)
    return paths


def _eval_months(candidate_monthly: pd.DataFrame) -> list[str]:
    months = candidate_monthly["month"].astype(str)
    return sorted(month for month in months.unique().tolist() if EVAL_START_MONTH <= month < EVAL_END_MONTH)


def _meta_map(candidate_meta: pd.DataFrame) -> dict[int, dict[str, Any]]:
    return {int(row["candidate_id"]): row.to_dict() for _, row in candidate_meta.iterrows()}


def _selection_params(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": int(meta["candidate_id"]),
        "confirm_bars": int(meta["confirm_bars"]),
        "leverage": float(meta["leverage"]),
        "lock_log": float(meta["lock_log"]),
        "quota_arm_log": _none_if_nan(meta.get("quota_arm_log")),
        "quota_leverage": _none_if_nan(meta.get("quota_leverage")),
    }


def _none_if_nan(value: Any) -> Any:
    return None if value is None or pd.isna(value) else value


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_strict_exact_result"]
    decision = summary["decision"]
    return "\n".join(
        [
            "# 28 Relaxed No-Monthly-Profit Audit",
            "",
            "This is research only. It is not a live-trading strategy.",
            "",
            "## Question",
            "",
            "What happens if the monthly-profitable-month requirement is removed?",
            "",
            "## Best strict exact result",
            "",
            f"- Selector: `{best['selector_id']}`",
            f"- 2025 return: `{best['return_2025_pct']:.2f}%`",
            f"- 2026 YTD return: `{best['return_2026_ytd_pct']:.2f}%`",
            f"- Losing eval months: `{best['losing_eval_months']}`",
            f"- Worst month: `{best['min_monthly_return_pct']:.2f}%`",
            f"- Max drawdown: `{best['max_drawdown_pct']:.2f}%`",
            "",
            "## Decision",
            "",
            f"- Verdict: `{decision['verdict']}`",
            f"- Reason: {decision['reason']}",
            f"- Next step: {decision['next_step']}",
            "",
        ]
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False), encoding="utf-8")


def _rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
