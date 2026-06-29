from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ID = "strategy_34_multisymbol_failure_root_cause_20260629"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
SOURCE_ID = "strategy_33_multisymbol_free_futures_strict_selector_20260629"
SOURCE_DIR = ROOT / "artifacts" / SOURCE_ID

EVAL_START_MONTH = "2023-01"
EVAL_END_EXCLUSIVE = "2026-06"
TRAIN_START_MONTH = "2020-01"
REQUIRED_RETURN_PCT = 100.0
REQUIRED_MIN_MONTHLY_ORDERS = 10
ORACLE_ID = "monthly_oracle_best_return_order10"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_summary = json.loads((SOURCE_DIR / "summary.json").read_text(encoding="utf-8"))
    best_selector_id = source_summary["best_selector"]["selector_id"]
    candidate_monthly = pd.read_csv(SOURCE_DIR / "candidate_monthly.csv")
    selected_params = pd.read_csv(SOURCE_DIR / "selected_params.csv")
    selector_monthly = pd.read_csv(SOURCE_DIR / "selector_monthly.csv")
    oracle_monthly = pd.read_csv(SOURCE_DIR / "oracle_monthly.csv")

    eval_candidates = _eval_months(candidate_monthly)
    selected = selector_monthly.loc[selector_monthly["selector_id"] == best_selector_id].copy()
    params = selected_params.loc[selected_params["selector_id"] == best_selector_id].copy()
    oracle = oracle_monthly.loc[oracle_monthly["oracle_id"] == ORACLE_ID].copy()

    opportunity = _opportunity_by_month(eval_candidates)
    ranks = _oracle_training_ranks(candidate_monthly, oracle)
    month_root = _month_root_cause(selected, params, oracle, opportunity, ranks)
    prev_oracle = _previous_oracle_follow(eval_candidates, oracle)
    persistence_summary = _summary_from_monthly(prev_oracle)

    month_root.to_csv(OUT_DIR / "month_root_cause.csv", index=False)
    opportunity.to_csv(OUT_DIR / "opportunity_by_month.csv", index=False)
    ranks.to_csv(OUT_DIR / "oracle_training_ranks.csv", index=False)
    prev_oracle.to_csv(OUT_DIR / "previous_oracle_follow_monthly.csv", index=False)

    failure_months = month_root.loc[~month_root["selected_month_hard_ok"]].copy()
    failure_months.to_csv(OUT_DIR / "failure_months.csv", index=False)

    summary = {
        "status": "strategy_34_multisymbol_failure_root_cause_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "source_strategy_id": SOURCE_ID,
        "purpose": "Diagnose why Strategy 33's multi-symbol strict selector fails despite a strong leaky monthly oracle.",
        "source_best_selector_id": best_selector_id,
        "evaluation": {
            "train_start_month": TRAIN_START_MONTH,
            "eval_start_month": EVAL_START_MONTH,
            "eval_end_exclusive": EVAL_END_EXCLUSIVE,
            "required_min_monthly_orders": REQUIRED_MIN_MONTHLY_ORDERS,
            "required_2025_2026_ytd_return_pct": REQUIRED_RETURN_PCT,
        },
        "headline": _headline(month_root, ranks, prev_oracle),
        "strict_selector_summary": _summary_from_monthly(selected),
        "oracle_order10_summary": _summary_from_monthly(oracle),
        "previous_oracle_follow_summary": persistence_summary,
        "root_cause_counts": _value_counts(month_root["root_cause"]),
        "nonpassing_root_cause_counts": _value_counts(failure_months["root_cause"]),
        "selection_gap": {
            "months": int(len(month_root)),
            "selected_equals_oracle_months": int(month_root["selected_equals_oracle"].sum()),
            "same_symbol_as_oracle_months": int(month_root["same_symbol_as_oracle"].sum()),
            "median_oracle_hard_rank_before_month": float(ranks["oracle_hard_guard_rank"].median()),
            "oracle_top10_hard_rank_months": int((ranks["oracle_hard_guard_rank"] <= 10).sum()),
            "oracle_top50_hard_rank_months": int((ranks["oracle_hard_guard_rank"] <= 50).sum()),
            "oracle_unique_candidates": int(oracle["candidate_id"].nunique()),
            "oracle_unique_symbols": int(month_root["oracle_symbol"].nunique()),
            "oracle_unique_rules": int(month_root["oracle_rule"].nunique()),
        },
        "fee_vs_market_loss": _fee_vs_market_loss(month_root),
        "decision": _decision(month_root, ranks, prev_oracle),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "source_summary_sha256": _sha256(SOURCE_DIR / "summary.json"),
            "source_candidate_monthly_sha256": _sha256(SOURCE_DIR / "candidate_monthly.csv"),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "month_root_cause": _rel(OUT_DIR / "month_root_cause.csv"),
            "failure_months": _rel(OUT_DIR / "failure_months.csv"),
            "opportunity_by_month": _rel(OUT_DIR / "opportunity_by_month.csv"),
            "oracle_training_ranks": _rel(OUT_DIR / "oracle_training_ranks.csv"),
            "previous_oracle_follow_monthly": _rel(OUT_DIR / "previous_oracle_follow_monthly.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _eval_months(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[(frame["month"] >= EVAL_START_MONTH) & (frame["month"] < EVAL_END_EXCLUSIVE)].copy()


def _opportunity_by_month(candidate_monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for month, group in candidate_monthly.groupby("month", sort=True):
        order10 = group.loc[group["orders"] >= REQUIRED_MIN_MONTHLY_ORDERS]
        positive = group.loc[group["return_pct"] > 0]
        positive_order10 = order10.loc[order10["return_pct"] > 0]
        best = group.sort_values(["return_pct", "orders"], ascending=[False, False]).iloc[0]
        best_order10 = order10.sort_values(["return_pct", "orders"], ascending=[False, False]).iloc[0]
        rows.append(
            {
                "month": month,
                "candidate_count": int(len(group)),
                "positive_candidate_count": int(len(positive)),
                "order10_candidate_count": int(len(order10)),
                "positive_order10_candidate_count": int(len(positive_order10)),
                "best_candidate_id": best["candidate_id"],
                "best_return_pct": float(best["return_pct"]),
                "best_orders": int(best["orders"]),
                "best_order10_candidate_id": best_order10["candidate_id"],
                "best_order10_return_pct": float(best_order10["return_pct"]),
                "best_order10_orders": int(best_order10["orders"]),
                "median_order10_return_pct": float(order10["return_pct"].median()),
                "p90_order10_return_pct": float(order10["return_pct"].quantile(0.9)),
            }
        )
    return pd.DataFrame(rows)


def _month_root_cause(
    selected: pd.DataFrame,
    selected_params: pd.DataFrame,
    oracle: pd.DataFrame,
    opportunity: pd.DataFrame,
    ranks: pd.DataFrame,
) -> pd.DataFrame:
    selected = selected.rename(
        columns={
            "return_pct": "selected_return_pct",
            "orders": "selected_orders",
            "log_return": "selected_log_return",
            "cost_log": "selected_cost_log",
            "turnover": "selected_turnover",
            "max_drawdown_pct": "selected_max_drawdown_pct",
        }
    )
    params = selected_params.rename(
        columns={
            "eval_month": "month",
            "candidate_id": "selected_candidate_id",
            "family": "selected_family",
            "rule": "selected_rule",
            "leverage": "selected_leverage",
        }
    )
    oracle = oracle.rename(
        columns={
            "candidate_id": "oracle_candidate_id",
            "family": "oracle_family",
            "rule": "oracle_rule",
            "leverage": "oracle_leverage",
            "return_pct": "oracle_return_pct",
            "orders": "oracle_orders",
            "log_return": "oracle_log_return",
            "cost_log": "oracle_cost_log",
            "turnover": "oracle_turnover",
            "max_drawdown_pct": "oracle_max_drawdown_pct",
        }
    )
    keep_selected = [
        "month",
        "selected_return_pct",
        "selected_orders",
        "selected_log_return",
        "selected_cost_log",
        "selected_turnover",
        "selected_max_drawdown_pct",
    ]
    keep_params = [
        "month",
        "selected_candidate_id",
        "selected_family",
        "selected_rule",
        "selected_leverage",
        "train_hard_ok_candidate_count",
        "train_min10_orders_candidate_count",
        "train_return_pct",
        "train_losing_months",
        "train_min_monthly_return_pct",
        "train_min_monthly_orders",
        "train_turnover",
    ]
    keep_oracle = [
        "month",
        "oracle_candidate_id",
        "oracle_family",
        "oracle_rule",
        "oracle_leverage",
        "oracle_return_pct",
        "oracle_orders",
        "oracle_log_return",
        "oracle_cost_log",
        "oracle_turnover",
        "oracle_max_drawdown_pct",
    ]
    out = selected[keep_selected].merge(params[keep_params], on="month", how="left")
    out = out.merge(oracle[keep_oracle], on="month", how="left")
    out = out.merge(opportunity, on="month", how="left")
    out = out.merge(ranks.drop(columns=["oracle_candidate_id"], errors="ignore"), on="month", how="left")

    selected_meta = out["selected_candidate_id"].map(_parse_candidate)
    oracle_meta = out["oracle_candidate_id"].map(_parse_candidate)
    out["selected_symbol"] = selected_meta.map(lambda x: x["symbol"])
    out["selected_lookback"] = selected_meta.map(lambda x: x["lookback"])
    out["selected_threshold_bps"] = selected_meta.map(lambda x: x["threshold_bps"])
    out["oracle_symbol"] = oracle_meta.map(lambda x: x["symbol"])
    out["oracle_lookback"] = oracle_meta.map(lambda x: x["lookback"])
    out["oracle_threshold_bps"] = oracle_meta.map(lambda x: x["threshold_bps"])

    out["selected_gross_log_return"] = out["selected_log_return"] + out["selected_cost_log"]
    out["selected_gross_return_pct"] = (np.exp(out["selected_gross_log_return"]) - 1.0) * 100.0
    out["selected_month_hard_ok"] = (out["selected_return_pct"] > 0) & (out["selected_orders"] >= REQUIRED_MIN_MONTHLY_ORDERS)
    out["selected_equals_oracle"] = out["selected_candidate_id"] == out["oracle_candidate_id"]
    out["same_symbol_as_oracle"] = out["selected_symbol"].fillna("") == out["oracle_symbol"].fillna("")
    out["oracle_log_gap_vs_selected"] = out["oracle_log_return"] - out["selected_log_return"]
    out["root_cause"] = out.apply(_classify_month, axis=1)
    return out.sort_values("month")


def _classify_month(row: pd.Series) -> str:
    if int(row["positive_order10_candidate_count"]) == 0:
        return "NO_ORDER10_POSITIVE_OPPORTUNITY"
    if bool(row["selected_month_hard_ok"]):
        return "STRICT_MONTH_OK_BUT_BEHIND_ORACLE"
    if row["selected_return_pct"] <= 0 and row["selected_orders"] < REQUIRED_MIN_MONTHLY_ORDERS:
        return "WRONG_CANDIDATE_AND_TOO_FEW_TRADES"
    if row["selected_orders"] < REQUIRED_MIN_MONTHLY_ORDERS:
        return "TOO_FEW_TRADES"
    if row["selected_gross_log_return"] > 0:
        return "FEES_TURNED_GROSS_WIN_TO_NET_LOSS"
    return "WRONG_CANDIDATE_MARKET_LOSS"


def _oracle_training_ranks(candidate_monthly: pd.DataFrame, oracle: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for month in sorted(oracle["month"].unique()):
        train = candidate_monthly.loc[(candidate_monthly["month"] >= TRAIN_START_MONTH) & (candidate_monthly["month"] < month)]
        score = (
            train.groupby("candidate_id", as_index=False)
            .agg(
                family=("family", "first"),
                rule=("rule", "first"),
                leverage=("leverage", "first"),
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
                "candidate_id",
            ],
            ascending=[False, True, False, False, False, True, True, True],
        ).reset_index(drop=True)
        return_ranked = score.sort_values(
            ["train_return_pct", "train_losing_months", "train_min_monthly_return_pct", "train_turnover", "leverage", "candidate_id"],
            ascending=[False, True, False, True, True, True],
        ).reset_index(drop=True)
        oracle_candidate = str(oracle.loc[oracle["month"] == month, "candidate_id"].iloc[0])
        hard_idx = hard_ranked.index[hard_ranked["candidate_id"] == oracle_candidate]
        return_idx = return_ranked.index[return_ranked["candidate_id"] == oracle_candidate]
        hard_row = hard_ranked.iloc[int(hard_idx[0])]
        rows.append(
            {
                "month": month,
                "oracle_candidate_id": oracle_candidate,
                "oracle_hard_guard_rank": int(hard_idx[0]) + 1,
                "oracle_return_first_rank": int(return_idx[0]) + 1,
                "oracle_train_return_pct": float(hard_row["train_return_pct"]),
                "oracle_train_losing_months": int(hard_row["train_losing_months"]),
                "oracle_train_min_monthly_return_pct": float(hard_row["train_min_monthly_return_pct"]),
                "oracle_train_min_monthly_orders": int(hard_row["train_min_monthly_orders"]),
                "oracle_train_hard_ok": bool(hard_row["train_hard_ok"]),
            }
        )
    return pd.DataFrame(rows)


def _previous_oracle_follow(candidate_monthly: pd.DataFrame, oracle: pd.DataFrame) -> pd.DataFrame:
    oracle_by_month = oracle.set_index("month")["candidate_id"].to_dict()
    months = sorted(oracle["month"].unique())
    rows: list[dict[str, Any]] = []
    for i, month in enumerate(months):
        if i == 0:
            rows.append(
                {
                    "month": month,
                    "candidate_id": "flat_no_previous_oracle",
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
                }
            )
            continue
        candidate_id = oracle_by_month[months[i - 1]]
        current = candidate_monthly.loc[(candidate_monthly["month"] == month) & (candidate_monthly["candidate_id"] == candidate_id)].iloc[0].to_dict()
        current["used_previous_oracle_month"] = months[i - 1]
        rows.append(current)
    return pd.DataFrame(rows)


def _summary_from_monthly(monthly: pd.DataFrame) -> dict[str, Any]:
    out = monthly.copy()
    out["year"] = out["month"].str[:4]
    yearly = out.groupby("year", as_index=False).agg(log_return=("log_return", "sum"))
    yearly["return_pct"] = (np.exp(yearly["log_return"]) - 1.0) * 100.0
    returns = {str(row.year): float(row.return_pct) for row in yearly.itertuples()}
    losing = int((out["return_pct"] <= 0).sum())
    min_orders = int(out["orders"].min())
    return {
        "return_2023_pct": returns.get("2023"),
        "return_2024_pct": returns.get("2024"),
        "return_2025_pct": returns.get("2025"),
        "return_2026_ytd_pct": returns.get("2026"),
        "total_return_pct": float((np.exp(float(out["log_return"].sum())) - 1.0) * 100.0),
        "losing_or_flat_months": losing,
        "hard_nonpassing_months": int(((out["return_pct"] <= 0) | (out["orders"] < REQUIRED_MIN_MONTHLY_ORDERS)).sum()),
        "min_monthly_return_pct": float(out["return_pct"].min()),
        "min_monthly_orders": min_orders,
        "orders": int(out["orders"].sum()),
        "turnover": float(out["turnover"].sum()),
        "cost_log": float(out["cost_log"].sum()),
        "worst_month_drawdown_pct": float(out["max_drawdown_pct"].min()),
    }


def _headline(month_root: pd.DataFrame, ranks: pd.DataFrame, prev_oracle: pd.DataFrame) -> dict[str, Any]:
    nonpassing = month_root.loc[~month_root["selected_month_hard_ok"]]
    prev_summary = _summary_from_monthly(prev_oracle)
    return {
        "eval_months": int(len(month_root)),
        "strict_nonpassing_months": int(len(nonpassing)),
        "months_with_order10_positive_candidate": int((month_root["positive_order10_candidate_count"] > 0).sum()),
        "months_with_no_train_hard_ok_candidates": int((month_root["train_hard_ok_candidate_count"] == 0).sum()),
        "oracle_hard_rank_median": float(ranks["oracle_hard_guard_rank"].median()),
        "oracle_hard_rank_top10_months": int((ranks["oracle_hard_guard_rank"] <= 10).sum()),
        "previous_oracle_follow_2025_pct": prev_summary["return_2025_pct"],
        "previous_oracle_follow_2026_ytd_pct": prev_summary["return_2026_ytd_pct"],
        "plain_chinese": "每个月几乎都有能赚钱的候选，但这些候选在月初之前通常排不靠前，上月赢家下月也不能稳定延续。",
    }


def _fee_vs_market_loss(month_root: pd.DataFrame) -> dict[str, Any]:
    losing = month_root.loc[month_root["selected_return_pct"] <= 0]
    return {
        "selected_net_losing_months": int(len(losing)),
        "fee_killed_months": int(((losing["selected_gross_log_return"] > 0) & (losing["selected_return_pct"] <= 0)).sum()),
        "market_direction_loss_months": int((losing["selected_gross_log_return"] <= 0).sum()),
        "too_few_trade_months": int((month_root["selected_orders"] < REQUIRED_MIN_MONTHLY_ORDERS).sum()),
    }


def _decision(month_root: pd.DataFrame, ranks: pd.DataFrame, prev_oracle: pd.DataFrame) -> dict[str, Any]:
    prev = _summary_from_monthly(prev_oracle)
    strict_nonpassing = int((~month_root["selected_month_hard_ok"]).sum())
    oracle_not_findable = int((ranks["oracle_hard_guard_rank"] > 50).sum())
    if strict_nonpassing and oracle_not_findable >= len(ranks) // 2 and (prev["return_2025_pct"] or 0) < REQUIRED_RETURN_PCT:
        verdict = "ROOT_CAUSE_UNSTABLE_HINDSIGHT_SELECTION"
        next_step = "不要先加交易规则；若继续，只能另起新编号测试真正不同的选择方法，并先做上限/泄漏审计。"
    else:
        verdict = "ROOT_CAUSE_MAY_BE_SELECTOR_FIXABLE"
        next_step = "可以另起新编号，只测试一个更严格的选择器，不新增交易规则。"
    return {
        "verdict": verdict,
        "promote_strategy": False,
        "reason": "失败主因不是没有赚钱片段，而是赚钱片段换得太快，过去表现很难提前选中当月赢家。",
        "next_step": next_step,
    }


def _parse_candidate(candidate_id: str) -> dict[str, Any]:
    symbol = None
    match = re.search(r"symbol([A-Z]+USDT)", str(candidate_id))
    if match:
        symbol = match.group(1)
    lookback = _regex_int(candidate_id, r"lookback(\d+)")
    threshold = _regex_int(candidate_id, r"threshold_bps(\d+)")
    return {"symbol": symbol, "lookback": lookback, "threshold_bps": threshold}


def _regex_int(text: str, pattern: str) -> int | None:
    match = re.search(pattern, str(text))
    return int(match.group(1)) if match else None


def _value_counts(series: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in series.value_counts().sort_index().items()}


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
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _render_report(summary: dict[str, Any]) -> str:
    h = summary["headline"]
    strict = summary["strict_selector_summary"]
    prev = summary["previous_oracle_follow_summary"]
    rank = summary["selection_gap"]
    decision = summary["decision"]
    loss = summary["fee_vs_market_loss"]
    return f"""# 34号多币种失败根因审计

这不是策略，不能交易。它只拆 33号为什么失败。

## 一句话结论

33号不是完全没有赚钱机会，而是当月开始前选不准。看答案能挑到好候选；只看过去数据时，好候选通常排不靠前，上月赢家下月也不稳定。

## 关键检查

- 评估月份：`{h["eval_months"]}`
- 严格选择器不达标月份：`{h["strict_nonpassing_months"]}`
- 有“每月10单且正收益”候选的月份：`{h["months_with_order10_positive_candidate"]}`
- 训练期没有硬通过候选的月份：`{h["months_with_no_train_hard_ok_candidates"]}`
- 当月 oracle 赢家在月初训练排序里的中位名次：`{h["oracle_hard_rank_median"]:.0f}`
- oracle 赢家月初排进前10的月份：`{h["oracle_hard_rank_top10_months"]}`

## 严格选择器

- 2023：`{strict["return_2023_pct"]:.2f}%`
- 2024：`{strict["return_2024_pct"]:.2f}%`
- 2025：`{strict["return_2025_pct"]:.2f}%`
- 2026 YTD：`{strict["return_2026_ytd_pct"]:.2f}%`
- 不达标月份：`{strict["hard_nonpassing_months"]}`

## 上月赢家跟随

如果每个月跟随上个月的 oracle 赢家：

- 2025：`{prev["return_2025_pct"]:.2f}%`
- 2026 YTD：`{prev["return_2026_ytd_pct"]:.2f}%`
- 不达标月份：`{prev["hard_nonpassing_months"]}`

## 亏损来源

- 严格选择器净亏损月份：`{loss["selected_net_losing_months"]}`
- 其中手续费把毛盈利打成净亏的月份：`{loss["fee_killed_months"]}`
- 行情方向本身亏的月份：`{loss["market_direction_loss_months"]}`
- 交易次数不足10次的月份：`{loss["too_few_trade_months"]}`

## 判断

`{decision["verdict"]}`

{decision["reason"]}

下一步：{decision["next_step"]}
"""


if __name__ == "__main__":
    main()
