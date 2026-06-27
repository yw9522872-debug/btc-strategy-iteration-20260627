from __future__ import annotations

import hashlib
import io
import json
import sys
import time
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


STRATEGY_ID = "strategy_21_volume_upper_bound_20260627"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
BASELINE_15_SUMMARY = ROOT / "artifacts" / "strategy_15_unified_data_baseline_20260627" / "summary.json"
VOLUME_KLINES = OUT_DIR / "btc_15m_2020_2026_05_public_volume_klines.csv"

SYMBOL = "BTCUSDT"
INTERVAL = "15m"
BAR_DELTA = pd.Timedelta(minutes=15)
PUBLIC_ARCHIVE_BASE_URL = "https://data.binance.vision/data/futures/um/monthly/klines"
START_MONTH = pd.Period("2020-01", freq="M")
END_MONTH = pd.Period("2026-05", freq="M")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    baseline = json.loads(BASELINE_15_SUMMARY.read_text(encoding="utf-8"))
    if not baseline["quality"]["pass"]:
        raise RuntimeError("Strategy 15 data baseline is not ready.")

    volume_frame, data_quality = _load_or_fetch_volume_klines()
    parity = _parity_check_with_strategy_15(volume_frame, ROOT / baseline["input_files"]["combined_ohlc"])
    market = _market(volume_frame)
    features = VolumeFeatures(volume_frame)
    candidates = _candidate_library()
    candidate_monthly, candidate_scan = _candidate_results(candidates, market, features)

    oracle_specs = [
        ("monthly_oracle_best_return", None, False),
        ("monthly_oracle_best_return_order10", None, True),
        ("volume_spike_oracle_order10", "volume_spike", True),
        ("taker_imbalance_oracle_order10", "taker_imbalance", True),
        ("volume_confirmed_move_oracle_order10", "volume_confirmed_move", True),
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
        "status": "strategy_21_volume_upper_bound_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Measure a leaky monthly oracle upper bound for public Binance USD-M futures volume and taker-flow features.",
        "source": {
            "baseline_15_summary": _rel(BASELINE_15_SUMMARY),
            "public_archive_base_url": PUBLIC_ARCHIVE_BASE_URL,
            "download_months": f"{START_MONTH} to {END_MONTH}",
            "volume_klines": _rel(VOLUME_KLINES),
            "funding_and_open_interest_included": False,
            "funding_open_interest_note": "Strategy 21 first tests the easiest public 15m kline volume/taker fields. Funding and open interest use different sources and are left for a later test only if this upper bound is useful.",
        },
        "data": {
            "eval_start_month": probe16.EVAL_START_MONTH,
            "eval_end_exclusive": probe16.EVAL_END_EXCLUSIVE,
            "complete_eval_years_for_annual_threshold": probe16.COMPLETE_EVAL_YEARS,
            "partial_eval_year_recorded_not_annual_threshold": probe16.PARTIAL_EVAL_YEAR,
            "rows": int(len(volume_frame)),
            "start_timestamp": volume_frame["timestamp"].min().isoformat(),
            "end_timestamp": volume_frame["timestamp"].max().isoformat(),
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
            "per_candidate_signal_timing": "Each candidate uses closed bar t volume/taker/OHLC values and participates from bar t+1.",
        },
        "static_hard_pass_count": int(candidate_scan["hard_pass_complete_years"].sum()),
        "best_static_candidate": _json_ready(candidate_scan.iloc[0].to_dict()),
        "oracle_summary": _json_ready(oracle_summary.to_dict("records")),
        "best_oracle": _json_ready(best_oracle),
        "decision": _decision(best_oracle),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "volume_klines_sha256": _sha256(VOLUME_KLINES),
            "baseline_15_summary_sha256": _sha256(BASELINE_15_SUMMARY),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "volume_klines": _rel(VOLUME_KLINES),
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


def _load_or_fetch_volume_klines() -> tuple[pd.DataFrame, dict[str, Any]]:
    if VOLUME_KLINES.exists():
        frame = pd.read_csv(VOLUME_KLINES)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        return frame, _quality(frame, from_cache=True)

    frames: list[pd.DataFrame] = []
    for month in pd.period_range(START_MONTH, END_MONTH, freq="M"):
        url = f"{PUBLIC_ARCHIVE_BASE_URL}/{SYMBOL}/{INTERVAL}/{SYMBOL}-{INTERVAL}-{month.year}-{month.month:02d}.zip"
        frames.append(_fetch_month(url))
    frame = pd.concat(frames, ignore_index=True)
    frame = _clean_and_fill(frame)
    frame.to_csv(VOLUME_KLINES, index=False)
    return frame, _quality(frame, from_cache=False)


def _fetch_month(url: str) -> pd.DataFrame:
    payload = _download_url(url)
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = [name for name in zf.namelist() if name.endswith(".csv")]
        if not names:
            raise RuntimeError(f"No CSV found in {url}")
        with zf.open(names[0]) as handle:
            raw = pd.read_csv(handle, header=None)
    return _klines_to_frame(raw)


def _download_url(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "strategy-21-volume-research/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except Exception as exc:  # pragma: no cover - network reliability path
            last_error = exc
            if attempt < 3:
                time.sleep(2.0 + attempt)
    raise RuntimeError(f"Failed to download {url}: {last_error!r}")


def _klines_to_frame(raw: pd.DataFrame) -> pd.DataFrame:
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
    out = pd.DataFrame({"timestamp": pd.to_datetime(pd.to_numeric(raw["open_time"], errors="coerce"), unit="ms", utc=True)})
    for column in ["open", "high", "low", "close", "volume", "quote_volume", "trades", "taker_base", "taker_quote"]:
        out[column] = pd.to_numeric(raw[column], errors="coerce")
    return out.dropna(subset=["timestamp", "open", "high", "low", "close", "volume", "quote_volume", "taker_base", "taker_quote"])


def _clean_and_fill(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    out = out.loc[out["timestamp"].notna()].copy()
    out = out.drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
    full_index = pd.date_range(START_MONTH.start_time.tz_localize("UTC"), END_MONTH.end_time.tz_localize("UTC").floor("15min"), freq=BAR_DELTA)
    out = out.set_index("timestamp").reindex(full_index)
    filled = out["close"].isna()
    previous_close = out["close"].ffill()
    for column in ["open", "high", "low", "close"]:
        out[column] = out[column].fillna(previous_close)
    for column in ["volume", "quote_volume", "trades", "taker_base", "taker_quote"]:
        out[column] = out[column].fillna(0.0)
    out["calendar_filled"] = filled.to_numpy(bool)
    out = out.reset_index().rename(columns={"index": "timestamp"})
    if out[["open", "high", "low", "close"]].isna().any().any():
        raise RuntimeError("Calendar fill left missing OHLC values.")
    return out


def _quality(frame: pd.DataFrame, from_cache: bool) -> dict[str, Any]:
    timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    diffs = timestamp.diff().dropna()
    return {
        "from_cache": from_cache,
        "rows": int(len(frame)),
        "duplicate_timestamp_rows": int(timestamp.duplicated().sum()),
        "non_15m_gap_rows": int((diffs != BAR_DELTA).sum()),
        "calendar_fill_rows": int(frame["calendar_filled"].sum()) if "calendar_filled" in frame else 0,
        "invalid_volume_rows": int((pd.to_numeric(frame["volume"], errors="coerce") < 0).sum()),
        "first_timestamp": timestamp.min().isoformat(),
        "last_timestamp": timestamp.max().isoformat(),
        "pass": bool(timestamp.duplicated().sum() == 0 and (diffs != BAR_DELTA).sum() == 0),
    }


def _parity_check_with_strategy_15(volume_frame: pd.DataFrame, ohlc_path: Path) -> dict[str, Any]:
    ohlc = pd.read_csv(ohlc_path, usecols=["timestamp", "close"])
    ohlc["timestamp"] = pd.to_datetime(ohlc["timestamp"], utc=True)
    left = volume_frame[["timestamp", "close"]].copy()
    merged = left.merge(ohlc, on="timestamp", how="outer", suffixes=("_volume", "_strategy15"), indicator=True)
    both = merged.loc[merged["_merge"] == "both"].copy()
    both["abs_close_diff"] = (both["close_volume"] - both["close_strategy15"]).abs()
    return {
        "strategy15_rows": int(len(ohlc)),
        "volume_rows": int(len(left)),
        "matched_rows": int(len(both)),
        "missing_from_strategy15": int((merged["_merge"] == "left_only").sum()),
        "missing_from_volume": int((merged["_merge"] == "right_only").sum()),
        "close_mismatch_rows": int((both["abs_close_diff"] > 1e-8).sum()),
        "max_abs_close_diff": float(both["abs_close_diff"].max()) if len(both) else None,
    }


class VolumeFeatures:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.open = pd.Series(frame["open"].astype(float).to_numpy())
        self.close = pd.Series(frame["close"].astype(float).to_numpy())
        self.volume = pd.Series(frame["volume"].astype(float).to_numpy())
        self.quote_volume = pd.Series(frame["quote_volume"].astype(float).to_numpy())
        self.taker_base = pd.Series(frame["taker_base"].astype(float).to_numpy())
        self.body_bps = (self.close - self.open) / self.open * 10_000.0
        self.taker_buy_ratio = self.taker_base / self.volume.replace(0.0, np.nan)
        self._vol_ratio: dict[int, pd.Series] = {}
        self._quote_ratio: dict[int, pd.Series] = {}

    def volume_ratio(self, window: int) -> pd.Series:
        if window not in self._vol_ratio:
            mean = self.volume.rolling(window, min_periods=window).mean().replace(0.0, np.nan)
            self._vol_ratio[window] = self.volume / mean
        return self._vol_ratio[window]

    def quote_volume_ratio(self, window: int) -> pd.Series:
        if window not in self._quote_ratio:
            mean = self.quote_volume.rolling(window, min_periods=window).mean().replace(0.0, np.nan)
            self._quote_ratio[window] = self.quote_volume / mean
        return self._quote_ratio[window]


def _market(frame: pd.DataFrame) -> dict[str, Any]:
    raw_return = np.log(frame["close"].astype(float)).diff().fillna(0.0).to_numpy(dtype=float)
    timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    return {
        "timestamp": timestamp,
        "open": frame["open"].to_numpy(dtype=float),
        "high": frame["high"].to_numpy(dtype=float),
        "low": frame["low"].to_numpy(dtype=float),
        "close": frame["close"].to_numpy(dtype=float),
        "raw_return": raw_return,
        "month": timestamp.dt.strftime("%Y-%m").to_numpy(),
    }


def _candidate_library() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    leverages = [1.0, 2.0, 4.0]
    for window in [96, 384, 1536]:
        for min_volume_ratio in [1.5, 2.0, 3.0]:
            for min_body_bps in [0, 10]:
                for leverage in leverages:
                    candidates.append(_candidate("volume_spike", "volume_spike_body_momentum", leverage, window=window, min_volume_ratio=min_volume_ratio, min_body_bps=min_body_bps))
                    candidates.append(_candidate("volume_spike", "volume_spike_body_reversal", leverage, window=window, min_volume_ratio=min_volume_ratio, min_body_bps=min_body_bps))
    for window in [96, 384, 1536]:
        for min_volume_ratio in [1.0, 1.5, 2.0]:
            for buy_ratio in [0.55, 0.60, 0.65]:
                for leverage in leverages:
                    candidates.append(_candidate("taker_imbalance", "taker_imbalance_momentum", leverage, window=window, min_volume_ratio=min_volume_ratio, buy_ratio=buy_ratio))
                    candidates.append(_candidate("taker_imbalance", "taker_imbalance_reversal", leverage, window=window, min_volume_ratio=min_volume_ratio, buy_ratio=buy_ratio))
    for lookback in [4, 16, 64]:
        for min_volume_ratio in [1.5, 2.0]:
            for move_bps in [20, 50, 100]:
                for leverage in leverages:
                    candidates.append(_candidate("volume_confirmed_move", "volume_confirmed_momentum", leverage, lookback=lookback, min_volume_ratio=min_volume_ratio, move_bps=move_bps))
                    candidates.append(_candidate("volume_confirmed_move", "volume_confirmed_reversal", leverage, lookback=lookback, min_volume_ratio=min_volume_ratio, move_bps=move_bps))
    return candidates


def _candidate(family: str, rule: str, leverage: float, **params: Any) -> dict[str, Any]:
    suffix = "_".join(f"{key}{str(value).replace('.', 'p')}" for key, value in params.items())
    return {"candidate_id": f"{family}_{rule}_lev{str(leverage).replace('.', 'p')}_{suffix}", "family": family, "rule": rule, "leverage": leverage, **params}


def _target_for_candidate(candidate: dict[str, Any], f: VolumeFeatures) -> np.ndarray:
    rule = candidate["rule"]
    leverage = float(candidate["leverage"])
    side = pd.Series(0.0, index=f.close.index)

    if rule in {"volume_spike_body_momentum", "volume_spike_body_reversal"}:
        vol_ok = f.volume_ratio(int(candidate["window"])) >= float(candidate["min_volume_ratio"])
        body_ok = f.body_bps.abs() >= float(candidate["min_body_bps"])
        direction = np.sign(f.body_bps)
        if rule == "volume_spike_body_reversal":
            direction = -direction
        side = pd.Series(np.where(vol_ok & body_ok, direction, 0.0), index=f.close.index)
    elif rule in {"taker_imbalance_momentum", "taker_imbalance_reversal"}:
        ratio = f.taker_buy_ratio
        vol_ok = f.volume_ratio(int(candidate["window"])) >= float(candidate["min_volume_ratio"])
        buy_ratio = float(candidate["buy_ratio"])
        direction = pd.Series(np.where(ratio >= buy_ratio, 1.0, np.where(ratio <= 1.0 - buy_ratio, -1.0, 0.0)), index=f.close.index)
        if rule == "taker_imbalance_reversal":
            direction = -direction
        side = pd.Series(np.where(vol_ok, direction, 0.0), index=f.close.index)
    elif rule in {"volume_confirmed_momentum", "volume_confirmed_reversal"}:
        lookback = int(candidate["lookback"])
        move_bps = f.close.pct_change(lookback) * 10_000.0
        vol_ok = f.volume_ratio(max(96, lookback * 24)) >= float(candidate["min_volume_ratio"])
        direction = pd.Series(np.where(move_bps >= float(candidate["move_bps"]), 1.0, np.where(move_bps <= -float(candidate["move_bps"]), -1.0, 0.0)), index=f.close.index)
        if rule == "volume_confirmed_reversal":
            direction = -direction
        side = pd.Series(np.where(vol_ok, direction, 0.0), index=f.close.index)
    else:
        raise ValueError(f"Unknown rule: {rule}")

    return np.nan_to_num(side.to_numpy(dtype=float), nan=0.0) * leverage


def _candidate_results(
    candidates: list[dict[str, Any]], market: dict[str, Any], features: VolumeFeatures
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
            "verdict": "VOLUME_UPPER_BOUND_HAS_MONTHLY_PIECES",
            "promote_strategy": False,
            "reason": "看答案的成交量月度上限能过硬门槛，但它不能交易。",
            "next_step": "做严格逐月选择器，确认这些成交量月份能不能不用未来信息提前选中。",
        }
    return {
        "verdict": "VOLUME_UPPER_BOUND_FAILS",
        "promote_strategy": False,
        "reason": "即使每个月事后挑最好成交量候选，也过不了硬门槛。",
        "next_step": "不要把这批成交量小规则升级候选；再考虑资金费/持仓量前，应先确认是否值得补新数据源。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_oracle"]
    decision = summary["decision"]
    return f"""# 21号成交量上限测试

这不是策略，不能交易。它只看“如果事后知道每个月哪个成交量候选最好”，这批成交量候选理论上够不够。

## 口径

- 数据：`{summary["source"]["volume_klines"]}`
- 评估：`{probe16.EVAL_START_MONTH}` 到 `2026-05`
- 手续费：开平合计 `{probe16.ROUND_TRIP_COST * 100:.2f}%`
- 特征：volume、quote_volume、taker_base / volume
- 时序：每个候选只用已收盘K线，下一根K线才吃收益；但月度oracle会看答案，所以不能交易。

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
