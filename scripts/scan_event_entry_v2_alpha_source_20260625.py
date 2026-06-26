from __future__ import annotations

import hashlib
import itertools
import json
import math
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from btc_ml_trader.backtest import run_vector_backtest


ARTIFACTS = ROOT / "artifacts"
OUT_DIR = ARTIFACTS / "event_entry_v2_alpha_source_scan_20260625"

FEATURE_FRAME = ARTIFACTS / "event_entry_fullscan" / "event_entry_best_signals.csv"
CONTRACT_SCHEMA = (
    ARTIFACTS
    / "event_entry_v2_contract_freeze_decision_20260625"
    / "event_entry_v2_contract_schema.json"
)

BACKTEST_START = "2024-01-01"
FEE_BPS = 4.0
SLIPPAGE_BPS = 2.0
BARS_PER_YEAR = int(round(525_600 / 3))
LEVERAGE_GRID = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0]
REQUIRED_RETURN_PCT = 100.0
REQUIRED_YEARS = ["2025", "2026"]
DRAWDOWN_REVIEW_FLOOR_PCT = -75.0

FORBIDDEN_INPUT_COLUMNS = {
    "target_position",
    "component",
    "event_entry_reason",
    "exit_overlay_reason",
    "time_stop_reason",
}

RET_WINDOWS = [96, 192, 384, 672, 1344, 2688]
DONCHIAN_WINDOWS = [96, 192, 384, 672, 1344, 2688]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    source = _load_feature_frame(FEATURE_FRAME)
    features = _add_closed_bar_features(source)
    market = _market_arrays(features)

    rows: list[dict[str, Any]] = []
    target_cache: dict[str, np.ndarray] = {}
    trigger_cache: dict[str, int] = {}
    for params in _candidate_defs():
        base_id = _candidate_base_id(params)
        target, trigger_rows = _target_for_params(features, params)
        target_cache[base_id] = target
        trigger_cache[base_id] = trigger_rows
        for leverage in LEVERAGE_GRID:
            rows.append(
                _scan_row(
                    market=market,
                    target=target,
                    params=params,
                    candidate_id=f"{base_id}_lev{leverage}",
                    leverage=leverage,
                    trigger_rows=trigger_rows,
                )
            )

    scan = pd.DataFrame(rows).sort_values(_sort_columns(), ascending=_sort_ascending()).reset_index(drop=True)
    scan.to_csv(OUT_DIR / "alpha_source_scan.csv", index=False)

    best_row = scan.iloc[0].to_dict() if not scan.empty else {}
    passing = scan.loc[scan["yearly_return_gate_pass"].fillna(False)] if not scan.empty else pd.DataFrame()
    best_by_return_gate = (
        passing.sort_values(
            ["min_required_year_return_pct", "total_return_pct", "annualized_sharpe"],
            ascending=[False, False, False],
        )
        .head(1)
        .to_dict("records")
    )
    best_by_return_gate_row = best_by_return_gate[0] if best_by_return_gate else {}

    best_signals_path = OUT_DIR / "best_selected_signals.csv"
    best_equity_path = OUT_DIR / "best_equity.csv"
    best_monthly_path = OUT_DIR / "best_monthly.csv"
    best_yearly_path = OUT_DIR / "best_yearly.csv"

    if best_row:
        best_params = json.loads(str(best_row["params_json"]))
        best_target, _ = _target_for_params(features, best_params)
        best_signals = _signals(features, best_target, best_params, str(best_row["candidate_id"]))
        best_signals.to_csv(best_signals_path, index=False)
        equity, stats = run_vector_backtest(
            best_signals,
            fee_bps=FEE_BPS,
            slippage_bps=SLIPPAGE_BPS,
            bars_per_year=BARS_PER_YEAR,
            max_leverage=float(best_row["leverage"]),
        )
        monthly = _monthly_breakdown(equity, best_signals)
        yearly = _yearly_breakdown(monthly)
        formal_year_map = {
            str(row["year"]): float(row["compounded_return_pct"]) for _, row in yearly.iterrows()
        }
        best_row["formal_return_2025_pct"] = formal_year_map.get("2025")
        best_row["formal_return_2026_pct"] = formal_year_map.get("2026")
        best_row["formal_yearly_return_gate_pass"] = bool(
            best_row["formal_return_2025_pct"] is not None
            and best_row["formal_return_2026_pct"] is not None
            and best_row["formal_return_2025_pct"] >= REQUIRED_RETURN_PCT
            and best_row["formal_return_2026_pct"] >= REQUIRED_RETURN_PCT
        )
        equity.to_csv(best_equity_path, index=False)
        monthly.to_csv(best_monthly_path, index=False)
        yearly.to_csv(best_yearly_path, index=False)
        best_stats = asdict(stats)
        best_yearly = yearly.to_dict("records")
        best_monthly = _monthly_summary(monthly)
    else:
        best_stats = {}
        best_yearly = []
        best_monthly = {}

    summary = _summary(
        generated_at=generated_at,
        source=source,
        scan=scan,
        best_row=best_row,
        best_by_return_gate_row=best_by_return_gate_row,
        best_stats=best_stats,
        best_yearly=best_yearly,
        best_monthly=best_monthly,
        best_signals_path=best_signals_path if best_row else None,
    )
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": summary["status"],
                "scan_rows": summary["scan_rows"],
                "passing_candidates": summary["passing_candidates"],
                "best_candidate": summary["best_candidate"],
                "best_by_return_gate": summary["best_by_return_gate"],
                "candidate_ready": summary["candidate_ready"],
                "entry_capable": summary["entry_capable"],
                "live_promotion": summary["live_promotion"],
                "hard_veto": summary["hard_veto"],
                "files": summary["files"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def _load_feature_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, low_memory=False)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.loc[frame["timestamp"].notna()].sort_values("timestamp").reset_index(drop=True)
    frame = frame.loc[frame["timestamp"] >= pd.Timestamp(BACKTEST_START, tz="UTC")].reset_index(drop=True)
    dropped = [column for column in frame.columns if column in FORBIDDEN_INPUT_COLUMNS]
    out = frame[[column for column in frame.columns if column not in FORBIDDEN_INPUT_COLUMNS]].copy()
    out.attrs["dropped_forbidden_columns"] = dropped
    numeric_columns = [column for column in out.columns if column != "timestamp"]
    for column in numeric_columns:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    required = {
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "atr_30",
        "natr_30",
        "trend_close_ema_gap_bps_60",
        "trend_adx_30",
        "trend_donchian_pos_30",
        "ema20",
        "ema50",
        "ema100",
        "rsi14",
        "bbu",
        "bbl",
    }
    missing = required.difference(out.columns)
    if missing:
        raise ValueError(f"Missing required feature columns: {sorted(missing)}")
    return out


