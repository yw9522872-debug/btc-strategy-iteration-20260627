from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import audit_strategy_58_tail_event_micro_signal_20260630 as s58


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_59_tail_event_failure_attribution_20260630"
STRATEGY_ID = "strategy_59_tail_event_failure_attribution_20260630"
SOURCE_58 = ROOT / "artifacts" / "strategy_58_tail_event_micro_signal_20260630"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data, data_quality = s58._load_data()
    event = s58._event_mask(data)
    scan = pd.read_csv(SOURCE_58 / "action_policy_scan.csv")
    policies = _select_policies(scan)
    months = sorted(data[(data["month"] >= s58.EVAL_START) & (data["month"] < s58.EVAL_END_EXCLUSIVE)]["month"].unique())

    policy_rows = []
    monthly_rows = []
    trade_frames = []
    drawdown_frames = []
    worst_frames = []
    for name, policy in policies.items():
        labels = s58._oracle_event_labels(data, event, int(policy["confirm_bars"]))
        bar, trades, trained_months = s58._walkforward_action_policy(
            data,
            labels,
            months,
            s58._feature_names(str(policy["feature_set"])),
            int(policy["max_depth"]),
            int(policy["min_samples_leaf"]),
            int(policy["hold_bars"]),
            float(policy["leverage"]),
        )
        monthly = s58._monthly(bar)
        trades = _enrich_trades(data, trades)
        drawdown = _drawdown_window(bar, trades)
        concentration = _concentration(trades)
        policy_rows.append(
            {
                "policy_name": name,
                **{k: policy[k] for k in ["confirm_bars", "feature_set", "max_depth", "min_samples_leaf", "hold_bars", "leverage"]},
                "trained_months": trained_months,
                **s58._summary(monthly, int(len(trades)), float(monthly["turnover"].sum())),
                **concentration,
                **{f"drawdown_{k}": v for k, v in drawdown["summary"].items()},
            }
        )
        fail_months = _failure_months(monthly, trades)
        fail_months.insert(0, "policy_name", name)
        monthly_rows.append(fail_months)
        trades.insert(0, "policy_name", name)
        trade_frames.append(trades)
        dd_trades = drawdown["trades"]
        dd_trades.insert(0, "policy_name", name)
        drawdown_frames.append(dd_trades)
        worst_frames.append(trades.sort_values("trade_log_return").head(20))

    policy_summary = pd.DataFrame(policy_rows)
    failure_months = pd.concat(monthly_rows, ignore_index=True)
    trade_attribution = pd.concat(trade_frames, ignore_index=True)
    drawdown_trades = pd.concat(drawdown_frames, ignore_index=True)
    worst_trades = pd.concat(worst_frames, ignore_index=True)

    policy_summary.to_csv(OUT_DIR / "policy_failure_summary.csv", index=False)
    failure_months.to_csv(OUT_DIR / "failure_months.csv", index=False)
    trade_attribution.to_csv(OUT_DIR / "trade_attribution.csv", index=False)
    drawdown_trades.to_csv(OUT_DIR / "drawdown_window_trades.csv", index=False)
    worst_trades.to_csv(OUT_DIR / "worst_trades.csv", index=False)

    summary = {
        "status": "strategy_59_tail_event_failure_attribution_done",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "purpose": "Attribute Strategy 58 failures by month and event to test whether drawdown is concentrated in a few trades.",
        "data": data_quality,
        "source_strategy": "strategy_58_tail_event_micro_signal_20260630",
        "policy_summary": _json_ready(policy_summary.to_dict("records")),
        "decision": _decision(policy_summary),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "policy_failure_summary": _rel(OUT_DIR / "policy_failure_summary.csv"),
            "failure_months": _rel(OUT_DIR / "failure_months.csv"),
            "trade_attribution": _rel(OUT_DIR / "trade_attribution.csv"),
            "drawdown_window_trades": _rel(OUT_DIR / "drawdown_window_trades.csv"),
            "worst_trades": _rel(OUT_DIR / "worst_trades.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_report(summary, failure_months, worst_trades), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _select_policies(scan: pd.DataFrame) -> dict[str, dict[str, Any]]:
    best_return = scan.sort_values(["min_target_year_return_pct", "max_drawdown_pct"], ascending=[False, False]).iloc[0].to_dict()
    dd_ok = scan[scan["max_drawdown_pct"] >= -50.0]
    best_dd = dd_ok.sort_values(["min_target_year_return_pct", "max_drawdown_pct"], ascending=[False, False]).iloc[0].to_dict()
    return {"best_return_drawdown_fail": best_return, "best_dd_near_miss": best_dd}


def _enrich_trades(data: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades
    rows = []
    for row in trades.itertuples(index=False):
        start = int(row.decision_index) + 1
        end = min(len(data), start + int(row.hold_bars))
        stats = s58._trade_stats(data, start, int(row.hold_bars), float(row.btc_target), float(row.hype_target))
        out = row._asdict()
        out.update(
            {
                "start_index": start,
                "end_index": end,
                "start_timestamp": data["timestamp"].iloc[start] if start < len(data) else pd.NaT,
                "end_timestamp": data["timestamp"].iloc[end - 1] if end > start else pd.NaT,
                **stats,
                "oracle_match": str(row.predicted_action) == str(row.oracle_action),
            }
        )
        rows.append(out)
    enriched = pd.DataFrame(rows)
    enriched["cum_log_return"] = enriched["trade_log_return"].cumsum()
    enriched["cum_return_pct"] = (np.exp(enriched["cum_log_return"]) - 1.0) * 100.0
    return enriched


def _drawdown_window(bar: pd.DataFrame, trades: pd.DataFrame) -> dict[str, Any]:
    work = bar.copy()
    work["equity"] = np.exp(work["log_return"].cumsum())
    work["peak_equity"] = work["equity"].cummax()
    trough_i = int(work["drawdown_pct"].idxmin())
    peak_i = int(work.loc[:trough_i, "equity"].idxmax())
    peak_ts = work["timestamp"].iloc[peak_i]
    trough_ts = work["timestamp"].iloc[trough_i]
    in_window = trades[(pd.to_datetime(trades["start_timestamp"], utc=True) >= peak_ts) & (pd.to_datetime(trades["start_timestamp"], utc=True) <= trough_ts)].copy()
    neg_sum = float(in_window.loc[in_window["trade_log_return"] < 0, "trade_log_return"].sum())
    worst = in_window.sort_values("trade_log_return").head(3)
    summary = {
        "peak_timestamp": peak_ts,
        "trough_timestamp": trough_ts,
        "peak_to_trough_return_pct": float((work["equity"].iloc[trough_i] / work["equity"].iloc[peak_i] - 1.0) * 100.0),
        "trade_count": int(len(in_window)),
        "negative_trade_count": int((in_window["trade_log_return"] < 0).sum()),
        "negative_log_sum": neg_sum,
        "worst3_negative_share_pct": _share(float(worst.loc[worst["trade_log_return"] < 0, "trade_log_return"].sum()), neg_sum),
    }
    return {"summary": summary, "trades": in_window}


def _concentration(trades: pd.DataFrame) -> dict[str, float | int]:
    neg = trades[trades["trade_log_return"] < 0].sort_values("trade_log_return")
    neg_sum = float(neg["trade_log_return"].sum())
    return {
        "trade_count_total": int(len(trades)),
        "negative_trade_count_total": int(len(neg)),
        "negative_log_sum_total": neg_sum,
        "worst1_share_of_negative_pct": _share(float(neg.head(1)["trade_log_return"].sum()), neg_sum),
        "worst3_share_of_negative_pct": _share(float(neg.head(3)["trade_log_return"].sum()), neg_sum),
        "worst5_share_of_negative_pct": _share(float(neg.head(5)["trade_log_return"].sum()), neg_sum),
    }


def _failure_months(monthly: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    out = monthly.copy()
    counts = trades.groupby("month").agg(
        trade_count=("trade_log_return", "size"),
        negative_trade_count=("trade_log_return", lambda s: int((s < 0).sum())),
        worst_trade_log_return=("trade_log_return", "min"),
        worst_trade_return_pct=("trade_return_pct", "min"),
    )
    out = out.merge(counts, on="month", how="left").fillna(0)
    return out[(out["return_pct"] <= 0) | (out["max_drawdown_pct"] <= -50)].reset_index(drop=True)


def _share(part: float, total: float) -> float:
    if total == 0:
        return 0.0
    return float(abs(part) / abs(total) * 100.0)


def _decision(policy_summary: pd.DataFrame) -> dict[str, Any]:
    row = policy_summary[policy_summary["policy_name"] == "best_return_drawdown_fail"].iloc[0]
    concentrated = bool(row["drawdown_trade_count"] <= 5 or row["drawdown_worst3_negative_share_pct"] >= 70.0)
    if concentrated:
        verdict = "DRAWDOWN_CONCENTRATED_IN_FEW_EVENTS"
        reason = "58号最好收益配置的主回撤窗口由少数事件主导，下一步可以只测试极简因果风控。"
    else:
        verdict = "DRAWDOWN_SPREAD_ACROSS_MANY_EVENTS"
        reason = "58号最好收益配置的回撤不是单笔或少数几笔造成，简单删一两笔救不回来。"
    return {"verdict": verdict, "promote_strategy": False, "reason": reason}


def _report(summary: dict[str, Any], failure_months: pd.DataFrame, worst_trades: pd.DataFrame) -> str:
    policies = {row["policy_name"]: row for row in summary["policy_summary"]}
    best = policies["best_return_drawdown_fail"]
    near = policies["best_dd_near_miss"]
    worst_best = worst_trades[worst_trades["policy_name"] == "best_return_drawdown_fail"].head(5)
    fail_best = failure_months[failure_months["policy_name"] == "best_return_drawdown_fail"]
    lines = [
        "# Strategy 59：58号失败月份和失败事件归因",
        "",
        "- 这是研究审计，不是实盘策略。",
        "- 目标：看58号失败是不是集中在少数几笔事件。",
        "",
        "## 最好收益但回撤失败配置",
        "",
        f"- 2025: `{best['return_2025_pct']:.2f}%`",
        f"- 2026: `{best['return_2026_pct']:.2f}%`",
        f"- 最大回撤: `{best['max_drawdown_pct']:.2f}%`",
        f"- 主回撤窗口交易数: `{best['drawdown_trade_count']}`",
        f"- 主回撤窗口负交易数: `{best['drawdown_negative_trade_count']}`",
        f"- 主回撤窗口最差3笔占窗口亏损: `{best['drawdown_worst3_negative_share_pct']:.2f}%`",
        f"- 全样本最差3笔占总负交易亏损: `{best['worst3_share_of_negative_pct']:.2f}%`",
        "",
        "## 低回撤近似配置",
        "",
        f"- 2025: `{near['return_2025_pct']:.2f}%`",
        f"- 2026: `{near['return_2026_pct']:.2f}%`",
        f"- 最大回撤: `{near['max_drawdown_pct']:.2f}%`",
        f"- 主回撤窗口交易数: `{near['drawdown_trade_count']}`",
        f"- 全样本最差3笔占总负交易亏损: `{near['worst3_share_of_negative_pct']:.2f}%`",
        "",
        "## 最好收益配置失败月份",
        "",
        _markdown_table(fail_best[["month", "return_pct", "max_drawdown_pct", "trade_count", "negative_trade_count", "worst_trade_return_pct"]]),
        "",
        "## 最差5笔事件",
        "",
        _markdown_table(worst_best[["month", "decision_timestamp", "predicted_action", "oracle_action", "trade_return_pct", "oracle_match"]]),
        "",
        "## 结论",
        "",
        f"- `{summary['decision']['verdict']}`",
        f"- {summary['decision']['reason']}",
    ]
    return "\n".join(lines) + "\n"


def _markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_无_"
    work = df.copy()
    for col in work.columns:
        if pd.api.types.is_float_dtype(work[col]):
            work[col] = work[col].map(lambda x: f"{x:.2f}")
    header = "| " + " | ".join(work.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(work.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in work.to_numpy()]
    return "\n".join([header, sep, *rows])


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return value


if __name__ == "__main__":
    main()
