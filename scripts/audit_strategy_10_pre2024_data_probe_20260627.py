from __future__ import annotations

import hashlib
import io
import json
import math
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import search_monthly_profit_lock_20260627 as lock_search


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_10_pre2024_data_probe_20260627"
SYMBOL = "BTCUSDT"
INTERVAL = "15m"
START = pd.Timestamp("2023-01-01T00:00:00Z")
END = pd.Timestamp("2024-01-01T00:00:00Z")
BAR_DELTA = pd.Timedelta(minutes=15)

REQUIRED_FEATURE_COLUMNS = {
    "timestamp",
    "open",
    "high",
    "low",
    "close",
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    official_ohlc, source = _fetch_2023_ohlc()
    gap_probe = _probe_rest_for_missing_bars(official_ohlc)
    ohlc = _fill_calendar_gaps(official_ohlc)
    features = _add_probe_features(ohlc)
    checks = _quality_checks(official_ohlc, ohlc, features)
    month_coverage = _month_coverage(ohlc)

    official_ohlc_path = OUT_DIR / "btc_15m_2023_official_ohlc.csv"
    ohlc_path = OUT_DIR / "btc_15m_2023_ohlc.csv"
    feature_path = OUT_DIR / "btc_15m_2023_feature_probe.csv"
    month_path = OUT_DIR / "month_coverage.csv"
    gap_probe_path = OUT_DIR / "official_gap_rest_probe.csv"
    official_ohlc.to_csv(official_ohlc_path, index=False)
    ohlc.to_csv(ohlc_path, index=False)
    features.to_csv(feature_path, index=False)
    month_coverage.to_csv(month_path, index=False)
    gap_probe.to_csv(gap_probe_path, index=False)

    summary = {
        "status": "strategy_10_pre2024_data_probe_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "data_only": True,
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "requested_start": START.isoformat(),
        "requested_end_exclusive": END.isoformat(),
        "source": source,
        "no_api_keys_used": True,
        "does_not_overwrite": [
            "artifacts/strategy_freeze_monthly_profit_lock_20260627",
            "artifacts/strategy_1f_selective_runner_20260627",
            "artifacts/strategy_1g_cap7_selective_runner_20260627",
            "artifacts/strategy_2c_lock_cap_20260627",
            "artifacts/strategy_3_trend_coverage_20260627",
            "artifacts/strategy_4_entry_confirm_20260627",
        ],
        "quality_checks": checks,
        "rest_gap_probe": _gap_probe_summary(gap_probe),
        "month_count": int(len(month_coverage)),
        "ready_for_strategy_11_walkforward": bool(checks["ready_for_walkforward"]),
        "next_step": "Use this independent 2023 feature probe to build Strategy 11 true 2024 walk-forward. Do not reuse 2025+ selected controls on 2024.",
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "official_ohlc_sha256": _sha256(official_ohlc_path),
            "ohlc_sha256": _sha256(ohlc_path),
            "feature_probe_sha256": _sha256(feature_path),
        },
        "files": {
            "official_ohlc": _rel(official_ohlc_path),
            "ohlc": _rel(ohlc_path),
            "feature_probe": _rel(feature_path),
            "month_coverage": _rel(month_path),
            "official_gap_rest_probe": _rel(gap_probe_path),
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _fetch_2023_ohlc() -> tuple[pd.DataFrame, dict[str, Any]]:
    archive = _fetch_monthly_archive()
    if not archive.empty:
        return archive, {
            "kind": "Binance public monthly kline archive",
            "base_url": "https://data.binance.vision/data/spot/monthly/klines",
            "months": [f"2023-{month:02d}" for month in range(1, 13)],
        }

    api = _fetch_bounded_api()
    if not api.empty:
        return api, {
            "kind": "Binance public REST klines fallback",
            "endpoints": [
                "https://api.binance.com/api/v3/klines",
                "https://data-api.binance.vision/api/v3/klines",
            ],
        }
    raise RuntimeError("Could not fetch 2023 public Binance klines from archive or REST fallback.")


def _fetch_monthly_archive() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    last_error = None
    for month in range(1, 13):
        url = (
            "https://data.binance.vision/data/spot/monthly/klines/"
            f"{SYMBOL}/{INTERVAL}/{SYMBOL}-{INTERVAL}-2023-{month:02d}.zip"
        )
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                payload = response.read()
            with zipfile.ZipFile(io.BytesIO(payload)) as zf:
                names = [name for name in zf.namelist() if name.endswith(".csv")]
                if not names:
                    raise RuntimeError(f"No CSV found in {url}")
                with zf.open(names[0]) as handle:
                    raw = pd.read_csv(handle, header=None)
            frames.append(_klines_to_ohlc(raw))
        except Exception as exc:  # pragma: no cover - diagnostic path
            last_error = f"{url}: {exc!r}"
            frames.clear()
            break
    if not frames:
        if last_error:
            (OUT_DIR / "archive_fetch_error.txt").write_text(last_error, encoding="utf-8")
        return pd.DataFrame()
    return _clean_ohlc(pd.concat(frames, ignore_index=True))


def _fetch_bounded_api() -> pd.DataFrame:
    endpoints = [
        "https://api.binance.com/api/v3/klines",
        "https://data-api.binance.vision/api/v3/klines",
    ]
    start_ms = int(START.timestamp() * 1000)
    end_ms = int(END.timestamp() * 1000) - 1
    last_error = None
    for endpoint in endpoints:
        rows: list[list[Any]] = []
        cursor = start_ms
        try:
            while cursor < end_ms:
                query = urllib.parse.urlencode(
                    {
                        "symbol": SYMBOL,
                        "interval": INTERVAL,
                        "startTime": cursor,
                        "endTime": end_ms,
                        "limit": 1000,
                    }
                )
                with urllib.request.urlopen(f"{endpoint}?{query}", timeout=30) as response:
                    chunk = json.loads(response.read().decode("utf-8"))
                if not chunk:
                    break
                rows.extend(chunk)
                next_cursor = int(chunk[-1][0]) + int(BAR_DELTA.total_seconds() * 1000)
                if next_cursor <= cursor:
                    break
                cursor = next_cursor
                if len(chunk) < 1000:
                    break
            if rows:
                return _clean_ohlc(_klines_to_ohlc(pd.DataFrame(rows)))
        except Exception as exc:  # pragma: no cover - diagnostic path
            last_error = f"{endpoint}: {exc!r}"
            continue
    if last_error:
        (OUT_DIR / "api_fetch_error.txt").write_text(last_error, encoding="utf-8")
    return pd.DataFrame()


def _probe_rest_for_missing_bars(official_ohlc: pd.DataFrame) -> pd.DataFrame:
    full_index = pd.date_range(START, END - BAR_DELTA, freq=BAR_DELTA)
    official_index = pd.DatetimeIndex(pd.to_datetime(official_ohlc["timestamp"], utc=True))
    missing = full_index.difference(official_index)
    if missing.empty:
        return pd.DataFrame(columns=["timestamp", "api_binance_returned", "data_api_binance_vision_returned"])

    start_ms = int((missing.min() - BAR_DELTA).timestamp() * 1000)
    end_ms = int((missing.max() + BAR_DELTA).timestamp() * 1000)
    endpoint_results: dict[str, set[pd.Timestamp]] = {}
    endpoints = {
        "api_binance_returned": "https://api.binance.com/api/v3/klines",
        "data_api_binance_vision_returned": "https://data-api.binance.vision/api/v3/klines",
    }
    for label, endpoint in endpoints.items():
        returned: set[pd.Timestamp] = set()
        try:
            query = urllib.parse.urlencode(
                {
                    "symbol": SYMBOL,
                    "interval": INTERVAL,
                    "startTime": start_ms,
                    "endTime": end_ms,
                    "limit": 1000,
                }
            )
            with urllib.request.urlopen(f"{endpoint}?{query}", timeout=30) as response:
                chunk = json.loads(response.read().decode("utf-8"))
            returned = {pd.to_datetime(int(item[0]), unit="ms", utc=True) for item in chunk}
        except Exception as exc:  # pragma: no cover - diagnostic path
            (OUT_DIR / f"{label}_gap_probe_error.txt").write_text(repr(exc), encoding="utf-8")
        endpoint_results[label] = returned

    return pd.DataFrame(
        {
            "timestamp": [timestamp.isoformat() for timestamp in missing],
            "api_binance_returned": [timestamp in endpoint_results["api_binance_returned"] for timestamp in missing],
            "data_api_binance_vision_returned": [
                timestamp in endpoint_results["data_api_binance_vision_returned"] for timestamp in missing
            ],
        }
    )


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
    out = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(pd.to_numeric(raw["open_time"], errors="coerce"), unit="ms", utc=True),
            "open": pd.to_numeric(raw["open"], errors="coerce"),
            "high": pd.to_numeric(raw["high"], errors="coerce"),
            "low": pd.to_numeric(raw["low"], errors="coerce"),
            "close": pd.to_numeric(raw["close"], errors="coerce"),
        }
    )
    return out.dropna()


