from __future__ import annotations

import io
import json
import math
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


STRATEGY_ID = "strategy_41_btc_hype_relaxed_drawdown_20260629"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
PANEL_PATH = OUT_DIR / "btc_hype_close_panel_15m_2020_2026_05.csv.gz"
COVERAGE_PATH = OUT_DIR / "symbol_month_coverage.csv"

SYMBOLS = ["BTCUSDT", "HYPEUSDT"]
START_MONTH = pd.Period("2020-01", freq="M")
END_MONTH = pd.Period("2026-05", freq="M")
EVAL_START = "2023-01"
EVAL_END_EXCLUSIVE = "2026-06"
TARGET_YEARS = ["2025", "2026"]
COMPLETE_YEARS = ["2023", "2024", "2025"]
MAX_DRAWDOWN_LIMIT_PCT = -50.0
REQUIRED_YEAR_RETURN_PCT = 100.0
BAR_DELTA = pd.Timedelta(minutes=15)
URL = "https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/15m/{symbol}-15m-{yyyy}-{mm}.zip"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel, data_quality = _load_or_fetch_panel()
    market = _market(panel)
    candidates = _candidate_library()
    candidate_monthly, candidate_scan = _candidate_results(candidates, market)
    oracle_monthly, oracle_summary = _monthly_oracle(candidate_monthly)
    capped_oracle_monthly, capped_oracle_summary = _monthly_oracle_drawdown_capped(candidate_monthly)
    strict_monthly, strict_summary = _strict_selector(candidate_monthly)

    candidate_monthly.to_csv(OUT_DIR / "candidate_monthly.csv", index=False)
    candidate_scan.to_csv(OUT_DIR / "candidate_scan.csv", index=False)
    oracle_monthly.to_csv(OUT_DIR / "oracle_monthly.csv", index=False)
    pd.DataFrame([oracle_summary]).to_csv(OUT_DIR / "oracle_summary.csv", index=False)
    capped_oracle_monthly.to_csv(OUT_DIR / "oracle_drawdown_capped_monthly.csv", index=False)
    pd.DataFrame([capped_oracle_summary]).to_csv(OUT_DIR / "oracle_drawdown_capped_summary.csv", index=False)
    strict_monthly.to_csv(OUT_DIR / "strict_selector_monthly.csv", index=False)
    pd.DataFrame([strict_summary]).to_csv(OUT_DIR / "strict_selector_summary.csv", index=False)

    best_static = candidate_scan.iloc[0].to_dict()
    summary = {
        "status": "strategy_41_btc_hype_relaxed_drawdown_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "BTC+HYPE only, with monthly-profit and monthly-order gates removed; keep only max drawdown <= 50% and target-year return > 100%.",
        "data": data_quality,
        "symbols": SYMBOLS,
        "relaxed_gate": {
            "target_years": TARGET_YEARS,
            "required_each_target_year_return_pct": REQUIRED_YEAR_RETURN_PCT,
            "max_drawdown_limit_pct": MAX_DRAWDOWN_LIMIT_PCT,
            "monthly_profit_gate_removed": True,
            "monthly_order_gate_removed": True,
        },
        "cost_model": {
            "cost_per_side": probe16.COST_PER_SIDE,
            "round_trip_open_close": probe16.ROUND_TRIP_COST,
        },
        "timing": {
            "signals_use_closed_15m_bar_t": True,
            "position_participates_from_bar_t_plus_1": True,
            "monthly_oracle_is_leaky": True,
            "strict_selector_uses_only_months_before_eval_month": True,
        },
        "candidate_count": int(len(candidates)),
        "static_relaxed_pass_count": int(candidate_scan["hard_pass_target_years_relaxed"].sum()),
        "static_complete_year_pass_count": int(candidate_scan["hard_pass_complete_years_relaxed"].sum()),
        "best_static_candidate": _json_ready(best_static),
        "monthly_oracle": _json_ready(oracle_summary),
        "monthly_oracle_drawdown_capped": _json_ready(capped_oracle_summary),
        "strict_selector": _json_ready(strict_summary),
        "decision": _decision(best_static, oracle_summary, capped_oracle_summary, strict_summary),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "panel": _rel(PANEL_PATH),
            "coverage": _rel(COVERAGE_PATH),
            "candidate_scan": _rel(OUT_DIR / "candidate_scan.csv"),
            "candidate_monthly": _rel(OUT_DIR / "candidate_monthly.csv"),
            "oracle_monthly": _rel(OUT_DIR / "oracle_monthly.csv"),
            "oracle_summary": _rel(OUT_DIR / "oracle_summary.csv"),
            "oracle_drawdown_capped_monthly": _rel(OUT_DIR / "oracle_drawdown_capped_monthly.csv"),
            "oracle_drawdown_capped_summary": _rel(OUT_DIR / "oracle_drawdown_capped_summary.csv"),
            "strict_selector_monthly": _rel(OUT_DIR / "strict_selector_monthly.csv"),
            "strict_selector_summary": _rel(OUT_DIR / "strict_selector_summary.csv"),
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
        return panel, _data_quality(panel, coverage, True)

    full_index = pd.date_range(START_MONTH.start_time.tz_localize("UTC"), END_MONTH.end_time.tz_localize("UTC").floor("15min"), freq=BAR_DELTA)
    panel = pd.DataFrame({"timestamp": full_index})
    coverage_rows: list[dict[str, Any]] = []

    btc_source = ROOT / "artifacts" / "strategy_33_multisymbol_free_futures_strict_selector_20260629" / "multisymbol_close_panel_15m_2020_2026_05.csv.gz"
    if btc_source.exists():
        btc = pd.read_csv(btc_source, usecols=["timestamp", "close_BTCUSDT"])
        btc["timestamp"] = pd.to_datetime(btc["timestamp"], utc=True)
        panel = panel.merge(btc.rename(columns={"close_BTCUSDT": "close_BTCUSDT"}), on="timestamp", how="left")
        coverage_rows.extend(_coverage_from_panel(panel, "BTCUSDT", from_cache=True))
    else:
        btc_frame, rows = _fetch_symbol("BTCUSDT", full_index)
        panel = panel.merge(btc_frame.rename(columns={"close": "close_BTCUSDT"}), on="timestamp", how="left")
        coverage_rows.extend(rows)

    hype_frame, rows = _fetch_symbol("HYPEUSDT", full_index)
    panel = panel.merge(hype_frame.rename(columns={"close": "close_HYPEUSDT"}), on="timestamp", how="left")
    coverage_rows.extend(rows)

    panel["month"] = panel["timestamp"].dt.strftime("%Y-%m")
    panel = panel[["timestamp", "month", "close_BTCUSDT", "close_HYPEUSDT"]]
    coverage = pd.DataFrame(coverage_rows)
    panel.to_csv(PANEL_PATH, index=False)
    coverage.to_csv(COVERAGE_PATH, index=False)
    return panel, _data_quality(panel, coverage, False)


def _fetch_symbol(symbol: str, full_index: pd.DatetimeIndex) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    frames: list[pd.DataFrame] = []
    rows: list[dict[str, Any]] = []
    for month in pd.period_range(START_MONTH, END_MONTH, freq="M"):
        url = URL.format(symbol=symbol, yyyy=month.year, mm=f"{month.month:02d}")
        row = {"symbol": symbol, "month": str(month), "url": url, "ok": False, "rows": 0, "http_status": None, "error": None}
        try:
            frame = _fetch_month(url)
            frames.append(frame)
            row.update({"ok": True, "rows": int(len(frame)), "http_status": 200})
        except urllib.error.HTTPError as exc:
            row.update({"http_status": int(exc.code), "error": str(exc)})
        except Exception as exc:
            row.update({"error": repr(exc)})
        rows.append(row)
        time.sleep(0.01)
    if not frames:
        return pd.DataFrame({"timestamp": full_index, "close": np.nan}), rows
    out = pd.concat(frames, ignore_index=True).drop_duplicates("timestamp", keep="last").sort_values("timestamp")
    out = out.set_index("timestamp").reindex(full_index).rename_axis("timestamp").reset_index()
    return out[["timestamp", "close"]], rows


def _fetch_month(url: str) -> pd.DataFrame:
    request = urllib.request.Request(url, headers={"User-Agent": "strategy-41-btc-hype-research/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        names = [name for name in zf.namelist() if name.endswith(".csv")]
        if not names:
            raise RuntimeError(f"No CSV in {url}")
        with zf.open(names[0]) as handle:
            raw = pd.read_csv(handle, header=None)
    names = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "trades", "taker_base", "taker_quote", "ignore"]
    raw = raw.iloc[:, : len(names)].copy()
    raw.columns = names[: len(raw.columns)]
    if len(raw) and str(raw.iloc[0]["open_time"]).lower() == "open_time":
        raw = raw.iloc[1:].reset_index(drop=True)
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(pd.to_numeric(raw["open_time"], errors="raise"), unit="ms", utc=True),
            "close": pd.to_numeric(raw["close"], errors="raise"),
        }
    )


