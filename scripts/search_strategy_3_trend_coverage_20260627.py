from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import search_monthly_profit_lock_20260627 as lock_search
import search_online_expert_pool_20260627 as source_pool
import search_strategy_1_candidate_20260627 as strategy_1a
import search_strategy_1c_trend_runner_20260627 as strategy_1c
import search_strategy_1f_selective_runner_20260627 as strategy_1f


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_3_trend_coverage_20260627"
STRATEGY_ID = "strategy_3_trend_coverage_20260627"

LOCK_LOG_CAP = 0.04
RUNNER_GAP_BPS = 350.0
RUNNER_CONFIRM_BARS = 8
RUNNER_LEVERAGE = 0.10


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    old_runner = (strategy_1f.RUNNER_GAP_BPS, strategy_1f.RUNNER_CONFIRM_BARS, strategy_1f.RUNNER_LEVERAGE)
    try:
        strategy_1f.RUNNER_GAP_BPS = RUNNER_GAP_BPS
        strategy_1f.RUNNER_CONFIRM_BARS = RUNNER_CONFIRM_BARS
        strategy_1f.RUNNER_LEVERAGE = RUNNER_LEVERAGE
        summary = _run()
    finally:
        strategy_1f.RUNNER_GAP_BPS, strategy_1f.RUNNER_CONFIRM_BARS, strategy_1f.RUNNER_LEVERAGE = old_runner

    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _run() -> dict:
    source = source_pool._load_features(source_pool.FEATURE_FRAME)
    features = source_pool._add_features(source)
    market = source_pool._market(features)
    base_side = strategy_1f._base_side(features)
    trend_side = strategy_1f._trend_side(features)
    runner_side = strategy_1f._runner_side(features)
    weak_trend = strategy_1f._weak_trend_mask(features)
    selections = _selections()

    equity = strategy_1f._simulate(base_side, trend_side, runner_side, weak_trend, market, selections, lock_search.COST_PER_SIDE)
    strategy_1a._assert_signal_timing(equity)
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)
    row = strategy_1c._result_row(equity, monthly, yearly)
    diagnostics = strategy_1f._diagnostics(equity)
    coverage = _coverage_diagnostics(equity)
    signals = strategy_1a._signals(equity)
    signals["candidate_version"] = STRATEGY_ID

    stress = pd.DataFrame(
        [
            _stress_row(base_side, trend_side, runner_side, weak_trend, market, selections, cost, delay)
            for cost in [0.001, 0.0015, 0.002]
            for delay in [0, 1, 2]
        ]
    )

    selections.to_csv(OUT_DIR / "strategy_3_selections.csv", index=False)
    signals.to_csv(OUT_DIR / "strategy_3_signals.csv", index=False)
    equity.to_csv(OUT_DIR / "strategy_3_equity.csv", index=False)
    monthly.to_csv(OUT_DIR / "strategy_3_monthly.csv", index=False)
    yearly.to_csv(OUT_DIR / "strategy_3_yearly.csv", index=False)
    stress.to_csv(OUT_DIR / "strategy_3_stress.csv", index=False)

    return {
        "status": "strategy_3_trend_coverage_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "base": "strategy_2c_lock_cap_20260627",
        "strict_no_future_function": True,
        "change": "Keep Strategy 2C, but make the post-lock tiny trend runner cover strong trends earlier: 350 bps gap, ADX >= 30, 8-bar confirmation, 0.10x leverage.",
        "rules": {
            "lock_log_cap": LOCK_LOG_CAP,
            "post_lock_runner_gap_bps": RUNNER_GAP_BPS,
            "post_lock_runner_confirm_bars": RUNNER_CONFIRM_BARS,
            "post_lock_runner_leverage": RUNNER_LEVERAGE,
        },
        "cost_model": {
            "cost_per_side": lock_search.COST_PER_SIDE,
            "round_trip_open_close": lock_search.COST_PER_SIDE * 2,
        },
        "row": lock_search._json_ready(row),
        "diagnostics": lock_search._json_ready({**diagnostics, **coverage}),
        "yearly": lock_search._json_ready(yearly.to_dict("records")),
        "monthly": lock_search._json_ready(monthly[["month", "return_pct", "orders", "drawdown_pct"]].to_dict("records")),
        "stress": lock_search._json_ready(stress.to_dict("records")),
        "risk_flags": {
            "fixed_signal_still_from_prior_research": True,
            "uses_strategy_1b_selected_controls": True,
            "runner_gap_change_is_posthoc_visual_review": True,
            "not_a_live_guarantee": True,
        },
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "selections": _relpath(OUT_DIR / "strategy_3_selections.csv"),
            "signals": _relpath(OUT_DIR / "strategy_3_signals.csv"),
            "equity": _relpath(OUT_DIR / "strategy_3_equity.csv"),
            "monthly": _relpath(OUT_DIR / "strategy_3_monthly.csv"),
            "yearly": _relpath(OUT_DIR / "strategy_3_yearly.csv"),
            "stress": _relpath(OUT_DIR / "strategy_3_stress.csv"),
        },
    }


