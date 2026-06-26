from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import search_monthly_profit_lock_20260627 as lock_search
import search_online_expert_pool_20260627 as source_pool
import search_strategy_1_candidate_20260627 as strategy_1a
import search_strategy_1c_trend_runner_20260627 as strategy_1c


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_1e_shock_guard_20260627"
STRATEGY_ID = "strategy_1e_shock_guard_20260627"

BASE_WINDOW = 64
BASE_THRESHOLD_BPS = 100.0
LEVERAGE_CAP = 8.0

STRONG_TREND_GAP_BPS = 350.0
STRONG_TREND_ADX_MIN = 30.0
CONFLICT_FILLER_LEVERAGE = 0.25
RUNNER_LEVERAGE = 0.25

WEAK_TREND_GAP_BPS = 300.0
WEAK_TREND_ADX_MAX = 30.0
WEAK_NEW_ORDER_LEVERAGE = 0.10

ADVERSE_SHOCK_LOSS_LOG = 0.06
SHOCK_COOLDOWN_BARS = 1
SHOCK_COOLDOWN_LEVERAGE = 0.10


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = source_pool._load_features(source_pool.FEATURE_FRAME)
    features = source_pool._add_features(source)
    market = source_pool._market(features)
    base_side = _base_side(features)
    trend_side = _trend_side(features)
    weak_trend = _weak_trend_mask(features)
    selections = pd.read_csv(ROOT / "artifacts" / "strategy_1b_expanded_controls_20260627" / "strategy_1b_selections.csv")

    equity = _simulate(base_side, trend_side, weak_trend, market, selections, lock_search.COST_PER_SIDE)
    strategy_1a._assert_signal_timing(equity)
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)
    row = strategy_1c._result_row(equity, monthly, yearly)
    diagnostics = _diagnostics(equity)
    signals = strategy_1a._signals(equity)
    signals["candidate_version"] = STRATEGY_ID

    stress = pd.DataFrame(
        [
            _stress_row(base_side, trend_side, weak_trend, market, selections, 0.001, 0),
            _stress_row(base_side, trend_side, weak_trend, market, selections, 0.0015, 0),
            _stress_row(base_side, trend_side, weak_trend, market, selections, 0.002, 0),
            _stress_row(base_side, trend_side, weak_trend, market, selections, 0.001, 1),
            _stress_row(base_side, trend_side, weak_trend, market, selections, 0.0015, 1),
        ]
    )

    selections.to_csv(OUT_DIR / "strategy_1e_selections.csv", index=False)
    signals.to_csv(OUT_DIR / "strategy_1e_signals.csv", index=False)
    equity.to_csv(OUT_DIR / "strategy_1e_equity.csv", index=False)
    monthly.to_csv(OUT_DIR / "strategy_1e_monthly.csv", index=False)
    yearly.to_csv(OUT_DIR / "strategy_1e_yearly.csv", index=False)
    stress.to_csv(OUT_DIR / "strategy_1e_stress.csv", index=False)
    chart_files = _plot_trade_charts(equity)

    summary = {
        "status": "strategy_1e_shock_guard_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "strict_no_future_function": True,
        "base": "strategy_1d_trend_guard_20260627",
        "change": (
            "Tighten the strong-trend guard to 350 bps / ADX 30, keep weak-zone new trades tiny, "
            "and add a closed-bar adverse-shock guard to reduce position after a large hit."
        ),
        "rules": {
            "base_signal": {
                "family": "ret_state",
                "window_bars": BASE_WINDOW,
                "threshold_bps": BASE_THRESHOLD_BPS,
            },
            "leverage_cap": LEVERAGE_CAP,
            "strong_trend_guard": {
                "trend_gap_bps": STRONG_TREND_GAP_BPS,
                "adx_min": STRONG_TREND_ADX_MIN,
                "conflict_before_10_orders": f"use trend side at {CONFLICT_FILLER_LEVERAGE}x",
                "conflict_after_10_orders": "flat",
            },
            "weak_trend_guard": {
                "weak_when": f"ADX < {WEAK_TREND_ADX_MAX} and abs(trend_gap) < {WEAK_TREND_GAP_BPS}",
                "new_or_reverse_trade_leverage": WEAK_NEW_ORDER_LEVERAGE,
            },
            "adverse_shock_guard": {
                "trigger": f"active_position * current_bar_log_return <= -{ADVERSE_SHOCK_LOSS_LOG}",
                "cooldown_bars": SHOCK_COOLDOWN_BARS,
                "cooldown_leverage": SHOCK_COOLDOWN_LEVERAGE,
                "timing": "the shock is known at bar t close and only changes target position for bar t+1",
            },
            "post_lock_runner": {
                "runner_leverage": RUNNER_LEVERAGE,
                "runner_side": "same strong trend side as the strong trend guard",
            },
            "timing": "all signal inputs use closed bar t data; active_position participates from bar t+1",
        },
        "cost_model": {
            "cost_per_side": lock_search.COST_PER_SIDE,
            "round_trip_open_close": lock_search.COST_PER_SIDE * 2,
        },
        "row": lock_search._json_ready(row),
        "diagnostics": lock_search._json_ready(diagnostics),
        "yearly": lock_search._json_ready(yearly.to_dict("records")),
        "monthly": lock_search._json_ready(
            monthly[["month", "return_pct", "orders", "drawdown_pct"]].to_dict("records")
        ),
        "stress": lock_search._json_ready(stress.to_dict("records")),
        "risk_flags": {
            "fixed_signal_still_from_prior_research": True,
            "uses_strategy_1b_selected_controls": True,
            "trend_and_shock_guard_choice_is_posthoc_research": True,
            "not_a_live_guarantee": True,
        },
        "hashes": {
            "script_sha256": lock_search._sha256(Path(__file__)),
            "feature_frame_sha256": lock_search._sha256(source_pool.FEATURE_FRAME),
            "signals_sha256": lock_search._sha256(OUT_DIR / "strategy_1e_signals.csv"),
        },
        "files": {
            "summary": _relpath(OUT_DIR / "summary.json"),
            "report": _relpath(OUT_DIR / "report.md"),
            "selections": _relpath(OUT_DIR / "strategy_1e_selections.csv"),
            "signals": _relpath(OUT_DIR / "strategy_1e_signals.csv"),
            "equity": _relpath(OUT_DIR / "strategy_1e_equity.csv"),
            "monthly": _relpath(OUT_DIR / "strategy_1e_monthly.csv"),
            "yearly": _relpath(OUT_DIR / "strategy_1e_yearly.csv"),
            "stress": _relpath(OUT_DIR / "strategy_1e_stress.csv"),
            "charts": [_relpath(path) for path in chart_files],
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _base_side(features: pd.DataFrame) -> np.ndarray:
    ret = features[f"ret_{BASE_WINDOW}_bps"]
    return source_pool._state_from(ret.ge(BASE_THRESHOLD_BPS), ret.le(-BASE_THRESHOLD_BPS)).astype(np.int8)


def _trend_side(features: pd.DataFrame) -> np.ndarray:
    trend_gap = features["trend_close_ema_gap_bps_60"].to_numpy(float)
    adx = features["trend_adx_30"].to_numpy(float)
    side = np.zeros(len(features), dtype=np.int8)
    side[(trend_gap >= STRONG_TREND_GAP_BPS) & (adx >= STRONG_TREND_ADX_MIN)] = 1
    side[(trend_gap <= -STRONG_TREND_GAP_BPS) & (adx >= STRONG_TREND_ADX_MIN)] = -1
    return side


def _weak_trend_mask(features: pd.DataFrame) -> np.ndarray:
    trend_gap = features["trend_close_ema_gap_bps_60"].to_numpy(float)
    adx = features["trend_adx_30"].to_numpy(float)
    return (adx < WEAK_TREND_ADX_MAX) & (np.abs(trend_gap) < WEAK_TREND_GAP_BPS)


def _simulate(
    base_side: np.ndarray,
    trend_side: np.ndarray,
    weak_trend: np.ndarray,
    market: dict[str, Any],
    selections: pd.DataFrame,
    cost_per_side: float,
    extra_delay_bars: int = 0,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    previous_position = 0.0
    previous_side = 0
    shock_cooldown = 0
    timestamp = market["timestamp"].reset_index(drop=True)
    selection_map = {row["eval_month"]: row for _, row in selections.iterrows()}

    for start, end in zip(market["month_starts"], np.r_[market["month_starts"][1:], len(base_side)]):
        month = str(market["month"][start])
        if month not in selection_map:
            continue
        params = selection_map[month]
        month_log = 0.0
        month_orders = 0
        halted = False
        quota_mode = False
        for index in range(start, end):
            signal_index = index - extra_delay_bars
            current_base_side = int(base_side[signal_index]) if signal_index >= 0 else 0
            current_trend_side = int(trend_side[signal_index]) if signal_index >= 0 else 0
            is_weak_trend = bool(weak_trend[signal_index]) if signal_index >= 0 else False
            guard_reason = "main"

            if halted:
                current_side = current_trend_side
                current_leverage = RUNNER_LEVERAGE if current_side else 0.0
                guard_reason = "post_lock_runner" if current_side else "post_lock_flat"
            else:
                current_side = current_base_side
                quota_leverage = _none_if_nan(params["quota_leverage"])
                current_leverage = (
                    min(float(quota_leverage), LEVERAGE_CAP)
                    if quota_mode
                    and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS
                    and quota_leverage is not None
                    else min(float(params["leverage"]), LEVERAGE_CAP)
                )
                conflicts_with_strong_trend = bool(
                    current_trend_side and current_base_side and current_base_side == -current_trend_side
                )
                if conflicts_with_strong_trend:
                    if month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS:
                        current_side = current_trend_side
                        current_leverage = CONFLICT_FILLER_LEVERAGE
                        guard_reason = "strong_conflict_small_trend"
                    else:
                        current_side = 0
                        current_leverage = 0.0
                        guard_reason = "strong_conflict_flat"
                elif is_weak_trend and current_base_side != previous_side and current_side:
                    current_leverage = min(current_leverage, WEAK_NEW_ORDER_LEVERAGE)
                    guard_reason = "weak_new_order_small"

                if shock_cooldown > 0 and current_side:
                    current_leverage = min(current_leverage, SHOCK_COOLDOWN_LEVERAGE)
                    guard_reason = "shock_cooldown_small"

            current_position = current_side * current_leverage
            current_turnover = abs(current_position - previous_position)
            current_orders = abs(current_side - previous_side)
            current_lr = previous_position * market["raw_return"][index] - current_turnover * cost_per_side

            adverse_shock = previous_position != 0 and previous_position * market["raw_return"][index] <= -ADVERSE_SHOCK_LOSS_LOG
            if adverse_shock:
                if not halted and current_base_side and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS:
                    current_side = current_base_side
                    current_leverage = SHOCK_COOLDOWN_LEVERAGE
                else:
                    current_side = 0
                    current_leverage = 0.0
                guard_reason = "adverse_shock_cut"
                shock_cooldown = SHOCK_COOLDOWN_BARS
                current_position = current_side * current_leverage
                current_turnover = abs(current_position - previous_position)
                current_orders = abs(current_side - previous_side)
                current_lr = previous_position * market["raw_return"][index] - current_turnover * cost_per_side
            elif shock_cooldown > 0:
                shock_cooldown -= 1

            records.append(
                {
                    "timestamp": timestamp.iloc[index],
                    "close": market["close"][index],
                    "position": current_position,
                    "active_position": previous_position,
                    "turnover": current_turnover,
                    "order_count": current_orders,
                    "strategy_log_return": current_lr,
                    "base_side": current_base_side,
                    "trend_side": current_trend_side,
                    "weak_trend": is_weak_trend,
                    "guard_reason": guard_reason,
                }
            )

            month_log += current_lr
            month_orders += current_orders
            previous_position = current_position
            previous_side = current_side

            if not halted:
                quota_arm = _none_if_nan(params["quota_arm_log"])
                quota_leverage = _none_if_nan(params["quota_leverage"])
                if (
                    quota_arm is not None
                    and quota_leverage is not None
                    and not quota_mode
                    and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS
                    and month_log >= float(quota_arm)
                ):
                    quota_mode = True
                if month_orders >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS and month_log >= float(params["lock_log"]):
                    halted = True

    equity = pd.DataFrame(records)
    equity["equity"] = np.exp(equity["strategy_log_return"].cumsum())
    equity["drawdown"] = equity["equity"] / equity["equity"].cummax() - 1.0
    return equity


def _stress_row(
    base_side: np.ndarray,
    trend_side: np.ndarray,
    weak_trend: np.ndarray,
    market: dict[str, Any],
    selections: pd.DataFrame,
    cost_per_side: float,
    extra_delay_bars: int,
) -> dict[str, Any]:
    equity = _simulate(base_side, trend_side, weak_trend, market, selections, cost_per_side, extra_delay_bars)
    monthly = lock_search._monthly_breakdown(equity)
    yearly = lock_search._yearly_breakdown(monthly)
    row = strategy_1c._result_row(equity, monthly, yearly)
    return {
        "cost_per_side": cost_per_side,
        "round_trip_cost": cost_per_side * 2,
        "extra_delay_bars": extra_delay_bars,
        **row,
        **_diagnostics(equity),
    }


def _diagnostics(equity: pd.DataFrame) -> dict[str, Any]:
    active_position = equity["active_position"].to_numpy(float)
    active_side = np.sign(active_position).astype(int)
    trend_side = equity["trend_side"].to_numpy(int)
    weak_trend = equity["weak_trend"].to_numpy(bool)
    order_count = equity["order_count"].to_numpy(int)
    target_position = equity["position"].to_numpy(float)
    strong_reverse = (trend_side != 0) & (active_side == -trend_side) & (np.abs(active_position) > 0)
    strong_reverse_big = strong_reverse & (np.abs(active_position) >= 2.0)
    weak_order = weak_trend & (order_count > 0)
    weak_big_order = weak_order & (np.abs(target_position) >= 2.0)
    return {
        "strong_trend_reverse_active_bars": int(strong_reverse.sum()),
        "strong_trend_reverse_big_active_bars": int(strong_reverse_big.sum()),
        "weak_trend_order_events": int(weak_order.sum()),
        "weak_trend_big_order_events": int(weak_big_order.sum()),
        "adverse_shock_cut_events": int((equity["guard_reason"] == "adverse_shock_cut").sum()),
        "guard_reason_counts": equity["guard_reason"].value_counts().to_dict(),
    }


def _plot_trade_charts(equity: pd.DataFrame) -> list[Path]:
    _configure_plot_font()
    chart_files: list[Path] = []
    frame = equity.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["delta_position"] = frame["position"] - frame["active_position"]
    for year in ["2025", "2026"]:
        data = frame.loc[frame["timestamp"].dt.strftime("%Y") == year].copy()
        if data.empty:
            continue
        buys = data.loc[data["delta_position"] > 0]
        sells = data.loc[data["delta_position"] < 0]
        fig, ax = plt.subplots(figsize=(20, 8), dpi=150)
        ax.plot(data["timestamp"], data["close"], color="#243040", linewidth=0.6, alpha=0.85, label="BTC收盘价")
        ax.scatter(
            buys["timestamp"],
            buys["close"],
            marker="^",
            s=_marker_sizes(buys["delta_position"].abs()),
            color="#0f9f6e",
            edgecolors="white",
            linewidths=0.25,
            label="买点：开多或平空",
            zorder=3,
        )
        ax.scatter(
            sells["timestamp"],
            sells["close"],
            marker="v",
            s=_marker_sizes(sells["delta_position"].abs()),
            color="#e33d57",
            edgecolors="white",
            linewidths=0.25,
            label="卖点：开空或平多",
            zorder=3,
        )
        ax.set_title(f"1号E策略 {year} 年 BTC 15分钟回测买卖点", fontsize=18)
        ax.set_ylabel("BTC价格 USDT")
        ax.grid(True, linestyle="--", alpha=0.25)
        ax.legend(loc="upper left")
        ax.text(
            0.01,
            0.02,
            f"买点 {len(buys)} 个；卖点 {len(sells)} 个；小点代表小仓位，大点代表主仓变化",
            transform=ax.transAxes,
            fontsize=11,
            bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#dddddd", "alpha": 0.9},
        )
        fig.autofmt_xdate(rotation=35)
        fig.tight_layout()
        path = OUT_DIR / f"strategy1e_trades_{year}.png"
        fig.savefig(path)
        plt.close(fig)
        chart_files.append(path)
    return chart_files


def _marker_sizes(values: pd.Series) -> np.ndarray:
    if values.empty:
        return np.array([])
    clipped = values.clip(lower=0.05, upper=LEVERAGE_CAP)
    return 18.0 + (clipped / LEVERAGE_CAP).to_numpy(float) * 54.0


def _configure_plot_font() -> None:
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if font_path.exists():
        from matplotlib import font_manager

        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    plt.rcParams["axes.unicode_minus"] = False


def _none_if_nan(value: Any) -> Any:
    return None if pd.isna(value) else value


def _render_report(summary: dict[str, Any]) -> str:
    row = summary["row"]
    diagnostics = summary["diagnostics"]
    return "\n".join(
        [
            "# Strategy 1E Shock Guard",
            "",
            f"- strategy_id: `{summary['strategy_id']}`",
            f"- strict_no_future_function: `{summary['strict_no_future_function']}`",
            f"- hard_pass: `{row['hard_pass']}`",
            f"- return_2025_pct: `{row['return_2025_pct']}`",
            f"- return_2026_pct: `{row['return_2026_pct']}`",
            f"- min_monthly_return_pct: `{row['min_monthly_return_pct']}`",
            f"- min_monthly_orders: `{row['min_monthly_orders']}`",
            f"- max_drawdown_pct: `{row['max_drawdown_pct']}`",
            f"- strong_trend_reverse_big_active_bars: `{diagnostics['strong_trend_reverse_big_active_bars']}`",
            f"- weak_trend_big_order_events: `{diagnostics['weak_trend_big_order_events']}`",
            f"- adverse_shock_cut_events: `{diagnostics['adverse_shock_cut_events']}`",
            "",
            "## Change",
            "",
            "- Cap selected leverage at 8x.",
            "- If the base signal fights a strong trend, do not allow a large opposite trade.",
            "- In weak trend zones, new or reverse trades are shrunk to 0.10x.",
            "- If the current closed bar badly hurts the active position, cut or shrink the next-bar target.",
        ]
    ) + "\n"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
