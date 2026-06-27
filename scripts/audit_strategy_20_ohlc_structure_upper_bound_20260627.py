from __future__ import annotations

import hashlib
import json
import sys
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


STRATEGY_ID = "strategy_20_ohlc_structure_upper_bound_20260627"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
BASELINE_15_SUMMARY = ROOT / "artifacts" / "strategy_15_unified_data_baseline_20260627" / "summary.json"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    baseline = json.loads(BASELINE_15_SUMMARY.read_text(encoding="utf-8"))
    if not baseline["quality"]["pass"]:
        raise RuntimeError("Strategy 15 data baseline is not ready.")

    ohlc_path = ROOT / baseline["input_files"]["combined_ohlc"]
    market = probe16._load_market(ohlc_path)
    features = OhlcStructureFeatures(market)
    candidates = _candidate_library()
    candidate_monthly, candidate_scan = _candidate_results(candidates, market, features)

    oracle_specs = [
        ("monthly_oracle_best_return", None, False),
        ("monthly_oracle_best_return_order10", None, True),
        ("body_structure_oracle_order10", "body_structure", True),
        ("wick_structure_oracle_order10", "wick_structure", True),
        ("range_structure_oracle_order10", "range_structure", True),
        ("volatility_structure_oracle_order10", "volatility_structure", True),
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
        "status": "strategy_20_ohlc_structure_upper_bound_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Measure a leaky monthly oracle upper bound for OHLC-only candle, range, and volatility structure features on the Strategy 15 USD-M futures baseline.",
        "source": {
            "baseline_15_summary": _rel(BASELINE_15_SUMMARY),
            "combined_ohlc": baseline["input_files"]["combined_ohlc"],
            "volume_available": False,
            "volume_note": "Strategy 15 combined baseline contains OHLC only, so Strategy 20 does not test volume features.",
        },
        "data": {
            "eval_start_month": probe16.EVAL_START_MONTH,
            "eval_end_exclusive": probe16.EVAL_END_EXCLUSIVE,
            "complete_eval_years_for_annual_threshold": probe16.COMPLETE_EVAL_YEARS,
            "partial_eval_year_recorded_not_annual_threshold": probe16.PARTIAL_EVAL_YEAR,
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
            "per_candidate_signal_timing": "Each candidate uses closed bar t OHLC values and participates from bar t+1.",
        },
        "static_hard_pass_count": int(candidate_scan["hard_pass_complete_years"].sum()),
        "best_static_candidate": _json_ready(candidate_scan.iloc[0].to_dict()),
        "oracle_summary": _json_ready(oracle_summary.to_dict("records")),
        "best_oracle": _json_ready(best_oracle),
        "decision": _decision(best_oracle),
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "baseline_15_summary_sha256": _sha256(BASELINE_15_SUMMARY),
            "combined_ohlc_sha256": _sha256(ohlc_path),
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
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


class OhlcStructureFeatures:
    def __init__(self, market: dict[str, Any]) -> None:
        self.open = pd.Series(market["open"])
        self.high = pd.Series(market["high"])
        self.low = pd.Series(market["low"])
        self.close = pd.Series(market["close"])
        self.range_abs = (self.high - self.low).replace(0, np.nan)
        self.range_bps = self.range_abs / self.close * 10_000.0
        self.body_bps = (self.close - self.open) / self.open * 10_000.0
        self.upper_wick_ratio = (self.high - pd.concat([self.open, self.close], axis=1).max(axis=1)) / self.range_abs
        self.lower_wick_ratio = (pd.concat([self.open, self.close], axis=1).min(axis=1) - self.low) / self.range_abs
        self._natr: dict[int, pd.Series] = {}

    def natr_bps(self, window: int) -> pd.Series:
        if window not in self._natr:
            prev_close = self.close.shift(1)
            true_range = pd.concat(
                [
                    self.high - self.low,
                    (self.high - prev_close).abs(),
                    (self.low - prev_close).abs(),
                ],
                axis=1,
            ).max(axis=1)
            self._natr[window] = true_range.rolling(window, min_periods=window).mean() / self.close * 10_000.0
        return self._natr[window]


def _candidate_library() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    leverages = [1.0, 2.0, 4.0]
    for body_bps in [5, 10, 20, 40]:
        for min_range_bps in [0, 25, 50]:
            for leverage in leverages:
                candidates.append(_candidate("body_structure", "body_momentum", leverage, body_bps=body_bps, min_range_bps=min_range_bps))
                candidates.append(_candidate("body_structure", "body_reversal", leverage, body_bps=body_bps, min_range_bps=min_range_bps))
    for wick_ratio in [0.4, 0.55, 0.7]:
        for min_range_bps in [0, 25, 50]:
            for leverage in leverages:
                candidates.append(_candidate("wick_structure", "wick_reversal", leverage, wick_ratio=wick_ratio, min_range_bps=min_range_bps))
    for min_range_bps in [25, 50, 100]:
        for leverage in leverages:
            candidates.append(_candidate("range_structure", "range_momentum", leverage, min_range_bps=min_range_bps))
            candidates.append(_candidate("range_structure", "range_reversal", leverage, min_range_bps=min_range_bps))
    for natr_window in [14, 60, 192]:
        for natr_bps in [25, 50, 100]:
            for leverage in leverages:
                candidates.append(_candidate("volatility_structure", "high_vol_body_momentum", leverage, natr_window=natr_window, natr_min_bps=natr_bps, body_bps=5))
                candidates.append(_candidate("volatility_structure", "high_vol_body_reversal", leverage, natr_window=natr_window, natr_min_bps=natr_bps, body_bps=5))
        for natr_bps in [25, 50]:
            for leverage in leverages:
                candidates.append(_candidate("volatility_structure", "low_vol_wick_reversal", leverage, natr_window=natr_window, natr_max_bps=natr_bps, wick_ratio=0.4))
    return candidates


def _candidate(family: str, rule: str, leverage: float, **params: Any) -> dict[str, Any]:
    suffix = "_".join(f"{key}{str(value).replace('.', 'p')}" for key, value in params.items())
    return {"candidate_id": f"{family}_{rule}_lev{str(leverage).replace('.', 'p')}_{suffix}", "family": family, "rule": rule, "leverage": leverage, **params}


def _target_for_candidate(candidate: dict[str, Any], f: OhlcStructureFeatures) -> np.ndarray:
    rule = candidate["rule"]
    leverage = float(candidate["leverage"])
    side = pd.Series(0.0, index=f.close.index)

    if rule in {"body_momentum", "body_reversal"}:
        mask = (f.body_bps.abs() >= float(candidate["body_bps"])) & (f.range_bps >= float(candidate["min_range_bps"]))
        direction = np.sign(f.body_bps)
        if rule == "body_reversal":
            direction = -direction
        side = pd.Series(np.where(mask, direction, 0.0), index=f.close.index)
    elif rule == "wick_reversal":
        side = _wick_reversal_side(f, float(candidate["wick_ratio"]), f.range_bps >= float(candidate["min_range_bps"]))
    elif rule in {"range_momentum", "range_reversal"}:
        mask = f.range_bps >= float(candidate["min_range_bps"])
        direction = np.sign(f.body_bps)
        if rule == "range_reversal":
            direction = -direction
        side = pd.Series(np.where(mask, direction, 0.0), index=f.close.index)
    elif rule in {"high_vol_body_momentum", "high_vol_body_reversal"}:
        mask = (f.natr_bps(int(candidate["natr_window"])) >= float(candidate["natr_min_bps"])) & (f.body_bps.abs() >= float(candidate["body_bps"]))
        direction = np.sign(f.body_bps)
        if rule == "high_vol_body_reversal":
            direction = -direction
        side = pd.Series(np.where(mask, direction, 0.0), index=f.close.index)
    elif rule == "low_vol_wick_reversal":
        mask = f.natr_bps(int(candidate["natr_window"])) <= float(candidate["natr_max_bps"])
        side = _wick_reversal_side(f, float(candidate["wick_ratio"]), mask)
    else:
        raise ValueError(f"Unknown rule: {rule}")

    return np.nan_to_num(side.to_numpy(dtype=float), nan=0.0) * leverage


def _wick_reversal_side(f: OhlcStructureFeatures, wick_ratio: float, mask: pd.Series) -> pd.Series:
    long_signal = (f.lower_wick_ratio >= wick_ratio) & (f.lower_wick_ratio > f.upper_wick_ratio) & mask
    short_signal = (f.upper_wick_ratio >= wick_ratio) & (f.upper_wick_ratio > f.lower_wick_ratio) & mask
    return pd.Series(np.where(long_signal, 1.0, np.where(short_signal, -1.0, 0.0)), index=f.close.index)


def _candidate_results(
    candidates: list[dict[str, Any]], market: dict[str, Any], features: OhlcStructureFeatures
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
            "verdict": "OHLC_STRUCTURE_UPPER_BOUND_HAS_MONTHLY_PIECES",
            "promote_strategy": False,
            "reason": "看答案的OHLC结构月度上限能过硬门槛，但它不能交易。",
            "next_step": "再做严格逐月选择器，确认这些月份能不能不用未来信息提前选中。",
        }
    return {
        "verdict": "OHLC_STRUCTURE_UPPER_BOUND_FAILS",
        "promote_strategy": False,
        "reason": "即使每个月事后挑最好OHLC结构候选，也过不了硬门槛。",
        "next_step": "不要把这批OHLC结构规则升级候选；需要换特征源或重新审视每月10单硬条件。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_oracle"]
    decision = summary["decision"]
    return f"""# 20号 OHLC结构上限测试

这不是策略，不能交易。它只看“如果事后知道每个月哪个OHLC结构候选最好”，这批候选理论上够不够。

## 口径

- 数据：`{summary["source"]["combined_ohlc"]}`
- 评估：`{probe16.EVAL_START_MONTH}` 到 `2026-05`
- 手续费：开平合计 `{probe16.ROUND_TRIP_COST * 100:.2f}%`
- 成交量：15号底座没有成交量，本测试只用 open/high/low/close。
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
