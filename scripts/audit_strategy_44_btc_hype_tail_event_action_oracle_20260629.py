from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_44_btc_hype_tail_event_action_oracle_20260629"
SRC42 = ROOT / "artifacts" / "strategy_42_btc_hype_state_predictability_20260629"
COST_PER_SIDE = 0.001
EVAL_START = "2025-06"
EVAL_END = "2026-06"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = _load_data()
    configs = []
    for event_threshold in [(0.04, 0.10, 2.0), (0.05, 0.12, 2.5), (0.06, 0.15, 3.0)]:
        for min_gap in [16, 32, 64, 96]:
            for max_trade_dd in [-0.20, -0.30, -0.40]:
                configs.append({"event_threshold": event_threshold, "min_gap": min_gap, "max_trade_dd": max_trade_dd})

    rows = []
    best_monthly = None
    best_trades = None
    best_score = (-999.0, -999.0)
    for cfg in configs:
        trades, monthly, summary = _run_oracle(data, **cfg)
        rows.append({**_flat_cfg(cfg), **summary})
        if _score(summary) > best_score:
            best_monthly = monthly
            best_trades = trades
            best_score = _score(summary)

    scan = pd.DataFrame(rows).sort_values(["hard_pass_relaxed", "min_target_year_return_pct", "max_drawdown_pct"], ascending=[False, False, False])
    best = scan.iloc[0].to_dict()
    if best_monthly is None or best_trades is None:
        best_trades, best_monthly, _ = _run_oracle(data, event_threshold=(0.05, 0.12, 2.5), min_gap=64, max_trade_dd=-0.30)

    scan.to_csv(OUT_DIR / "config_scan.csv", index=False)
    best_trades.to_csv(OUT_DIR / "best_oracle_trades.csv", index=False)
    best_monthly.to_csv(OUT_DIR / "best_oracle_monthly.csv", index=False)

    summary = {
        "status": "strategy_44_btc_hype_tail_event_action_oracle_ready",
        "strategy_id": "strategy_44_btc_hype_tail_event_action_oracle_20260629",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "purpose": "Tail-event-after-action oracle upper bound for BTC/HYPE after Strategy 43 showed oracle PnL concentrates around tail events.",
        "leakage": {
            "event_detection_uses_closed_past_bars": True,
            "action_oracle_uses_future_after_event": True,
            "tradable_strategy": False,
        },
        "gate": {"target_years": ["2025", "2026"], "required_return_pct": 100.0, "max_drawdown_limit_pct": -50.0},
        "config_count": len(scan),
        "best_config": _json_ready(best),
        "decision": _decision(best),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "config_scan": _rel(OUT_DIR / "config_scan.csv"),
            "best_oracle_trades": _rel(OUT_DIR / "best_oracle_trades.csv"),
            "best_oracle_monthly": _rel(OUT_DIR / "best_oracle_monthly.csv"),
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
        df[f"close_{symbol}"] = close.to_numpy()
        df[f"valid_{symbol}"] = s["close"].reindex(idx).notna().to_numpy()
        df[f"lr_{symbol}"] = np.log(close / close.shift(1)).replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy()
        for bars in [16, 96, 384]:
            df[f"ret{bars}_{symbol}"] = np.log(close / close.shift(bars)).replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy()
    resid16 = df["ret16_HYPEUSDT"] - df["ret16_BTCUSDT"]
    resid_scale = resid16.rolling(96 * 30, min_periods=96).std().replace(0, np.nan)
    df["resid_z16"] = (resid16 / resid_scale).replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy()
    df["month"] = df["timestamp"].dt.strftime("%Y-%m")
    return df


def _run_oracle(data: pd.DataFrame, event_threshold: tuple[float, float, float], min_gap: int, max_trade_dd: float) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    ret16_thr, ret96_thr, resid_thr = event_threshold
    event = (
        data["valid_HYPEUSDT"].to_numpy()
        & (data["month"].to_numpy() >= EVAL_START)
        & (data["month"].to_numpy() < EVAL_END)
        & (
            (np.abs(data["ret16_HYPEUSDT"].to_numpy()) >= ret16_thr)
            | (np.abs(data["ret96_HYPEUSDT"].to_numpy()) >= ret96_thr)
            | (np.abs(data["resid_z16"].to_numpy()) >= resid_thr)
        )
    )
    event_indexes = np.where(event)[0]
    target_h = np.zeros(len(data))
    target_b = np.zeros(len(data))
    trades = []
    next_ok = 0
    for i in event_indexes:
        if i < next_ok or i + 2 >= len(data):
            continue
        option = _best_action(data, i, max_trade_dd)
        if option["action"] == "cash":
            next_ok = i + min_gap
            continue
        start = i + 1
        end = min(len(data), i + 1 + int(option["hold_bars"]))
        target_h[start:end] = option["hype_target"]
        target_b[start:end] = option["btc_target"]
        trades.append({**option, "event_timestamp": data["timestamp"].iloc[i], "month": data["month"].iloc[i], "event_index": int(i)})
        next_ok = max(i + min_gap, end)

    bar = _simulate(data, target_h, target_b)
    monthly = _monthly(bar)
    return pd.DataFrame(trades), monthly, _summary(monthly, len(event_indexes), len(trades))


def _best_action(data: pd.DataFrame, i: int, max_trade_dd: float) -> dict[str, Any]:
    shock_h = np.sign(data["ret16_HYPEUSDT"].iloc[i] if abs(data["ret16_HYPEUSDT"].iloc[i]) >= abs(data["ret96_HYPEUSDT"].iloc[i]) else data["ret96_HYPEUSDT"].iloc[i])
    shock_b = np.sign(data["ret16_BTCUSDT"].iloc[i])
    resid = np.sign(data["resid_z16"].iloc[i])
    options = [{"action": "cash", "hype_target": 0.0, "btc_target": 0.0, "hold_bars": 0, "trade_log_return": 0.0, "trade_max_drawdown_pct": 0.0}]
    for hold in [16, 32, 64, 96, 192]:
        for lev in [1.0, 2.0, 3.0, 4.0]:
            candidates = [
                ("hype_momentum", shock_h * lev, 0.0),
                ("hype_reversal", -shock_h * lev, 0.0),
                ("btc_momentum", 0.0, shock_b * lev),
                ("btc_reversal", 0.0, -shock_b * lev),
                ("pair_rv_reversal", -resid * lev, resid * lev / 2.0),
            ]
            for action, th, tb in candidates:
                if th == 0 and tb == 0:
                    continue
                stats = _trade_stats(data, i + 1, hold, th, tb)
                if stats["trade_max_drawdown_pct"] >= max_trade_dd * 100.0:
                    options.append({"action": action, "hype_target": th, "btc_target": tb, "hold_bars": hold, **stats})
    return max(options, key=lambda x: x["trade_log_return"])


def _trade_stats(data: pd.DataFrame, start: int, hold: int, th: float, tb: float) -> dict[str, float]:
    end = min(len(data), start + hold)
    if start >= end:
        return {"trade_log_return": 0.0, "trade_return_pct": 0.0, "trade_max_drawdown_pct": 0.0}
    lr = th * data["lr_HYPEUSDT"].to_numpy()[start:end] + tb * data["lr_BTCUSDT"].to_numpy()[start:end]
    lr = lr.copy()
    lr[0] -= COST_PER_SIDE * (abs(th) + abs(tb))
    lr[-1] -= COST_PER_SIDE * (abs(th) + abs(tb))
    eq = np.exp(np.cumsum(lr))
    dd = eq / np.maximum.accumulate(eq) - 1.0
    return {"trade_log_return": float(lr.sum()), "trade_return_pct": float((math.exp(lr.sum()) - 1.0) * 100.0), "trade_max_drawdown_pct": float(dd.min() * 100.0)}


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


def _summary(monthly: pd.DataFrame, event_count: int, trade_count: int) -> dict[str, Any]:
    yearly = {year: (math.exp(group["log_return"].sum()) - 1.0) * 100.0 for year, group in monthly.groupby(monthly["month"].str[:4])}
    min_target = min(yearly.get("2025", -999.0), yearly.get("2026", -999.0))
    max_dd = float(monthly["max_drawdown_pct"].min()) if len(monthly) else 0.0
    return {
        "return_2025_pct": yearly.get("2025", 0.0),
        "return_2026_ytd_pct": yearly.get("2026", 0.0),
        "min_target_year_return_pct": min_target,
        "max_drawdown_pct": max_dd,
        "event_count": int(event_count),
        "trade_count": int(trade_count),
        "turnover": float(monthly["turnover"].sum()) if len(monthly) else 0.0,
        "hard_pass_relaxed": bool(min_target > 100.0 and max_dd >= -50.0),
    }


def _score(row: dict[str, Any]) -> tuple[float, float]:
    return (float(row.get("min_target_year_return_pct", -999.0)), float(row.get("max_drawdown_pct", -999.0)))


def _flat_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    a, b, c = cfg["event_threshold"]
    return {"ret16_abs_thr": a, "ret96_abs_thr": b, "resid_z16_abs_thr": c, "min_gap": cfg["min_gap"], "max_trade_dd": cfg["max_trade_dd"]}


def _decision(best: dict[str, Any]) -> dict[str, Any]:
    if best["hard_pass_relaxed"]:
        verdict = "TAIL_EVENT_ACTION_ORACLE_PASSES_RELAXED_GATE"
        reason = "事件发生后看答案选择动作能通过放宽门槛，但这仍然使用未来收益选择动作，不能交易。"
    else:
        verdict = "TAIL_EVENT_ACTION_ORACLE_FAILS_RELAXED_GATE"
        reason = "事件后动作看答案上限也没通过放宽门槛，BTC+HYPE主线应停止。"
    return {"verdict": verdict, "promote_strategy": False, "reason": reason}


def _report(summary: dict[str, Any]) -> str:
    b = summary["best_config"]
    return f"""# 44号 BTC+HYPE 尾部事件后动作 oracle

本审计不是策略，不能交易。它只检查：极端事件发生后，如果看答案选择顺势/反转/配对/空仓，理论上还有没有足够收益。

## 最好配置

- 2025：`{b["return_2025_pct"]:.2f}%`
- 2026 YTD：`{b["return_2026_ytd_pct"]:.2f}%`
- 最大回撤：`{b["max_drawdown_pct"]:.2f}%`
- 事件数：`{b["event_count"]}`
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
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if value is None or pd.isna(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
