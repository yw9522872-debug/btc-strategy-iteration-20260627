from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import audit_strategy_16_new_family_probe_20260627 as probe16
import audit_strategy_17_simple_family_upper_bound_20260627 as upper17


STRATEGY_ID = "strategy_18_upper_bound_failure_review_20260627"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
SOURCE_17_SUMMARY = ROOT / "artifacts" / "strategy_17_simple_family_upper_bound_20260627" / "summary.json"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source17 = json.loads(SOURCE_17_SUMMARY.read_text(encoding="utf-8"))
    ohlc_path = ROOT / source17["source"]["combined_ohlc"]
    market = probe16._load_market(ohlc_path)
    features = probe16.FeatureCache(market)
    candidates = probe16._candidate_library()
    candidate_monthly = upper17._candidate_monthly(candidates, market, features)

    failure_months = sorted(
        set(source17["oracle_summary"][0]["non_positive_months"])
        | set(source17["oracle_summary"][1]["non_positive_months"])
    )
    review = _review_failure_months(candidate_monthly, market, failure_months)
    family = _family_failure_summary(review)
    summary = {
        "status": "strategy_18_upper_bound_failure_review_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Review the months where Strategy 17 simple-family oracle upper bounds still failed monthly profitability or order-count gates.",
        "source": {
            "strategy_17_summary": _rel(SOURCE_17_SUMMARY),
            "strategy_17_decision": source17["decision"],
            "combined_ohlc": source17["source"]["combined_ohlc"],
        },
        "failure_months": failure_months,
        "failure_month_count": len(failure_months),
        "review": _json_ready(review.to_dict("records")),
        "failure_type_counts": {str(k): int(v) for k, v in review["failure_type"].value_counts().sort_index().items()},
        "family_failure_summary": _json_ready(family.to_dict("records")),
        "decision": {
            "verdict": "FAILURE_MONTHS_EXPLAIN_SIMPLE_FAMILY_STOP",
            "promote_strategy": False,
            "reason": "失败月里多次出现最佳候选是空仓或交易不足，说明继续微调这批简单规则意义不大。",
            "next_step": "如果继续研究，应换更不同的策略族；先不要再扩均线/Donchian/RSI/布林带/ATR突破这批规则。",
        },
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "strategy_17_summary_sha256": _sha256(SOURCE_17_SUMMARY),
            "strategy_17_script_sha256": _sha256(SCRIPTS / "audit_strategy_17_simple_family_upper_bound_20260627.py"),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "failure_month_review": _rel(OUT_DIR / "failure_month_review.csv"),
            "family_failure_summary": _rel(OUT_DIR / "family_failure_summary.csv"),
        },
    }

    review.to_csv(OUT_DIR / "failure_month_review.csv", index=False)
    family.to_csv(OUT_DIR / "family_failure_summary.csv", index=False)
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _review_failure_months(candidate_monthly: pd.DataFrame, market: dict[str, Any], months: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for month in months:
        group = candidate_monthly.loc[candidate_monthly["month"] == month].copy()
        order_pool = group.loc[group["orders"] >= probe16.REQUIRED_MIN_MONTHLY_ORDERS].copy()
        best_all = group.sort_values(["return_pct", "orders"], ascending=[False, False]).iloc[0]
        best_order10 = order_pool.sort_values(["return_pct", "orders"], ascending=[False, False]).iloc[0]
        stats = _market_month_stats(market, month)
        best_all_return = float(best_all["return_pct"])
        best_order10_return = float(best_order10["return_pct"])
        if best_all_return <= 0:
            failure_type = "no_positive_candidate"
        elif best_order10_return <= 0:
            failure_type = "positive_only_with_too_few_orders"
        else:
            failure_type = "other"
        rows.append(
            {
                "month": month,
                "failure_type": failure_type,
                **stats,
                "positive_candidate_count": int((group["return_pct"] > 0).sum()),
                "positive_order10_candidate_count": int((order_pool["return_pct"] > 0).sum()),
                "best_all_return_pct": best_all_return,
                "best_all_orders": int(best_all["orders"]),
                "best_all_family": best_all["family"],
                "best_all_rule": best_all["rule"],
                "best_all_candidate_id": best_all["candidate_id"],
                "best_order10_return_pct": best_order10_return,
                "best_order10_orders": int(best_order10["orders"]),
                "best_order10_family": best_order10["family"],
                "best_order10_rule": best_order10["rule"],
                "best_order10_candidate_id": best_order10["candidate_id"],
            }
        )
    return pd.DataFrame(rows)


def _market_month_stats(market: dict[str, Any], month: str) -> dict[str, Any]:
    mask = market["month"] == month
    close = market["close"][mask]
    high = market["high"][mask]
    low = market["low"][mask]
    raw_return = market["raw_return"][mask]
    month_return = close[-1] / close[0] - 1.0
    high_low_range = high.max() / low.min() - 1.0
    realized_vol = float(np.std(raw_return) * np.sqrt(len(raw_return)) * 100.0)
    trend_efficiency = abs(month_return) / high_low_range if high_low_range else 0.0
    return {
        "btc_month_return_pct": float(month_return * 100.0),
        "btc_high_low_range_pct": float(high_low_range * 100.0),
        "realized_vol_proxy_pct": realized_vol,
        "trend_efficiency": float(trend_efficiency),
    }


def _family_failure_summary(review: pd.DataFrame) -> pd.DataFrame:
    return (
        review.groupby(["failure_type", "best_order10_family", "best_order10_rule"], as_index=False)
        .agg(
            months=("month", "count"),
            avg_best_order10_return_pct=("best_order10_return_pct", "mean"),
            min_best_order10_return_pct=("best_order10_return_pct", "min"),
        )
        .sort_values(["failure_type", "months"], ascending=[True, False])
    )


def _render_report(summary: dict[str, Any]) -> str:
    rows = summary["review"]
    lines = [
        "# 18号上限失败月份复盘",
        "",
        "这不是新策略，只解释17号为什么连看答案上限都没过。",
        "",
        f"- 失败月份数：`{summary['failure_month_count']}`",
        f"- 失败类型：`{summary['failure_type_counts']}`",
        "",
        "## 失败月份",
        "",
    ]
    for row in rows:
        lines.append(
            f"- `{row['month']}`：`{row['failure_type']}`，BTC月涨跌 `{row['btc_month_return_pct']:.2f}%`，"
            f"最佳全候选 `{row['best_all_return_pct']:.2f}%`/{row['best_all_orders']}单，"
            f"最佳10单候选 `{row['best_order10_return_pct']:.2f}%`/{row['best_order10_orders']}单"
        )
    lines.extend(
        [
            "",
            "## 判断",
            "",
            f"`{summary['decision']['verdict']}`",
            "",
            summary["decision"]["reason"],
        ]
    )
    return "\n".join(lines) + "\n"


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, float):
        return None if np.isnan(value) else value
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
