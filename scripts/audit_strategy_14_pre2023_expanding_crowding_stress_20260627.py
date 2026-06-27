from __future__ import annotations

import hashlib
import io
import json
import math
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import audit_strategy_11_true_2024_walkforward_20260627 as audit11
import search_monthly_profit_lock_20260627 as lock_search


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_14_pre2023_expanding_crowding_stress_audit_20260627"
STRATEGY_ID = "strategy_14_pre2023_expanding_crowding_stress_audit_20260627"

SYMBOL = "BTCUSDT"
INTERVAL = "15m"
BAR_DELTA = pd.Timedelta(minutes=15)
PUBLIC_ARCHIVE_KIND = "Binance public USD-M futures monthly kline archive"
PUBLIC_ARCHIVE_BASE_URL = "https://data.binance.vision/data/futures/um/monthly/klines"
PUBLIC_YEARS = [2020, 2021, 2022, 2023, 2024]
EVENT_FRAME = ROOT / "artifacts" / "event_entry_fullscan" / "event_entry_best_signals.csv"

TRAIN_START_MONTH = "2020-01"
EVAL_START_MONTH = "2023-01"
EVAL_END_EXCLUSIVE = pd.Timestamp("2026-06-01T00:00:00Z")
COMPLETE_EVAL_YEARS = ["2023", "2024", "2025"]
PARTIAL_EVAL_YEAR = "2026"

