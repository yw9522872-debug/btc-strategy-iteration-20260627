from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import search_monthly_profit_lock_20260627 as lock_search
import search_online_expert_pool_20260627 as source_pool
import search_strategy_1_candidate_20260627 as strategy_1a
import validate_profit_lock_overfit_20260627 as overfit
import validate_profit_lock_walkforward_20260627 as walkforward


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_1b_expanded_controls_20260627"
STRATEGY_ID = "strategy_1b_expanded_controls_20260627"

LEVERAGES = [2.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0]
LOCK_LOGS = [0.0, 0.002, 0.005, 0.01, 0.02, 0.04, 0.06, 0.08]
QUOTA_CHOICES = [
    (None, None),
    (0.04, 0.0),
    (0.04, 0.1),
    (0.04, 0.25),
    (0.04, 0.5),
    (0.04, 1.0),
    (0.04, 2.0),
    (0.08, 0.0),
    (0.08, 0.1),
    (0.08, 0.25),
    (0.08, 0.5),
    (0.08, 1.0),
    (0.08, 2.0),
    (0.12, 0.0),
    (0.12, 0.1),
    (0.12, 0.25),
    (0.12, 0.5),
    (0.12, 1.0),
    (0.12, 2.0),
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = source_pool._load_features(source_pool.FEATURE_FRAME)
    features = source_pool._add_features(source)
    market = source_pool._market(features)
    experts = source_pool._expert_pool(features)
    expert_index = overfit._find_fixed_expert(experts)
    side = experts[expert_index].target

    candidates = _candidate_results(side, market)
    eval_months = [str(month) for month in market["month_labels"] if str(month)[:4] in lock_search.EVAL_YEARS]
    selections = [walkforward._select_for_month(month, candidates) for month in eval_months]
    walkforward._assert_no_future(selections)

    equity = walkforward._simulate_walkforward(side, market, {row["eval_month"]: row for row in selections})
    strategy_1a._assert_signal_timing(equity)
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)
    row = walkforward._result_row(equity, monthly, yearly)
    signals = strategy_1a._signals(equity)
    signals["candidate_version"] = STRATEGY_ID

    pd.DataFrame(selections).to_csv(OUT_DIR / "strategy_1b_selections.csv", index=False)
    signals.to_csv(OUT_DIR / "strategy_1b_signals.csv", index=False)
    equity.to_csv(OUT_DIR / "strategy_1b_equity.csv", index=False)
    monthly.to_csv(OUT_DIR / "strategy_1b_monthly.csv", index=False)
    yearly.to_csv(OUT_DIR / "strategy_1b_yearly.csv", index=False)

    summary = {
        "status": "strategy_1b_expanded_controls_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "strict_no_future_function": True,
        "no_future_checks": {
            "selection_uses_only_months_before_eval_month": True,
            "bar_return_uses_previous_bar_position": True,
        },
        "selection_rule": (
            "For each evaluated month, choose leverage/lock/quota from an expanded grid using only "
            f"months from {walkforward.TRAIN_START_MONTH} through the month before that evaluated month."
        ),
        "expert": experts[expert_index].params,
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
        "monthly": lock_search._json_ready(
            monthly[["month", "return_pct", "orders", "drawdown_pct"]].to_dict("records")
        ),
        "risk_flags": {
            "fixed_signal_still_from_prior_research": True,
            "uses_higher_leverage_than_strategy_0": True,
            "not_a_live_guarantee": True,
        },
        "hashes": {
            "script_sha256": lock_search._sha256(Path(__file__)),
            "feature_frame_sha256": lock_search._sha256(source_pool.FEATURE_FRAME),
            "signals_sha256": lock_search._sha256(OUT_DIR / "strategy_1b_signals.csv"),
        },
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "selections": _relpath(OUT_DIR / "strategy_1b_selections.csv"),
            "signals": _relpath(OUT_DIR / "strategy_1b_signals.csv"),
            "equity": _relpath(OUT_DIR / "strategy_1b_equity.csv"),
            "monthly": _relpath(OUT_DIR / "strategy_1b_monthly.csv"),
            "yearly": _relpath(OUT_DIR / "strategy_1b_yearly.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _candidate_results(side: Any, market: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for leverage in LEVERAGES:
        for lock_log in LOCK_LOGS:
            for quota_arm_log, quota_leverage in QUOTA_CHOICES:
                _, arrays = lock_search._simulate(side, leverage, lock_log, None, quota_arm_log, quota_leverage, market)
                candidates.append(
                    {
                        "candidate_id": len(candidates),
                        "params": {
                            "leverage": leverage,
                            "lock_log": lock_log,
                            "quota_arm_log": quota_arm_log,
                            "quota_leverage": quota_leverage,
                        },
                        "monthly": overfit._arrays_to_monthly(arrays, market),
                    }
                )
    return candidates


def _render_report(summary: dict[str, Any]) -> str:
    row = summary["row"]
    lines = [
        "# Strategy 1B Expanded Controls",
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
        "## Risk Flags",
        "",
        "- fixed signal still comes from prior research",
        "- expanded grid can select leverage up to 12x",
        "- research only, not a live guarantee",
    ]
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
