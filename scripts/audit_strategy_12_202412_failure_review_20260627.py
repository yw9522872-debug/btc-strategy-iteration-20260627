from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import audit_strategy_11_true_2024_walkforward_20260627 as audit11
import search_monthly_profit_lock_20260627 as lock_search
import search_online_expert_pool_20260627 as source_pool


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_12_202412_failure_review_20260627"
EQUITY_11 = ROOT / "artifacts" / "strategy_11_true_2024_walkforward_20260627" / "fixed_ret_state_64_100_equity.csv"
MONTHLY_11 = ROOT / "artifacts" / "strategy_11_true_2024_walkforward_20260627" / "fixed_ret_state_64_100_monthly.csv"
SELECTIONS_11 = ROOT / "artifacts" / "strategy_11_true_2024_walkforward_20260627" / "fixed_ret_state_64_100_selections.csv"
FEATURE_2024 = ROOT / "artifacts" / "event_entry_fullscan" / "event_entry_best_signals.csv"
REVIEW_MONTH = "2024-12"
STRATEGY_ID = "strategy_12_202412_failure_review_20260627"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    equity = _load_equity()
    features = _load_features()
    frame = equity.merge(features, on="timestamp", how="left")
    dec = frame.loc[frame["month"] == REVIEW_MONTH].copy()
    selected = pd.read_csv(SELECTIONS_11).loc[lambda df: df["eval_month"] == REVIEW_MONTH].iloc[0].to_dict()

    month_decomposition = _month_decomposition(equity)
    order_events = _order_events(dec)
    worst_bars = _worst_bars(dec)
    phase_breakdown = _phase_breakdown(dec)
    param_sweep = _december_param_sweep(selected)

    month_decomposition.to_csv(OUT_DIR / "month_decomposition.csv", index=False)
    order_events.to_csv(OUT_DIR / "december_order_events.csv", index=False)
    worst_bars.to_csv(OUT_DIR / "december_worst_bars.csv", index=False)
    phase_breakdown.to_csv(OUT_DIR / "december_phase_breakdown.csv", index=False)
    param_sweep.to_csv(OUT_DIR / "december_param_sweep.csv", index=False)

    dec_summary = month_decomposition.loc[month_decomposition["month"] == REVIEW_MONTH].iloc[0].to_dict()
    through_quota = phase_breakdown.loc[phase_breakdown["phase"] == "through_10th_order"].iloc[0].to_dict()
    after_quota = phase_breakdown.loc[phase_breakdown["phase"] == "after_10th_order"].iloc[0].to_dict()
    summary = {
        "status": "strategy_12_202412_failure_review_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "review_month": REVIEW_MONTH,
        "source": "Strategy 11 fixed_ret_state_64_100 true 2024 walk-forward result.",
        "selected_params_for_2024_12": lock_search._json_ready(selected),
        "december_summary": lock_search._json_ready(dec_summary),
        "through_10th_order": lock_search._json_ready(through_quota),
        "after_10th_order": lock_search._json_ready(after_quota),
        "param_sweep_summary": _param_sweep_summary(param_sweep),
        "decision": {
            "promote_strategy": False,
            "add_new_rule_now": False,
            "reason": "这是样本外失败复盘。单月亏损不能直接拿来补规则，否则很容易继续过拟合。",
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "month_decomposition": _rel(OUT_DIR / "month_decomposition.csv"),
            "december_order_events": _rel(OUT_DIR / "december_order_events.csv"),
            "december_worst_bars": _rel(OUT_DIR / "december_worst_bars.csv"),
            "december_phase_breakdown": _rel(OUT_DIR / "december_phase_breakdown.csv"),
            "december_param_sweep": _rel(OUT_DIR / "december_param_sweep.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _load_equity() -> pd.DataFrame:
    equity = pd.read_csv(EQUITY_11)
    equity["timestamp"] = pd.to_datetime(equity["timestamp"], utc=True)
    equity = equity.sort_values("timestamp").reset_index(drop=True)
    equity["month"] = equity["timestamp"].dt.strftime("%Y-%m")
    equity["raw_return"] = np.log(equity["close"].astype(float)).diff().fillna(0.0)
    equity["gross_log_return"] = equity["active_position"].astype(float) * equity["raw_return"]
    equity["cost_log"] = equity["turnover"].astype(float) * lock_search.COST_PER_SIDE
    equity["cum_month_log"] = equity.groupby("month")["strategy_log_return"].cumsum()
    equity["cum_month_orders"] = equity.groupby("month")["order_count"].cumsum()
    return equity


def _load_features() -> pd.DataFrame:
    columns = ["timestamp", "close", "trend_close_ema_gap_bps_60", "trend_adx_30", "trend_donchian_pos_30", "rsi14"]
    features = pd.read_csv(FEATURE_2024, usecols=columns)
    features["timestamp"] = pd.to_datetime(features["timestamp"], utc=True)
    features["ret_64_bps"] = features["close"].astype(float).pct_change(64) * 10_000.0
    return features[["timestamp", "ret_64_bps", "trend_close_ema_gap_bps_60", "trend_adx_30", "trend_donchian_pos_30", "rsi14"]]


def _month_decomposition(equity: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month, group in equity.groupby("month", sort=True):
        long_gross = group.loc[group["active_position"] > 0, "gross_log_return"].sum()
        short_gross = group.loc[group["active_position"] < 0, "gross_log_return"].sum()
        net_log = float(group["strategy_log_return"].sum())
        gross_log = float(group["gross_log_return"].sum())
        cost_log = float(group["cost_log"].sum())
        rows.append(
            {
                "month": month,
                "net_return_pct": float((np.exp(net_log) - 1.0) * 100.0),
                "gross_before_cost_return_pct": float((np.exp(gross_log) - 1.0) * 100.0),
                "cost_log_pct": cost_log * 100.0,
                "net_log": net_log,
                "gross_log": gross_log,
                "cost_log": cost_log,
                "turnover": float(group["turnover"].sum()),
                "orders": int(group["order_count"].sum()),
                "active_bars": int((group["active_position"].abs() > 0).sum()),
                "exposure_pct": float((group["active_position"].abs() > 0).mean() * 100.0),
                "avg_abs_active_position": float(group["active_position"].abs().mean()),
                "long_gross_log": float(long_gross),
                "short_gross_log": float(short_gross),
            }
        )
    return pd.DataFrame(rows)


def _order_events(dec: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "timestamp",
        "close",
        "active_position",
        "position",
        "turnover",
        "order_count",
        "cost_log",
        "strategy_log_return",
        "cum_month_log",
        "cum_month_orders",
        "ret_64_bps",
        "trend_close_ema_gap_bps_60",
        "trend_adx_30",
    ]
    return dec.loc[dec["turnover"] > 0, cols].copy()


def _worst_bars(dec: pd.DataFrame) -> pd.DataFrame:
    out = dec.loc[dec["active_position"].abs() > 0].nsmallest(30, "strategy_log_return").copy()
    out["raw_return_pct"] = (np.exp(out["raw_return"]) - 1.0) * 100.0
    out["gross_log_pct"] = out["gross_log_return"] * 100.0
    out["cost_log_pct"] = out["cost_log"] * 100.0
    cols = [
        "timestamp",
        "close",
        "active_position",
        "position",
        "raw_return_pct",
        "gross_log_pct",
        "cost_log_pct",
        "strategy_log_return",
        "cum_month_log",
        "cum_month_orders",
        "ret_64_bps",
        "trend_close_ema_gap_bps_60",
        "trend_adx_30",
    ]
    return out[cols]


def _phase_breakdown(dec: pd.DataFrame) -> pd.DataFrame:
    quota_rows = dec.index[dec["cum_month_orders"] >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS].tolist()
    split_index = quota_rows[0] if quota_rows else dec.index[-1]
    phases = {
        "all_month": dec,
        "through_10th_order": dec.loc[:split_index],
        "after_10th_order": dec.loc[split_index + 1 :],
    }
    rows = []
    for phase, group in phases.items():
        net_log = float(group["strategy_log_return"].sum())
        gross_log = float(group["gross_log_return"].sum())
        cost_log = float(group["cost_log"].sum())
        rows.append(
            {
                "phase": phase,
                "bars": int(len(group)),
                "net_return_pct": float((np.exp(net_log) - 1.0) * 100.0),
                "gross_before_cost_return_pct": float((np.exp(gross_log) - 1.0) * 100.0),
                "cost_log_pct": cost_log * 100.0,
                "turnover": float(group["turnover"].sum()),
                "orders": int(group["order_count"].sum()),
                "max_cum_month_log_pct": float(group["cum_month_log"].max() * 100.0) if len(group) else 0.0,
                "min_cum_month_log_pct": float(group["cum_month_log"].min() * 100.0) if len(group) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _december_param_sweep(selected: dict[str, Any]) -> pd.DataFrame:
    features = audit11._load_combined_features()
    market = source_pool._market(features)
    side = audit11._ret_state_side(features, audit11.FIXED_WINDOW, audit11.FIXED_THRESHOLD_BPS)
    rows = []
    for candidate in audit11._candidate_results(side, market, audit11._small_param_grid()):
        params = candidate["params"]
        score = audit11._score_before_month(candidate["monthly"], REVIEW_MONTH)
        dec = candidate["monthly"].loc[candidate["monthly"]["month"] == REVIEW_MONTH].iloc[0]
        selected_match = all(_same(params[key], selected[key]) for key in ["leverage", "lock_log", "quota_arm_log", "quota_leverage"])
        rows.append(
            {
                "selected_by_walkforward": bool(selected_match),
                "candidate_id": int(candidate["candidate_id"]),
                **params,
                "train_months": score["months"],
                "train_return_pct": score["return_pct"],
                "train_losing_months": score["losing_months"],
                "train_min_month_return_pct": score["min_month_return_pct"],
                "train_min_orders": score["min_orders"],
                "train_hard_ok": bool(
                    score["return_pct"] > lock_search.REQUIRED_RETURN_PCT
                    and score["losing_months"] == 0
                    and score["min_orders"] >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS
                ),
                "dec_return_pct": float(dec["return_pct"]),
                "dec_orders": int(dec["orders"]),
                "dec_turnover": float(dec["turnover"]),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["selected_by_walkforward", "train_hard_ok", "train_min_month_return_pct", "train_return_pct"],
        ascending=[False, False, False, False],
    )


def _param_sweep_summary(param_sweep: pd.DataFrame) -> dict[str, Any]:
    selected = param_sweep.loc[param_sweep["selected_by_walkforward"]].iloc[0]
    train_ok = param_sweep.loc[param_sweep["train_hard_ok"]]
    dec_positive = train_ok.loc[train_ok["dec_return_pct"] > 0]
    best_dec = param_sweep.sort_values("dec_return_pct", ascending=False).iloc[0]
    return lock_search._json_ready(
        {
            "candidate_count": int(len(param_sweep)),
            "train_hard_ok_count": int(len(train_ok)),
            "train_hard_ok_and_dec_positive_count": int(len(dec_positive)),
            "selected_dec_return_pct": float(selected["dec_return_pct"]),
            "best_dec_return_pct_leaky": float(best_dec["dec_return_pct"]),
            "best_dec_params_leaky": {
                "leverage": float(best_dec["leverage"]),
                "lock_log": float(best_dec["lock_log"]),
                "quota_arm_log": None if pd.isna(best_dec["quota_arm_log"]) else float(best_dec["quota_arm_log"]),
                "quota_leverage": None if pd.isna(best_dec["quota_leverage"]) else float(best_dec["quota_leverage"]),
            },
        }
    )


def _same(left: Any, right: Any) -> bool:
    if pd.isna(left) and pd.isna(right):
        return True
    return left == right


def _render_report(summary: dict[str, Any]) -> str:
    dec = summary["december_summary"]
    through = summary["through_10th_order"]
    after = summary["after_10th_order"]
    sweep = summary["param_sweep_summary"]
    return "\n".join(
        [
            "# 12号 2024-12 失败复盘",
            "",
            "这不是新策略，只复盘 11号真正样本外测试里的亏损月。",
            "",
            "## 结论",
            "",
            f"- 2024-12 净收益：`{dec['net_return_pct']:.2f}%`。",
            f"- 不算手续费/换手前：`{dec['gross_before_cost_return_pct']:.2f}%`。",
            f"- 换手成本约：`{dec['cost_log_pct']:.2f}%` log。",
            f"- 订单数：`{dec['orders']}`，换手：`{dec['turnover']}`。",
            f"- 达到月交易配额前后那段：净收益 `{through['net_return_pct']:.2f}%`，不算成本 `{through['gross_before_cost_return_pct']:.2f}%`，成本 `{through['cost_log_pct']:.2f}%` log。",
            f"- 之后净收益：`{after['net_return_pct']:.2f}%`，但只能部分补回血。",
            "",
            "## 参数复查",
            "",
            f"- 小网格候选数：`{sweep['candidate_count']}`。",
            f"- 训练期达标候选数：`{sweep['train_hard_ok_count']}`。",
            f"- 训练期达标且 2024-12 为正的候选数：`{sweep['train_hard_ok_and_dec_positive_count']}`。",
            f"- 选中参数的 2024-12：`{sweep['selected_dec_return_pct']:.2f}%`。",
            f"- 事后最佳 2024-12：`{sweep['best_dec_return_pct_leaky']:.2f}%`，这是看答案，不能交易。",
            "",
            "## 判断",
            "",
            "- 主要问题是月初连续反手打错方向，加上高换手成本；后半月追回很多，但没有完全补回。",
            "- 不能只根据 2024-12 马上加止损或停手规则；这会继续过拟合。",
        ]
    ) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
