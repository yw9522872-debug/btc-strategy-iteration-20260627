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
OUT_DIR = ROOT / "artifacts" / "strategy_46_btc_hype_tail_event_walkforward_policy_20260629"
SRC44 = ROOT / "artifacts" / "strategy_44_btc_hype_tail_event_action_oracle_20260629"
SCRIPT45 = ROOT / "scripts" / "audit_strategy_45_btc_hype_tail_event_fitted_policy_20260629.py"


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
    months = sorted(data[(data["month"] >= "2025-06") & (data["month"] < "2026-06")]["month"].unique())
    for feature_set in ["market_only", "market_plus_time"]:
        features = s45._feature_names(feature_set)
        for max_depth in [2, 3, 4, 5, 6, 8, 12, None]:
            for min_leaf in [1, 2, 3, 5]:
                target_h = np.zeros(len(data))
                target_b = np.zeros(len(data))
                trades = []
                trained_months = 0
                for month in months:
                    hist = training[training["month"] < month]
                    if len(hist) < 20 or hist["label"].nunique() < 2:
                        continue
                    clf = DecisionTreeClassifier(max_depth=max_depth, min_samples_leaf=min_leaf, random_state=46)
                    clf.fit(hist[features].to_numpy(), hist["label"].to_numpy())
                    month_event = event & (data["month"].to_numpy() == month)
                    th, tb, mt = s45._apply_tree_policy(data, month_event, clf, feature_set, min_gap)
                    target_h += th
                    target_b += tb
                    if len(mt):
                        mt["trained_rows"] = len(hist)
                        mt["trained_labels"] = hist["label"].nunique()
                        trades.append(mt)
                    trained_months += 1
                bar = s45._simulate(data, target_h, target_b)
                monthly = s45._monthly(bar)
                trade_table = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
                row = {
                    "feature_set": feature_set,
                    "max_depth": -1 if max_depth is None else max_depth,
                    "min_samples_leaf": min_leaf,
                    "trained_months": int(trained_months),
                    **_summary(monthly, len(trade_table), float(monthly["turnover"].sum()) if len(monthly) else 0.0),
                }
                rows.append(row)
                if _score(row) > _score(best):
                    best = row
                    best_monthly = monthly
                    best_trades = trade_table

    if best is None or best_monthly is None or best_trades is None:
        raise RuntimeError("no walk-forward policy evaluated")

    scan = pd.DataFrame(rows).sort_values(["hard_pass_relaxed", "min_target_year_return_pct", "max_drawdown_pct"], ascending=[False, False, False])
    scan.to_csv(OUT_DIR / "walkforward_scan.csv", index=False)
    best_monthly.to_csv(OUT_DIR / "best_walkforward_monthly.csv", index=False)
    best_trades.to_csv(OUT_DIR / "best_walkforward_trades.csv", index=False)

    summary = {
        "status": "strategy_46_btc_hype_tail_event_walkforward_policy_ready",
        "strategy_id": "strategy_46_btc_hype_tail_event_walkforward_policy_20260629",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "purpose": "Strict walk-forward validation of Strategy 45 tail-event fitted policy: each month trains only on earlier oracle-labeled tail events, then tests the current month.",
        "leakage": {
            "event_detection_uses_closed_past_bars": True,
            "current_month_labels_used_for_current_month": False,
            "oracle_labels_used_only_after_their_month_has_passed": True,
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
        "best_policy": _json_ready(best),
        "decision": _decision(best),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "walkforward_scan": _rel(OUT_DIR / "walkforward_scan.csv"),
            "best_walkforward_monthly": _rel(OUT_DIR / "best_walkforward_monthly.csv"),
            "best_walkforward_trades": _rel(OUT_DIR / "best_walkforward_trades.csv"),
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


def _decision(best: dict[str, Any]) -> dict[str, Any]:
    if best["hard_pass_relaxed"]:
        return {
            "verdict": "TAIL_EVENT_WALKFORWARD_POLICY_PASSES_RELAXED_GATE",
            "promote_strategy": False,
            "reason": "严格走步通过放宽门槛，但仍需更长历史和样本外影子验证。",
        }
    return {
        "verdict": "TAIL_EVENT_WALKFORWARD_POLICY_FAILS_RELAXED_GATE",
        "promote_strategy": False,
        "reason": "45号强过拟合规律用过去事件训练后，不能稳定预测未来月份；45号暂时更像记忆历史，而不是已验证alpha。",
    }


def _report(summary: dict[str, Any]) -> str:
    b = summary["best_policy"]
    return f"""# 46号 BTC+HYPE 尾部事件严格走步验证

本审计不是策略，不能交易。它只检查45号强过拟合规律能不能用过去事件训练后，预测未来月份。

## 最好结果

- 特征集：`{b["feature_set"]}`
- 树深度：`{b["max_depth"]}`
- 最小叶子样本：`{b["min_samples_leaf"]}`
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
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
