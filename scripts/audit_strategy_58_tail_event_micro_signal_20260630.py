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
OUT_DIR = ROOT / "artifacts" / "strategy_58_tail_event_micro_signal_20260630"
STRATEGY_ID = "strategy_58_tail_event_micro_signal_20260630"
SOURCE_42 = ROOT / "artifacts" / "strategy_42_btc_hype_state_predictability_20260629"
KLINES_42 = SOURCE_42 / "btc_hype_15m_klines_rest_2025_05_2026_05.csv.gz"
FUNDING_42 = SOURCE_42 / "btc_hype_funding_rate_2025_05_2026_05.csv"
PREMIUM_42 = SOURCE_42 / "btc_hype_premiumIndexKlines_15m_2025_05_2026_05.csv.gz"
SYMBOLS = ["BTCUSDT", "HYPEUSDT"]
WARMUP_START = "2025-05"
EVAL_START = "2025-06"
EVAL_END_EXCLUSIVE = "2026-06"
TARGET_YEARS = ["2025", "2026"]
EVENT_THRESHOLD = {"hype_ret16_abs": 0.04, "hype_ret96_abs": 0.10, "resid_z_abs": 2.0}
MIN_GAP = 16
HOLDS = [16, 32, 64, 96]
LEVERAGES = [0.5, 1.0, 2.0]
CONFIRM_BARS = [0, 1, 2, 4]
MAX_TRADE_DD_PCT = -50.0
MAX_DRAWDOWN_LIMIT_PCT = -50.0
REQUIRED_YEAR_RETURN_PCT = 100.0


