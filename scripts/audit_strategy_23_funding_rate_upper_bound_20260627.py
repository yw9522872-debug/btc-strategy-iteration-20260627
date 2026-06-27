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


STRATEGY_ID = "strategy_23_funding_rate_upper_bound_20260627"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
BASELINE_15_SUMMARY = ROOT / "artifacts" / "strategy_15_unified_data_baseline_20260627" / "summary.json"
FUNDING_RATES = OUT_DIR / "btcusdt_funding_rate_2020_2026_05.csv"

SYMBOL = "BTCUSDT"
PUBLIC_ARCHIVE_BASE_URL = "https://data.binance.vision/data/futures/um/monthly/fundingRate"
START_MONTH = pd.Period("2020-01", freq="M")
END_MONTH = pd.Period("2026-05", freq="M")
FUNDING_DELTA = pd.Timedelta(hours=8)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    baseline = json.loads(BASELINE_15_SUMMARY.read_text(encoding="utf-8"))
    if not baseline["quality"]["pass"]:
        raise RuntimeError("Strategy 15 data baseline is not ready.")

    ohlc_path = ROOT / baseline["input_files"]["combined_ohlc"]
    market = probe16._load_market(ohlc_path)
    funding, quality = _load_or_fetch_funding_rates()
    features = FundingFeatures(market, funding)
    candidates = _candidate_library()
    candidate_monthly, candidate_scan = _candidate_results(candidates, market, features)

    oracle_specs = [
        ("monthly_oracle_best_return", None, False),
        ("monthly_oracle_best_return_order10", None, True),
        ("funding_level_oracle_order10", "funding_level", True),
        ("funding_change_oracle_order10", "funding_change", True),
        ("funding_zscore_oracle_order10", "funding_zscore", True),
        ("funding_mean_oracle_order10", "funding_mean", True),
    ]
    oracle_rows: list[dict[str, Any]] = []
    oracle_monthly_frames: list[pd.DataFrame] = []
    oracle_yearly_frames: list[pd.DataFrame] = []
    for oracle_id, family, require_order_floor in oracle_specs:
        selected = upper17._select_oracle_months(candidate_monthly, oracle_id, family, require_order_floor)
        yearly = upper17._yearly_from_monthly(selected)
        oracle_rows.append(
            {
                "oracle_id": oracle_id,
                "family_filter": family or "all",
                "leaky_oracle": True,
                "requires_monthly_orders_ge_10_at_selection": require_order_floor,
                "months_without_order_floor_candidate": int(selected["no_order_floor_candidate"].sum()),
                **upper17._summary_from_monthly(selected, yearly),
            }
        )
        yearly.insert(0, "oracle_id", oracle_id)
        oracle_monthly_frames.append(selected)
        oracle_yearly_frames.append(yearly)

    oracle_summary = pd.DataFrame(oracle_rows).sort_values(
        ["hard_pass_complete_years", "losing_eval_months", "min_monthly_return_pct", "min_complete_year_return_pct"],
        ascending=[False, True, False, False],
    )
    best_oracle = oracle_summary.iloc[0].to_dict()
    summary = {
        "status": "strategy_23_funding_rate_upper_bound_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Measure a leaky monthly oracle upper bound for Binance USD-M futures funding-rate features.",
        "source": {
            "baseline_15_summary": _rel(BASELINE_15_SUMMARY),
            "combined_ohlc": baseline["input_files"]["combined_ohlc"],
            "public_archive_base_url": PUBLIC_ARCHIVE_BASE_URL,
            "download_months": f"{START_MONTH} to {END_MONTH}",
            "funding_rates": _rel(FUNDING_RATES),
            "open_interest_included": False,
            "open_interest_note": "Open-interest REST history was only verified for recent data in this run, so Strategy 23 keeps the test to funding-rate archive data.",
        },
        "data": {
            "eval_start_month": probe16.EVAL_START_MONTH,
            "eval_end_exclusive": probe16.EVAL_END_EXCLUSIVE,
            "complete_eval_years_for_annual_threshold": probe16.COMPLETE_EVAL_YEARS,
            "partial_eval_year_recorded_not_annual_threshold": probe16.PARTIAL_EVAL_YEAR,
            "quality": quality,
            "baseline_rows": int(len(market["timestamp"])),
            "baseline_start_timestamp": market["timestamp"].iloc[0].isoformat(),
            "baseline_end_timestamp": market["timestamp"].iloc[-1].isoformat(),
        },
        "cost_model": {"cost_per_side": probe16.COST_PER_SIDE, "round_trip_open_close": probe16.ROUND_TRIP_COST},
        "candidate_grid": probe16._candidate_grid_summary(candidates),
        "oracle_warning": {
            "strict_no_future": False,
            "tradeable": False,
            "reason": "The monthly oracle chooses the best funding-rate candidate after seeing the evaluated month.",
            "month_boundary_switching_cost_included": False,
            "per_candidate_signal_timing": "Each candidate uses latest funding data at or before bar t and participates from bar t+1.",
        },
        "static_hard_pass_count": int(candidate_scan["hard_pass_complete_years"].sum()),
        "best_static_candidate": _json_ready(candidate_scan.iloc[0].to_dict()),
        "oracle_summary": _json_ready(oracle_summary.to_dict("records")),
        "best_oracle": _json_ready(best_oracle),
        "decision": _decision(best_oracle),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "funding_rates_sha256": _sha256(FUNDING_RATES),
            "baseline_15_summary_sha256": _sha256(BASELINE_15_SUMMARY),
            "combined_ohlc_sha256": _sha256(ohlc_path),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "funding_rates": _rel(FUNDING_RATES),
            "candidate_scan": _rel(OUT_DIR / "candidate_scan.csv"),
            "oracle_summary": _rel(OUT_DIR / "oracle_summary.csv"),
            "oracle_monthly": _rel(OUT_DIR / "oracle_monthly.csv"),
            "oracle_yearly": _rel(OUT_DIR / "oracle_yearly.csv"),
        },
    }

    candidate_scan.to_csv(OUT_DIR / "candidate_scan.csv", index=False)
    oracle_summary.to_csv(OUT_DIR / "oracle_summary.csv", index=False)
    pd.concat(oracle_monthly_frames, ignore_index=True).to_csv(OUT_DIR / "oracle_monthly.csv", index=False)
    pd.concat(oracle_yearly_frames, ignore_index=True).to_csv(OUT_DIR / "oracle_yearly.csv", index=False)
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_or_fetch_funding_rates() -> tuple[pd.DataFrame, dict[str, Any]]:
    if FUNDING_RATES.exists():
        frame = pd.read_csv(FUNDING_RATES)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, format="mixed")
        return frame, _quality(frame, from_cache=True)

    frames: list[pd.DataFrame] = []
    for month in pd.period_range(START_MONTH, END_MONTH, freq="M"):
        url = f"{PUBLIC_ARCHIVE_BASE_URL}/{SYMBOL}/{SYMBOL}-fundingRate-{month.year}-{month.month:02d}.zip"
        frames.append(_fetch_month(url))
    frame = pd.concat(frames, ignore_index=True)
    frame = frame.drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
    frame.to_csv(FUNDING_RATES, index=False)
    return frame, _quality(frame, from_cache=False)