def _selections() -> pd.DataFrame:
    selections = pd.read_csv(ROOT / "artifacts" / "strategy_1b_expanded_controls_20260627" / "strategy_1b_selections.csv")
    selections = selections.copy()
    selections["original_lock_log"] = selections["lock_log"]
    selections["lock_log"] = selections["lock_log"].clip(upper=LOCK_LOG_CAP)
    return selections


def _stress_row(
    base_side,
    trend_side,
    runner_side,
    weak_trend,
    market,
    selections: pd.DataFrame,
    cost_per_side: float,
    extra_delay_bars: int,
) -> dict:
    equity = strategy_1f._simulate(
        base_side,
        trend_side,
        runner_side,
        weak_trend,
        market,
        selections,
        cost_per_side,
        extra_delay_bars,
    )
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)
    row = strategy_1c._result_row(equity, monthly, yearly)
    return {
        "cost_per_side": cost_per_side,
        "round_trip_cost": cost_per_side * 2,
        "extra_delay_bars": extra_delay_bars,
        **row,
        **strategy_1f._diagnostics(equity),
        **_coverage_diagnostics(equity),
    }


def _coverage_diagnostics(equity: pd.DataFrame) -> dict:
    strong = equity["trend_side"].to_numpy(int) != 0
    active = equity["active_position"].abs().to_numpy(float) > 1e-12
    return {
        "strong_trend_flat_bars": int((strong & ~active).sum()),
        "post_lock_runner_bars": int((equity["guard_reason"] == "post_lock_runner").sum()),
    }


def _render_report(summary: dict) -> str:
    row = summary["row"]
    hard_pass_count = sum(1 for item in summary["stress"] if item["hard_pass"])
    d = summary["diagnostics"]
    return "\n".join(
        [
            "# 3号候选：Trend Coverage",
            "",
            f"- strategy_id: `{summary['strategy_id']}`",
            "- 这是研究候选，不是固化版。",
            f"- hard_pass: `{row['hard_pass']}`",
            f"- 2025收益: `{row['return_2025_pct']}`",
            f"- 2026收益: `{row['return_2026_pct']}`",
            f"- 最差月份: `{row['min_monthly_return_pct']}`",
            f"- 压力场景通过: `{hard_pass_count}/9`",
            f"- 强趋势空仓K线: `{d['strong_trend_flat_bars']}`",
            f"- 锁利后趋势仓K线: `{d['post_lock_runner_bars']}`",
            "",
            "## 改动",
            "",
            "- 基于 2C。",
            "- 锁利后小趋势仓仍然只有 0.10x。",
            "- 趋势触发从 700 bps 放宽到 350 bps，并要求连续确认 8 根K线。",
            "- 目的：减少大趋势中完全空仓的问题，但不靠加杠杆解决。",
        ]
    ) + "\n"


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