def main() -> None:
    warnings.filterwarnings("ignore", message="The number of unique classes.*")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data, data_quality = _load_data()
    event = _event_mask(data)
    months = sorted(data[(data["month"] >= EVAL_START) & (data["month"] < EVAL_END_EXCLUSIVE)]["month"].unique())

    all_labels = []
    oracle_rows = []
    scan_rows = []
    best_policy = None
    best_monthly = None
    best_trades = None

    for confirm_bars in CONFIRM_BARS:
        labels = _oracle_event_labels(data, event, confirm_bars)
        all_labels.append(labels)
        oracle_bar, oracle_trades = _apply_label_policy(data, labels)
        oracle_monthly = _monthly(oracle_bar)
        oracle_summary = {
            "confirm_bars": confirm_bars,
            "event_label_rows": int(len(labels)),
            "action_counts": labels["action"].value_counts().to_dict(),
            **_summary(oracle_monthly, int(len(oracle_trades)), float(oracle_monthly["turnover"].sum())),
        }
        oracle_rows.append(oracle_summary)

        for feature_set in ["market_only", "event_micro", "event_micro_plus_time"]:
            features = _feature_names(feature_set)
            for max_depth in [2, 3, 4, 5, 6]:
                for min_leaf in [3, 5, 8]:
                    for hold_bars in [32, 64, 96]:
                        for leverage in [0.5, 1.0, 2.0]:
                            bar, trades, trained_months = _walkforward_action_policy(
                                data,
                                labels,
                                months,
                                features,
                                max_depth,
                                min_leaf,
                                hold_bars,
                                leverage,
                            )
                            monthly = _monthly(bar)
                            row = {
                                "confirm_bars": confirm_bars,
                                "feature_set": feature_set,
                                "max_depth": max_depth,
                                "min_samples_leaf": min_leaf,
                                "hold_bars": hold_bars,
                                "leverage": leverage,
                                "trained_months": trained_months,
                                **_summary(monthly, int(len(trades)), float(monthly["turnover"].sum())),
                            }
                            scan_rows.append(row)
                            if _score(row) > _score(best_policy):
                                best_policy = row
                                best_monthly = monthly
                                best_trades = trades

    labels_all = pd.concat(all_labels, ignore_index=True)
    oracle_scan = pd.DataFrame(oracle_rows).sort_values(
        ["hard_pass_relaxed", "min_target_year_return_pct", "max_drawdown_pct"],
        ascending=[False, False, False],
    )
    policy_scan = pd.DataFrame(scan_rows).sort_values(
        ["hard_pass_relaxed", "min_target_year_return_pct", "max_drawdown_pct"],
        ascending=[False, False, False],
    )
    if best_policy is None or best_monthly is None or best_trades is None:
        raise RuntimeError("no policy evaluated")

    labels_all.to_csv(OUT_DIR / "oracle_event_labels.csv", index=False)
    oracle_scan.to_csv(OUT_DIR / "oracle_by_confirm.csv", index=False)
    policy_scan.to_csv(OUT_DIR / "action_policy_scan.csv", index=False)
    best_monthly.to_csv(OUT_DIR / "best_action_policy_monthly.csv", index=False)
    best_trades.to_csv(OUT_DIR / "best_action_policy_trades.csv", index=False)

    best_oracle = oracle_scan.iloc[0].to_dict()
    summary = {
        "status": "strategy_58_tail_event_micro_signal_done",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "purpose": "Test event-close funding/premium, lead-lag, first-bar confirmation, volume, and taker pressure for causal post-tail-event action selection.",
        "data": data_quality,
        "event_threshold": EVENT_THRESHOLD,
        "confirm_bars_tested": CONFIRM_BARS,
        "label_leakage_note": "Oracle labels use future post-decision returns, but walk-forward training uses only labels from months before the tested month. Confirmation bars delay entry and are known before decision.",
        "cost_model": {"cost_per_side": probe16.COST_PER_SIDE, "round_trip_open_close": probe16.ROUND_TRIP_COST},
        "best_oracle_by_confirm": _json_ready(best_oracle),
        "best_walkforward_action_policy": _json_ready(best_policy),
        "decision": _decision(best_policy, best_oracle),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "oracle_event_labels": _rel(OUT_DIR / "oracle_event_labels.csv"),
            "oracle_by_confirm": _rel(OUT_DIR / "oracle_by_confirm.csv"),
            "action_policy_scan": _rel(OUT_DIR / "action_policy_scan.csv"),
            "best_action_policy_monthly": _rel(OUT_DIR / "best_action_policy_monthly.csv"),
            "best_action_policy_trades": _rel(OUT_DIR / "best_action_policy_trades.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_data() -> tuple[pd.DataFrame, dict[str, Any]]:
    klines = pd.read_csv(KLINES_42, parse_dates=["timestamp"])
    funding = pd.read_csv(FUNDING_42, parse_dates=["timestamp"])
    premium = pd.read_csv(PREMIUM_42, parse_dates=["timestamp"])
    panel = _wide(klines, ["close", "quote_volume", "trades", "taker_buy_quote"])
    panel = panel.merge(_wide(premium, ["premium_close"]), on="timestamp", how="left")

    funding_wide = _wide(funding, ["funding_rate"]).sort_values("timestamp")
    panel = panel.sort_values("timestamp").merge(funding_wide, on="timestamp", how="left")
    for symbol in SYMBOLS:
        panel[f"funding_rate_{symbol}"] = panel[f"funding_rate_{symbol}"].ffill()

    panel["timestamp"] = pd.to_datetime(panel["timestamp"], utc=True)
    panel["month"] = panel["timestamp"].dt.strftime("%Y-%m")
    panel = panel[(panel["month"] >= WARMUP_START) & (panel["month"] < EVAL_END_EXCLUSIVE)].dropna().reset_index(drop=True)
    _add_price_features(panel)
    _add_micro_features(panel)
    panel = panel.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    quality = {
        "sources": [_rel(KLINES_42), _rel(FUNDING_42), _rel(PREMIUM_42)],
        "rows": int(len(panel)),
        "start_timestamp": panel["timestamp"].min().isoformat(),
        "end_timestamp": panel["timestamp"].max().isoformat(),
        "duplicate_timestamp_rows": int(panel["timestamp"].duplicated().sum()),
        "non_15m_gap_rows": int((panel["timestamp"].diff().dropna() != pd.Timedelta(minutes=15)).sum()),
        "latest_2026_06_note": "Strategy 49 latest klines only contain close, so this audit stops at 2026-05 to keep volume/taker features complete.",
    }
    return panel, quality


def _wide(df: pd.DataFrame, values: list[str]) -> pd.DataFrame:
    wide = df.pivot(index="timestamp", columns="symbol", values=values)
    wide.columns = [f"{value}_{symbol}" for value, symbol in wide.columns]
    wide = wide.reset_index()
    wide["timestamp"] = pd.to_datetime(wide["timestamp"], utc=True, format="mixed")
    return wide


def _add_price_features(panel: pd.DataFrame) -> None:
    for symbol in SYMBOLS:
        close = panel[f"close_{symbol}"].astype(float)
        panel[f"lr_{symbol}"] = np.log(close / close.shift(1)).fillna(0.0)
        for bars in [4, 8, 16, 96, 384]:
            panel[f"ret{bars}_{symbol}"] = np.log(close / close.shift(bars)).fillna(0.0)
    panel["rel_ret16"] = panel["ret16_HYPEUSDT"] - panel["ret16_BTCUSDT"]
    panel["rel_ret96"] = panel["ret96_HYPEUSDT"] - panel["ret96_BTCUSDT"]
    resid_scale = panel["rel_ret16"].rolling(96 * 30, min_periods=96).std().replace(0, np.nan)
    panel["resid_z16"] = (panel["rel_ret16"] / resid_scale).fillna(0.0)
    panel["shock_sign"] = np.sign(np.where(panel["ret16_HYPEUSDT"].abs() >= panel["ret96_HYPEUSDT"].abs(), panel["ret16_HYPEUSDT"], panel["ret96_HYPEUSDT"]))
    panel["trend_align"] = np.sign(panel["ret384_HYPEUSDT"]) * panel["shock_sign"]
    panel["btc_align"] = np.sign(panel["ret96_BTCUSDT"]) * panel["shock_sign"]
    panel["btc_early4"] = np.log(panel["close_BTCUSDT"].shift(4) / panel["close_BTCUSDT"].shift(8)).fillna(0.0)
    panel["btc_late4"] = np.log(panel["close_BTCUSDT"] / panel["close_BTCUSDT"].shift(4)).fillna(0.0)
    panel["hype_early4"] = np.log(panel["close_HYPEUSDT"].shift(4) / panel["close_HYPEUSDT"].shift(8)).fillna(0.0)
    panel["hype_late4"] = np.log(panel["close_HYPEUSDT"] / panel["close_HYPEUSDT"].shift(4)).fillna(0.0)
    panel["btc_lead_score"] = panel["btc_early4"].abs() * panel["hype_late4"].abs() - panel["hype_early4"].abs() * panel["btc_late4"].abs()
    panel["lead_direction_score"] = panel["btc_early4"] * panel["hype_late4"] - panel["hype_early4"] * panel["btc_late4"]
    panel["month_num"] = panel["timestamp"].dt.month
    panel["day_num"] = panel["timestamp"].dt.day
    panel["hour_float"] = panel["timestamp"].dt.hour + panel["timestamp"].dt.minute / 60.0
    panel["event_index_frac"] = np.arange(len(panel)) / max(1, len(panel) - 1)


def _add_micro_features(panel: pd.DataFrame) -> None:
    panel["funding_diff"] = panel["funding_rate_HYPEUSDT"] - panel["funding_rate_BTCUSDT"]
    panel["funding_abs_hype"] = panel["funding_rate_HYPEUSDT"].abs()
    panel["funding_abs_diff"] = panel["funding_diff"].abs()
    for symbol in SYMBOLS:
        panel[f"funding_chg32_{symbol}"] = panel[f"funding_rate_{symbol}"] - panel[f"funding_rate_{symbol}"].shift(32)
        panel[f"premium_chg16_{symbol}"] = panel[f"premium_close_{symbol}"] - panel[f"premium_close_{symbol}"].shift(16)
        panel[f"premium_chg96_{symbol}"] = panel[f"premium_close_{symbol}"] - panel[f"premium_close_{symbol}"].shift(96)
        for bars in [16, 96]:
            qv = panel[f"quote_volume_{symbol}"].rolling(bars, min_periods=1).sum()
            taker = panel[f"taker_buy_quote_{symbol}"].rolling(bars, min_periods=1).sum()
            trades = panel[f"trades_{symbol}"].rolling(bars, min_periods=1).sum()
            panel[f"taker_imb{bars}_{symbol}"] = (taker / qv.replace(0, np.nan) - 0.5).fillna(0.0)
            vol_log = np.log1p(qv)
            vol_scale = vol_log.rolling(96 * 30, min_periods=96).std().replace(0, np.nan)
            panel[f"vol_z{bars}_{symbol}"] = ((vol_log - vol_log.rolling(96 * 30, min_periods=96).mean()) / vol_scale).fillna(0.0)
            trade_log = np.log1p(trades)
            trade_scale = trade_log.rolling(96 * 30, min_periods=96).std().replace(0, np.nan)
            panel[f"trades_z{bars}_{symbol}"] = ((trade_log - trade_log.rolling(96 * 30, min_periods=96).mean()) / trade_scale).fillna(0.0)
    panel["premium_diff"] = panel["premium_close_HYPEUSDT"] - panel["premium_close_BTCUSDT"]
    panel["premium_abs_hype"] = panel["premium_close_HYPEUSDT"].abs()
    panel["taker_diff16"] = panel["taker_imb16_HYPEUSDT"] - panel["taker_imb16_BTCUSDT"]
    panel["vol_diff16"] = panel["vol_z16_HYPEUSDT"] - panel["vol_z16_BTCUSDT"]


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


def _oracle_event_labels(data: pd.DataFrame, event: np.ndarray, confirm_bars: int) -> pd.DataFrame:
    rows = []
    next_ok = 0
    for event_i in np.where(event)[0]:
        decision_i = int(event_i + confirm_bars)
        if event_i < next_ok or decision_i + 2 >= len(data):
            continue
        option = _best_action(data, int(event_i), decision_i + 1)
        features = _feature_row(data, int(event_i), decision_i, "event_micro_plus_time")
        rows.append(
            {
                "event_index": int(event_i),
                "decision_index": decision_i,
                "confirm_bars": confirm_bars,
                "event_timestamp": data["timestamp"].iloc[event_i],
                "decision_timestamp": data["timestamp"].iloc[decision_i],
                "month": data["month"].iloc[decision_i],
                "label": _label(option["action"], option["btc_target"], option["hype_target"], option["hold_bars"]),
                **option,
                **features,
            }
        )
        next_ok = max(int(event_i) + MIN_GAP, decision_i + 1 + int(option["hold_bars"]))
    return pd.DataFrame(rows)


def _best_action(data: pd.DataFrame, event_index: int, start: int) -> dict[str, Any]:
    options = [{"action": "cash", "hype_target": 0.0, "btc_target": 0.0, "hold_bars": 0, "trade_log_return": 0.0, "trade_return_pct": 0.0, "trade_max_drawdown_pct": 0.0}]
    for hold in HOLDS:
        for leverage in LEVERAGES:
            for action in ["hype_momentum", "hype_reversal", "btc_momentum", "btc_reversal", "pair_momentum", "pair_reversal"]:
                btc_target, hype_target = _position_for_action(data, event_index, action, leverage)
                stats = _trade_stats(data, start, hold, btc_target, hype_target)
                if stats["trade_max_drawdown_pct"] >= MAX_TRADE_DD_PCT:
                    options.append({"action": action, "btc_target": btc_target, "hype_target": hype_target, "hold_bars": hold, **stats})
    return max(options, key=lambda row: row["trade_log_return"])


def _walkforward_action_policy(
    data: pd.DataFrame,
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
        clf = DecisionTreeClassifier(max_depth=max_depth, min_samples_leaf=min_leaf, random_state=58)
        clf.fit(train[features].to_numpy(float), train["action"].to_numpy(str))
        next_ok = 0
        for row in labels[labels["month"] == month].sort_values("decision_index").itertuples(index=False):
            event_i = int(row.event_index)
            decision_i = int(row.decision_index)
            if event_i < next_ok:
                continue
            action = str(clf.predict(pd.DataFrame([row._asdict()])[features].to_numpy(float))[0])
            btc_target, hype_target = _position_for_action(data, event_i, action, leverage)
            start = decision_i + 1
            end = min(len(data), start + hold_bars)
            if start >= end:
                continue
            target_btc[start:end] = btc_target
            target_hype[start:end] = hype_target
            trade_rows.append(
                {
                    "month": month,
                    "event_index": event_i,
                    "decision_index": decision_i,
                    "event_timestamp": row.event_timestamp,
                    "decision_timestamp": row.decision_timestamp,
                    "predicted_action": action,
                    "oracle_action": row.action,
                    "btc_target": btc_target,
                    "hype_target": hype_target,
                    "hold_bars": hold_bars,
                    "leverage": leverage,
                    "trained_rows": len(train),
                    "trained_actions": train["action"].nunique(),
                }
            )
            next_ok = max(event_i + MIN_GAP, end)
        trained_months += 1
    return _simulate(data, target_btc, target_hype), pd.DataFrame(trade_rows), trained_months


def _apply_label_policy(data: pd.DataFrame, labels: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    target_btc = np.zeros(len(data))
    target_hype = np.zeros(len(data))
    trade_rows = []
    for row in labels.itertuples(index=False):
        start = int(row.decision_index) + 1
        end = min(len(data), start + int(row.hold_bars))
        if start >= end:
            continue
        target_btc[start:end] = float(row.btc_target)
        target_hype[start:end] = float(row.hype_target)
        trade_rows.append(row._asdict())
    return _simulate(data, target_btc, target_hype), pd.DataFrame(trade_rows)


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


def _feature_names(feature_set: str) -> list[str]:
    market = [
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
    micro = market + [
        "funding_rate_BTCUSDT",
        "funding_rate_HYPEUSDT",
        "funding_diff",
        "funding_abs_hype",
        "funding_abs_diff",
        "funding_chg32_BTCUSDT",
        "funding_chg32_HYPEUSDT",
        "premium_close_BTCUSDT",
        "premium_close_HYPEUSDT",
        "premium_diff",
        "premium_abs_hype",
        "premium_chg16_BTCUSDT",
        "premium_chg16_HYPEUSDT",
        "premium_chg96_BTCUSDT",
        "premium_chg96_HYPEUSDT",
        "btc_lead_score",
        "lead_direction_score",
        "taker_imb16_BTCUSDT",
        "taker_imb16_HYPEUSDT",
        "taker_imb96_BTCUSDT",
        "taker_imb96_HYPEUSDT",
        "taker_diff16",
        "vol_z16_BTCUSDT",
        "vol_z16_HYPEUSDT",
        "vol_z96_BTCUSDT",
        "vol_z96_HYPEUSDT",
        "vol_diff16",
        "trades_z16_BTCUSDT",
        "trades_z16_HYPEUSDT",
        "confirm_ret_BTCUSDT",
        "confirm_ret_HYPEUSDT",
        "confirm_rel_ret",
        "confirm_taker_imb_BTCUSDT",
        "confirm_taker_imb_HYPEUSDT",
    ]
    if feature_set == "market_only":
        return market
    if feature_set == "event_micro":
        return micro
    if feature_set == "event_micro_plus_time":
        return micro + ["month_num", "day_num", "hour_float", "event_index_frac"]
    raise ValueError(feature_set)


def _feature_row(data: pd.DataFrame, event_i: int, decision_i: int, feature_set: str) -> dict[str, float]:
    row = {name: float(data[name].iloc[decision_i]) for name in _feature_names("event_micro_plus_time") if not name.startswith("confirm_")}
    if decision_i > event_i:
        sl = slice(event_i + 1, decision_i + 1)
        row["confirm_ret_BTCUSDT"] = float(np.log(data["close_BTCUSDT"].iloc[decision_i] / data["close_BTCUSDT"].iloc[event_i]))
        row["confirm_ret_HYPEUSDT"] = float(np.log(data["close_HYPEUSDT"].iloc[decision_i] / data["close_HYPEUSDT"].iloc[event_i]))
        row["confirm_rel_ret"] = row["confirm_ret_HYPEUSDT"] - row["confirm_ret_BTCUSDT"]
        for symbol in SYMBOLS:
            qv = float(data[f"quote_volume_{symbol}"].iloc[sl].sum())
            taker = float(data[f"taker_buy_quote_{symbol}"].iloc[sl].sum())
            row[f"confirm_taker_imb_{symbol}"] = taker / qv - 0.5 if qv > 0 else 0.0
    else:
        row.update(
            {
                "confirm_ret_BTCUSDT": 0.0,
                "confirm_ret_HYPEUSDT": 0.0,
                "confirm_rel_ret": 0.0,
                "confirm_taker_imb_BTCUSDT": 0.0,
                "confirm_taker_imb_HYPEUSDT": 0.0,
            }
        )
    return {name: row[name] for name in _feature_names(feature_set)}


def _label(action: str, btc_target: float, hype_target: float, hold: int) -> str:
    return f"{action}|{btc_target:.3f}|{hype_target:.3f}|{int(hold)}"


def _sign(value: float) -> int:
    return 1 if value > 0 else (-1 if value < 0 else 0)


def _score(row: dict[str, Any] | None) -> tuple[float, float]:
    if row is None:
        return (-999.0, -999.0)
    return (float(row.get("min_target_year_return_pct", -999.0)), float(row.get("max_drawdown_pct", -999.0)))


def _decision(best_policy: dict[str, Any], best_oracle: dict[str, Any]) -> dict[str, Any]:
    if best_policy["hard_pass_relaxed"]:
        verdict = "EVENT_MICRO_ACTION_WALKFORWARD_PASSES"
        reason = "更贴近事件的信息严格走步通过放宽门槛，但仍需冻结验证。"
    elif best_oracle["hard_pass_relaxed"]:
        verdict = "EVENT_MICRO_ORACLE_PASSES_BUT_WALKFORWARD_FAILS"
        reason = "确认K、funding、premium、lead-lag、成交量/taker 的看答案空间存在，但严格走步动作选择仍失败。"
    else:
        verdict = "EVENT_MICRO_UPPER_BOUND_FAILS"
        reason = "加入更贴近事件的信息后，连确认延迟后的事件oracle上限也不足。"
    return {"verdict": verdict, "promote_strategy": False, "reason": reason}


def _report(summary: dict[str, Any]) -> str:
    oracle = summary["best_oracle_by_confirm"]
    best = summary["best_walkforward_action_policy"]
    decision = summary["decision"]
    return f"""# Strategy 58：尾部事件微观提前信息审计

- 这是研究审计，不是实盘策略。
- 主数据到 2026-05，因为 2026-06 最新K线缺成交量/taker列。
- 事件后确认K线只在收盘后使用，入场也延后，不算偷看。

## 最好确认延迟oracle

- confirm_bars: `{oracle['confirm_bars']}`
- 2025: `{oracle['return_2025_pct']:.2f}%`
- 2026: `{oracle['return_2026_pct']:.2f}%`
- 最大回撤: `{oracle['max_drawdown_pct']:.2f}%`
- 交易数: `{oracle['trade_count']}`
- hard_pass_relaxed: `{oracle['hard_pass_relaxed']}`

## 最好严格走步动作策略

- confirm_bars: `{best['confirm_bars']}`
- feature_set: `{best['feature_set']}`
- max_depth: `{best['max_depth']}`
- min_samples_leaf: `{best['min_samples_leaf']}`
- hold_bars: `{best['hold_bars']}`
- leverage: `{best['leverage']}`
- 2025: `{best['return_2025_pct']:.2f}%`
- 2026: `{best['return_2026_pct']:.2f}%`
- 最大回撤: `{best['max_drawdown_pct']:.2f}%`
- 亏损月: `{best['losing_months']}`
- 交易数: `{best['trade_count']}`
- hard_pass_relaxed: `{best['hard_pass_relaxed']}`

## 结论

- `{decision['verdict']}`
- {decision['reason']}
"""


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
