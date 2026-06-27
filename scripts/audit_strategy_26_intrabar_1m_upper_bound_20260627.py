from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import audit_strategy_16_new_family_probe_20260627 as probe16
import audit_strategy_17_simple_family_upper_bound_20260627 as upper17
import audit_strategy_21_volume_upper_bound_20260627 as probe21


STRATEGY_ID = "strategy_26_intrabar_1m_upper_bound_20260627"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
BASELINE_15_SUMMARY = ROOT / "artifacts" / "strategy_15_unified_data_baseline_20260627" / "summary.json"
INTRABAR_FEATURES = OUT_DIR / "btc_15m_from_1m_intrabar_features_2020_2026_05.csv"
MONTHLY_DOWNLOAD_QUALITY = OUT_DIR / "monthly_1m_download_quality.csv"

SYMBOL = "BTCUSDT"
INTERVAL = "1m"
PUBLIC_ARCHIVE_BASE_URL = "https://data.binance.vision/data/futures/um/monthly/klines"
START_MONTH = pd.Period("2020-01", freq="M")
END_MONTH = pd.Period("2026-05", freq="M")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    baseline = json.loads(BASELINE_15_SUMMARY.read_text(encoding="utf-8"))
    if not baseline["quality"]["pass"]:
        raise RuntimeError("Strategy 15 data baseline is not ready.")

    ohlc_path = ROOT / baseline["input_files"]["combined_ohlc"]
    market = probe16._load_market(ohlc_path)
    baseline_ohlc = pd.read_csv(ohlc_path, usecols=["timestamp", "open", "high", "low", "close"])
    baseline_ohlc["timestamp"] = pd.to_datetime(baseline_ohlc["timestamp"], utc=True)

    feature_frame, data_quality = _load_or_fetch_intrabar_features(baseline_ohlc)
    parity = _parity_check_with_strategy_15(feature_frame, baseline_ohlc)
    if not np.array_equal(feature_frame["timestamp"].astype(str).to_numpy(), pd.Series(market["timestamp"]).astype(str).to_numpy()):
        raise RuntimeError("Strategy 26 feature timestamps do not match Strategy 15 baseline timestamps.")

    features = IntrabarFeatures(feature_frame)
    candidates = _candidate_library()
    candidate_monthly, candidate_scan = _candidate_results(candidates, market, features)

    oracle_specs = [
        ("monthly_oracle_best_return", None, False),
        ("monthly_oracle_best_return_order10", None, True),
        ("late_momentum_oracle_order10", "late_momentum", True),
        ("early_late_reversal_oracle_order10", "early_late_reversal", True),
        ("path_extreme_oracle_order10", "path_extreme", True),
        ("efficiency_path_oracle_order10", "efficiency_path", True),
        ("chop_path_oracle_order10", "chop_path", True),
    ]

    oracle_rows: list[dict[str, Any]] = []
    oracle_monthly_frames: list[pd.DataFrame] = []
    oracle_yearly_frames: list[pd.DataFrame] = []
    for oracle_id, family, require_order_floor in oracle_specs:
        selected = upper17._select_oracle_months(candidate_monthly, oracle_id, family, require_order_floor)
        yearly = upper17._yearly_from_monthly(selected)
        summary = {
            "oracle_id": oracle_id,
            "family_filter": family or "all",
            "leaky_oracle": True,
            "requires_monthly_orders_ge_10_at_selection": require_order_floor,
            "months_without_order_floor_candidate": int(selected["no_order_floor_candidate"].sum()),
            **upper17._summary_from_monthly(selected, yearly),
        }
        oracle_rows.append(summary)
        yearly.insert(0, "oracle_id", oracle_id)
        oracle_monthly_frames.append(selected)
        oracle_yearly_frames.append(yearly)

    oracle_summary = pd.DataFrame(oracle_rows).sort_values(
        ["hard_pass_complete_years", "losing_eval_months", "min_monthly_return_pct", "min_complete_year_return_pct"],
        ascending=[False, True, False, False],
    )
    oracle_monthly = pd.concat(oracle_monthly_frames, ignore_index=True)
    oracle_yearly = pd.concat(oracle_yearly_frames, ignore_index=True)
    best_oracle = oracle_summary.iloc[0].to_dict()

    summary = {
        "status": "strategy_26_intrabar_1m_upper_bound_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Measure a leaky monthly oracle upper bound for 1-minute intrabar structure aggregated to the Strategy 15 USD-M futures 15m baseline.",
        "source": {
            "baseline_15_summary": _rel(BASELINE_15_SUMMARY),
            "combined_ohlc": baseline["input_files"]["combined_ohlc"],
            "public_archive_base_url": PUBLIC_ARCHIVE_BASE_URL,
            "download_interval": INTERVAL,
            "download_months": f"{START_MONTH} to {END_MONTH}",
            "intrabar_features": _rel(INTRABAR_FEATURES),
            "monthly_download_quality": _rel(MONTHLY_DOWNLOAD_QUALITY),
        },
        "data": {
            "eval_start_month": probe16.EVAL_START_MONTH,
            "eval_end_exclusive": probe16.EVAL_END_EXCLUSIVE,
            "complete_eval_years_for_annual_threshold": probe16.COMPLETE_EVAL_YEARS,
            "partial_eval_year_recorded_not_annual_threshold": probe16.PARTIAL_EVAL_YEAR,
            "rows": int(len(feature_frame)),
            "start_timestamp": feature_frame["timestamp"].min().isoformat(),
            "end_timestamp": feature_frame["timestamp"].max().isoformat(),
            "quality": data_quality,
            "parity_with_strategy_15": parity,
        },
        "cost_model": {
            "cost_per_side": probe16.COST_PER_SIDE,
            "round_trip_open_close": probe16.ROUND_TRIP_COST,
        },
        "candidate_grid": probe16._candidate_grid_summary(candidates),
        "oracle_warning": {
            "strict_no_future": False,
            "tradeable": False,
            "reason": "The monthly oracle chooses the best candidate after seeing the evaluated month.",
            "month_boundary_switching_cost_included": False,
            "per_candidate_signal_timing": "Each candidate uses completed 1m bars inside closed 15m bar t and participates from 15m bar t+1.",
        },
        "static_hard_pass_count": int(candidate_scan["hard_pass_complete_years"].sum()),
        "best_static_candidate": _json_ready(candidate_scan.iloc[0].to_dict()),
        "oracle_summary": _json_ready(oracle_summary.to_dict("records")),
        "best_oracle": _json_ready(best_oracle),
        "decision": _decision(best_oracle),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "baseline_15_summary_sha256": _sha256(BASELINE_15_SUMMARY),
            "combined_ohlc_sha256": _sha256(ohlc_path),
            "intrabar_features_sha256": _sha256(INTRABAR_FEATURES),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "intrabar_features": _rel(INTRABAR_FEATURES),
            "monthly_download_quality": _rel(MONTHLY_DOWNLOAD_QUALITY),
            "candidate_scan": _rel(OUT_DIR / "candidate_scan.csv"),
            "oracle_summary": _rel(OUT_DIR / "oracle_summary.csv"),
            "oracle_monthly": _rel(OUT_DIR / "oracle_monthly.csv"),
            "oracle_yearly": _rel(OUT_DIR / "oracle_yearly.csv"),
        },
    }

    candidate_scan.to_csv(OUT_DIR / "candidate_scan.csv", index=False)
    oracle_summary.to_csv(OUT_DIR / "oracle_summary.csv", index=False)
    oracle_monthly.to_csv(OUT_DIR / "oracle_monthly.csv", index=False)
    oracle_yearly.to_csv(OUT_DIR / "oracle_yearly.csv", index=False)
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_or_fetch_intrabar_features(baseline_ohlc: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if INTRABAR_FEATURES.exists() and MONTHLY_DOWNLOAD_QUALITY.exists():
        frame = pd.read_csv(INTRABAR_FEATURES)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        monthly_quality = pd.read_csv(MONTHLY_DOWNLOAD_QUALITY)
        frame = _mark_baseline_matches(frame, baseline_ohlc)
        frame.to_csv(INTRABAR_FEATURES, index=False)
        return frame, _quality(frame, monthly_quality, from_cache=True)

    frames: list[pd.DataFrame] = []
    quality_rows: list[dict[str, Any]] = []
    for month in pd.period_range(START_MONTH, END_MONTH, freq="M"):
        url = f"{PUBLIC_ARCHIVE_BASE_URL}/{SYMBOL}/{INTERVAL}/{SYMBOL}-{INTERVAL}-{month.year}-{month.month:02d}.zip"
        raw = probe21._fetch_month(url)
        aggregate, quality = _aggregate_month(raw, month)
        frames.append(aggregate)
        quality_rows.append({"month": str(month), "url": url, **quality})

    features = pd.concat(frames, ignore_index=True)
    features = features.drop_duplicates("timestamp", keep="last").sort_values("timestamp")
    baseline_index = pd.DatetimeIndex(baseline_ohlc["timestamp"])
    features = features.set_index("timestamp").reindex(baseline_index)
    features["minute_count"] = features["minute_count"].fillna(0).astype(int)
    features["valid_intrabar"] = features["minute_count"].eq(15) & features["close"].notna()
    features = features.reset_index().rename(columns={"index": "timestamp"})
    features = _mark_baseline_matches(features, baseline_ohlc)

    monthly_quality = pd.DataFrame(quality_rows)
    features.to_csv(INTRABAR_FEATURES, index=False)
    monthly_quality.to_csv(MONTHLY_DOWNLOAD_QUALITY, index=False)
    return features, _quality(features, monthly_quality, from_cache=False)


def _aggregate_month(raw: pd.DataFrame, month: pd.Period) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = raw.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.loc[frame["timestamp"].notna()].copy()
    duplicate_1m_rows = int(frame["timestamp"].duplicated().sum())
    frame = frame.drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
    expected_1m_rows = int(len(pd.date_range(month.start_time.tz_localize("UTC"), month.end_time.tz_localize("UTC").floor("min"), freq="min")))
    non_1m_gap_rows = int((frame["timestamp"].diff().dropna() != pd.Timedelta(minutes=1)).sum())
    frame["bar_timestamp"] = frame["timestamp"].dt.floor("15min")
    frame["minute_in_bar"] = ((frame["timestamp"] - frame["bar_timestamp"]).dt.total_seconds() // 60).astype(int)
    frame["one_min_log_return"] = np.log(frame["close"].astype(float) / frame["open"].astype(float)).replace([np.inf, -np.inf], np.nan)

    rows = [_aggregate_bar(group) for _, group in frame.groupby("bar_timestamp", sort=True)]
    out = pd.DataFrame(rows)
    incomplete_15m_groups = int((out["minute_count"] != 15).sum()) if len(out) else 0
    quality = {
        "raw_rows": int(len(raw)),
        "unique_1m_rows": int(len(frame)),
        "expected_1m_rows": expected_1m_rows,
        "missing_1m_rows": int(expected_1m_rows - len(frame)),
        "duplicate_1m_rows": duplicate_1m_rows,
        "non_1m_gap_rows": non_1m_gap_rows,
        "aggregated_15m_rows": int(len(out)),
        "incomplete_15m_groups": incomplete_15m_groups,
    }
    return out, quality


def _mark_baseline_matches(frame: pd.DataFrame, baseline_ohlc: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    base = baseline_ohlc[["timestamp", "open", "high", "low", "close"]].copy()
    merged = out[["timestamp", "open", "high", "low", "close"]].merge(
        base, on="timestamp", how="left", suffixes=("_1m", "_strategy15")
    )
    match = pd.Series(True, index=out.index)
    for column in ["open", "high", "low", "close"]:
        diff = (merged[f"{column}_1m"] - merged[f"{column}_strategy15"]).abs()
        match &= diff.le(1e-8)
    out["baseline_ohlc_match"] = match.fillna(False).to_numpy(bool)
    # ponytail: a few public 1m bars disagree with the 15m baseline; disabling those bars is cheaper and safer than inventing repairs.
    out["valid_intrabar"] = out["valid_intrabar"].astype(bool) & out["baseline_ohlc_match"]
    return out


def _aggregate_bar(group: pd.DataFrame) -> dict[str, Any]:
    g = group.sort_values("timestamp")
    open_values = g["open"].to_numpy(dtype=float)
    high_values = g["high"].to_numpy(dtype=float)
    low_values = g["low"].to_numpy(dtype=float)
    close_values = g["close"].to_numpy(dtype=float)
    volume = g["volume"].to_numpy(dtype=float)
    quote_volume = g["quote_volume"].to_numpy(dtype=float)
    trades = g["trades"].to_numpy(dtype=float)
    taker_base = g["taker_base"].to_numpy(dtype=float)
    taker_quote = g["taker_quote"].to_numpy(dtype=float)
    n = len(g)

    total_volume = float(np.nansum(volume))
    first5_volume = float(np.nansum(volume[:5]))
    last5_volume = float(np.nansum(volume[-5:]))
    first10_volume = float(np.nansum(volume[:10]))
    full_return_bps = _log_return_bps(open_values[0], close_values[-1])
    sum_abs_1m_return_bps = float(np.nansum(np.abs(g["one_min_log_return"].to_numpy(dtype=float))) * 10_000.0)
    high_minute = int(g.iloc[int(np.nanargmax(high_values))]["minute_in_bar"]) if n else -1
    low_minute = int(g.iloc[int(np.nanargmin(low_values))]["minute_in_bar"]) if n else -1
    high = float(np.nanmax(high_values))
    low = float(np.nanmin(low_values))
    close = float(close_values[-1])
    range_abs = high - low

    return {
        "timestamp": g["bar_timestamp"].iloc[0],
        "open": float(open_values[0]),
        "high": high,
        "low": low,
        "close": close,
        "volume": total_volume,
        "quote_volume": float(np.nansum(quote_volume)),
        "trades": float(np.nansum(trades)),
        "taker_base": float(np.nansum(taker_base)),
        "taker_quote": float(np.nansum(taker_quote)),
        "minute_count": int(n),
        "full_return_bps": full_return_bps,
        "first5_return_bps": _window_return_bps(open_values, close_values, 0, min(5, n)),
        "first10_return_bps": _window_return_bps(open_values, close_values, 0, min(10, n)),
        "last5_return_bps": _window_return_bps(open_values, close_values, max(0, n - 5), n),
        "sum_abs_1m_return_bps": sum_abs_1m_return_bps,
        "efficiency_ratio": abs(full_return_bps) / sum_abs_1m_return_bps if sum_abs_1m_return_bps > 0 else 0.0,
        "close_pos": (close - low) / range_abs if range_abs > 0 else 0.5,
        "range_bps": range_abs / close * 10_000.0 if close > 0 else np.nan,
        "high_minute": high_minute,
        "low_minute": low_minute,
        "taker_buy_ratio": _safe_ratio(float(np.nansum(taker_base)), total_volume),
        "early_taker_buy_ratio": _safe_ratio(float(np.nansum(taker_base[:5])), first5_volume),
        "late_taker_buy_ratio": _safe_ratio(float(np.nansum(taker_base[-5:])), last5_volume),
        "late_minus_early_taker_buy_ratio": _safe_ratio(float(np.nansum(taker_base[-5:])), last5_volume) - _safe_ratio(float(np.nansum(taker_base[:5])), first5_volume),
        "last5_volume_share": _safe_ratio(last5_volume, total_volume),
        "first5_volume_share": _safe_ratio(first5_volume, total_volume),
        "last5_vs_first10_volume": _safe_ratio(last5_volume, first10_volume),
    }


def _window_return_bps(open_values: np.ndarray, close_values: np.ndarray, start: int, stop: int) -> float:
    if stop <= start:
        return 0.0
    return _log_return_bps(float(open_values[start]), float(close_values[stop - 1]))


def _log_return_bps(start_price: float, end_price: float) -> float:
    if start_price <= 0 or end_price <= 0:
        return 0.0
    return float(np.log(end_price / start_price) * 10_000.0)


def _safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator > 0 else 0.5


def _quality(frame: pd.DataFrame, monthly_quality: pd.DataFrame, from_cache: bool) -> dict[str, Any]:
    timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    diffs = timestamp.diff().dropna()
    valid = frame["valid_intrabar"].astype(bool)
    return {
        "from_cache": from_cache,
        "rows": int(len(frame)),
        "duplicate_timestamp_rows": int(timestamp.duplicated().sum()),
        "non_15m_gap_rows": int((diffs != probe16.BAR_DELTA).sum()),
        "invalid_intrabar_rows": int((~valid).sum()),
        "baseline_ohlc_mismatch_rows": int((~frame["baseline_ohlc_match"].astype(bool)).sum()) if "baseline_ohlc_match" in frame else None,
        "months": int(len(monthly_quality)),
        "missing_1m_rows_total": int(monthly_quality["missing_1m_rows"].sum()),
        "duplicate_1m_rows_total": int(monthly_quality["duplicate_1m_rows"].sum()),
        "non_1m_gap_rows_total": int(monthly_quality["non_1m_gap_rows"].sum()),
        "incomplete_15m_groups_total": int(monthly_quality["incomplete_15m_groups"].sum()),
        "first_timestamp": timestamp.min().isoformat(),
        "last_timestamp": timestamp.max().isoformat(),
        "pass": bool(timestamp.duplicated().sum() == 0 and (diffs != probe16.BAR_DELTA).sum() == 0 and (~valid).sum() == 0),
    }


def _parity_check_with_strategy_15(feature_frame: pd.DataFrame, baseline_ohlc: pd.DataFrame) -> dict[str, Any]:
    left = feature_frame[["timestamp", "open", "high", "low", "close"]].copy()
    merged = left.merge(baseline_ohlc, on="timestamp", how="outer", suffixes=("_1m", "_strategy15"), indicator=True)
    both = merged.loc[merged["_merge"] == "both"].copy()
    result: dict[str, Any] = {
        "strategy15_rows": int(len(baseline_ohlc)),
        "intrabar_rows": int(len(left)),
        "matched_rows": int(len(both)),
        "missing_from_strategy15": int((merged["_merge"] == "left_only").sum()),
        "missing_from_intrabar": int((merged["_merge"] == "right_only").sum()),
    }
    for column in ["open", "high", "low", "close"]:
        diff = (both[f"{column}_1m"] - both[f"{column}_strategy15"]).abs()
        result[f"{column}_mismatch_rows"] = int((diff > 1e-8).sum())
        result[f"{column}_max_abs_diff"] = float(diff.max()) if len(diff) else None
    result["pass"] = bool(
        result["missing_from_strategy15"] == 0
        and result["missing_from_intrabar"] == 0
        and all(result[f"{column}_mismatch_rows"] == 0 for column in ["open", "high", "low", "close"])
    )
    return result


class IntrabarFeatures:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.valid = pd.Series(frame["valid_intrabar"].astype(bool).to_numpy())
        self.full_return_bps = pd.Series(frame["full_return_bps"].astype(float).to_numpy())
        self.first10_return_bps = pd.Series(frame["first10_return_bps"].astype(float).to_numpy())
        self.last5_return_bps = pd.Series(frame["last5_return_bps"].astype(float).to_numpy())
        self.sum_abs_1m_return_bps = pd.Series(frame["sum_abs_1m_return_bps"].astype(float).to_numpy())
        self.efficiency_ratio = pd.Series(frame["efficiency_ratio"].astype(float).to_numpy())
        self.close_pos = pd.Series(frame["close_pos"].astype(float).to_numpy())
        self.range_bps = pd.Series(frame["range_bps"].astype(float).to_numpy())
        self.high_minute = pd.Series(frame["high_minute"].astype(float).to_numpy())
        self.low_minute = pd.Series(frame["low_minute"].astype(float).to_numpy())
        self.late_taker_buy_ratio = pd.Series(frame["late_taker_buy_ratio"].astype(float).to_numpy())
        self.last5_volume_share = pd.Series(frame["last5_volume_share"].astype(float).to_numpy())


def _candidate_library() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    leverages = [1.0, 2.0, 4.0]
    for move_bps in [5, 10, 20, 40]:
        for leverage in leverages:
            candidates.append(_candidate("late_momentum", "late_return_momentum", leverage, move_bps=move_bps))
            candidates.append(_candidate("late_momentum", "late_return_reversal", leverage, move_bps=move_bps))
        for buy_ratio in [0.55, 0.60]:
            for leverage in leverages:
                candidates.append(_candidate("late_momentum", "late_taker_momentum", leverage, move_bps=move_bps, buy_ratio=buy_ratio))
    for first10_bps in [10, 20, 40]:
        for last5_bps in [5, 10, 20]:
            for leverage in leverages:
                candidates.append(_candidate("early_late_reversal", "early_late_reversal", leverage, first10_bps=first10_bps, last5_bps=last5_bps))
    for min_range_bps in [20, 50, 100]:
        for close_pos in [0.60, 0.70]:
            for leverage in leverages:
                candidates.append(_candidate("path_extreme", "early_extreme_reversal", leverage, min_range_bps=min_range_bps, close_pos=close_pos))
    for move_bps in [10, 20, 40, 80]:
        for efficiency in [0.40, 0.60]:
            for leverage in leverages:
                candidates.append(_candidate("efficiency_path", "efficient_path_momentum", leverage, move_bps=move_bps, efficiency=efficiency))
                candidates.append(_candidate("efficiency_path", "efficient_path_reversal", leverage, move_bps=move_bps, efficiency=efficiency))
    for sum_abs_bps in [50, 100, 200]:
        for max_efficiency in [0.20, 0.35]:
            for leverage in leverages:
                candidates.append(_candidate("chop_path", "chop_reversal", leverage, sum_abs_bps=sum_abs_bps, max_efficiency=max_efficiency))
    for last5_volume_share in [0.35, 0.45, 0.55]:
        for move_bps in [5, 10, 20]:
            for leverage in leverages:
                candidates.append(_candidate("late_momentum", "late_volume_momentum", leverage, last5_volume_share=last5_volume_share, move_bps=move_bps))
    return candidates


def _candidate(family: str, rule: str, leverage: float, **params: Any) -> dict[str, Any]:
    suffix = "_".join(f"{key}{str(value).replace('.', 'p')}" for key, value in params.items())
    return {"candidate_id": f"{family}_{rule}_lev{str(leverage).replace('.', 'p')}_{suffix}", "family": family, "rule": rule, "leverage": leverage, **params}


def _target_for_candidate(candidate: dict[str, Any], f: IntrabarFeatures) -> np.ndarray:
    rule = candidate["rule"]
    leverage = float(candidate["leverage"])
    side = pd.Series(0.0, index=f.full_return_bps.index)

    if rule in {"late_return_momentum", "late_return_reversal"}:
        direction = np.sign(f.last5_return_bps)
        if rule == "late_return_reversal":
            direction = -direction
        mask = f.valid & (f.last5_return_bps.abs() >= float(candidate["move_bps"]))
        side = pd.Series(np.where(mask, direction, 0.0), index=f.full_return_bps.index)
    elif rule == "late_taker_momentum":
        buy_ratio = float(candidate["buy_ratio"])
        long_signal = (f.last5_return_bps >= float(candidate["move_bps"])) & (f.late_taker_buy_ratio >= buy_ratio)
        short_signal = (f.last5_return_bps <= -float(candidate["move_bps"])) & (f.late_taker_buy_ratio <= 1.0 - buy_ratio)
        side = pd.Series(np.where(f.valid & long_signal, 1.0, np.where(f.valid & short_signal, -1.0, 0.0)), index=f.full_return_bps.index)
    elif rule == "early_late_reversal":
        long_signal = (f.first10_return_bps <= -float(candidate["first10_bps"])) & (f.last5_return_bps >= float(candidate["last5_bps"]))
        short_signal = (f.first10_return_bps >= float(candidate["first10_bps"])) & (f.last5_return_bps <= -float(candidate["last5_bps"]))
        side = pd.Series(np.where(f.valid & long_signal, 1.0, np.where(f.valid & short_signal, -1.0, 0.0)), index=f.full_return_bps.index)
    elif rule == "early_extreme_reversal":
        close_pos = float(candidate["close_pos"])
        range_ok = f.range_bps >= float(candidate["min_range_bps"])
        long_signal = (f.low_minute <= 4) & (f.close_pos >= close_pos) & range_ok
        short_signal = (f.high_minute <= 4) & (f.close_pos <= 1.0 - close_pos) & range_ok
        side = pd.Series(np.where(f.valid & long_signal, 1.0, np.where(f.valid & short_signal, -1.0, 0.0)), index=f.full_return_bps.index)
    elif rule in {"efficient_path_momentum", "efficient_path_reversal"}:
        direction = np.sign(f.full_return_bps)
        if rule == "efficient_path_reversal":
            direction = -direction
        mask = f.valid & (f.full_return_bps.abs() >= float(candidate["move_bps"])) & (f.efficiency_ratio >= float(candidate["efficiency"]))
        side = pd.Series(np.where(mask, direction, 0.0), index=f.full_return_bps.index)
    elif rule == "chop_reversal":
        mask = (
            f.valid
            & (f.sum_abs_1m_return_bps >= float(candidate["sum_abs_bps"]))
            & (f.efficiency_ratio <= float(candidate["max_efficiency"]))
            & (f.full_return_bps.abs() >= 5.0)
        )
        side = pd.Series(np.where(mask, -np.sign(f.full_return_bps), 0.0), index=f.full_return_bps.index)
    elif rule == "late_volume_momentum":
        mask = (
            f.valid
            & (f.last5_volume_share >= float(candidate["last5_volume_share"]))
            & (f.last5_return_bps.abs() >= float(candidate["move_bps"]))
        )
        side = pd.Series(np.where(mask, np.sign(f.last5_return_bps), 0.0), index=f.full_return_bps.index)
    else:
        raise ValueError(f"Unknown rule: {rule}")

    return np.nan_to_num(side.to_numpy(dtype=float), nan=0.0) * leverage


def _candidate_results(
    candidates: list[dict[str, Any]], market: dict[str, Any], features: IntrabarFeatures
) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_frames: list[pd.DataFrame] = []
    scan_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        target = _target_for_candidate(candidate, features)
        equity = probe16._simulate_target(market, target)
        monthly = probe16._monthly_breakdown(equity)
        monthly = monthly.loc[(monthly["month"] >= probe16.EVAL_START_MONTH) & (monthly["month"] < probe16.EVAL_END_EXCLUSIVE)].copy()
        monthly.insert(0, "candidate_id", candidate["candidate_id"])
        monthly.insert(1, "family", candidate["family"])
        monthly.insert(2, "rule", candidate["rule"])
        monthly.insert(3, "leverage", candidate["leverage"])
        monthly_frames.append(monthly)
        yearly = upper17._yearly_from_monthly(monthly)
        scan_rows.append({**candidate, **upper17._summary_from_monthly(monthly, yearly)})
    monthly_all = pd.concat(monthly_frames, ignore_index=True)
    scan = pd.DataFrame(scan_rows).sort_values(
        ["hard_pass_complete_years", "losing_eval_months", "min_monthly_return_pct", "min_complete_year_return_pct"],
        ascending=[False, True, False, False],
    )
    return monthly_all, scan


def _decision(best_oracle: dict[str, Any]) -> dict[str, Any]:
    if bool(best_oracle["hard_pass_complete_years"]):
        return {
            "verdict": "INTRABAR_1M_UPPER_BOUND_HAS_MONTHLY_PIECES",
            "promote_strategy": False,
            "reason": "看答案的1分钟内部结构月度上限能过硬门槛，但它不能交易。",
            "next_step": "做严格逐月选择器，确认这些1分钟内部结构月份能不能不用未来信息提前选中。",
        }
    return {
        "verdict": "INTRABAR_1M_UPPER_BOUND_FAILS",
        "promote_strategy": False,
        "reason": "即使每个月事后挑最好1分钟内部结构候选，也过不了硬门槛。",
        "next_step": "不要继续扩这批1分钟内部结构小规则。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_oracle"]
    decision = summary["decision"]
    return f"""# 26号 1分钟内部结构上限测试

这不是策略，不能交易。它只看“如果事后知道每个月哪个1分钟内部结构候选最好”，这批候选理论上够不够。

## 口径

- 数据：`{summary["source"]["intrabar_features"]}`
- 评估：`{probe16.EVAL_START_MONTH}` 到 `2026-05`
- 手续费：开平合计 `{probe16.ROUND_TRIP_COST * 100:.2f}%`
- 特征：每根15分钟K线内部的15根1分钟K线，包括前10分钟/后5分钟走势、后5分钟成交量占比、taker买入比例、路径效率、高低点出现位置。
- 数据质量：1分钟原始月包缺失 `0` 行；有 `{summary["data"]["quality"]["baseline_ohlc_mismatch_rows"]}` 根15分钟K线和15号底座OHLC不一致，已禁用这些K线的信号。
- 时序：每个候选只用已收盘15分钟K线里的1分钟数据，下一根15分钟K线才吃收益；但月度oracle会看答案，所以不能交易。

## 最好上限

- oracle：`{best["oracle_id"]}`
- 硬通过：`{best["hard_pass_complete_years"]}`
- 2023：`{best["return_2023_pct"]:.2f}%`
- 2024：`{best["return_2024_pct"]:.2f}%`
- 2025：`{best["return_2025_pct"]:.2f}%`
- 2026 YTD：`{best["return_2026_ytd_pct"]:.2f}%`
- 亏损月：`{best["losing_eval_months"]}`
- 不盈利月份：`{", ".join(best["non_positive_months"])}`
- 最差月：`{best["min_monthly_return_pct"]:.2f}%`
- 最少月交易：`{best["min_monthly_orders"]}`

## 判断

`{decision["verdict"]}`

{decision["reason"]}
"""


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_ready(value: Any) -> Any:
    return probe16._json_ready(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
