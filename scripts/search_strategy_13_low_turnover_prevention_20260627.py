from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import audit_strategy_11_true_2024_walkforward_20260627 as audit11
import search_monthly_profit_lock_20260627 as lock_search
import search_online_expert_pool_20260627 as source_pool


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_13_low_turnover_prevention_20260627"
STRATEGY_ID = "strategy_13_low_turnover_prevention_20260627"
TRAIN_YEAR = "2023"
EVAL_YEAR = "2024"
CONFIRM_BARS = [1, 2, 4, 8, 12]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    features = audit11._load_combined_features()
    train_features = _year_features(features, TRAIN_YEAR)
    eval_features = _year_features(features, EVAL_YEAR)
    train_market = source_pool._market(train_features)
    eval_market = source_pool._market(eval_features)
    raw_train_side = audit11._ret_state_side(train_features, audit11.FIXED_WINDOW, audit11.FIXED_THRESHOLD_BPS)
    raw_eval_side = audit11._ret_state_side(eval_features, audit11.FIXED_WINDOW, audit11.FIXED_THRESHOLD_BPS)
    scan = _scan_candidates(raw_train_side, train_market, raw_eval_side, eval_market)
    selected = scan.sort_values(_sort_columns(), ascending=_sort_ascending()).iloc[0].to_dict()
    equity = _equity_for(raw_eval_side, eval_market, selected)
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)

    scan.to_csv(OUT_DIR / "candidate_scan.csv", index=False)
    equity.to_csv(OUT_DIR / "selected_equity.csv", index=False)
    monthly.to_csv(OUT_DIR / "selected_monthly.csv", index=False)
    yearly.to_csv(OUT_DIR / "selected_yearly.csv", index=False)

    summary = {
        "status": "strategy_13_low_turnover_prevention_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "strict_train_only_selection": True,
        "base_signal": {"family": "ret_state", "window": audit11.FIXED_WINDOW, "threshold_bps": audit11.FIXED_THRESHOLD_BPS},
        "rule": "Only switch side after the new ret_state side persists for confirm_bars closed 15m bars.",
        "train_year": TRAIN_YEAR,
        "eval_year": EVAL_YEAR,
        "selected_by_2023": lock_search._json_ready(selected),
        "yearly": lock_search._json_ready(yearly.to_dict("records")),
        "monthly": lock_search._json_ready(monthly[monthly["month"].str[:4] == EVAL_YEAR].to_dict("records")),
        "leaky_diagnostics_not_for_selection": _leaky_diagnostics(scan),
        "decision": _decision(selected),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "candidate_scan": _rel(OUT_DIR / "candidate_scan.csv"),
            "selected_equity": _rel(OUT_DIR / "selected_equity.csv"),
            "selected_monthly": _rel(OUT_DIR / "selected_monthly.csv"),
            "selected_yearly": _rel(OUT_DIR / "selected_yearly.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _year_features(features: pd.DataFrame, year: str) -> pd.DataFrame:
    return features.loc[features["timestamp"].dt.strftime("%Y") == year].reset_index(drop=True)


def _scan_candidates(
    raw_train_side: np.ndarray,
    train_market: dict[str, Any],
    raw_eval_side: np.ndarray,
    eval_market: dict[str, Any],
) -> pd.DataFrame:
    rows = []
    # ponytail: small fixed grid; widen only if this 2023-only check earns it.
    for confirm_bars in CONFIRM_BARS:
        train_side = _confirmed_side(raw_train_side, confirm_bars)
        eval_side = _confirmed_side(raw_eval_side, confirm_bars)
        for params in audit11._small_param_grid():
            _, train_arrays = lock_search._simulate(
                train_side,
                params["leverage"],
                params["lock_log"],
                None,
                params["quota_arm_log"],
                params["quota_leverage"],
                train_market,
            )
            _, eval_arrays = lock_search._simulate(
                eval_side,
                params["leverage"],
                params["lock_log"],
                None,
                params["quota_arm_log"],
                params["quota_leverage"],
                eval_market,
            )
            train_monthly = _arrays_to_monthly(train_arrays, train_market)
            eval_monthly = _arrays_to_monthly(eval_arrays, eval_market)
            rows.append({"confirm_bars": confirm_bars, **params, **_scores(train_monthly, eval_monthly)})
    return pd.DataFrame(rows)


def _confirmed_side(raw_side: np.ndarray, confirm_bars: int) -> np.ndarray:
    raw_side = raw_side.astype(np.int8)
    if confirm_bars <= 1:
        return raw_side.copy()
    out = np.zeros(len(raw_side), dtype=np.int8)
    active = 0
    pending = 0
    pending_bars = 0
    for index, side in enumerate(raw_side):
        side = int(side)
        if side == active:
            pending = 0
            pending_bars = 0
        elif side == pending:
            pending_bars += 1
        else:
            pending = side
            pending_bars = 1
        if pending_bars >= confirm_bars:
            active = pending
            pending = 0
            pending_bars = 0
        out[index] = active
    return out


def _scores(train_monthly: pd.DataFrame, eval_monthly: pd.DataFrame) -> dict[str, Any]:
    train = _score_year(train_monthly, TRAIN_YEAR)
    test = _score_year(eval_monthly, EVAL_YEAR)
    train_hard_ok = bool(
        train["return_pct"] > lock_search.REQUIRED_RETURN_PCT
        and train["losing_months"] == 0
        and train["min_monthly_orders"] >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS
    )
    return {
        "train_hard_ok": train_hard_ok,
        "train_return_pct": train["return_pct"],
        "train_losing_months": train["losing_months"],
        "train_min_monthly_return_pct": train["min_monthly_return_pct"],
        "train_min_monthly_orders": train["min_monthly_orders"],
        "train_turnover": train["turnover"],
        "eval_return_pct": test["return_pct"],
        "eval_losing_months": test["losing_months"],
        "eval_min_monthly_return_pct": test["min_monthly_return_pct"],
        "eval_min_monthly_orders": test["min_monthly_orders"],
        "eval_turnover": test["turnover"],
        "eval_hard_pass": bool(
            test["return_pct"] > lock_search.REQUIRED_RETURN_PCT
            and test["losing_months"] == 0
            and test["min_monthly_orders"] >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS
        ),
    }


def _score_year(monthly: pd.DataFrame, year: str) -> dict[str, Any]:
    subset = monthly.loc[monthly["month"].str[:4] == year]
    log_return = float(subset["log_return"].sum())
    return {
        "return_pct": float((np.exp(log_return) - 1.0) * 100.0),
        "losing_months": int((subset["return_pct"] <= 0).sum()),
        "min_monthly_return_pct": float(subset["return_pct"].min()),
        "min_monthly_orders": int(subset["orders"].min()),
        "turnover": float(subset["turnover"].sum()),
    }


def _equity_for(raw_side: np.ndarray, market: dict[str, Any], row: dict[str, Any]) -> pd.DataFrame:
    side = _confirmed_side(raw_side, int(row["confirm_bars"]))
    _, arrays = lock_search._simulate(
        side,
        float(row["leverage"]),
        float(row["lock_log"]),
        None,
        _none_if_nan(row["quota_arm_log"]),
        _none_if_nan(row["quota_leverage"]),
        market,
    )
    equity = pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "close": market["close"],
            "position": arrays["position"],
            "active_position": arrays["active_position"],
            "turnover": arrays["turnover"],
            "order_count": arrays["order_count"],
            "strategy_log_return": arrays["strategy_log_return"],
            "equity": arrays["equity"],
            "drawdown": arrays["drawdown"],
        }
    )
    _assert_signal_timing(equity)
    return equity.loc[equity["timestamp"].dt.strftime("%Y").isin([TRAIN_YEAR, EVAL_YEAR])].reset_index(drop=True)


