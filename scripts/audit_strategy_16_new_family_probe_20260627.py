from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ID = "strategy_16_new_family_probe_20260627"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID

BASELINE_15_SUMMARY = ROOT / "artifacts" / "strategy_15_unified_data_baseline_20260627" / "summary.json"
COST_PER_SIDE = 0.001
ROUND_TRIP_COST = COST_PER_SIDE * 2
BAR_DELTA = pd.Timedelta(minutes=15)

TRAIN_START_MONTH = "2020-01"
EVAL_START_MONTH = "2023-01"
EVAL_END_EXCLUSIVE = "2026-06"
COMPLETE_EVAL_YEARS = ["2023", "2024", "2025"]
PARTIAL_EVAL_YEAR = "2026"
REQUIRED_RETURN_PCT = 100.0
REQUIRED_MIN_MONTHLY_ORDERS = 10


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    baseline = json.loads(BASELINE_15_SUMMARY.read_text(encoding="utf-8"))
    if not baseline["quality"]["pass"]:
        raise RuntimeError("Strategy 15 data baseline is not ready.")

    ohlc_path = ROOT / baseline["input_files"]["combined_ohlc"]
    market = _load_market(ohlc_path)
    features = FeatureCache(market)
    candidates = _candidate_library()

    monthly_rows: list[pd.DataFrame] = []
    static_scan_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        target = _target_for_candidate(candidate, features)
        equity = _simulate_target(market, target)
        monthly = _monthly_breakdown(equity)
        monthly.insert(0, "candidate_id", candidate["candidate_id"])
        monthly.insert(1, "family", candidate["family"])
        monthly.insert(2, "rule", candidate["rule"])
        monthly_rows.append(monthly)
        static_scan_rows.append({**candidate, **_result_summary(_eval_months_only(monthly), None)})

    candidate_monthly = pd.concat(monthly_rows, ignore_index=True)
    candidate_static_scan = pd.DataFrame(static_scan_rows).sort_values(
        ["hard_pass_complete_years", "losing_eval_months", "min_monthly_return_pct", "min_complete_year_return_pct"],
        ascending=[False, True, False, False],
    )

    selectors = [
        ("all_families", None),
        ("trend", "trend"),
        ("mean_reversion", "mean_reversion"),
        ("volatility_breakout", "volatility_breakout"),
    ]
    target_cache: dict[str, np.ndarray] = {}
    selection_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    yearly_frames: list[pd.DataFrame] = []
    selector_summaries: list[dict[str, Any]] = []

    for selector_id, family in selectors:
        selections = _select_months(candidate_monthly, candidates, selector_id, family)
        selected_target = np.zeros(len(market["timestamp"]), dtype=float)
        for row in selections:
            candidate_id = row["candidate_id"]
            if candidate_id not in target_cache:
                target_cache[candidate_id] = _target_for_candidate(_candidate_by_id(candidates, candidate_id), features)
            mask = market["month"] == row["eval_month"]
            selected_target[mask] = target_cache[candidate_id][mask]

        equity = _simulate_target(market, selected_target)
        equity = equity.loc[(equity["month"] >= EVAL_START_MONTH) & (equity["month"] < EVAL_END_EXCLUSIVE)].copy()
        monthly = _monthly_breakdown(equity)
        yearly = _yearly_breakdown(monthly)
        summary = {
            "selector_id": selector_id,
            "family_filter": family or "all",
            "selected_candidate_count": int(pd.DataFrame(selections)["candidate_id"].nunique()),
            **_result_summary(monthly, yearly),
        }
        selector_summaries.append(summary)

        selections_df = pd.DataFrame(selections)
        selections_df.insert(0, "selector_id", selector_id)
        monthly.insert(0, "selector_id", selector_id)
        yearly.insert(0, "selector_id", selector_id)
        selection_frames.append(selections_df)
        monthly_frames.append(monthly)
        yearly_frames.append(yearly)

    selected_params = pd.concat(selection_frames, ignore_index=True)
    selector_monthly = pd.concat(monthly_frames, ignore_index=True)
    selector_yearly = pd.concat(yearly_frames, ignore_index=True)
    selector_summary = pd.DataFrame(selector_summaries).sort_values(
        ["hard_pass_complete_years", "losing_eval_months", "min_monthly_return_pct", "min_complete_year_return_pct"],
        ascending=[False, True, False, False],
    )

    summary = {
        "status": "strategy_16_new_family_probe_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_freeze": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Probe simple non-ret_state strategy families on the Strategy 15 USD-M futures baseline using strict expanding monthly selection.",
        "data": {
            "baseline_15_summary": _rel(BASELINE_15_SUMMARY),
            "combined_ohlc": _rel(ohlc_path),
            "start_timestamp": market["timestamp"].iloc[0].isoformat(),
            "end_timestamp": market["timestamp"].iloc[-1].isoformat(),
            "rows": int(len(market["timestamp"])),
            "train_start_month": TRAIN_START_MONTH,
            "eval_start_month": EVAL_START_MONTH,
            "eval_end_exclusive": EVAL_END_EXCLUSIVE,
            "complete_eval_years_for_annual_threshold": COMPLETE_EVAL_YEARS,
            "partial_eval_year_recorded_not_annual_threshold": PARTIAL_EVAL_YEAR,
        },
        "strict_no_future": {
            "signals_use_closed_bar_t": True,
            "position_participates_from_bar_t_plus_1": True,
            "monthly_selection_uses_only_months_before_eval_month": True,
        },
        "cost_model": {
            "cost_per_side": COST_PER_SIDE,
            "round_trip_open_close": ROUND_TRIP_COST,
        },
        "candidate_grid": _candidate_grid_summary(candidates),
        "selector_summary": _json_ready(selector_summary.to_dict("records")),
        "static_hard_pass_count": int((candidate_static_scan["hard_pass_complete_years"] == True).sum()),
        "best_selector": _json_ready(selector_summary.iloc[0].to_dict()),
        "best_static_candidate": _json_ready(candidate_static_scan.iloc[0].to_dict()),
        "decision": _decision(selector_summary.iloc[0].to_dict()),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "baseline_15_summary_sha256": _sha256(BASELINE_15_SUMMARY),
            "combined_ohlc_sha256": _sha256(ohlc_path),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "selector_summary": _rel(OUT_DIR / "selector_summary.csv"),
            "selector_monthly": _rel(OUT_DIR / "selector_monthly.csv"),
            "selector_yearly": _rel(OUT_DIR / "selector_yearly.csv"),
            "selected_params_by_month": _rel(OUT_DIR / "selected_params_by_month.csv"),
            "candidate_static_scan": _rel(OUT_DIR / "candidate_static_scan.csv"),
        },
    }

    selector_summary.to_csv(OUT_DIR / "selector_summary.csv", index=False)
    selector_monthly.to_csv(OUT_DIR / "selector_monthly.csv", index=False)
    selector_yearly.to_csv(OUT_DIR / "selector_yearly.csv", index=False)
    selected_params.to_csv(OUT_DIR / "selected_params_by_month.csv", index=False)
    candidate_static_scan.to_csv(OUT_DIR / "candidate_static_scan.csv", index=False)
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


