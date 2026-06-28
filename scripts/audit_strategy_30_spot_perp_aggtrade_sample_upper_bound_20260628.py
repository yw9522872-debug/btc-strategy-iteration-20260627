from __future__ import annotations

import hashlib
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


STRATEGY_ID = "strategy_30_spot_perp_aggtrade_sample_upper_bound_20260628"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
FEATURES_15M = OUT_DIR / "spot_perp_aggtrade_features_15m_sample.csv"
DOWNLOAD_QUALITY = OUT_DIR / "download_quality.csv"
BASELINE_15_SUMMARY = ROOT / "artifacts" / "strategy_15_unified_data_baseline_20260627" / "summary.json"

SYMBOL = "BTCUSDT"
SAMPLE_MONTHS = ["2023-07", "2024-06", "2025-08", "2026-05"]
USER_AGENT = "strategy-30-spot-perp-aggtrade-sample/1.0"
CHUNKSIZE = 750_000

URLS = {
    "spot": "https://data.binance.vision/data/spot/monthly/aggTrades/{symbol}/{symbol}-aggTrades-{yyyy}-{mm}.zip",
    "futures": "https://data.binance.vision/data/futures/um/monthly/aggTrades/{symbol}/{symbol}-aggTrades-{yyyy}-{mm}.zip",
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    baseline = json.loads(BASELINE_15_SUMMARY.read_text(encoding="utf-8"))
    if not baseline["quality"]["pass"]:
        raise RuntimeError("Strategy 15 data baseline is not ready.")

    ohlc_path = ROOT / baseline["input_files"]["combined_ohlc"]
    market = probe16._load_market(ohlc_path)
    features, data_quality = _load_or_fetch_features(market)
    feature_set = FeatureSet(market, features)
    candidates = _candidate_library()
    candidate_monthly, candidate_scan = _candidate_results(candidates, market, feature_set)
    oracle_summary, oracle_monthly = _oracle_results(candidate_monthly)
    best_oracle = oracle_summary.iloc[0].to_dict()
    best_static = candidate_scan.iloc[0].to_dict()

    candidate_scan.to_csv(OUT_DIR / "candidate_scan.csv", index=False)
    candidate_monthly.to_csv(OUT_DIR / "candidate_monthly.csv", index=False)
    oracle_summary.to_csv(OUT_DIR / "oracle_summary.csv", index=False)
    oracle_monthly.to_csv(OUT_DIR / "oracle_monthly.csv", index=False)

    summary = {
        "status": "strategy_30_spot_perp_aggtrade_sample_upper_bound_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Small sample upper-bound test for free Binance spot-vs-USD-M futures aggTrades lead/lag features.",
        "sample_months": SAMPLE_MONTHS,
        "source": {
            "strategy_29_summary": "artifacts/strategy_29_free_raw_trade_coverage_audit_20260628/summary.json",
            "baseline_15_summary": _rel(BASELINE_15_SUMMARY),
            "combined_ohlc": _rel(ohlc_path),
            "features_15m": _rel(FEATURES_15M),
            "download_quality": _rel(DOWNLOAD_QUALITY),
            "raw_zip_retained": False,
            "raw_zip_note": "Downloaded monthly zip files are processed into 15m features and then deleted.",
        },
        "cost_model": {
            "cost_per_side": probe16.COST_PER_SIDE,
            "round_trip_open_close": probe16.ROUND_TRIP_COST,
        },
        "timing": {
            "signals_use_closed_15m_aggTrades": True,
            "position_participates_from_next_15m_bar": True,
            "leaky_oracle_tradeable": False,
            "sample_only_not_full_backtest": True,
        },
        "data_quality": data_quality,
        "candidate_grid": _candidate_grid_summary(candidates),
        "best_static_candidate": _json_ready(best_static),
        "oracle_summary": _json_ready(oracle_summary.to_dict("records")),
        "best_oracle": _json_ready(best_oracle),
        "decision": _decision(best_oracle),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "features_15m_sha256": _sha256(FEATURES_15M),
            "baseline_15_summary_sha256": _sha256(BASELINE_15_SUMMARY),
            "combined_ohlc_sha256": _sha256(ohlc_path),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "features_15m": _rel(FEATURES_15M),
            "download_quality": _rel(DOWNLOAD_QUALITY),
            "candidate_scan": _rel(OUT_DIR / "candidate_scan.csv"),
            "candidate_monthly": _rel(OUT_DIR / "candidate_monthly.csv"),
            "oracle_summary": _rel(OUT_DIR / "oracle_summary.csv"),
            "oracle_monthly": _rel(OUT_DIR / "oracle_monthly.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_or_fetch_features(market: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    if FEATURES_15M.exists() and DOWNLOAD_QUALITY.exists():
        features = pd.read_csv(FEATURES_15M)
        features["timestamp"] = pd.to_datetime(features["timestamp"], utc=True)
        quality = pd.read_csv(DOWNLOAD_QUALITY)
        return features, _data_quality(features, quality, from_cache=True)

    frames: list[pd.DataFrame] = []
    quality_rows: list[dict[str, Any]] = []
    for month in SAMPLE_MONTHS:
        month_index = pd.Series(market["timestamp"])[pd.Series(market["month"]).eq(month)].reset_index(drop=True)
        spot, spot_quality = _load_month("spot", month)
        futures, futures_quality = _load_month("futures", month)
        combined, combined_quality = _combine_month(month, month_index, spot, futures)
        frames.append(combined)
        quality_rows.extend([spot_quality, futures_quality, combined_quality])

    features = pd.concat(frames, ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    quality = pd.DataFrame(quality_rows)
    features.to_csv(FEATURES_15M, index=False)
    quality.to_csv(DOWNLOAD_QUALITY, index=False)
    return features, _data_quality(features, quality, from_cache=False)


def _load_month(kind: str, month: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    yyyy, mm = month.split("-")
    url = URLS[kind].format(symbol=SYMBOL, yyyy=yyyy, mm=mm)
    tmp = OUT_DIR / f"_tmp_{kind}_{month}.zip"
    print(f"downloading {kind} {month}", flush=True)
    size = _download(url, tmp)
    print(f"aggregating {kind} {month}", flush=True)
    try:
        frame, quality = _aggregate_zip(tmp)
    finally:
        if tmp.exists():
            tmp.unlink()
    quality.update({"kind": kind, "month": month, "url": url, "downloaded_bytes": size})
    return frame, quality


def _download(url: str, path: Path) -> int:
    if path.exists():
        path.unlink()
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            total = 0
            with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as handle:
                while True:
                    chunk = response.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    total += len(chunk)
            return total
        except Exception as exc:  # pragma: no cover - network reliability path
            last_error = exc
            if path.exists():
                path.unlink()
            time.sleep(2.0 + attempt)
    raise RuntimeError(f"Failed to download {url}: {last_error!r}")


def _aggregate_zip(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    parts: list[pd.DataFrame] = []
    raw_rows = 0
    parsed_rows = 0
    unit_counts: dict[str, int] = {}
    with zipfile.ZipFile(path) as zf:
        names = [name for name in zf.namelist() if name.endswith(".csv")]
        if not names:
            raise RuntimeError(f"No CSV found in {path}")
        with zf.open(names[0]) as handle:
            for chunk in pd.read_csv(handle, header=None, chunksize=CHUNKSIZE, low_memory=False):
                raw_rows += len(chunk)
                part, unit = _aggregate_chunk(chunk)
                if len(part):
                    parts.append(part)
                    parsed_rows += int(part["trades"].sum())
                    unit_counts[unit] = unit_counts.get(unit, 0) + len(part)

    if not parts:
        raise RuntimeError(f"No parsed aggTrades in {path}")
    frame = _combine_chunk_groups(pd.concat(parts, ignore_index=True))
    quality = {
        "raw_rows": raw_rows,
        "parsed_rows": parsed_rows,
        "aggregated_15m_rows": int(len(frame)),
        "first_trade_time": frame["first_time"].min().isoformat(),
        "last_trade_time": frame["last_time"].max().isoformat(),
        "timestamp_units_seen": ",".join(f"{unit}:{count}" for unit, count in sorted(unit_counts.items())),
    }
    return frame, quality


def _aggregate_chunk(raw: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    chunk = raw.iloc[:, :7].copy()
    chunk.columns = ["agg_id", "price", "qty", "first_id", "last_id", "trade_time", "is_buyer_maker"]
    price = pd.to_numeric(chunk["price"], errors="coerce")
    qty = pd.to_numeric(chunk["qty"], errors="coerce")
    trade_time = pd.to_numeric(chunk["trade_time"], errors="coerce")
    mask = price.notna() & qty.notna() & trade_time.notna()
    if not bool(mask.any()):
        return pd.DataFrame(), "unknown"

    price = price[mask].astype(float)
    qty = qty[mask].astype(float)
    trade_time = trade_time[mask].astype("int64")
    unit = "us" if int(trade_time.max()) > 100_000_000_000_000 else "ms"
    timestamp = pd.to_datetime(trade_time, unit=unit, utc=True, errors="coerce")
    buyer_maker = chunk.loc[mask, "is_buyer_maker"].astype(str).str.lower().isin(["true", "1"])
    quote = price * qty
    signed_quote = np.where(buyer_maker.to_numpy(), -quote.to_numpy(), quote.to_numpy())
    out = pd.DataFrame(
        {
            "trade_time": timestamp,
            "timestamp": timestamp.dt.floor("15min"),
            "price": price.to_numpy(),
            "quote": quote.to_numpy(),
            "signed_quote": signed_quote,
            "buy_quote": np.where(signed_quote > 0, quote.to_numpy(), 0.0),
            "sell_quote": np.where(signed_quote < 0, quote.to_numpy(), 0.0),
        }
    ).dropna(subset=["trade_time", "timestamp", "price", "quote"])

    grouped = (
        out.groupby("timestamp", as_index=False)
        .agg(
            first_time=("trade_time", "first"),
            last_time=("trade_time", "last"),
            open=("price", "first"),
            high=("price", "max"),
            low=("price", "min"),
            close=("price", "last"),
            quote=("quote", "sum"),
            signed_quote=("signed_quote", "sum"),
            buy_quote=("buy_quote", "sum"),
            sell_quote=("sell_quote", "sum"),
            trades=("price", "count"),
        )
    )
    return grouped, unit


def _combine_chunk_groups(parts: pd.DataFrame) -> pd.DataFrame:
    first_open = parts.sort_values(["timestamp", "first_time"]).drop_duplicates("timestamp", keep="first")
    last_close = parts.sort_values(["timestamp", "last_time"]).drop_duplicates("timestamp", keep="last")
    summed = (
        parts.groupby("timestamp", as_index=False)
        .agg(
            first_time=("first_time", "min"),
            last_time=("last_time", "max"),
            high=("high", "max"),
            low=("low", "min"),
            quote=("quote", "sum"),
            signed_quote=("signed_quote", "sum"),
            buy_quote=("buy_quote", "sum"),
            sell_quote=("sell_quote", "sum"),
            trades=("trades", "sum"),
        )
    )
    out = summed.merge(first_open[["timestamp", "open"]], on="timestamp", how="left")
    out = out.merge(last_close[["timestamp", "close"]], on="timestamp", how="left")
    return out.sort_values("timestamp").reset_index(drop=True)


def _combine_month(month: str, month_index: pd.Series, spot: pd.DataFrame, futures: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    base = pd.DataFrame({"timestamp": pd.to_datetime(month_index, utc=True)})
    merged = base.merge(_prefix(spot, "spot"), on="timestamp", how="left")
    merged = merged.merge(_prefix(futures, "futures"), on="timestamp", how="left")
    merged["month"] = month
    merged["valid"] = (
        merged["spot_close"].notna()
        & merged["futures_close"].notna()
        & merged["spot_quote"].fillna(0).gt(0)
        & merged["futures_quote"].fillna(0).gt(0)
    )

    for venue in ["spot", "futures"]:
        merged[f"{venue}_ret_bps"] = _log_bps(merged[f"{venue}_open"], merged[f"{venue}_close"])
        merged[f"{venue}_imbalance"] = merged[f"{venue}_signed_quote"] / merged[f"{venue}_quote"]
    merged["ret_gap_bps"] = merged["spot_ret_bps"] - merged["futures_ret_bps"]
    merged["imbalance_gap"] = merged["spot_imbalance"] - merged["futures_imbalance"]
    merged["basis_bps"] = _log_bps(merged["spot_close"], merged["futures_close"])
    merged = merged.fillna(
        {
            "spot_ret_bps": 0.0,
            "futures_ret_bps": 0.0,
            "spot_imbalance": 0.0,
            "futures_imbalance": 0.0,
            "ret_gap_bps": 0.0,
            "imbalance_gap": 0.0,
            "basis_bps": 0.0,
        }
    )
    quality = {
        "kind": "combined",
        "month": month,
        "url": "",
        "downloaded_bytes": 0,
        "raw_rows": 0,
        "parsed_rows": 0,
        "aggregated_15m_rows": int(len(merged)),
        "valid_15m_rows": int(merged["valid"].sum()),
        "missing_spot_15m_rows": int(merged["spot_close"].isna().sum()),
        "missing_futures_15m_rows": int(merged["futures_close"].isna().sum()),
        "first_trade_time": "",
        "last_trade_time": "",
        "timestamp_units_seen": "",
    }
    return merged, quality


def _prefix(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    return frame.rename(columns={column: f"{prefix}_{column}" for column in frame.columns if column != "timestamp"})


def _log_bps(start: pd.Series, end: pd.Series) -> pd.Series:
    start = pd.to_numeric(start, errors="coerce")
    end = pd.to_numeric(end, errors="coerce")
    return np.log(end / start).replace([np.inf, -np.inf], np.nan) * 10_000.0


class FeatureSet:
    def __init__(self, market: dict[str, Any], features: pd.DataFrame) -> None:
        base = pd.DataFrame({"timestamp": market["timestamp"], "month": market["month"]})
        joined = base.merge(features, on="timestamp", how="left", suffixes=("", "_feature"))
        self.valid = pd.Series(joined["valid"].eq(True).to_numpy())
        self.spot_ret_bps = pd.Series(joined["spot_ret_bps"].fillna(0).astype(float).to_numpy())
        self.ret_gap_bps = pd.Series(joined["ret_gap_bps"].fillna(0).astype(float).to_numpy())
        self.spot_imbalance = pd.Series(joined["spot_imbalance"].fillna(0).astype(float).to_numpy())
        self.imbalance_gap = pd.Series(joined["imbalance_gap"].fillna(0).astype(float).to_numpy())
        months = np.asarray(market["month"])
        next_month = np.empty(len(months), dtype=object)
        next_month[:-1] = months[1:]
        next_month[-1] = ""
        self.sample_month_last_bar = np.isin(months, SAMPLE_MONTHS) & (months != next_month)


def _candidate_library() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    leverages = [1.0, 2.0, 4.0]
    for move_bps in [5, 10, 20, 40]:
        for gap_bps in [0, 5, 10, 20]:
            for leverage in leverages:
                candidates.append(_candidate("return_lead", "return_gap_momentum", leverage, move_bps=move_bps, gap_bps=gap_bps))
                candidates.append(_candidate("return_lead", "return_gap_reversal", leverage, move_bps=move_bps, gap_bps=gap_bps))
    for imbalance in [0.05, 0.10, 0.20]:
        for gap in [0.0, 0.05, 0.10]:
            for leverage in leverages:
                candidates.append(_candidate("flow_lead", "flow_gap_momentum", leverage, imbalance=imbalance, gap=gap))
                candidates.append(_candidate("flow_lead", "flow_gap_reversal", leverage, imbalance=imbalance, gap=gap))
    for move_bps in [5, 10, 20]:
        for imbalance in [0.05, 0.10, 0.20]:
            for leverage in leverages:
                candidates.append(_candidate("return_flow_combo", "return_flow_momentum", leverage, move_bps=move_bps, imbalance=imbalance))
                candidates.append(_candidate("return_flow_combo", "return_flow_reversal", leverage, move_bps=move_bps, imbalance=imbalance))
    return candidates


def _candidate(family: str, rule: str, leverage: float, **params: Any) -> dict[str, Any]:
    suffix = "_".join(f"{key}{str(value).replace('.', 'p')}" for key, value in params.items())
    return {"candidate_id": f"{family}_{rule}_lev{str(leverage).replace('.', 'p')}_{suffix}", "family": family, "rule": rule, "leverage": leverage, **params}


def _target_for_candidate(candidate: dict[str, Any], f: FeatureSet) -> np.ndarray:
    rule = candidate["rule"]
    leverage = float(candidate["leverage"])
    side = pd.Series(0.0, index=f.valid.index)

    if rule in {"return_gap_momentum", "return_gap_reversal"}:
        direction = np.sign(f.spot_ret_bps)
        if rule == "return_gap_reversal":
            direction = -direction
        lead_ok = np.sign(f.ret_gap_bps) == np.sign(f.spot_ret_bps)
        mask = f.valid & (f.spot_ret_bps.abs() >= float(candidate["move_bps"])) & (f.ret_gap_bps.abs() >= float(candidate["gap_bps"])) & lead_ok
        side = pd.Series(np.where(mask, direction, 0.0), index=f.valid.index)
    elif rule in {"flow_gap_momentum", "flow_gap_reversal"}:
        direction = np.sign(f.spot_imbalance)
        if rule == "flow_gap_reversal":
            direction = -direction
        lead_ok = np.sign(f.imbalance_gap) == np.sign(f.spot_imbalance)
        mask = f.valid & (f.spot_imbalance.abs() >= float(candidate["imbalance"])) & (f.imbalance_gap.abs() >= float(candidate["gap"])) & lead_ok
        side = pd.Series(np.where(mask, direction, 0.0), index=f.valid.index)
    elif rule in {"return_flow_momentum", "return_flow_reversal"}:
        direction = np.sign(f.spot_ret_bps)
        if rule == "return_flow_reversal":
            direction = -direction
        same_side = np.sign(f.spot_imbalance) == np.sign(f.spot_ret_bps)
        lead_ok = np.sign(f.ret_gap_bps) == np.sign(f.spot_ret_bps)
        mask = f.valid & same_side & lead_ok & (f.spot_ret_bps.abs() >= float(candidate["move_bps"])) & (f.spot_imbalance.abs() >= float(candidate["imbalance"]))
        side = pd.Series(np.where(mask, direction, 0.0), index=f.valid.index)
    else:
        raise ValueError(f"Unknown rule: {rule}")

    target = np.nan_to_num(side.to_numpy(dtype=float), nan=0.0) * leverage
    target[f.sample_month_last_bar] = 0.0
    return target


def _candidate_results(candidates: list[dict[str, Any]], market: dict[str, Any], features: FeatureSet) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_frames: list[pd.DataFrame] = []
    scan_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        target = _target_for_candidate(candidate, features)
        equity = probe16._simulate_target(market, target)
        monthly = probe16._monthly_breakdown(equity)
        monthly = monthly.loc[monthly["month"].isin(SAMPLE_MONTHS)].copy()
        monthly.insert(0, "candidate_id", candidate["candidate_id"])
        monthly.insert(1, "family", candidate["family"])
        monthly.insert(2, "rule", candidate["rule"])
        monthly.insert(3, "leverage", candidate["leverage"])
        monthly_frames.append(monthly)
        scan_rows.append({**candidate, **_sample_summary(monthly)})
    candidate_monthly = pd.concat(monthly_frames, ignore_index=True)
    scan = pd.DataFrame(scan_rows).sort_values(
        ["losing_sample_months", "total_sample_return_pct", "min_monthly_return_pct", "orders"],
        ascending=[True, False, False, False],
    )
    return candidate_monthly, scan


def _oracle_results(candidate_monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    specs = [
        ("monthly_oracle_best_return", None, False),
        ("monthly_oracle_best_return_order10", None, True),
        ("return_lead_order10", "return_lead", True),
        ("flow_lead_order10", "flow_lead", True),
        ("return_flow_combo_order10", "return_flow_combo", True),
    ]
    rows: list[dict[str, Any]] = []
    monthly_frames: list[pd.DataFrame] = []
    for oracle_id, family, require_order_floor in specs:
        selected = _select_oracle_months(candidate_monthly, oracle_id, family, require_order_floor)
        rows.append(
            {
                "oracle_id": oracle_id,
                "family_filter": family or "all",
                "leaky_oracle": True,
                "requires_monthly_orders_ge_10_at_selection": require_order_floor,
                "months_without_order_floor_candidate": int(selected["no_order_floor_candidate"].sum()),
                **_sample_summary(selected),
            }
        )
        monthly_frames.append(selected)
    summary = pd.DataFrame(rows).sort_values(
        ["losing_sample_months", "months_without_order_floor_candidate", "total_sample_return_pct", "min_monthly_return_pct"],
        ascending=[True, True, False, False],
    )
    return summary, pd.concat(monthly_frames, ignore_index=True)


def _select_oracle_months(candidate_monthly: pd.DataFrame, oracle_id: str, family: str | None, require_order_floor: bool) -> pd.DataFrame:
    subset = candidate_monthly.copy()
    if family:
        subset = subset.loc[subset["family"] == family].copy()
    selected_rows: list[dict[str, Any]] = []
    for month, group in subset.groupby("month", sort=True):
        pool = group
        no_order_floor_candidate = False
        if require_order_floor:
            order_pool = group.loc[group["orders"] >= probe16.REQUIRED_MIN_MONTHLY_ORDERS]
            if order_pool.empty:
                no_order_floor_candidate = True
            else:
                pool = order_pool
        best = pool.sort_values(["return_pct", "orders", "turnover"], ascending=[False, False, True]).iloc[0].to_dict()
        best["oracle_id"] = oracle_id
        best["no_order_floor_candidate"] = no_order_floor_candidate
        selected_rows.append(best)
    return pd.DataFrame(selected_rows)


def _sample_summary(monthly: pd.DataFrame) -> dict[str, Any]:
    return {
        "sample_month_count": int(len(monthly)),
        "non_positive_months": monthly.loc[monthly["return_pct"] <= 0, "month"].tolist(),
        "total_sample_return_pct": float((np.exp(float(monthly["log_return"].sum())) - 1.0) * 100.0),
        "losing_sample_months": int((monthly["return_pct"] <= 0).sum()),
        "min_monthly_return_pct": float(monthly["return_pct"].min()),
        "max_monthly_return_pct": float(monthly["return_pct"].max()),
        "min_monthly_orders": int(monthly["orders"].min()),
        "orders": int(monthly["orders"].sum()),
        "turnover": float(monthly["turnover"].sum()),
        "cost_log": float(monthly["cost_log"].sum()),
        "worst_month_drawdown_pct": float(monthly["max_drawdown_pct"].min()),
        "selected_candidate_count": int(monthly["candidate_id"].nunique()),
    }


def _candidate_grid_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    meta = pd.DataFrame(candidates)
    return {
        "candidate_count": int(len(meta)),
        "families": sorted(meta["family"].unique().tolist()),
        "rules": sorted(meta["rule"].unique().tolist()),
        "leverages": sorted(float(x) for x in meta["leverage"].unique()),
    }


def _data_quality(features: pd.DataFrame, quality: pd.DataFrame, from_cache: bool) -> dict[str, Any]:
    ts = pd.to_datetime(features["timestamp"], utc=True)
    combined = quality.loc[quality["kind"] == "combined"].copy()
    raw = quality.loc[quality["kind"].isin(["spot", "futures"])].copy()
    return {
        "from_cache": from_cache,
        "feature_rows": int(len(features)),
        "sample_months": SAMPLE_MONTHS,
        "first_timestamp": ts.min().isoformat(),
        "last_timestamp": ts.max().isoformat(),
        "duplicate_feature_timestamps": int(ts.duplicated().sum()),
        "valid_15m_rows": int(features["valid"].sum()),
        "invalid_15m_rows": int((~features["valid"].astype(bool)).sum()),
        "missing_spot_15m_rows": int(combined["missing_spot_15m_rows"].sum()) if "missing_spot_15m_rows" in combined else 0,
        "missing_futures_15m_rows": int(combined["missing_futures_15m_rows"].sum()) if "missing_futures_15m_rows" in combined else 0,
        "downloaded_raw_zip_gb": round(float(raw["downloaded_bytes"].sum()) / 1024**3, 3) if "downloaded_bytes" in raw else 0.0,
        "raw_rows": int(raw["raw_rows"].sum()) if "raw_rows" in raw else 0,
        "parsed_rows": int(raw["parsed_rows"].sum()) if "parsed_rows" in raw else 0,
        "pass": bool(ts.duplicated().sum() == 0 and int((~features["valid"].astype(bool)).sum()) == 0),
    }


def _decision(best_oracle: dict[str, Any]) -> dict[str, Any]:
    ok = (
        int(best_oracle["losing_sample_months"]) == 0
        and int(best_oracle["months_without_order_floor_candidate"]) == 0
        and int(best_oracle["min_monthly_orders"]) >= probe16.REQUIRED_MIN_MONTHLY_ORDERS
    )
    if ok:
        return {
            "verdict": "SPOT_PERP_AGGTRADE_SAMPLE_UPPER_BOUND_HAS_SIGNAL",
            "promote_strategy": False,
            "reason": "四个样本月里，看答案的 aggTrades 现货-合约错位候选能做到每个样本月盈利且每月至少10单；这仍然不能交易。",
            "next_step": "做30B，扩到2020-01到2026-05全样本，再看严格选择器是否能提前选中这些候选。",
        }
    return {
        "verdict": "SPOT_PERP_AGGTRADE_SAMPLE_UPPER_BOUND_FAILS",
        "promote_strategy": False,
        "reason": "即使只看四个关键样本月并允许每个月事后挑最好候选，仍不能稳定满足盈利和每月至少10单。",
        "next_step": "停止这条免费aggTrades lead-lag路线，不再下载全量90GB。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_oracle"]
    static = summary["best_static_candidate"]
    decision = summary["decision"]
    return f"""# 30号 spot-perp aggTrades 样本上限测试

这不是策略，不能交易。它只是先拿四个样本月，测试免费 `aggTrades` 的“现货-永续成交流错位”有没有明显希望。

## 样本

- 月份：{", ".join(SAMPLE_MONTHS)}
- 数据：Binance 免费公开 spot `aggTrades` + USD-M futures `aggTrades`
- 收益口径：15号 USD-M futures 15分钟K线
- 手续费：开平合计 `{probe16.ROUND_TRIP_COST * 100:.2f}%`
- 时序：用已收盘15分钟成交流，下一根15分钟K线才吃收益
- 注意：月度 oracle 是“看答案”，只能测上限，不能交易

## 数据质量

- 聚合特征行数：`{summary["data_quality"]["feature_rows"]}`
- 无效15分钟行数：`{summary["data_quality"]["invalid_15m_rows"]}`
- 下载压缩包：约 `{summary["data_quality"]["downloaded_raw_zip_gb"]}` GB，已处理后删除

## 最好静态候选

- 候选：`{static["candidate_id"]}`
- 样本总收益：`{static["total_sample_return_pct"]:.2f}%`
- 不盈利样本月：`{", ".join(static["non_positive_months"])}`
- 最少月交易：`{static["min_monthly_orders"]}`

## 最好看答案上限

- oracle：`{best["oracle_id"]}`
- 样本总收益：`{best["total_sample_return_pct"]:.2f}%`
- 不盈利样本月：`{", ".join(best["non_positive_months"])}`
- 最差月：`{best["min_monthly_return_pct"]:.2f}%`
- 最少月交易：`{best["min_monthly_orders"]}`
- 找不到10单候选的月份数：`{best["months_without_order_floor_candidate"]}`

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
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if pd.isna(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
