from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

import audit_strategy_16_new_family_probe_20260627 as probe16


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_57_tail_event_state_action_predictability_20260630"
STRATEGY_ID = "strategy_57_tail_event_state_action_predictability_20260630"
PANEL_41 = ROOT / "artifacts" / "strategy_41_btc_hype_relaxed_drawdown_20260629" / "btc_hype_close_panel_15m_2020_2026_05.csv.gz"
LATEST_49 = ROOT / "artifacts" / "strategy_49_btc_hype_frozen_47_latest_public_20260629" / "latest_klines.csv.gz"
WARMUP_START = "2025-05"
EVAL_START = "2025-06"
EVAL_END_EXCLUSIVE = "2026-07"
TARGET_YEARS = ["2025", "2026"]
MAX_TRADE_DD_PCT = -50.0
MAX_DRAWDOWN_LIMIT_PCT = -50.0
REQUIRED_YEAR_RETURN_PCT = 100.0
EVENT_THRESHOLD = {"hype_ret16_abs": 0.04, "hype_ret96_abs": 0.10, "resid_z_abs": 2.0}
MIN_GAP = 16
HOLDS = [16, 32, 64, 96]
LEVERAGES = [0.5, 1.0, 2.0]


def main() -> None:
    warnings.filterwarnings("ignore", message="The number of unique classes.*")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data, data_quality = _load_data()
    event = _event_mask(data)
    labels = _oracle_event_labels(data, event)
    oracle_bar, oracle_trades = _apply_label_policy(data, event, labels)
    oracle_monthly = _monthly(oracle_bar)
    oracle_summary = _summary(oracle_monthly, int(len(oracle_trades)), float(oracle_monthly["turnover"].sum()))

    scan_rows = []
    best = None
    best_monthly = None
    best_trades = None
    months = sorted(data[(data["month"] >= EVAL_START) & (data["month"] < EVAL_END_EXCLUSIVE)]["month"].unique())
    for feature_set in ["market_only", "market_plus_time"]:
        features = _feature_names(feature_set)
        for max_depth in [2, 3, 4, 5, 6]:
            for min_leaf in [2, 3, 5, 8]:
                bar, trades, trained_months = _walkforward_policy(data, event, labels, months, features, max_depth, min_leaf)
                monthly = _monthly(bar)
                row = {
                    "feature_set": feature_set,
                    "max_depth": max_depth,
                    "min_samples_leaf": min_leaf,
                    "trained_months": trained_months,
                    **_summary(monthly, int(len(trades)), float(monthly["turnover"].sum())),
                }
                scan_rows.append(row)
                if _score(row) > _score(best):
                    best = row
                    best_monthly = monthly
                    best_trades = trades

    if best is None or best_monthly is None or best_trades is None:
        raise RuntimeError("no policy evaluated")

    action_scan_rows = []
    best_action = None
    best_action_monthly = None
    best_action_trades = None
    for feature_set in ["market_only", "market_plus_time"]:
        features = _feature_names(feature_set)
        for max_depth in [2, 3, 4, 5, 6]:
            for min_leaf in [3, 5, 8]:
                for hold_bars in [32, 64, 96]:
                    for leverage in [0.5, 1.0, 2.0]:
                        bar, trades, trained_months = _walkforward_action_only_policy(
                            data, event, labels, months, features, max_depth, min_leaf, hold_bars, leverage
                        )
                        monthly = _monthly(bar)
                        row = {
                            "feature_set": feature_set,
                            "max_depth": max_depth,
                            "min_samples_leaf": min_leaf,
                            "hold_bars": hold_bars,
                            "leverage": leverage,
                            "trained_months": trained_months,
                            **_summary(monthly, int(len(trades)), float(monthly["turnover"].sum())),
                        }
                        action_scan_rows.append(row)
                        if _score(row) > _score(best_action):
                            best_action = row
                            best_action_monthly = monthly
                            best_action_trades = trades

    if best_action is None or best_action_monthly is None or best_action_trades is None:
        raise RuntimeError("no action-only policy evaluated")

    scan = pd.DataFrame(scan_rows).sort_values(["hard_pass_relaxed", "min_target_year_return_pct", "max_drawdown_pct"], ascending=[False, False, False])
    action_scan = pd.DataFrame(action_scan_rows).sort_values(["hard_pass_relaxed", "min_target_year_return_pct", "max_drawdown_pct"], ascending=[False, False, False])
    labels.to_csv(OUT_DIR / "oracle_event_labels.csv", index=False)
    oracle_monthly.to_csv(OUT_DIR / "oracle_event_action_monthly.csv", index=False)
    oracle_trades.to_csv(OUT_DIR / "oracle_event_action_trades.csv", index=False)
    scan.to_csv(OUT_DIR / "walkforward_policy_scan.csv", index=False)
    action_scan.to_csv(OUT_DIR / "walkforward_action_only_scan.csv", index=False)
    best_monthly.to_csv(OUT_DIR / "best_walkforward_monthly.csv", index=False)
    best_trades.to_csv(OUT_DIR / "best_walkforward_trades.csv", index=False)
    best_action_monthly.to_csv(OUT_DIR / "best_action_only_monthly.csv", index=False)
    best_action_trades.to_csv(OUT_DIR / "best_action_only_trades.csv", index=False)

    summary = {
        "status": "strategy_57_tail_event_state_action_predictability_done",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "purpose": "Test whether event-time state features can predict post-tail-event action choice without using current-month labels.",
        "data": data_quality,
        "event_threshold": EVENT_THRESHOLD,
        "label_leakage_note": "Oracle labels use future returns, but walk-forward training uses only labels from months before the tested month.",
        "cost_model": {"cost_per_side": probe16.COST_PER_SIDE, "round_trip_open_close": probe16.ROUND_TRIP_COST},
        "label_summary": _label_summary(labels),
        "oracle_event_action": _json_ready(oracle_summary),
        "best_walkforward_policy": _json_ready(best),
        "best_action_only_policy": _json_ready(best_action),
        "decision": _decision(best, best_action, oracle_summary),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "oracle_event_labels": _rel(OUT_DIR / "oracle_event_labels.csv"),
            "oracle_event_action_monthly": _rel(OUT_DIR / "oracle_event_action_monthly.csv"),
            "walkforward_policy_scan": _rel(OUT_DIR / "walkforward_policy_scan.csv"),
            "walkforward_action_only_scan": _rel(OUT_DIR / "walkforward_action_only_scan.csv"),
            "best_walkforward_monthly": _rel(OUT_DIR / "best_walkforward_monthly.csv"),
            "best_walkforward_trades": _rel(OUT_DIR / "best_walkforward_trades.csv"),
            "best_action_only_monthly": _rel(OUT_DIR / "best_action_only_monthly.csv"),
            "best_action_only_trades": _rel(OUT_DIR / "best_action_only_trades.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_data() -> tuple[pd.DataFrame, dict[str, Any]]:
    base = pd.read_csv(PANEL_41, parse_dates=["timestamp"])
    latest = pd.read_csv(LATEST_49, parse_dates=["timestamp"]).pivot(index="timestamp", columns="symbol", values="close").reset_index()
    latest = latest.rename(columns={"BTCUSDT": "close_BTCUSDT", "HYPEUSDT": "close_HYPEUSDT"})
    panel = (
        pd.concat([base[["timestamp", "close_BTCUSDT", "close_HYPEUSDT"]], latest], ignore_index=True)
        .drop_duplicates("timestamp", keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    panel["timestamp"] = pd.to_datetime(panel["timestamp"], utc=True)
    panel["month"] = panel["timestamp"].dt.strftime("%Y-%m")
    panel = panel[(panel["month"] >= WARMUP_START) & (panel["month"] < EVAL_END_EXCLUSIVE)].dropna().reset_index(drop=True)
    for symbol in ["BTCUSDT", "HYPEUSDT"]:
        close = panel[f"close_{symbol}"].astype(float)
        panel[f"lr_{symbol}"] = np.log(close / close.shift(1)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        for bars in [16, 96, 384]:
            panel[f"ret{bars}_{symbol}"] = np.log(close / close.shift(bars)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    panel["rel_ret16"] = panel["ret16_HYPEUSDT"] - panel["ret16_BTCUSDT"]
    panel["rel_ret96"] = panel["ret96_HYPEUSDT"] - panel["ret96_BTCUSDT"]
    resid_scale = panel["rel_ret16"].rolling(96 * 30, min_periods=96).std().replace(0, np.nan)
    panel["resid_z16"] = (panel["rel_ret16"] / resid_scale).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    panel["shock_sign"] = np.sign(np.where(panel["ret16_HYPEUSDT"].abs() >= panel["ret96_HYPEUSDT"].abs(), panel["ret16_HYPEUSDT"], panel["ret96_HYPEUSDT"]))
    panel["trend_align"] = np.sign(panel["ret384_HYPEUSDT"]) * panel["shock_sign"]
    panel["btc_align"] = np.sign(panel["ret96_BTCUSDT"]) * panel["shock_sign"]
    panel["month_num"] = panel["timestamp"].dt.month
    panel["day_num"] = panel["timestamp"].dt.day
    panel["hour_float"] = panel["timestamp"].dt.hour + panel["timestamp"].dt.minute / 60.0
    panel["event_index_frac"] = np.arange(len(panel)) / max(1, len(panel) - 1)
    quality = {
        "sources": [_rel(PANEL_41), _rel(LATEST_49)],
        "rows": int(len(panel)),
        "start_timestamp": panel["timestamp"].min().isoformat(),
        "end_timestamp": panel["timestamp"].max().isoformat(),
        "duplicate_timestamp_rows": int(panel["timestamp"].duplicated().sum()),
        "non_15m_gap_rows": int((panel["timestamp"].diff().dropna() != pd.Timedelta(minutes=15)).sum()),
    }
    return panel, quality


def _event_mask(data: pd.DataFrame) -> np.ndarray:
    month = data["month"].to_numpy(str)
    return (
        (month >= EVAL_START)
        & (month < EVAL_END_EXCLUSIVE)
        & (
            (data["ret16_HYPEUSDT"].abs().to_numpy() >= EVENT_THRESHOLD["hype_ret16_abs"])
            | (data["ret96_HYPEUSDT"].abs().to_numpy() >= EVENT_THRESHOLD["hype_ret96_abs"])
            | (data["resid_z16"].abs().to_numpy() >= EVENT_THRESHOLD["resid_z_abs"])
        )
    )


def _oracle_event_labels(data: pd.DataFrame, event: np.ndarray) -> pd.DataFrame:
    rows = []
    next_ok = 0
    for i in np.where(event)[0]:
        if i < next_ok or i + 2 >= len(data):
            continue
        option = _best_action(data, int(i))
        features = _feature_row(data, int(i), "market_plus_time")
        rows.append(
            {
                "event_index": int(i),
                "event_timestamp": data["timestamp"].iloc[i],
                "month": data["month"].iloc[i],
                "label": _label(option["action"], option["hype_target"], option["btc_target"], option["hold_bars"]),
                **option,
                **features,
            }
        )
        next_ok = max(i + MIN_GAP, i + 1 + int(option["hold_bars"]))
    return pd.DataFrame(rows)


def _best_action(data: pd.DataFrame, event_index: int) -> dict[str, Any]:
    options = [{"action": "cash", "hype_target": 0.0, "btc_target": 0.0, "hold_bars": 0, "trade_log_return": 0.0, "trade_return_pct": 0.0, "trade_max_drawdown_pct": 0.0}]
    hype_shock = _sign(data["ret16_HYPEUSDT"].iloc[event_index] if abs(data["ret16_HYPEUSDT"].iloc[event_index]) >= abs(data["ret96_HYPEUSDT"].iloc[event_index]) else data["ret96_HYPEUSDT"].iloc[event_index])
    btc_shock = _sign(data["ret16_BTCUSDT"].iloc[event_index])
    rel_shock = _sign(data["resid_z16"].iloc[event_index] if data["resid_z16"].iloc[event_index] != 0 else data["rel_ret16"].iloc[event_index])
    for hold in HOLDS:
        for lev in LEVERAGES:
            candidates = [
                ("hype_momentum", hype_shock * lev, 0.0),
                ("hype_reversal", -hype_shock * lev, 0.0),
                ("btc_momentum", 0.0, btc_shock * lev),
                ("btc_reversal", 0.0, -btc_shock * lev),
                ("pair_momentum", -rel_shock * lev / 2.0, rel_shock * lev / 2.0),
                ("pair_reversal", rel_shock * lev / 2.0, -rel_shock * lev / 2.0),
            ]
            for action, btc_target, hype_target in candidates:
                if btc_target == 0 and hype_target == 0:
                    continue
                stats = _trade_stats(data, event_index + 1, hold, btc_target, hype_target)
                if stats["trade_max_drawdown_pct"] >= MAX_TRADE_DD_PCT:
                    options.append({"action": action, "btc_target": btc_target, "hype_target": hype_target, "hold_bars": hold, **stats})
    return max(options, key=lambda row: row["trade_log_return"])


def _trade_stats(data: pd.DataFrame, start: int, hold: int, btc_target: float, hype_target: float) -> dict[str, float]:
    end = min(len(data), start + hold)
    if start >= end:
        return {"trade_log_return": 0.0, "trade_return_pct": 0.0, "trade_max_drawdown_pct": 0.0}
    lr = btc_target * data["lr_BTCUSDT"].to_numpy()[start:end] + hype_target * data["lr_HYPEUSDT"].to_numpy()[start:end]
    lr = lr.copy()
    lr[0] -= probe16.COST_PER_SIDE * (abs(btc_target) + abs(hype_target))
    lr[-1] -= probe16.COST_PER_SIDE * (abs(btc_target) + abs(hype_target))
    equity = np.exp(np.cumsum(lr))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    return {"trade_log_return": float(lr.sum()), "trade_return_pct": float((np.exp(lr.sum()) - 1.0) * 100.0), "trade_max_drawdown_pct": float(drawdown.min() * 100.0)}


def _walkforward_policy(
    data: pd.DataFrame,
    event: np.ndarray,
    labels: pd.DataFrame,
    months: list[str],
    features: list[str],
    max_depth: int,
    min_leaf: int,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    target_btc = np.zeros(len(data))
    target_hype = np.zeros(len(data))
    trade_rows = []
    trained_months = 0
    for month in months:
        train = labels[labels["month"] < month]
        if len(train) < 20 or train["label"].nunique() < 2:
            continue
        clf = DecisionTreeClassifier(max_depth=max_depth, min_samples_leaf=min_leaf, random_state=57)
        clf.fit(train[features].to_numpy(float), train["label"].to_numpy(str))
        next_ok = 0
        month_events = np.where(event & (data["month"].to_numpy(str) == month))[0]
        for i in month_events:
            if i < next_ok:
                continue
            label = str(clf.predict(np.array([[float(data[name].iloc[i]) for name in features]]))[0])
            action, btc_target, hype_target, hold = _parse_label(label)
            if action == "cash" or hold <= 0:
                next_ok = i + MIN_GAP
                continue
            start = i + 1
            end = min(len(data), start + hold)
            target_btc[start:end] = btc_target
            target_hype[start:end] = hype_target
            trade_rows.append({"month": month, "event_index": int(i), "event_timestamp": data["timestamp"].iloc[i], "label": label, "action": action, "btc_target": btc_target, "hype_target": hype_target, "hold_bars": hold, "trained_rows": len(train), "trained_labels": train["label"].nunique()})
            next_ok = max(i + MIN_GAP, end)
        trained_months += 1
    return _simulate(data, target_btc, target_hype), pd.DataFrame(trade_rows), trained_months


def _walkforward_action_only_policy(
    data: pd.DataFrame,
    event: np.ndarray,
    labels: pd.DataFrame,
    months: list[str],
    features: list[str],
    max_depth: int,
    min_leaf: int,
    hold_bars: int,
    leverage: float,
) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    target_btc = np.zeros(len(data))
    target_hype = np.zeros(len(data))
    trade_rows = []
    trained_months = 0
    for month in months:
        train = labels[labels["month"] < month]
        if len(train) < 20 or train["action"].nunique() < 2:
            continue
        clf = DecisionTreeClassifier(max_depth=max_depth, min_samples_leaf=min_leaf, random_state=571)
        clf.fit(train[features].to_numpy(float), train["action"].to_numpy(str))
        next_ok = 0
        month_events = np.where(event & (data["month"].to_numpy(str) == month))[0]
        for i in month_events:
            if i < next_ok:
                continue
            action = str(clf.predict(np.array([[float(data[name].iloc[i]) for name in features]]))[0])
            btc_target, hype_target = _position_for_action(data, int(i), action, leverage)
            if action == "cash" or (btc_target == 0.0 and hype_target == 0.0):
                next_ok = i + MIN_GAP
                continue
            start = i + 1
            end = min(len(data), start + hold_bars)
            target_btc[start:end] = btc_target
            target_hype[start:end] = hype_target
            trade_rows.append(
                {
                    "month": month,
                    "event_index": int(i),
                    "event_timestamp": data["timestamp"].iloc[i],
                    "action": action,
                    "btc_target": btc_target,
                    "hype_target": hype_target,
                    "hold_bars": hold_bars,
                    "leverage": leverage,
                    "trained_rows": len(train),
                    "trained_actions": train["action"].nunique(),
                }
            )
            next_ok = max(i + MIN_GAP, end)
        trained_months += 1
    return _simulate(data, target_btc, target_hype), pd.DataFrame(trade_rows), trained_months


def _apply_label_policy(data: pd.DataFrame, event: np.ndarray, labels: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    label_map = {int(row.event_index): row for row in labels.itertuples(index=False)}
    target_btc = np.zeros(len(data))
    target_hype = np.zeros(len(data))
    trades = []
    next_ok = 0
    for i in np.where(event)[0]:
        if i < next_ok or int(i) not in label_map:
            continue
        row = label_map[int(i)]
        action, btc_target, hype_target, hold = _parse_label(str(row.label))
        if action == "cash" or hold <= 0:
            next_ok = i + MIN_GAP
            continue
        start = i + 1
        end = min(len(data), start + hold)
        target_btc[start:end] = btc_target
        target_hype[start:end] = hype_target
        trades.append({"month": data["month"].iloc[i], "event_index": int(i), "event_timestamp": data["timestamp"].iloc[i], "label": row.label, "action": action, "btc_target": btc_target, "hype_target": hype_target, "hold_bars": hold})
        next_ok = max(i + MIN_GAP, end)
    return _simulate(data, target_btc, target_hype), pd.DataFrame(trades)


def _simulate(data: pd.DataFrame, target_btc: np.ndarray, target_hype: np.ndarray) -> pd.DataFrame:
    previous_btc = np.r_[0.0, target_btc[:-1]]
    previous_hype = np.r_[0.0, target_hype[:-1]]
    turnover = np.abs(target_btc - previous_btc) + np.abs(target_hype - previous_hype)
    lr = previous_btc * data["lr_BTCUSDT"].to_numpy() + previous_hype * data["lr_HYPEUSDT"].to_numpy() - turnover * probe16.COST_PER_SIDE
    equity = np.exp(np.cumsum(lr))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    return pd.DataFrame({"timestamp": data["timestamp"], "month": data["month"], "log_return": lr, "turnover": turnover, "drawdown_pct": drawdown * 100.0})


def _monthly(bar: pd.DataFrame) -> pd.DataFrame:
    out = bar[(bar["month"] >= EVAL_START) & (bar["month"] < EVAL_END_EXCLUSIVE)].groupby("month", as_index=False).agg(
        log_return=("log_return", "sum"),
        turnover=("turnover", "sum"),
        max_drawdown_pct=("drawdown_pct", "min"),
    )
    out["return_pct"] = (np.exp(out["log_return"]) - 1.0) * 100.0
    return out


def _summary(monthly: pd.DataFrame, trade_count: int, turnover: float) -> dict[str, Any]:
    yearly = {year: (np.exp(group["log_return"].sum()) - 1.0) * 100.0 for year, group in monthly.groupby(monthly["month"].str[:4])}
    min_target = min(yearly.get("2025", -999.0), yearly.get("2026", -999.0))
    max_drawdown = float(monthly["max_drawdown_pct"].min()) if len(monthly) else 0.0
    return {
        "return_2025_pct": yearly.get("2025", 0.0),
        "return_2026_pct": yearly.get("2026", 0.0),
        "min_target_year_return_pct": float(min_target),
        "max_drawdown_pct": max_drawdown,
        "losing_months": int((monthly["return_pct"] <= 0).sum()) if len(monthly) else 0,
        "min_monthly_return_pct": float(monthly["return_pct"].min()) if len(monthly) else 0.0,
        "trade_count": int(trade_count),
        "turnover": float(turnover),
        "hard_pass_relaxed": bool(min_target > REQUIRED_YEAR_RETURN_PCT and max_drawdown >= MAX_DRAWDOWN_LIMIT_PCT),
    }


def _label_summary(labels: pd.DataFrame) -> dict[str, Any]:
    return {
        "event_label_rows": int(len(labels)),
        "non_cash_rows": int((labels["action"] != "cash").sum()),
        "unique_labels": int(labels["label"].nunique()),
        "action_counts": labels["action"].value_counts().to_dict(),
    }


def _position_for_action(data: pd.DataFrame, event_index: int, action: str, leverage: float) -> tuple[float, float]:
    hype_shock = _sign(data["ret16_HYPEUSDT"].iloc[event_index] if abs(data["ret16_HYPEUSDT"].iloc[event_index]) >= abs(data["ret96_HYPEUSDT"].iloc[event_index]) else data["ret96_HYPEUSDT"].iloc[event_index])
    btc_shock = _sign(data["ret16_BTCUSDT"].iloc[event_index])
    rel_shock = _sign(data["resid_z16"].iloc[event_index] if data["resid_z16"].iloc[event_index] != 0 else data["rel_ret16"].iloc[event_index])
    if action == "hype_momentum":
        return 0.0, hype_shock * leverage
    if action == "hype_reversal":
        return 0.0, -hype_shock * leverage
    if action == "btc_momentum":
        return btc_shock * leverage, 0.0
    if action == "btc_reversal":
        return -btc_shock * leverage, 0.0
    if action == "pair_momentum":
        return -rel_shock * leverage / 2.0, rel_shock * leverage / 2.0
    if action == "pair_reversal":
        return rel_shock * leverage / 2.0, -rel_shock * leverage / 2.0
    return 0.0, 0.0


def _decision(best: dict[str, Any], best_action: dict[str, Any], oracle: dict[str, Any]) -> dict[str, Any]:
    if best["hard_pass_relaxed"]:
        verdict = "EVENT_STATE_ACTION_WALKFORWARD_PASSES"
        reason = "完整标签严格走步通过放宽门槛，但仍需冻结验证。"
    elif best_action["hard_pass_relaxed"]:
        verdict = "EVENT_STATE_ACTION_ONLY_WALKFORWARD_PASSES"
        reason = "粗动作严格走步通过放宽门槛，但仍需冻结验证。"
    elif oracle["hard_pass_relaxed"]:
        verdict = "EVENT_STATE_LABEL_ORACLE_PASSES_BUT_WALKFORWARD_FAILS"
        reason = "事件标签oracle有空间，但当前简单状态特征/决策树无论预测完整标签还是粗动作，都不能稳定预测未来月份动作。"
    else:
        verdict = "EVENT_STATE_ACTION_PREDICTABILITY_FAILS"
        reason = "连事件级oracle上限也没过，应停止这条动作选择路线。"
    return {"verdict": verdict, "promote_strategy": False, "reason": reason}


def _render_report(summary: dict[str, Any]) -> str:
    oracle = summary["oracle_event_action"]
    best = summary["best_walkforward_policy"]
    action = summary["best_action_only_policy"]
    return "\n".join(
        [
            "# Strategy 57：尾部事件状态动作可预测性审计",
            "",
            "- 这是研究审计，不是实盘策略。",
            "- 目标：用事件发生当时已经知道的状态，预测该顺势还是反转。",
            "",
            "## 标签oracle",
            "",
            f"- 2025: `{oracle['return_2025_pct']:.2f}%`",
            f"- 2026: `{oracle['return_2026_pct']:.2f}%`",
            f"- 最大回撤: `{oracle['max_drawdown_pct']:.2f}%`",
            f"- 交易数: `{oracle['trade_count']}`",
            f"- hard_pass_relaxed: `{oracle['hard_pass_relaxed']}`",
            "",
            "## 最好严格走步策略",
            "",
            f"- feature_set: `{best['feature_set']}`",
            f"- max_depth: `{best['max_depth']}`",
            f"- min_samples_leaf: `{best['min_samples_leaf']}`",
            f"- 2025: `{best['return_2025_pct']:.2f}%`",
            f"- 2026: `{best['return_2026_pct']:.2f}%`",
            f"- 最大回撤: `{best['max_drawdown_pct']:.2f}%`",
            f"- 亏损月: `{best['losing_months']}`",
            f"- 交易数: `{best['trade_count']}`",
            f"- hard_pass_relaxed: `{best['hard_pass_relaxed']}`",
            "",
            "## 最好粗动作走步策略",
            "",
            f"- feature_set: `{action['feature_set']}`",
            f"- max_depth: `{action['max_depth']}`",
            f"- min_samples_leaf: `{action['min_samples_leaf']}`",
            f"- hold_bars: `{action['hold_bars']}`",
            f"- leverage: `{action['leverage']}`",
            f"- 2025: `{action['return_2025_pct']:.2f}%`",
            f"- 2026: `{action['return_2026_pct']:.2f}%`",
            f"- 最大回撤: `{action['max_drawdown_pct']:.2f}%`",
            f"- 亏损月: `{action['losing_months']}`",
            f"- 交易数: `{action['trade_count']}`",
            f"- hard_pass_relaxed: `{action['hard_pass_relaxed']}`",
            "",
            "## 结论",
            "",
            f"- `{summary['decision']['verdict']}`",
            f"- {summary['decision']['reason']}",
        ]
    ) + "\n"


def _feature_names(feature_set: str) -> list[str]:
    base = [
        "ret16_HYPEUSDT",
        "ret96_HYPEUSDT",
        "ret384_HYPEUSDT",
        "ret16_BTCUSDT",
        "ret96_BTCUSDT",
        "ret384_BTCUSDT",
        "rel_ret16",
        "rel_ret96",
        "resid_z16",
        "shock_sign",
        "trend_align",
        "btc_align",
    ]
    if feature_set == "market_only":
        return base
    if feature_set == "market_plus_time":
        return base + ["month_num", "day_num", "hour_float", "event_index_frac"]
    raise ValueError(feature_set)


def _feature_row(data: pd.DataFrame, i: int, feature_set: str) -> dict[str, float]:
    return {name: float(data[name].iloc[i]) for name in _feature_names(feature_set)}


def _label(action: str, btc_target: float, hype_target: float, hold: int) -> str:
    return f"{action}|{btc_target:.3f}|{hype_target:.3f}|{int(hold)}"


def _parse_label(label: str) -> tuple[str, float, float, int]:
    action, btc, hype, hold = label.split("|")
    return action, float(btc), float(hype), int(hold)


def _sign(value: float) -> int:
    return 1 if value > 0 else (-1 if value < 0 else 0)


def _score(row: dict[str, Any] | None) -> tuple[float, float]:
    if row is None:
        return (-999.0, -999.0)
    return (float(row.get("min_target_year_return_pct", -999.0)), float(row.get("max_drawdown_pct", -999.0)))


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