def _fetch_month(url: str) -> pd.DataFrame:
    payload = _download_url(url)
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = [name for name in zf.namelist() if name.endswith(".csv")]
        if not names:
            raise RuntimeError(f"No CSV found in {url}")
        with zf.open(names[0]) as handle:
            raw = pd.read_csv(handle)
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(pd.to_numeric(raw["calc_time"], errors="raise"), unit="ms", utc=True),
            "funding_interval_hours": pd.to_numeric(raw["funding_interval_hours"], errors="raise"),
            "funding_rate": pd.to_numeric(raw["last_funding_rate"], errors="raise"),
        }
    )


def _download_url(url: str) -> bytes:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "strategy-23-funding-rate-research/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(2.0 + attempt)
    raise RuntimeError(f"Failed to download {url}: {last_error!r}")


def _quality(frame: pd.DataFrame, from_cache: bool) -> dict[str, Any]:
    timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    rounded = timestamp.dt.floor("s")
    diffs = rounded.diff().dropna()
    return {
        "from_cache": from_cache,
        "rows": int(len(frame)),
        "duplicate_timestamp_rows": int(timestamp.duplicated().sum()),
        "non_8h_gap_rows_after_second_floor": int((diffs != FUNDING_DELTA).sum()),
        "invalid_interval_rows": int((pd.to_numeric(frame["funding_interval_hours"], errors="coerce") != 8).sum()),
        "missing_funding_rate_rows": int(pd.to_numeric(frame["funding_rate"], errors="coerce").isna().sum()),
        "first_timestamp": timestamp.min().isoformat(),
        "last_timestamp": timestamp.max().isoformat(),
        "pass": bool(timestamp.duplicated().sum() == 0 and (pd.to_numeric(frame["funding_rate"], errors="coerce").isna().sum() == 0)),
    }


class FundingFeatures:
    def __init__(self, market: dict[str, Any], funding: pd.DataFrame) -> None:
        events = funding.copy().sort_values("timestamp").reset_index(drop=True)
        events["funding_bps"] = events["funding_rate"] * 10_000.0
        for window in [3, 9, 21, 63]:
            events[f"mean_{window}"] = events["funding_bps"].rolling(window, min_periods=window).mean()
            events[f"change_{window}"] = events["funding_bps"] - events["funding_bps"].shift(window)
            std = events["funding_bps"].rolling(window, min_periods=window).std(ddof=0).replace(0.0, np.nan)
            events[f"z_{window}"] = (events["funding_bps"] - events[f"mean_{window}"]) / std
        bar_frame = pd.DataFrame({"timestamp": market["timestamp"]})
        merged = pd.merge_asof(
            bar_frame.sort_values("timestamp"),
            events.drop(columns=["funding_interval_hours", "funding_rate"]),
            on="timestamp",
            direction="backward",
        ).fillna(0.0)
        self.funding_bps = merged["funding_bps"].to_numpy(dtype=float)
        self.mean = {window: merged[f"mean_{window}"].to_numpy(dtype=float) for window in [3, 9, 21, 63]}
        self.change = {window: merged[f"change_{window}"].to_numpy(dtype=float) for window in [3, 9, 21, 63]}
        self.z = {window: merged[f"z_{window}"].to_numpy(dtype=float) for window in [3, 9, 21, 63]}


