from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ID = "strategy_15_unified_data_baseline_20260627"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID

SOURCE_14_DIR = ROOT / "artifacts" / "strategy_14_pre2023_expanding_crowding_stress_audit_20260627"
COMBINED_OHLC = SOURCE_14_DIR / "btc_15m_2020_2026_05_combined_ohlc.csv"
SUMMARY_14 = SOURCE_14_DIR / "summary.json"

BAR_DELTA = pd.Timedelta(minutes=15)
REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "calendar_filled", "source"]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_summary = json.loads(SUMMARY_14.read_text(encoding="utf-8"))
    frame = _load_ohlc()

    month_coverage = _month_coverage(frame)
    source_profile = _source_profile(frame)
    quality = _quality(frame, month_coverage)

    summary = {
        "status": "strategy_15_unified_data_baseline_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Lock in the data baseline to use before trying a new strategy family. This audits the Strategy 14 combined USD-M futures OHLC file; it does not backtest returns.",
        "input_files": {
            "strategy_14_summary": _rel(SUMMARY_14),
            "combined_ohlc": _rel(COMBINED_OHLC),
        },
        "accepted_baseline": {
            "instrument": "BTCUSDT",
            "bar_interval": "15m",
            "data_kind": "Binance USD-M futures public klines plus local event_entry_fullscan tail",
            "start_timestamp": frame["timestamp"].iloc[0].isoformat(),
            "end_timestamp": frame["timestamp"].iloc[-1].isoformat(),
            "rows": int(len(frame)),
            "months": int(len(month_coverage)),
            "source_rows": {
                str(row.source): int(row.rows)
                for row in source_profile.groupby("source", as_index=False)["rows"].sum().itertuples()
            },
        },
        "quality": quality,
        "inherited_from_strategy_14": {
            "public_archive_kind": source_summary["data"]["public_archive_kind"],
            "public_archive_years": source_summary["data"]["public_archive_years"],
            "event_tail_source": source_summary["data"]["event_tail_source"],
            "parity_2024": source_summary["data_quality"]["parity_2024"],
            "strategy_14_decision": source_summary["decision"],
        },
        "decision": {
            "verdict": "DATA_BASELINE_READY" if quality["pass"] else "DATA_BASELINE_NEEDS_FIX",
            "use_for_next_new_strategy_family": bool(quality["pass"]),
            "do_not_continue_ret_state_64_100_family": True,
            "next_step": "Build Strategy 16 as a new-family feature probe on this baseline, or first extend the same baseline beyond 2026-05.",
        },
        "hashes": {
            "combined_ohlc_sha256": _sha256(COMBINED_OHLC),
            "strategy_14_summary_sha256": _sha256(SUMMARY_14),
            "script_sha256": _sha256(Path(__file__)),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "month_coverage": _rel(OUT_DIR / "month_coverage.csv"),
            "source_profile": _rel(OUT_DIR / "source_profile.csv"),
        },
    }

    month_coverage.to_csv(OUT_DIR / "month_coverage.csv", index=False)
    source_profile.to_csv(OUT_DIR / "source_profile.csv", index=False)
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_ohlc() -> pd.DataFrame:
    missing = [str(path) for path in [COMBINED_OHLC, SUMMARY_14] if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing Strategy 14 baseline files: {missing}")

    frame = pd.read_csv(COMBINED_OHLC)
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in frame.columns]
    if missing_columns:
        raise ValueError(f"Missing required OHLC columns: {missing_columns}")

    frame = frame[REQUIRED_COLUMNS].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    for col in ["open", "high", "low", "close"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["calendar_filled"] = frame["calendar_filled"].astype(str).str.lower().eq("true")
    return frame


def _month_coverage(frame: pd.DataFrame) -> pd.DataFrame:
    tmp = frame.copy()
    tmp["month"] = tmp["timestamp"].dt.strftime("%Y-%m")
    rows: list[dict[str, Any]] = []
    for month, group in tmp.groupby("month", sort=True):
        start = pd.Timestamp(f"{month}-01T00:00:00Z")
        expected_rows = int(((start + pd.offsets.MonthBegin(1)) - start) / BAR_DELTA)
        sources = sorted(group["source"].dropna().unique())
        rows.append(
            {
                "month": month,
                "rows": int(len(group)),
                "expected_rows": expected_rows,
                "complete": bool(len(group) == expected_rows),
                "first_timestamp": group["timestamp"].iloc[0].isoformat(),
                "last_timestamp": group["timestamp"].iloc[-1].isoformat(),
                "calendar_fill_rows": int(group["calendar_filled"].sum()),
                "source": sources[0] if len(sources) == 1 else "mixed",
            }
        )
    return pd.DataFrame(rows)


def _source_profile(frame: pd.DataFrame) -> pd.DataFrame:
    tmp = frame.copy()
    tmp["year"] = tmp["timestamp"].dt.year
    grouped = tmp.groupby(["source", "year"], as_index=False).agg(
        rows=("timestamp", "size"),
        first_timestamp=("timestamp", "min"),
        last_timestamp=("timestamp", "max"),
        calendar_fill_rows=("calendar_filled", "sum"),
    )
    grouped["first_timestamp"] = grouped["first_timestamp"].map(lambda x: x.isoformat())
    grouped["last_timestamp"] = grouped["last_timestamp"].map(lambda x: x.isoformat())
    grouped["calendar_fill_rows"] = grouped["calendar_fill_rows"].astype(int)
    return grouped


def _quality(frame: pd.DataFrame, month_coverage: pd.DataFrame) -> dict[str, Any]:
    diffs = frame["timestamp"].diff().dropna()
    bad_ohlc = (
        frame[["open", "high", "low", "close"]].isna().any(axis=1)
        | (frame[["open", "high", "low", "close"]] <= 0).any(axis=1)
        | (frame["high"] < frame[["open", "low", "close"]].max(axis=1))
        | (frame["low"] > frame[["open", "high", "close"]].min(axis=1))
    )
    checks = {
        "required_columns": REQUIRED_COLUMNS,
        "missing_required_columns": [],
        "duplicate_timestamp_rows": int(frame["timestamp"].duplicated().sum()),
        "non_15m_gap_rows": int((diffs != BAR_DELTA).sum()),
        "invalid_ohlc_rows": int(bad_ohlc.sum()),
        "calendar_fill_rows": int(frame["calendar_filled"].sum()),
        "incomplete_months": int((~month_coverage["complete"]).sum()),
        "missing_months": _missing_months(month_coverage["month"].tolist()),
    }
    checks["pass"] = (
        checks["duplicate_timestamp_rows"] == 0
        and checks["non_15m_gap_rows"] == 0
        and checks["invalid_ohlc_rows"] == 0
        and checks["incomplete_months"] == 0
        and not checks["missing_months"]
    )
    return checks


def _missing_months(months: list[str]) -> list[str]:
    if not months:
        return []
    start = pd.Period(months[0], freq="M")
    end = pd.Period(months[-1], freq="M")
    present = set(months)
    return [str(period) for period in pd.period_range(start, end, freq="M") if str(period) not in present]


def _render_report(summary: dict[str, Any]) -> str:
    baseline = summary["accepted_baseline"]
    quality = summary["quality"]
    parity = summary["inherited_from_strategy_14"]["parity_2024"]
    decision = summary["decision"]
    return f"""# 15号统一数据底座体检

这不是新策略，也不是收益回测。它只确认以后换新策略族时，先从哪份 K 线数据开始。

## 数据底座

- 文件：`{summary["input_files"]["combined_ohlc"]}`
- 数据：`{baseline["data_kind"]}`
- 时间：`{baseline["start_timestamp"]}` 到 `{baseline["end_timestamp"]}`
- 行数：`{baseline["rows"]}`
- 月份数：`{baseline["months"]}`

## 质量检查

- 重复时间戳：`{quality["duplicate_timestamp_rows"]}`
- 非 15分钟间隔：`{quality["non_15m_gap_rows"]}`
- OHLC 异常行：`{quality["invalid_ohlc_rows"]}`
- 补齐K线行：`{quality["calendar_fill_rows"]}`
- 不完整月份：`{quality["incomplete_months"]}`
- 缺失月份：`{len(quality["missing_months"])}`

## 继承 14号的重要结论

- 2024 public futures 行数：`{parity["public_2024_rows"]}`
- 2024 event 行数：`{parity["event_2024_rows"]}`
- close 不匹配行数：`{parity["close_mismatch_rows"]}`
- 14号策略族判断：`{summary["inherited_from_strategy_14"]["strategy_14_decision"]["verdict"]}`

## 判断

`{decision["verdict"]}`

下一步不要继续修 `ret_state 64/100` 老家族。更合适的是在这份统一 futures 数据底座上，另起 16号做新策略族或新特征探针。
"""


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_ready(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_ready(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_ready(v) for v in obj]
    if isinstance(obj, tuple):
        return [_json_ready(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
