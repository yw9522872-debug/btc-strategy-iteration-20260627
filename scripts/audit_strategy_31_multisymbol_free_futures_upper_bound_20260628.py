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


STRATEGY_ID = "strategy_31_multisymbol_free_futures_sample_upper_bound_20260628"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
PANEL_PATH = OUT_DIR / "multisymbol_close_panel_15m_sample.csv.gz"
COVERAGE_PATH = OUT_DIR / "symbol_month_coverage.csv"

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "HYPEUSDT", "DOGEUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT"]
SAMPLE_MONTHS = ["2023-07", "2024-06", "2025-08", "2026-05"]
START_MONTH = pd.Period(SAMPLE_MONTHS[0], freq="M")
END_MONTH = pd.Period(SAMPLE_MONTHS[-1], freq="M")
BAR_DELTA = pd.Timedelta(minutes=15)
USER_AGENT = "strategy-31-multisymbol-free-futures/1.0"
URL_TEMPLATE = "https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/15m/{symbol}-15m-{yyyy}-{mm}.zip"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel, data_quality = _load_or_fetch_panel()
    close = panel[[f"close_{symbol}" for symbol in SYMBOLS]].copy()
    close.columns = SYMBOLS
    valid = close.notna()
    returns = np.log(close / close.shift(1)).replace([np.inf, -np.inf], np.nan).where(valid & valid.shift(1)).fillna(0.0)
    market = {
        "timestamp": pd.to_datetime(panel["timestamp"], utc=True),
        "month": panel["month"].astype(str).to_numpy(),
        "symbols": SYMBOLS,
        "close": close,
        "valid": valid,
        "returns": returns,
    }
    candidates = _candidate_library()
    candidate_monthly, candidate_scan = _candidate_results(candidates, market)
    oracle_summary, oracle_monthly, oracle_yearly = _oracle_results(candidate_monthly)
    best_oracle = oracle_summary.iloc[0].to_dict()
    best_order10 = oracle_summary.loc[oracle_summary["requires_monthly_orders_ge_10_at_selection"]].iloc[0].to_dict()

    candidate_monthly.to_csv(OUT_DIR / "candidate_monthly.csv", index=False)
    candidate_scan.to_csv(OUT_DIR / "candidate_scan.csv", index=False)
    oracle_summary.to_csv(OUT_DIR / "oracle_summary.csv", index=False)
    oracle_monthly.to_csv(OUT_DIR / "oracle_monthly.csv", index=False)
    oracle_yearly.to_csv(OUT_DIR / "oracle_yearly.csv", index=False)

    summary = {
        "status": "strategy_31_multisymbol_free_futures_sample_upper_bound_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Small sample test for whether a free multi-symbol USD-M futures basket gives enough upper-bound pieces beyond BTC-only rules.",
        "symbols": SYMBOLS,
        "sample_months": SAMPLE_MONTHS,
        "data": data_quality,
        "cost_model": {
            "cost_per_side": probe16.COST_PER_SIDE,
            "round_trip_open_close": probe16.ROUND_TRIP_COST,
            "multi_asset_turnover_note": "Cost is charged on the sum of absolute target weight changes across symbols.",
        },
        "timing": {
            "signals_use_closed_bar_t": True,
            "position_participates_from_bar_t_plus_1": True,
            "monthly_oracle_is_leaky_and_not_tradeable": True,
        },
        "candidate_grid": _candidate_grid_summary(candidates),
        "static_positive_all_sample_months_count": int((candidate_scan["losing_sample_months"] == 0).sum()),
        "best_static_candidate": _json_ready(candidate_scan.iloc[0].to_dict()),
        "oracle_summary": _json_ready(oracle_summary.to_dict("records")),
        "best_oracle": _json_ready(best_oracle),
        "best_order10_oracle": _json_ready(best_order10),
        "decision": _decision(best_order10),
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
        return panel, _data_quality(panel, coverage, from_cache=True)

    months = [pd.Period(month, freq="M") for month in SAMPLE_MONTHS]
    # ponytail: keep only sample months; the signal code blocks lookback across month gaps.
    full_index = pd.DatetimeIndex(
        np.concatenate(
            [
                pd.date_range(month.start_time.tz_localize("UTC"), month.end_time.tz_localize("UTC").floor("15min"), freq=BAR_DELTA).to_numpy()
                for month in months
            ]
        )
    )
    panel = pd.DataFrame({"timestamp": full_index})
    coverage_rows: list[dict[str, Any]] = []
    for symbol in SYMBOLS:
        print(f"symbol {symbol}", flush=True)
        frames: list[pd.DataFrame] = []
        for month in months:
            url = URL_TEMPLATE.format(symbol=symbol, yyyy=month.year, mm=f"{month.month:02d}")
            head = _head_check(url)
            row = {"symbol": symbol, "month": str(month), "url": url, **head}
            if head["ok"]:
                try:
                    frame = _fetch_month(url)
                    frames.append(frame)
                    row["rows"] = int(len(frame))
                except Exception as exc:
                    row["ok"] = False
                    row["error"] = repr(exc)
                    row["rows"] = 0
            else:
                row["rows"] = 0
            coverage_rows.append(row)
            time.sleep(0.02)
        symbol_frame = _symbol_close_frame(frames, full_index)
        panel = panel.merge(symbol_frame.rename(columns={"close": f"close_{symbol}"}), on="timestamp", how="left")

    panel["month"] = panel["timestamp"].dt.strftime("%Y-%m")
    columns = ["timestamp", "month"] + [f"close_{symbol}" for symbol in SYMBOLS]
    panel = panel[columns]
    coverage = pd.DataFrame(coverage_rows)
    panel.to_csv(PANEL_PATH, index=False)
    coverage.to_csv(COVERAGE_PATH, index=False)
    return panel, _data_quality(panel, coverage, from_cache=False)


def _head_check(url: str) -> dict[str, Any]:
    try:
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            return {"ok": True, "http_status": int(response.status), "content_length": _int_or_none(response.headers.get("Content-Length")), "error": None}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "http_status": int(exc.code), "content_length": None, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "http_status": None, "content_length": None, "error": repr(exc)}


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
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
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
    out["close"] = pd.to_numeric(raw["close"], errors="coerce")
    return out.dropna(subset=["timestamp", "close"]).drop_duplicates("timestamp", keep="last").sort_values("timestamp")