def _add_closed_bar_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for span in [20, 50, 100]:
        ema = out[f"ema{span}"].replace(0, np.nan)
        out[f"close_ema{span}_gap_bps"] = (out["close"] / ema - 1.0) * 10_000.0
    band_width = (out["bbu"] - out["bbl"]).replace(0, np.nan)
    out["bb_pos"] = (out["close"] - out["bbl"]) / band_width
    for bars in sorted(set([12, 24, *RET_WINDOWS])):
        out[f"ret_{bars}_bps"] = out["close"].pct_change(bars) * 10_000.0
    for window in DONCHIAN_WINDOWS:
        prior_high = out["high"].rolling(window).max().shift(1)
        prior_low = out["low"].rolling(window).min().shift(1)
        out[f"donchian_pos_{window}"] = (out["close"] - prior_low) / (prior_high - prior_low).replace(0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan)


def _candidate_defs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for gap_min, adx_min, mode in itertools.product(
        [50.0, 100.0, 200.0, 350.0, 500.0, 800.0, 1200.0],
        [0.0, 8.0, 12.0, 18.0, 24.0, 30.0, 36.0],
        ["momentum", "fade"],
    ):
        rows.append(
            {
                "family": "gap_adx_regime",
                "mode": mode,
                "gap_min": gap_min,
                "adx_min": adx_min,
            }
        )
    for window, threshold, mode in itertools.product(
        RET_WINDOWS,
        [50.0, 100.0, 200.0, 350.0, 500.0, 800.0, 1200.0, 1800.0, 2500.0],
        ["momentum", "fade"],
    ):
        rows.append(
            {
                "family": "long_return_regime",
                "mode": mode,
                "window": window,
                "threshold_bps": threshold,
            }
        )
    for window, band, mode in itertools.product(
        DONCHIAN_WINDOWS,
        [(0.05, 0.95), (0.10, 0.90), (0.15, 0.85), (0.20, 0.80), (0.25, 0.75), (0.30, 0.70), (0.35, 0.65)],
        ["breakout", "fade"],
    ):
        low, high = band
        rows.append(
            {
                "family": "donchian_regime",
                "mode": mode,
                "window": window,
                "low_band": low,
                "high_band": high,
            }
        )
    for low, high, mode in itertools.product(
        [20.0, 25.0, 30.0, 35.0, 40.0, 45.0],
        [55.0, 60.0, 65.0, 70.0, 75.0, 80.0],
        ["momentum", "fade"],
    ):
        if low >= high:
            continue
        rows.append(
            {
                "family": "rsi_regime",
                "mode": mode,
                "low": low,
                "high": high,
            }
        )
    return rows


