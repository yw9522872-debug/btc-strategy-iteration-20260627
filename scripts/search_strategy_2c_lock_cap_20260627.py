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
OUT_DIR = ROOT / "artifacts" / "strategy_2c_lock_cap_20260627"
STRATEGY_ID = "strategy_2c_lock_cap_20260627"
LOCK_LOG_CAP = 0.04


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
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
    signals = strategy_1a._signals(equity)
    signals["candidate_version"] = STRATEGY_ID

    stress = pd.DataFrame(
        [
            _stress_row(base_side, trend_side, runner_side, weak_trend, market, selections, cost, delay)
            for cost in [0.001, 0.0015, 0.002]
            for delay in [0, 1, 2]
        ]
    )

    selections.to_csv(OUT_DIR / "strategy_2c_selections.csv", index=False)
    signals.to_csv(OUT_DIR / "strategy_2c_signals.csv", index=False)
    equity.to_csv(OUT_DIR / "strategy_2c_equity.csv", index=False)
    monthly.to_csv(OUT_DIR / "strategy_2c_monthly.csv", index=False)
    yearly.to_csv(OUT_DIR / "strategy_2c_yearly.csv", index=False)
    stress.to_csv(OUT_DIR / "strategy_2c_stress.csv", index=False)

    summary = {
        "status": "strategy_2c_lock_cap_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "base": "strategy_1f_selective_runner_20260627",
        "strict_no_future_function": True,
        "change": "Keep Strategy 1F logic, but cap the walk-forward selected monthly lock target at 0.04 log return.",
        "lock_cap": {
            "lock_log_cap": LOCK_LOG_CAP,
            "why": "2025-02 stress failures came from not locking early enough, which left the strategy exposed for almost the whole month.",
        },
        "cost_model": {
            "cost_per_side": lock_search.COST_PER_SIDE,
            "round_trip_open_close": lock_search.COST_PER_SIDE * 2,
        },
        "row": lock_search._json_ready(row),
        "diagnostics": lock_search._json_ready(diagnostics),
        "yearly": lock_search._json_ready(yearly.to_dict("records")),
        "monthly": lock_search._json_ready(monthly[["month", "return_pct", "orders", "drawdown_pct"]].to_dict("records")),
        "stress": lock_search._json_ready(stress.to_dict("records")),
        "risk_flags": {
            "fixed_signal_still_from_prior_research": True,
            "uses_strategy_1b_selected_controls": True,
            "lock_cap_choice_is_posthoc_after_2025_02_review": True,
            "not_a_live_guarantee": True,
        },
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "selections": _relpath(OUT_DIR / "strategy_2c_selections.csv"),
            "signals": _relpath(OUT_DIR / "strategy_2c_signals.csv"),
            "equity": _relpath(OUT_DIR / "strategy_2c_equity.csv"),
            "monthly": _relpath(OUT_DIR / "strategy_2c_monthly.csv"),
            "yearly": _relpath(OUT_DIR / "strategy_2c_yearly.csv"),
            "stress": _relpath(OUT_DIR / "strategy_2c_stress.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


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
    }


def _render_report(summary: dict) -> str:
    row = summary["row"]
    hard_pass_count = sum(1 for item in summary["stress"] if item["hard_pass"])
    return "\n".join(
        [
            "# 2C候选：Lock Cap",
            "",
            f"- strategy_id: `{summary['strategy_id']}`",
            "- 这是研究候选，不是固化版。",
            f"- hard_pass: `{row['hard_pass']}`",
            f"- 2025收益: `{row['return_2025_pct']}`",
            f"- 2026收益: `{row['return_2026_pct']}`",
            f"- 最差月份: `{row['min_monthly_return_pct']}`",
            f"- 压力场景通过: `{hard_pass_count}/9`",
            "",
            "## 改动",
            "",
            "- 基于 1F。",
            "- 月度锁利目标最高只允许 0.04。",
            "- 目的：满 10 次交易后更早收手，避免 2025-02 这种月份整月暴露。",
        ]
    ) + "\n"


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