def _clean_ohlc(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    out = out.loc[out["timestamp"].notna()].copy()
    out = out.loc[(out["timestamp"] >= START) & (out["timestamp"] < END)].copy()
    out = out.drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
    return out


def _fill_calendar_gaps(frame: pd.DataFrame) -> pd.DataFrame:
    full_index = pd.date_range(START, END - BAR_DELTA, freq=BAR_DELTA)
    out = frame.set_index("timestamp").reindex(full_index)
    filled = out["close"].isna()
    previous_close = out["close"].ffill()
    for column in ["open", "high", "low", "close"]:
        out[column] = out[column].fillna(previous_close)
    out["calendar_filled"] = filled.to_numpy(bool)
    out = out.reset_index().rename(columns={"index": "timestamp"})
    if out[["open", "high", "low", "close"]].isna().any().any():
        raise RuntimeError("Calendar fill left missing OHLC values.")
    return out


def _add_probe_features(ohlc: pd.DataFrame) -> pd.DataFrame:
    out = ohlc.copy()
    close = out["close"].astype(float)
    high = out["high"].astype(float)
    low = out["low"].astype(float)
    prev_close = close.shift(1)

    for span in [20, 50, 60, 100]:
        out[f"_ema{span}"] = close.ewm(span=span, adjust=False, min_periods=span).mean()
    out["ema20"] = out["_ema20"]
    out["ema50"] = out["_ema50"]
    out["ema100"] = out["_ema100"]
    out["trend_ema_fast"] = out["_ema20"].fillna(0.0)
    out["trend_ema_slow"] = out["_ema100"].fillna(0.0)
    out["trend_close_ema_gap_bps_60"] = (close / out["_ema60"].replace(0, np.nan) - 1.0) * 10_000.0

    true_range = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = _wilder(true_range, 30)
    out["atr_30"] = atr
    out["natr_30"] = atr / close * 100.0

    out["trend_adx_30"] = _adx(high, low, close, 30)
    roll_high = high.rolling(30, min_periods=30).max()
    roll_low = low.rolling(30, min_periods=30).min()
    out["trend_donchian_pos_30"] = ((close - roll_low) / (roll_high - roll_low).replace(0, np.nan)).fillna(0.5)
    out["rsi14"] = _rsi(close, 14).fillna(50.0)

    middle = close.rolling(20, min_periods=20).mean()
    std = close.rolling(20, min_periods=20).std(ddof=0)
    out["bbu"] = middle + 2.0 * std
    out["bbl"] = middle - 2.0 * std
    out = out.drop(columns=[column for column in out.columns if column.startswith("_ema")])
    return out.replace([np.inf, -np.inf], np.nan)


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)
    up_move = high - prev_high
    down_move = prev_low - low
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index)
    true_range = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = _wilder(true_range, period)
    plus_di = 100.0 * _wilder(plus_dm, period) / atr.replace(0, np.nan)
    minus_di = 100.0 * _wilder(minus_dm, period) / atr.replace(0, np.nan)
    dx = (100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0.0)
    return _wilder(dx, period).fillna(0.0)


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = _wilder(gain, period)
    avg_loss = _wilder(loss, period)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.mask(avg_loss == 0.0, 100.0)


