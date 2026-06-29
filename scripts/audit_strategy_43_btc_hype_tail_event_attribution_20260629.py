from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_strategy_41_btc_hype_relaxed_drawdown_20260629 as s41


OUT_DIR = ROOT / "artifacts" / "strategy_43_btc_hype_tail_event_attribution_20260629"
SRC41 = ROOT / "artifacts" / "strategy_41_btc_hype_relaxed_drawdown_20260629"
SRC42 = ROOT / "artifacts" / "strategy_42_btc_hype_state_predictability_20260629"
EVAL_START = "2025-06"
EVAL_END = "2026-06"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    oracle = pd.read_csv(SRC41 / "oracle_drawdown_capped_monthly.csv")
    scan = pd.read_csv(SRC41 / "candidate_scan.csv")
    panel, _ = s41._load_or_fetch_panel()
    market = s41._market(panel)
    oracle_pnl = _oracle_bar_pnl(oracle, scan, market)
    events = _tail_events()
    joined = oracle_pnl.merge(events, on="timestamp", how="left").fillna({"event_window": False, "tail_event": False})
    monthly = _monthly(joined)
    summary = _summary(joined, monthly)

    joined.to_csv(OUT_DIR / "oracle_bar_pnl_with_tail_events.csv", index=False)
    monthly.to_csv(OUT_DIR / "monthly_tail_event_attribution.csv", index=False)
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _oracle_bar_pnl(oracle: pd.DataFrame, scan: pd.DataFrame, market: dict[str, Any]) -> pd.DataFrame:
    rows = []
    scan_by_id = {r.candidate_id: r._asdict() for r in scan.itertuples(index=False)}
    for row in oracle.itertuples(index=False):
        if not (EVAL_START <= row.month < EVAL_END):
            continue
        candidate_id = row.candidate_id
        if candidate_id not in scan_by_id:
            continue
        candidate = scan_by_id[candidate_id]
        sim = s41._simulate(market, s41._target_for_candidate(candidate, market))
        part = sim[sim["month"] == row.month].copy()
        part["candidate_id"] = candidate_id
        rows.append(part)
    return pd.concat(rows, ignore_index=True)


def _tail_events() -> pd.DataFrame:
    klines = pd.read_csv(SRC42 / "btc_hype_15m_klines_rest_2025_05_2026_05.csv.gz")
    klines["timestamp"] = pd.to_datetime(klines["timestamp"], utc=True, format="mixed")
    idx = pd.date_range("2025-05-01", "2026-06-01", freq="15min", tz="UTC", inclusive="left")
    wide = pd.DataFrame({"timestamp": idx})
    for symbol in ["BTCUSDT", "HYPEUSDT"]:
        s = klines[klines["symbol"] == symbol].set_index("timestamp")["close"].reindex(idx).ffill()
        wide[f"close_{symbol}"] = s.to_numpy()
        wide[f"valid_{symbol}"] = klines[klines["symbol"] == symbol].set_index("timestamp")["close"].reindex(idx).notna().to_numpy()
        for bars in [16, 96]:
            wide[f"ret{bars}_{symbol}"] = np.log(s / s.shift(bars)).replace([np.inf, -np.inf], np.nan).fillna(0).to_numpy()
    resid16 = wide["ret16_HYPEUSDT"] - wide["ret16_BTCUSDT"]
    resid_scale = resid16.rolling(96 * 30, min_periods=96).std().replace(0, np.nan)
    wide["resid_z16"] = (resid16 / resid_scale).replace([np.inf, -np.inf], np.nan).fillna(0)
    wide["tail_event"] = (
        wide["valid_HYPEUSDT"]
        & (
            (wide["ret16_HYPEUSDT"].abs() >= 0.05)
            | (wide["ret96_HYPEUSDT"].abs() >= 0.12)
            | (wide["resid_z16"].abs() >= 2.5)
        )
    )
    wide["event_window"] = wide["tail_event"].rolling(385, center=True, min_periods=1).max().astype(bool)
    return wide[["timestamp", "tail_event", "event_window", "ret16_HYPEUSDT", "ret96_HYPEUSDT", "resid_z16"]]