def _candidate_base_id(params: dict[str, Any]) -> str:
    digest = hashlib.sha1(json.dumps(params, sort_keys=True).encode("utf-8")).hexdigest()[:10]
    return f"alpha_{params['family']}_{params['mode']}_{digest}"


def _target_for_params(features: pd.DataFrame, params: dict[str, Any]) -> tuple[np.ndarray, int]:
    family = params["family"]
    mode = params["mode"]
    if family == "gap_adx_regime":
        gap = features["trend_close_ema_gap_bps_60"]
        adx = features["trend_adx_30"]
        positive = gap.ge(params["gap_min"]) & adx.ge(params["adx_min"])
        negative = gap.le(-params["gap_min"]) & adx.ge(params["adx_min"])
        if mode == "momentum":
            return _state_from(positive, negative)
        return _state_from(negative, positive)
    if family == "long_return_regime":
        ret = features[f"ret_{int(params['window'])}_bps"]
        positive = ret.ge(params["threshold_bps"])
        negative = ret.le(-params["threshold_bps"])
        if mode == "momentum":
            return _state_from(positive, negative)
        return _state_from(negative, positive)
    if family == "donchian_regime":
        pos = features[f"donchian_pos_{int(params['window'])}"]
        upper = pos.ge(params["high_band"])
        lower = pos.le(params["low_band"])
        if mode == "breakout":
            return _state_from(upper, lower)
        return _state_from(lower, upper)
    if family == "rsi_regime":
        high = features["rsi14"].ge(params["high"])
        low = features["rsi14"].le(params["low"])
        if mode == "momentum":
            return _state_from(high, low)
        return _state_from(low, high)
    raise ValueError(f"Unknown family: {family}")


def _state_from(long_condition: pd.Series, short_condition: pd.Series) -> tuple[np.ndarray, int]:
    long_values = long_condition.fillna(False).to_numpy(bool)
    short_values = short_condition.fillna(False).to_numpy(bool)
    target = np.zeros(len(long_values), dtype=np.int8)
    active_side = 0
    trigger_rows = int(np.count_nonzero(long_values | short_values))
    for index, (long_hit, short_hit) in enumerate(zip(long_values, short_values)):
        if long_hit:
            active_side = 1
        elif short_hit:
            active_side = -1
        target[index] = active_side
    return target, trigger_rows


