from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import audit_strategy_58_tail_event_micro_signal_20260630 as s58


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_60_tail_event_simple_causal_risk_overlay_20260630"
SOURCE_58 = ROOT / "artifacts" / "strategy_58_tail_event_micro_signal_20260630"
STRATEGY_ID = "strategy_60_tail_event_simple_causal_risk_overlay_20260630"

MONTH_LOSS_TRIGGERS = [None, -0.10, -0.15, -0.20, -0.25, -0.30, -0.35]
MONTH_DD_TRIGGERS = [None, -0.15, -0.20, -0.25, -0.30, -0.35]
ACCOUNT_DD_TRIGGERS = [None, -0.25, -0.35, -0.45, -0.55]
TRIGGERED_SCALES = [0.0, 0.25, 0.5]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data, data_quality = s58._load_data()
    source_policy = _source_policy()
    base_bar, planned_trades, source_monthly = _source_58_policy(data, source_policy)

    baseline_bar = _apply_overlay(base_bar, _config(None, None, None, 1.0))
    baseline_monthly = _monthly(baseline_bar)
    baseline = _summary(baseline_monthly, planned_trades, baseline_bar)
    _assert_baseline_close(baseline, source_policy)

    rows = []
    for month_loss in MONTH_LOSS_TRIGGERS:
        for month_dd in MONTH_DD_TRIGGERS:
            for account_dd in ACCOUNT_DD_TRIGGERS:
                trigger_exists = month_loss is not None or month_dd is not None or account_dd is not None
                for triggered_scale in (TRIGGERED_SCALES if trigger_exists else [1.0]):
                    cfg = _config(month_loss, month_dd, account_dd, triggered_scale)
                    bar = _apply_overlay(base_bar, cfg)
                    monthly = _monthly(bar)
                    trades = _scale_trades(planned_trades, bar)
                    row = {**cfg, **_summary(monthly, trades, bar)}
                    rows.append(row)

    scan = pd.DataFrame(rows).sort_values(
        ["hard_pass_relaxed", "min_target_year_return_pct", "max_drawdown_pct"],
        ascending=[False, False, False],
    )
    dd_ok = scan[scan["max_drawdown_pct"] >= s58.MAX_DRAWDOWN_LIMIT_PCT]
    best_dd_ok = dd_ok.sort_values(["min_target_year_return_pct", "max_drawdown_pct"], ascending=[False, False]).head(1)
    best_return = scan.sort_values(["min_target_year_return_pct", "max_drawdown_pct"], ascending=[False, False]).head(1)
    pass_count = int(scan["hard_pass_relaxed"].sum())
    selected = _selected_display_row(scan, best_dd_ok, best_return)
    best = selected.to_dict()
    best_bar = _apply_overlay(base_bar, _config_from_row(best))
    best_monthly = _monthly(best_bar)
    best_trades = _scale_trades(planned_trades, best_bar)

    scan.to_csv(OUT_DIR / "risk_overlay_scan.csv", index=False)
    source_monthly.to_csv(OUT_DIR / "source_58_policy_monthly.csv", index=False)
    baseline_monthly.to_csv(OUT_DIR / "baseline_replay_monthly.csv", index=False)
    best_monthly.to_csv(OUT_DIR / "best_overlay_monthly.csv", index=False)
    best_bar.to_csv(OUT_DIR / "best_overlay_bar.csv", index=False)
    best_trades.to_csv(OUT_DIR / "best_overlay_trades.csv", index=False)

    summary = {
        "status": "strategy_60_tail_event_simple_causal_risk_overlay_done",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "purpose": "Run an optimistic upper-bound test: can simple causal loss/drawdown scaling rescue Strategy 58 best-return policy?",
        "source_strategy": "strategy_58_tail_event_micro_signal_20260630",
        "data": data_quality,
        "leakage": {
            "uses_strategy_58_walkforward_bar_returns": True,
            "retrained_action_model": False,
            "current_month_labels_used": False,
            "risk_controls_use_only_prior_bar_realized_pnl_and_drawdown": True,
            "risk_grid_selected_on_same_2025_06_2026_05_sample": True,
            "optimistic_upper_bound": True,
            "tradable_strategy": False,
        },
        "gate": {
            "required_return_pct_each_target_year": s58.REQUIRED_YEAR_RETURN_PCT,
            "max_drawdown_limit_pct": s58.MAX_DRAWDOWN_LIMIT_PCT,
            "target_years": s58.TARGET_YEARS,
        },
        "source_policy": _json_ready(source_policy),
        "baseline_replay": _json_ready(baseline),
        "scan": {
            "config_count": int(len(scan)),
            "hard_pass_relaxed_count": pass_count,
            "month_loss_triggers": MONTH_LOSS_TRIGGERS,
            "month_dd_triggers": MONTH_DD_TRIGGERS,
            "account_dd_triggers": ACCOUNT_DD_TRIGGERS,
            "triggered_scales": TRIGGERED_SCALES,
        },
        "best_policy": _json_ready(best),
        "best_drawdown_capped_policy": _json_ready(best_dd_ok.iloc[0].to_dict()) if len(best_dd_ok) else None,
        "best_return_policy": _json_ready(best_return.iloc[0].to_dict()) if len(best_return) else None,
        "decision": _decision(pass_count, best_dd_ok),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "risk_overlay_scan": _rel(OUT_DIR / "risk_overlay_scan.csv"),
            "source_58_policy_monthly": _rel(OUT_DIR / "source_58_policy_monthly.csv"),
            "baseline_replay_monthly": _rel(OUT_DIR / "baseline_replay_monthly.csv"),
            "best_overlay_monthly": _rel(OUT_DIR / "best_overlay_monthly.csv"),
            "best_overlay_bar": _rel(OUT_DIR / "best_overlay_bar.csv"),
            "best_overlay_trades": _rel(OUT_DIR / "best_overlay_trades.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _source_policy() -> dict[str, Any]:
    return json.loads((SOURCE_58 / "summary.json").read_text(encoding="utf-8"))["best_walkforward_action_policy"]


def _source_58_policy(data: pd.DataFrame, policy: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    event = s58._event_mask(data)
    months = sorted(data[(data["month"] >= s58.EVAL_START) & (data["month"] < s58.EVAL_END_EXCLUSIVE)]["month"].unique())
    labels = s58._oracle_event_labels(data, event, int(policy["confirm_bars"]))
    bar, trades, _trained_months = s58._walkforward_action_policy(
        data,
        labels,
        months,
        s58._feature_names(str(policy["feature_set"])),
        int(policy["max_depth"]),
        int(policy["min_samples_leaf"]),
        int(policy["hold_bars"]),
        float(policy["leverage"]),
    )
    return bar, trades.sort_values("decision_index").reset_index(drop=True), s58._monthly(bar)


def _config(
    month_loss_trigger: float | None,
    month_dd_trigger: float | None,
    account_dd_trigger: float | None,
    triggered_scale: float,
) -> dict[str, Any]:
    return {
        "month_loss_trigger": month_loss_trigger,
        "month_dd_trigger": month_dd_trigger,
        "account_dd_trigger": account_dd_trigger,
        "triggered_scale": triggered_scale,
    }


def _config_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return _config(
        _none_if_nan(row.get("month_loss_trigger")),
        _none_if_nan(row.get("month_dd_trigger")),
        _none_if_nan(row.get("account_dd_trigger")),
        float(row["triggered_scale"]),
    )


def _none_if_nan(value: Any) -> Any:
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return value


def _selected_display_row(scan: pd.DataFrame, best_dd_ok: pd.DataFrame, best_return: pd.DataFrame) -> pd.Series:
    passes = scan[scan["hard_pass_relaxed"]]
    if len(passes):
        return passes.iloc[0]
    if len(best_dd_ok):
        return best_dd_ok.iloc[0]
    return best_return.iloc[0]


def _apply_overlay(base_bar: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    rows = []
    account_log = 0.0
    account_peak_log = 0.0
    current_month = None
    month_log = 0.0
    month_peak_log = 0.0
    month_triggered = False

    for row in base_bar.itertuples(index=False):
        month = str(row.month)
        if month != current_month:
            current_month = month
            month_log = 0.0
            month_peak_log = 0.0
            month_triggered = False

        account_dd = math.exp(account_log - account_peak_log) - 1.0
        account_triggered = cfg["account_dd_trigger"] is not None and account_dd <= float(cfg["account_dd_trigger"])
        active_trigger = month_triggered or account_triggered
        scale = float(cfg["triggered_scale"]) if active_trigger else 1.0

        lr = float(row.log_return) * scale
        account_log += lr
        account_peak_log = max(account_peak_log, account_log)
        month_log += lr
        month_peak_log = max(month_peak_log, month_log)

        month_return = math.exp(month_log) - 1.0
        month_dd = math.exp(month_log - month_peak_log) - 1.0
        if cfg["month_loss_trigger"] is not None and month_return <= float(cfg["month_loss_trigger"]):
            month_triggered = True
        if cfg["month_dd_trigger"] is not None and month_dd <= float(cfg["month_dd_trigger"]):
            month_triggered = True

        rows.append(
            {
                "timestamp": row.timestamp,
                "month": month,
                "base_log_return": float(row.log_return),
                "log_return": lr,
                "turnover": float(row.turnover) * abs(scale),
                "risk_scale": scale,
                "risk_triggered": bool(active_trigger),
            }
        )

    out = pd.DataFrame(rows)
    equity = np.exp(out["log_return"].cumsum())
    out["drawdown_pct"] = (equity / equity.cummax() - 1.0) * 100.0
    return out


def _scale_trades(planned: pd.DataFrame, bar: pd.DataFrame) -> pd.DataFrame:
    if planned.empty:
        return planned.copy()
    out = planned.copy()
    starts = (out["decision_index"].astype(int) + 1).clip(upper=len(bar) - 1)
    out["risk_scale_at_entry"] = [float(bar["risk_scale"].iloc[i]) for i in starts]
    out["risk_triggered_at_entry"] = [bool(bar["risk_triggered"].iloc[i]) for i in starts]
    out["skipped_by_overlay"] = out["risk_scale_at_entry"] == 0.0
    return out


def _monthly(bar: pd.DataFrame) -> pd.DataFrame:
    out = bar[(bar["month"] >= s58.EVAL_START) & (bar["month"] < s58.EVAL_END_EXCLUSIVE)].groupby("month", as_index=False).agg(
        log_return=("log_return", "sum"),
        turnover=("turnover", "sum"),
        max_drawdown_pct=("drawdown_pct", "min"),
        scaled_bars=("risk_triggered", "sum"),
    )
    out["return_pct"] = (np.exp(out["log_return"]) - 1.0) * 100.0
    return out


def _summary(monthly: pd.DataFrame, trades: pd.DataFrame, bar: pd.DataFrame) -> dict[str, Any]:
    yearly = {year: (math.exp(group["log_return"].sum()) - 1.0) * 100.0 for year, group in monthly.groupby(monthly["month"].str[:4])}
    min_target = min(yearly.get("2025", -999.0), yearly.get("2026", -999.0))
    max_dd = float(monthly["max_drawdown_pct"].min()) if len(monthly) else 0.0
    skipped = int(trades.get("skipped_by_overlay", pd.Series(dtype=bool)).sum()) if len(trades) else 0
    return {
        "return_2025_pct": yearly.get("2025", 0.0),
        "return_2026_pct": yearly.get("2026", 0.0),
        "min_target_year_return_pct": float(min_target),
        "max_drawdown_pct": max_dd,
        "losing_months": int((monthly["return_pct"] <= 0).sum()) if len(monthly) else 0,
        "min_monthly_return_pct": float(monthly["return_pct"].min()) if len(monthly) else 0.0,
        "planned_trade_count": int(len(trades)),
        "skipped_trade_count": skipped,
        "risk_scaled_bar_count": int(bar["risk_triggered"].sum()) if len(bar) else 0,
        "turnover": float(monthly["turnover"].sum()) if len(monthly) else 0.0,
        "hard_pass_relaxed": bool(min_target > s58.REQUIRED_YEAR_RETURN_PCT and max_dd >= s58.MAX_DRAWDOWN_LIMIT_PCT),
    }


def _assert_baseline_close(baseline: dict[str, Any], source_policy: dict[str, Any]) -> None:
    for key in ["return_2025_pct", "return_2026_pct", "max_drawdown_pct"]:
        if abs(float(baseline[key]) - float(source_policy[key])) > 1e-8:
            raise AssertionError(f"baseline replay mismatch for {key}: {baseline[key]} vs {source_policy[key]}")


def _decision(pass_count: int, best_dd_ok: pd.DataFrame) -> dict[str, Any]:
    if pass_count:
        return {
            "verdict": "SIMPLE_CAUSAL_RISK_OVERLAY_UPPER_BOUND_PASSES_IN_SAMPLE",
            "promote_strategy": False,
            "reason": "极简因果风控上限在同段历史能过放宽门槛，但这是同段挑参且逐K收益缩放偏乐观，不能直接实盘。",
        }
    if len(best_dd_ok):
        row = best_dd_ok.iloc[0]
        return {
            "verdict": "SIMPLE_CAUSAL_RISK_OVERLAY_UPPER_BOUND_FAILS_RELAXED_GATE",
            "promote_strategy": False,
            "reason": f"回撤能压到 {row['max_drawdown_pct']:.2f}%，但最低目标年收益只有 {row['min_target_year_return_pct']:.2f}%，达不到100%。",
        }
    return {
        "verdict": "SIMPLE_CAUSAL_RISK_OVERLAY_UPPER_BOUND_FAILS_DRAWDOWN_CONTROL",
        "promote_strategy": False,
        "reason": "极简因果风控上限连最大回撤50%以内也没有压住。",
    }


def _report(summary: dict[str, Any]) -> str:
    base = summary["baseline_replay"]
    best = summary["best_policy"]
    capped = summary["best_drawdown_capped_policy"]
    capped_lines = ["_无回撤合格配置_"] if capped is None else [
        f"- month_loss_trigger: `{capped['month_loss_trigger']}`",
        f"- month_dd_trigger: `{capped['month_dd_trigger']}`",
        f"- account_dd_trigger: `{capped['account_dd_trigger']}`",
        f"- triggered_scale: `{capped['triggered_scale']}`",
        f"- 2025: `{capped['return_2025_pct']:.2f}%`",
        f"- 2026: `{capped['return_2026_pct']:.2f}%`",
        f"- 最大回撤: `{capped['max_drawdown_pct']:.2f}%`",
        f"- 是否过放宽门槛: `{capped['hard_pass_relaxed']}`",
    ]
    return "\n".join(
        [
            "# Strategy 60：尾部事件极简因果风控上限测试",
            "",
            "这是研究审计，不是实盘策略。",
            "",
            "## 口径",
            "",
            "- 复用58号最好收益配置的逐K收益。",
            "- 不重新训练动作模型，不新增入场规则。",
            "- 风控只看上一根K线已经发生后的月内亏损、月内回撤、账户回撤。",
            "- 这是偏乐观上限：直接缩放58号逐K收益，没有重新撮合真实开平仓成本。",
            "",
            "## 58号基线复放",
            "",
            f"- 2025: `{base['return_2025_pct']:.2f}%`",
            f"- 2026: `{base['return_2026_pct']:.2f}%`",
            f"- 最大回撤: `{base['max_drawdown_pct']:.2f}%`",
            "",
            "## 选中展示配置",
            "",
            f"- month_loss_trigger: `{best['month_loss_trigger']}`",
            f"- month_dd_trigger: `{best['month_dd_trigger']}`",
            f"- account_dd_trigger: `{best['account_dd_trigger']}`",
            f"- triggered_scale: `{best['triggered_scale']}`",
            f"- 2025: `{best['return_2025_pct']:.2f}%`",
            f"- 2026: `{best['return_2026_pct']:.2f}%`",
            f"- 最大回撤: `{best['max_drawdown_pct']:.2f}%`",
            f"- 是否过放宽门槛: `{best['hard_pass_relaxed']}`",
            "",
            "## 回撤合格里收益最高",
            "",
            *capped_lines,
            "",
            "## 结论",
            "",
            f"- `{summary['decision']['verdict']}`",
            f"- {summary['decision']['reason']}",
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
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
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