def _candidate_library() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    leverages = [1.0, 2.0, 4.0]
    for threshold_bps in [0.5, 1.0, 2.0, 5.0, 10.0]:
        for direction in ["contrarian", "momentum"]:
            for leverage in leverages:
                candidates.append(_candidate("funding_level", "funding_level", direction, leverage, threshold_bps=threshold_bps))
    for window in [3, 9, 21, 63]:
        for threshold_bps in [1.0, 2.0, 5.0]:
            for direction in ["contrarian", "momentum"]:
                for leverage in leverages:
                    candidates.append(_candidate("funding_change", "funding_change", direction, leverage, window=window, threshold_bps=threshold_bps))
        for z_threshold in [1.0, 1.5, 2.0]:
            for direction in ["contrarian", "momentum"]:
                for leverage in leverages:
                    candidates.append(_candidate("funding_zscore", "funding_zscore", direction, leverage, window=window, z_threshold=z_threshold))
        for threshold_bps in [0.5, 1.0, 2.0]:
            for direction in ["contrarian", "momentum"]:
                for leverage in leverages:
                    candidates.append(_candidate("funding_mean", "funding_mean", direction, leverage, window=window, threshold_bps=threshold_bps))
    return candidates


def _candidate(family: str, rule: str, direction: str, leverage: float, **params: Any) -> dict[str, Any]:
    suffix = "_".join(f"{key}{str(value).replace('.', 'p')}" for key, value in params.items())
    return {
        "candidate_id": f"{family}_{rule}_{direction}_lev{str(leverage).replace('.', 'p')}_{suffix}",
        "family": family,
        "rule": rule,
        "direction": direction,
        "leverage": leverage,
        **params,
    }


def _target_for_candidate(candidate: dict[str, Any], f: FundingFeatures) -> np.ndarray:
    rule = candidate["rule"]
    if rule == "funding_level":
        value = f.funding_bps
        active = np.abs(value) >= float(candidate["threshold_bps"])
    elif rule == "funding_change":
        value = f.change[int(candidate["window"])]
        active = np.abs(value) >= float(candidate["threshold_bps"])
    elif rule == "funding_zscore":
        value = f.z[int(candidate["window"])]
        active = np.abs(value) >= float(candidate["z_threshold"])
    elif rule == "funding_mean":
        value = f.mean[int(candidate["window"])]
        active = np.abs(value) >= float(candidate["threshold_bps"])
    else:
        raise ValueError(f"Unknown rule: {rule}")

    side = np.sign(value)
    if candidate["direction"] == "contrarian":
        side = -side
    elif candidate["direction"] != "momentum":
        raise ValueError(candidate["direction"])
    return np.nan_to_num(np.where(active, side, 0.0), nan=0.0) * float(candidate["leverage"])


def _candidate_results(
    candidates: list[dict[str, Any]], market: dict[str, Any], features: FundingFeatures
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
        monthly.insert(3, "direction", candidate["direction"])
        monthly.insert(4, "leverage", candidate["leverage"])
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
            "verdict": "FUNDING_RATE_UPPER_BOUND_HAS_MONTHLY_PIECES",
            "promote_strategy": False,
            "reason": "看答案的资金费率月度上限能过硬门槛，但它不能交易。",
            "next_step": "再做严格逐月选择器，确认这些月份能不能不用未来信息提前选中。",
        }
    return {
        "verdict": "FUNDING_RATE_UPPER_BOUND_FAILS",
        "promote_strategy": False,
        "reason": "即使每个月事后挑最好资金费率候选，也过不了硬门槛。",
        "next_step": "不要把这批资金费率小规则升级候选；若继续新数据源，应另起编号测持仓量或先调整硬目标。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_oracle"]
    decision = summary["decision"]
    return f"""# 23号资金费率上限测试

这不是策略，不能交易。它只看“如果事后知道每个月哪个资金费率候选最好”，这批资金费率候选理论上够不够。

## 口径

- 数据：`{summary["source"]["funding_rates"]}`
- 评估：`{probe16.EVAL_START_MONTH}` 到 `2026-05`
- 手续费：开平合计 `{probe16.ROUND_TRIP_COST * 100:.2f}%`
- 特征：资金费率水平、变化、均值、z-score
- 时序：每个候选只用当时已知资金费率，下一根15分钟K线才吃收益；但月度oracle会看答案，所以不能交易。

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
