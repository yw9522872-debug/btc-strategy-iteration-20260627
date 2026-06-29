from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_45_btc_hype_tail_event_fitted_policy_20260629"
SRC42 = ROOT / "artifacts" / "strategy_42_btc_hype_state_predictability_20260629"
SRC44 = ROOT / "artifacts" / "strategy_44_btc_hype_tail_event_action_oracle_20260629"
COST_PER_SIDE = 0.001
EVAL_START = "2025-06"
EVAL_END = "2026-06"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = _load_data()
    event_threshold, min_gap = _load_44_config()
    event = _event_mask(data, event_threshold)
    oracle_trades = pd.read_csv(SRC44 / "best_oracle_trades.csv")
    training = _oracle_training_rows(data, event, oracle_trades, min_gap)

    policies = []
    best = None
    best_bar = None
    best_trades = None
    best_tree = ""
    for feature_set in ["market_only", "market_plus_time"]:
        feature_names = _feature_names(feature_set)
        x = training[feature_names].to_numpy()
        y = training["label"].to_numpy()
        for max_depth in [3, 4, 5, 6, 8, 12, None]:
            clf = DecisionTreeClassifier(max_depth=max_depth, min_samples_leaf=1, random_state=45)
            clf.fit(x, y)
            target_h, target_b, trades = _apply_tree_policy(data, event, clf, feature_set, min_gap)
            bar = _simulate(data, target_h, target_b)
            monthly = _monthly(bar)
            row = {
                "policy": "decision_tree",
                "feature_set": feature_set,
                "max_depth": -1 if max_depth is None else max_depth,
                "train_accuracy": float(clf.score(x, y)),
                "tree_depth": int(clf.get_depth()),
                "leaf_count": int(clf.get_n_leaves()),
                **_summary(monthly, len(trades), float(monthly["turnover"].sum()) if len(monthly) else 0.0),
            }
            policies.append(row)
            if _score(row) > _score(best):
                best = row
                best_bar = bar
                best_trades = trades
                best_tree = export_text(clf, feature_names=feature_names, max_depth=6)

    target_h, target_b, trades = _apply_lookup_policy(data, event, training, min_gap)
    bar = _simulate(data, target_h, target_b)
    monthly = _monthly(bar)
    lookup_row = {
        "policy": "event_index_lookup",
        "feature_set": "event_index_memory",
        "max_depth": -1,
        "train_accuracy": 1.0,
        "tree_depth": -1,
        "leaf_count": int(training["label"].nunique()),
        **_summary(monthly, len(trades), float(monthly["turnover"].sum()) if len(monthly) else 0.0),
    }
    policies.append(lookup_row)
    if _score(lookup_row) > _score(best):
        best = lookup_row
        best_bar = bar
        best_trades = trades
        best_tree = "event_index -> memorized oracle label"

    if best is None or best_bar is None or best_trades is None:
        raise RuntimeError("no policy evaluated")

    scan = pd.DataFrame(policies).sort_values(["hard_pass_relaxed", "min_target_year_return_pct", "max_drawdown_pct"], ascending=[False, False, False])
    monthly = _monthly(best_bar)
    scan.to_csv(OUT_DIR / "policy_scan.csv", index=False)
    monthly.to_csv(OUT_DIR / "best_policy_monthly.csv", index=False)
    best_trades.to_csv(OUT_DIR / "best_policy_trades.csv", index=False)
    training.to_csv(OUT_DIR / "oracle_training_rows.csv", index=False)
    (OUT_DIR / "best_tree.txt").write_text(best_tree, encoding="utf-8")

    summary = {
        "status": "strategy_45_btc_hype_tail_event_fitted_policy_ready",
        "strategy_id": "strategy_45_btc_hype_tail_event_fitted_policy_20260629",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "purpose": "Strongly fit a fixed tail-event policy from Strategy 44 oracle labels, then inspect whether the fitted policy can pass the relaxed BTC/HYPE gate in sample.",
        "leakage": {
            "event_detection_uses_closed_past_bars": True,
            "policy_fit_uses_same_period_future_oracle_labels": True,
            "best_policy_uses_event_index_memory": bool(best["policy"] == "event_index_lookup"),
            "tradable_strategy": False,
        },
        "gate": {"target_years": ["2025", "2026"], "required_return_pct": 100.0, "max_drawdown_limit_pct": -50.0},
        "event_config": {
            "ret16_abs_thr": event_threshold[0],
            "ret96_abs_thr": event_threshold[1],
            "resid_z16_abs_thr": event_threshold[2],
            "min_gap": min_gap,
            "event_count": int(event.sum()),
            "training_rows": int(len(training)),
            "non_cash_training_rows": int((training["label"] != "cash|0|0|0").sum()),
        },
        "best_policy": _json_ready(best),
        "decision": _decision(best),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "policy_scan": _rel(OUT_DIR / "policy_scan.csv"),
            "best_policy_monthly": _rel(OUT_DIR / "best_policy_monthly.csv"),
            "best_policy_trades": _rel(OUT_DIR / "best_policy_trades.csv"),
            "oracle_training_rows": _rel(OUT_DIR / "oracle_training_rows.csv"),
            "best_tree": _rel(OUT_DIR / "best_tree.txt"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_data() -> pd.DataFrame:
    kl = pd.read_csv(SRC42 / "btc_hype_15m_klines_rest_2025_05_2026_05.csv.gz")
    kl["timestamp"] = pd.to_datetime(kl["timestamp"], utc=True, format="mixed")
    idx = pd.date_range("2025-05-01", "2026-06-01", freq="15min", tz="UTC", inclusive="left")
    df = pd.DataFrame({"timestamp": idx})
    for symbol in ["BTCUSDT", "HYPEUSDT"]:
        s = kl[kl["symbol"] == symbol].set_index("timestamp")
        close = s["close"].reindex(idx).ffill()
        df[f"valid_{symbol}"] = s["close"].reindex(idx).notna().to_numpy()
        df[f"lr_{symbol}"] = np.log(close / close.shift(1)).replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy()
        for bars in [16, 96, 384]:
            df[f"ret{bars}_{symbol}"] = np.log(close / close.shift(bars)).replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy()

    resid16 = df["ret16_HYPEUSDT"] - df["ret16_BTCUSDT"]
    resid_scale = resid16.rolling(96 * 30, min_periods=96).std().replace(0, np.nan)
    df["resid_z16"] = (resid16 / resid_scale).replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy()

    premium = pd.read_csv(SRC42 / "btc_hype_premiumIndexKlines_15m_2025_05_2026_05.csv.gz")
    premium["timestamp"] = pd.to_datetime(premium["timestamp"], utc=True, format="mixed")
    p = premium[premium["symbol"] == "HYPEUSDT"].set_index("timestamp")["premium_close"].reindex(idx).ffill().fillna(0)
    df["premium96"] = p.rolling(96, min_periods=1).mean().to_numpy()

    funding = pd.read_csv(SRC42 / "btc_hype_funding_rate_2025_05_2026_05.csv")
    funding["timestamp"] = pd.to_datetime(funding["timestamp"], utc=True, format="mixed")
    f = funding[funding["symbol"] == "HYPEUSDT"].set_index("timestamp")["funding_rate"].reindex(idx).ffill().fillna(0)
    df["fund672"] = f.rolling(96 * 7, min_periods=1).sum().to_numpy()

    df["shock_sign"] = np.sign(np.where(np.abs(df["ret16_HYPEUSDT"]) >= np.abs(df["ret96_HYPEUSDT"]), df["ret16_HYPEUSDT"], df["ret96_HYPEUSDT"]))
    df["trend_align"] = np.sign(df["ret384_HYPEUSDT"]) * df["shock_sign"]
    df["crowd_align"] = np.sign(df["premium96"] + df["fund672"]) * df["shock_sign"]
    df["month"] = df["timestamp"].dt.strftime("%Y-%m")
    df["month_num"] = df["timestamp"].dt.month
    df["day_num"] = df["timestamp"].dt.day
    df["hour_float"] = df["timestamp"].dt.hour + df["timestamp"].dt.minute / 60.0
    df["event_index_frac"] = np.arange(len(df)) / max(1, len(df) - 1)
    return df


def _load_44_config() -> tuple[tuple[float, float, float], int]:
    summary = json.loads((SRC44 / "summary.json").read_text(encoding="utf-8"))
    best = summary["best_config"]
    return (float(best["ret16_abs_thr"]), float(best["ret96_abs_thr"]), float(best["resid_z16_abs_thr"])), int(best["min_gap"])


def _event_mask(data: pd.DataFrame, event_threshold: tuple[float, float, float]) -> np.ndarray:
    ret16_thr, ret96_thr, resid_thr = event_threshold
    month = data["month"].to_numpy()
    return (
        data["valid_HYPEUSDT"].to_numpy()
        & (month >= EVAL_START)
        & (month < EVAL_END)
        & (
            (np.abs(data["ret16_HYPEUSDT"].to_numpy()) >= ret16_thr)
            | (np.abs(data["ret96_HYPEUSDT"].to_numpy()) >= ret96_thr)
            | (np.abs(data["resid_z16"].to_numpy()) >= resid_thr)
        )
    )


def _oracle_training_rows(data: pd.DataFrame, event: np.ndarray, oracle_trades: pd.DataFrame, min_gap: int) -> pd.DataFrame:
    trade_map = {int(row.event_index): row for row in oracle_trades.itertuples(index=False)}
    rows = []
    next_ok = 0
    for i in np.where(event)[0]:
        if i < next_ok:
            continue
        row = _feature_row(data, int(i), "market_plus_time")
        row["event_index"] = int(i)
        if i in trade_map:
            t = trade_map[i]
            label = _label(str(t.action), float(t.hype_target), float(t.btc_target), int(t.hold_bars))
            row.update({"label": label, "oracle_action": str(t.action), "oracle_hold_bars": int(t.hold_bars)})
            next_ok = max(i + min_gap, i + 1 + int(t.hold_bars))
        else:
            row.update({"label": "cash|0|0|0", "oracle_action": "cash", "oracle_hold_bars": 0})
            next_ok = i + min_gap
        rows.append(row)
    return pd.DataFrame(rows)


def _feature_names(feature_set: str) -> list[str]:
    base = [
        "ret16_HYPEUSDT",
        "ret96_HYPEUSDT",
        "ret384_HYPEUSDT",
        "ret16_BTCUSDT",
        "ret96_BTCUSDT",
        "ret384_BTCUSDT",
        "resid_z16",
        "premium96",
        "fund672",
        "shock_sign",
        "trend_align",
        "crowd_align",
    ]
    if feature_set == "market_only":
        return base
    if feature_set == "market_plus_time":
        return base + ["month_num", "day_num", "hour_float", "event_index_frac"]
    raise ValueError(feature_set)


def _feature_row(data: pd.DataFrame, i: int, feature_set: str) -> dict[str, float]:
    return {name: float(data[name].iloc[i]) for name in _feature_names(feature_set)}


def _apply_tree_policy(data: pd.DataFrame, event: np.ndarray, clf: DecisionTreeClassifier, feature_set: str, min_gap: int) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    target_h = np.zeros(len(data))
    target_b = np.zeros(len(data))
    trades = []
    next_ok = 0
    feature_names = _feature_names(feature_set)
    for i in np.where(event)[0]:
        if i < next_ok:
            continue
        x = np.array([[float(data[name].iloc[i]) for name in feature_names]])
        action, th, tb, hold = _parse_label(str(clf.predict(x)[0]))
        if action == "cash" or hold <= 0:
            next_ok = i + min_gap
            continue
        start = i + 1
        end = min(len(data), start + hold)
        target_h[start:end] = th
        target_b[start:end] = tb
        trades.append({"event_index": int(i), "event_timestamp": data["timestamp"].iloc[i], "month": data["month"].iloc[i], "action": action, "hype_target": th, "btc_target": tb, "hold_bars": hold})
        next_ok = max(i + min_gap, end)
    return target_h, target_b, pd.DataFrame(trades)


def _apply_lookup_policy(data: pd.DataFrame, event: np.ndarray, training: pd.DataFrame, min_gap: int) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    label_by_event = {int(row.event_index): str(row.label) for row in training.itertuples(index=False)}
    target_h = np.zeros(len(data))
    target_b = np.zeros(len(data))
    trades = []
    next_ok = 0
    for i in np.where(event)[0]:
        if i < next_ok:
            continue
        action, th, tb, hold = _parse_label(label_by_event.get(int(i), "cash|0|0|0"))
        if action == "cash" or hold <= 0:
            next_ok = i + min_gap
            continue
        start = i + 1
        end = min(len(data), start + hold)
        target_h[start:end] = th
        target_b[start:end] = tb
        trades.append({"event_index": int(i), "event_timestamp": data["timestamp"].iloc[i], "month": data["month"].iloc[i], "action": action, "hype_target": th, "btc_target": tb, "hold_bars": hold})
        next_ok = max(i + min_gap, end)
    return target_h, target_b, pd.DataFrame(trades)


def _simulate(data: pd.DataFrame, target_h: np.ndarray, target_b: np.ndarray) -> pd.DataFrame:
    prev_h = np.r_[0.0, target_h[:-1]]
    prev_b = np.r_[0.0, target_b[:-1]]
    active_h = np.r_[0.0, target_h[:-1]]
    active_b = np.r_[0.0, target_b[:-1]]
    turnover = np.abs(target_h - prev_h) + np.abs(target_b - prev_b)
    lr = active_h * data["lr_HYPEUSDT"].to_numpy() + active_b * data["lr_BTCUSDT"].to_numpy() - COST_PER_SIDE * turnover
    eq = np.exp(np.cumsum(lr))
    dd = eq / np.maximum.accumulate(eq) - 1.0
    return pd.DataFrame({"timestamp": data["timestamp"], "month": data["month"], "log_return": lr, "turnover": turnover, "drawdown_pct": dd * 100.0})


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
    return (float(row.get("min_target_year_return_pct", -999.0)), float(row.get("max_drawdown_pct", -999.0)))


def _label(action: str, hype_target: float, btc_target: float, hold_bars: int) -> str:
    return f"{action}|{hype_target:g}|{btc_target:g}|{hold_bars}"


def _parse_label(label: str) -> tuple[str, float, float, int]:
    action, th, tb, hold = label.split("|")
    return action, float(th), float(tb), int(hold)


def _decision(best: dict[str, Any]) -> dict[str, Any]:
    if best["hard_pass_relaxed"]:
        return {
            "verdict": "TAIL_EVENT_FITTED_POLICY_PASSES_IN_SAMPLE_RELAXED_GATE",
            "promote_strategy": False,
            "reason": "强过拟合策略在同一段历史里通过放宽门槛，但训练标签来自44号未来oracle，不能当实盘策略。",
        }
    return {
        "verdict": "TAIL_EVENT_FITTED_POLICY_FAILS_RELAXED_GATE",
        "promote_strategy": False,
        "reason": "把44号oracle压成固定规则后仍不能通过放宽门槛。",
    }


def _report(summary: dict[str, Any]) -> str:
    b = summary["best_policy"]
    return f"""# 45号 BTC+HYPE 尾部事件强过拟合策略

本审计按用户要求强行过拟合：用44号未来oracle当老师，再拟合成固定事件策略。它只做研究，不是实盘策略。

## 最好结果

- 策略类型：`{b["policy"]}`
- 特征集：`{b["feature_set"]}`
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
