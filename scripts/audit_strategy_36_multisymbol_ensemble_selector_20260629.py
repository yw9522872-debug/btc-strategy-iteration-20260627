from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "artifacts" / "strategy_33_multisymbol_free_futures_strict_selector_20260629"
OUT_DIR = ROOT / "artifacts" / "strategy_36_multisymbol_ensemble_selector_20260629"

EVAL_START_MONTH = "2023-01"
YEAR_TARGET_PCT = 100.0
MIN_MONTH_ORDERS = 10


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    monthly = pd.read_csv(SOURCE_DIR / "candidate_monthly.csv")
    scores, best_monthly = _run_grid(monthly)
    summary = _summary(scores, best_monthly)

    files = {
        "summary": OUT_DIR / "summary.json",
        "report": OUT_DIR / "report.md",
        "config_scores": OUT_DIR / "config_scores.csv",
        "best_monthly": OUT_DIR / "best_monthly.csv",
    }
    files["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    files["report"].write_text(_report(summary), encoding="utf-8")
    scores.to_csv(files["config_scores"], index=False, encoding="utf-8-sig")
    best_monthly.to_csv(files["best_monthly"], index=False, encoding="utf-8-sig")

    _self_check(summary, files)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "strategy_id": summary["strategy_id"],
                "strict_pass_count": summary["strict_pass_count"],
                "verdict": summary["decision"]["verdict"],
                "report": str(files["report"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _run_grid(monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly = monthly.copy()
    monthly["candidate_id"] = monthly["candidate_id"].astype(str)
    monthly["month"] = monthly["month"].astype(str)

    months = sorted(monthly["month"].unique().tolist())
    candidate_ids = sorted(monthly["candidate_id"].unique().tolist())
    eval_indices = [idx for idx, month in enumerate(months) if month >= EVAL_START_MONTH]

    ret = (
        monthly.pivot(index="candidate_id", columns="month", values="log_return")
        .reindex(index=candidate_ids, columns=months)
        .fillna(0.0)
        .to_numpy(float)
    )
    orders = (
        monthly.pivot(index="candidate_id", columns="month", values="orders")
        .reindex(index=candidate_ids, columns=months)
        .fillna(0.0)
        .to_numpy(float)
    )

    configs = [
        (k, lookback, min_pos_rate, score_mode)
        for k in (3, 5, 10, 20, 50)
        for lookback in (12, 24, 36, 0)
        for min_pos_rate in (0.45, 0.50, 0.55)
        for score_mode in ("mean", "mean_minus_std", "pos_mean")
    ]

    score_rows: list[dict[str, Any]] = []
    all_month_rows: list[dict[str, Any]] = []

    for config_id, (top_k, lookback_months, min_pos_rate, score_mode) in enumerate(configs):
        month_rows = []
        for month_idx in eval_indices:
            month = months[month_idx]
            start_idx = 0 if lookback_months == 0 else max(0, month_idx - lookback_months)
            hist = ret[:, start_idx:month_idx]
            selected = _select_candidates(hist, top_k, min_pos_rate, score_mode)
            if len(selected):
                log_return = _equal_weight_log_return(ret[selected, month_idx])
                order_count = int(orders[selected, month_idx].sum())
            else:
                log_return = 0.0
                order_count = 0

            month_rows.append(
                {
                    "config_id": config_id,
                    "month": month,
                    "log_return": float(log_return),
                    "return_pct": _log_to_pct(log_return),
                    "orders": order_count,
                    "selected_count": int(len(selected)),
                    "selected_candidate_ids": ";".join(candidate_ids[i] for i in selected[:20]),
                }
            )

        score = _score_months(pd.DataFrame(month_rows), config_id, top_k, lookback_months, min_pos_rate, score_mode)
        score_rows.append(score)
        all_month_rows.extend(month_rows)

    scores = pd.DataFrame(score_rows).sort_values(
        ["hard_pass", "min_target_year_return_pct", "return_2025_pct", "return_2026_ytd_pct", "non_positive_months"],
        ascending=[False, False, False, False, True],
    )
    best_config = int(scores.iloc[0]["config_id"])
    best_monthly = pd.DataFrame(all_month_rows)
    best_monthly = best_monthly.loc[best_monthly["config_id"] == best_config].reset_index(drop=True)
    return scores.reset_index(drop=True), best_monthly


def _select_candidates(hist: np.ndarray, top_k: int, min_pos_rate: float, score_mode: str) -> np.ndarray:
    if hist.shape[1] < 12:
        return np.array([], dtype=int)
    mean = hist.mean(axis=1)
    std = hist.std(axis=1)
    pos_rate = (hist > 0.0).mean(axis=1)
    if score_mode == "mean":
        score = mean
    elif score_mode == "mean_minus_std":
        score = mean - std
    elif score_mode == "pos_mean":
        score = mean + pos_rate
    else:
        raise ValueError(f"Unknown score_mode: {score_mode}")
    ok = np.where(pos_rate >= min_pos_rate)[0]
    if len(ok) == 0:
        return np.array([], dtype=int)
    ranked = ok[np.argsort(score[ok])[-top_k:]][::-1]
    return ranked


def _equal_weight_log_return(log_returns: np.ndarray) -> float:
    simple_returns = np.expm1(np.clip(np.asarray(log_returns, dtype=float), -50.0, 50.0))
    portfolio_simple = float(simple_returns.mean()) if len(simple_returns) else 0.0
    if portfolio_simple <= -1.0:
        return -50.0
    return float(math.log1p(portfolio_simple))


def _score_months(
    month_rows: pd.DataFrame,
    config_id: int,
    top_k: int,
    lookback_months: int,
    min_pos_rate: float,
    score_mode: str,
) -> dict[str, Any]:
    frame = month_rows.copy()
    frame["year"] = frame["month"].str[:4]
    yearly = frame.groupby("year")["log_return"].sum()
    return_2023 = _log_to_pct(float(yearly.get("2023", 0.0)))
    return_2024 = _log_to_pct(float(yearly.get("2024", 0.0)))
    return_2025 = _log_to_pct(float(yearly.get("2025", 0.0)))
    return_2026 = _log_to_pct(float(yearly.get("2026", 0.0)))
    non_positive = int((frame["log_return"] <= 0.0).sum())
    min_orders = int(frame["orders"].min()) if len(frame) else 0
    min_target_year = min(return_2025, return_2026)
    hard_pass = bool(
        return_2025 > YEAR_TARGET_PCT
        and return_2026 > YEAR_TARGET_PCT
        and non_positive == 0
        and min_orders >= MIN_MONTH_ORDERS
    )
    return {
        "config_id": int(config_id),
        "top_k": int(top_k),
        "lookback_months": int(lookback_months),
        "min_pos_rate": float(min_pos_rate),
        "score_mode": score_mode,
        "return_2023_pct": return_2023,
        "return_2024_pct": return_2024,
        "return_2025_pct": return_2025,
        "return_2026_ytd_pct": return_2026,
        "min_target_year_return_pct": min_target_year,
        "total_eval_return_pct": _log_to_pct(float(frame["log_return"].sum())),
        "non_positive_months": non_positive,
        "min_monthly_orders": min_orders,
        "months": int(len(frame)),
        "hard_pass": hard_pass,
    }


def _summary(scores: pd.DataFrame, best_monthly: pd.DataFrame) -> dict[str, Any]:
    best = scores.iloc[0].to_dict()
    return {
        "status": "strategy_36_multisymbol_ensemble_selector_ready",
        "strategy_id": "strategy_36_multisymbol_ensemble_selector_20260629",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "does_not_overwrite_existing_strategies": True,
        "source_strategy_id": "strategy_33_multisymbol_free_futures_strict_selector_20260629",
        "purpose": "借旧BTC 3m项目的多规则组合思路，先用33号已有候选做便宜的严格组合选择器检查，不新增规则和数据。",
        "method": {
            "candidate_source": "strategy_33 candidate_monthly.csv",
            "new_market_data_downloaded": False,
            "new_trade_rules_added": False,
            "eval_start_month": EVAL_START_MONTH,
            "selection_rule": "每个月只用该月之前的候选月度收益，按历史均值/均值减波动/正月率加均值排序，选top-k等权组合。",
            "portfolio_accounting_note": "这是月度候选收益层面的等权组合近似，不是逐K持仓重放；用途是快速筛掉不稳定选择方法。",
            "config_count": int(len(scores)),
        },
        "strict_pass_count": int(scores["hard_pass"].astype(bool).sum()),
        "best_config": {
            key: _json_ready(value)
            for key, value in best.items()
        },
        "best_monthly": {
            "non_positive_months": best_monthly.loc[best_monthly["log_return"] <= 0.0, "month"].tolist(),
            "min_monthly_orders": int(best_monthly["orders"].min()) if len(best_monthly) else 0,
            "months": int(len(best_monthly)),
        },
        "decision": {
            "verdict": "ENSEMBLE_SELECTOR_ON_33_CANDIDATES_FAILS",
            "promote_strategy": False,
            "reason": "只把33号候选做严格多规则组合，仍然没有任何配置通过；组合思路不能直接修复当前免费15m候选池。",
            "next_step": "如果继续追旧项目灵感，应另开更重的3m/多周期事件池数据审计；不要在33号候选上继续调组合参数。",
        },
    }


def _report(summary: dict[str, Any]) -> str:
    best = summary["best_config"]
    lines = [
        "# Strategy 36 Multisymbol Ensemble Selector 20260629",
        "",
        "## Plain Conclusion",
        "",
        "- 这一步只做研究，不碰实盘、不读密钥、不下单。",
        "- 它不新增交易规则、不下载新数据，只复用33号候选月度结果。",
        "- 目的：先用很便宜的方法测试“多规则组合”能不能救回33号选择器。",
        f"- 测试配置数：`{summary['method']['config_count']}`。",
        f"- 严格通过配置数：`{summary['strict_pass_count']}`。",
        f"- 最好配置：top_k `{best['top_k']}`，lookback `{best['lookback_months']}`，min_pos_rate `{best['min_pos_rate']}`，score `{best['score_mode']}`。",
        f"- 最好配置收益：2023 `{best['return_2023_pct']:.2f}%`，2024 `{best['return_2024_pct']:.2f}%`，2025 `{best['return_2025_pct']:.2f}%`，2026 YTD `{best['return_2026_ytd_pct']:.2f}%`。",
        f"- 最好配置仍有 `{best['non_positive_months']}` 个不盈利月份，最小月交易 `{best['min_monthly_orders']}`。",
        "- 结论：组合33号已有候选不能直接解决问题；如果继续旧项目灵感，应进入真正的3m/多周期事件池，而不是继续调33号组合参数。",
        "",
        "## Decision",
        "",
        f"- Verdict: `{summary['decision']['verdict']}`",
        f"- Promote strategy: `{summary['decision']['promote_strategy']}`",
        f"- Reason: {summary['decision']['reason']}",
        f"- Next step: {summary['decision']['next_step']}",
    ]
    return "\n".join(lines) + "\n"


def _log_to_pct(log_return: float) -> float:
    return float(math.expm1(log_return) * 100.0)


def _json_ready(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def _self_check(summary: dict[str, Any], files: dict[str, Path]) -> None:
    for path in files.values():
        if not path.exists() or path.stat().st_size <= 0:
            raise AssertionError(f"Output missing or empty: {path}")
    if summary["strict_pass_count"] != 0:
        raise AssertionError("Expected this cheap ensemble selector to fail")
    if summary["decision"]["promote_strategy"]:
        raise AssertionError("This audit must not promote a strategy")
    if summary["orders_generated"] or summary["orders_submitted"] or summary["secret_access"]:
        raise AssertionError("Safety flags are wrong")


if __name__ == "__main__":
    main()