class FeatureCache:
    def __init__(self, market: dict[str, Any]) -> None:
        self.market = market
        self.close = pd.Series(market["close"])
        self.high = pd.Series(market["high"])
        self.low = pd.Series(market["low"])
        self._ema: dict[int, pd.Series] = {}
        self._mean: dict[int, pd.Series] = {}
        self._std: dict[int, pd.Series] = {}
        self._rsi: dict[int, pd.Series] = {}
        self._atr: dict[int, pd.Series] = {}
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

    def rsi(self, window: int) -> pd.Series:
        if window not in self._rsi:
            delta = self.close.diff()
            gain = delta.clip(lower=0).rolling(window, min_periods=window).mean()
            loss = (-delta.clip(upper=0)).rolling(window, min_periods=window).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = 100.0 - (100.0 / (1.0 + rs))
            self._rsi[window] = rsi.fillna(50.0)
        return self._rsi[window]

    def atr(self, window: int) -> pd.Series:
        if window not in self._atr:
            prev_close = self.close.shift(1)
            true_range = pd.concat(
                [
                    self.high - self.low,
                    (self.high - prev_close).abs(),
                    (self.low - prev_close).abs(),
                ],
                axis=1,
            ).max(axis=1)
            self._atr[window] = true_range.rolling(window, min_periods=window).mean()
        return self._atr[window]

    def natr_bps(self, window: int) -> pd.Series:
        return self.atr(window) / self.close * 10_000.0

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

    for fast in [20, 50]:
        for slow in [100, 200]:
            if fast >= slow:
                continue
            for gap_bps in [0, 50, 100]:
                for leverage in leverages:
                    candidates.append(_candidate("trend", "ma_trend", leverage, fast=fast, slow=slow, gap_bps=gap_bps))

    for lookback in [32, 96, 192]:
        for leverage in leverages:
            candidates.append(_candidate("trend", "donchian_trend", leverage, lookback=lookback))

    for window in [14, 28]:
        for lower, upper in [(25, 75), (30, 70), (35, 65)]:
            for leverage in leverages:
                candidates.append(_candidate("mean_reversion", "rsi_reversion", leverage, window=window, lower=lower, upper=upper))

    for window in [48, 96, 192]:
        for z in [1.5, 2.0, 2.5]:
            for leverage in leverages:
                candidates.append(_candidate("mean_reversion", "bollinger_reversion", leverage, window=window, z=z))

    for atr_window in [14, 30, 60]:
        for k in [0.5, 1.0, 1.5]:
            for natr_min_bps in [0, 50]:
                for leverage in leverages:
                    candidates.append(
                        _candidate(
                            "volatility_breakout",
                            "atr_breakout",
                            leverage,
                            atr_window=atr_window,
                            k=k,
                            natr_min_bps=natr_min_bps,
                        )
                    )
    return candidates


