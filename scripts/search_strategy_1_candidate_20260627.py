from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import search_monthly_profit_lock_20260627 as lock_search
import search_online_expert_pool_20260627 as source_pool
import validate_profit_lock_overfit_20260627 as overfit
import validate_profit_lock_walkforward_20260627 as walkforward


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_1_candidate_20260627"
WALKFORWARD_DIR = ROOT / "artifacts" / "profit_lock_walkforward_20260627"
STRATEGY_ID = "strategy_1_candidate_20260627"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    cached = _load_cached_walkforward()
    if cached is None:
        selections, equity, monthly, yearly, row, expert, candidate_count, eval_month_count, source_mode = _compute_walkforward()
    else:
        selections, equity, monthly, yearly, row, expert, candidate_count, eval_month_count = cached
        source_mode = "reused_artifacts/profit_lock_walkforward_20260627"

    selection_rows = selections.to_dict("records")
    walkforward._assert_no_future(selection_rows)
    _assert_signal_timing(equity)
    signals = _signals(equity)

    selections.to_csv(OUT_DIR / "strategy_1_selections.csv", index=False)
    signals.to_csv(OUT_DIR / "strategy_1_signals.csv", index=False)
    equity.to_csv(OUT_DIR / "strategy_1_equity.csv", index=False)
    monthly.to_csv(OUT_DIR / "strategy_1_monthly.csv", index=False)
    yearly.to_csv(OUT_DIR / "strategy_1_yearly.csv", index=False)

    summary = {
        "status": "strategy_1_candidate_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_mode": source_mode,
        "research_only": True,
        "not_a_freeze": True,
        "strict_no_future_function": True,
        "no_future_checks": {
            "selection_uses_only_months_before_eval_month": True,
            "bar_return_uses_previous_bar_position": True,
        },
        "signal_timing": (
            "At bar t close, target_position is decided from bar-t-or-earlier data. "
            "The return from close t-1 to close t is earned only by active_position, "
            "which equals the previous bar position."
        ),
        "selection_rule": (
            "For each evaluated month, choose lock/quota/leverage using only months "
            f"from {walkforward.TRAIN_START_MONTH} through the month before that evaluated month."
        ),
        "expert": expert,
        "cost_model": {
            "cost_per_side": lock_search.COST_PER_SIDE,
            "round_trip_open_close": lock_search.COST_PER_SIDE * 2,
        },
        "candidate_count": candidate_count,
        "eval_month_count": eval_month_count,
        "row": lock_search._json_ready(row),
        "yearly": lock_search._json_ready(yearly.to_dict("records")),
        "monthly": lock_search._json_ready(
            monthly[["month", "return_pct", "orders", "drawdown_pct"]].to_dict("records")
        ),
        "hashes": {
            "script_sha256": lock_search._sha256(Path(__file__)),
            "feature_frame_sha256": lock_search._sha256(source_pool.FEATURE_FRAME),
            "signals_sha256": lock_search._sha256(OUT_DIR / "strategy_1_signals.csv"),
        },
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "selections": _relpath(OUT_DIR / "strategy_1_selections.csv"),
            "signals": _relpath(OUT_DIR / "strategy_1_signals.csv"),
            "equity": _relpath(OUT_DIR / "strategy_1_equity.csv"),
            "monthly": _relpath(OUT_DIR / "strategy_1_monthly.csv"),
            "yearly": _relpath(OUT_DIR / "strategy_1_yearly.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _load_cached_walkforward() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any], int, int] | None:
    paths = {
        "summary": WALKFORWARD_DIR / "summary.json",
        "selections": WALKFORWARD_DIR / "walkforward_selections.csv",
        "equity": WALKFORWARD_DIR / "walkforward_equity.csv",
        "monthly": WALKFORWARD_DIR / "walkforward_monthly.csv",
        "yearly": WALKFORWARD_DIR / "walkforward_yearly.csv",
    }
    if not all(path.exists() for path in paths.values()):
        return None
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    return (
        pd.read_csv(paths["selections"]),
        pd.read_csv(paths["equity"]),
        pd.read_csv(paths["monthly"]),
        pd.read_csv(paths["yearly"]),
        summary["row"],
        summary["expert"],
        int(summary["candidate_count"]),
        int(summary["eval_month_count"]),
    )


def _compute_walkforward() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any], int, int, str]:
    source = source_pool._load_features(source_pool.FEATURE_FRAME)
    features = source_pool._add_features(source)
    market = source_pool._market(features)
    experts = source_pool._expert_pool(features)
    expert_index = overfit._find_fixed_expert(experts)
    side = experts[expert_index].target

    candidates = walkforward._candidate_results(side, market)
    eval_months = [str(month) for month in market["month_labels"] if str(month)[:4] in lock_search.EVAL_YEARS]
    selections = [walkforward._select_for_month(month, candidates) for month in eval_months]

    equity = walkforward._simulate_walkforward(side, market, {row["eval_month"]: row for row in selections})
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)
    row = walkforward._result_row(equity, monthly, yearly)
    return (
        pd.DataFrame(selections),
        equity,
        monthly,
        yearly,
        row,
        experts[expert_index].params,
        len(candidates),
        len(eval_months),
        "computed_from_feature_frame",
    )


def _assert_signal_timing(equity: pd.DataFrame) -> None:
    active = equity["active_position"].to_numpy(float)
    target = equity["position"].to_numpy(float)
    assert len(active) > 0
    assert active[0] == 0.0
    assert np.allclose(active[1:], target[:-1])


def _signals(equity: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": equity["timestamp"],
            "close": equity["close"],
            "target_position": equity["position"],
            "active_position": equity["active_position"],
            "candidate_version": STRATEGY_ID,
        }
    )


def _render_report(summary: dict[str, Any]) -> str:
    row = summary["row"]
    lines = [
        "# Strategy 1 Candidate 20260627",
        "",
        f"- strategy_id: `{summary['strategy_id']}`",
        f"- strict_no_future_function: `{summary['strict_no_future_function']}`",
        f"- round_trip_cost: `{summary['cost_model']['round_trip_open_close']}`",
        f"- hard_pass: `{row['hard_pass']}`",
        f"- return_2025_pct: `{row['return_2025_pct']}`",
        f"- return_2026_pct: `{row['return_2026_pct']}`",
        f"- min_monthly_return_pct: `{row['min_monthly_return_pct']}`",
        f"- min_monthly_orders: `{row['min_monthly_orders']}`",
        f"- max_drawdown_pct: `{row['max_drawdown_pct']}`",
        "",
        "## Yearly",
        "",
        "| year | return_pct | orders | max_drawdown_pct | losing_months |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for item in summary["yearly"]:
        lines.append(
            f"| {item['year']} | {item['compounded_return_pct']:.6f} | "
            f"{item['orders_sum']} | {item['max_drawdown_pct']:.6f} | {item['losing_months']} |"
        )
    lines.extend(
        [
            "",
            "## Monthly",
            "",
            "| month | return_pct | orders | drawdown_pct |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for item in summary["monthly"]:
        lines.append(
            f"| {item['month']} | {item['return_pct']:.6f} | "
            f"{item['orders']} | {item['drawdown_pct']:.6f} |"
        )
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