def _arrays_to_monthly(arrays: dict[str, np.ndarray], market: dict[str, Any]) -> pd.DataFrame:
    equity = pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "close": market["close"],
            "position": arrays["position"],
            "active_position": arrays["active_position"],
            "turnover": arrays["turnover"],
            "order_count": arrays["order_count"],
            "strategy_log_return": arrays["strategy_log_return"],
            "equity": arrays["equity"],
            "drawdown": arrays["drawdown"],
        }
    )
    return lock_search._monthly_breakdown(equity)


def _leaky_diagnostics(scan: pd.DataFrame) -> dict[str, Any]:
    eval_pass = scan.loc[scan["eval_hard_pass"]]
    best_eval = scan.sort_values(["eval_hard_pass", "eval_return_pct"], ascending=[False, False]).iloc[0].to_dict()
    return lock_search._json_ready(
        {
            "candidate_count": int(len(scan)),
            "eval_hard_pass_count": int(len(eval_pass)),
            "best_eval_return_pct_leaky": float(best_eval["eval_return_pct"]),
            "best_eval_confirm_bars_leaky": int(best_eval["confirm_bars"]),
            "note": "These numbers look at 2024 and are diagnostics only, not selection evidence.",
        }
    )


def _decision(selected: dict[str, Any]) -> dict[str, Any]:
    return {
        "promote_strategy": bool(selected["eval_hard_pass"]),
        "reason": "Promote only if the 2023-selected low-turnover rule passes full 2024 hard conditions.",
    }


def _assert_signal_timing(equity: pd.DataFrame) -> None:
    active = equity["active_position"].to_numpy(float)
    position = equity["position"].to_numpy(float)
    assert active[0] == 0.0
    assert np.allclose(active[1:], position[:-1])


def _sort_columns() -> list[str]:
    return [
        "train_hard_ok",
        "train_losing_months",
        "train_min_monthly_return_pct",
        "train_return_pct",
        "train_min_monthly_orders",
        "train_turnover",
    ]


def _sort_ascending() -> list[bool]:
    return [False, True, False, False, False, True]


def _render_report(summary: dict[str, Any]) -> str:
    row = summary["selected_by_2023"]
    leak = summary["leaky_diagnostics_not_for_selection"]
    return "\n".join(
        [
            "# 13号低换手/低反手预防规则",
            "",
            "这不是固化版。只用 2023 选择确认根数和控制参数，再测完整 2024。",
            "",
            "## 2023选中",
            "",
            f"- confirm_bars: `{row['confirm_bars']}`",
            f"- leverage: `{row['leverage']}`",
            f"- lock_log: `{row['lock_log']}`",
            f"- quota: `{row['quota_arm_log']}` / `{row['quota_leverage']}`",
            "",
            "## 2024结果",
            "",
            f"- hard_pass: `{row['eval_hard_pass']}`",
            f"- 2024收益: `{row['eval_return_pct']:.2f}%`",
            f"- 亏损月: `{row['eval_losing_months']}`",
            f"- 最差月: `{row['eval_min_monthly_return_pct']:.2f}%`",
            f"- 最少月交易: `{row['eval_min_monthly_orders']}`",
            f"- 2024换手: `{row['eval_turnover']}`",
            "",
            "## 诊断",
            "",
            f"- 事后看 2024 能通过的候选数：`{leak['eval_hard_pass_count']}`，但这是看答案。",
            f"- 事后最佳 2024收益：`{leak['best_eval_return_pct_leaky']:.2f}%`。",
        ]
    ) + "\n"


def _none_if_nan(value: Any) -> Any:
    return None if pd.isna(value) else value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