def _candidate(family: str, rule: str, leverage: float, **params: Any) -> dict[str, Any]:
    suffix = "_".join(f"{key}{str(value).replace('.', 'p')}" for key, value in params.items())
    return {
        "candidate_id": f"{family}_{rule}_lev{str(leverage).replace('.', 'p')}_{suffix}",
        "family": family,
        "rule": rule,
        "leverage": leverage,
        **params,
    }


def _target_for_candidate(candidate: dict[str, Any], f: FeatureCache) -> np.ndarray:
    rule = candidate["rule"]
    leverage = float(candidate["leverage"])
    close = f.close
    side = pd.Series(0, index=close.index, dtype=float)

    if rule == "ma_trend":
        fast = f.ema(int(candidate["fast"]))
        slow = f.ema(int(candidate["slow"]))
        gap = float(candidate["gap_bps"]) / 10_000.0
        side = pd.Series(np.where((fast > slow * (1 + gap)) & (close > slow), 1, np.where((fast < slow * (1 - gap)) & (close < slow), -1, 0)))
    elif rule == "donchian_trend":
        high = f.donchian_high_prev(int(candidate["lookback"])).to_numpy()
        low = f.donchian_low_prev(int(candidate["lookback"])).to_numpy()
        close_arr = close.to_numpy()
        state = 0
        out = np.zeros(len(close_arr), dtype=float)
        for index, price in enumerate(close_arr):
            if np.isfinite(high[index]) and price > high[index]:
                state = 1
            elif np.isfinite(low[index]) and price < low[index]:
                state = -1
            out[index] = state
        side = pd.Series(out)
    elif rule == "rsi_reversion":
        rsi = f.rsi(int(candidate["window"]))
        side = pd.Series(np.where(rsi <= float(candidate["lower"]), 1, np.where(rsi >= float(candidate["upper"]), -1, 0)))
    elif rule == "bollinger_reversion":
        window = int(candidate["window"])
        z = (close - f.mean(window)) / f.std(window).replace(0, np.nan)
        threshold = float(candidate["z"])
        side = pd.Series(np.where(z <= -threshold, 1, np.where(z >= threshold, -1, 0)))
    elif rule == "atr_breakout":
        atr_window = int(candidate["atr_window"])
        threshold = float(candidate["k"]) * f.atr(atr_window)
        natr_ok = f.natr_bps(atr_window) >= float(candidate["natr_min_bps"])
        move = close.diff()
        side = pd.Series(np.where((move > threshold) & natr_ok, 1, np.where((move < -threshold) & natr_ok, -1, 0)))
    else:
        raise ValueError(f"Unknown rule: {rule}")

    return np.nan_to_num(side.to_numpy(dtype=float), nan=0.0) * leverage


def _load_market(path: Path) -> dict[str, Any]:
    frame = pd.read_csv(path)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    diffs = frame["timestamp"].diff().dropna()
    if int((diffs != BAR_DELTA).sum()) != 0:
        raise ValueError("Baseline has non-15m gaps.")
    for col in ["open", "high", "low", "close"]:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    return {
        "timestamp": frame["timestamp"],
        "open": frame["open"].to_numpy(dtype=float),
        "high": frame["high"].to_numpy(dtype=float),
        "low": frame["low"].to_numpy(dtype=float),
        "close": frame["close"].to_numpy(dtype=float),
        "raw_return": np.log(frame["close"]).diff().fillna(0.0).to_numpy(dtype=float),
        "month": frame["timestamp"].dt.strftime("%Y-%m").to_numpy(),
    }