def _symbol_close_frame(frames: list[pd.DataFrame], full_index: pd.DatetimeIndex) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame({"timestamp": full_index, "close": np.nan})
    out = pd.concat(frames, ignore_index=True).drop_duplicates("timestamp", keep="last").sort_values("timestamp")
    out = out.set_index("timestamp").reindex(full_index)
    return out.reset_index().rename(columns={"index": "timestamp"})[["timestamp", "close"]]


def _candidate_library() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    leverages = [1.0, 2.0, 4.0]
    for lookback in [16, 96, 384, 1536]:
        for threshold_bps in [0, 50, 100, 200]:
            for leverage in leverages:
                candidates.append(_candidate("cross_section", "long_strong_short_weak", leverage, lookback=lookback, threshold_bps=threshold_bps))
                candidates.append(_candidate("cross_section", "long_weak_short_strong", leverage, lookback=lookback, threshold_bps=threshold_bps))
    for symbol in SYMBOLS:
        for lookback in [16, 96, 384, 1536]:
            for threshold_bps in [20, 50, 100]:
                for leverage in leverages:
                    candidates.append(_candidate("single_symbol", "symbol_momentum", leverage, symbol=symbol, lookback=lookback, threshold_bps=threshold_bps))
                    candidates.append(_candidate("single_symbol", "symbol_reversal", leverage, symbol=symbol, lookback=lookback, threshold_bps=threshold_bps))
    return candidates


def _candidate(family: str, rule: str, leverage: float, **params: Any) -> dict[str, Any]:
    suffix = "_".join(f"{key}{str(value).replace('.', 'p')}" for key, value in params.items())
    return {"candidate_id": f"{family}_{rule}_lev{str(leverage).replace('.', 'p')}_{suffix}", "family": family, "rule": rule, "leverage": leverage, **params}


def _target_for_candidate(candidate: dict[str, Any], market: dict[str, Any]) -> np.ndarray:
    close: pd.DataFrame = market["close"]
    valid: pd.DataFrame = market["valid"]
    n, m = close.shape
    target = np.zeros((n, m), dtype=float)
    lookback = int(candidate["lookback"])
    threshold = float(candidate["threshold_bps"])
    signal_bps = np.log(close / close.shift(lookback)).replace([np.inf, -np.inf], np.nan) * 10_000.0
    same_month = pd.Series(market["month"]).eq(pd.Series(market["month"]).shift(lookback))
    tradable = (valid & valid.shift(lookback)).mul(same_month.to_numpy(), axis=0)
    leverage = float(candidate["leverage"])

    if candidate["family"] == "cross_section":
        for i, row in enumerate(signal_bps.to_numpy(dtype=float)):
            ok = tradable.iloc[i].to_numpy(dtype=bool) & np.isfinite(row)
            if ok.sum() < 2:
                continue
            values = np.where(ok, row, np.nan)
            strong = int(np.nanargmax(values))
            weak = int(np.nanargmin(values))
            if values[strong] - values[weak] < threshold:
                continue
            long_idx, short_idx = (strong, weak) if candidate["rule"] == "long_strong_short_weak" else (weak, strong)
            target[i, long_idx] = leverage / 2.0
            target[i, short_idx] = -leverage / 2.0
    elif candidate["family"] == "single_symbol":
        symbol = str(candidate["symbol"])
        if symbol not in close.columns:
            return target
        j = list(close.columns).index(symbol)
        side = np.sign(signal_bps[symbol].to_numpy(dtype=float))
        if candidate["rule"] == "symbol_reversal":
            side = -side
        mask = tradable[symbol].to_numpy(dtype=bool) & (np.abs(signal_bps[symbol].to_numpy(dtype=float)) >= threshold)
        target[:, j] = np.where(mask, side * leverage, 0.0)
    else:
        raise ValueError(candidate["family"])
    return np.nan_to_num(target, nan=0.0)


