from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import audit_strategy_16_new_family_probe_20260627 as probe16


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_55_btc_hype_tail_event_core_signal_20260630"
STRATEGY_ID = "strategy_55_btc_hype_tail_event_core_signal_20260630"
PANEL_41 = ROOT / "artifacts" / "strategy_41_btc_hype_relaxed_drawdown_20260629" / "btc_hype_close_panel_15m_2020_2026_05.csv.gz"
LATEST_49 = ROOT / "artifacts" / "strategy_49_btc_hype_frozen_47_latest_public_20260629" / "latest_klines.csv.gz"
EVAL_START = "2025-06"
EVAL_END_EXCLUSIVE = "2026-07"
TARGET_YEARS = ["2025", "2026"]
REQUIRED_YEAR_RETURN_PCT = 100.0
MAX_DRAWDOWN_LIMIT_PCT = -50.0


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    market, data_quality = _load_market()
    candidates = _candidate_library()
    candidate_monthly, candidate_scan = _candidate_results(candidates, market)
    oracle_monthly, oracle_summary = _monthly_oracle(candidate_monthly)
    capped_oracle_monthly, capped_oracle_summary = _monthly_oracle_drawdown_capped(candidate_monthly)
    strict_monthly, strict_summary = _strict_selector(candidate_monthly)

    candidate_monthly.to_csv(OUT_DIR / "candidate_monthly.csv", index=False)
    candidate_scan.to_csv(OUT_DIR / "candidate_scan.csv", index=False)
    oracle_monthly.to_csv(OUT_DIR / "monthly_oracle.csv", index=False)
    capped_oracle_monthly.to_csv(OUT_DIR / "monthly_oracle_drawdown_capped.csv", index=False)
    strict_monthly.to_csv(OUT_DIR / "strict_selector_monthly.csv", index=False)
    pd.DataFrame([oracle_summary]).to_csv(OUT_DIR / "monthly_oracle_summary.csv", index=False)
    pd.DataFrame([capped_oracle_summary]).to_csv(OUT_DIR / "monthly_oracle_drawdown_capped_summary.csv", index=False)
    pd.DataFrame([strict_summary]).to_csv(OUT_DIR / "strict_selector_summary.csv", index=False)

    summary = {
        "status": "strategy_55_btc_hype_tail_event_core_signal_done",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "purpose": "Switch away from old 2C/ret_state. Test BTC/HYPE tail-event triggers as a new core signal source.",
        "data": data_quality,
        "cost_model": {
            "cost_per_side": probe16.COST_PER_SIDE,
            "round_trip_open_close": probe16.ROUND_TRIP_COST,
        },
        "timing": {
            "signals_use_closed_15m_bar_t": True,
            "position_participates_from_bar_t_plus_1": True,
            "monthly_oracle_is_leaky": True,
            "strict_selector_uses_only_prior_months": True,
        },
        "candidate_count": int(len(candidates)),
        "static_relaxed_pass_count": int(candidate_scan["relaxed_pass"].sum()),
        "best_static_candidate": _json_ready(candidate_scan.iloc[0].to_dict()),
        "monthly_oracle": _json_ready(oracle_summary),
        "monthly_oracle_drawdown_capped": _json_ready(capped_oracle_summary),
        "strict_selector": _json_ready(strict_summary),
        "decision": _decision(candidate_scan.iloc[0].to_dict(), oracle_summary, capped_oracle_summary, strict_summary),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "candidate_scan": _rel(OUT_DIR / "candidate_scan.csv"),
            "candidate_monthly": _rel(OUT_DIR / "candidate_monthly.csv"),
            "monthly_oracle": _rel(OUT_DIR / "monthly_oracle.csv"),
            "monthly_oracle_drawdown_capped": _rel(OUT_DIR / "monthly_oracle_drawdown_capped.csv"),
            "strict_selector_monthly": _rel(OUT_DIR / "strict_selector_monthly.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_market() -> tuple[dict[str, Any], dict[str, Any]]:
    base = pd.read_csv(PANEL_41, parse_dates=["timestamp"])
    latest = pd.read_csv(LATEST_49, parse_dates=["timestamp"])
    latest = latest.pivot(index="timestamp", columns="symbol", values="close").reset_index()
    latest = latest.rename(columns={"BTCUSDT": "close_BTCUSDT", "HYPEUSDT": "close_HYPEUSDT"})
    panel = (
        pd.concat([base[["timestamp", "close_BTCUSDT", "close_HYPEUSDT"]], latest], ignore_index=True)
        .drop_duplicates("timestamp", keep="last")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    panel["timestamp"] = pd.to_datetime(panel["timestamp"], utc=True)
    panel["month"] = panel["timestamp"].dt.strftime("%Y-%m")
    panel = panel[(panel["month"] >= EVAL_START) & (panel["month"] < EVAL_END_EXCLUSIVE)].copy()
    panel = panel.dropna(subset=["close_BTCUSDT", "close_HYPEUSDT"]).reset_index(drop=True)
    close = panel[["close_BTCUSDT", "close_HYPEUSDT"]].astype(float)
    returns = np.log(close / close.shift(1)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    features = _features(panel)
    quality = {
        "sources": [_rel(PANEL_41), _rel(LATEST_49)],
        "rows": int(len(panel)),
        "start_timestamp": panel["timestamp"].min().isoformat(),
        "end_timestamp": panel["timestamp"].max().isoformat(),
        "duplicate_timestamp_rows": int(panel["timestamp"].duplicated().sum()),
        "non_15m_gap_rows": int((panel["timestamp"].diff().dropna() != pd.Timedelta(minutes=15)).sum()),
        "months": sorted(panel["month"].unique().tolist()),
    }
    market = {
        "timestamp": panel["timestamp"],
        "month": panel["month"].to_numpy(str),
        "returns": returns.to_numpy(float),
        "features": features,
    }
    return market, quality


def _features(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel[["timestamp", "month"]].copy()
    btc = np.log(panel["close_BTCUSDT"].astype(float))
    hype = np.log(panel["close_HYPEUSDT"].astype(float))
    spread = hype - btc
    for bars in [16, 96]:
        out[f"ret{bars}_BTCUSDT"] = btc.diff(bars).fillna(0.0)
        out[f"ret{bars}_HYPEUSDT"] = hype.diff(bars).fillna(0.0)
        out[f"rel_ret{bars}"] = out[f"ret{bars}_HYPEUSDT"] - out[f"ret{bars}_BTCUSDT"]
    spread_mean = spread.rolling(96 * 30, min_periods=96).mean()
    spread_std = spread.rolling(96 * 30, min_periods=96).std().replace(0, np.nan)
    resid_std = out["rel_ret16"].rolling(96 * 30, min_periods=96).std().replace(0, np.nan)
    out["spread_z"] = ((spread - spread_mean) / spread_std).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    out["resid_z16"] = (out["rel_ret16"] / resid_std).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return out


def _candidate_library() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    event_sets = [
        {"event_set": "strict", "hype_ret16_abs": 0.05, "hype_ret96_abs": 0.12, "resid_z_abs": 2.5},
        {"event_set": "loose", "hype_ret16_abs": 0.04, "hype_ret96_abs": 0.10, "resid_z_abs": 2.0},
    ]
    for event in event_sets:
        for action in ["hype_momentum", "hype_reversal", "pair_momentum", "pair_reversal", "btc_momentum", "btc_reversal"]:
            for hold_bars in [16, 32, 64, 96]:
                for leverage in [0.5, 1.0, 2.0]:
                    candidates.append(
                        {
                            "candidate_id": f"{event['event_set']}_{action}_hold{hold_bars}_lev{str(leverage).replace('.', 'p')}",
                            **event,
                            "action": action,
                            "hold_bars": hold_bars,
                            "leverage": leverage,
                        }
                    )
    return candidates


def _candidate_results(candidates: list[dict[str, Any]], market: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_frames = []
    scan_rows = []
    for candidate in candidates:
        monthly = _monthly_breakdown(_simulate(market, _target_for_candidate(candidate, market)))
        for key in ["candidate_id", "event_set", "action", "hold_bars", "leverage"]:
            monthly.insert(0, key, candidate[key])
        monthly_frames.append(monthly)
        scan_rows.append({**candidate, **_summary(monthly)})
    candidate_monthly = pd.concat(monthly_frames, ignore_index=True)
    candidate_scan = pd.DataFrame(scan_rows).sort_values(
        ["relaxed_pass", "min_target_year_return_pct", "max_drawdown_pct", "return_2026_pct", "return_2025_pct"],
        ascending=[False, False, False, False, False],
    )
    return candidate_monthly, candidate_scan


def _target_for_candidate(candidate: dict[str, Any], market: dict[str, Any]) -> np.ndarray:
    features = market["features"]
    event = (
        (features["ret16_HYPEUSDT"].abs() >= candidate["hype_ret16_abs"])
        | (features["ret96_HYPEUSDT"].abs() >= candidate["hype_ret96_abs"])
        | (features["resid_z16"].abs() >= candidate["resid_z_abs"])
    ).to_numpy(bool)
    target = np.zeros((len(features), 2), dtype=float)
    next_allowed = 0
    for i, is_event in enumerate(event):
        if not is_event or i < next_allowed:
            continue
        position = _event_position(candidate, features.iloc[i])
        if np.all(position == 0):
            continue
        end = min(len(features), i + int(candidate["hold_bars"]))
        target[i:end, :] = position
        next_allowed = end
    return target


def _event_position(candidate: dict[str, Any], row: pd.Series) -> np.ndarray:
    leverage = float(candidate["leverage"])
    action = str(candidate["action"])
    hype_side = _sign(row["ret16_HYPEUSDT"] if abs(row["ret16_HYPEUSDT"]) >= abs(row["ret96_HYPEUSDT"]) else row["ret96_HYPEUSDT"])
    btc_side = _sign(row["ret16_BTCUSDT"])
    rel_side = _sign(row["resid_z16"] if abs(row["resid_z16"]) > 0 else row["rel_ret16"])
    position = np.zeros(2, dtype=float)
    if action == "hype_momentum":
        position[1] = hype_side * leverage
    elif action == "hype_reversal":
        position[1] = -hype_side * leverage
    elif action == "pair_momentum":
        position[1] = rel_side * leverage / 2.0
        position[0] = -rel_side * leverage / 2.0
    elif action == "pair_reversal":
        position[1] = -rel_side * leverage / 2.0
        position[0] = rel_side * leverage / 2.0
    elif action == "btc_momentum":
        position[0] = btc_side * leverage
    elif action == "btc_reversal":
        position[0] = -btc_side * leverage
    return position


def _simulate(market: dict[str, Any], target: np.ndarray) -> pd.DataFrame:
    returns = market["returns"]
    active = np.roll(target, 1, axis=0)
    active[0, :] = 0.0
    previous = np.vstack([np.zeros((1, target.shape[1])), target[:-1, :]])
    turnover = np.abs(target - previous).sum(axis=1)
    orders = (np.abs(target - previous) > 1e-12).sum(axis=1)
    lr = (active * returns).sum(axis=1) - turnover * probe16.COST_PER_SIDE
    equity = np.exp(np.cumsum(lr))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    return pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "month": market["month"],
            "log_return": lr,
            "turnover": turnover,
            "orders": orders,
            "drawdown_pct": drawdown * 100.0,
        }
    )


def _monthly_breakdown(equity: pd.DataFrame) -> pd.DataFrame:
    monthly = equity.groupby("month", as_index=False).agg(
        log_return=("log_return", "sum"),
        turnover=("turnover", "sum"),
        orders=("orders", "sum"),
        max_drawdown_pct=("drawdown_pct", "min"),
    )
    monthly["return_pct"] = (np.exp(monthly["log_return"]) - 1.0) * 100.0
    return monthly


def _monthly_oracle(candidate_monthly: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    eval_rows = _eval_months(candidate_monthly)
    selected = eval_rows.sort_values(["month", "log_return"], ascending=[True, False]).groupby("month", as_index=False).head(1)
    return selected, _summary(selected)


def _monthly_oracle_drawdown_capped(candidate_monthly: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    eval_rows = _eval_months(candidate_monthly)
    capped = eval_rows[eval_rows["max_drawdown_pct"] >= MAX_DRAWDOWN_LIMIT_PCT]
    selected = capped.sort_values(["month", "log_return"], ascending=[True, False]).groupby("month", as_index=False).head(1)
    return selected, _summary(selected)


def _strict_selector(candidate_monthly: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = []
    for month in sorted(_eval_months(candidate_monthly)["month"].unique()):
        train = candidate_monthly[candidate_monthly["month"] < month]
        if train.empty:
            continue
        score = train.groupby("candidate_id", as_index=False).agg(train_log_return=("log_return", "sum"), train_max_drawdown_pct=("max_drawdown_pct", "min"))
        score = score.sort_values(["train_max_drawdown_pct", "train_log_return"], ascending=[False, False])
        best_id = score.iloc[0]["candidate_id"]
        rows.append(candidate_monthly[(candidate_monthly["month"] == month) & (candidate_monthly["candidate_id"] == best_id)].iloc[0])
    selected = pd.DataFrame(rows)
    return selected, _summary(selected) if len(selected) else ({}, {})


def _summary(monthly: pd.DataFrame) -> dict[str, Any]:
    eval_monthly = _eval_months(monthly)
    yearly = {year: (np.exp(group["log_return"].sum()) - 1.0) * 100.0 for year, group in eval_monthly.groupby(eval_monthly["month"].str[:4])}
    target_returns = [yearly.get(year) for year in TARGET_YEARS if yearly.get(year) is not None]
    max_dd = float(eval_monthly["max_drawdown_pct"].min()) if len(eval_monthly) else 0.0
    min_target = min(target_returns) if target_returns else -999.0
    return {
        "relaxed_pass": bool(len(target_returns) == len(TARGET_YEARS) and min_target > REQUIRED_YEAR_RETURN_PCT and max_dd >= MAX_DRAWDOWN_LIMIT_PCT),
        "return_2025_pct": yearly.get("2025"),
        "return_2026_pct": yearly.get("2026"),
        "min_target_year_return_pct": float(min_target),
        "max_drawdown_pct": max_dd,
        "losing_months": int((eval_monthly["return_pct"] <= 0).sum()) if len(eval_monthly) else 0,
        "min_monthly_return_pct": float(eval_monthly["return_pct"].min()) if len(eval_monthly) else 0.0,
        "orders": int(eval_monthly["orders"].sum()) if len(eval_monthly) else 0,
        "turnover": float(eval_monthly["turnover"].sum()) if len(eval_monthly) else 0.0,
        "selected_month_count": int(eval_monthly["month"].nunique()) if len(eval_monthly) else 0,
        "selected_candidate_count": int(eval_monthly["candidate_id"].nunique()) if "candidate_id" in eval_monthly.columns and len(eval_monthly) else 0,
    }


def _eval_months(monthly: pd.DataFrame) -> pd.DataFrame:
    return monthly[(monthly["month"] >= EVAL_START) & (monthly["month"] < EVAL_END_EXCLUSIVE)].copy()


def _decision(best_static: dict[str, Any], oracle: dict[str, Any], capped_oracle: dict[str, Any], strict: dict[str, Any]) -> dict[str, Any]:
    if strict.get("relaxed_pass"):
        verdict = "TAIL_EVENT_CORE_STRICT_SELECTOR_PASSES"
        reason = "严格不看未来选择器过了放宽门槛。"
    elif best_static.get("relaxed_pass"):
        verdict = "TAIL_EVENT_CORE_STATIC_PASSES_ONLY"
        reason = "静态固定候选过了放宽门槛，但严格选择器没有证明可提前选中。"
    elif oracle.get("relaxed_pass"):
        verdict = "TAIL_EVENT_CORE_ORACLE_ONLY_PASSES"
        reason = "看答案月度oracle能过，说明事件后有空间，但还不能交易。"
    elif capped_oracle.get("relaxed_pass"):
        verdict = "TAIL_EVENT_CORE_DRAWDOWN_CAPPED_ORACLE_ONLY_PASSES"
        reason = "回撤限制版看答案oracle能过，说明事件后有风险受控空间，但还不能提前选中。"
    else:
        verdict = "TAIL_EVENT_CORE_FIRST_PASS_FAILS"
        reason = "这批固定尾部事件动作没有通过放宽门槛。"
    return {"verdict": verdict, "promote_strategy": bool(strict.get("relaxed_pass")), "reason": reason}


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_static_candidate"]
    oracle = summary["monthly_oracle"]
    capped_oracle = summary["monthly_oracle_drawdown_capped"]
    strict = summary["strict_selector"]
    return "\n".join(
        [
            "# Strategy 55：BTC/HYPE 尾部事件核心信号审计",
            "",
            "- 这是研究审计，不是实盘策略。",
            "- 目的：换掉旧2C/ret_state核心信号，测试 BTC/HYPE 尾部事件触发是否有更干净的边。",
            "",
            "## 数据",
            "",
            f"- 起止：`{summary['data']['start_timestamp']}` 到 `{summary['data']['end_timestamp']}`",
            f"- 行数：`{summary['data']['rows']}`",
            f"- 月份：`{', '.join(summary['data']['months'])}`",
            "",
            "## 最好静态候选",
            "",
            f"- candidate_id: `{best['candidate_id']}`",
            f"- 2025: `{best['return_2025_pct']:.2f}%`",
            f"- 2026: `{best['return_2026_pct']:.2f}%`",
            f"- 最大回撤: `{best['max_drawdown_pct']:.2f}%`",
            f"- relaxed_pass: `{best['relaxed_pass']}`",
            "",
            "## 月度看答案 oracle",
            "",
            f"- 2025: `{oracle.get('return_2025_pct'):.2f}%`",
            f"- 2026: `{oracle.get('return_2026_pct'):.2f}%`",
            f"- 最大回撤: `{oracle.get('max_drawdown_pct'):.2f}%`",
            f"- relaxed_pass: `{oracle.get('relaxed_pass')}`",
            "",
            "## 回撤限制版月度看答案 oracle",
            "",
            f"- 2025: `{capped_oracle.get('return_2025_pct'):.2f}%`",
            f"- 2026: `{capped_oracle.get('return_2026_pct'):.2f}%`",
            f"- 最大回撤: `{capped_oracle.get('max_drawdown_pct'):.2f}%`",
            f"- relaxed_pass: `{capped_oracle.get('relaxed_pass')}`",
            "",
            "## 严格选择器",
            "",
            f"- 2025: `{strict.get('return_2025_pct'):.2f}%`",
            f"- 2026: `{strict.get('return_2026_pct'):.2f}%`",
            f"- 最大回撤: `{strict.get('max_drawdown_pct'):.2f}%`",
            f"- relaxed_pass: `{strict.get('relaxed_pass')}`",
            "",
            "## 结论",
            "",
            f"- `{summary['decision']['verdict']}`",
            f"- {summary['decision']['reason']}",
        ]
    ) + "\n"


def _sign(value: float) -> int:
    return 1 if value > 0 else (-1 if value < 0 else 0)


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