FIXED_WINDOW = 64
FIXED_THRESHOLD_BPS = 100.0
CONFIRM_BARS = [1, 2, 4, 8, 12]
ROUND_TRIP_COSTS = [0.002, 0.003, 0.004, 0.006]
DELAY_BARS = [0, 1, 2, 4]
FUNDING_PER_8H = [0.0, 0.0001, 0.0003, 0.0005]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    public_ohlc, year_quality = _load_public_ohlc()
    event_ohlc = _load_event_tail()
    parity = _parity_check_2024(public_ohlc, event_ohlc)
    combined_ohlc = _combine_ohlc(public_ohlc, event_ohlc)
    features = _add_features(combined_ohlc)
    market = _market(features)

    candidates = _candidate_library(features, market)
    selections = _select_months(candidates)
    base = _simulate_walkforward(features, market, selections, cost_per_side=lock_search.COST_PER_SIDE)
    _assert_signal_timing(base)
    base_monthly = lock_search._monthly_breakdown(base)
    base_yearly = lock_search._yearly_breakdown(base_monthly)

    stress, stress_monthly = _run_stress(features, market, selections)
    selected_params = pd.DataFrame(selections)
    coverage = _month_coverage(combined_ohlc)

    paths = _write_outputs(
        public_ohlc,
        combined_ohlc,
        year_quality,
        parity,
        coverage,
        selected_params,
        base,
        base_monthly,
        base_yearly,
        stress,
        stress_monthly,
    )

    summary = {
        "status": "strategy_14_pre2023_expanding_crowding_stress_audit_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "gpt_pro_review_applied": True,
        "purpose": (
            "Audit the ret_state 64/100 monthly-lock family with 2020-2022 prehistory, "
            "nested expanding walk-forward selection, and fixed crowding/execution stress. "
            "This is not a new candidate strategy."
        ),
        "data": {
            "public_archive_kind": PUBLIC_ARCHIVE_KIND,
            "public_archive_base_url": PUBLIC_ARCHIVE_BASE_URL,
            "public_archive_years": PUBLIC_YEARS,
            "event_tail_source": _rel(EVENT_FRAME),
            "train_start_month": TRAIN_START_MONTH,
            "eval_start_month": EVAL_START_MONTH,
            "eval_end_exclusive": EVAL_END_EXCLUSIVE.isoformat(),
            "complete_eval_years_for_annual_threshold": COMPLETE_EVAL_YEARS,
            "partial_eval_year_recorded_not_annual_threshold": PARTIAL_EVAL_YEAR,
        },
        "base_signal": {"family": "ret_state", "window": FIXED_WINDOW, "threshold_bps": FIXED_THRESHOLD_BPS},
        "candidate_grid": {
            "confirm_bars": CONFIRM_BARS,
            "control_grid_rows": len(audit11._small_param_grid()),
            "total_candidates": len(candidates),
            "selection_sort": [
                "train_hard_ok",
                "fewest_train_losing_months",
                "highest_train_min_month",
                "highest_train_return",
                "highest_train_min_orders",
                "lowest_train_turnover",
                "lowest_leverage",
                "smallest_confirm_bars",
            ],
        },
        "cost_model": {"cost_per_side": lock_search.COST_PER_SIDE, "round_trip_open_close": lock_search.COST_PER_SIDE * 2},
        "data_quality": {
            "year_quality": lock_search._json_ready(year_quality.to_dict("records")),
            "parity_2024": lock_search._json_ready(parity),
            "month_coverage_rows": int(len(coverage)),
            "source_note": "2024 event_entry_fullscan close matches Binance USD-M futures public klines, not spot klines.",
        },
        "base_result": _result_summary(base, base_monthly, base_yearly),
        "stress_result": _stress_summary(stress),
        "selected_confirm_bars_counts": lock_search._json_ready(
            selected_params["confirm_bars"].value_counts().sort_index().to_dict()
        ),
        "decision": _decision(base_monthly, base_yearly, stress),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "combined_ohlc_sha256": _sha256(paths["combined_ohlc"]),
            "selected_params_sha256": _sha256(paths["selected_params"]),
            "base_equity_sha256": _sha256(paths["base_equity"]),
        },
        "files": {key: _rel(value) for key, value in paths.items()},
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _load_public_ohlc() -> tuple[pd.DataFrame, pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    quality_rows: list[dict[str, Any]] = []
    for year in PUBLIC_YEARS:
        official = _fetch_year_archive(year)
        filled = _fill_calendar_gaps(official, year)
        quality_rows.append(_year_quality(official, filled, year))
        frames.append(filled)
    return pd.concat(frames, ignore_index=True), pd.DataFrame(quality_rows)


def _fetch_year_archive(year: int) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for month in range(1, 13):
        url = f"{PUBLIC_ARCHIVE_BASE_URL}/{SYMBOL}/{INTERVAL}/{SYMBOL}-{INTERVAL}-{year}-{month:02d}.zip"
        payload = _download_url(url)
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            names = [name for name in zf.namelist() if name.endswith(".csv")]
            if not names:
                raise RuntimeError(f"No CSV found in {url}")
            with zf.open(names[0]) as handle:
                raw = pd.read_csv(handle, header=None)
        frames.append(_klines_to_ohlc(raw))
    return _clean_ohlc(pd.concat(frames, ignore_index=True), _year_start(year), _year_end(year))


def _download_url(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "strategy-14-research-audit/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except Exception as exc:  # pragma: no cover - network reliability path
            last_error = exc
            if attempt < 3:
                time.sleep(2.0 + attempt)
    raise RuntimeError(f"Failed to download {url}: {last_error!r}")


def _load_event_tail() -> pd.DataFrame:
    required = ["timestamp", "open", "high", "low", "close"]
    frame = pd.read_csv(EVENT_FRAME, usecols=lambda column: column in required, low_memory=False)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.loc[frame["timestamp"].notna()].copy()
    for column in ["open", "high", "low", "close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["open", "high", "low", "close"])
    frame = frame.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    frame = frame.loc[(frame["timestamp"] >= "2024-01-01") & (frame["timestamp"] < EVAL_END_EXCLUSIVE)]
    frame["calendar_filled"] = False
    frame["source"] = "event_entry_fullscan"
    return frame.reset_index(drop=True)


def _combine_ohlc(public_ohlc: pd.DataFrame, event_ohlc: pd.DataFrame) -> pd.DataFrame:
    public = public_ohlc.copy()
    public["source"] = "binance_public_um_futures_archive"
    tail = event_ohlc.loc[event_ohlc["timestamp"] >= "2025-01-01"].copy()
    out = pd.concat([public, tail], ignore_index=True)
    out = out.sort_values("timestamp").drop_duplicates("timestamp", keep="last").reset_index(drop=True)
    out = out.loc[(out["timestamp"] >= "2020-01-01") & (out["timestamp"] < EVAL_END_EXCLUSIVE)].reset_index(drop=True)
    return out


def _parity_check_2024(public_ohlc: pd.DataFrame, event_ohlc: pd.DataFrame) -> dict[str, Any]:
    public = public_ohlc.loc[public_ohlc["timestamp"].dt.strftime("%Y") == "2024", ["timestamp", "close"]]
    event = event_ohlc.loc[event_ohlc["timestamp"].dt.strftime("%Y") == "2024", ["timestamp", "close"]]
    merged = public.merge(event, on="timestamp", how="outer", suffixes=("_public", "_event"), indicator=True)
    both = merged.loc[merged["_merge"] == "both"].copy()
    both["abs_close_diff"] = (both["close_public"] - both["close_event"]).abs()
    mismatch = both.loc[both["abs_close_diff"] > 1e-8]
    parity_path = OUT_DIR / "event_2024_close_mismatches.csv"
    mismatch.head(1000).to_csv(parity_path, index=False)
    return {
        "public_2024_rows": int(len(public)),
        "event_2024_rows": int(len(event)),
        "matched_rows": int(len(both)),
        "missing_from_event": int((merged["_merge"] == "left_only").sum()),
        "missing_from_public": int((merged["_merge"] == "right_only").sum()),
        "close_mismatch_rows": int(len(mismatch)),
        "max_abs_close_diff": float(both["abs_close_diff"].max()) if len(both) else None,
        "mismatch_file": _rel(parity_path),
    }


def _klines_to_ohlc(raw: pd.DataFrame) -> pd.DataFrame:
    names = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "trades",
        "taker_base",
        "taker_quote",
        "ignore",
    ]
    raw = raw.iloc[:, : len(names)].copy()
    raw.columns = names[: len(raw.columns)]
    if len(raw) and str(raw.iloc[0]["open_time"]).lower() == "open_time":
        raw = raw.iloc[1:].reset_index(drop=True)
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(pd.to_numeric(raw["open_time"], errors="coerce"), unit="ms", utc=True),
            "open": pd.to_numeric(raw["open"], errors="coerce"),
            "high": pd.to_numeric(raw["high"], errors="coerce"),
            "low": pd.to_numeric(raw["low"], errors="coerce"),
            "close": pd.to_numeric(raw["close"], errors="coerce"),
        }
    ).dropna()