def _coverage_from_panel(panel: pd.DataFrame, symbol: str, from_cache: bool) -> list[dict[str, Any]]:
    close = panel[f"close_{symbol}"]
    rows = []
    for month, group in panel.assign(close=close).groupby(panel["timestamp"].dt.strftime("%Y-%m")):
        valid = group["close"].notna()
        rows.append({"symbol": symbol, "month": month, "url": "strategy_33_cached_panel" if from_cache else None, "ok": bool(valid.any()), "rows": int(valid.sum()), "http_status": None, "error": None})
    return rows


def _market(panel: pd.DataFrame) -> dict[str, Any]:
    close = panel[[f"close_{s}" for s in SYMBOLS]].copy()
    close.columns = SYMBOLS
    valid = close.notna()
    returns = np.log(close / close.shift(1)).replace([np.inf, -np.inf], np.nan).where(valid & valid.shift(1)).fillna(0.0)
    return {"timestamp": pd.to_datetime(panel["timestamp"], utc=True), "month": panel["month"].astype(str).to_numpy(), "symbols": SYMBOLS, "close": close, "valid": valid, "returns": returns}


def _candidate_library() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for lookback in [16, 64, 96, 192, 384, 768, 1536]:
        for threshold_bps in [0, 20, 50, 100, 200, 400]:
            for leverage in [1.0, 2.0, 3.0, 4.0]:
                candidates.append(_candidate("pair", "long_strong_short_weak", leverage, lookback=lookback, threshold_bps=threshold_bps))
                candidates.append(_candidate("pair", "long_weak_short_strong", leverage, lookback=lookback, threshold_bps=threshold_bps))
                for symbol in SYMBOLS:
                    candidates.append(_candidate("single_symbol", "symbol_momentum", leverage, symbol=symbol, lookback=lookback, threshold_bps=threshold_bps))
                    candidates.append(_candidate("single_symbol", "symbol_reversal", leverage, symbol=symbol, lookback=lookback, threshold_bps=threshold_bps))
    return candidates


