from __future__ import annotations

import importlib.util
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_47_btc_hype_tail_event_causal_risk_overlay_20260629"
SRC44 = ROOT / "artifacts" / "strategy_44_btc_hype_tail_event_action_oracle_20260629"
SCRIPT45 = ROOT / "scripts" / "audit_strategy_45_btc_hype_tail_event_fitted_policy_20260629.py"
COST_PER_SIDE = 0.001
EVAL_START = "2025-06"
EVAL_END = "2026-06"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    s45 = _load_strategy45()
    data = s45._load_data()
    event_threshold, min_gap = s45._load_44_config()
    event = s45._event_mask(data, event_threshold)
    oracle_trades = pd.read_csv(SRC44 / "best_oracle_trades.csv")
    training = s45._oracle_training_rows(data, event, oracle_trades, min_gap)
    training["month"] = [data["month"].iloc[int(i)] for i in training["event_index"]]

    rows = []
    best = None
    best_monthly = None
    best_trades = None
    for feature_set in ["market_only", "market_plus_time"]:
        for depth in [4, 5, 6, 8, 12]:
            for min_leaf in [2, 3, 5]:
                base_trades = _walkforward_predicted_trades(s45, data, event, training, feature_set, depth, min_leaf, min_gap)
                for scale in [0.5, 0.65, 0.8, 1.0]:
                    for stop_loss in [None, -0.08, -0.10, -0.15]:
                        for trailing_stop in [None, -0.08, -0.10, -0.15]:
                            for take_profit in [None, 0.20, 0.35, 0.50]:
                                if stop_loss is None and trailing_stop is None and take_profit is None:
                                    continue
                                bar, trades = _simulate_trades(data, base_trades, scale, stop_loss, trailing_stop, take_profit)
                                monthly = _monthly(bar)
                                row = {
                                    "feature_set": feature_set,
                                    "max_depth": depth,
                                    "min_samples_leaf": min_leaf,
                                    "position_scale": scale,
                                    "stop_loss": stop_loss,
                                    "trailing_stop": trailing_stop,
                                    "take_profit": take_profit,
                                    **_summary(monthly, len(trades), float(monthly["turnover"].sum()) if len(monthly) else 0.0),
                                }
                                rows.append(row)
                                if _score(row) > _score(best):
                                    best = row
                                    best_monthly = monthly
                                    best_trades = trades

    if best is None or best_monthly is None or best_trades is None:
        raise RuntimeError("no risk-overlay policy evaluated")

    scan = pd.DataFrame(rows).sort_values(["hard_pass_relaxed", "min_target_year_return_pct", "max_drawdown_pct"], ascending=[False, False, False])
    pass_count = int(scan["hard_pass_relaxed"].sum())
    safer = scan[scan["hard_pass_relaxed"]].sort_values(["max_drawdown_pct", "min_target_year_return_pct"], ascending=[False, False]).head(1)
    market_only = scan[(scan["hard_pass_relaxed"]) & (scan["feature_set"] == "market_only")].head(1)

    scan.to_csv(OUT_DIR / "risk_overlay_scan.csv", index=False)
    best_monthly.to_csv(OUT_DIR / "best_policy_monthly.csv", index=False)
    best_trades.to_csv(OUT_DIR / "best_policy_trades.csv", index=False)

    summary = {
        "status": "strategy_47_btc_hype_tail_event_causal_risk_overlay_ready",
        "strategy_id": "strategy_47_btc_hype_tail_event_causal_risk_overlay_20260629",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "purpose": "Add causal per-trade risk controls to Strategy 46 strict walk-forward tail-event policy.",
        "leakage": {
            "event_detection_uses_closed_past_bars": True,
            "current_month_labels_used_for_current_month": False,
            "risk_controls_use_only_trade_to_date_pnl": True,
            "risk_grid_selected_on_same_2025_06_2026_05_sample": True,
            "tradable_strategy": False,
        },
        "gate": {"target_years": ["2025", "2026"], "required_return_pct": 100.0, "max_drawdown_limit_pct": -50.0},
        "event_config": {
            "ret16_abs_thr": event_threshold[0],
            "ret96_abs_thr": event_threshold[1],
            "resid_z16_abs_thr": event_threshold[2],
            "min_gap": min_gap,
            "event_count": int(event.sum()),
            "training_rows_total": int(len(training)),
        },
        "scan": {"config_count": int(len(scan)), "hard_pass_relaxed_count": pass_count},
        "best_policy": _json_ready(best),
        "safer_passing_policy": _json_ready(safer.iloc[0].to_dict()) if len(safer) else None,
        "best_market_only_passing_policy": _json_ready(market_only.iloc[0].to_dict()) if len(market_only) else None,
        "decision": _decision(best, pass_count),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "risk_overlay_scan": _rel(OUT_DIR / "risk_overlay_scan.csv"),
            "best_policy_monthly": _rel(OUT_DIR / "best_policy_monthly.csv"),
            "best_policy_trades": _rel(OUT_DIR / "best_policy_trades.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_strategy45():
    spec = importlib.util.spec_from_file_location("strategy45", SCRIPT45)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("cannot load strategy 45 helpers")
    spec.loader.exec_module(module)
    return module


def _walkforward_predicted_trades(s45, data: pd.DataFrame, event: np.ndarray, training: pd.DataFrame, feature_set: str, depth: int, min_leaf: int, min_gap: int) -> list[dict[str, Any]]:
    features = s45._feature_names(feature_set)
    months = sorted(data[(data["month"] >= EVAL_START) & (data["month"] < EVAL_END)]["month"].unique())
    out = []
    for month in months:
        hist = training[training["month"] < month]
        if len(hist) < 20 or hist["label"].nunique() < 2:
            continue
        clf = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=min_leaf, random_state=47)
        clf.fit(hist[features].to_numpy(), hist["label"].to_numpy())
        next_ok = 0
        month_event = np.where(event & (data["month"].to_numpy() == month))[0]
        for i in month_event:
            if i < next_ok:
                continue
            x = np.array([[float(data[name].iloc[i]) for name in features]])
            action, th, tb, hold = s45._parse_label(str(clf.predict(x)[0]))
            if action == "cash" or hold <= 0:
                next_ok = i + min_gap
                continue
            start = i + 1
            end = min(len(data), start + hold)
            out.append({"event_index": int(i), "start": int(start), "end": int(end), "hype_target": float(th), "btc_target": float(tb), "month": month, "action": action, "hold_bars": int(hold)})
            next_ok = max(i + min_gap, end)
    return out


def _simulate_trades(data: pd.DataFrame, base_trades: list[dict[str, Any]], scale: float, stop_loss: float | None, trailing_stop: float | None, take_profit: float | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    lr_h = data["lr_HYPEUSDT"].to_numpy()
    lr_b = data["lr_BTCUSDT"].to_numpy()
    bar_lr = np.zeros(len(data))
    turnover = np.zeros(len(data))
    rows = []
    active_until = 0
    for trade in base_trades:
        start = int(trade["start"])
        end = int(trade["end"])
        if start < active_until or start >= end:
            continue
        h = float(trade["hype_target"]) * scale
        b = float(trade["btc_target"]) * scale
        eq = 1.0
        peak = 1.0
        trade_lr = 0.0
        exit_reason = "time"
        exit_i = end - 1
        for j in range(start, end):
            r = h * lr_h[j] + b * lr_b[j]
            if j == start:
                r -= COST_PER_SIDE * (abs(h) + abs(b))
                turnover[j] += abs(h) + abs(b)
            eq *= math.exp(r)
            peak = max(peak, eq)
            ret = eq - 1.0
            dd = eq / peak - 1.0
            hit_stop = stop_loss is not None and ret <= stop_loss
            hit_trail = trailing_stop is not None and dd <= trailing_stop
            hit_take = take_profit is not None and ret >= take_profit
            if hit_stop or hit_trail or hit_take or j == end - 1:
                if hit_stop:
                    exit_reason = "stop_loss"
                elif hit_trail:
                    exit_reason = "trailing_stop"
                elif hit_take:
                    exit_reason = "take_profit"
                r -= COST_PER_SIDE * (abs(h) + abs(b))
                turnover[j] += abs(h) + abs(b)
                eq *= math.exp(-COST_PER_SIDE * (abs(h) + abs(b)))
                bar_lr[j] += r
                trade_lr += r
                exit_i = j
                break
            bar_lr[j] += r
            trade_lr += r
        active_until = exit_i + 1
        rows.append({
            **trade,
            "scaled_hype_target": h,
            "scaled_btc_target": b,
            "exit_index": int(exit_i),
            "entry_timestamp": data["timestamp"].iloc[start],
            "exit_timestamp": data["timestamp"].iloc[exit_i],
            "exit_reason": exit_reason,
            "trade_log_return": float(trade_lr),
            "trade_return_pct": float((math.exp(trade_lr) - 1.0) * 100.0),
        })

    eq_curve = np.exp(np.cumsum(bar_lr))
    dd_curve = eq_curve / np.maximum.accumulate(eq_curve) - 1.0
    bar = pd.DataFrame({"timestamp": data["timestamp"], "month": data["month"], "log_return": bar_lr, "turnover": turnover, "drawdown_pct": dd_curve * 100.0})
    return bar, pd.DataFrame(rows)


def _monthly(bar: pd.DataFrame) -> pd.DataFrame:
    out = bar[(bar["month"] >= EVAL_START) & (bar["month"] < EVAL_END)].groupby("month", as_index=False).agg(
        log_return=("log_return", "sum"),
        turnover=("turnover", "sum"),
        max_drawdown_pct=("drawdown_pct", "min"),
    )
    out["return_pct"] = (np.exp(out["log_return"]) - 1.0) * 100.0
    return out


def _summary(monthly: pd.DataFrame, trade_count: int, turnover: float) -> dict[str, Any]:
    yearly = {year: (math.exp(group["log_return"].sum()) - 1.0) * 100.0 for year, group in monthly.groupby(monthly["month"].str[:4])}
    min_target = min(yearly.get("2025", -999.0), yearly.get("2026", -999.0))
    max_dd = float(monthly["max_drawdown_pct"].min()) if len(monthly) else 0.0
    return {
        "return_2025_pct": yearly.get("2025", 0.0),
        "return_2026_ytd_pct": yearly.get("2026", 0.0),
        "min_target_year_return_pct": min_target,
        "max_drawdown_pct": max_dd,
        "trade_count": int(trade_count),
        "turnover": turnover,
        "hard_pass_relaxed": bool(min_target > 100.0 and max_dd >= -50.0),
    }


def _score(row: dict[str, Any] | None) -> tuple[float, float]:
    if row is None:
        return (-999.0, -999.0)
    return (float(row.get("hard_pass_relaxed", False)), float(row.get("min_target_year_return_pct", -999.0)), float(row.get("max_drawdown_pct", -999.0)))


def _decision(best: dict[str, Any], pass_count: int) -> dict[str, Any]:
    if pass_count:
        return {
            "verdict": "TAIL_EVENT_CAUSAL_RISK_OVERLAY_PASSES_RELAXED_GATE_IN_SAMPLE",
            "promote_strategy": False,
            "reason": "严格走步动作加因果逐笔风控后，同段历史能过放宽门槛；但风控参数仍是在这段历史上挑出来的，不能直接实盘。",
        }
    return {
        "verdict": "TAIL_EVENT_CAUSAL_RISK_OVERLAY_FAILS_RELAXED_GATE",
        "promote_strategy": False,
        "reason": "加逐笔因果风控后仍不能通过放宽门槛。",
    }


def _report(summary: dict[str, Any]) -> str:
    b = summary["best_policy"]
    return f"""# 47号 BTC+HYPE 尾部事件因果风控覆盖审计

本审计不是实盘策略。它只检查：46号严格走步动作，加上只用交易当下盈亏的逐笔风控后，历史上能不能通过放宽门槛。

## 最好结果

- 特征集：`{b["feature_set"]}`
- 树深度：`{b["max_depth"]}`
- 最小叶子样本：`{b["min_samples_leaf"]}`
- 仓位缩放：`{b["position_scale"]}`
- 止损：`{b["stop_loss"]}`
- 跟踪止损：`{b["trailing_stop"]}`
- 止盈：`{b["take_profit"]}`
- 2025：`{b["return_2025_pct"]:.2f}%`
- 2026 YTD：`{b["return_2026_ytd_pct"]:.2f}%`
- 最大回撤：`{b["max_drawdown_pct"]:.2f}%`
- 交易数：`{b["trade_count"]}`
- 是否过放宽门槛：`{b["hard_pass_relaxed"]}`

## 判断

`{summary["decision"]["verdict"]}`

{summary["decision"]["reason"]}
"""


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value) if isinstance(value, float) else False:
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
