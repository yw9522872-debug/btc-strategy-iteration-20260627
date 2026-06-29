from __future__ import annotations

import importlib.util
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_49_btc_hype_frozen_47_latest_public_20260629"
SRC44 = ROOT / "artifacts" / "strategy_44_btc_hype_tail_event_action_oracle_20260629"
SCRIPT45 = ROOT / "scripts" / "audit_strategy_45_btc_hype_tail_event_fitted_policy_20260629.py"
BASE = "https://fapi.binance.com"
INTERVAL_MS = 15 * 60 * 1000
COST_PER_SIDE = 0.001
FETCH_START = pd.Timestamp("2026-05-01T00:00:00Z")
EVAL_MONTH = "2026-06"
POLICIES = [
    {
        "name": "strategy_47_best",
        "feature_set": "market_plus_time",
        "max_depth": 5,
        "min_samples_leaf": 3,
        "position_scale": 0.8,
        "stop_loss": None,
        "trailing_stop": -0.10,
        "take_profit": 0.20,
    },
    {
        "name": "strategy_47_market_only",
        "feature_set": "market_only",
        "max_depth": 6,
        "min_samples_leaf": 3,
        "position_scale": 0.65,
        "stop_loss": None,
        "trailing_stop": -0.08,
        "take_profit": 0.50,
    },
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    s45 = _load_strategy45()
    train_data = s45._load_data()
    event_threshold, min_gap = s45._load_44_config()
    oracle_trades = pd.read_csv(SRC44 / "best_oracle_trades.csv")
    training = s45._oracle_training_rows(train_data, s45._event_mask(train_data, event_threshold), oracle_trades, min_gap)
    training["month"] = [train_data["month"].iloc[int(i)] for i in training["event_index"]]
    training = training[training["month"] < EVAL_MONTH]

    server_time_ms = int(_get_json("/fapi/v1/time", {})["serverTime"])
    end = (pd.to_datetime(server_time_ms, unit="ms", utc=True) - pd.Timedelta(minutes=15)).floor("15min")
    data, quality = _load_latest_panel(end)
    event = _event_mask(data, event_threshold)

    rows = []
    trade_tables = []
    monthly_tables = []
    for policy in POLICIES:
        trades = _predict_trades(s45, data, event, training, policy, min_gap)
        bar, used = _simulate_trades(data, trades, policy)
        monthly = _monthly(bar)
        summary = _summary(monthly, len(used), float(monthly["turnover"].sum()) if len(monthly) else 0.0)
        row = {**policy, **summary}
        rows.append(row)
        used["policy"] = policy["name"] if len(used) else policy["name"]
        monthly["policy"] = policy["name"] if len(monthly) else policy["name"]
        trade_tables.append(used)
        monthly_tables.append(monthly)

    result = pd.DataFrame(rows).sort_values(["return_pct", "max_drawdown_pct"], ascending=[False, False])
    trades_out = pd.concat(trade_tables, ignore_index=True) if trade_tables else pd.DataFrame()
    monthly_out = pd.concat(monthly_tables, ignore_index=True) if monthly_tables else pd.DataFrame()
    result.to_csv(OUT_DIR / "frozen_policy_latest_summary.csv", index=False)
    trades_out.to_csv(OUT_DIR / "frozen_policy_latest_trades.csv", index=False)
    monthly_out.to_csv(OUT_DIR / "frozen_policy_latest_monthly.csv", index=False)

    best = result.iloc[0].to_dict() if len(result) else {}
    summary = {
        "status": "strategy_49_btc_hype_frozen_47_latest_public_ready",
        "strategy_id": "strategy_49_btc_hype_frozen_47_latest_public_20260629",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "purpose": "Freeze Strategy 47 parameters and test them on the latest public 2026-06 BTC/HYPE data without rescanning parameters.",
        "why_strategy_49": "Local uncommitted Strategy 48 public Jesse files already exist; BTC/HYPE frozen validation uses the next unused number.",
        "data": {
            "source": "Binance USD-M futures public REST",
            "symbols": ["BTCUSDT", "HYPEUSDT"],
            "fetch_start": str(FETCH_START),
            "last_closed_15m_bar": str(end),
            "eval_month": EVAL_MONTH,
            "quality": quality,
        },
        "leakage": {
            "event_detection_uses_closed_past_bars": True,
            "current_month_labels_used_for_current_month": False,
            "parameters_frozen_from_strategy_47": True,
            "parameters_rescanned_on_latest_data": False,
            "tradable_strategy": False,
        },
        "policies": _json_ready(rows),
        "best_policy": _json_ready(best),
        "decision": _decision(result),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "policy_summary": _rel(OUT_DIR / "frozen_policy_latest_summary.csv"),
            "monthly": _rel(OUT_DIR / "frozen_policy_latest_monthly.csv"),
            "trades": _rel(OUT_DIR / "frozen_policy_latest_trades.csv"),
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


def _load_latest_panel(end: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, Any]]:
    start_ms = int(FETCH_START.timestamp() * 1000)
    end_ms = int((end + pd.Timedelta(minutes=15)).timestamp() * 1000)
    klines = []
    premiums = []
    fundings = []
    for symbol in ["BTCUSDT", "HYPEUSDT"]:
        klines.extend(_klines("/fapi/v1/klines", symbol, start_ms, end_ms, "close"))
        premiums.extend(_klines("/fapi/v1/premiumIndexKlines", symbol, start_ms, end_ms, "premium_close"))
        fundings.extend(_funding(symbol, start_ms, end_ms))
    k = pd.DataFrame(klines)
    p = pd.DataFrame(premiums)
    f = pd.DataFrame(fundings)
    k.to_csv(OUT_DIR / "latest_klines.csv.gz", index=False)
    p.to_csv(OUT_DIR / "latest_premium.csv.gz", index=False)
    f.to_csv(OUT_DIR / "latest_funding.csv", index=False)

    idx = pd.date_range(FETCH_START, end, freq="15min", tz="UTC")
    df = pd.DataFrame({"timestamp": idx})
    quality: dict[str, Any] = {}
    for symbol in ["BTCUSDT", "HYPEUSDT"]:
        s = k[k["symbol"] == symbol].set_index("timestamp")
        close = s["close"].reindex(idx).ffill()
        valid = s["close"].reindex(idx).notna()
        df[f"valid_{symbol}"] = valid.to_numpy()
        df[f"lr_{symbol}"] = np.log(close / close.shift(1)).replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy()
        for bars in [16, 96, 384]:
            df[f"ret{bars}_{symbol}"] = np.log(close / close.shift(bars)).replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy()
        quality[symbol] = {
            "rows": int(len(s)),
            "duplicates": int(s.index.duplicated().sum()),
            "missing_15m_rows": int((~valid).sum()),
        }

    resid16 = df["ret16_HYPEUSDT"] - df["ret16_BTCUSDT"]
    resid_scale = resid16.rolling(96 * 30, min_periods=96).std().replace(0, np.nan)
    df["resid_z16"] = (resid16 / resid_scale).replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy()
    prem = p[p["symbol"] == "HYPEUSDT"].set_index("timestamp")["premium_close"].reindex(idx).ffill().fillna(0)
    fund = f[f["symbol"] == "HYPEUSDT"].set_index("timestamp")["funding_rate"].reindex(idx).ffill().fillna(0)
    df["premium96"] = prem.rolling(96, min_periods=1).mean().to_numpy()
    df["fund672"] = fund.rolling(96 * 7, min_periods=1).sum().to_numpy()
    df["shock_sign"] = np.sign(np.where(np.abs(df["ret16_HYPEUSDT"]) >= np.abs(df["ret96_HYPEUSDT"]), df["ret16_HYPEUSDT"], df["ret96_HYPEUSDT"]))
    df["trend_align"] = np.sign(df["ret384_HYPEUSDT"]) * df["shock_sign"]
    df["crowd_align"] = np.sign(df["premium96"] + df["fund672"]) * df["shock_sign"]
    df["month"] = df["timestamp"].dt.strftime("%Y-%m")
    df["month_num"] = df["timestamp"].dt.month
    df["day_num"] = df["timestamp"].dt.day
    df["hour_float"] = df["timestamp"].dt.hour + df["timestamp"].dt.minute / 60.0
    df["event_index_frac"] = np.arange(len(df)) / max(1, len(df) - 1)
    return df, quality


def _event_mask(data: pd.DataFrame, event_threshold: tuple[float, float, float]) -> np.ndarray:
    ret16_thr, ret96_thr, resid_thr = event_threshold
    month = data["month"].to_numpy()
    return (
        data["valid_HYPEUSDT"].to_numpy()
        & (month == EVAL_MONTH)
        & (
            (np.abs(data["ret16_HYPEUSDT"].to_numpy()) >= ret16_thr)
            | (np.abs(data["ret96_HYPEUSDT"].to_numpy()) >= ret96_thr)
            | (np.abs(data["resid_z16"].to_numpy()) >= resid_thr)
        )
    )


def _predict_trades(s45, data: pd.DataFrame, event: np.ndarray, training: pd.DataFrame, policy: dict[str, Any], min_gap: int) -> list[dict[str, Any]]:
    features = s45._feature_names(policy["feature_set"])
    clf = DecisionTreeClassifier(max_depth=policy["max_depth"], min_samples_leaf=policy["min_samples_leaf"], random_state=47)
    clf.fit(training[features].to_numpy(), training["label"].to_numpy())
    out = []
    next_ok = 0
    for i in np.where(event)[0]:
        if i < next_ok:
            continue
        x = np.array([[float(data[name].iloc[i]) for name in features]])
        action, th, tb, hold = s45._parse_label(str(clf.predict(x)[0]))
        if action == "cash" or hold <= 0:
            next_ok = i + min_gap
            continue
        start = i + 1
        end = min(len(data), start + hold)
        out.append({"event_index": int(i), "start": int(start), "end": int(end), "hype_target": float(th), "btc_target": float(tb), "month": EVAL_MONTH, "action": action, "hold_bars": int(hold)})
        next_ok = max(i + min_gap, end)
    return out


def _simulate_trades(data: pd.DataFrame, base_trades: list[dict[str, Any]], policy: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    lr_h = data["lr_HYPEUSDT"].to_numpy()
    lr_b = data["lr_BTCUSDT"].to_numpy()
    bar_lr = np.zeros(len(data))
    turnover = np.zeros(len(data))
    rows = []
    active_until = 0
    scale = policy["position_scale"]
    for trade in base_trades:
        start, end = int(trade["start"]), int(trade["end"])
        if start < active_until or start >= end:
            continue
        h = float(trade["hype_target"]) * scale
        b = float(trade["btc_target"]) * scale
        eq = peak = 1.0
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
            hit_stop = policy["stop_loss"] is not None and ret <= policy["stop_loss"]
            hit_trail = policy["trailing_stop"] is not None and dd <= policy["trailing_stop"]
            hit_take = policy["take_profit"] is not None and ret >= policy["take_profit"]
            if hit_stop or hit_trail or hit_take or j == end - 1:
                if hit_stop:
                    exit_reason = "stop_loss"
                elif hit_trail:
                    exit_reason = "trailing_stop"
                elif hit_take:
                    exit_reason = "take_profit"
                r -= COST_PER_SIDE * (abs(h) + abs(b))
                turnover[j] += abs(h) + abs(b)
                bar_lr[j] += r
                trade_lr += r
                exit_i = j
                break
            bar_lr[j] += r
            trade_lr += r
        active_until = exit_i + 1
        rows.append({**trade, "policy": policy["name"], "scaled_hype_target": h, "scaled_btc_target": b, "exit_index": int(exit_i), "entry_timestamp": data["timestamp"].iloc[start], "exit_timestamp": data["timestamp"].iloc[exit_i], "exit_reason": exit_reason, "trade_log_return": float(trade_lr), "trade_return_pct": float((math.exp(trade_lr) - 1.0) * 100.0)})

    eq_curve = np.exp(np.cumsum(bar_lr))
    dd_curve = eq_curve / np.maximum.accumulate(eq_curve) - 1.0
    return pd.DataFrame({"timestamp": data["timestamp"], "month": data["month"], "log_return": bar_lr, "turnover": turnover, "drawdown_pct": dd_curve * 100.0}), pd.DataFrame(rows)


def _monthly(bar: pd.DataFrame) -> pd.DataFrame:
    out = bar[bar["month"] == EVAL_MONTH].groupby("month", as_index=False).agg(
        log_return=("log_return", "sum"),
        turnover=("turnover", "sum"),
        max_drawdown_pct=("drawdown_pct", "min"),
    )
    out["return_pct"] = (np.exp(out["log_return"]) - 1.0) * 100.0
    return out


def _summary(monthly: pd.DataFrame, trade_count: int, turnover: float) -> dict[str, Any]:
    if monthly.empty:
        return {"return_pct": 0.0, "max_drawdown_pct": 0.0, "trade_count": int(trade_count), "turnover": turnover}
    return {"return_pct": float(monthly["return_pct"].iloc[0]), "max_drawdown_pct": float(monthly["max_drawdown_pct"].iloc[0]), "trade_count": int(trade_count), "turnover": turnover}


def _klines(path: str, symbol: str, start_ms: int, end_ms: int, value_name: str) -> list[dict[str, Any]]:
    rows = []
    cursor = start_ms
    while cursor < end_ms:
        data = _get_json(path, {"symbol": symbol, "interval": "15m", "startTime": cursor, "endTime": min(end_ms, cursor + INTERVAL_MS * 1499), "limit": 1500})
        if not data:
            cursor += INTERVAL_MS * 1500
            continue
        for row in data:
            rows.append({"timestamp": pd.to_datetime(int(row[0]), unit="ms", utc=True), "symbol": symbol, value_name: float(row[4])})
        cursor = max(int(data[-1][0]) + INTERVAL_MS, cursor + INTERVAL_MS)
    return rows


def _funding(symbol: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
    rows = []
    cursor = start_ms
    while cursor < end_ms:
        data = _get_json("/fapi/v1/fundingRate", {"symbol": symbol, "startTime": cursor, "endTime": end_ms, "limit": 1000})
        if not data:
            cursor += 7 * 24 * 60 * 60 * 1000
            continue
        rows.extend({"timestamp": pd.to_datetime(int(row["fundingTime"]), unit="ms", utc=True), "symbol": symbol, "funding_rate": float(row["fundingRate"])} for row in data)
        cursor = max(int(data[-1]["fundingTime"]) + 1, cursor + 1)
    return rows


def _get_json(path: str, params: dict[str, Any]) -> Any:
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            if attempt == 4:
                raise
            time.sleep(1 + attempt)
    raise RuntimeError("unreachable")


def _decision(result: pd.DataFrame) -> dict[str, Any]:
    if result.empty:
        return {"verdict": "FROZEN_47_LATEST_NO_TRADES", "promote_strategy": False, "reason": "最新公开数据没有可评估交易。"}
    best = result.iloc[0]
    if float(best["return_pct"]) > 0 and float(best["max_drawdown_pct"]) >= -50.0:
        return {"verdict": "FROZEN_47_LATEST_PARTIAL_MONTH_POSITIVE", "promote_strategy": False, "reason": "冻结47号参数在最新未调参数据上暂时为正，但仍只是部分月份影子验证，不能实盘。"}
    return {"verdict": "FROZEN_47_LATEST_PARTIAL_MONTH_FAILS", "promote_strategy": False, "reason": "冻结47号参数在最新未调参数据上没有通过正收益/回撤 sanity check。"}


def _report(summary: dict[str, Any]) -> str:
    b = summary["best_policy"]
    return f"""# 49号 BTC+HYPE 冻结47号参数最新公开数据验证

本审计不是实盘策略。它冻结47号参数，不再调参，只补最新 Binance 公共数据做后推检查。

## 最新数据

- 评估月份：`{summary["data"]["eval_month"]}`
- 最后一根15分钟K线：`{summary["data"]["last_closed_15m_bar"]}`

## 最好冻结结果

- 策略：`{b.get("name")}`
- 2026-06 当前收益：`{b.get("return_pct", 0):.2f}%`
- 最大回撤：`{b.get("max_drawdown_pct", 0):.2f}%`
- 交易数：`{b.get("trade_count", 0)}`

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