def _market_arrays(features: pd.DataFrame) -> dict[str, Any]:
    raw_return = np.log(features["close"].astype(float)).diff().fillna(0.0).to_numpy(float)
    years = pd.to_datetime(features["timestamp"], utc=True).dt.year.astype(str).to_numpy()
    return {
        "raw_return": raw_return,
        "year_masks": {year: years == year for year in REQUIRED_YEARS},
        "bars_per_year": BARS_PER_YEAR,
    }


def _scan_row(
    *,
    market: dict[str, Any],
    target: np.ndarray,
    params: dict[str, Any],
    candidate_id: str,
    leverage: float,
    trigger_rows: int,
) -> dict[str, Any]:
    position = target.astype(float) * leverage
    active_position = np.r_[0.0, position[:-1]]
    turnover = np.abs(np.diff(position, prepend=0.0))
    cost_per_turnover = (FEE_BPS + SLIPPAGE_BPS) / 10_000.0
    strategy_log_return = active_position * market["raw_return"] - turnover * cost_per_turnover
    equity = np.exp(np.cumsum(strategy_log_return))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    return_std = strategy_log_return.std()
    active_returns = strategy_log_return[np.abs(active_position) > 0]
    gains = active_returns[active_returns > 0].sum()
    losses = active_returns[active_returns < 0].sum()
    yearly_returns = {
        year: (np.exp(strategy_log_return[mask].sum()) - 1.0) * 100.0
        for year, mask in market["year_masks"].items()
    }
    y2025 = yearly_returns.get("2025")
    y2026 = yearly_returns.get("2026")
    yearly_gate_pass = bool(
        y2025 is not None
        and y2026 is not None
        and y2025 >= REQUIRED_RETURN_PCT
        and y2026 >= REQUIRED_RETURN_PCT
    )
    max_drawdown_pct = float(drawdown.min() * 100.0)
    return {
        "candidate_id": candidate_id,
        "family": params["family"],
        "mode": params["mode"],
        "leverage": float(leverage),
        "total_return_pct": float((equity[-1] - 1.0) * 100.0),
        "annualized_sharpe": float(
            0.0 if return_std == 0 else (strategy_log_return.mean() / return_std) * math.sqrt(BARS_PER_YEAR)
        ),
        "max_drawdown_pct": max_drawdown_pct,
        "exposure_pct": float((np.abs(active_position) > 0).mean() * 100.0),
        "turnover": float(turnover.sum()),
        "trade_count": int(np.count_nonzero(turnover)),
        "win_rate_pct": float(0.0 if active_returns.size == 0 else (active_returns > 0).mean() * 100.0),
        "profit_factor": float("inf") if losses == 0 and gains > 0 else float(gains / abs(losses) if losses != 0 else 0.0),
        "return_2025_pct": float(y2025) if y2025 is not None else None,
        "return_2026_pct": float(y2026) if y2026 is not None else None,
        "min_required_year_return_pct": float(
            min(
                y2025 if y2025 is not None else -999.0,
                y2026 if y2026 is not None else -999.0,
            )
        ),
        "yearly_return_gate_pass": yearly_gate_pass,
        "drawdown_review_gate_pass": bool(max_drawdown_pct >= DRAWDOWN_REVIEW_FLOOR_PCT),
        "active_rows": int(np.count_nonzero(target)),
        "segments": int(_segment_count(target)),
        "trigger_rows": int(trigger_rows),
        "params_json": json.dumps(_json_ready(params), ensure_ascii=False, sort_keys=True),
    }


def _signals(features: pd.DataFrame, target: np.ndarray, params: dict[str, Any], candidate_id: str) -> pd.DataFrame:
    out = features[["timestamp", "open", "high", "low", "close"]].copy()
    out["target_position"] = target.astype(float)
    active = target != 0
    out["component"] = np.where(active, f"v2_alpha_{params['family']}", "flat")
    out["entry_reason"] = np.where(active, f"v2_alpha_{params['family']}_{params['mode']}", "")
    out["exit_reason"] = _exit_reasons(target)
    out["action"] = _actions(target)
    out["confidence"] = np.where(active, 0.6, 1.0)
    out["data_basis"] = "event_entry_fullscan_closed_bar_feature_frame_labels_dropped"
    out["candidate_version"] = candidate_id
    return out


