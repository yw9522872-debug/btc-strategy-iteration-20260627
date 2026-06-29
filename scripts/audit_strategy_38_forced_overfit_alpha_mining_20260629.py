from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ID = "strategy_38_forced_overfit_alpha_mining_20260629"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID

SOURCE_SPECS = [
    {
        "source_id": "strategy_33",
        "source_name": "33号多币种15m免费期货候选池",
        "dir": ROOT / "artifacts" / "strategy_33_multisymbol_free_futures_strict_selector_20260629",
    },
    {
        "source_id": "strategy_37",
        "source_name": "37号BTC 3m多周期事件池",
        "dir": ROOT / "artifacts" / "strategy_37_btc_3m_multitimeframe_event_pool_20260629",
    },
]

TRAIN_START_MONTH = "2020-01"
EVAL_START_MONTH = "2023-01"
EVAL_END_EXCLUSIVE = "2026-06"
REQUIRED_RETURN_PCT = 100.0
REQUIRED_MIN_MONTHLY_ORDERS = 10

SUMMARY_COLUMNS = {
    "hard_pass_original_2025_2026_ytd",
    "hard_pass_complete_years",
    "non_positive_months",
    "total_eval_return_pct",
    "return_2023_pct",
    "return_2024_pct",
    "return_2025_pct",
    "return_2026_ytd_pct",
    "min_complete_year_return_pct",
    "min_target_year_return_pct",
    "losing_eval_months",
    "min_monthly_return_pct",
    "min_monthly_orders",
    "orders",
    "turnover",
    "cost_log",
    "worst_selected_month_drawdown_pct",
    "selected_candidate_count",
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_monthly, source_meta, source_summaries = _load_sources()
    eval_monthly = _eval_months(all_monthly)

    combined_oracle = _select_oracle(eval_monthly, "combined_order10_oracle", None)
    source_oracles = pd.concat(
        [_select_oracle(eval_monthly, f"{spec['source_id']}_order10_oracle", spec["source_id"]) for spec in SOURCE_SPECS],
        ignore_index=True,
    )
    all_oracle_monthly = pd.concat([combined_oracle, source_oracles], ignore_index=True)
    ranks = _oracle_training_ranks(all_monthly, combined_oracle)
    previous_follow = _previous_winner_follow(eval_monthly, combined_oracle)
    pattern_summary = _pattern_summary(combined_oracle)
    source_oracle_summary = _source_oracle_summary(source_oracles)

    combined_oracle.to_csv(OUT_DIR / "combined_oracle_monthly.csv", index=False)
    source_oracles.to_csv(OUT_DIR / "source_oracle_monthly.csv", index=False)
    all_oracle_monthly.to_csv(OUT_DIR / "all_oracle_monthly.csv", index=False)
    ranks.to_csv(OUT_DIR / "oracle_training_ranks.csv", index=False)
    previous_follow.to_csv(OUT_DIR / "previous_winner_follow_monthly.csv", index=False)
    pattern_summary.to_csv(OUT_DIR / "winner_pattern_summary.csv", index=False)
    source_oracle_summary.to_csv(OUT_DIR / "source_oracle_summary.csv", index=False)
    source_meta.to_csv(OUT_DIR / "source_candidate_pool_overview.csv", index=False)

    combined_summary = _summary_from_monthly(combined_oracle)
    previous_summary = _summary_from_monthly(previous_follow)
    summary = {
        "status": "strategy_38_forced_overfit_alpha_mining_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Deliberately use leaky monthly winners from Strategy 33 and Strategy 37 to mine alpha clues, then test whether the winners are stable enough to become non-leaky rules.",
        "method": {
            "forced_overfit": True,
            "tradeable": False,
            "new_market_data_downloaded": False,
            "new_trade_rules_added": False,
            "selection_rule": "For each evaluated month, choose the candidate with the best same-month return among candidates with at least 10 orders.",
            "warning": "This sees the month before choosing. It is only for clue mining, never for promotion.",
        },
        "sources": source_summaries,
        "evaluation": {
            "train_start_month": TRAIN_START_MONTH,
            "eval_start_month": EVAL_START_MONTH,
            "eval_end_exclusive": EVAL_END_EXCLUSIVE,
            "required_min_monthly_orders": REQUIRED_MIN_MONTHLY_ORDERS,
            "required_2025_2026_ytd_return_pct": REQUIRED_RETURN_PCT,
        },
        "combined_oracle_summary": combined_summary,
        "source_oracle_summary": _json_ready(source_oracle_summary.to_dict("records")),
        "winner_stability": _winner_stability(combined_oracle),
        "winner_pattern_top10": _json_ready(pattern_summary.head(10).to_dict("records")),
        "training_rank_diagnostics": {
            "months": int(len(ranks)),
            "median_hard_guard_rank": float(ranks["hard_guard_rank"].median()),
            "top10_hard_guard_months": int((ranks["hard_guard_rank"] <= 10).sum()),
            "top50_hard_guard_months": int((ranks["hard_guard_rank"] <= 50).sum()),
            "median_return_first_rank": float(ranks["return_first_rank"].median()),
            "top10_return_first_months": int((ranks["return_first_rank"] <= 10).sum()),
            "train_hard_ok_months": int(ranks["train_hard_ok"].sum()),
        },
        "previous_winner_follow_summary": previous_summary,
        "alpha_clues": _alpha_clues(combined_oracle, pattern_summary, ranks, previous_summary, source_oracle_summary),
        "decision": _decision(combined_summary, ranks, previous_summary),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "source_33_candidate_monthly_sha256": _sha256(SOURCE_SPECS[0]["dir"] / "candidate_monthly.csv"),
            "source_37_candidate_monthly_sha256": _sha256(SOURCE_SPECS[1]["dir"] / "candidate_monthly.csv"),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "combined_oracle_monthly": _rel(OUT_DIR / "combined_oracle_monthly.csv"),
            "source_oracle_monthly": _rel(OUT_DIR / "source_oracle_monthly.csv"),
            "all_oracle_monthly": _rel(OUT_DIR / "all_oracle_monthly.csv"),
            "oracle_training_ranks": _rel(OUT_DIR / "oracle_training_ranks.csv"),
            "previous_winner_follow_monthly": _rel(OUT_DIR / "previous_winner_follow_monthly.csv"),
            "winner_pattern_summary": _rel(OUT_DIR / "winner_pattern_summary.csv"),
            "source_oracle_summary": _rel(OUT_DIR / "source_oracle_summary.csv"),
            "source_candidate_pool_overview": _rel(OUT_DIR / "source_candidate_pool_overview.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    _self_check(summary)
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_sources() -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    monthly_frames: list[pd.DataFrame] = []
    meta_frames: list[pd.DataFrame] = []
    source_summaries: list[dict[str, Any]] = []
    for spec in SOURCE_SPECS:
        source_dir = spec["dir"]
        monthly = pd.read_csv(source_dir / "candidate_monthly.csv")
        scan = pd.read_csv(source_dir / "candidate_scan.csv")
        summary = json.loads((source_dir / "summary.json").read_text(encoding="utf-8"))

        for frame in [monthly, scan]:
            frame["source_id"] = spec["source_id"]
            frame["source_name"] = spec["source_name"]
            frame["global_candidate_id"] = frame["source_id"].astype(str) + "::" + frame["candidate_id"].astype(str)

        meta_cols = [col for col in scan.columns if col not in SUMMARY_COLUMNS]
        monthly = monthly.merge(scan[meta_cols], on=["source_id", "source_name", "global_candidate_id", "candidate_id", "family", "rule", "leverage"], how="left")
        monthly_frames.append(monthly)
        meta_frames.append(scan[meta_cols].drop_duplicates("global_candidate_id"))
        source_summaries.append(
            {
                "source_id": spec["source_id"],
                "source_name": spec["source_name"],
                "source_strategy_id": summary["strategy_id"],
                "candidate_count": int(summary["candidate_grid"]["candidate_count"]),
                "source_decision": summary["decision"]["verdict"],
            }
        )
    return pd.concat(monthly_frames, ignore_index=True), pd.concat(meta_frames, ignore_index=True), source_summaries


def _eval_months(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[(frame["month"] >= EVAL_START_MONTH) & (frame["month"] < EVAL_END_EXCLUSIVE)].copy()


def _select_oracle(monthly: pd.DataFrame, oracle_id: str, source_id: str | None) -> pd.DataFrame:
    subset = monthly.copy()
    if source_id is not None:
        subset = subset.loc[subset["source_id"] == source_id].copy()
    rows: list[dict[str, Any]] = []
    for month, group in subset.groupby("month", sort=True):
        pool = group.loc[group["orders"] >= REQUIRED_MIN_MONTHLY_ORDERS].copy()
        no_order_floor_candidate = pool.empty
        if pool.empty:
            pool = group.copy()
        best = pool.sort_values(["return_pct", "orders", "turnover"], ascending=[False, False, True]).iloc[0].to_dict()
        best["oracle_id"] = oracle_id
        best["no_order_floor_candidate"] = bool(no_order_floor_candidate)
        rows.append(best)
    return pd.DataFrame(rows)


def _oracle_training_ranks(all_monthly: pd.DataFrame, oracle: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for month in sorted(oracle["month"].unique()):
        train = all_monthly.loc[(all_monthly["month"] >= TRAIN_START_MONTH) & (all_monthly["month"] < month)]
        score = (
            train.groupby("global_candidate_id", as_index=False)
            .agg(
                source_id=("source_id", "first"),
                source_name=("source_name", "first"),
                candidate_id=("candidate_id", "first"),
                family=("family", "first"),
                rule=("rule", "first"),
                leverage=("leverage", "first"),
                symbol=("symbol", "first"),
                train_months=("month", "count"),
                train_log_return=("log_return", "sum"),
                train_losing_months=("return_pct", lambda values: int((values <= 0).sum())),
                train_min_monthly_return_pct=("return_pct", "min"),
                train_min_monthly_orders=("orders", "min"),
                train_turnover=("turnover", "sum"),
            )
        )
        score["train_return_pct"] = (np.exp(score["train_log_return"]) - 1.0) * 100.0
        score["train_hard_ok"] = (
            (score["train_return_pct"] > REQUIRED_RETURN_PCT)
            & (score["train_losing_months"] == 0)
            & (score["train_min_monthly_orders"] >= REQUIRED_MIN_MONTHLY_ORDERS)
        )
        hard_ranked = score.sort_values(
            [
                "train_hard_ok",
                "train_losing_months",
                "train_min_monthly_return_pct",
                "train_return_pct",
                "train_min_monthly_orders",
                "train_turnover",
                "leverage",
                "global_candidate_id",
            ],
            ascending=[False, True, False, False, False, True, True, True],
        ).reset_index(drop=True)
        return_ranked = score.sort_values(
            ["train_return_pct", "train_losing_months", "train_min_monthly_return_pct", "train_turnover", "leverage", "global_candidate_id"],
            ascending=[False, True, False, True, True, True],
        ).reset_index(drop=True)
        winner_id = str(oracle.loc[oracle["month"] == month, "global_candidate_id"].iloc[0])
        hard_idx = int(hard_ranked.index[hard_ranked["global_candidate_id"] == winner_id][0])
        return_idx = int(return_ranked.index[return_ranked["global_candidate_id"] == winner_id][0])
        winner_score = hard_ranked.iloc[hard_idx]
        rows.append(
            {
                "month": month,
                "global_candidate_id": winner_id,
                "hard_guard_rank": hard_idx + 1,
                "return_first_rank": return_idx + 1,
                "train_return_pct": float(winner_score["train_return_pct"]),
                "train_losing_months": int(winner_score["train_losing_months"]),
                "train_min_monthly_return_pct": float(winner_score["train_min_monthly_return_pct"]),
                "train_min_monthly_orders": int(winner_score["train_min_monthly_orders"]),
                "train_hard_ok": bool(winner_score["train_hard_ok"]),
            }
        )
    return pd.DataFrame(rows)


def _previous_winner_follow(eval_monthly: pd.DataFrame, oracle: pd.DataFrame) -> pd.DataFrame:
    oracle_by_month = oracle.set_index("month")["global_candidate_id"].to_dict()
    months = sorted(oracle["month"].unique())
    rows: list[dict[str, Any]] = []
    for index, month in enumerate(months):
        if index == 0:
            rows.append(
                {
                    "month": month,
                    "global_candidate_id": "flat_no_previous_winner",
                    "candidate_id": "flat_no_previous_winner",
                    "source_id": "flat",
                    "source_name": "flat",
                    "family": "flat",
                    "rule": "flat",
                    "leverage": 0.0,
                    "log_return": 0.0,
                    "cost_log": 0.0,
                    "turnover": 0.0,
                    "orders": 0,
                    "exposure_pct": 0.0,
                    "max_drawdown_pct": 0.0,
                    "return_pct": 0.0,
                    "used_previous_winner_month": None,
                }
            )
            continue
        previous_month = months[index - 1]
        candidate_id = oracle_by_month[previous_month]
        row = eval_monthly.loc[(eval_monthly["month"] == month) & (eval_monthly["global_candidate_id"] == candidate_id)].iloc[0].to_dict()
        row["used_previous_winner_month"] = previous_month
        rows.append(row)
    return pd.DataFrame(rows)


def _pattern_summary(oracle: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["source_id", "source_name", "family", "rule", "symbol", "leverage"]
    frame = oracle.copy()
    frame["symbol"] = frame["symbol"].fillna("")
    out = (
        frame.groupby(group_cols, dropna=False)
        .agg(
            months=("month", "count"),
            total_log_return=("log_return", "sum"),
            mean_return_pct=("return_pct", "mean"),
            min_return_pct=("return_pct", "min"),
            max_return_pct=("return_pct", "max"),
            total_orders=("orders", "sum"),
            candidate_count=("global_candidate_id", "nunique"),
        )
        .reset_index()
    )
    out["total_return_pct"] = (np.exp(out["total_log_return"]) - 1.0) * 100.0
    return out.sort_values(["months", "total_log_return", "mean_return_pct"], ascending=[False, False, False])


def _source_oracle_summary(source_oracles: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for oracle_id, group in source_oracles.groupby("oracle_id", sort=True):
        summary = _summary_from_monthly(group)
        rows.append(
            {
                "oracle_id": oracle_id,
                "source_id": str(group["source_id"].iloc[0]),
                "source_name": str(group["source_name"].iloc[0]),
                **summary,
            }
        )
    return pd.DataFrame(rows).sort_values(["hard_pass_original_2025_2026_ytd", "min_target_year_return_pct"], ascending=[False, False])


def _summary_from_monthly(monthly: pd.DataFrame) -> dict[str, Any]:
    out = monthly.copy()
    out["year"] = out["month"].str[:4]
    yearly = out.groupby("year", as_index=False).agg(log_return=("log_return", "sum"))
    yearly["return_pct"] = (np.exp(yearly["log_return"]) - 1.0) * 100.0
    returns = {str(row.year): float(row.return_pct) for row in yearly.itertuples()}
    losing_months = int((out["return_pct"] <= 0).sum())
    min_orders = int(out["orders"].min()) if len(out) else 0
    return_2025 = returns.get("2025")
    return_2026 = returns.get("2026")
    hard = bool(
        return_2025 is not None
        and return_2026 is not None
        and return_2025 > REQUIRED_RETURN_PCT
        and return_2026 > REQUIRED_RETURN_PCT
        and losing_months == 0
        and min_orders >= REQUIRED_MIN_MONTHLY_ORDERS
    )
    target_returns = [value for value in [return_2025, return_2026] if value is not None]
    return {
        "hard_pass_original_2025_2026_ytd": hard,
        "return_2023_pct": returns.get("2023"),
        "return_2024_pct": returns.get("2024"),
        "return_2025_pct": return_2025,
        "return_2026_ytd_pct": return_2026,
        "min_target_year_return_pct": min(target_returns) if target_returns else None,
        "total_eval_return_pct": float((np.exp(float(out["log_return"].sum())) - 1.0) * 100.0),
        "non_positive_months": out.loc[out["return_pct"] <= 0, "month"].tolist(),
        "losing_eval_months": losing_months,
        "min_monthly_return_pct": float(out["return_pct"].min()) if len(out) else None,
        "min_monthly_orders": min_orders,
        "orders": int(out["orders"].sum()) if len(out) else 0,
        "turnover": float(out["turnover"].sum()) if "turnover" in out.columns else None,
        "cost_log": float(out["cost_log"].sum()) if "cost_log" in out.columns else None,
        "selected_candidate_count": int(out["global_candidate_id"].nunique()) if "global_candidate_id" in out.columns else None,
    }


def _winner_stability(oracle: pd.DataFrame) -> dict[str, Any]:
    winners = oracle["global_candidate_id"].astype(str)
    same_as_prev = winners.eq(winners.shift(1)).fillna(False)
    source = oracle["source_id"].astype(str)
    family = oracle["family"].astype(str)
    rule = oracle["rule"].astype(str)
    return {
        "months": int(len(oracle)),
        "unique_winner_candidates": int(winners.nunique()),
        "max_repeat_count_for_one_candidate": int(winners.value_counts().max()),
        "same_candidate_as_previous_months": int(same_as_prev.sum()),
        "unique_sources": int(source.nunique()),
        "dominant_source": source.value_counts().idxmax(),
        "dominant_source_months": int(source.value_counts().max()),
        "dominant_family": family.value_counts().idxmax(),
        "dominant_family_months": int(family.value_counts().max()),
        "dominant_rule": rule.value_counts().idxmax(),
        "dominant_rule_months": int(rule.value_counts().max()),
    }


def _alpha_clues(
    combined_oracle: pd.DataFrame,
    pattern_summary: pd.DataFrame,
    ranks: pd.DataFrame,
    previous_summary: dict[str, Any],
    source_oracle_summary: pd.DataFrame,
) -> list[str]:
    clues: list[str] = []
    top = pattern_summary.iloc[0].to_dict()
    clues.append(
        f"最常出现的赢家结构是 {top['source_id']} / {top['family']} / {top['rule']} / {top.get('symbol') or 'no_symbol'}，出现 {int(top['months'])} 个月。"
    )
    source_counts = combined_oracle["source_id"].value_counts()
    clues.append(f"合并看答案赢家主要来自 {source_counts.idxmax()}，出现 {int(source_counts.max())}/{len(combined_oracle)} 个月。")
    if int((ranks["hard_guard_rank"] <= 10).sum()) == 0:
        clues.append("当月赢家在月初训练排序里从未进前10，说明这个alpha线索现在还不能直接变成严格选择器。")
    if (previous_summary.get("return_2025_pct") or 0) < 0 and (previous_summary.get("return_2026_ytd_pct") or 0) < 0:
        clues.append("跟随上月赢家在2025和2026都亏，说明赢家切换太快，不能简单追上月。")
    passed_sources = source_oracle_summary.loc[source_oracle_summary["hard_pass_original_2025_2026_ytd"].astype(bool), "source_id"].tolist()
    if passed_sources:
        clues.append(f"单独来源里只有 {', '.join(passed_sources)} 的看答案oracle通过硬目标；它值得拿来找特征，但不能交易。")
    else:
        clues.append("单独来源的看答案oracle都没硬通过，说明当前候选池本身仍不足。")
    return clues


def _decision(combined_summary: dict[str, Any], ranks: pd.DataFrame, previous_summary: dict[str, Any]) -> dict[str, Any]:
    if not combined_summary["hard_pass_original_2025_2026_ytd"]:
        return {
            "verdict": "FORCED_OVERFIT_ALPHA_POOL_STILL_FAILS",
            "promote_strategy": False,
            "reason": "把33号和37号放在一起看答案，仍过不了硬目标，说明候选池本身还不够。",
            "next_step": "停止这批候选池，换真正不同的数据源或降低目标。",
        }
    top10 = int((ranks["hard_guard_rank"] <= 10).sum())
    prev_2025 = previous_summary.get("return_2025_pct") or 0.0
    prev_2026 = previous_summary.get("return_2026_ytd_pct") or 0.0
    if top10 == 0 and (prev_2025 < 0 or prev_2026 < 0):
        return {
            "verdict": "FORCED_OVERFIT_ALPHA_CLUES_NOT_YET_TRADEABLE",
            "promote_strategy": False,
            "reason": "强行过拟合能找到赚钱片段，但月初无法提前识别；上月赢家也不能稳定延续。",
            "next_step": "可以只保留赢家结构做灵感，不要升级策略；下一步若继续，应设计能提前识别这些结构的独立选择器。",
        }
    return {
        "verdict": "FORCED_OVERFIT_ALPHA_CLUES_MAY_BE_SELECTOR_TESTABLE",
        "promote_strategy": False,
        "reason": "强行过拟合有赢家结构，而且部分赢家能被训练排序提前靠前识别。",
        "next_step": "另起39号，只测试一个严格不看未来的选择器，不新增交易规则。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    combo = summary["combined_oracle_summary"]
    rank = summary["training_rank_diagnostics"]
    prev = summary["previous_winner_follow_summary"]
    stability = summary["winner_stability"]
    decision = summary["decision"]
    clues = "\n".join(f"- {line}" for line in summary["alpha_clues"])
    source_lines = "\n".join(
        f"- `{row['source_id']}`：2025 `{row['return_2025_pct']:.2f}%`，2026 YTD `{row['return_2026_ytd_pct']:.2f}%`，不盈利月 `{row['losing_eval_months']}`，硬通过 `{row['hard_pass_original_2025_2026_ytd']}`"
        for row in summary["source_oracle_summary"]
    )
    return f"""# 38号强行过拟合 Alpha 挖掘审计

这不是策略，不能交易。它故意“看答案”，目的是找线索。

## 做法

- 复用 33号多币种15m候选池和37号 BTC 3m事件池。
- 不下载新数据，不新增交易规则。
- 每个月从所有候选里，强行挑当月收益最高、且当月至少10单的候选。
- 然后检查这些赢家有没有共同点，以及月初能不能提前排到前面。

## 合并看答案结果

- 2023：`{combo["return_2023_pct"]:.2f}%`
- 2024：`{combo["return_2024_pct"]:.2f}%`
- 2025：`{combo["return_2025_pct"]:.2f}%`
- 2026 YTD：`{combo["return_2026_ytd_pct"]:.2f}%`
- 不盈利月份：`{combo["losing_eval_months"]}`
- 最差月：`{combo["min_monthly_return_pct"]:.2f}%`
- 最少月交易：`{combo["min_monthly_orders"]}`

## 分来源看答案

{source_lines}

## 赢家稳定性

- 评估月份：`{stability["months"]}`
- 不同赢家候选数：`{stability["unique_winner_candidates"]}`
- 单个候选最多重复次数：`{stability["max_repeat_count_for_one_candidate"]}`
- 和上月同一个赢家的月份数：`{stability["same_candidate_as_previous_months"]}`
- 主来源：`{stability["dominant_source"]}`，出现 `{stability["dominant_source_months"]}` 个月
- 主家族：`{stability["dominant_family"]}`，出现 `{stability["dominant_family_months"]}` 个月
- 主规则：`{stability["dominant_rule"]}`，出现 `{stability["dominant_rule_months"]}` 个月

## 月初能否提前识别

- 当月赢家训练期排序中位名次：`{rank["median_hard_guard_rank"]:.0f}`
- 排进前10的月份：`{rank["top10_hard_guard_months"]}`
- 排进前50的月份：`{rank["top50_hard_guard_months"]}`
- 训练期已经硬通过的月份：`{rank["train_hard_ok_months"]}`

## 跟随上月赢家

- 2025：`{prev["return_2025_pct"]:.2f}%`
- 2026 YTD：`{prev["return_2026_ytd_pct"]:.2f}%`
- 不达标月份：`{prev["losing_eval_months"]}`

## Alpha 线索

{clues}

## 判断

`{decision["verdict"]}`

{decision["reason"]}

下一步：{decision["next_step"]}
"""


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
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


def _self_check(summary: dict[str, Any]) -> None:
    if summary["orders_generated"] or summary["orders_submitted"] or summary["secret_access"]:
        raise AssertionError("Safety flags are wrong.")
    if summary["decision"]["promote_strategy"]:
        raise AssertionError("This audit must not promote a strategy.")
    for path in summary["files"].values():
        full_path = ROOT / path
        if not full_path.exists() or full_path.stat().st_size <= 0:
            raise AssertionError(f"Missing output file: {full_path}")


if __name__ == "__main__":
    main()