def _wilder(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def _quality_checks(official_ohlc: pd.DataFrame, ohlc: pd.DataFrame, features: pd.DataFrame) -> dict[str, Any]:
    expected_rows = int((END - START) / BAR_DELTA)
    timestamp = pd.to_datetime(ohlc["timestamp"], utc=True)
    official_timestamp = pd.to_datetime(official_ohlc["timestamp"], utc=True)
    official_gaps = official_timestamp.diff().dropna()
    duplicate_rows = int(timestamp.duplicated().sum())
    gaps = timestamp.diff().dropna()
    gap_rows = int((gaps != BAR_DELTA).sum())
    missing_required = sorted(REQUIRED_FEATURE_COLUMNS.difference(features.columns))
    non_null_counts = {column: int(features[column].notna().sum()) for column in sorted(REQUIRED_FEATURE_COLUMNS - {"timestamp"})}
    ready = (
        int(len(ohlc)) == expected_rows
        and duplicate_rows == 0
        and gap_rows == 0
        and not missing_required
        and timestamp.min() == START
        and timestamp.max() == END - BAR_DELTA
    )
    return {
        "row_count": int(len(ohlc)),
        "expected_row_count": expected_rows,
        "official_row_count": int(len(official_ohlc)),
        "official_missing_calendar_rows": int(expected_rows - len(official_ohlc)),
        "official_non_15m_gap_rows": int((official_gaps != BAR_DELTA).sum()),
        "calendar_fill_rows": int(ohlc.get("calendar_filled", pd.Series(dtype=bool)).sum()),
        "first_timestamp": timestamp.min().isoformat() if len(timestamp) else None,
        "last_timestamp": timestamp.max().isoformat() if len(timestamp) else None,
        "duplicate_rows": duplicate_rows,
        "non_15m_gap_rows": gap_rows,
        "missing_required_feature_columns": missing_required,
        "feature_non_null_counts": non_null_counts,
        "ready_for_walkforward": bool(ready),
        "note": "Official Binance data has a small 2023-03-24 maintenance gap. The calendar-filled file inserts flat bars from the prior close and marks them with calendar_filled=True. This is not a profitability test.",
    }


def _gap_probe_summary(gap_probe: pd.DataFrame) -> dict[str, Any]:
    if gap_probe.empty:
        return {"missing_timestamp_count": 0, "returned_by_any_rest_endpoint": 0}
    returned = gap_probe[["api_binance_returned", "data_api_binance_vision_returned"]].any(axis=1)
    return {
        "missing_timestamp_count": int(len(gap_probe)),
        "returned_by_any_rest_endpoint": int(returned.sum()),
        "timestamps": gap_probe["timestamp"].astype(str).tolist(),
    }


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
            }
        )
    return pd.DataFrame(rows)