def _actions(target: np.ndarray) -> list[str]:
    previous = np.r_[0, target[:-1]]
    actions = []
    for old, new in zip(previous, target):
        old = int(old)
        new = int(new)
        if old == new:
            actions.append("hold")
        elif old == 0 and new == 1:
            actions.append("enter_long")
        elif old == 0 and new == -1:
            actions.append("enter_short")
        elif old == 1 and new == 0:
            actions.append("exit_long")
        elif old == -1 and new == 0:
            actions.append("exit_short")
        elif new == 1:
            actions.append("flip_long")
        elif new == -1:
            actions.append("flip_short")
        else:
            actions.append("hold")
    return actions


def _exit_reasons(target: np.ndarray) -> np.ndarray:
    previous = np.r_[0, target[:-1]]
    reasons = np.full(len(target), "", dtype=object)
    for index, (old, new) in enumerate(zip(previous, target)):
        old = int(old)
        new = int(new)
        if old != 0 and new == 0:
            reasons[index] = "alpha_state_flatten"
        elif old != 0 and new != 0 and old != new:
            reasons[index] = "alpha_state_flip"
    return reasons


def _monthly_breakdown(equity: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    eq = equity.copy()
    sig = signals.copy()
    eq["timestamp"] = pd.to_datetime(eq["timestamp"], utc=True)
    sig["timestamp"] = pd.to_datetime(sig["timestamp"], utc=True)
    eq["month"] = eq["timestamp"].dt.strftime("%Y-%m")
    sig["month"] = sig["timestamp"].dt.strftime("%Y-%m")
    monthly = eq.groupby("month").agg(
        first_equity=("equity", "first"),
        last_equity=("equity", "last"),
        min_drawdown=("drawdown", "min"),
        turnover=("turnover", "sum"),
    )
    monthly["return_pct"] = (monthly["last_equity"] / monthly["first_equity"] - 1.0) * 100.0
    entries = sig.loc[sig["action"].isin(["enter_long", "enter_short", "flip_long", "flip_short"])].groupby("month").size()
    exits = sig.loc[sig["action"].isin(["exit_long", "exit_short", "flip_long", "flip_short"])].groupby("month").size()
    monthly["entries"] = entries
    monthly["exits"] = exits
    monthly[["entries", "exits"]] = monthly[["entries", "exits"]].fillna(0).astype(int)
    monthly["drawdown_pct"] = monthly["min_drawdown"] * 100.0
    return monthly.reset_index()


def _yearly_breakdown(monthly: pd.DataFrame) -> pd.DataFrame:
    if monthly.empty:
        return pd.DataFrame()
    frame = monthly.copy()
    frame["year"] = frame["month"].str[:4]
    return frame.groupby("year").agg(
        compounded_return_pct=("return_pct", lambda values: (values.div(100.0).add(1.0).prod() - 1.0) * 100.0),
        months=("month", "count"),
        losing_months=("return_pct", lambda values: int((values < 0).sum())),
        entries=("entries", "sum"),
        exits=("exits", "sum"),
        min_monthly_return_pct=("return_pct", "min"),
        max_drawdown_pct=("drawdown_pct", "min"),
    ).reset_index()


def _monthly_summary(monthly: pd.DataFrame) -> dict[str, Any]:
    if monthly.empty:
        return {}
    return {
        "months": int(len(monthly)),
        "losing_months": int((monthly["return_pct"] < 0).sum()),
        "worst_month": str(monthly.loc[monthly["return_pct"].idxmin(), "month"]),
        "worst_month_return_pct": float(monthly["return_pct"].min()),
        "best_month": str(monthly.loc[monthly["return_pct"].idxmax(), "month"]),
        "best_month_return_pct": float(monthly["return_pct"].max()),
    }


def _summary(
    *,
    generated_at: str,
    source: pd.DataFrame,
    scan: pd.DataFrame,
    best_row: dict[str, Any],
    best_by_return_gate_row: dict[str, Any],
    best_stats: dict[str, Any],
    best_yearly: list[dict[str, Any]],
    best_monthly: dict[str, Any],
    best_signals_path: Path | None,
) -> dict[str, Any]:
    passing = scan.loc[scan["yearly_return_gate_pass"].fillna(False)] if not scan.empty else pd.DataFrame()
    passing_review = passing.loc[passing["drawdown_review_gate_pass"].fillna(False)] if not passing.empty else pd.DataFrame()
    hard_veto = [
        "research_scan_only_not_live_source",
        "entry_capable_false",
        "downstream_rebuild_not_allowed",
        "monthly_meta_late_era_rebuild_not_run",
        "observe_paper_mock_acceptance_not_run",
        "explicit_user_live_confirmation_missing",
        "LIVE_PROMOTION_NO_GO",
    ]
    if passing.empty:
        hard_veto.append("no_candidate_passed_2025_2026_return_gate")
    else:
        hard_veto.append("return_gate_pass_is_alpha_source_only_not_promotion")
    if passing_review.empty:
        hard_veto.append("no_return_gate_candidate_with_drawdown_review_floor")
    else:
        hard_veto.append("drawdown_and_robustness_review_still_required")
    return {
        "status": "event_entry_v2_alpha_source_scan_ready",
        "generated_at": generated_at,
        "research_only": True,
        "execution_ready": False,
        "execution_ready_source": False,
        "orders_generated": False,
        "orders_submitted": False,
        "live_actions_taken": False,
        "entry_capable": False,
        "candidate_ready": False,
        "return_gate_candidate_found": bool(not passing.empty),
        "return_gate_and_drawdown_review_candidate_found": bool(not passing_review.empty),
        "downstream_rebuild_allowed": False,
        "live_promotion": "LIVE_PROMOTION_NO_GO",
        "contract_schema": str(CONTRACT_SCHEMA),
        "source_feature_frame": str(FEATURE_FRAME),
        "source_forbidden_columns_dropped": source.attrs.get("dropped_forbidden_columns", []),
        "non_oracle_claim": (
            "The scan uses closed-bar price/indicator columns only. Legacy target, component, and reason labels "
            "are dropped before rule generation."
        ),
        "scan_rows": int(len(scan)),
        "passing_candidates": int(len(passing)),
        "passing_candidates_with_drawdown_review_floor": int(len(passing_review)),
        "best_candidate": _json_ready(best_row),
        "best_by_return_gate": _json_ready(best_by_return_gate_row),
        "best_stats": _json_ready(best_stats),
        "best_yearly": _json_ready(best_yearly),
        "best_monthly_summary": _json_ready(best_monthly),
        "cost": {
            "fee_bps": FEE_BPS,
            "slippage_bps": SLIPPAGE_BPS,
            "leverage_grid": LEVERAGE_GRID,
            "bars_per_year": BARS_PER_YEAR,
            "return_timing": "position decided at bar t participates in bar t+1 return",
        },
        "yearly_return_gate": {
            "backtest_start": BACKTEST_START,
            "required_return_pct": REQUIRED_RETURN_PCT,
            "required_years": REQUIRED_YEARS,
            "decision_rule": "Reject as final if either 2025 or 2026 return is below 100%.",
        },
        "drawdown_review_floor": {
            "max_drawdown_pct_must_be_at_least": DRAWDOWN_REVIEW_FLOOR_PCT,
            "purpose": "Review floor for choosing the next alpha source candidate, not a live approval rule.",
        },
        "assessment": (
            "This scan searches for a fresh closed-bar alpha source after coarse state-combiner and low-frequency "
            "quality/cooldown scans failed. It can identify an alpha direction, but it does not create a live source "
            "or unblock downstream lineage."
        ),
        "hard_veto": hard_veto,
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "feature_frame_sha256": _sha256(FEATURE_FRAME),
            "contract_schema_sha256": _sha256(CONTRACT_SCHEMA),
            "best_selected_signals_sha256": _sha256(best_signals_path) if best_signals_path else None,
        },
        "files": {
            "summary": str(OUT_DIR / "summary.json"),
            "report": str(OUT_DIR / "report.md"),
            "alpha_source_scan": str(OUT_DIR / "alpha_source_scan.csv"),
            "best_selected_signals": str(best_signals_path) if best_signals_path else None,
            "best_equity": str(OUT_DIR / "best_equity.csv") if best_signals_path else None,
            "best_monthly": str(OUT_DIR / "best_monthly.csv") if best_signals_path else None,
            "best_yearly": str(OUT_DIR / "best_yearly.csv") if best_signals_path else None,
        },
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_candidate"]
    best_return = summary["best_by_return_gate"]
    lines = [
        "# Event Entry V2 Alpha Source Scan",
        "",
        f"- Status: `{summary['status']}`",
        f"- Passing candidates: `{summary['passing_candidates']}`",
        f"- Passing candidates with drawdown review floor: `{summary['passing_candidates_with_drawdown_review_floor']}`",
        f"- Candidate ready: `{summary['candidate_ready']}`",
        f"- Entry capable: `{summary['entry_capable']}`",
        f"- Live promotion: `{summary['live_promotion']}`",
        "",
        "## Best Review Candidate",
        "",
        f"- Candidate: `{best.get('candidate_id')}`",
        f"- Family: `{best.get('family')}`",
        f"- Mode: `{best.get('mode')}`",
        f"- Leverage: `{best.get('leverage')}`",
        f"- Total return: `{best.get('total_return_pct')}`",
        f"- 2025 return: `{best.get('return_2025_pct')}`",
        f"- 2026 return: `{best.get('return_2026_pct')}`",
        f"- Formal 2025 return: `{best.get('formal_return_2025_pct')}`",
        f"- Formal 2026 return: `{best.get('formal_return_2026_pct')}`",
        f"- Formal yearly gate pass: `{best.get('formal_yearly_return_gate_pass')}`",
        f"- Yearly gate pass: `{best.get('yearly_return_gate_pass')}`",
        f"- Max drawdown: `{best.get('max_drawdown_pct')}`",
        f"- Exposure: `{best.get('exposure_pct')}`",
        f"- Segments: `{best.get('segments')}`",
        "",
        "## Highest Return-Gate Candidate",
        "",
        f"- Candidate: `{best_return.get('candidate_id')}`",
        f"- Family: `{best_return.get('family')}`",
        f"- Leverage: `{best_return.get('leverage')}`",
        f"- 2025 return: `{best_return.get('return_2025_pct')}`",
        f"- 2026 return: `{best_return.get('return_2026_pct')}`",
        f"- Max drawdown: `{best_return.get('max_drawdown_pct')}`",
        "",
        "## Guard",
        "",
    ]
    lines.extend(f"- `{item}`" for item in summary["hard_veto"])
    lines.append("")
    return "\n".join(lines)


def _sort_columns() -> list[str]:
    return [
        "yearly_return_gate_pass",
        "drawdown_review_gate_pass",
        "min_required_year_return_pct",
        "max_drawdown_pct",
        "total_return_pct",
        "annualized_sharpe",
    ]


def _sort_ascending() -> list[bool]:
    return [False, False, False, False, False, False]


def _segment_count(target: np.ndarray) -> int:
    active = target != 0.0
    previous_active = np.r_[False, active[:-1]]
    previous_target = np.r_[0.0, target[:-1]]
    starts = active & (~previous_active | (np.sign(target) != np.sign(previous_target)))
    return int(starts.sum())


def _sha256(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is pd.NA:
        return None
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