def _monthly(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month, group in df.groupby("month"):
        inside = group[group["event_window"]]
        outside = group[~group["event_window"]]
        pos_total = group["log_return"].clip(lower=0).sum()
        rows.append(
            {
                "month": month,
                "log_return": group["log_return"].sum(),
                "return_pct": (math.exp(group["log_return"].sum()) - 1.0) * 100.0,
                "event_window_bar_share": len(inside) / len(group) if len(group) else 0.0,
                "net_log_inside_event_window": inside["log_return"].sum(),
                "net_log_outside_event_window": outside["log_return"].sum(),
                "positive_log_inside_share": inside["log_return"].clip(lower=0).sum() / pos_total if pos_total > 0 else 0.0,
                "candidate_id": group["candidate_id"].iloc[0],
            }
        )
    return pd.DataFrame(rows)


def _summary(df: pd.DataFrame, monthly: pd.DataFrame) -> dict[str, Any]:
    inside = df[df["event_window"]]
    outside = df[~df["event_window"]]
    pos_total = df["log_return"].clip(lower=0).sum()
    yearly = {year: (math.exp(group["log_return"].sum()) - 1.0) * 100.0 for year, group in df.groupby(df["month"].str[:4])}
    positive_share = inside["log_return"].clip(lower=0).sum() / pos_total if pos_total > 0 else 0.0
    verdict = "TAIL_EVENTS_NOT_DOMINANT"
    if positive_share >= 0.7 and inside["log_return"].sum() > outside["log_return"].sum():
        verdict = "TAIL_EVENTS_DOMINATE_ORACLE_PNL"
    return {
        "status": "strategy_43_btc_hype_tail_event_attribution_ready",
        "strategy_id": "strategy_43_btc_hype_tail_event_attribution_20260629",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "purpose": "Check whether Strategy 41 drawdown-capped oracle PnL is concentrated around pre-defined BTC/HYPE tail-event windows.",
        "event_definition": {
            "hype_ret16_abs_gte": 0.05,
            "hype_ret96_abs_gte": 0.12,
            "hype_minus_btc_resid_z16_abs_gte": 2.5,
            "window_hours_each_side": 48,
        },
        "return_2025_pct": yearly.get("2025", 0.0),
        "return_2026_ytd_pct": yearly.get("2026", 0.0),
        "event_window_bar_share": float(df["event_window"].mean()),
        "tail_event_bar_share": float(df["tail_event"].mean()),
        "net_log_inside_event_window": float(inside["log_return"].sum()),
        "net_log_outside_event_window": float(outside["log_return"].sum()),
        "positive_log_inside_event_window_share": float(positive_share),
        "monthly": _json_ready(monthly.to_dict(orient="records")),
        "decision": {"verdict": verdict, "promote_strategy": False},
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "oracle_bar_pnl_with_tail_events": _rel(OUT_DIR / "oracle_bar_pnl_with_tail_events.csv"),
            "monthly_tail_event_attribution": _rel(OUT_DIR / "monthly_tail_event_attribution.csv"),
        },
    }


def _report(summary: dict[str, Any]) -> str:
    return f"""# 43号 BTC+HYPE 尾部事件归因审计

本审计不是策略，只检查 41号回撤限制版看答案 oracle 的利润是否集中在极端事件附近。

## 结果

- 2025：`{summary["return_2025_pct"]:.2f}%`
- 2026 YTD：`{summary["return_2026_ytd_pct"]:.2f}%`
- 事件窗口占全部15分钟K线比例：`{summary["event_window_bar_share"]:.2%}`
- 正收益 log 里落在事件窗口的比例：`{summary["positive_log_inside_event_window_share"]:.2%}`
- 事件窗口内净 log 收益：`{summary["net_log_inside_event_window"]:.4f}`
- 事件窗口外净 log 收益：`{summary["net_log_outside_event_window"]:.4f}`

## 判断

`{summary["decision"]["verdict"]}`
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
