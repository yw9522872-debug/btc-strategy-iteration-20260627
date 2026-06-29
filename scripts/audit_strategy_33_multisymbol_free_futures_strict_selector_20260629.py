from __future__ import annotations

import hashlib
import io
import json
import sys
import time
import urllib.error
import zipfile
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
import audit_strategy_31_multisymbol_free_futures_upper_bound_20260628 as s31


STRATEGY_ID = "strategy_33_multisymbol_free_futures_strict_selector_20260629"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
PANEL_PATH = OUT_DIR / "multisymbol_close_panel_15m_2020_2026_05.csv.gz"
COVERAGE_PATH = OUT_DIR / "symbol_month_coverage.csv"

MAIN_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT"]
OBSERVATION_ONLY_SYMBOLS = ["HYPEUSDT"]
START_MONTH = pd.Period("2020-01", freq="M")
END_MONTH = pd.Period("2026-05", freq="M")
MONTHS = list(pd.period_range(START_MONTH, END_MONTH, freq="M"))
BAR_DELTA = pd.Timedelta(minutes=15)
URL_TEMPLATE = "https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/15m/{symbol}-15m-{yyyy}-{mm}.zip"

SELECTORS = [
    ("all_multisymbol", None, "hard_guard"),
    ("single_symbol_only", "single_symbol", "hard_guard"),
    ("cross_section_only", "cross_section", "hard_guard"),
    ("return_first_all", None, "return_first"),
    ("min10_return_first_all", None, "min10_return_first"),
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel, data_quality = _load_or_fetch_panel()
    market = _market(panel)
    candidates = _candidate_library()
    candidate_monthly, candidate_scan = _candidate_results(candidates, market)
    oracle_summary, oracle_monthly, oracle_yearly = _oracle_results(candidate_monthly)
    selector_summary, selector_monthly, selector_yearly, selected_params = _selector_results(candidate_monthly, candidates, market)

    candidate_monthly.to_csv(OUT_DIR / "candidate_monthly.csv", index=False)
    candidate_scan.to_csv(OUT_DIR / "candidate_scan.csv", index=False)
    oracle_summary.to_csv(OUT_DIR / "oracle_summary.csv", index=False)
    oracle_monthly.to_csv(OUT_DIR / "oracle_monthly.csv", index=False)
    oracle_yearly.to_csv(OUT_DIR / "oracle_yearly.csv", index=False)
    selector_summary.to_csv(OUT_DIR / "selector_summary.csv", index=False)
    selector_monthly.to_csv(OUT_DIR / "selector_monthly.csv", index=False)
    selector_yearly.to_csv(OUT_DIR / "selector_yearly.csv", index=False)
    selected_params.to_csv(OUT_DIR / "selected_params.csv", index=False)

    best_selector = selector_summary.iloc[0].to_dict()
    best_oracle_order10 = oracle_summary.loc[oracle_summary["requires_monthly_orders_ge_10_at_selection"]].iloc[0].to_dict()
    summary = {
        "status": "strategy_33_multisymbol_free_futures_strict_selector_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Full-history multi-symbol Binance USD-M futures 15m strict monthly selector after Strategy 31 sample upper-bound signal.",
        "data": data_quality,
        "symbols": {
            "main_symbols": MAIN_SYMBOLS,
            "observation_only_symbols": OBSERVATION_ONLY_SYMBOLS,
            "hype_note": "HYPEUSDT history is too short, so Strategy 33 does not use it in candidate selection.",
        },
        "evaluation": {
            "train_start_month": probe16.TRAIN_START_MONTH,
            "eval_start_month": probe16.EVAL_START_MONTH,
            "eval_end_exclusive": probe16.EVAL_END_EXCLUSIVE,
            "available_data_end_month": str(END_MONTH),
            "complete_eval_years_for_reference": probe16.COMPLETE_EVAL_YEARS,
            "main_hard_target": "2025 > 100%, 2026 YTD > 100%, every eval month positive, every eval month orders >= 10.",
        },
        "cost_model": {
            "cost_per_side": probe16.COST_PER_SIDE,
            "round_trip_open_close": probe16.ROUND_TRIP_COST,
            "multi_asset_turnover_note": "Cost is charged on the sum of absolute target weight changes across symbols.",
        },
        "timing": {
            "signals_use_closed_15m_bar_t": True,
            "position_participates_from_bar_t_plus_1": True,
            "strict_selector_uses_only_months_before_eval_month": True,
            "monthly_oracle_is_leaky_and_not_tradeable": True,
        },
        "candidate_grid": _candidate_grid_summary(candidates),
        "static_hard_pass_original_target_count": int(candidate_scan["hard_pass_original_2025_2026_ytd"].sum()),
        "static_hard_pass_complete_years_count": int(candidate_scan["hard_pass_complete_years"].sum()),
        "best_static_candidate": _json_ready(candidate_scan.iloc[0].to_dict()),
        "oracle_summary": _json_ready(oracle_summary.to_dict("records")),
        "best_order10_oracle": _json_ready(best_oracle_order10),
        "selector_summary": _json_ready(selector_summary.to_dict("records")),
        "best_selector": _json_ready(best_selector),
        "decision": _decision(best_selector, best_oracle_order10),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "panel_sha256": _sha256(PANEL_PATH),
            "coverage_sha256": _sha256(COVERAGE_PATH),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "panel": _rel(PANEL_PATH),
            "coverage": _rel(COVERAGE_PATH),
            "candidate_scan": _rel(OUT_DIR / "candidate_scan.csv"),
            "candidate_monthly": _rel(OUT_DIR / "candidate_monthly.csv"),
            "oracle_summary": _rel(OUT_DIR / "oracle_summary.csv"),
            "oracle_monthly": _rel(OUT_DIR / "oracle_monthly.csv"),
            "oracle_yearly": _rel(OUT_DIR / "oracle_yearly.csv"),
            "selector_summary": _rel(OUT_DIR / "selector_summary.csv"),
            "selector_monthly": _rel(OUT_DIR / "selector_monthly.csv"),
            "selector_yearly": _rel(OUT_DIR / "selector_yearly.csv"),
            "selected_params": _rel(OUT_DIR / "selected_params.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_or_fetch_panel() -> tuple[pd.DataFrame, dict[str, Any]]:
    if PANEL_PATH.exists() and COVERAGE_PATH.exists():
        panel = pd.read_csv(PANEL_PATH)
        panel["timestamp"] = pd.to_datetime(panel["timestamp"], utc=True)
        coverage = pd.read_csv(COVERAGE_PATH)
        data_quality = _data_quality(panel, coverage, from_cache=True)
        if data_quality["pass"]:
            return panel, data_quality
        print("cached panel failed quality; rebuilding", flush=True)

    full_index = pd.date_range(
        START_MONTH.start_time.tz_localize("UTC"),
        END_MONTH.end_time.tz_localize("UTC").floor("15min"),
        freq=BAR_DELTA,
    )
    panel = pd.DataFrame({"timestamp": full_index})
    coverage_rows: list[dict[str, Any]] = []
    for symbol in MAIN_SYMBOLS:
        print(f"downloading {symbol}", flush=True)
        frames: list[pd.DataFrame] = []
        for month in MONTHS:
            url = URL_TEMPLATE.format(symbol=symbol, yyyy=month.year, mm=f"{month.month:02d}")
            row = {"symbol": symbol, "month": str(month), "url": url, "ok": False, "http_status": None, "content_length": None, "error": None, "rows": 0}
            try:
                frame, payload_size = _fetch_month_with_size(url)
                frames.append(frame)
                row.update({"ok": True, "http_status": 200, "content_length": payload_size, "rows": int(len(frame))})
            except urllib.error.HTTPError as exc:
                row.update({"http_status": int(exc.code), "error": str(exc)})
            except Exception as exc:
                row.update({"error": repr(exc)})
            coverage_rows.append(row)
            time.sleep(0.01)
        symbol_frame = s31._symbol_close_frame(frames, full_index)
        panel = panel.merge(symbol_frame.rename(columns={"close": f"close_{symbol}"}), on="timestamp", how="left")

    panel["month"] = panel["timestamp"].dt.strftime("%Y-%m")
    panel = panel[["timestamp", "month"] + [f"close_{symbol}" for symbol in MAIN_SYMBOLS]]
    coverage = pd.DataFrame(coverage_rows)
    panel.to_csv(PANEL_PATH, index=False)
    coverage.to_csv(COVERAGE_PATH, index=False)
    return panel, _data_quality(panel, coverage, from_cache=False)


def _fetch_month_with_size(url: str) -> tuple[pd.DataFrame, int]:
    payload = s31._download_url(url)
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = [name for name in zf.namelist() if name.endswith(".csv")]
        if not names:
            raise RuntimeError(f"No CSV found in {url}")
        with zf.open(names[0]) as handle:
            raw = pd.read_csv(handle, header=None)
    return s31._klines_to_frame(raw), len(payload)


def _market(panel: pd.DataFrame) -> dict[str, Any]:
    close = panel[[f"close_{symbol}" for symbol in MAIN_SYMBOLS]].copy()
    close.columns = MAIN_SYMBOLS
    valid = close.notna()
    returns = np.log(close / close.shift(1)).replace([np.inf, -np.inf], np.nan).where(valid & valid.shift(1)).fillna(0.0)
    return {
        "timestamp": pd.to_datetime(panel["timestamp"], utc=True),
        "month": panel["month"].astype(str).to_numpy(),
        "symbols": MAIN_SYMBOLS,
        "close": close,
        "valid": valid,
        "returns": returns,
    }


def _candidate_library() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    leverages = [1.0, 2.0, 4.0]
    for lookback in [16, 96, 384, 1536]:
        for threshold_bps in [0, 50, 100, 200]:
            for leverage in leverages:
                candidates.append(s31._candidate("cross_section", "long_strong_short_weak", leverage, lookback=lookback, threshold_bps=threshold_bps))
                candidates.append(s31._candidate("cross_section", "long_weak_short_strong", leverage, lookback=lookback, threshold_bps=threshold_bps))
    for symbol in MAIN_SYMBOLS:
        for lookback in [16, 96, 384, 1536]:
            for threshold_bps in [20, 50, 100]:
                for leverage in leverages:
                    candidates.append(s31._candidate("single_symbol", "symbol_momentum", leverage, symbol=symbol, lookback=lookback, threshold_bps=threshold_bps))
                    candidates.append(s31._candidate("single_symbol", "symbol_reversal", leverage, symbol=symbol, lookback=lookback, threshold_bps=threshold_bps))
    return candidates


def _candidate_results(candidates: list[dict[str, Any]], market: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_frames: list[pd.DataFrame] = []
    scan_rows: list[dict[str, Any]] = []
    for i, candidate in enumerate(candidates, start=1):
        if i == 1 or i % 100 == 0:
            print(f"candidate {i}/{len(candidates)}", flush=True)
        target = _target_for_candidate(candidate, market)
        monthly_all = s31._monthly_breakdown(s31._simulate_target(market, target))
        monthly_all.insert(0, "candidate_id", candidate["candidate_id"])
        monthly_all.insert(1, "family", candidate["family"])
        monthly_all.insert(2, "rule", candidate["rule"])
        monthly_all.insert(3, "leverage", candidate["leverage"])
        monthly_frames.append(monthly_all)
        monthly_eval = _eval_months_only(monthly_all)
        yearly = upper17._yearly_from_monthly(monthly_eval)
        scan_rows.append({**candidate, **_summary_from_monthly(monthly_eval, yearly)})
    monthly = pd.concat(monthly_frames, ignore_index=True)
    scan = pd.DataFrame(scan_rows).sort_values(
        ["hard_pass_original_2025_2026_ytd", "losing_eval_months", "min_monthly_return_pct", "min_target_year_return_pct"],
        ascending=[False, True, False, False],
    )
    return monthly, scan


def _oracle_results(candidate_monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    eval_monthly = _eval_months_only(candidate_monthly)
    specs = [
        ("monthly_oracle_best_return", None, False),
        ("monthly_oracle_best_return_order10", None, True),
        ("single_symbol_oracle_order10", "single_symbol", True),
        ("cross_section_oracle_order10", "cross_section", True),
    ]
    rows: list[dict[str, Any]] = []
    monthly_frames: list[pd.DataFrame] = []
    yearly_frames: list[pd.DataFrame] = []
    for oracle_id, family, require_order_floor in specs:
        selected = upper17._select_oracle_months(eval_monthly, oracle_id, family, require_order_floor)
        yearly = upper17._yearly_from_monthly(selected)
        rows.append(
            {
                "oracle_id": oracle_id,
                "family_filter": family or "all",
                "leaky_oracle": True,
                "requires_monthly_orders_ge_10_at_selection": require_order_floor,
                "months_without_order_floor_candidate": int(selected["no_order_floor_candidate"].sum()),
                **_summary_from_monthly(selected, yearly),
            }
        )
        if "oracle_id" not in selected.columns:
            selected.insert(0, "oracle_id", oracle_id)
        yearly.insert(0, "oracle_id", oracle_id)
        monthly_frames.append(selected)
        yearly_frames.append(yearly)
    summary = pd.DataFrame(rows).sort_values(
        ["hard_pass_original_2025_2026_ytd", "losing_eval_months", "min_monthly_return_pct", "min_target_year_return_pct"],
        ascending=[False, True, False, False],
    )
    return summary, pd.concat(monthly_frames, ignore_index=True), pd.concat(yearly_frames, ignore_index=True)


def _selector_results(
    candidate_monthly: pd.DataFrame,
    candidates: list[dict[str, Any]],
    market: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    target_cache: dict[str, np.ndarray] = {}
    selection_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    yearly_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []

    for selector_id, family, mode in SELECTORS:
        selections = _select_months(candidate_monthly, candidates, selector_id, family, mode)
        selected_target = np.zeros((len(market["timestamp"]), len(MAIN_SYMBOLS)), dtype=float)
        for row in selections:
            candidate_id = row["candidate_id"]
            if candidate_id not in target_cache:
                target_cache[candidate_id] = _target_for_candidate(_candidate_by_id(candidates, candidate_id), market)
            mask = market["month"] == row["eval_month"]
            selected_target[mask, :] = target_cache[candidate_id][mask, :]
        equity = s31._simulate_target(market, selected_target)
        monthly = _eval_months_only(s31._monthly_breakdown(equity))
        yearly = upper17._yearly_from_monthly(monthly)
        summary_rows.append(
            {
                "selector_id": selector_id,
                "family_filter": family or "all",
                "selection_mode": mode,
                "selected_candidate_count": int(pd.DataFrame(selections)["candidate_id"].nunique()),
                **_summary_from_monthly(monthly, yearly),
            }
        )
        selected = pd.DataFrame(selections)
        selected.insert(0, "selector_id", selector_id)
        monthly.insert(0, "selector_id", selector_id)
        yearly.insert(0, "selector_id", selector_id)
        selection_frames.append(selected)
        monthly_frames.append(monthly)
        yearly_frames.append(yearly)

    summary = pd.DataFrame(summary_rows).sort_values(
        ["hard_pass_original_2025_2026_ytd", "losing_eval_months", "min_monthly_return_pct", "min_target_year_return_pct"],
        ascending=[False, True, False, False],
    )
    return summary, pd.concat(monthly_frames, ignore_index=True), pd.concat(yearly_frames, ignore_index=True), pd.concat(selection_frames, ignore_index=True)


def _select_months(
    candidate_monthly: pd.DataFrame,
    candidates: list[dict[str, Any]],
    selector_id: str,
    family: str | None,
    mode: str,
) -> list[dict[str, Any]]:
    meta = pd.DataFrame(candidates)
    if family:
        meta = meta.loc[meta["family"] == family].copy()
    subset = candidate_monthly.loc[candidate_monthly["candidate_id"].isin(set(meta["candidate_id"]))].copy()
    eval_months = sorted(month for month in subset["month"].unique() if probe16.EVAL_START_MONTH <= str(month) < probe16.EVAL_END_EXCLUSIVE)
    selections: list[dict[str, Any]] = []
    for eval_month in eval_months:
        train = subset.loc[(subset["month"] >= probe16.TRAIN_START_MONTH) & (subset["month"] < eval_month)]
        if train.empty:
            raise RuntimeError(f"No training rows for {selector_id} {eval_month}")
        score = (
            train.groupby("candidate_id", as_index=False)
            .agg(
                train_months=("month", "count"),
                train_log_return=("log_return", "sum"),
                train_losing_months=("return_pct", lambda values: int((values <= 0).sum())),
                train_min_monthly_return_pct=("return_pct", "min"),
                train_min_monthly_orders=("orders", "min"),
                train_turnover=("turnover", "sum"),
                train_last_month=("month", "max"),
            )
            .merge(meta, on="candidate_id", how="left")
        )
        score["train_return_pct"] = (np.exp(score["train_log_return"]) - 1.0) * 100.0
        score["train_hard_ok"] = (
            (score["train_return_pct"] > probe16.REQUIRED_RETURN_PCT)
            & (score["train_losing_months"] == 0)
            & (score["train_min_monthly_orders"] >= probe16.REQUIRED_MIN_MONTHLY_ORDERS)
        )
        score["train_min10_orders_ok"] = score["train_min_monthly_orders"] >= probe16.REQUIRED_MIN_MONTHLY_ORDERS
        score = score.sort_values(_sort_columns(mode), ascending=_sort_ascending(mode))
        best = score.iloc[0].to_dict()
        if not str(best["train_last_month"]) < eval_month:
            raise AssertionError(best)
        eval_row = subset.loc[(subset["candidate_id"] == best["candidate_id"]) & (subset["month"] == eval_month)].iloc[0].to_dict()
        selections.append(
            {
                "eval_month": eval_month,
                "candidate_id": best["candidate_id"],
                "family": best["family"],
                "rule": best["rule"],
                "leverage": best["leverage"],
                "train_hard_ok_candidate_count": int(score["train_hard_ok"].sum()),
                "train_min10_orders_candidate_count": int(score["train_min10_orders_ok"].sum()),
                **{key: value for key, value in best.items() if key.startswith("train_")},
                "eval_static_return_pct": eval_row["return_pct"],
                "eval_static_orders": eval_row["orders"],
                "eval_static_turnover": eval_row["turnover"],
            }
        )
    return selections


def _sort_columns(mode: str) -> list[str]:
    if mode == "hard_guard":
        return [
            "train_hard_ok",
            "train_losing_months",
            "train_min_monthly_return_pct",
            "train_return_pct",
            "train_min_monthly_orders",
            "train_turnover",
            "leverage",
            "candidate_id",
        ]
    if mode == "return_first":
        return ["train_return_pct", "train_losing_months", "train_min_monthly_return_pct", "train_turnover", "leverage", "candidate_id"]
    if mode == "min10_return_first":
        return ["train_min10_orders_ok", "train_return_pct", "train_losing_months", "train_min_monthly_return_pct", "train_turnover", "leverage", "candidate_id"]
    raise KeyError(mode)


def _sort_ascending(mode: str) -> list[bool]:
    if mode == "hard_guard":
        return [False, True, False, False, False, True, True, True]
    if mode == "return_first":
        return [False, True, False, True, True, True]
    if mode == "min10_return_first":
        return [False, False, True, False, True, True, True]
    raise KeyError(mode)


def _candidate_by_id(candidates: list[dict[str, Any]], candidate_id: str) -> dict[str, Any]:
    for candidate in candidates:
        if candidate["candidate_id"] == candidate_id:
            return candidate
    raise KeyError(candidate_id)


def _target_for_candidate(candidate: dict[str, Any], market: dict[str, Any]) -> np.ndarray:
    signal_bps, tradable = _signal_for_lookback(market, int(candidate["lookback"]))
    leverage = float(candidate["leverage"])
    target = np.zeros_like(signal_bps, dtype=float)
    if candidate["family"] == "cross_section":
        finite = np.isfinite(signal_bps) & tradable
        values = np.where(finite, signal_bps, np.nan)
        ok_count = finite.sum(axis=1)
        max_values = np.where(finite, signal_bps, -np.inf)
        min_values = np.where(finite, signal_bps, np.inf)
        strong = np.argmax(max_values, axis=1)
        weak = np.argmin(min_values, axis=1)
        spread = max_values[np.arange(len(strong)), strong] - min_values[np.arange(len(weak)), weak]
        rows = np.where((ok_count >= 2) & (spread >= float(candidate["threshold_bps"])))[0]
        if candidate["rule"] == "long_strong_short_weak":
            long_idx, short_idx = strong[rows], weak[rows]
        else:
            long_idx, short_idx = weak[rows], strong[rows]
        target[rows, long_idx] = leverage / 2.0
        target[rows, short_idx] = -leverage / 2.0
        return target

    symbol = str(candidate["symbol"])
    j = MAIN_SYMBOLS.index(symbol)
    side = np.sign(signal_bps[:, j])
    if candidate["rule"] == "symbol_reversal":
        side = -side
    mask = tradable[:, j] & (np.abs(signal_bps[:, j]) >= float(candidate["threshold_bps"]))
    target[:, j] = np.where(mask, side * leverage, 0.0)
    return np.nan_to_num(target, nan=0.0)


def _signal_for_lookback(market: dict[str, Any], lookback: int) -> tuple[np.ndarray, np.ndarray]:
    cache = market.setdefault("signal_cache", {})
    if lookback in cache:
        return cache[lookback]
    close = market["close"].to_numpy(dtype=float)
    valid = market["valid"].to_numpy(dtype=bool)
    shifted = np.full_like(close, np.nan, dtype=float)
    shifted_valid = np.zeros_like(valid, dtype=bool)
    shifted[lookback:] = close[:-lookback]
    shifted_valid[lookback:] = valid[:-lookback]
    same_month = np.zeros(len(close), dtype=bool)
    same_month[lookback:] = market["month"][lookback:] == market["month"][:-lookback]
    with np.errstate(divide="ignore", invalid="ignore"):
        signal_bps = np.log(close / shifted) * 10_000.0
    tradable = valid & shifted_valid & same_month[:, None] & np.isfinite(signal_bps)
    cache[lookback] = (signal_bps, tradable)
    return cache[lookback]


def _eval_months_only(monthly: pd.DataFrame) -> pd.DataFrame:
    return monthly.loc[(monthly["month"] >= probe16.EVAL_START_MONTH) & (monthly["month"] < probe16.EVAL_END_EXCLUSIVE)].copy()


def _summary_from_monthly(monthly: pd.DataFrame, yearly: pd.DataFrame) -> dict[str, Any]:
    yearly_by_year = {str(row.year): row for row in yearly.itertuples()}
    return_2023 = _year_return(yearly_by_year, "2023")
    return_2024 = _year_return(yearly_by_year, "2024")
    return_2025 = _year_return(yearly_by_year, "2025")
    return_2026 = _year_return(yearly_by_year, "2026")
    complete_returns = [float(yearly_by_year[year].compounded_return_pct) for year in probe16.COMPLETE_EVAL_YEARS if year in yearly_by_year]
    target_returns = [value for value in [return_2025, return_2026] if value is not None]
    min_complete_year_return = min(complete_returns) if complete_returns else -999.0
    min_target_year_return = min(target_returns) if target_returns else -999.0
    losing_eval_months = int((monthly["return_pct"] <= 0).sum())
    min_orders = int(monthly["orders"].min())
    common_gate = losing_eval_months == 0 and min_orders >= probe16.REQUIRED_MIN_MONTHLY_ORDERS
    summary = {
        "hard_pass_original_2025_2026_ytd": bool(
            return_2025 is not None
            and return_2026 is not None
            and return_2025 > probe16.REQUIRED_RETURN_PCT
            and return_2026 > probe16.REQUIRED_RETURN_PCT
            and common_gate
        ),
        "hard_pass_complete_years": bool(
            len(complete_returns) == len(probe16.COMPLETE_EVAL_YEARS)
            and min_complete_year_return > probe16.REQUIRED_RETURN_PCT
            and common_gate
        ),
        "non_positive_months": monthly.loc[monthly["return_pct"] <= 0, "month"].tolist(),
        "total_eval_return_pct": float((np.exp(float(monthly["log_return"].sum())) - 1.0) * 100.0),
        "return_2023_pct": return_2023,
        "return_2024_pct": return_2024,
        "return_2025_pct": return_2025,
        "return_2026_ytd_pct": return_2026,
        "min_complete_year_return_pct": float(min_complete_year_return),
        "min_target_year_return_pct": float(min_target_year_return),
        "losing_eval_months": losing_eval_months,
        "min_monthly_return_pct": float(monthly["return_pct"].min()),
        "min_monthly_orders": min_orders,
        "orders": int(monthly["orders"].sum()),
        "turnover": float(monthly["turnover"].sum()),
        "cost_log": float(monthly["cost_log"].sum()),
        "worst_selected_month_drawdown_pct": float(monthly["max_drawdown_pct"].min()),
    }
    if "candidate_id" in monthly.columns:
        summary["selected_candidate_count"] = int(monthly["candidate_id"].nunique())
    return summary


def _year_return(yearly_by_year: dict[str, Any], year: str) -> float | None:
    if year not in yearly_by_year:
        return None
    return float(yearly_by_year[year].compounded_return_pct)


def _candidate_grid_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    frame = pd.DataFrame(candidates)
    return {
        "candidate_count": int(len(frame)),
        "families": {str(key): int(value) for key, value in frame["family"].value_counts().sort_index().items()},
        "rules": {str(key): int(value) for key, value in frame["rule"].value_counts().sort_index().items()},
        "leverages": sorted(float(value) for value in frame["leverage"].unique()),
    }


def _data_quality(panel: pd.DataFrame, coverage: pd.DataFrame, from_cache: bool) -> dict[str, Any]:
    ts = pd.to_datetime(panel["timestamp"], utc=True)
    months = [str(month) for month in MONTHS]
    symbol_rows = []
    for symbol in MAIN_SYMBOLS:
        cov = coverage.loc[coverage["symbol"] == symbol].copy()
        ok = cov.loc[cov["ok"].astype(bool)].copy()
        first_ok = str(ok["month"].min()) if len(ok) else None
        last_ok = str(ok["month"].max()) if len(ok) else None
        missing_after_first = []
        if first_ok is not None:
            missing_after_first = [
                month
                for month in months[months.index(first_ok) :]
                if month not in set(ok["month"].astype(str))
            ]
        close = panel[f"close_{symbol}"]
        first_ts = panel.loc[close.notna(), "timestamp"].min() if close.notna().any() else None
        last_ts = panel.loc[close.notna(), "timestamp"].max() if close.notna().any() else None
        symbol_rows.append(
            {
                "symbol": symbol,
                "ok_months": int(len(ok)),
                "first_ok_month": first_ok,
                "last_ok_month": last_ok,
                "missing_months_after_first_ok": missing_after_first,
                "first_timestamp": first_ts.isoformat() if first_ts is not None else None,
                "last_timestamp": last_ts.isoformat() if last_ts is not None else None,
                "valid_15m_rows": int(close.notna().sum()),
                "download_size_mb": round(float(ok["content_length"].fillna(0).sum()) / 1024**2, 3),
            }
        )
    symbol_quality = pd.DataFrame(symbol_rows)
    symbol_quality.to_csv(OUT_DIR / "symbol_coverage_summary.csv", index=False)
    non_15m_gap_rows = int((ts.diff().dropna() != BAR_DELTA).sum())
    pass_symbols = all((row["ok_months"] > 0 and row["last_ok_month"] == str(END_MONTH) and len(row["missing_months_after_first_ok"]) == 0) for row in symbol_rows)
    return {
        "from_cache": from_cache,
        "rows": int(len(panel)),
        "start_timestamp": ts.min().isoformat(),
        "end_timestamp": ts.max().isoformat(),
        "months": len(months),
        "duplicate_timestamp_rows": int(ts.duplicated().sum()),
        "non_15m_gap_rows": non_15m_gap_rows,
        "symbols": _json_ready(symbol_rows),
        "coverage": _rel(COVERAGE_PATH),
        "coverage_summary": _rel(OUT_DIR / "symbol_coverage_summary.csv"),
        "pass": bool(ts.duplicated().sum() == 0 and non_15m_gap_rows == 0 and pass_symbols),
    }


def _decision(best_selector: dict[str, Any], best_oracle_order10: dict[str, Any]) -> dict[str, Any]:
    if bool(best_selector["hard_pass_original_2025_2026_ytd"]):
        return {
            "verdict": "MULTISYMBOL_FULL_HISTORY_STRICT_SELECTOR_PROMISING",
            "promote_strategy": False,
            "reason": "多币种完整历史严格选择器通过了2025/2026、月月盈利和每月10单门槛；但这仍是研究审计，还要做压力测试。",
            "next_step": "另起34号做手续费、延迟、漏单和月初切换成本压力测试。",
        }
    if bool(best_oracle_order10["hard_pass_original_2025_2026_ytd"]):
        return {
            "verdict": "MULTISYMBOL_ORACLE_HAS_PIECES_BUT_STRICT_SELECTOR_FAILS",
            "promote_strategy": False,
            "reason": "看答案的月度oracle能过，但严格逐月选择器不能提前选中正确候选。",
            "next_step": "不要升级为策略；除非换真正新的选择方法或新数据，否则不要继续堆同类小规则。",
        }
    return {
        "verdict": "MULTISYMBOL_FULL_HISTORY_STRICT_SELECTOR_FAILS",
        "promote_strategy": False,
        "reason": "多币种完整历史下，严格选择器和每月10单看答案oracle都没过原硬目标。",
        "next_step": "不要把31号样本信号升级为候选；后续应换新数据源或降低目标。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_selector"]
    oracle = summary["best_order10_oracle"]
    static = summary["best_static_candidate"]
    decision = summary["decision"]
    return f"""# 33号多币种完整历史严格选择器

这不是策略，不能交易，也不是固化版。它只检查 31号“四个月样本看答案”信号，扩到完整历史后，能不能严格不看未来地提前选中。

## 数据

- 主币种：{", ".join(MAIN_SYMBOLS)}
- 附加观察但不参与选择：{", ".join(OBSERVATION_ONLY_SYMBOLS)}
- 数据：Binance 免费 USD-M futures 15m 月包
- 范围：`{summary["data"]["start_timestamp"]}` 到 `{summary["data"]["end_timestamp"]}`
- 行数：`{summary["data"]["rows"]}`
- 重复时间：`{summary["data"]["duplicate_timestamp_rows"]}`
- 15分钟断档：`{summary["data"]["non_15m_gap_rows"]}`
- 手续费：开平合计 `{probe16.ROUND_TRIP_COST * 100:.2f}%`
- 时序：信号只用已收盘K线，下一根15分钟K线才吃收益

## 候选

- 候选数：`{summary["candidate_grid"]["candidate_count"]}`
- 静态事后硬通过数：`{summary["static_hard_pass_original_target_count"]}`
- 最好静态候选：`{static["candidate_id"]}`

## 最好每月10单看答案上限

- oracle：`{oracle["oracle_id"]}`
- 2025：`{oracle["return_2025_pct"]:.2f}%`
- 2026 YTD：`{oracle["return_2026_ytd_pct"]:.2f}%`
- 不盈利月份数：`{oracle["losing_eval_months"]}`
- 最差月：`{oracle["min_monthly_return_pct"]:.2f}%`
- 最少月交易：`{oracle["min_monthly_orders"]}`

## 最好严格选择器

- selector：`{best["selector_id"]}`
- 2023：`{best["return_2023_pct"]:.2f}%`
- 2024：`{best["return_2024_pct"]:.2f}%`
- 2025：`{best["return_2025_pct"]:.2f}%`
- 2026 YTD：`{best["return_2026_ytd_pct"]:.2f}%`
- 不盈利月份数：`{best["losing_eval_months"]}`
- 最差月：`{best["min_monthly_return_pct"]:.2f}%`
- 最少月交易：`{best["min_monthly_orders"]}`
- 最大回撤：`{best["worst_selected_month_drawdown_pct"]:.2f}%`

## 判断

`{decision["verdict"]}`

{decision["reason"]}

下一步：{decision["next_step"]}
"""


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_ready(value: Any) -> Any:
    return probe16._json_ready(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
