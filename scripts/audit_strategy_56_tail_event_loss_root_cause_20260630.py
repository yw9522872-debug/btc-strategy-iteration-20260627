from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_56_tail_event_loss_root_cause_20260630"
SRC55 = ROOT / "artifacts" / "strategy_55_btc_hype_tail_event_core_signal_20260630"
STRATEGY_ID = "strategy_56_tail_event_loss_root_cause_20260630"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    monthly = pd.read_csv(SRC55 / "candidate_monthly.csv")
    scan = pd.read_csv(SRC55 / "candidate_scan.csv")
    oracle = pd.read_csv(SRC55 / "monthly_oracle_drawdown_capped.csv")
    strict = pd.read_csv(SRC55 / "strict_selector_monthly.csv")

    oracle_vs_strict = _oracle_vs_strict(oracle, strict)
    train_rank = _oracle_train_rank(monthly, oracle)
    previous_oracle = _previous_oracle_follow(monthly, oracle)
    action_summary = _action_summary(monthly, scan, oracle, strict)
    candidate_persistence = _candidate_persistence(monthly, oracle)

    oracle_vs_strict.to_csv(OUT_DIR / "oracle_vs_strict_by_month.csv", index=False)
    train_rank.to_csv(OUT_DIR / "oracle_train_rank_by_month.csv", index=False)
    previous_oracle.to_csv(OUT_DIR / "follow_previous_oracle_by_month.csv", index=False)
    action_summary.to_csv(OUT_DIR / "action_summary.csv", index=False)
    candidate_persistence.to_csv(OUT_DIR / "oracle_candidate_persistence.csv", index=False)

    summary = {
        "status": "strategy_56_tail_event_loss_root_cause_done",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "source": {
            "strategy_55_dir": _rel(SRC55),
            "candidate_monthly": _rel(SRC55 / "candidate_monthly.csv"),
            "drawdown_capped_oracle": _rel(SRC55 / "monthly_oracle_drawdown_capped.csv"),
            "strict_selector": _rel(SRC55 / "strict_selector_monthly.csv"),
        },
        "root_cause": _root_cause(oracle_vs_strict, train_rank, previous_oracle, oracle, strict),
        "oracle_action_counts": _json_ready(oracle["action"].value_counts().to_dict()),
        "strict_action_counts": _json_ready(strict["action"].value_counts().to_dict()),
        "oracle_unique_candidate_count": int(oracle["candidate_id"].nunique()),
        "oracle_month_count": int(oracle["month"].nunique()),
        "strict_unique_candidate_count": int(strict["candidate_id"].nunique()),
        "strict_month_count": int(strict["month"].nunique()),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "oracle_vs_strict_by_month": _rel(OUT_DIR / "oracle_vs_strict_by_month.csv"),
            "oracle_train_rank_by_month": _rel(OUT_DIR / "oracle_train_rank_by_month.csv"),
            "follow_previous_oracle_by_month": _rel(OUT_DIR / "follow_previous_oracle_by_month.csv"),
            "action_summary": _rel(OUT_DIR / "action_summary.csv"),
            "oracle_candidate_persistence": _rel(OUT_DIR / "oracle_candidate_persistence.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _oracle_vs_strict(oracle: pd.DataFrame, strict: pd.DataFrame) -> pd.DataFrame:
    o = oracle.add_prefix("oracle_").rename(columns={"oracle_month": "month"})
    s = strict.add_prefix("strict_").rename(columns={"strict_month": "month"})
    out = o.merge(s, on="month", how="left")
    out["return_gap_pct"] = out["oracle_return_pct"] - out["strict_return_pct"]
    out["same_candidate"] = out["oracle_candidate_id"] == out["strict_candidate_id"]
    out["same_action"] = out["oracle_action"] == out["strict_action"]
    out["same_event_set"] = out["oracle_event_set"] == out["strict_event_set"]
    out["strict_missed_positive_oracle"] = (out["oracle_return_pct"] > 0) & (out["strict_return_pct"] <= 0)
    return out


def _oracle_train_rank(monthly: pd.DataFrame, oracle: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in oracle.itertuples(index=False):
        train = monthly[monthly["month"] < row.month]
        if train.empty:
            continue
        score = train.groupby("candidate_id", as_index=False).agg(
            train_log_return=("log_return", "sum"),
            train_max_drawdown_pct=("max_drawdown_pct", "min"),
            train_losing_months=("return_pct", lambda value: int((value <= 0).sum())),
            train_months=("month", "nunique"),
        )
        score = score.sort_values(["train_max_drawdown_pct", "train_log_return"], ascending=[False, False]).reset_index(drop=True)
        score["train_rank"] = np.arange(1, len(score) + 1)
        picked = score[score["candidate_id"] == row.candidate_id]
        if picked.empty:
            continue
        item = picked.iloc[0].to_dict()
        rows.append(
            {
                "month": row.month,
                "oracle_candidate_id": row.candidate_id,
                "oracle_action": row.action,
                "oracle_return_pct": row.return_pct,
                **item,
            }
        )
    return pd.DataFrame(rows)


def _previous_oracle_follow(monthly: pd.DataFrame, oracle: pd.DataFrame) -> pd.DataFrame:
    oracle = oracle.sort_values("month").reset_index(drop=True)
    rows = []
    for index in range(1, len(oracle)):
        prev = oracle.iloc[index - 1]
        current = oracle.iloc[index]
        candidate_row = monthly[(monthly["month"] == current["month"]) & (monthly["candidate_id"] == prev["candidate_id"])]
        if candidate_row.empty:
            continue
        item = candidate_row.iloc[0]
        rows.append(
            {
                "month": current["month"],
                "previous_oracle_candidate_id": prev["candidate_id"],
                "previous_oracle_action": prev["action"],
                "current_oracle_candidate_id": current["candidate_id"],
                "current_oracle_action": current["action"],
                "follow_previous_return_pct": item["return_pct"],
                "current_oracle_return_pct": current["return_pct"],
                "return_gap_pct": current["return_pct"] - item["return_pct"],
                "same_as_current_oracle": prev["candidate_id"] == current["candidate_id"],
            }
        )
    return pd.DataFrame(rows)


def _action_summary(monthly: pd.DataFrame, scan: pd.DataFrame, oracle: pd.DataFrame, strict: pd.DataFrame) -> pd.DataFrame:
    eval_monthly = monthly.copy()
    static = scan.groupby("action", as_index=False).agg(
        best_static_2025_pct=("return_2025_pct", "max"),
        best_static_2026_pct=("return_2026_pct", "max"),
        best_static_max_drawdown_pct=("max_drawdown_pct", "max"),
        candidate_count=("candidate_id", "nunique"),
    )
    month_stats = eval_monthly.groupby("action", as_index=False).agg(
        avg_monthly_return_pct=("return_pct", "mean"),
        positive_month_share=("return_pct", lambda value: float((value > 0).mean())),
        avg_drawdown_pct=("max_drawdown_pct", "mean"),
    )
    oracle_counts = oracle["action"].value_counts().rename_axis("action").reset_index(name="oracle_months")
    strict_counts = strict["action"].value_counts().rename_axis("action").reset_index(name="strict_months")
    return static.merge(month_stats, on="action", how="outer").merge(oracle_counts, on="action", how="outer").merge(strict_counts, on="action", how="outer").fillna(0)


def _candidate_persistence(monthly: pd.DataFrame, oracle: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for candidate_id, group in oracle.groupby("candidate_id"):
        months = sorted(group["month"].tolist())
        all_rows = monthly[monthly["candidate_id"] == candidate_id]
        rows.append(
            {
                "candidate_id": candidate_id,
                "oracle_months": len(months),
                "oracle_month_list": ",".join(months),
                "all_month_return_sum_pct_approx": float(all_rows["return_pct"].sum()),
                "positive_month_share_all": float((all_rows["return_pct"] > 0).mean()),
                "worst_month_pct_all": float(all_rows["return_pct"].min()),
                "best_month_pct_all": float(all_rows["return_pct"].max()),
            }
        )
    return pd.DataFrame(rows).sort_values(["oracle_months", "positive_month_share_all"], ascending=[False, False])


def _root_cause(
    oracle_vs_strict: pd.DataFrame,
    train_rank: pd.DataFrame,
    previous_oracle: pd.DataFrame,
    oracle: pd.DataFrame,
    strict: pd.DataFrame,
) -> dict[str, Any]:
    action_switches = int((oracle["action"].shift(1) != oracle["action"]).iloc[1:].sum())
    median_rank = float(train_rank["train_rank"].median()) if not train_rank.empty else None
    top10 = int((train_rank["train_rank"] <= 10).sum()) if not train_rank.empty else 0
    follow_positive = int((previous_oracle["follow_previous_return_pct"] > 0).sum()) if not previous_oracle.empty else 0
    follow_months = int(len(previous_oracle))
    return {
        "verdict": "LOSS_ROOT_CAUSE_UNSTABLE_ACTION_SELECTION",
        "plain_chinese": "亏损根因不是事件不存在，而是事件后的正确动作每月切换太快；过去表现很难提前告诉我们该顺势还是反转。严格选择器为了控制回撤，长期偏向低杠杆BTC动作，结果错过HYPE大机会，收益被磨成小亏。",
        "oracle_action_switches": action_switches,
        "oracle_unique_candidates": int(oracle["candidate_id"].nunique()),
        "oracle_months": int(oracle["month"].nunique()),
        "strict_same_candidate_months": int(oracle_vs_strict["same_candidate"].sum()),
        "strict_same_action_months": int(oracle_vs_strict["same_action"].sum()),
        "strict_missed_positive_oracle_months": int(oracle_vs_strict["strict_missed_positive_oracle"].sum()),
        "oracle_train_rank_median": median_rank,
        "oracle_train_rank_top10_months": top10,
        "oracle_train_rank_months": int(len(train_rank)),
        "follow_previous_oracle_positive_months": follow_positive,
        "follow_previous_oracle_months": follow_months,
        "follow_previous_oracle_return_sum_pct_approx": float(previous_oracle["follow_previous_return_pct"].sum()) if follow_months else None,
        "current_oracle_return_sum_pct_approx": float(previous_oracle["current_oracle_return_pct"].sum()) if follow_months else None,
        "strict_action_counts": strict["action"].value_counts().to_dict(),
        "oracle_action_counts": oracle["action"].value_counts().to_dict(),
    }


def _render_report(summary: dict[str, Any]) -> str:
    rc = summary["root_cause"]
    return "\n".join(
        [
            "# Strategy 56：尾部事件亏损根因审计",
            "",
            "- 这是亏损归因，不是策略。",
            "- 复用55号结果，不新增候选、不调参数。",
            "",
            "## 根因结论",
            "",
            f"- `{rc['verdict']}`",
            f"- {rc['plain_chinese']}",
            "",
            "## 关键证据",
            "",
            f"- oracle 月份数：`{rc['oracle_months']}`",
            f"- oracle 不同候选数：`{rc['oracle_unique_candidates']}`",
            f"- oracle 动作切换次数：`{rc['oracle_action_switches']}`",
            f"- 严格选择器选中同一个候选的月份：`{rc['strict_same_candidate_months']}`",
            f"- 严格选择器选中同一种动作的月份：`{rc['strict_same_action_months']}`",
            f"- 严格选择器错过正收益oracle的月份：`{rc['strict_missed_positive_oracle_months']}`",
            f"- oracle赢家在训练期排序中位名次：`{rc['oracle_train_rank_median']}`",
            f"- oracle赢家训练期排前10的月份：`{rc['oracle_train_rank_top10_months']}/{rc['oracle_train_rank_months']}`",
            f"- 跟随上月oracle赢家为正的月份：`{rc['follow_previous_oracle_positive_months']}/{rc['follow_previous_oracle_months']}`",
            f"- 跟随上月oracle赢家收益简单求和：`{rc['follow_previous_oracle_return_sum_pct_approx']:.2f}%`",
            f"- 当月oracle收益简单求和：`{rc['current_oracle_return_sum_pct_approx']:.2f}%`",
            "",
            "## 文件",
            "",
            f"- oracle_vs_strict_by_month: `{summary['files']['oracle_vs_strict_by_month']}`",
            f"- oracle_train_rank_by_month: `{summary['files']['oracle_train_rank_by_month']}`",
            f"- follow_previous_oracle_by_month: `{summary['files']['follow_previous_oracle_by_month']}`",
            f"- action_summary: `{summary['files']['action_summary']}`",
        ]
    ) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
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