def _simulate_target(market: dict[str, Any], target: np.ndarray) -> pd.DataFrame:
    target = np.nan_to_num(target.astype(float), nan=0.0)
    active = np.roll(target, 1)
    active[0] = 0.0
    turnover = np.abs(target - np.r_[0.0, target[:-1]])
    order_count = (turnover > 1e-12).astype(int)
    cost = turnover * COST_PER_SIDE
    strategy_lr = active * market["raw_return"] - cost
    equity = np.exp(np.cumsum(strategy_lr))
    drawdown = equity / np.maximum.accumulate(equity) - 1.0
    if len(target) > 1 and not np.allclose(active[1:], target[:-1]):
        raise AssertionError("Timing check failed: active position must lag target by one bar.")
    return pd.DataFrame(
        {
            "timestamp": market["timestamp"],
            "month": market["month"],
            "close": market["close"],
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


def _yearly_breakdown(monthly: pd.DataFrame) -> pd.DataFrame:
    out = monthly.copy()
    out["year"] = out["month"].str[:4]
    return (
        out.groupby("year", as_index=False)
        .agg(
            log_return=("log_return", "sum"),
            cost_log=("cost_log", "sum"),
            turnover=("turnover", "sum"),
            orders_sum=("orders", "sum"),
            months=("month", "count"),
            losing_months=("return_pct", lambda values: int((values <= 0).sum())),
            min_monthly_return_pct=("return_pct", "min"),
            min_monthly_orders=("orders", "min"),
            max_drawdown_pct=("max_drawdown_pct", "min"),
        )
        .assign(compounded_return_pct=lambda df: (np.exp(df["log_return"]) - 1.0) * 100.0)
    )


def _select_months(
    candidate_monthly: pd.DataFrame,
    candidates: list[dict[str, Any]],
    selector_id: str,
    family: str | None,
) -> list[dict[str, Any]]:
    meta = pd.DataFrame(candidates)
    if family:
        candidate_ids = set(meta.loc[meta["family"] == family, "candidate_id"])
    else:
        candidate_ids = set(meta["candidate_id"])
    eval_months = sorted(
        month
        for month in candidate_monthly["month"].unique()
        if EVAL_START_MONTH <= str(month) < EVAL_END_EXCLUSIVE
    )
    selections: list[dict[str, Any]] = []
    subset = candidate_monthly.loc[candidate_monthly["candidate_id"].isin(candidate_ids)].copy()
    for eval_month in eval_months:
        train = subset.loc[(subset["month"] >= TRAIN_START_MONTH) & (subset["month"] < eval_month)]
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
        )
        score["train_return_pct"] = (np.exp(score["train_log_return"]) - 1.0) * 100.0
        score["train_hard_ok"] = (
            (score["train_return_pct"] > REQUIRED_RETURN_PCT)
            & (score["train_losing_months"] == 0)
            & (score["train_min_monthly_orders"] >= REQUIRED_MIN_MONTHLY_ORDERS)
        )
        score = score.merge(meta, on="candidate_id", how="left")
        score = score.sort_values(
            [
                "train_hard_ok",
                "train_losing_months",
                "train_min_monthly_return_pct",
                "train_return_pct",
                "train_min_monthly_orders",
                "train_turnover",
                "leverage",
                "candidate_id",
            ],
            ascending=[False, True, False, False, False, True, True, True],
        )
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
                **{key: value for key, value in best.items() if key.startswith("train_")},
                "eval_static_return_pct": eval_row["return_pct"],
                "eval_static_orders": eval_row["orders"],
                "eval_static_turnover": eval_row["turnover"],
            }
        )
    return selections


def _candidate_by_id(candidates: list[dict[str, Any]], candidate_id: str) -> dict[str, Any]:
    for candidate in candidates:
        if candidate["candidate_id"] == candidate_id:
            return candidate
    raise KeyError(candidate_id)


def _eval_months_only(monthly: pd.DataFrame) -> pd.DataFrame:
    return monthly.loc[(monthly["month"] >= EVAL_START_MONTH) & (monthly["month"] < EVAL_END_EXCLUSIVE)].copy()


