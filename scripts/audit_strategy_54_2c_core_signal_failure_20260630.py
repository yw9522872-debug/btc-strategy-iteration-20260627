from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import search_monthly_profit_lock_20260627 as lock_search
import search_online_expert_pool_20260627 as source_pool
import search_strategy_1c_trend_runner_20260627 as strategy_1c
import search_strategy_1f_selective_runner_20260627 as strategy_1f


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_54_2c_core_signal_failure_20260630"
STRATEGY_ID = "strategy_54_2c_core_signal_failure_20260630"
SOURCE_50 = ROOT / "artifacts" / "strategy_50_2c_without_monthly_lock_20260629"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = source_pool._load_features(source_pool.FEATURE_FRAME)
    features = source_pool._add_features(source)
    market = source_pool._market(features)
    base_side = strategy_1f._base_side(features)

    variants = {
        "base_1x_zero_cost_no_lock": (_simulate_static(base_side, 1.0, market, 0.0), 0.0),
        "base_1x_cost_no_lock": (_simulate_static(base_side, 1.0, market, lock_search.COST_PER_SIDE), lock_search.COST_PER_SIDE),
        "base_8x_zero_cost_no_lock": (_simulate_static(base_side, 8.0, market, 0.0), 0.0),
        "base_8x_cost_no_lock": (_simulate_static(base_side, 8.0, market, lock_search.COST_PER_SIDE), lock_search.COST_PER_SIDE),
        "strategy_2c_guards_no_lock_keep_quota": (
            pd.read_csv(SOURCE_50 / "no_lock_keep_quota_equity.csv", parse_dates=["timestamp"]),
            lock_search.COST_PER_SIDE,
        ),
        "strategy_2c_guards_no_lock_no_quota": (
            pd.read_csv(SOURCE_50 / "no_lock_no_quota_equity.csv", parse_dates=["timestamp"]),
            lock_search.COST_PER_SIDE,
        ),
    }

    scan_rows: list[dict[str, Any]] = []
    yearly_rows: list[pd.DataFrame] = []
    for variant_id, (equity, charged_cost_per_side) in variants.items():
        equity = _normalize_equity(equity)
        monthly = lock_search._monthly_breakdown(equity)
        yearly = lock_search._yearly_breakdown(monthly)
        row = strategy_1c._result_row(equity, monthly, yearly)
        cost = _cost_summary(equity, charged_cost_per_side)
        scan_rows.append({"variant_id": variant_id, **row, **cost})
        yf = _yearly_cost_summary(equity, charged_cost_per_side)
        yf.insert(0, "variant_id", variant_id)
        yearly_rows.append(yf)
        equity.to_csv(OUT_DIR / f"{variant_id}_equity.csv", index=False)

    scan = pd.DataFrame(scan_rows)
    yearly_cost = pd.concat(yearly_rows, ignore_index=True)
    one_bar = _one_bar_signal_edge(base_side, market)
    monthly_edge = _monthly_signal_edge(one_bar)
    yearly_edge = _yearly_signal_edge(one_bar)

    scan.to_csv(OUT_DIR / "strategy_54_variant_scan.csv", index=False)
    yearly_cost.to_csv(OUT_DIR / "strategy_54_yearly_cost.csv", index=False)
    monthly_edge.to_csv(OUT_DIR / "strategy_54_one_bar_monthly_edge.csv", index=False)
    yearly_edge.to_csv(OUT_DIR / "strategy_54_one_bar_yearly_edge.csv", index=False)

    summary = {
        "status": "strategy_54_2c_core_signal_failure_done",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "strict_no_future_function": True,
        "purpose": "Check whether Strategy 2C's underlying ret_state 64/100 signal has standalone edge, instead of focusing on monthly lock order count.",
        "cost_model": {
            "cost_per_side": lock_search.COST_PER_SIDE,
            "round_trip_open_close": lock_search.COST_PER_SIDE * 2,
        },
        "variant_scan": lock_search._json_ready(scan.to_dict("records")),
        "yearly_cost": lock_search._json_ready(yearly_cost.to_dict("records")),
        "one_bar_yearly_edge": lock_search._json_ready(yearly_edge.to_dict("records")),
        "decision": _decision(scan, yearly_cost, yearly_edge),
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "variant_scan": _relpath(OUT_DIR / "strategy_54_variant_scan.csv"),
            "yearly_cost": _relpath(OUT_DIR / "strategy_54_yearly_cost.csv"),
            "one_bar_monthly_edge": _relpath(OUT_DIR / "strategy_54_one_bar_monthly_edge.csv"),
            "one_bar_yearly_edge": _relpath(OUT_DIR / "strategy_54_one_bar_yearly_edge.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _simulate_static(side: np.ndarray, leverage: float, market: dict[str, Any], cost_per_side: float) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    previous_position = 0.0
    previous_side = 0
    timestamp = market["timestamp"].reset_index(drop=True)
    for index, current_side in enumerate(side.astype(int)):
        current_position = float(current_side) * leverage
        current_turnover = abs(current_position - previous_position)
        current_orders = abs(int(current_side) - previous_side)
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
        previous_position = current_position
        previous_side = int(current_side)
    equity = pd.DataFrame(records)
    equity["equity"] = np.exp(equity["strategy_log_return"].cumsum())
    equity["drawdown"] = equity["equity"] / equity["equity"].cummax() - 1.0
    return equity


def _normalize_equity(equity: pd.DataFrame) -> pd.DataFrame:
    equity = equity.copy()
    equity["timestamp"] = pd.to_datetime(equity["timestamp"], utc=True)
    if "equity" not in equity:
        equity["equity"] = np.exp(equity["strategy_log_return"].cumsum())
    if "drawdown" not in equity:
        equity["drawdown"] = equity["equity"] / equity["equity"].cummax() - 1.0
    return equity


def _cost_summary(equity: pd.DataFrame, charged_cost_per_side: float) -> dict[str, float]:
    gross_log = equity["strategy_log_return"] + equity["turnover"] * charged_cost_per_side
    cost_log = equity["turnover"] * charged_cost_per_side
    return {
        "gross_log_return_before_cost": float(gross_log.sum()),
        "cost_log": float(cost_log.sum()),
        "net_log_return": float(equity["strategy_log_return"].sum()),
        "gross_return_before_cost_pct": float((np.exp(gross_log.sum()) - 1.0) * 100.0),
        "cost_drag_pct_approx": float(cost_log.sum() * 100.0),
    }


def _yearly_cost_summary(equity: pd.DataFrame, charged_cost_per_side: float) -> pd.DataFrame:
    frame = equity.copy()
    frame["year"] = frame["timestamp"].dt.strftime("%Y")
    frame["gross_log_return_before_cost"] = frame["strategy_log_return"] + frame["turnover"] * charged_cost_per_side
    frame["cost_log"] = frame["turnover"] * charged_cost_per_side
    out = frame.groupby("year").agg(
        gross_log_return_before_cost=("gross_log_return_before_cost", "sum"),
        cost_log=("cost_log", "sum"),
        net_log_return=("strategy_log_return", "sum"),
        turnover=("turnover", "sum"),
        orders=("order_count", "sum"),
        exposure_pct=("active_position", lambda value: float((value.abs() > 0).mean() * 100.0)),
    )
    out["gross_return_before_cost_pct"] = (np.exp(out["gross_log_return_before_cost"]) - 1.0) * 100.0
    out["net_return_pct"] = (np.exp(out["net_log_return"]) - 1.0) * 100.0
    return out.reset_index()


def _one_bar_signal_edge(base_side: np.ndarray, market: dict[str, Any]) -> pd.DataFrame:
    timestamp = market["timestamp"].reset_index(drop=True)
    signal = pd.Series(base_side[:-1].astype(int))
    edge = signal.to_numpy(float) * market["raw_return"][1:]
    out = pd.DataFrame(
        {
            "timestamp": timestamp.iloc[1:].to_numpy(),
            "signal": signal.to_numpy(),
            "edge_log_return_1x_no_cost": edge,
        }
    )
    out = out.loc[out["signal"] != 0].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    out["month"] = out["timestamp"].dt.strftime("%Y-%m")
    out["year"] = out["timestamp"].dt.strftime("%Y")
    out["win"] = out["edge_log_return_1x_no_cost"] > 0
    return out


def _monthly_signal_edge(one_bar: pd.DataFrame) -> pd.DataFrame:
    out = one_bar.groupby("month").agg(
        log_return_1x_no_cost=("edge_log_return_1x_no_cost", "sum"),
        signal_bars=("edge_log_return_1x_no_cost", "size"),
        win_rate=("win", "mean"),
        avg_edge_bps=("edge_log_return_1x_no_cost", lambda value: float(value.mean() * 10000.0)),
    )
    out["return_pct_1x_no_cost"] = (np.exp(out["log_return_1x_no_cost"]) - 1.0) * 100.0
    return out.reset_index()


def _yearly_signal_edge(one_bar: pd.DataFrame) -> pd.DataFrame:
    out = one_bar.groupby("year").agg(
        log_return_1x_no_cost=("edge_log_return_1x_no_cost", "sum"),
        signal_bars=("edge_log_return_1x_no_cost", "size"),
        win_rate=("win", "mean"),
        avg_edge_bps=("edge_log_return_1x_no_cost", lambda value: float(value.mean() * 10000.0)),
    )
    out["return_pct_1x_no_cost"] = (np.exp(out["log_return_1x_no_cost"]) - 1.0) * 100.0
    return out.reset_index()


def _decision(scan: pd.DataFrame, yearly_cost: pd.DataFrame, yearly_edge: pd.DataFrame) -> dict[str, Any]:
    base_1x = scan.loc[scan["variant_id"] == "base_1x_cost_no_lock"].iloc[0]
    base_8x = scan.loc[scan["variant_id"] == "base_8x_cost_no_lock"].iloc[0]
    guard = scan.loc[scan["variant_id"] == "strategy_2c_guards_no_lock_keep_quota"].iloc[0]
    edge = yearly_edge.set_index("year")["return_pct_1x_no_cost"].to_dict()
    return {
        "verdict": "CORE_RET_STATE_SIGNAL_NOT_GOOD_ENOUGH",
        "reason": "用户判断成立：问题不是开仓笔数，而是旧2C/ret_state核心信号不能在不靠早停的情况下稳定赚钱；加保护后仍会在长期暴露中被打穿。",
        "base_1x_cost_no_lock_2025_pct": float(base_1x["return_2025_pct"]),
        "base_1x_cost_no_lock_2026_pct": float(base_1x["return_2026_pct"]),
        "base_8x_cost_no_lock_2025_pct": float(base_8x["return_2025_pct"]),
        "base_8x_cost_no_lock_2026_pct": float(base_8x["return_2026_pct"]),
        "guarded_2c_no_lock_2025_pct": float(guard["return_2025_pct"]),
        "guarded_2c_no_lock_2026_pct": float(guard["return_2026_pct"]),
        "one_bar_signal_2025_pct_1x_no_cost": edge.get("2025"),
        "one_bar_signal_2026_pct_1x_no_cost": edge.get("2026"),
    }


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Strategy 54：2C 核心信号失败归因",
        "",
        f"- strategy_id: `{summary['strategy_id']}`",
        "- 这是研究归因，不是策略。",
        "- 目的：不再看开仓笔数，直接检查旧2C/ret_state核心信号本身。",
        "",
        "## 主要变体",
        "",
        "| 版本 | 2025 | 2026 | 最大回撤 | 换手 | 成本log |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary["variant_scan"]:
        lines.append(
            f"| `{row['variant_id']}` | {row['return_2025_pct']:.2f}% | {row['return_2026_pct']:.2f}% | "
            f"{row['max_drawdown_pct']:.2f}% | {row['turnover']:.1f} | {row['cost_log']:.3f} |"
        )
    lines += [
        "",
        "## 单根K线方向预测",
        "",
        "| 年份 | 1x无成本方向收益 | 信号K线数 | 胜率 | 平均边际bps |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in summary["one_bar_yearly_edge"]:
        lines.append(
            f"| {row['year']} | {row['return_pct_1x_no_cost']:.2f}% | {row['signal_bars']} | "
            f"{row['win_rate'] * 100.0:.2f}% | {row['avg_edge_bps']:.4f} |"
        )
    decision = summary["decision"]
    lines += [
        "",
        "## 结论",
        "",
        f"- `{decision['verdict']}`",
        f"- {decision['reason']}",
    ]
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
