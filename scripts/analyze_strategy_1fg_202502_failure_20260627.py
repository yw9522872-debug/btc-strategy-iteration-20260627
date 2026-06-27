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
import search_strategy_1f_selective_runner_20260627 as strategy_1f
import search_strategy_1g_cap7_selective_runner_20260627 as strategy_1g


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_1fg_202502_failure_review_20260627"
MONTH = "2025-02"

SCENARIOS = [
    ("1F_base", "1F", 0.001, 0),
    ("1F_04pct_delay1_fail", "1F", 0.002, 1),
    ("1F_04pct_delay2_fail", "1F", 0.002, 2),
    ("1G_base", "1G", 0.001, 0),
    ("1G_03pct_delay1_fail", "1G", 0.0015, 1),
    ("1G_04pct_delay0_fail", "1G", 0.002, 0),
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = source_pool._load_features(source_pool.FEATURE_FRAME)
    features = source_pool._add_features(source)
    market = source_pool._market(features)
    feature_slice = _feature_slice(features)
    selections = pd.read_csv(ROOT / "artifacts" / "strategy_1b_expanded_controls_20260627" / "strategy_1b_selections.csv")

    scenario_rows: list[dict[str, Any]] = []
    guard_rows: list[dict[str, Any]] = []
    day_rows: list[dict[str, Any]] = []
    worst_bar_rows: list[dict[str, Any]] = []
    order_rows: list[dict[str, Any]] = []

    for scenario_id, label, cost_per_side, extra_delay_bars in SCENARIOS:
        module = strategy_1f if label == "1F" else strategy_1g
        inputs = (
            module._base_side(features),
            module._trend_side(features),
            module._runner_side(features),
            module._weak_trend_mask(features),
        )
        equity = module._simulate(*inputs, market, selections, cost_per_side, extra_delay_bars)
        strategy_1a._assert_signal_timing(equity)
        month_frame = _month_frame(equity, feature_slice, cost_per_side)

        scenario_rows.append(_scenario_summary(scenario_id, label, cost_per_side, extra_delay_bars, month_frame))
        guard_rows.extend(_breakdown(month_frame, ["guard_reason"], scenario_id, label, cost_per_side, extra_delay_bars))
        day_rows.extend(_breakdown(month_frame, ["date"], scenario_id, label, cost_per_side, extra_delay_bars))
        worst_bar_rows.extend(_worst_bars(month_frame, scenario_id, label, cost_per_side, extra_delay_bars))
        order_rows.extend(_order_events(month_frame, scenario_id, label, cost_per_side, extra_delay_bars))

    scenarios = pd.DataFrame(scenario_rows)
    guard_breakdown = pd.DataFrame(guard_rows)
    day_breakdown = pd.DataFrame(day_rows)
    worst_bars = pd.DataFrame(worst_bar_rows)
    order_events = pd.DataFrame(order_rows)
    order_summary = _order_summary(order_events)

    scenarios.to_csv(OUT_DIR / "scenario_summary.csv", index=False)
    guard_breakdown.to_csv(OUT_DIR / "guard_reason_breakdown.csv", index=False)
    day_breakdown.to_csv(OUT_DIR / "daily_breakdown.csv", index=False)
    worst_bars.to_csv(OUT_DIR / "worst_bars.csv", index=False)
    order_events.to_csv(OUT_DIR / "order_events.csv", index=False)
    order_summary.to_csv(OUT_DIR / "order_event_summary.csv", index=False)

    summary = {
        "status": "strategy_1fg_202502_failure_review_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "month": MONTH,
        "does_not_overwrite": [
            "artifacts/strategy_freeze_monthly_profit_lock_20260627",
            "artifacts/strategy_1f_selective_runner_20260627",
            "artifacts/strategy_1g_cap7_selective_runner_20260627",
        ],
        "scenario_summary": lock_search._json_ready(scenarios.to_dict("records")),
        "order_event_summary": lock_search._json_ready(order_summary.to_dict("records")),
        "main_findings": _main_findings(scenarios, guard_breakdown, day_breakdown, worst_bars),
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "scenario_summary": _relpath(OUT_DIR / "scenario_summary.csv"),
            "guard_reason_breakdown": _relpath(OUT_DIR / "guard_reason_breakdown.csv"),
            "daily_breakdown": _relpath(OUT_DIR / "daily_breakdown.csv"),
            "worst_bars": _relpath(OUT_DIR / "worst_bars.csv"),
            "order_events": _relpath(OUT_DIR / "order_events.csv"),
            "order_event_summary": _relpath(OUT_DIR / "order_event_summary.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _feature_slice(features: pd.DataFrame) -> pd.DataFrame:
    out = features[
        [
            "timestamp",
            "natr_30",
            "trend_close_ema_gap_bps_60",
            "trend_adx_30",
            "trend_donchian_pos_30",
            "rsi14",
        ]
    ].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    return out


def _month_frame(equity: pd.DataFrame, feature_slice: pd.DataFrame, cost_per_side: float) -> pd.DataFrame:
    frame = equity.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.loc[frame["timestamp"].dt.strftime("%Y-%m") == MONTH].copy()
    frame = frame.merge(feature_slice, on="timestamp", how="left")
    frame["raw_log_return"] = np.log(frame["close"].astype(float)).diff().fillna(0.0)
    frame["gross_log_return"] = frame["active_position"].astype(float) * frame["raw_log_return"]
    frame["cost_log_return"] = -frame["turnover"].astype(float) * cost_per_side
    frame["date"] = frame["timestamp"].dt.strftime("%Y-%m-%d")
    active_side = np.sign(frame["active_position"].astype(float)).astype(int)
    trend_side = frame["trend_side"].astype(int)
    frame["trend_alignment"] = np.select(
        [
            active_side == 0,
            trend_side == 0,
            active_side == trend_side,
            active_side == -trend_side,
        ],
        ["flat", "no_strong_trend", "with_trend", "against_trend"],
        default="mixed",
    )
    frame["abs_active_position"] = frame["active_position"].astype(float).abs()
    frame["large_active_position"] = frame["abs_active_position"] >= 2.0
    return frame


def _scenario_summary(
    scenario_id: str,
    label: str,
    cost_per_side: float,
    extra_delay_bars: int,
    frame: pd.DataFrame,
) -> dict[str, Any]:
    strategy_log = float(frame["strategy_log_return"].sum())
    gross_log = float(frame["gross_log_return"].sum())
    cost_log = float(frame["cost_log_return"].sum())
    return {
        "scenario_id": scenario_id,
        "candidate": label,
        "cost_per_side": cost_per_side,
        "round_trip_cost": cost_per_side * 2,
        "extra_delay_bars": extra_delay_bars,
        "month_return_pct": float((np.exp(strategy_log) - 1.0) * 100.0),
        "gross_return_pct": float((np.exp(gross_log) - 1.0) * 100.0),
        "cost_log": cost_log,
        "cost_pct_rough": float((np.exp(cost_log) - 1.0) * 100.0),
        "turnover": float(frame["turnover"].sum()),
        "orders": int(frame["order_count"].sum()),
        "bars": int(len(frame)),
        "active_bars": int((frame["abs_active_position"] > 0).sum()),
        "large_active_bars": int(frame["large_active_position"].sum()),
        "against_strong_trend_bars": int((frame["trend_alignment"] == "against_trend").sum()),
        "worst_bar_log_return": float(frame["strategy_log_return"].min()),
        "worst_bar_time": str(frame.loc[frame["strategy_log_return"].idxmin(), "timestamp"]),
    }


def _breakdown(
    frame: pd.DataFrame,
    group_cols: list[str],
    scenario_id: str,
    label: str,
    cost_per_side: float,
    extra_delay_bars: int,
) -> list[dict[str, Any]]:
    rows = (
        frame.groupby(group_cols, dropna=False)
        .agg(
            bars=("timestamp", "size"),
            net_log=("strategy_log_return", "sum"),
            gross_log=("gross_log_return", "sum"),
            cost_log=("cost_log_return", "sum"),
            turnover=("turnover", "sum"),
            orders=("order_count", "sum"),
            active_bars=("abs_active_position", lambda values: int((values > 0).sum())),
            large_active_bars=("large_active_position", "sum"),
            worst_bar_log_return=("strategy_log_return", "min"),
        )
        .reset_index()
    )
    rows["net_return_pct"] = (np.exp(rows["net_log"]) - 1.0) * 100.0
    rows["scenario_id"] = scenario_id
    rows["candidate"] = label
    rows["cost_per_side"] = cost_per_side
    rows["round_trip_cost"] = cost_per_side * 2
    rows["extra_delay_bars"] = extra_delay_bars
    return rows.to_dict("records")


def _worst_bars(
    frame: pd.DataFrame,
    scenario_id: str,
    label: str,
    cost_per_side: float,
    extra_delay_bars: int,
) -> list[dict[str, Any]]:
    cols = [
        "timestamp",
        "date",
        "close",
        "strategy_log_return",
        "gross_log_return",
        "cost_log_return",
        "raw_log_return",
        "active_position",
        "position",
        "turnover",
        "order_count",
        "base_side",
        "trend_side",
        "trend_alignment",
        "weak_trend",
        "guard_reason",
        "natr_30",
        "trend_close_ema_gap_bps_60",
        "trend_adx_30",
        "rsi14",
    ]
    out = frame.nsmallest(20, "strategy_log_return")[cols].copy()
    out["scenario_id"] = scenario_id
    out["candidate"] = label
    out["cost_per_side"] = cost_per_side
    out["round_trip_cost"] = cost_per_side * 2
    out["extra_delay_bars"] = extra_delay_bars
    return out.to_dict("records")


def _order_events(
    frame: pd.DataFrame,
    scenario_id: str,
    label: str,
    cost_per_side: float,
    extra_delay_bars: int,
) -> list[dict[str, Any]]:
    raw = frame["raw_log_return"].to_numpy(float)
    position = frame["position"].to_numpy(float)
    records: list[dict[str, Any]] = []
    order_indexes = np.flatnonzero(frame["turnover"].to_numpy(float) > 0)
    for idx in order_indexes:
        row = frame.iloc[idx]
        next_1 = _future_position_return(raw, position[idx], idx, 1)
        next_3 = _future_position_return(raw, position[idx], idx, 3)
        next_8 = _future_position_return(raw, position[idx], idx, 8)
        records.append(
            {
                "scenario_id": scenario_id,
                "candidate": label,
                "cost_per_side": cost_per_side,
                "round_trip_cost": cost_per_side * 2,
                "extra_delay_bars": extra_delay_bars,
                "timestamp": row["timestamp"],
                "date": row["date"],
                "guard_reason": row["guard_reason"],
                "trend_alignment": row["trend_alignment"],
                "from_active_position": float(row["active_position"]),
                "to_position": float(row["position"]),
                "turnover": float(row["turnover"]),
                "order_count": int(row["order_count"]),
                "entry_cost_log": float(-row["turnover"] * cost_per_side),
                "next_1bar_target_log_return": next_1,
                "next_3bar_target_log_return": next_3,
                "next_8bar_target_log_return": next_8,
                "close": float(row["close"]),
                "natr_30": float(row["natr_30"]),
                "trend_close_ema_gap_bps_60": float(row["trend_close_ema_gap_bps_60"]),
                "trend_adx_30": float(row["trend_adx_30"]),
            }
        )
    return records


def _future_position_return(raw: np.ndarray, target_position: float, index: int, bars: int) -> float:
    start = index + 1
    end = min(index + 1 + bars, len(raw))
    if start >= end:
        return 0.0
    return float(target_position * raw[start:end].sum())


def _order_summary(order_events: pd.DataFrame) -> pd.DataFrame:
    if order_events.empty:
        return pd.DataFrame()
    return (
        order_events.groupby(["scenario_id", "candidate", "cost_per_side", "extra_delay_bars"])
        .agg(
            order_events=("timestamp", "size"),
            turnover=("turnover", "sum"),
            entry_cost_log=("entry_cost_log", "sum"),
            avg_next_1bar_target_log_return=("next_1bar_target_log_return", "mean"),
            avg_next_3bar_target_log_return=("next_3bar_target_log_return", "mean"),
            avg_next_8bar_target_log_return=("next_8bar_target_log_return", "mean"),
            bad_next_3bar_events=("next_3bar_target_log_return", lambda values: int((values < 0).sum())),
            worst_next_3bar_target_log_return=("next_3bar_target_log_return", "min"),
        )
        .reset_index()
    )


def _main_findings(
    scenarios: pd.DataFrame,
    guard_breakdown: pd.DataFrame,
    day_breakdown: pd.DataFrame,
    worst_bars: pd.DataFrame,
) -> dict[str, Any]:
    failed = scenarios.loc[scenarios["month_return_pct"] < 0].copy()
    worst_days = (
        day_breakdown.sort_values("net_log")
        .groupby("scenario_id", as_index=False)
        .first()[["scenario_id", "date", "net_return_pct", "turnover", "orders"]]
    )
    worst_guards = (
        guard_breakdown.sort_values("net_log")
        .groupby("scenario_id", as_index=False)
        .first()[["scenario_id", "guard_reason", "net_return_pct", "gross_log", "cost_log", "turnover", "orders"]]
    )
    return lock_search._json_ready(
        {
            "failed_scenarios": failed[["scenario_id", "candidate", "month_return_pct", "turnover", "orders"]].to_dict("records"),
            "worst_day_by_scenario": worst_days.to_dict("records"),
            "worst_guard_reason_by_scenario": worst_guards.to_dict("records"),
            "single_worst_bars": worst_bars.sort_values("strategy_log_return").head(10).to_dict("records"),
            "interpretation": [
                "2025-02 的失败不是单纯方向错，而是高成本或延迟下没能快速锁利停手，暴露K线、订单和换手急剧增加。",
                "失败场景的最大亏损来自 adverse_shock_cut：大仓刚被急跌/急涨打中，又立刻切仓，手续费和行情亏损叠加。",
                "下一步应先研究降频、急变后冷却、以及锁利失败时的保命规则，不宜继续加复杂预测模型。",
            ],
        }
    )


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# 1F/1G 2025-02 失败复盘",
        "",
        f"- status: `{summary['status']}`",
        "- 这不是新策略，只是拆解 2025-02 为什么在高手续费和延迟下失败。",
        "- 所有信号仍复用已有 1F/1G 的已收盘K线逻辑。",
        "",
        "## 场景汇总",
        "",
        "| 场景 | 候选 | 开平合计手续费 | 延迟K线 | 月收益 | 毛收益 | 手续费粗略损耗 | 暴露K线 | 大仓K线 | 换手 | 订单 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["scenario_summary"]:
        lines.append(
            f"| {row['scenario_id']} | {row['candidate']} | {row['round_trip_cost']:.4f} | "
            f"{row['extra_delay_bars']} | {row['month_return_pct']:.2f}% | {row['gross_return_pct']:.2f}% | "
            f"{row['cost_pct_rough']:.2f}% | {row['active_bars']} | {row['large_active_bars']} | "
            f"{row['turnover']:.1f} | {row['orders']} |"
        )
    lines.extend(
        [
            "",
            "## 初步结论",
            "",
            "- 正常场景只暴露约 640 根K线；失败场景暴露约 2630 根K线，几乎整月都在场内。",
            "- 失败场景的核心伤口是 `adverse_shock_cut`：大仓遇到急变，被迫切仓，行情亏损和手续费一起放大。",
            "- 下一步应优先研究：锁利失败后的保命规则、高波动降频、急变后冷却、以及 2025-02 这种行情的 regime 识别。",
            "- 不建议继续直接堆指标或大规模调参，那很容易只是拟合 2025-02 的噪声。",
            "",
            "## 文件",
            "",
            f"- 场景汇总：`{summary['files']['scenario_summary']}`",
            f"- 保护规则拆解：`{summary['files']['guard_reason_breakdown']}`",
            f"- 最差K线：`{summary['files']['worst_bars']}`",
            f"- 下单事件：`{summary['files']['order_events']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
