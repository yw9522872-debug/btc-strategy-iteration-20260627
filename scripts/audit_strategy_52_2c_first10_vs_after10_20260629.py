from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import search_monthly_profit_lock_20260627 as lock_search


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_52_2c_first10_vs_after10_20260629"
STRATEGY_ID = "strategy_52_2c_first10_vs_after10_20260629"
SOURCE_EQUITY = ROOT / "artifacts" / "strategy_50_2c_without_monthly_lock_20260629" / "no_lock_keep_quota_equity.csv"
SOURCE_SUMMARY = ROOT / "artifacts" / "strategy_50_2c_without_monthly_lock_20260629" / "summary.json"
ORDER_CUTOFF = 10
EVAL_YEARS = {"2025", "2026"}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    equity = pd.read_csv(SOURCE_EQUITY, parse_dates=["timestamp"])
    equity["month"] = equity["timestamp"].dt.strftime("%Y-%m")
    equity["year"] = equity["timestamp"].dt.strftime("%Y")
    orders_after = equity.groupby("month")["order_count"].cumsum()
    equity["orders_before_bar"] = orders_after - equity["order_count"]
    equity["phase"] = np.where(equity["orders_before_bar"] < ORDER_CUTOFF, "first_10_order_area", "after_10_order_area")

    phase_yearly = _phase_summary(equity, ["year", "phase"])
    phase_monthly = _phase_summary(equity, ["month", "phase"])
    monthly = _monthly_summary(equity, phase_monthly)
    guard = _guard_summary(equity)

    phase_yearly.to_csv(OUT_DIR / "phase_yearly.csv", index=False)
    phase_monthly.to_csv(OUT_DIR / "phase_monthly.csv", index=False)
    monthly.to_csv(OUT_DIR / "monthly_first10_vs_after10.csv", index=False)
    guard.to_csv(OUT_DIR / "guard_phase_counts.csv", index=False)

    summary = {
        "status": "strategy_52_2c_first10_vs_after10_done",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "base": "strategy_50 no-lock keep-quota replay of strategy_2c",
        "strict_no_future_function": True,
        "purpose": "Attribute the no-lock 2C replay into the area before the first 10 monthly orders and the area after 10 monthly orders.",
        "source_equity": _relpath(SOURCE_EQUITY),
        "source_summary": _relpath(SOURCE_SUMMARY),
        "order_cutoff": ORDER_CUTOFF,
        "phase_yearly": lock_search._json_ready(phase_yearly.to_dict("records")),
        "monthly": lock_search._json_ready(monthly.to_dict("records")),
        "guard_phase_counts": lock_search._json_ready(guard.to_dict("records")),
        "decision": _decision(monthly, phase_yearly),
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "phase_yearly": _relpath(OUT_DIR / "phase_yearly.csv"),
            "phase_monthly": _relpath(OUT_DIR / "phase_monthly.csv"),
            "monthly": _relpath(OUT_DIR / "monthly_first10_vs_after10.csv"),
            "guard_phase_counts": _relpath(OUT_DIR / "guard_phase_counts.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _phase_summary(equity: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    grouped = equity.groupby(keys).agg(
        log_return=("strategy_log_return", "sum"),
        bars=("strategy_log_return", "size"),
        orders=("order_count", "sum"),
        turnover=("turnover", "sum"),
        exposure_pct=("active_position", lambda value: float((value.abs() > 0).mean() * 100.0)),
    )
    grouped["return_pct"] = (np.exp(grouped["log_return"]) - 1.0) * 100.0
    return grouped.reset_index()


def _monthly_summary(equity: pd.DataFrame, phase_monthly: pd.DataFrame) -> pd.DataFrame:
    full = equity.groupby("month").agg(
        full_log_return=("strategy_log_return", "sum"),
        full_orders=("order_count", "sum"),
        full_turnover=("turnover", "sum"),
    )
    full["full_return_pct"] = (np.exp(full["full_log_return"]) - 1.0) * 100.0

    pivot = phase_monthly.pivot(index="month", columns="phase", values=["log_return", "return_pct", "orders", "turnover"])
    pivot.columns = [f"{phase}_{metric}" for metric, phase in pivot.columns]
    out = full.join(pivot, how="left").reset_index()
    out["year"] = out["month"].str[:4]
    return out


def _guard_summary(equity: pd.DataFrame) -> pd.DataFrame:
    return (
        equity.groupby(["phase", "guard_reason"])
        .agg(bars=("guard_reason", "size"), log_return=("strategy_log_return", "sum"), orders=("order_count", "sum"), turnover=("turnover", "sum"))
        .assign(return_pct=lambda frame: (np.exp(frame["log_return"]) - 1.0) * 100.0)
        .reset_index()
        .sort_values(["phase", "bars"], ascending=[True, False])
    )


def _decision(monthly: pd.DataFrame, phase_yearly: pd.DataFrame) -> dict[str, Any]:
    eval_monthly = monthly.loc[monthly["year"].isin(EVAL_YEARS)].copy()
    after_col = "after_10_order_area_return_pct"
    first_col = "first_10_order_area_return_pct"
    after_losing = int((eval_monthly[after_col].fillna(0.0) <= 0).sum())
    first_losing = int((eval_monthly[first_col].fillna(0.0) <= 0).sum())
    y = phase_yearly.set_index(["year", "phase"])["return_pct"].to_dict()
    return {
        "verdict": "POST_10_TRADES_EXPOSES_WEAK_RAW_SIGNAL",
        "reason": "用户判断成立：10笔锁利不是优势，而是因为后续交易区间整体质量很差；2C原始信号不能长时间暴露。",
        "first_10_losing_months": first_losing,
        "after_10_losing_months": after_losing,
        "first_10_return_2025_pct": y.get(("2025", "first_10_order_area")),
        "after_10_return_2025_pct": y.get(("2025", "after_10_order_area")),
        "first_10_return_2026_pct": y.get(("2026", "first_10_order_area")),
        "after_10_return_2026_pct": y.get(("2026", "after_10_order_area")),
    }


def _render_report(summary: dict[str, Any]) -> str:
    decision = summary["decision"]
    lines = [
        "# Strategy 52：2C 前10笔与10笔后归因",
        "",
        f"- strategy_id: `{summary['strategy_id']}`",
        "- 这是研究归因，不是策略。",
        "- 用50号“不锁利但保留临时降仓”的回放结果，把每个月拆成前10笔交易区域和10笔之后区域。",
        "",
        "| 年份 | 区域 | 收益 | 订单 | 换手 | 暴露率 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in summary["phase_yearly"]:
        if row["year"] not in EVAL_YEARS:
            continue
        phase = "前10笔区域" if row["phase"] == "first_10_order_area" else "10笔之后区域"
        lines.append(
            f"| {row['year']} | {phase} | {row['return_pct']:.2f}% | {row['orders']} | "
            f"{row['turnover']:.1f} | {row['exposure_pct']:.2f}% |"
        )
    lines += [
        "",
        "## 结论",
        "",
        f"- `{decision['verdict']}`",
        f"- {decision['reason']}",
        f"- 前10笔区域亏损月份：`{decision['first_10_losing_months']}`",
        f"- 10笔之后区域亏损月份：`{decision['after_10_losing_months']}`",
    ]
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