def _clean_ohlc(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    out = frame.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    out = out.loc[out["timestamp"].notna()].copy()
    out = out.loc[(out["timestamp"] >= start) & (out["timestamp"] < end)].copy()
    out = out.drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
    return out


def _fill_calendar_gaps(frame: pd.DataFrame, year: int) -> pd.DataFrame:
    full_index = pd.date_range(_year_start(year), _year_end(year) - BAR_DELTA, freq=BAR_DELTA)
    out = frame.set_index("timestamp").reindex(full_index)
    filled = out["close"].isna()
    previous_close = out["close"].ffill()
    for column in ["open", "high", "low", "close"]:
        out[column] = out[column].fillna(previous_close)
    out["calendar_filled"] = filled.to_numpy(bool)
    out = out.reset_index().rename(columns={"index": "timestamp"})
    if out[["open", "high", "low", "close"]].isna().any().any():
        raise RuntimeError(f"Calendar fill left missing OHLC values for {year}.")
    return out


def _year_quality(official: pd.DataFrame, filled: pd.DataFrame, year: int) -> dict[str, Any]:
    expected = int((_year_end(year) - _year_start(year)) / BAR_DELTA)
    timestamp = pd.to_datetime(filled["timestamp"], utc=True)
    official_timestamp = pd.to_datetime(official["timestamp"], utc=True)
    gaps = timestamp.diff().dropna()
    official_gaps = official_timestamp.diff().dropna()
    return {
        "year": year,
        "expected_rows": expected,
        "official_rows": int(len(official)),
        "filled_rows": int(len(filled)),
        "calendar_fill_rows": int(filled["calendar_filled"].sum()),
        "duplicate_rows_after_fill": int(timestamp.duplicated().sum()),
        "non_15m_gap_rows_after_fill": int((gaps != BAR_DELTA).sum()),
        "official_non_15m_gap_rows": int((official_gaps != BAR_DELTA).sum()),
        "first_timestamp": timestamp.min().isoformat(),
        "last_timestamp": timestamp.max().isoformat(),
        "ready": bool(len(filled) == expected and timestamp.duplicated().sum() == 0 and (gaps != BAR_DELTA).sum() == 0),
    }


def _add_features(ohlc: pd.DataFrame) -> pd.DataFrame:
    out = ohlc.copy()
    close = out["close"].astype(float)
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    prev_close = close.shift(1)
    true_range = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = true_range.ewm(alpha=1.0 / 30.0, adjust=False, min_periods=30).mean()
    out["natr_30"] = atr / close * 100.0
    out[f"ret_{FIXED_WINDOW}_bps"] = close.pct_change(FIXED_WINDOW) * 10_000.0
    return out.replace([np.inf, -np.inf], np.nan)


def _market(frame: pd.DataFrame) -> dict[str, Any]:
    timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    raw_return = np.log(frame["close"].astype(float)).diff().fillna(0.0).to_numpy(float)
    month = timestamp.dt.strftime("%Y-%m").to_numpy()
    year = timestamp.dt.year.astype(str).to_numpy()
    month_starts = np.r_[0, np.flatnonzero(month[1:] != month[:-1]) + 1]
    year_starts = np.r_[0, np.flatnonzero(year[1:] != year[:-1]) + 1]
    return {
        "timestamp": timestamp.reset_index(drop=True),
        "close": frame["close"].astype(float).to_numpy(float),
        "raw_return": raw_return,
        "month": month,
        "year": year,
        "month_starts": month_starts,
        "month_labels": month[month_starts],
        "year_starts": year_starts,
        "year_labels": year[year_starts],
        "natr_30": frame["natr_30"].fillna(0.0).to_numpy(float),
    }


def _candidate_library(features: pd.DataFrame, market: dict[str, Any]) -> list[dict[str, Any]]:
    raw_side = _ret_state_side(features)
    candidates: list[dict[str, Any]] = []
    candidate_id = 0
    for confirm_bars in CONFIRM_BARS:
        side = _confirmed_side(raw_side, confirm_bars)
        for params in audit11._small_param_grid():
            equity = _simulate_static_candidate(side, market, params, cost_per_side=lock_search.COST_PER_SIDE)
            monthly = lock_search._monthly_breakdown(equity)
            candidates.append(
                {
                    "candidate_id": candidate_id,
                    "confirm_bars": confirm_bars,
                    "side": side,
                    "params": params,
                    "monthly": monthly,
                }
            )
            candidate_id += 1
    return candidates


def _select_months(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    eval_months = sorted(
        {
            str(month)
            for candidate in candidates[:1]
            for month in candidate["monthly"]["month"].tolist()
            if str(month) >= EVAL_START_MONTH and str(month) < EVAL_END_EXCLUSIVE.strftime("%Y-%m")
        }
    )
    selections = []
    for eval_month in eval_months:
        best_key = None
        best_row = None
        scored_candidates = []
        for candidate in candidates:
            score = _score_before_month(candidate["monthly"], eval_month)
            if score["months"] < 12:
                continue
            scored_candidates.append((candidate, score))
        train_hard_ok_count = sum(1 for _, score in scored_candidates if score["hard_ok"])
        for candidate, score in scored_candidates:
            params = candidate["params"]
            key = (
                score["hard_ok"],
                -score["losing_months"],
                score["min_month_return_pct"],
                score["return_pct"],
                score["min_orders"],
                -score["turnover"],
                -float(params["leverage"]),
                -int(candidate["confirm_bars"]),
            )
            if best_key is None or key > best_key:
                best_key = key
                best_row = {
                    "eval_month": eval_month,
                    "train_start_month": TRAIN_START_MONTH,
                    "train_end_month": score["last_month"],
                    "candidate_id": candidate["candidate_id"],
                    "confirm_bars": candidate["confirm_bars"],
                    **params,
                    **{f"train_{key_name}": value for key_name, value in score.items() if key_name != "last_month"},
                    "train_hard_ok_candidate_count": train_hard_ok_count,
                }
        if best_row is None:
            raise RuntimeError(f"No candidate selected for {eval_month}")
        if not (best_row["train_end_month"] < best_row["eval_month"]):
            raise AssertionError(best_row)
        selections.append(best_row)
    return selections


def _score_before_month(monthly: pd.DataFrame, eval_month: str) -> dict[str, Any]:
    train = monthly.loc[(monthly["month"] >= TRAIN_START_MONTH) & (monthly["month"] < eval_month)]
    if train.empty:
        return {
            "months": 0,
            "last_month": None,
            "return_pct": -999.0,
            "losing_months": 999,
            "min_month_return_pct": -999.0,
            "min_orders": 0,
            "turnover": 999999.0,
            "hard_ok": False,
        }
    log_return = float(train["log_return"].sum())
    score = {
        "months": int(len(train)),
        "last_month": str(train["month"].iloc[-1]),
        "return_pct": float((np.exp(log_return) - 1.0) * 100.0),
        "losing_months": int((train["return_pct"] <= 0).sum()),
        "min_month_return_pct": float(train["return_pct"].min()),
        "min_orders": int(train["orders"].min()),
        "turnover": float(train["turnover"].sum()),
    }
    score["hard_ok"] = bool(
        score["return_pct"] > lock_search.REQUIRED_RETURN_PCT
        and score["losing_months"] == 0
        and score["min_orders"] >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS
    )
    return score


def _simulate_static_candidate(
    side: np.ndarray,
    market: dict[str, Any],
    params: dict[str, Any],
    cost_per_side: float,
) -> pd.DataFrame:
    selections = {
        str(month): {"confirm_bars": 1, **params}
        for month in market["month_labels"]
        if str(month) >= TRAIN_START_MONTH and str(month) < EVAL_END_EXCLUSIVE.strftime("%Y-%m")
    }
    return _simulate_walkforward_from_side(side, market, selections, cost_per_side=cost_per_side)


def _simulate_walkforward(
    features: pd.DataFrame,
    market: dict[str, Any],
    selections: list[dict[str, Any]],
    cost_per_side: float,
    delay_bars: int = 0,
    funding_per_8h: float = 0.0,
    dynamic_slip: bool = False,
) -> pd.DataFrame:
    raw_side = _ret_state_side(features)
    side_cache = {
        confirm_bars: _delay_side(_confirmed_side(raw_side, confirm_bars), delay_bars)
        for confirm_bars in sorted({int(row["confirm_bars"]) for row in selections})
    }
    selection_map = {row["eval_month"]: row for row in selections}
    return _simulate_walkforward_from_side_map(
        side_cache,
        market,
        selection_map,
        cost_per_side=cost_per_side,
        funding_per_8h=funding_per_8h,
        dynamic_slip=dynamic_slip,
    )


def _simulate_walkforward_from_side(
    side: np.ndarray,
    market: dict[str, Any],
    selections: dict[str, dict[str, Any]],
    cost_per_side: float,
) -> pd.DataFrame:
    return _simulate_walkforward_from_side_map({1: side}, market, selections, cost_per_side=cost_per_side)


def _simulate_walkforward_from_side_map(
    side_map: dict[int, np.ndarray],
    market: dict[str, Any],
    selections: dict[str, dict[str, Any]],
    cost_per_side: float,
    funding_per_8h: float = 0.0,
    dynamic_slip: bool = False,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    previous_position = 0.0
    previous_side = 0
    funding_per_bar = funding_per_8h / 32.0
    for start, end in zip(market["month_starts"], np.r_[market["month_starts"][1:], len(market["close"])]):
        month = str(market["month"][start])
        params = selections.get(month)
        if params is None:
            continue
        side = side_map[int(params.get("confirm_bars", 1))]
        month_log = 0.0
        month_orders = 0
        halted = False
        quota_mode = False
        for index in range(start, end):
            current_side = 0 if halted else int(side[index])
            effective_leverage = (
                float(params["quota_leverage"])
                if quota_mode
                and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS
                and params["quota_leverage"] is not None
                else float(params["leverage"])
            )
            current_position = current_side * effective_leverage
            turnover = abs(current_position - previous_position)
            orders = abs(current_side - previous_side)
            extra_cost = _dynamic_extra_cost(market, index) if dynamic_slip else 0.0
            lr = (
                previous_position * market["raw_return"][index]
                - turnover * (cost_per_side + extra_cost)
                - abs(previous_position) * funding_per_bar
            )
            records.append(
                {
                    "timestamp": market["timestamp"].iloc[index],
                    "close": market["close"][index],
                    "position": current_position,
                    "active_position": previous_position,
                    "turnover": turnover,
                    "order_count": orders,
                    "strategy_log_return": lr,
                    "selected_confirm_bars": int(params.get("confirm_bars", 1)),
                    "selected_leverage": float(params["leverage"]),
                    "selected_lock_log": float(params["lock_log"]),
                    "selected_quota_arm_log": params["quota_arm_log"],
                    "selected_quota_leverage": params["quota_leverage"],
                }
            )
            month_log += lr
            month_orders += orders
            previous_position = current_position
            previous_side = current_side
            if (
                params["quota_arm_log"] is not None
                and params["quota_leverage"] is not None
                and not quota_mode
                and month_orders < lock_search.REQUIRED_MIN_MONTHLY_ORDERS
                and month_log >= float(params["quota_arm_log"])
            ):
                quota_mode = True
            if not halted and month_orders >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS and month_log >= float(params["lock_log"]):
                halted = True
    equity = pd.DataFrame(records)
    equity["equity"] = np.exp(equity["strategy_log_return"].cumsum())
    equity["drawdown"] = equity["equity"] / equity["equity"].cummax() - 1.0
    return equity


def _run_stress(features: pd.DataFrame, market: dict[str, Any], selections: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    scenario_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    scenarios = _stress_scenarios()
    for scenario in scenarios:
        equity = _simulate_walkforward(features, market, selections, **scenario["kwargs"])
        _assert_signal_timing(equity)
        monthly = lock_search._monthly_breakdown(equity)
        yearly = lock_search._yearly_breakdown(monthly)
        row = {
            "scenario_id": scenario["scenario_id"],
            "description": scenario["description"],
            **_result_summary(equity, monthly, yearly),
        }
        scenario_rows.append(row)
        for item in monthly.to_dict("records"):
            item["scenario_id"] = scenario["scenario_id"]
            monthly_rows.append(item)
    return pd.DataFrame(scenario_rows), pd.DataFrame(monthly_rows)


def _stress_scenarios() -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    for round_trip in ROUND_TRIP_COSTS:
        scenarios.append(
            {
                "scenario_id": f"round_trip_cost_{round_trip * 100:.1f}pct".replace(".", "p"),
                "description": f"round-trip cost {round_trip * 100:.1f}%",
                "kwargs": {"cost_per_side": round_trip / 2.0},
            }
        )
    for delay in DELAY_BARS[1:]:
        scenarios.append(
            {
                "scenario_id": f"delay_{delay}_bars",
                "description": f"extra signal delay {delay} closed 15m bars",
                "kwargs": {"cost_per_side": lock_search.COST_PER_SIDE, "delay_bars": delay},
            }
        )
    for funding in FUNDING_PER_8H[1:]:
        scenarios.append(
            {
                "scenario_id": f"funding_{funding * 10000:.0f}bp_8h",
                "description": f"funding drag {funding * 10000:.0f}bp per 8h on notional exposure",
                "kwargs": {"cost_per_side": lock_search.COST_PER_SIDE, "funding_per_8h": funding},
            }
        )
    scenarios.append(
        {
            "scenario_id": "dynamic_vol_slip_min1bp_k10pct",
            "description": "extra per-side slippage max(1bp, 10% of current NATR_30)",
            "kwargs": {"cost_per_side": lock_search.COST_PER_SIDE, "dynamic_slip": True},
        }
    )
    return scenarios


def _result_summary(equity: pd.DataFrame, monthly: pd.DataFrame, yearly: pd.DataFrame) -> dict[str, Any]:
    eval_monthly = monthly.loc[
        (monthly["month"] >= EVAL_START_MONTH) & (monthly["month"] < EVAL_END_EXCLUSIVE.strftime("%Y-%m"))
    ]
    year_map = dict(zip(yearly["year"], yearly["compounded_return_pct"]))
    complete_year_returns = [float(year_map.get(year, -999.0)) for year in COMPLETE_EVAL_YEARS]
    complete_hard = bool(
        all(value > lock_search.REQUIRED_RETURN_PCT for value in complete_year_returns)
        and not eval_monthly.empty
        and float(eval_monthly["return_pct"].min()) > 0.0
        and int(eval_monthly["orders"].min()) >= lock_search.REQUIRED_MIN_MONTHLY_ORDERS
    )
    returns = equity["strategy_log_return"]
    active_returns = returns[equity["active_position"].abs() > 0]
    losses = float(active_returns[active_returns < 0].sum())
    gains = float(active_returns[active_returns > 0].sum())
    std = float(returns.std())
    return {
        "hard_pass_complete_years": complete_hard,
        "return_2023_pct": float(year_map.get("2023", -999.0)),
        "return_2024_pct": float(year_map.get("2024", -999.0)),
        "return_2025_pct": float(year_map.get("2025", -999.0)),
        "return_2026_ytd_pct": float(year_map.get("2026", -999.0)),
        "min_complete_year_return_pct": float(min(complete_year_returns)),
        "losing_eval_months": int((eval_monthly["return_pct"] <= 0).sum()) if not eval_monthly.empty else 999,
        "min_monthly_return_pct": float(eval_monthly["return_pct"].min()) if not eval_monthly.empty else -999.0,
        "min_monthly_orders": int(eval_monthly["orders"].min()) if not eval_monthly.empty else 0,
        "max_drawdown_pct": float(equity["drawdown"].min() * 100.0),
        "orders": int(equity["order_count"].sum()),
        "turnover": float(equity["turnover"].sum()),
        "exposure_pct": float((equity["active_position"].abs() > 0).mean() * 100.0),
        "annualized_sharpe": float(0.0 if std == 0 else returns.mean() / std * math.sqrt(365 * 24 * 4)),
        "win_rate_pct": float(0.0 if active_returns.empty else (active_returns > 0).mean() * 100.0),
        "profit_factor": float("inf") if losses == 0 and gains > 0 else float(gains / abs(losses) if losses != 0 else 0.0),
    }


def _stress_summary(stress: pd.DataFrame) -> dict[str, Any]:
    if stress.empty:
        return {"scenario_count": 0, "hard_pass_scenarios": 0}
    failed = stress.loc[~stress["hard_pass_complete_years"]]
    return {
        "scenario_count": int(len(stress)),
        "hard_pass_scenarios": int(stress["hard_pass_complete_years"].sum()),
        "failed_scenarios": int(len(failed)),
        "worst_min_monthly_return_pct": float(stress["min_monthly_return_pct"].min()),
        "worst_min_complete_year_return_pct": float(stress["min_complete_year_return_pct"].min()),
        "worst_max_drawdown_pct": float(stress["max_drawdown_pct"].min()),
        "failed_scenario_ids": failed["scenario_id"].astype(str).tolist(),
    }


def _decision(base_monthly: pd.DataFrame, base_yearly: pd.DataFrame, stress: pd.DataFrame) -> dict[str, Any]:
    dummy_equity = pd.DataFrame(
        {
            "strategy_log_return": [0.0],
            "active_position": [0.0],
            "drawdown": [0.0],
            "turnover": [0.0],
            "order_count": [0],
        }
    )
    base_summary = _result_summary(dummy_equity, base_monthly, base_yearly)
    if not base_summary["hard_pass_complete_years"]:
        verdict = "STOP_FAMILY"
        reason = "Base nested walk-forward still has a losing month, too few monthly orders, or a complete year below +100%."
    elif int(stress["hard_pass_complete_years"].sum()) < max(1, math.ceil(len(stress) * 0.6)):
        verdict = "DIAGNOSTIC_ONLY"
        reason = "Base passes, but fixed cost/delay/funding/slippage stress is too fragile."
    else:
        verdict = "PASS_CONTINUE_RESEARCH"
        reason = "Base and most stress scenarios pass. This still is research only, not live approval."
    return {
        "verdict": verdict,
        "promote_strategy": False,
        "reason": reason,
        "next_step": "If verdict is STOP_FAMILY or DIAGNOSTIC_ONLY, do not add more hand-tuned 2024-12 patch rules.",
    }


def _ret_state_side(features: pd.DataFrame) -> np.ndarray:
    ret = features[f"ret_{FIXED_WINDOW}_bps"]
    side = np.zeros(len(features), dtype=np.int8)
    side[ret.ge(FIXED_THRESHOLD_BPS).fillna(False).to_numpy(bool)] = 1
    side[ret.le(-FIXED_THRESHOLD_BPS).fillna(False).to_numpy(bool)] = -1
    return side


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


def _delay_side(side: np.ndarray, delay_bars: int) -> np.ndarray:
    if delay_bars <= 0:
        return side.copy()
    out = np.zeros(len(side), dtype=np.int8)
    out[delay_bars:] = side[:-delay_bars]
    return out


def _dynamic_extra_cost(market: dict[str, Any], index: int) -> float:
    natr_decimal = max(0.0, float(market["natr_30"][index]) / 100.0)
    return max(0.0001, 0.10 * natr_decimal)


def _month_coverage(ohlc: pd.DataFrame) -> pd.DataFrame:
    out = ohlc.copy()
    out["month"] = pd.to_datetime(out["timestamp"], utc=True).dt.strftime("%Y-%m")
    rows = []
    for month, group in out.groupby("month", sort=True):
        rows.append(
            {
                "month": month,
                "rows": int(len(group)),
                "first_timestamp": pd.to_datetime(group["timestamp"], utc=True).min().isoformat(),
                "last_timestamp": pd.to_datetime(group["timestamp"], utc=True).max().isoformat(),
                "calendar_fill_rows": int(group.get("calendar_filled", pd.Series(dtype=bool)).sum()),
                "source": ",".join(sorted(group["source"].astype(str).unique())) if "source" in group else "unknown",
            }
        )
    return pd.DataFrame(rows)


def _write_outputs(
    public_ohlc: pd.DataFrame,
    combined_ohlc: pd.DataFrame,
    year_quality: pd.DataFrame,
    parity: dict[str, Any],
    coverage: pd.DataFrame,
    selected_params: pd.DataFrame,
    base: pd.DataFrame,
    base_monthly: pd.DataFrame,
    base_yearly: pd.DataFrame,
    stress: pd.DataFrame,
    stress_monthly: pd.DataFrame,
) -> dict[str, Path]:
    paths = {
        "public_ohlc_2020_2024": OUT_DIR / "btc_15m_2020_2024_public_ohlc.csv",
        "combined_ohlc": OUT_DIR / "btc_15m_2020_2026_05_combined_ohlc.csv",
        "year_quality": OUT_DIR / "public_year_quality.csv",
        "month_coverage": OUT_DIR / "month_coverage.csv",
        "selected_params": OUT_DIR / "selected_params_by_month.csv",
        "base_equity": OUT_DIR / "base_nested_equity.csv",
        "base_monthly": OUT_DIR / "base_nested_monthly.csv",
        "base_yearly": OUT_DIR / "base_nested_yearly.csv",
        "stress": OUT_DIR / "stress_scenarios.csv",
        "stress_monthly": OUT_DIR / "stress_monthly.csv",
        "event_2024_close_mismatches": OUT_DIR / "event_2024_close_mismatches.csv",
        "summary": OUT_DIR / "summary.json",
        "report": OUT_DIR / "report.md",
    }
    public_ohlc.to_csv(paths["public_ohlc_2020_2024"], index=False)
    combined_ohlc.to_csv(paths["combined_ohlc"], index=False)
    year_quality.to_csv(paths["year_quality"], index=False)
    coverage.to_csv(paths["month_coverage"], index=False)
    selected_params.to_csv(paths["selected_params"], index=False)
    base.to_csv(paths["base_equity"], index=False)
    base_monthly.to_csv(paths["base_monthly"], index=False)
    base_yearly.to_csv(paths["base_yearly"], index=False)
    stress.to_csv(paths["stress"], index=False)
    stress_monthly.to_csv(paths["stress_monthly"], index=False)
    if not paths["event_2024_close_mismatches"].exists():
        pd.DataFrame().to_csv(paths["event_2024_close_mismatches"], index=False)
    return paths


def _render_report(summary: dict[str, Any]) -> str:
    base = summary["base_result"]
    stress = summary["stress_result"]
    decision = summary["decision"]
    lines = [
        "# 14号 pre-2023 扩展滚动与拥挤压力审计",
        "",
        "这不是新策略，也不是固化版。它只回答一个问题：这个策略族在更早历史、严格按月只看过去、以及更差交易环境下，还值不值得继续研究。",
        "",
        "## GPT Pro 复核后的纪律",
        "",
        "- 不升级 13号，也不冻结事后看 2024 得到的 `confirm_bars=4`。",
        "- 不为 2024-12 单独打补丁。",
        "- 14号只做审计，不做新候选。",
        "",
        "## 基础滚动结果",
        "",
        "| 年份 | 收益 |",
        "| --- | ---: |",
        f"| 2023 | {base['return_2023_pct']:.2f}% |",
        f"| 2024 | {base['return_2024_pct']:.2f}% |",
        f"| 2025 | {base['return_2025_pct']:.2f}% |",
        f"| 2026 YTD | {base['return_2026_ytd_pct']:.2f}% |",
        "",
        f"- 完整年份硬通过：`{base['hard_pass_complete_years']}`",
        f"- 评估期亏损月：`{base['losing_eval_months']}`",
        f"- 最差月：`{base['min_monthly_return_pct']:.2f}%`",
        f"- 最少月交易：`{base['min_monthly_orders']}`",
        f"- 最大回撤：`{base['max_drawdown_pct']:.2f}%`",
        "",
        "## 压力测试",
        "",
        f"- 压力场景数：`{stress['scenario_count']}`",
        f"- 仍硬通过场景：`{stress['hard_pass_scenarios']}`",
        f"- 失败场景：`{stress['failed_scenarios']}`",
        f"- 压力下最差月：`{stress['worst_min_monthly_return_pct']:.2f}%`",
        "",
        "## 结论",
        "",
        f"- verdict: `{decision['verdict']}`",
        f"- promote_strategy: `{decision['promote_strategy']}`",
        f"- 原因：{decision['reason']}",
        "",
        "通俗说：如果这里判成 `STOP_FAMILY` 或 `DIAGNOSTIC_ONLY`，就不要继续往这个家族上堆参数。应该承认它容易被成本、延迟和已知失败月打坏。",
    ]
    return "\n".join(lines) + "\n"


def _assert_signal_timing(equity: pd.DataFrame) -> None:
    active = equity["active_position"].to_numpy(float)
    position = equity["position"].to_numpy(float)
    assert active[0] == 0.0
    assert np.allclose(active[1:], position[:-1])


def _year_start(year: int) -> pd.Timestamp:
    return pd.Timestamp(f"{year}-01-01T00:00:00Z")


def _year_end(year: int) -> pd.Timestamp:
    return pd.Timestamp(f"{year + 1}-01-01T00:00:00Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
