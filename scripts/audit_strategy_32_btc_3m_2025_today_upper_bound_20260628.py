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


STRATEGY_ID = "strategy_32_btc_3m_2025_today_upper_bound_20260628"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
KLINES_PATH = OUT_DIR / "btc_3m_2025_to_20260628_public_klines.csv.gz"
DOWNLOAD_QUALITY = OUT_DIR / "download_quality.csv"

SYMBOL = "BTCUSDT"
INTERVAL = "3m"
BAR_DELTA = pd.Timedelta(minutes=3)
START_MONTH = pd.Period("2025-01", freq="M")
LAST_FULL_MONTH = pd.Period("2026-05", freq="M")
DAILY_START = pd.Timestamp("2026-06-01", tz="UTC")
TODAY_UTC = pd.Timestamp("2026-06-28", tz="UTC")
USER_AGENT = "strategy-32-btc-3m-2025-today/1.0"
MONTHLY_URL = "https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{yyyy}-{mm}.zip"
DAILY_URL = "https://data.binance.vision/data/futures/um/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{date}.zip"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    klines, data_quality = _load_or_fetch_klines()
    market = _market(klines)
    features = FeatureCache(klines)
    candidates = _candidate_library()
    candidate_monthly, candidate_scan = _candidate_results(candidates, market, features)
    oracle_summary, oracle_monthly, oracle_yearly = _oracle_results(candidate_monthly)
    best_oracle = oracle_summary.iloc[0].to_dict()
    best_order10 = oracle_summary.loc[oracle_summary["requires_monthly_orders_ge_10_at_selection"]].iloc[0].to_dict()

    candidate_monthly.to_csv(OUT_DIR / "candidate_monthly.csv", index=False)
    candidate_scan.to_csv(OUT_DIR / "candidate_scan.csv", index=False)
    oracle_summary.to_csv(OUT_DIR / "oracle_summary.csv", index=False)
    oracle_monthly.to_csv(OUT_DIR / "oracle_monthly.csv", index=False)
    oracle_yearly.to_csv(OUT_DIR / "oracle_yearly.csv", index=False)

    summary = {
        "status": "strategy_32_btc_3m_2025_today_upper_bound_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Test BTCUSDT 3m public USD-M futures klines from 2025-01 through the latest available 2026-06 public daily archive.",
        "source": {
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "monthly_archive": f"{START_MONTH} to {LAST_FULL_MONTH}",
            "daily_archive_attempted": f"{DAILY_START.date()} to {TODAY_UTC.date()}",
            "klines": _rel(KLINES_PATH),
            "download_quality": _rel(DOWNLOAD_QUALITY),
            "today_note": "Binance Vision daily archive for 2026-06-28 was not available at run time, so the usable end is the latest downloaded closed 3m bar.",
        },
        "data": data_quality,
        "cost_model": {
            "cost_per_side": probe16.COST_PER_SIDE,
            "round_trip_open_close": probe16.ROUND_TRIP_COST,
        },
        "timing": {
            "signals_use_closed_3m_bar_t": True,
            "position_participates_from_bar_t_plus_1": True,
            "monthly_oracle_is_leaky_and_not_tradeable": True,
            "strict_selector_run": False,
            "strict_selector_note": "This first pass only tests upper bounds for the user-requested 2025-to-today window.",
        },
        "candidate_grid": _candidate_grid_summary(candidates),
        "static_positive_all_months_count": int((candidate_scan["losing_eval_months"] == 0).sum()),
        "best_static_candidate": _json_ready(candidate_scan.iloc[0].to_dict()),
        "oracle_summary": _json_ready(oracle_summary.to_dict("records")),
        "best_oracle": _json_ready(best_oracle),
        "best_order10_oracle": _json_ready(best_order10),
        "decision": _decision(best_order10),
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
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_or_fetch_klines() -> tuple[pd.DataFrame, dict[str, Any]]:
    if KLINES_PATH.exists() and DOWNLOAD_QUALITY.exists():
        frame = pd.read_csv(KLINES_PATH)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        quality = pd.read_csv(DOWNLOAD_QUALITY)
        return frame, _data_quality(frame, quality, from_cache=True)

    frames: list[pd.DataFrame] = []
    quality_rows: list[dict[str, Any]] = []
    for month in pd.period_range(START_MONTH, LAST_FULL_MONTH, freq="M"):
        url = MONTHLY_URL.format(symbol=SYMBOL, interval=INTERVAL, yyyy=month.year, mm=f"{month.month:02d}")
        frame, row = _fetch_archive(url, "monthly", str(month))
        frames.append(frame)
        quality_rows.append(row)

    for day in pd.date_range(DAILY_START, TODAY_UTC, freq="D"):
        date = day.strftime("%Y-%m-%d")
        url = DAILY_URL.format(symbol=SYMBOL, interval=INTERVAL, date=date)
        try:
            frame, row = _fetch_archive(url, "daily", date)
            frames.append(frame)
            quality_rows.append(row)
        except urllib.error.HTTPError as exc:
            quality_rows.append({"kind": "daily", "period": date, "url": url, "ok": False, "http_status": int(exc.code), "rows": 0, "content_length": None, "error": str(exc)})
        time.sleep(0.02)

    frame = pd.concat(frames, ignore_index=True).drop_duplicates("timestamp", keep="last").sort_values("timestamp").reset_index(drop=True)
    frame = _calendar_fill(frame)
    quality = pd.DataFrame(quality_rows)
    frame.to_csv(KLINES_PATH, index=False)
    quality.to_csv(DOWNLOAD_QUALITY, index=False)
    return frame, _data_quality(frame, quality, from_cache=False)


def _fetch_archive(url: str, kind: str, period: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    payload = _download_url(url)
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = [name for name in zf.namelist() if name.endswith(".csv")]
        if not names:
            raise RuntimeError(f"No CSV found in {url}")
        with zf.open(names[0]) as handle:
            raw = pd.read_csv(handle, header=None)
    frame = _klines_to_frame(raw)
    return frame, {"kind": kind, "period": period, "url": url, "ok": True, "http_status": 200, "rows": int(len(frame)), "content_length": len(payload), "error": None}


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
    return out.dropna(subset=["timestamp", "open", "high", "low", "close", "volume", "quote_volume", "taker_base", "taker_quote"])


def _calendar_fill(frame: pd.DataFrame) -> pd.DataFrame:
    start = frame["timestamp"].min()
    end = frame["timestamp"].max()
    full_index = pd.date_range(start, end, freq=BAR_DELTA)
    out = frame.set_index("timestamp").reindex(full_index)
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


class FeatureCache:
    def __init__(self, frame: pd.DataFrame) -> None:
        self.open = pd.Series(frame["open"].astype(float).to_numpy())
        self.high = pd.Series(frame["high"].astype(float).to_numpy())
        self.low = pd.Series(frame["low"].astype(float).to_numpy())
        self.close = pd.Series(frame["close"].astype(float).to_numpy())
        self.volume = pd.Series(frame["volume"].astype(float).to_numpy())
        self.taker_base = pd.Series(frame["taker_base"].astype(float).to_numpy())
        self.body_bps = (self.close - self.open) / self.open * 10_000.0
        self.taker_buy_ratio = self.taker_base / self.volume.replace(0.0, np.nan)
        self._ema: dict[int, pd.Series] = {}
        self._mean: dict[int, pd.Series] = {}
        self._std: dict[int, pd.Series] = {}
        self._atr: dict[int, pd.Series] = {}
        self._rsi: dict[int, pd.Series] = {}
        self._volume_ratio: dict[int, pd.Series] = {}
        self._donchian_high: dict[int, pd.Series] = {}
        self._donchian_low: dict[int, pd.Series] = {}

    def ema(self, window: int) -> pd.Series:
        if window not in self._ema:
            self._ema[window] = self.close.ewm(span=window, adjust=False, min_periods=window).mean()
        return self._ema[window]

    def mean(self, window: int) -> pd.Series:
        if window not in self._mean:
            self._mean[window] = self.close.rolling(window, min_periods=window).mean()
        return self._mean[window]

    def std(self, window: int) -> pd.Series:
        if window not in self._std:
            self._std[window] = self.close.rolling(window, min_periods=window).std(ddof=0)
        return self._std[window]

    def atr(self, window: int) -> pd.Series:
        if window not in self._atr:
            prev_close = self.close.shift(1)
            true_range = pd.concat([self.high - self.low, (self.high - prev_close).abs(), (self.low - prev_close).abs()], axis=1).max(axis=1)
            self._atr[window] = true_range.rolling(window, min_periods=window).mean()
        return self._atr[window]

    def rsi(self, window: int) -> pd.Series:
        if window not in self._rsi:
            delta = self.close.diff()
            gain = delta.clip(lower=0).rolling(window, min_periods=window).mean()
            loss = (-delta.clip(upper=0)).rolling(window, min_periods=window).mean()
            rs = gain / loss.replace(0, np.nan)
            self._rsi[window] = (100.0 - 100.0 / (1.0 + rs)).fillna(50.0)
        return self._rsi[window]

    def volume_ratio(self, window: int) -> pd.Series:
        if window not in self._volume_ratio:
            mean = self.volume.rolling(window, min_periods=window).mean().replace(0.0, np.nan)
            self._volume_ratio[window] = self.volume / mean
        return self._volume_ratio[window]

    def donchian_high_prev(self, window: int) -> pd.Series:
        if window not in self._donchian_high:
            self._donchian_high[window] = self.high.rolling(window, min_periods=window).max().shift(1)
        return self._donchian_high[window]

    def donchian_low_prev(self, window: int) -> pd.Series:
        if window not in self._donchian_low:
            self._donchian_low[window] = self.low.rolling(window, min_periods=window).min().shift(1)
        return self._donchian_low[window]


def _candidate_library() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    leverages = [1.0, 2.0, 4.0]
    for lookback in [5, 20, 80, 320, 960]:
        for threshold_bps in [5, 20, 50, 100]:
            for leverage in leverages:
                candidates.append(_candidate("momentum", "price_momentum", leverage, lookback=lookback, threshold_bps=threshold_bps))
                candidates.append(_candidate("momentum", "price_reversal", leverage, lookback=lookback, threshold_bps=threshold_bps))
    for fast in [50, 200]:
        for slow in [800, 2400]:
            for gap_bps in [0, 20, 50]:
                for leverage in leverages:
                    candidates.append(_candidate("trend", "ema_trend", leverage, fast=fast, slow=slow, gap_bps=gap_bps))
    for lookback in [80, 320, 960]:
        for leverage in leverages:
            candidates.append(_candidate("trend", "donchian_trend", leverage, lookback=lookback))
    for window in [14, 56, 224]:
        for lower, upper in [(25, 75), (30, 70), (35, 65)]:
            for leverage in leverages:
                candidates.append(_candidate("mean_reversion", "rsi_reversion", leverage, window=window, lower=lower, upper=upper))
    for window in [160, 480, 1440]:
        for z in [1.5, 2.0, 2.5]:
            for leverage in leverages:
                candidates.append(_candidate("mean_reversion", "bollinger_reversion", leverage, window=window, z=z))
    for atr_window in [14, 56, 224]:
        for k in [0.5, 1.0, 1.5]:
            for natr_min_bps in [0, 10, 30]:
                for leverage in leverages:
                    candidates.append(_candidate("breakout", "atr_breakout", leverage, atr_window=atr_window, k=k, natr_min_bps=natr_min_bps))
    for window in [320, 1440]:
        for min_volume_ratio in [1.5, 2.5]:
            for min_body_bps in [5, 20]:
                for leverage in leverages:
                    candidates.append(_candidate("volume", "volume_body_momentum", leverage, window=window, min_volume_ratio=min_volume_ratio, min_body_bps=min_body_bps))
                    candidates.append(_candidate("volume", "volume_body_reversal", leverage, window=window, min_volume_ratio=min_volume_ratio, min_body_bps=min_body_bps))
    return candidates


def _candidate(family: str, rule: str, leverage: float, **params: Any) -> dict[str, Any]:
    suffix = "_".join(f"{key}{str(value).replace('.', 'p')}" for key, value in params.items())
    return {"candidate_id": f"{family}_{rule}_lev{str(leverage).replace('.', 'p')}_{suffix}", "family": family, "rule": rule, "leverage": leverage, **params}


def _target_for_candidate(candidate: dict[str, Any], f: FeatureCache) -> np.ndarray:
    rule = candidate["rule"]
    leverage = float(candidate["leverage"])
    side = pd.Series(0.0, index=f.close.index)
    if rule in {"price_momentum", "price_reversal"}:
        move_bps = np.log(f.close / f.close.shift(int(candidate["lookback"]))) * 10_000.0
        direction = np.sign(move_bps)
        if rule == "price_reversal":
            direction = -direction
        side = pd.Series(np.where(move_bps.abs() >= float(candidate["threshold_bps"]), direction, 0.0), index=f.close.index)
    elif rule == "ema_trend":
        fast = f.ema(int(candidate["fast"]))
        slow = f.ema(int(candidate["slow"]))
        gap = float(candidate["gap_bps"]) / 10_000.0
        side = pd.Series(np.where((fast > slow * (1 + gap)) & (f.close > slow), 1.0, np.where((fast < slow * (1 - gap)) & (f.close < slow), -1.0, 0.0)))
    elif rule == "donchian_trend":
        high = f.donchian_high_prev(int(candidate["lookback"])).to_numpy()
        low = f.donchian_low_prev(int(candidate["lookback"])).to_numpy()
        close = f.close.to_numpy()
        state = 0.0
        out = np.zeros(len(close))
        for idx, price in enumerate(close):
            if np.isfinite(high[idx]) and price > high[idx]:
                state = 1.0
            elif np.isfinite(low[idx]) and price < low[idx]:
                state = -1.0
            out[idx] = state
        side = pd.Series(out)
    elif rule == "rsi_reversion":
        rsi = f.rsi(int(candidate["window"]))
        side = pd.Series(np.where(rsi <= float(candidate["lower"]), 1.0, np.where(rsi >= float(candidate["upper"]), -1.0, 0.0)))
    elif rule == "bollinger_reversion":
        window = int(candidate["window"])
        z = (f.close - f.mean(window)) / f.std(window).replace(0, np.nan)
        side = pd.Series(np.where(z <= -float(candidate["z"]), 1.0, np.where(z >= float(candidate["z"]), -1.0, 0.0)))
    elif rule == "atr_breakout":
        atr = f.atr(int(candidate["atr_window"]))
        natr_bps = atr / f.close * 10_000.0
        move = f.close.diff()
        threshold = float(candidate["k"]) * atr
        ok = natr_bps >= float(candidate["natr_min_bps"])
        side = pd.Series(np.where((move > threshold) & ok, 1.0, np.where((move < -threshold) & ok, -1.0, 0.0)))
    elif rule in {"volume_body_momentum", "volume_body_reversal"}:
        ok = (f.volume_ratio(int(candidate["window"])) >= float(candidate["min_volume_ratio"])) & (f.body_bps.abs() >= float(candidate["min_body_bps"]))
        direction = np.sign(f.body_bps)
        if rule == "volume_body_reversal":
            direction = -direction
        side = pd.Series(np.where(ok, direction, 0.0), index=f.close.index)
    else:
        raise ValueError(rule)
    return np.nan_to_num(side.to_numpy(dtype=float), nan=0.0) * leverage


def _market(frame: pd.DataFrame) -> dict[str, Any]:
    timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    return {
        "timestamp": timestamp,
        "month": timestamp.dt.strftime("%Y-%m").to_numpy(),
        "close": frame["close"].to_numpy(dtype=float),
        "raw_return": np.log(frame["close"].astype(float)).diff().fillna(0.0).to_numpy(dtype=float),
    }


def _simulate_target(market: dict[str, Any], target: np.ndarray) -> pd.DataFrame:
    target = np.nan_to_num(target.astype(float), nan=0.0)
    active = np.roll(target, 1)
    active[0] = 0.0
    turnover = np.abs(target - np.r_[0.0, target[:-1]])
    orders = (turnover > 1e-12).astype(int)
    cost = turnover * probe16.COST_PER_SIDE
    strategy_lr = active * market["raw_return"] - cost
    equity = np.exp(np.cumsum(strategy_lr))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    if len(target) > 1 and not np.allclose(active[1:], target[:-1]):
        raise AssertionError("Timing check failed.")
    return pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "month": market["month"],
            "target_position": target,
            "active_position": active,
            "turnover": turnover,
            "order_count": orders,
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
    for candidate in candidates:
        target = _target_for_candidate(candidate, features)
        monthly = _monthly_breakdown(_simulate_target(market, target))
        monthly.insert(0, "candidate_id", candidate["candidate_id"])
        monthly.insert(1, "family", candidate["family"])
        monthly.insert(2, "rule", candidate["rule"])
        monthly.insert(3, "leverage", candidate["leverage"])
        monthly_frames.append(monthly)
        yearly = upper17._yearly_from_monthly(monthly)
        scan_rows.append({**candidate, **_summary_from_monthly_2025_today(monthly, yearly)})
    all_monthly = pd.concat(monthly_frames, ignore_index=True)
    scan = pd.DataFrame(scan_rows).sort_values(
        ["hard_pass_2025_to_latest", "losing_eval_months", "min_monthly_return_pct", "min_target_year_return_pct"],
        ascending=[False, True, False, False],
    )
    return all_monthly, scan


def _oracle_results(candidate_monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    specs = [
        ("monthly_oracle_best_return", None, False),
        ("monthly_oracle_best_return_order10", None, True),
        ("momentum_order10", "momentum", True),
        ("trend_order10", "trend", True),
        ("mean_reversion_order10", "mean_reversion", True),
        ("breakout_order10", "breakout", True),
        ("volume_order10", "volume", True),
    ]
    rows: list[dict[str, Any]] = []
    monthly_frames: list[pd.DataFrame] = []
    yearly_frames: list[pd.DataFrame] = []
    for oracle_id, family, require_order_floor in specs:
        selected = upper17._select_oracle_months(candidate_monthly, oracle_id, family, require_order_floor)
        yearly = upper17._yearly_from_monthly(selected)
        rows.append(
            {
                "oracle_id": oracle_id,
                "family_filter": family or "all",
                "leaky_oracle": True,
                "requires_monthly_orders_ge_10_at_selection": require_order_floor,
                "months_without_order_floor_candidate": int(selected["no_order_floor_candidate"].sum()),
                **_summary_from_monthly_2025_today(selected, yearly),
            }
        )
        if "oracle_id" not in selected.columns:
            selected.insert(0, "oracle_id", oracle_id)
        yearly.insert(0, "oracle_id", oracle_id)
        monthly_frames.append(selected)
        yearly_frames.append(yearly)
    summary = pd.DataFrame(rows).sort_values(
        ["hard_pass_2025_to_latest", "losing_eval_months", "min_monthly_return_pct", "min_target_year_return_pct"],
        ascending=[False, True, False, False],
    )
    return summary, pd.concat(monthly_frames, ignore_index=True), pd.concat(yearly_frames, ignore_index=True)


def _summary_from_monthly_2025_today(monthly: pd.DataFrame, yearly: pd.DataFrame) -> dict[str, Any]:
    yearly_by_year = {str(row.year): row for row in yearly.itertuples()}
    return_2025 = _year_return(yearly_by_year, "2025")
    return_2026 = _year_return(yearly_by_year, "2026")
    target_returns = [value for value in [return_2025, return_2026] if value is not None]
    min_target_year_return = min(target_returns) if target_returns else -999.0
    losing_eval_months = int((monthly["return_pct"] <= 0).sum())
    min_orders = int(monthly["orders"].min())
    hard_pass = bool(
        return_2025 is not None
        and return_2026 is not None
        and return_2025 > probe16.REQUIRED_RETURN_PCT
        and return_2026 > probe16.REQUIRED_RETURN_PCT
        and losing_eval_months == 0
        and min_orders >= probe16.REQUIRED_MIN_MONTHLY_ORDERS
    )
    return {
        "hard_pass_2025_to_latest": hard_pass,
        "hard_pass_complete_years": hard_pass,
        "non_positive_months": monthly.loc[monthly["return_pct"] <= 0, "month"].tolist(),
        "total_eval_return_pct": float((np.exp(float(monthly["log_return"].sum())) - 1.0) * 100.0),
        "return_2025_pct": return_2025,
        "return_2026_ytd_pct": return_2026,
        "target_years": ["2025", "2026_ytd"],
        "min_target_year_return_pct": float(min_target_year_return),
        "min_complete_year_return_pct": float(min_target_year_return),
        "losing_eval_months": losing_eval_months,
        "min_monthly_return_pct": float(monthly["return_pct"].min()),
        "min_monthly_orders": min_orders,
        "orders": int(monthly["orders"].sum()),
        "turnover": float(monthly["turnover"].sum()),
        "cost_log": float(monthly["cost_log"].sum()),
        "worst_selected_month_drawdown_pct": float(monthly["max_drawdown_pct"].min()),
        "selected_candidate_count": int(monthly["candidate_id"].nunique()),
    }


def _year_return(yearly_by_year: dict[str, Any], year: str) -> float | None:
    if year not in yearly_by_year:
        return None
    return float(yearly_by_year[year].compounded_return_pct)


def _data_quality(frame: pd.DataFrame, quality: pd.DataFrame, from_cache: bool) -> dict[str, Any]:
    timestamp = pd.to_datetime(frame["timestamp"], utc=True)
    diffs = timestamp.diff().dropna()
    ok_downloads = quality.loc[quality["ok"].astype(bool)] if "ok" in quality else pd.DataFrame()
    return {
        "from_cache": from_cache,
        "rows": int(len(frame)),
        "start_timestamp": timestamp.min().isoformat(),
        "end_timestamp": timestamp.max().isoformat(),
        "months": sorted(frame["timestamp"].dt.strftime("%Y-%m").unique().tolist()),
        "duplicate_timestamp_rows": int(timestamp.duplicated().sum()),
        "non_3m_gap_rows": int((diffs != BAR_DELTA).sum()),
        "calendar_fill_rows": int(frame["calendar_filled"].sum()) if "calendar_filled" in frame else 0,
        "downloaded_files": int(len(ok_downloads)),
        "download_size_mb": round(float(ok_downloads["content_length"].fillna(0).sum()) / 1024**2, 3) if len(ok_downloads) else 0.0,
        "missing_daily_archives": quality.loc[(quality["kind"] == "daily") & (~quality["ok"].astype(bool)), "period"].tolist() if "kind" in quality else [],
        "pass": bool(timestamp.duplicated().sum() == 0 and (diffs != BAR_DELTA).sum() == 0),
    }


def _candidate_grid_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    meta = pd.DataFrame(candidates)
    return {
        "candidate_count": int(len(meta)),
        "families": {str(key): int(value) for key, value in meta["family"].value_counts().sort_index().items()},
        "rules": {str(key): int(value) for key, value in meta["rule"].value_counts().sort_index().items()},
        "leverages": sorted(float(value) for value in meta["leverage"].unique()),
    }


def _decision(best_order10: dict[str, Any]) -> dict[str, Any]:
    if bool(best_order10["hard_pass_2025_to_latest"]):
        return {
            "verdict": "BTC_3M_2025_TODAY_UPPER_BOUND_HAS_MONTHLY_PIECES",
            "promote_strategy": False,
            "reason": "BTC 3m 在2025到最新公开数据窗口里，看答案月度上限满足年收益、月盈利和每月10单门槛；但它不能交易。",
            "next_step": "如果继续，另起33号补2023-2024的3m训练历史，再做严格逐月选择器。",
        }
    return {
        "verdict": "BTC_3M_2025_TODAY_UPPER_BOUND_FAILS",
        "promote_strategy": False,
        "reason": "即使用BTC 3m并允许每个月事后挑最好候选，也过不了硬目标。",
        "next_step": "不要继续单币BTC 3m小规则；回到多币种完整历史严格选择器。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_order10_oracle"]
    static = summary["best_static_candidate"]
    decision = summary["decision"]
    data = summary["data"]
    return f"""# 32号 BTC 3m 2025到最新公开数据上限测试

这不是策略，不能交易。它只回答：如果把 BTC 从15分钟改成3分钟，2025到现在这段有没有更好的上限。

## 数据

- 数据：Binance 免费 USD-M futures `BTCUSDT` 3m K线
- 开始：`{data["start_timestamp"]}`
- 结束：`{data["end_timestamp"]}`
- 行数：`{data["rows"]}`
- 缺3分钟断档：`{data["non_3m_gap_rows"]}`
- 补齐K线：`{data["calendar_fill_rows"]}`
- 未拿到的日包：`{", ".join(data["missing_daily_archives"])}`

## 口径

- 手续费：开平合计 `{probe16.ROUND_TRIP_COST * 100:.2f}%`
- 信号：只用已收盘3分钟K线，下一根3分钟才吃收益
- 候选：动量/反转、EMA趋势、Donchian、RSI、布林带、ATR突破、成交量放大
- 月度 oracle 是看答案，不能交易

## 最好静态候选

- 候选：`{static["candidate_id"]}`
- 2025：`{static["return_2025_pct"]:.2f}%`
- 2026 YTD：`{static["return_2026_ytd_pct"]:.2f}%`
- 不盈利月份数：`{static["losing_eval_months"]}`
- 最差月：`{static["min_monthly_return_pct"]:.2f}%`
- 最少月交易：`{static["min_monthly_orders"]}`

## 最好每月10单上限

- oracle：`{best["oracle_id"]}`
- 2025：`{best["return_2025_pct"]:.2f}%`
- 2026 YTD：`{best["return_2026_ytd_pct"]:.2f}%`
- 不盈利月份：`{", ".join(best["non_positive_months"])}`
- 最差月：`{best["min_monthly_return_pct"]:.2f}%`
- 最少月交易：`{best["min_monthly_orders"]}`

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