def _candidate(family: str, rule: str, leverage: float, **params: Any) -> dict[str, Any]:
    suffix = "_".join(f"{k}{str(v).replace('.', 'p')}" for k, v in params.items())
    return {"candidate_id": f"{family}_{rule}_lev{str(leverage).replace('.', 'p')}_{suffix}", "family": family, "rule": rule, "leverage": leverage, **params}


def _target_for_candidate(candidate: dict[str, Any], market: dict[str, Any]) -> np.ndarray:
    signal_bps, tradable = _signal_for_lookback(market, int(candidate["lookback"]))
    leverage = float(candidate["leverage"])
    threshold = float(candidate["threshold_bps"])
    target = np.zeros_like(signal_bps)
    if candidate["family"] == "pair":
        finite = np.isfinite(signal_bps) & tradable
        spread = signal_bps[:, 1] - signal_bps[:, 0]
        rows = np.where(finite.all(axis=1) & (np.abs(spread) >= threshold))[0]
        hype_strong = spread[rows] > 0
        if candidate["rule"] == "long_strong_short_weak":
            target[rows, 1] = np.where(hype_strong, leverage / 2.0, -leverage / 2.0)
            target[rows, 0] = -target[rows, 1]
        else:
            target[rows, 1] = np.where(hype_strong, -leverage / 2.0, leverage / 2.0)
            target[rows, 0] = -target[rows, 1]
        return target

    j = SYMBOLS.index(str(candidate["symbol"]))
    side = np.sign(signal_bps[:, j])
    if candidate["rule"] == "symbol_reversal":
        side = -side
    mask = tradable[:, j] & (np.abs(signal_bps[:, j]) >= threshold)
    target[:, j] = np.where(mask, side * leverage, 0.0)
    return target