def _render_report(summary: dict[str, Any]) -> str:
    checks = summary["quality_checks"]
    return "\n".join(
        [
            "# 10号 pre-2024 数据探针",
            "",
            "这不是新策略，只是把 2023 年 BTCUSDT 15m 公开K线补进一个独立目录，为下一步 2024 walk-forward 做准备。",
            "",
            "## 结论",
            "",
            f"- 数据范围：`{summary['requested_start']}` 到 `{summary['requested_end_exclusive']}`，右边不包含。",
            f"- 官方K线数量：`{checks['official_row_count']}`，比日历应有数量少 `{checks['official_missing_calendar_rows']}`。",
            f"- 补齐后K线数量：`{checks['row_count']}`，应有 `35040`。",
            f"- 日历补齐K线：`{checks['calendar_fill_rows']}`。",
            f"- REST 缺口复查返回数量：`{summary['rest_gap_probe']['returned_by_any_rest_endpoint']}`。",
            f"- 重复K线：`{checks['duplicate_rows']}`。",
            f"- 非15分钟间隔缺口：`{checks['non_15m_gap_rows']}`。",
            f"- 必要特征缺失列：`{checks['missing_required_feature_columns']}`。",
            f"- 能否作为 11号 walk-forward 的数据底座：`{checks['ready_for_walkforward']}`。",
            "",
            "## 说明",
            "",
            "- 这里只用 Binance 公开历史K线，不读取密钥，不下单，不启动 supervisor。",
            "- 官方数据在 2023-03-24 有 5 根15分钟K线缺口；补齐版用上一根收盘价补平，并用 `calendar_filled=True` 标记。",
            "- 这个探针本身不回测、不选参数、不评价收益。",
            "- 下一步应另起 11号，用 2023 数据提前训练/选择，再测 2024，避免用未来参数倒测过去。",
        ]
    ) + "\n"


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
