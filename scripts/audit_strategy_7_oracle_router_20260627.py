from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_7_oracle_router_audit_20260627"
MARKET_STATE = ROOT / "artifacts" / "strategy_6_market_regime_audit_20260627" / "market_state_monthly.csv"

CANDIDATES = {
    "2C": ROOT / "artifacts" / "strategy_2c_lock_cap_20260627" / "strategy_2c_monthly.csv",
    "3": ROOT / "artifacts" / "strategy_3_trend_coverage_20260627" / "strategy_3_monthly.csv",
    "4": ROOT / "artifacts" / "strategy_4_entry_confirm_20260627" / "strategy_4_monthly.csv",
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    monthly = _load_complete_monthly()
    _self_check(monthly)

    candidate_summary = pd.DataFrame(_candidate_summary(monthly))
    regime_choice = _fullsample_regime_choice(monthly)
    routers = {
        "oracle_month_best": _oracle_month_best(monthly),
        "oracle_regime_best_fullsample": _apply_regime_choice(monthly, regime_choice),
        "oracle_regime_past_only": _oracle_regime_past_only(monthly),
    }
    router_monthly = pd.concat(routers.values(), ignore_index=True)
    router_summary = pd.DataFrame(_router_summary(router_monthly, candidate_summary))

    monthly.to_csv(OUT_DIR / "candidate_complete_monthly.csv", index=False)
    candidate_summary.to_csv(OUT_DIR / "candidate_complete_summary.csv", index=False)
    regime_choice.to_csv(OUT_DIR / "oracle_regime_choice_map.csv", index=False)
    router_monthly.to_csv(OUT_DIR / "oracle_router_monthly.csv", index=False)
    router_summary.to_csv(OUT_DIR / "oracle_router_summary.csv", index=False)

    summary = {
        "status": "strategy_7_oracle_router_audit_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "uses_posthoc_month_labels": True,
        "oracle_upper_bound": True,
        "does_not_overwrite": [
            "artifacts/strategy_2c_lock_cap_20260627",
            "artifacts/strategy_3_trend_coverage_20260627",
            "artifacts/strategy_4_entry_confirm_20260627",
            "artifacts/strategy_6_market_regime_audit_20260627",
        ],
        "complete_months_only": True,
        "excluded_partial_months": ["2026-06"],
        "candidate_summary": _records(candidate_summary),
        "oracle_regime_choice_map": _records(regime_choice),
        "oracle_router_summary": _records(router_summary),
        "decision": _decision(router_summary),
        "files": {
            "candidate_complete_monthly": _rel(OUT_DIR / "candidate_complete_monthly.csv"),
            "candidate_complete_summary": _rel(OUT_DIR / "candidate_complete_summary.csv"),
            "oracle_regime_choice_map": _rel(OUT_DIR / "oracle_regime_choice_map.csv"),
            "oracle_router_monthly": _rel(OUT_DIR / "oracle_router_monthly.csv"),
            "oracle_router_summary": _rel(OUT_DIR / "oracle_router_summary.csv"),
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_complete_monthly() -> pd.DataFrame:
    market = pd.read_csv(MARKET_STATE)
    market = market[market["complete_month"].map(_to_bool)].copy()
    rows = []
    for candidate, path in CANDIDATES.items():
        frame = pd.read_csv(path)
        frame["candidate"] = candidate
        rows.append(frame.merge(market, on="month", how="inner"))
    out = pd.concat(rows, ignore_index=True)
    out["year"] = out["month"].str[:4]
    out["complete_month"] = out["complete_month"].map(_to_bool)
    out["partial_month"] = out["partial_month"].map(_to_bool)
    return out.sort_values(["month", "candidate"]).reset_index(drop=True)


def _candidate_summary(monthly: pd.DataFrame) -> list[dict[str, Any]]:
    return [_summary_row(candidate, group, "candidate") for candidate, group in monthly.groupby("candidate", sort=False)]


def _oracle_month_best(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month, group in monthly.groupby("month", sort=True):
        chosen = group.sort_values(["log_return", "candidate"], ascending=[False, True]).iloc[0].copy()
        chosen["router"] = "oracle_month_best"
        chosen["choice_rule"] = "picked best candidate after seeing this month"
        rows.append(chosen)
    return pd.DataFrame(rows)


def _fullsample_regime_choice(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for regime, group in monthly.groupby("market_regime", sort=True):
        totals = group.groupby("candidate", as_index=False).agg(
            log_return=("log_return", "sum"),
            months=("month", "nunique"),
            min_monthly_return_pct=("return_pct", "min"),
            min_orders=("orders", "min"),
        )
        totals["total_return_pct"] = totals["log_return"].map(_return_pct)
        winner = totals.sort_values(["log_return", "candidate"], ascending=[False, True]).iloc[0]
        rows.append(
            {
                "market_regime": regime,
                "chosen_candidate": winner["candidate"],
                "chosen_total_return_pct": winner["total_return_pct"],
                "candidate_returns": json.dumps(_records(totals), ensure_ascii=False),
            }
        )
    return pd.DataFrame(rows)


def _apply_regime_choice(monthly: pd.DataFrame, choices: pd.DataFrame) -> pd.DataFrame:
    choice = dict(zip(choices["market_regime"], choices["chosen_candidate"]))
    rows = []
    for _, row in monthly.iterrows():
        if row["candidate"] != choice[row["market_regime"]]:
            continue
        selected = row.copy()
        selected["router"] = "oracle_regime_best_fullsample"
        selected["choice_rule"] = "picked full-sample best candidate for this posthoc regime"
        rows.append(selected)
    return pd.DataFrame(rows)


def _oracle_regime_past_only(monthly: pd.DataFrame) -> pd.DataFrame:
    rows = []
    months = sorted(monthly["month"].unique())
    for month in months:
        current = monthly[monthly["month"] == month]
        regime = current["market_regime"].iloc[0]
        history = monthly[(monthly["month"] < month) & (monthly["market_regime"] == regime)]
        if history.empty:
            candidate = "2C"
            rule = "no past month in this posthoc regime, defaulted to 2C"
        else:
            totals = history.groupby("candidate", as_index=False)["log_return"].sum()
            candidate = totals.sort_values(["log_return", "candidate"], ascending=[False, True]).iloc[0]["candidate"]
            rule = "picked best candidate from earlier months in this posthoc regime"
        selected = current[current["candidate"] == candidate].iloc[0].copy()
        selected["router"] = "oracle_regime_past_only"
        selected["choice_rule"] = rule
        rows.append(selected)
    return pd.DataFrame(rows)


def _router_summary(router_monthly: pd.DataFrame, candidate_summary: pd.DataFrame) -> list[dict[str, Any]]:
    baseline_log = float(candidate_summary.loc[candidate_summary["candidate"] == "2C", "log_return"].iloc[0])
    rows = []
    for router, group in router_monthly.groupby("router", sort=False):
        row = _summary_row(router, group, "router")
        row["delta_vs_2c_log_return"] = row["log_return"] - baseline_log
        row["delta_vs_2c_pct_points"] = row["total_return_pct"] - float(
            candidate_summary.loc[candidate_summary["candidate"] == "2C", "total_return_pct"].iloc[0]
        )
        rows.append(row)
    return rows


def _summary_row(name: str, group: pd.DataFrame, name_field: str) -> dict[str, Any]:
    yearly = {
        f"return_{year}_complete_pct": _return_pct(float(year_group["log_return"].sum()))
        for year, year_group in group.groupby("year", sort=True)
    }
    return {
        name_field: name,
        "months": int(group["month"].nunique()),
        "log_return": float(group["log_return"].sum()),
        "total_return_pct": _return_pct(float(group["log_return"].sum())),
        **yearly,
        "min_monthly_return_pct": float(group["return_pct"].min()),
        "losing_months": int((group["return_pct"] <= 0.0).sum()),
        "min_monthly_orders": int(group["orders"].min()),
        "worst_month_drawdown_pct": float(group["drawdown_pct"].min()),
        "avg_monthly_orders": float(group["orders"].mean()),
    }


def _decision(router_summary: pd.DataFrame) -> dict[str, Any]:
    best = router_summary.sort_values("total_return_pct", ascending=False).iloc[0]
    regime_full = router_summary.loc[router_summary["router"] == "oracle_regime_best_fullsample"].iloc[0]
    regime_past = router_summary.loc[router_summary["router"] == "oracle_regime_past_only"].iloc[0]
    return {
        "promote_router": False,
        "best_oracle_router": best["router"],
        "regime_fullsample_delta_vs_2c_pct_points": float(regime_full["delta_vs_2c_pct_points"]),
        "regime_past_only_delta_vs_2c_pct_points": float(regime_past["delta_vs_2c_pct_points"]),
        "reason": "每月事后最佳太泄漏；只按状态的 oracle 提升很小；只用过去同状态选择还跑输 2C。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# 7号 Oracle 路由上限审计",
        "",
        "这不是新策略。它故意使用事后市场状态，测试“如果完美知道状态，最多能不能明显超过 2C”。",
        "",
        "## 静态候选",
        "",
        "| 候选 | 月数 | 总收益 | 2025 | 2026完整月 | 最差月 | 最低交易 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["candidate_summary"]:
        lines.append(
            f"| {row['candidate']} | {row['months']} | {row['total_return_pct']:.2f} | "
            f"{row.get('return_2025_complete_pct', 0.0):.2f} | {row.get('return_2026_complete_pct', 0.0):.2f} | "
            f"{row['min_monthly_return_pct']:.2f} | {row['min_monthly_orders']} |"
        )
    lines.extend(
        [
            "",
            "## Oracle 路由",
            "",
            "| 路由 | 月数 | 总收益 | 2025 | 2026完整月 | 较2C多 | 最差月 | 最低交易 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in summary["oracle_router_summary"]:
        lines.append(
            f"| {row['router']} | {row['months']} | {row['total_return_pct']:.2f} | "
            f"{row.get('return_2025_complete_pct', 0.0):.2f} | {row.get('return_2026_complete_pct', 0.0):.2f} | "
            f"{row['delta_vs_2c_pct_points']:.2f} | {row['min_monthly_return_pct']:.2f} | {row['min_monthly_orders']} |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"- 是否升级成策略：`{summary['decision']['promote_router']}`。",
            f"- 原因：{summary['decision']['reason']}",
            f"- 按状态事后最佳只比 2C 多 `{summary['decision']['regime_fullsample_delta_vs_2c_pct_points']:.2f}` 个百分点。",
            f"- 只用过去同状态选择比 2C 少 `{abs(summary['decision']['regime_past_only_delta_vs_2c_pct_points']):.2f}` 个百分点。",
            "- 如果连 oracle 上限都只是小幅改善，真实实时状态识别更不该急着做复杂路由。",
            "- 这里排除了 `2026-06` 未完整月份，只看完整月。",
        ]
    )
    return "\n".join(lines) + "\n"


def _self_check(monthly: pd.DataFrame) -> None:
    assert set(monthly["candidate"]) == set(CANDIDATES)
    assert monthly["complete_month"].all()
    assert "2026-06" not in set(monthly["month"])
    assert monthly.groupby("month")["candidate"].nunique().min() == len(CANDIDATES)


def _return_pct(log_return: float) -> float:
    return (math.exp(log_return) - 1.0) * 100.0


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return _json_ready(frame.to_dict("records"))


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