def _signal_for_lookback(market: dict[str, Any], lookback: int) -> tuple[np.ndarray, np.ndarray]:
    close = market["close"].to_numpy(dtype=float)
    valid = market["valid"].to_numpy(dtype=bool)
    shifted = np.full_like(close, np.nan)
    shifted_valid = np.zeros_like(valid)
    shifted[lookback:] = close[:-lookback]
    shifted_valid[lookback:] = valid[:-lookback]
    same_month = np.zeros(len(close), dtype=bool)
    same_month[lookback:] = market["month"][lookback:] == market["month"][:-lookback]
    with np.errstate(divide="ignore", invalid="ignore"):
        signal = np.log(close / shifted) * 10_000.0
    return signal, valid & shifted_valid & same_month[:, None] & np.isfinite(signal)


def _simulate(market: dict[str, Any], target: np.ndarray) -> pd.DataFrame:
    returns = market["returns"].to_numpy(dtype=float)
    active = np.roll(target, 1, axis=0)
    active[0, :] = 0.0
    previous = np.vstack([np.zeros((1, target.shape[1])), target[:-1, :]])
    turnover = np.abs(target - previous).sum(axis=1)
    orders = (np.abs(target - previous) > 1e-12).sum(axis=1)
    cost = turnover * probe16.COST_PER_SIDE
    lr = (active * returns).sum(axis=1) - cost
    equity = np.exp(np.cumsum(lr))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    return pd.DataFrame({"timestamp": market["timestamp"], "month": market["month"], "log_return": lr, "turnover": turnover, "orders": orders, "drawdown_pct": drawdown * 100.0})


def _monthly_breakdown(equity: pd.DataFrame) -> pd.DataFrame:
    monthly = equity.groupby("month", as_index=False).agg(
        log_return=("log_return", "sum"),
        turnover=("turnover", "sum"),
        orders=("orders", "sum"),
        max_drawdown_pct=("drawdown_pct", "min"),
    )
    monthly["return_pct"] = (np.exp(monthly["log_return"]) - 1.0) * 100.0
    return monthly


