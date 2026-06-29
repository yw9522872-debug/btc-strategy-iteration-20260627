from __future__ import annotations

import hashlib
import io
import json
import sys
import time
import urllib.error
import urllib.request
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


STRATEGY_ID = "strategy_37_btc_3m_multitimeframe_event_pool_20260629"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
KLINES_PATH = OUT_DIR / "btc_3m_2020_2026_05_public_klines.csv.gz"
DOWNLOAD_QUALITY = OUT_DIR / "download_quality.csv"

SYMBOL = "BTCUSDT"
INTERVAL = "3m"
START_MONTH = pd.Period("2020-01", freq="M")
END_MONTH = pd.Period("2026-05", freq="M")
MONTHS = list(pd.period_range(START_MONTH, END_MONTH, freq="M"))
BAR_DELTA = pd.Timedelta(minutes=3)
USER_AGENT = "strategy-37-btc-3m-multitimeframe-event-pool/1.0"
URL_TEMPLATE = "https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{yyyy}-{mm}.zip"

SELECTORS = [
    ("all_events", None, "hard_guard"),
    ("trend_events", "event_trend", "hard_guard"),
    ("range_events", "event_range", "hard_guard"),
    ("return_first_all", None, "return_first"),
    ("min10_return_first_all", None, "min10_return_first"),
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    klines, data_quality = _load_or_fetch_klines()
    if not data_quality["pass"]:
        raise RuntimeError("Strategy 37 BTC 3m data quality failed.")

    market = _market(klines)
    features = FeatureCache(klines)
    candidates = _candidate_library()
    candidate_monthly, candidate_scan = _candidate_results(candidates, market, features)
    oracle_summary, oracle_monthly, oracle_yearly = _oracle_results(candidate_monthly)
    selector_summary, selector_monthly, selector_yearly, selected_params = _selector_results(candidate_monthly, candidates, market, features)
    combo_summary, combo_monthly = _combo_monthly_approx(candidate_monthly)

    candidate_monthly.to_csv(OUT_DIR / "candidate_monthly.csv", index=False)
    candidate_scan.to_csv(OUT_DIR / "candidate_scan.csv", index=False)
    oracle_summary.to_csv(OUT_DIR / "oracle_summary.csv", index=False)
    oracle_monthly.to_csv(OUT_DIR / "oracle_monthly.csv", index=False)
    oracle_yearly.to_csv(OUT_DIR / "oracle_yearly.csv", index=False)
    selector_summary.to_csv(OUT_DIR / "selector_summary.csv", index=False)
    selector_monthly.to_csv(OUT_DIR / "selector_monthly.csv", index=False)
    selector_yearly.to_csv(OUT_DIR / "selector_yearly.csv", index=False)
    selected_params.to_csv(OUT_DIR / "selected_params.csv", index=False)
    combo_summary.to_csv(OUT_DIR / "combo_summary.csv", index=False)
    combo_monthly.to_csv(OUT_DIR / "combo_monthly.csv", index=False)

    best_selector = selector_summary.iloc[0].to_dict()
    best_oracle_order10 = oracle_summary.loc[oracle_summary["requires_monthly_orders_ge_10_at_selection"]].iloc[0].to_dict()
    best_combo = combo_summary.iloc[0].to_dict()
    summary = {
        "status": "strategy_37_btc_3m_multitimeframe_event_pool_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Test a genuinely new BTCUSDT 3m multi-timeframe event pool with leaky upper bound and strict monthly walk-forward selectors.",
        "data": data_quality,
        "evaluation": {
            "train_start_month": probe16.TRAIN_START_MONTH,
            "eval_start_month": probe16.EVAL_START_MONTH,
            "eval_end_exclusive": probe16.EVAL_END_EXCLUSIVE,
            "available_data_end_month": str(END_MONTH),
            "main_hard_target": "2025 > 100%, 2026 YTD > 100%, every eval month positive, every eval month orders >= 10.",
        },
        "cost_model": {
            "cost_per_side": probe16.COST_PER_SIDE,
            "round_trip_open_close": probe16.ROUND_TRIP_COST,
        },
        "timing": {
            "signals_use_closed_3m_bar_t": True,
            "position_participates_from_bar_t_plus_1": True,
            "strict_selector_uses_only_months_before_eval_month": True,
            "monthly_oracle_is_leaky_and_not_tradeable": True,
            "combo_monthly_approx_is_not_trade_replay": True,
        },
        "candidate_grid": _candidate_grid_summary(candidates),
        "static_hard_pass_original_target_count": int(candidate_scan["hard_pass_original_2025_2026_ytd"].sum()),
        "static_hard_pass_complete_years_count": int(candidate_scan["hard_pass_complete_years"].sum()),
        "best_static_candidate": _json_ready(candidate_scan.iloc[0].to_dict()),
        "oracle_summary": _json_ready(oracle_summary.to_dict("records")),
        "best_order10_oracle": _json_ready(best_oracle_order10),
        "selector_summary": _json_ready(selector_summary.to_dict("records")),
        "best_selector": _json_ready(best_selector),
        "combo_monthly_approx": {
            "config_count": int(len(combo_summary)),
            "best_config": _json_ready(best_combo),
            "note": "This combines candidate monthly returns only, so it is a cheap screen, not a per-3m-bar capital replay.",
        },
        "decision": _decision(best_selector, best_oracle_order10, best_combo),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "klines_sha256": _sha256(KLINES_PATH),
            "download_quality_sha256": _sha256(DOWNLOAD_QUALITY),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "klines": _rel(KLINES_PATH),
            "download_quality": _rel(DOWNLOAD_QUALITY),
            "candidate_scan": _rel(OUT_DIR / "candidate_scan.csv"),
            "candidate_monthly": _rel(OUT_DIR / "candidate_monthly.csv"),
            "oracle_summary": _rel(OUT_DIR / "oracle_summary.csv"),
            "oracle_monthly": _rel(OUT_DIR / "oracle_monthly.csv"),
            "oracle_yearly": _rel(OUT_DIR / "oracle_yearly.csv"),
            "selector_summary": _rel(OUT_DIR / "selector_summary.csv"),
            "selector_monthly": _rel(OUT_DIR / "selector_monthly.csv"),
            "selector_yearly": _rel(OUT_DIR / "selector_yearly.csv"),
            "selected_params": _rel(OUT_DIR / "selected_params.csv"),
            "combo_summary": _rel(OUT_DIR / "combo_summary.csv"),
            "combo_monthly": _rel(OUT_DIR / "combo_monthly.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    _self_check(summary)
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_or_fetch_klines() -> tuple[pd.DataFrame, dict[str, Any]]:
    if KLINES_PATH.exists() and DOWNLOAD_QUALITY.exists():
        frame = pd.read_csv(KLINES_PATH)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        quality = pd.read_csv(DOWNLOAD_QUALITY)
        return frame, _data_quality(frame, quality, from_cache=True)

    frames: list[pd.DataFrame] = []
    quality_rows: list[dict[str, Any]] = []
    for month in MONTHS:
        url = URL_TEMPLATE.format(symbol=SYMBOL, interval=INTERVAL, yyyy=month.year, mm=f"{month.month:02d}")
        row = {"month": str(month), "url": url, "ok": False, "http_status": None, "rows": 0, "content_length": None, "error": None}
        try:
            frame, payload_size = _fetch_archive(url)
            frames.append(frame)
            row.update({"ok": True, "http_status": 200, "rows": int(len(frame)), "content_length": payload_size})
        except urllib.error.HTTPError as exc:
            row.update({"http_status": int(exc.code), "error": str(exc)})
        except Exception as exc:
            row.update({"error": repr(exc)})
        quality_rows.append(row)
        time.sleep(0.01)

    if not frames:
        raise RuntimeError("No BTC 3m monthly archive was downloaded.")
    frame = pd.concat(frames, ignore_index=True).drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
    quality = pd.DataFrame(quality_rows)
    frame.to_csv(KLINES_PATH, index=False)
    quality.to_csv(DOWNLOAD_QUALITY, index=False)
    return frame, _data_quality(frame, quality, from_cache=False)


def _fetch_archive(url: str) -> tuple[pd.DataFrame, int]:
    payload = _download_url(url)
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = [name for name in zf.namelist() if name.endswith(".csv")]
        if not names:
            raise RuntimeError(f"No CSV found in {url}")
        with zf.open(names[0]) as handle:
            raw = pd.read_csv(handle, header=None)
    return _klines_to_frame(raw), len(payload)


def _download_url(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError:
            raise
        except Exception as exc:
            last_error = exc
            time.sleep(1.0 + attempt)
    raise RuntimeError(f"Failed to download {url}: {last_error!r}")


def _klines_to_frame(raw: pd.DataFrame) -> pd.DataFrame:
    names = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore"]
    raw = raw.iloc[:, : len(names)].copy()
    raw.columns = names[: len(raw.columns)]
    if len(raw) and str(raw.iloc[0]["open_time"]).lower() == "open_time":
        raw = raw.iloc[1:].reset_index(drop=True)
    out = pd.DataFrame({"timestamp": pd.to_datetime(pd.to_numeric(raw["open_time"], errors="coerce"), unit="ms", utc=True)})
    for column in ["open", "high", "low", "close", "volume", "quote_volume", "trades", "taker_base", "taker_quote"]:
        out[column] = pd.to_numeric(raw[column], errors="coerce")
    return out.dropna(subset=["timestamp", "open", "high", "low", "close", "volume"]).drop_duplicates("timestamp", keep="last").sort_values("timestamp")


class FeatureCache:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.open = pd.Series(frame["open"].astype(float).to_numpy())
        self.high = pd.Series(frame["high"].astype(float).to_numpy())
        self.low = pd.Series(frame["low"].astype(float).to_numpy())
        self.close = pd.Series(frame["close"].astype(float).to_numpy())
        self.volume = pd.Series(frame["volume"].astype(float).to_numpy())
        self.raw_return = np.log(self.close).diff().fillna(0.0)
        self._ret_bps: dict[int, pd.Series] = {}
        self._atr: dict[int, pd.Series] = {}
        self._volume_z: dict[int, pd.Series] = {}

    def ret_bps(self, window: int) -> pd.Series:
        if window not in self._ret_bps:
            self._ret_bps[window] = np.log(self.close / self.close.shift(window)) * 10_000.0
        return self._ret_bps[window]

    def atr_bps(self, window: int) -> pd.Series:
        if window not in self._atr:
            prev_close = self.close.shift(1)
            true_range = pd.concat([self.high - self.low, (self.high - prev_close).abs(), (self.low - prev_close).abs()], axis=1).max(axis=1)
            self._atr[window] = true_range.rolling(window, min_periods=window).mean() / self.close * 10_000.0
        return self._atr[window]

    def volume_z(self, window: int) -> pd.Series:
        if window not in self._volume_z:
            mean = self.volume.rolling(window, min_periods=window).mean()
            std = self.volume.rolling(window, min_periods=window).std(ddof=0).replace(0, np.nan)
            self._volume_z[window] = (self.volume - mean) / std
        return self._volume_z[window]


def _candidate_library() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    leverages = [1.0, 2.0, 4.0]
    for trigger_window in [5, 20, 80]:
        for trend_window in [320, 960]:
            for trigger_threshold_bps in [50, 100]:
                for trend_threshold_bps in [50, 150]:
                    for hold_bars in [8, 32]:
                        for leverage in leverages:
                            candidates.append(
                                _candidate(
                                    "event_trend",
                                    "trend_breakout",
                                    leverage,
                                    trigger_window=trigger_window,
                                    trend_window=trend_window,
                                    trigger_threshold_bps=trigger_threshold_bps,
                                    trend_threshold_bps=trend_threshold_bps,
                                    hold_bars=hold_bars,
                                )
                            )
                            candidates.append(
                                _candidate(
                                    "event_trend",
                                    "trend_pullback",
                                    leverage,
                                    trigger_window=trigger_window,
                                    trend_window=trend_window,
                                    trigger_threshold_bps=trigger_threshold_bps,
                                    trend_threshold_bps=trend_threshold_bps,
                                    hold_bars=hold_bars,
                                )
                            )
                            candidates.append(
                                _candidate(
                                    "event_range",
                                    "range_reversal",
                                    leverage,
                                    trigger_window=trigger_window,
                                    trend_window=trend_window,
                                    trigger_threshold_bps=trigger_threshold_bps,
                                    trend_threshold_bps=trend_threshold_bps,
                                    hold_bars=hold_bars,
                                )
                            )
    for trigger_window in [5, 20]:
        for trend_window in [320, 960]:
            for trend_threshold_bps in [50, 150]:
                for volume_z in [1.5, 2.5]:
                    for hold_bars in [8, 32]:
                        for leverage in [1.0, 2.0]:
                            candidates.append(
                                _candidate(
                                    "event_volume",
                                    "volume_trend_breakout",
                                    leverage,
                                    trigger_window=trigger_window,
                                    trend_window=trend_window,
                                    trigger_threshold_bps=50,
                                    trend_threshold_bps=trend_threshold_bps,
                                    volume_z=volume_z,
                                    hold_bars=hold_bars,
                                )
                            )
    return candidates


def _candidate(family: str, rule: str, leverage: float, **params: Any) -> dict[str, Any]:
    suffix = "_".join(f"{key}{str(value).replace('.', 'p')}" for key, value in params.items())
    return {"candidate_id": f"{family}_{rule}_lev{str(leverage).replace('.', 'p')}_{suffix}", "family": family, "rule": rule, "leverage": leverage, **params}


def _target_for_candidate(candidate: dict[str, Any], f: FeatureCache) -> np.ndarray:
    rule = str(candidate["rule"])
    trigger = f.ret_bps(int(candidate["trigger_window"]))
    trend = f.ret_bps(int(candidate["trend_window"]))
    trigger_abs = trigger.abs()
    trend_abs = trend.abs()
    trigger_side = np.sign(trigger)
    trend_side = np.sign(trend)
    trigger_ok = trigger_abs >= float(candidate["trigger_threshold_bps"])
    trend_ok = trend_abs >= float(candidate["trend_threshold_bps"])

    if rule == "trend_breakout":
        event = trigger_ok & trend_ok & (trigger_side == trend_side)
        side = trend_side.where(event, 0.0)
    elif rule == "trend_pullback":
        event = trigger_ok & trend_ok & (trigger_side == -trend_side)
        side = trend_side.where(event, 0.0)
    elif rule == "range_reversal":
        event = trigger_ok & (~trend_ok)
        side = (-trigger_side).where(event, 0.0)
    elif rule == "volume_trend_breakout":
        event = trigger_ok & trend_ok & (trigger_side == trend_side) & (f.volume_z(320) >= float(candidate["volume_z"]))
        side = trend_side.where(event, 0.0)
    else:
        raise ValueError(rule)

    held = _hold_event_side(side.to_numpy(dtype=float), int(candidate["hold_bars"]))
    return np.nan_to_num(held, nan=0.0) * float(candidate["leverage"])


def _hold_event_side(event_side: np.ndarray, hold_bars: int) -> np.ndarray:
    side = pd.Series(np.where(np.isfinite(event_side) & (event_side != 0), event_side, np.nan))
    return side.ffill(limit=max(0, hold_bars - 1)).fillna(0.0).to_numpy(dtype=float)


def _market(frame: pd.DataFrame) -> dict[str, Any]:
    timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    close = frame["close"].astype(float)
    return {
        "timestamp": timestamp,
        "month": timestamp.dt.strftime("%Y-%m").to_numpy(),
        "close": close.to_numpy(dtype=float),
        "raw_return": np.log(close).diff().fillna(0.0).to_numpy(dtype=float),
    }


def _simulate_target(market: dict[str, Any], target: np.ndarray) -> pd.DataFrame:
    target = np.nan_to_num(target.astype(float), nan=0.0)
    active = np.roll(target, 1)
    active[0] = 0.0
    turnover = np.abs(target - np.r_[0.0, target[:-1]])
    order_count = (turnover > 1e-12).astype(int)
    cost = turnover * probe16.COST_PER_SIDE
    strategy_lr = active * market["raw_return"] - cost
    equity = np.exp(np.cumsum(strategy_lr))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    if len(target) > 1 and not np.allclose(active[1:], target[:-1]):
        raise AssertionError("Timing check failed: active position must lag target by one bar.")
    return pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "month": market["month"],
            "target_position": target,
            "active_position": active,
            "turnover": turnover,
            "order_count": order_count,
            "cost": cost,
            "strategy_log_return": strategy_lr,
            "equity": equity,
            "drawdown": drawdown,
        }
    )


def _monthly_breakdown(equity: pd.DataFrame) -> pd.DataFrame:
    monthly = equity.groupby("month", as_index=False).agg(
        log_return=("strategy_log_return", "sum"),
        cost_log=("cost", "sum"),
        turnover=("turnover", "sum"),
        orders=("order_count", "sum"),
        exposure_pct=("active_position", lambda values: float((np.abs(values) > 0).mean() * 100.0)),
        max_drawdown_pct=("drawdown", lambda values: float(values.min() * 100.0)),
    )
    monthly["return_pct"] = (np.exp(monthly["log_return"]) - 1.0) * 100.0
    return monthly


def _candidate_results(candidates: list[dict[str, Any]], market: dict[str, Any], features: FeatureCache) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_frames: list[pd.DataFrame] = []
    scan_rows: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        if index == 1 or index % 100 == 0:
            print(f"candidate {index}/{len(candidates)}", flush=True)
        target = _target_for_candidate(candidate, features)
        monthly_all = _monthly_breakdown(_simulate_target(market, target))
        monthly_all.insert(0, "candidate_id", candidate["candidate_id"])
        monthly_all.insert(1, "family", candidate["family"])
        monthly_all.insert(2, "rule", candidate["rule"])
        monthly_all.insert(3, "leverage", candidate["leverage"])
        monthly_frames.append(monthly_all)
        monthly_eval = _eval_months_only(monthly_all)
        yearly = upper17._yearly_from_monthly(monthly_eval)
        scan_rows.append({**candidate, **_summary_from_monthly(monthly_eval, yearly)})
    scan = pd.DataFrame(scan_rows).sort_values(
        ["hard_pass_original_2025_2026_ytd", "losing_eval_months", "min_monthly_return_pct", "min_target_year_return_pct"],
        ascending=[False, True, False, False],
    )
    return pd.concat(monthly_frames, ignore_index=True), scan


def _oracle_results(candidate_monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    eval_monthly = _eval_months_only(candidate_monthly)
    specs = [
        ("monthly_oracle_best_return", None, False),
        ("monthly_oracle_best_return_order10", None, True),
        ("trend_oracle_order10", "event_trend", True),
        ("range_oracle_order10", "event_range", True),
        ("volume_oracle_order10", "event_volume", True),
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
    features: FeatureCache,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    target_cache: dict[str, np.ndarray] = {}
    summary_rows: list[dict[str, Any]] = []
    monthly_frames: list[pd.DataFrame] = []
    yearly_frames: list[pd.DataFrame] = []
    selected_frames: list[pd.DataFrame] = []
    for selector_id, family, mode in SELECTORS:
        selections = _select_months(candidate_monthly, candidates, selector_id, family, mode)
        selected_target = np.zeros(len(market["timestamp"]), dtype=float)
        for row in selections:
            candidate_id = row["candidate_id"]
            if candidate_id not in target_cache:
                target_cache[candidate_id] = _target_for_candidate(_candidate_by_id(candidates, candidate_id), features)
            mask = market["month"] == row["eval_month"]
            selected_target[mask] = target_cache[candidate_id][mask]
        monthly = _eval_months_only(_monthly_breakdown(_simulate_target(market, selected_target)))
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
        selected_frames.append(selected)
        monthly_frames.append(monthly)
        yearly_frames.append(yearly)
    summary = pd.DataFrame(summary_rows).sort_values(
        ["hard_pass_original_2025_2026_ytd", "losing_eval_months", "min_monthly_return_pct", "min_target_year_return_pct"],
        ascending=[False, True, False, False],
    )
    return summary, pd.concat(monthly_frames, ignore_index=True), pd.concat(yearly_frames, ignore_index=True), pd.concat(selected_frames, ignore_index=True)


def _select_months(candidate_monthly: pd.DataFrame, candidates: list[dict[str, Any]], selector_id: str, family: str | None, mode: str) -> list[dict[str, Any]]:
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


def _combo_monthly_approx(candidate_monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    eval_months = sorted(month for month in candidate_monthly["month"].unique() if probe16.EVAL_START_MONTH <= str(month) < probe16.EVAL_END_EXCLUSIVE)
    configs = [
        (top_k, lookback, min_pos_rate, score_mode)
        for top_k in [3, 5, 10, 20]
        for lookback in [12, 24, 0]
        for min_pos_rate in [0.45, 0.50]
        for score_mode in ["mean", "pos_mean"]
    ]
    score_rows: list[dict[str, Any]] = []
    all_monthly: list[dict[str, Any]] = []
    for config_id, (top_k, lookback, min_pos_rate, score_mode) in enumerate(configs):
        rows = []
        for eval_month in eval_months:
            train = candidate_monthly.loc[(candidate_monthly["month"] < eval_month) & (candidate_monthly["month"] >= probe16.TRAIN_START_MONTH)]
            if lookback:
                months = sorted(train["month"].unique())[-lookback:]
                train = train.loc[train["month"].isin(months)]
            selected = _combo_select(train, top_k, min_pos_rate, score_mode)
            current = candidate_monthly.loc[(candidate_monthly["month"] == eval_month) & (candidate_monthly["candidate_id"].isin(selected))]
            if current.empty:
                log_return = 0.0
                orders = 0
            else:
                log_return = _equal_weight_log_return(current["log_return"].to_numpy(float))
                orders = int(current["orders"].sum())
            rows.append(
                {
                    "config_id": config_id,
                    "month": eval_month,
                    "log_return": log_return,
                    "return_pct": (np.exp(log_return) - 1.0) * 100.0,
                    "cost_log": 0.0,
                    "turnover": 0.0,
                    "orders": orders,
                    "max_drawdown_pct": min(0.0, (np.exp(log_return) - 1.0) * 100.0),
                    "selected_count": int(len(selected)),
                    "selected_candidate_ids": ";".join(selected[:20]),
                }
            )
        monthly = pd.DataFrame(rows)
        score_rows.append(_combo_score(monthly, config_id, top_k, lookback, min_pos_rate, score_mode))
        all_monthly.extend(rows)
    summary = pd.DataFrame(score_rows).sort_values(
        ["hard_pass_original_2025_2026_ytd", "losing_eval_months", "min_monthly_return_pct", "min_target_year_return_pct"],
        ascending=[False, True, False, False],
    )
    best_config = int(summary.iloc[0]["config_id"])
    return summary.reset_index(drop=True), pd.DataFrame(all_monthly).loc[lambda df: df["config_id"] == best_config].reset_index(drop=True)


def _combo_select(train: pd.DataFrame, top_k: int, min_pos_rate: float, score_mode: str) -> list[str]:
    if train["month"].nunique() < 12:
        return []
    score = train.groupby("candidate_id", as_index=False).agg(mean_lr=("log_return", "mean"), pos_rate=("return_pct", lambda values: float((values > 0).mean())))
    score = score.loc[score["pos_rate"] >= min_pos_rate].copy()
    if score.empty:
        return []
    score["score"] = score["mean_lr"] if score_mode == "mean" else score["mean_lr"] + score["pos_rate"]
    return score.sort_values(["score", "mean_lr", "candidate_id"], ascending=[False, False, True]).head(top_k)["candidate_id"].tolist()


def _equal_weight_log_return(log_returns: np.ndarray) -> float:
    simple = np.expm1(np.clip(np.asarray(log_returns, dtype=float), -50.0, 50.0))
    portfolio_simple = float(simple.mean()) if len(simple) else 0.0
    if portfolio_simple <= -1.0:
        return -50.0
    return float(np.log1p(portfolio_simple))


def _combo_score(monthly: pd.DataFrame, config_id: int, top_k: int, lookback: int, min_pos_rate: float, score_mode: str) -> dict[str, Any]:
    yearly = upper17._yearly_from_monthly(monthly)
    return {
        "config_id": int(config_id),
        "top_k": int(top_k),
        "lookback_months": int(lookback),
        "min_pos_rate": float(min_pos_rate),
        "score_mode": score_mode,
        **_summary_from_monthly(monthly, yearly),
    }


def _sort_columns(mode: str) -> list[str]:
    if mode == "hard_guard":
        return ["train_hard_ok", "train_losing_months", "train_min_monthly_return_pct", "train_return_pct", "train_min_monthly_orders", "train_turnover", "leverage", "candidate_id"]
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
    return {
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
        "turnover": float(monthly["turnover"].sum()) if "turnover" in monthly.columns else None,
        "cost_log": float(monthly["cost_log"].sum()) if "cost_log" in monthly.columns else None,
        "worst_selected_month_drawdown_pct": float(monthly["max_drawdown_pct"].min()) if "max_drawdown_pct" in monthly.columns else None,
        **({"selected_candidate_count": int(monthly["candidate_id"].nunique())} if "candidate_id" in monthly.columns else {}),
    }


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
        "trigger_windows_3m_bars": sorted(int(value) for value in frame["trigger_window"].dropna().unique()),
        "trend_windows_3m_bars": sorted(int(value) for value in frame["trend_window"].dropna().unique()),
        "hold_bars": sorted(int(value) for value in frame["hold_bars"].dropna().unique()),
    }


def _data_quality(frame: pd.DataFrame, quality: pd.DataFrame, from_cache: bool) -> dict[str, Any]:
    ts = pd.to_datetime(frame["timestamp"], utc=True)
    diffs = ts.diff().dropna()
    ok = quality.loc[quality["ok"].astype(bool)] if "ok" in quality else pd.DataFrame()
    missing_months = [str(month) for month in MONTHS if str(month) not in set(ok["month"].astype(str))] if "month" in quality else []
    return {
        "from_cache": from_cache,
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "rows": int(len(frame)),
        "start_timestamp": ts.min().isoformat(),
        "end_timestamp": ts.max().isoformat(),
        "months": int(len(MONTHS)),
        "duplicate_timestamp_rows": int(ts.duplicated().sum()),
        "non_3m_gap_rows": int((diffs != BAR_DELTA).sum()),
        "downloaded_files": int(len(ok)),
        "download_size_mb": round(float(ok["content_length"].fillna(0).sum()) / 1024**2, 3) if len(ok) else 0.0,
        "missing_months": missing_months,
        "pass": bool(ts.duplicated().sum() == 0 and (diffs != BAR_DELTA).sum() == 0 and not missing_months),
    }


def _decision(best_selector: dict[str, Any], best_oracle_order10: dict[str, Any], best_combo: dict[str, Any]) -> dict[str, Any]:
    if bool(best_selector["hard_pass_original_2025_2026_ytd"]):
        return {
            "verdict": "BTC_3M_MULTITIMEFRAME_EVENT_STRICT_SELECTOR_PROMISING",
            "promote_strategy": False,
            "reason": "严格月初选择器通过了2025/2026、每月盈利和每月10单门槛；但这仍是研究审计，不是实盘策略。",
            "next_step": "另起38号做手续费、延迟、漏单、2024压力和泄漏复核。",
        }
    if bool(best_oracle_order10["hard_pass_original_2025_2026_ytd"]):
        return {
            "verdict": "BTC_3M_MULTITIMEFRAME_ORACLE_HAS_PIECES_SELECTOR_FAILS",
            "promote_strategy": False,
            "reason": "看答案月度上限能过，但严格月初选择器不能提前选中正确事件。",
            "next_step": "不要升级为策略；若继续，只能研究新的非未来选择方法或换新数据。",
        }
    if bool(best_combo["hard_pass_original_2025_2026_ytd"]):
        return {
            "verdict": "BTC_3M_MULTITIMEFRAME_COMBO_APPROX_HAS_PIECES",
            "promote_strategy": False,
            "reason": "单事件看答案没过，但月度组合近似出现通过；它不是逐K资金重放，不能交易。",
            "next_step": "若继续，另起38号只重放这个组合近似的少数最佳配置，先查泄漏和换手。",
        }
    return {
        "verdict": "BTC_3M_MULTITIMEFRAME_EVENT_POOL_FAILS",
        "promote_strategy": False,
        "reason": "新的3m多周期事件池里，静态候选、看答案月度上限、严格选择器和便宜组合近似都没过硬目标。",
        "next_step": "不要继续小修这批事件；除非换真正不同的数据源，否则更适合降低目标做影子跟踪。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_selector"]
    oracle = summary["best_order10_oracle"]
    combo = summary["combo_monthly_approx"]["best_config"]
    static = summary["best_static_candidate"]
    decision = summary["decision"]
    return f"""# 37号 BTC 3m 多周期事件池审计

这不是策略，不能交易，也不是固化版。

## 数据和口径

- 数据：Binance 免费 USD-M futures `BTCUSDT` 3m K线
- 范围：`{summary["data"]["start_timestamp"]}` 到 `{summary["data"]["end_timestamp"]}`
- 行数：`{summary["data"]["rows"]}`
- 缺3分钟断档：`{summary["data"]["non_3m_gap_rows"]}`
- 手续费：开平合计 `{probe16.ROUND_TRIP_COST * 100:.2f}%`
- 时序：信号只用已收盘3分钟K线，下一根3分钟K线才吃收益
- 选择器：每个月只用该月之前的数据选事件

## 候选池

- 候选数：`{summary["candidate_grid"]["candidate_count"]}`
- 家族：`{", ".join(summary["candidate_grid"]["families"].keys())}`
- 规则：`{", ".join(summary["candidate_grid"]["rules"].keys())}`
- 静态硬通过数：`{summary["static_hard_pass_original_target_count"]}`
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

## 便宜组合近似

- 配置数：`{summary["combo_monthly_approx"]["config_count"]}`
- 最好配置：top_k `{combo["top_k"]}`，lookback `{combo["lookback_months"]}`，min_pos_rate `{combo["min_pos_rate"]}`，score `{combo["score_mode"]}`
- 2025：`{combo["return_2025_pct"]:.2f}%`
- 2026 YTD：`{combo["return_2026_ytd_pct"]:.2f}%`
- 不盈利月份数：`{combo["losing_eval_months"]}`
- 注意：这只是月度收益层面的便宜筛查，不是逐K资金重放。

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


def _self_check(summary: dict[str, Any]) -> None:
    if summary["orders_generated"] or summary["orders_submitted"] or summary["secret_access"]:
        raise AssertionError("Safety flags are wrong.")
    for path in summary["files"].values():
        full_path = ROOT / path
        if not full_path.exists() or full_path.stat().st_size <= 0:
            raise AssertionError(f"Missing output file: {full_path}")


if __name__ == "__main__":
    main()