def _result_summary(monthly: pd.DataFrame, yearly: pd.DataFrame | None) -> dict[str, Any]:
    if yearly is None:
        yearly = _yearly_breakdown(monthly)
    yearly_by_year = {str(row.year): row for row in yearly.itertuples()}
    complete_returns = [
        float(yearly_by_year[year].compounded_return_pct)
        for year in COMPLETE_EVAL_YEARS
        if year in yearly_by_year
    ]
    log_return = float(monthly["log_return"].sum()) if not monthly.empty else 0.0
    losing_eval_months = int((monthly["return_pct"] <= 0).sum()) if not monthly.empty else 999
    min_monthly_orders = int(monthly["orders"].min()) if not monthly.empty else 0
    min_complete_year_return = min(complete_returns) if complete_returns else -999.0
    return {
        "hard_pass_complete_years": bool(
            len(complete_returns) == len(COMPLETE_EVAL_YEARS)
            and min_complete_year_return > REQUIRED_RETURN_PCT
            and losing_eval_months == 0
            and min_monthly_orders >= REQUIRED_MIN_MONTHLY_ORDERS
        ),
        "total_eval_return_pct": float((np.exp(log_return) - 1.0) * 100.0),
        "return_2023_pct": _year_return(yearly_by_year, "2023"),
        "return_2024_pct": _year_return(yearly_by_year, "2024"),
        "return_2025_pct": _year_return(yearly_by_year, "2025"),
        "return_2026_ytd_pct": _year_return(yearly_by_year, "2026"),
        "min_complete_year_return_pct": float(min_complete_year_return),
        "losing_eval_months": losing_eval_months,
        "min_monthly_return_pct": float(monthly["return_pct"].min()) if not monthly.empty else -999.0,
        "min_monthly_orders": min_monthly_orders,
        "orders": int(monthly["orders"].sum()) if not monthly.empty else 0,
        "turnover": float(monthly["turnover"].sum()) if not monthly.empty else 0.0,
        "cost_log": float(monthly["cost_log"].sum()) if not monthly.empty else 0.0,
        "max_drawdown_pct": float(monthly["max_drawdown_pct"].min()) if not monthly.empty else 0.0,
    }


def _year_return(yearly_by_year: dict[str, Any], year: str) -> float | None:
    if year not in yearly_by_year:
        return None
    return float(yearly_by_year[year].compounded_return_pct)


def _candidate_grid_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    frame = pd.DataFrame(candidates)
    return {
        "total_candidates": int(len(frame)),
        "families": {str(key): int(value) for key, value in frame["family"].value_counts().sort_index().items()},
        "rules": {str(key): int(value) for key, value in frame["rule"].value_counts().sort_index().items()},
        "leverages": sorted(float(value) for value in frame["leverage"].unique()),
    }


def _decision(best_selector: dict[str, Any]) -> dict[str, Any]:
    hard_pass = bool(best_selector["hard_pass_complete_years"])
    return {
        "verdict": "PROMISING_NEW_FAMILY_PROBE" if hard_pass else "NO_HARD_PASS_IN_SIMPLE_NEW_FAMILY_PROBE",
        "promote_strategy": False,
        "reason": (
            "至少有一个严格逐月选择器满足完整年份、每月盈利和每月交易次数门槛。"
            if hard_pass
            else "简单新策略族在严格逐月滚动选择下没有通过全部硬门槛。"
        ),
        "next_step": (
            "如果以后升级，固化前还要重新做更宽的压力测试。"
            if hard_pass
            else "下一步更适合做上限测试，或者一次只新增一个小策略族继续探针。"
        ),
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_selector"]
    decision = summary["decision"]
    lines = [
        "# 16号新策略族可行性探针",
        "",
        "这不是固化版，也不是实盘策略。它只是在 15号统一 futures K线底座上，检查几个简单新策略族有没有继续研究价值。",
        "",
        "## 口径",
        "",
        f"- 数据：`{summary['data']['combined_ohlc']}`",
        f"- 评估：`{EVAL_START_MONTH}` 到 `2026-05`",
        f"- 手续费：开平合计 `{ROUND_TRIP_COST * 100:.2f}%`，代码里单边 `{COST_PER_SIDE}`",
        "- 时序：信号只用已收盘K线，下一根K线才吃收益；每个月只用过去月份选参数。",
        "",
        "## 最好严格选择器",
        "",
        f"- selector：`{best['selector_id']}`",
        f"- 是否硬通过：`{best['hard_pass_complete_years']}`",
        f"- 2023：`{best['return_2023_pct']:.2f}%`",
        f"- 2024：`{best['return_2024_pct']:.2f}%`",
        f"- 2025：`{best['return_2025_pct']:.2f}%`",
        f"- 2026 YTD：`{best['return_2026_ytd_pct']:.2f}%`",
        f"- 亏损月：`{best['losing_eval_months']}`",
        f"- 最差月：`{best['min_monthly_return_pct']:.2f}%`",
        f"- 最少月交易：`{best['min_monthly_orders']}`",
        f"- 最大回撤：`{best['max_drawdown_pct']:.2f}%`",
        "",
        "## 判断",
        "",
        f"`{decision['verdict']}`",
        "",
        decision["reason"],
    ]
    return "\n".join(lines) + "\n"


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, float):
        return None if np.isnan(value) else value
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