def _candidate_results(candidates: list[dict[str, Any]], market: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_frames = []
    scan_rows = []
    for candidate in candidates:
        monthly = _monthly_breakdown(_simulate(market, _target_for_candidate(candidate, market)))
        for key in ["candidate_id", "family", "rule", "leverage"]:
            monthly.insert(len([c for c in ["candidate_id", "family", "rule", "leverage"] if c in monthly.columns]), key, candidate[key])
        monthly_frames.append(monthly)
        scan_rows.append({**candidate, **_summary(monthly)})
    candidate_monthly = pd.concat(monthly_frames, ignore_index=True)
    candidate_scan = pd.DataFrame(scan_rows).sort_values(
        ["hard_pass_target_years_relaxed", "max_drawdown_pct", "min_target_year_return_pct", "return_2025_pct", "return_2026_ytd_pct"],
        ascending=[False, False, False, False, False],
    )
    return candidate_monthly, candidate_scan


def _monthly_oracle(candidate_monthly: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    eval_rows = _eval_months(candidate_monthly)
    selected = eval_rows.sort_values(["month", "log_return"], ascending=[True, False]).groupby("month", as_index=False).head(1)
    return selected, _summary(selected)


def _monthly_oracle_drawdown_capped(candidate_monthly: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    eval_rows = _eval_months(candidate_monthly)
    capped = eval_rows.loc[eval_rows["max_drawdown_pct"] >= MAX_DRAWDOWN_LIMIT_PCT]
    selected = capped.sort_values(["month", "log_return"], ascending=[True, False]).groupby("month", as_index=False).head(1)
    return selected, _summary(selected)


def _strict_selector(candidate_monthly: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    eval_months = sorted(_eval_months(candidate_monthly)["month"].unique())
    selected_rows = []
    for month in eval_months:
        train = candidate_monthly.loc[candidate_monthly["month"] < month]
        score = train.groupby("candidate_id", as_index=False).agg(train_log_return=("log_return", "sum"), train_max_drawdown_pct=("max_drawdown_pct", "min"))
        score = score.sort_values(["train_max_drawdown_pct", "train_log_return"], ascending=[False, False])
        best_id = score.iloc[0]["candidate_id"]
        selected_rows.append(candidate_monthly.loc[(candidate_monthly["month"] == month) & (candidate_monthly["candidate_id"] == best_id)].iloc[0])
    selected = pd.DataFrame(selected_rows)
    return selected, _summary(selected)


def _summary(monthly: pd.DataFrame) -> dict[str, Any]:
    eval_monthly = _eval_months(monthly)
    yearly = {year: (math.exp(group["log_return"].sum()) - 1.0) * 100.0 for year, group in eval_monthly.groupby(eval_monthly["month"].str[:4])}
    target_returns = [yearly.get(year) for year in TARGET_YEARS if yearly.get(year) is not None]
    complete_returns = [yearly.get(year) for year in COMPLETE_YEARS if yearly.get(year) is not None]
    max_dd = float(eval_monthly["max_drawdown_pct"].min()) if len(eval_monthly) else 0.0
    min_target = min(target_returns) if target_returns else -999.0
    return {
        "hard_pass_target_years_relaxed": bool(len(target_returns) == len(TARGET_YEARS) and min_target > REQUIRED_YEAR_RETURN_PCT and max_dd >= MAX_DRAWDOWN_LIMIT_PCT),
        "hard_pass_complete_years_relaxed": bool(len(complete_returns) == len(COMPLETE_YEARS) and min(complete_returns) > REQUIRED_YEAR_RETURN_PCT and max_dd >= MAX_DRAWDOWN_LIMIT_PCT),
        "return_2023_pct": yearly.get("2023"),
        "return_2024_pct": yearly.get("2024"),
        "return_2025_pct": yearly.get("2025"),
        "return_2026_ytd_pct": yearly.get("2026"),
        "min_target_year_return_pct": float(min_target),
        "max_drawdown_pct": max_dd,
        "orders": int(eval_monthly["orders"].sum()) if len(eval_monthly) else 0,
        "turnover": float(eval_monthly["turnover"].sum()) if len(eval_monthly) else 0.0,
        "selected_month_count": int(eval_monthly["month"].nunique()) if len(eval_monthly) else 0,
        "selected_candidate_count": int(eval_monthly["candidate_id"].nunique()) if "candidate_id" in eval_monthly.columns and len(eval_monthly) else 0,
    }


def _eval_months(monthly: pd.DataFrame) -> pd.DataFrame:
    return monthly.loc[(monthly["month"] >= EVAL_START) & (monthly["month"] < EVAL_END_EXCLUSIVE)].copy()


def _data_quality(panel: pd.DataFrame, coverage: pd.DataFrame, from_cache: bool) -> dict[str, Any]:
    rows = []
    for symbol in SYMBOLS:
        close = panel[f"close_{symbol}"]
        valid = panel.loc[close.notna()]
        rows.append(
            {
                "symbol": symbol,
                "valid_rows": int(close.notna().sum()),
                "first_timestamp": valid["timestamp"].min().isoformat() if len(valid) else None,
                "last_timestamp": valid["timestamp"].max().isoformat() if len(valid) else None,
                "ok_months": int(coverage.loc[(coverage["symbol"] == symbol) & coverage["ok"].astype(bool), "month"].nunique()) if len(coverage) else 0,
            }
        )
    ts = pd.to_datetime(panel["timestamp"], utc=True)
    return {"from_cache": from_cache, "rows": int(len(panel)), "start_timestamp": ts.min().isoformat(), "end_timestamp": ts.max().isoformat(), "duplicate_timestamp_rows": int(ts.duplicated().sum()), "non_15m_gap_rows": int((ts.diff().dropna() != BAR_DELTA).sum()), "symbols": rows}


def _decision(static: dict[str, Any], oracle: dict[str, Any], capped_oracle: dict[str, Any], strict: dict[str, Any]) -> dict[str, Any]:
    if strict["hard_pass_target_years_relaxed"]:
        verdict = "BTC_HYPE_RELAXED_STRICT_SELECTOR_PASSES"
        reason = "严格不看未来选择器通过了目标年份收益和最大回撤门槛。"
    elif static["hard_pass_target_years_relaxed"]:
        verdict = "BTC_HYPE_STATIC_HINDSIGHT_PASSES_ONLY"
        reason = "静态候选过了放宽门槛，但这是事后选参；严格选择器没过。"
    elif oracle["hard_pass_target_years_relaxed"]:
        verdict = "BTC_HYPE_ORACLE_ONLY_PASSES"
        reason = "看答案月度oracle过了放宽门槛，但不能交易。"
    elif capped_oracle["hard_pass_target_years_relaxed"]:
        verdict = "BTC_HYPE_DRAWDOWN_CAPPED_ORACLE_ONLY_PASSES"
        reason = "看答案并强制回撤不破50%时可以拼过目标年份，但严格选择器没过，不能交易。"
    else:
        verdict = "BTC_HYPE_RELAXED_TARGET_FAILS"
        reason = "BTC+HYPE在这个候选池下，放宽后仍没有找到合格策略。"
    return {"verdict": verdict, "promote_strategy": bool(strict["hard_pass_target_years_relaxed"]), "reason": reason}


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_static_candidate"]
    oracle = summary["monthly_oracle"]
    capped_oracle = summary["monthly_oracle_drawdown_capped"]
    strict = summary["strict_selector"]
    return f"""# 41号 BTC+HYPE 放宽门槛审计

这不是实盘策略，只是按新门槛做研究。

## 新门槛

- 只用 BTCUSDT 和 HYPEUSDT。
- 去掉月月盈利要求。
- 去掉每月交易次数要求。
- 保留最大回撤不超过 `50%`。
- 目标年份 `{", ".join(TARGET_YEARS)}` 都要超过 `100%`。

## 数据

- BTC 有效行：`{summary["data"]["symbols"][0]["valid_rows"]}`
- HYPE 有效行：`{summary["data"]["symbols"][1]["valid_rows"]}`
- HYPE 第一根：`{summary["data"]["symbols"][1]["first_timestamp"]}`
- HYPE 最后一根：`{summary["data"]["symbols"][1]["last_timestamp"]}`

## 最好静态候选

- 候选：`{best["candidate_id"]}`
- 是否过目标年份放宽门槛：`{best["hard_pass_target_years_relaxed"]}`
- 2025：`{best["return_2025_pct"]:.2f}%`
- 2026 YTD：`{best["return_2026_ytd_pct"]:.2f}%`
- 最大回撤：`{best["max_drawdown_pct"]:.2f}%`

## 看答案月度 oracle

- 是否过目标年份放宽门槛：`{oracle["hard_pass_target_years_relaxed"]}`
- 2025：`{oracle["return_2025_pct"]:.2f}%`
- 2026 YTD：`{oracle["return_2026_ytd_pct"]:.2f}%`
- 最大回撤：`{oracle["max_drawdown_pct"]:.2f}%`

## 回撤限制版看答案 oracle

- 是否过目标年份放宽门槛：`{capped_oracle["hard_pass_target_years_relaxed"]}`
- 2025：`{capped_oracle["return_2025_pct"]:.2f}%`
- 2026 YTD：`{capped_oracle["return_2026_ytd_pct"]:.2f}%`
- 最大回撤：`{capped_oracle["max_drawdown_pct"]:.2f}%`
- 选择月份数：`{capped_oracle["selected_month_count"]}`

## 严格不看未来选择器

- 是否过目标年份放宽门槛：`{strict["hard_pass_target_years_relaxed"]}`
- 2025：`{strict["return_2025_pct"]:.2f}%`
- 2026 YTD：`{strict["return_2026_ytd_pct"]:.2f}%`
- 最大回撤：`{strict["max_drawdown_pct"]:.2f}%`

## 判断

`{summary["decision"]["verdict"]}`

{summary["decision"]["reason"]}
"""


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if value is None or pd.isna(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