def _simulate_target(market: dict[str, Any], target: np.ndarray) -> pd.DataFrame:
    returns = market["returns"].to_numpy(dtype=float)
    active = np.roll(target, 1, axis=0)
    active[0, :] = 0.0
    previous = np.vstack([np.zeros((1, target.shape[1])), target[:-1, :]])
    turnover = np.abs(target - previous).sum(axis=1)
    orders = (np.abs(target - previous) > 1e-12).sum(axis=1)
    cost = turnover * probe16.COST_PER_SIDE
    strategy_lr = (active * returns).sum(axis=1) - cost
    equity = np.exp(np.cumsum(strategy_lr))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    if len(target) > 1 and not np.allclose(active[1:], target[:-1]):
        raise AssertionError("Timing check failed.")
    return pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "month": market["month"],
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
        exposure_pct=("turnover", lambda values: float((values > 0).mean() * 100.0)),
        max_drawdown_pct=("drawdown", lambda values: float(values.min() * 100.0)),
    )
    monthly["return_pct"] = (np.exp(monthly["log_return"]) - 1.0) * 100.0
    return monthly


def _candidate_results(candidates: list[dict[str, Any]], market: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_frames: list[pd.DataFrame] = []
    scan_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        target = _target_for_candidate(candidate, market)
        equity = _simulate_target(market, target)
        monthly_all = _monthly_breakdown(equity)
        monthly = monthly_all.loc[(monthly_all["month"] >= probe16.EVAL_START_MONTH) & (monthly_all["month"] < probe16.EVAL_END_EXCLUSIVE)].copy()
        monthly.insert(0, "candidate_id", candidate["candidate_id"])
        monthly.insert(1, "family", candidate["family"])
        monthly.insert(2, "rule", candidate["rule"])
        monthly.insert(3, "leverage", candidate["leverage"])
        monthly_frames.append(monthly)
        scan_rows.append({**candidate, **_sample_summary(monthly)})
    all_monthly = pd.concat(monthly_frames, ignore_index=True)
    scan = pd.DataFrame(scan_rows).sort_values(
        ["losing_sample_months", "total_sample_return_pct", "min_monthly_return_pct", "orders"],
        ascending=[True, False, False, False],
    )
    return all_monthly, scan


def _oracle_results(candidate_monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    specs = [
        ("monthly_oracle_best_return", None, False),
        ("monthly_oracle_best_return_order10", None, True),
        ("cross_section_oracle_order10", "cross_section", True),
        ("single_symbol_oracle_order10", "single_symbol", True),
    ]
    rows: list[dict[str, Any]] = []
    monthly_frames: list[pd.DataFrame] = []
    for oracle_id, family, require_order_floor in specs:
        selected = upper17._select_oracle_months(candidate_monthly, oracle_id, family, require_order_floor)
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
        if "oracle_id" not in selected.columns:
            selected.insert(0, "oracle_id", oracle_id)
        monthly_frames.append(selected)
    summary = pd.DataFrame(rows).sort_values(
        ["losing_sample_months", "months_without_order_floor_candidate", "total_sample_return_pct", "min_monthly_return_pct"],
        ascending=[True, True, False, False],
    )
    yearly = pd.DataFrame()
    return summary, pd.concat(monthly_frames, ignore_index=True), yearly


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


def _data_quality(panel: pd.DataFrame, coverage: pd.DataFrame, from_cache: bool) -> dict[str, Any]:
    symbol_rows = []
    for symbol in SYMBOLS:
        month_ok = coverage.loc[(coverage["symbol"] == symbol) & (coverage["ok"].astype(bool))]
        close = panel[f"close_{symbol}"]
        first = panel.loc[close.notna(), "timestamp"].min() if close.notna().any() else None
        last = panel.loc[close.notna(), "timestamp"].max() if close.notna().any() else None
        symbol_rows.append(
            {
                "symbol": symbol,
                "ok_months": int(len(month_ok)),
                "first_timestamp": first.isoformat() if first is not None else None,
                "last_timestamp": last.isoformat() if last is not None else None,
                "valid_15m_rows": int(close.notna().sum()),
                "download_size_mb": round(float(month_ok["content_length"].fillna(0).sum()) / 1024**2, 3),
            }
        )
    coverage_summary = pd.DataFrame(symbol_rows)
    coverage_summary.to_csv(OUT_DIR / "symbol_coverage_summary.csv", index=False)
    ts = pd.to_datetime(panel["timestamp"], utc=True)
    non_15m_gap_rows = int((ts.diff().dropna() != BAR_DELTA).sum())
    expected_sample_boundary_gaps = max(0, len(SAMPLE_MONTHS) - 1)
    return {
        "from_cache": from_cache,
        "rows": int(len(panel)),
        "start_timestamp": ts.min().isoformat(),
        "end_timestamp": ts.max().isoformat(),
        "duplicate_timestamp_rows": int(ts.duplicated().sum()),
        "non_15m_gap_rows": non_15m_gap_rows,
        "expected_sample_boundary_gaps": expected_sample_boundary_gaps,
        "symbols": _json_ready(coverage_summary.to_dict("records")),
        "coverage_summary": _rel(OUT_DIR / "symbol_coverage_summary.csv"),
        "pass": bool(ts.duplicated().sum() == 0 and non_15m_gap_rows == expected_sample_boundary_gaps),
    }


def _candidate_grid_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    meta = pd.DataFrame(candidates)
    return {
        "candidate_count": int(len(meta)),
        "families": sorted(meta["family"].unique().tolist()),
        "rules": sorted(meta["rule"].unique().tolist()),
        "leverages": sorted(float(x) for x in meta["leverage"].unique()),
    }


def _decision(best_order10: dict[str, Any]) -> dict[str, Any]:
    ok = (
        int(best_order10["losing_sample_months"]) == 0
        and int(best_order10["months_without_order_floor_candidate"]) == 0
        and int(best_order10["min_monthly_orders"]) >= probe16.REQUIRED_MIN_MONTHLY_ORDERS
    )
    if ok:
        return {
            "verdict": "MULTISYMBOL_FREE_FUTURES_SAMPLE_UPPER_BOUND_HAS_SIGNAL",
            "promote_strategy": False,
            "reason": "四个样本月里，多币种看答案上限在每月至少10单口径下全为正收益；但它仍然不能交易。",
            "next_step": "另起32号扩到完整2020-2026，再做严格逐月选择器。",
        }
    return {
        "verdict": "MULTISYMBOL_FREE_FUTURES_SAMPLE_UPPER_BOUND_FAILS",
        "promote_strategy": False,
        "reason": "即使把免费多币种加入，并允许每个月事后挑最好候选，四个关键样本月仍不能同时满足盈利和每月至少10单。",
        "next_step": "不要继续扩大免费多币种小规则；改成更现实目标或等待真正不同的新数据源。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_order10_oracle"]
    decision = summary["decision"]
    symbols = "\n".join(
        f"- `{row['symbol']}`：可用月份 `{row['ok_months']}`，首根 `{row['first_timestamp']}`，末根 `{row['last_timestamp']}`"
        for row in summary["data"]["symbols"]
    )
    return f"""# 31号多币种免费期货上限测试

    这不是策略，不能交易。它只拿四个样本月，先检查多币种免费 USD-M futures 15分钟K线，能不能比 BTC 单币多给一些机会。

## 币种覆盖

{symbols}

## 口径

- 币种：{", ".join(SYMBOLS)}
- 数据：Binance 免费 USD-M futures 15m klines
- 样本月：{", ".join(SAMPLE_MONTHS)}
- 手续费：开平合计 `{probe16.ROUND_TRIP_COST * 100:.2f}%`
- 候选：跨币种强弱轮动、单币种动量/反转
- 时序：只用已收盘K线，下一根15分钟K线才吃收益
- 注意：月度 oracle 会看答案，不能交易

## 最好每月10单上限

- oracle：`{best["oracle_id"]}`
- 样本总收益：`{best["total_sample_return_pct"]:.2f}%`
- 不盈利月份：`{", ".join(best["non_positive_months"])}`
- 最差月：`{best["min_monthly_return_pct"]:.2f}%`
- 最少月交易：`{best["min_monthly_orders"]}`

## 判断

`{decision["verdict"]}`

{decision["reason"]}

下一步：{decision["next_step"]}
"""


def _int_or_none(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


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
