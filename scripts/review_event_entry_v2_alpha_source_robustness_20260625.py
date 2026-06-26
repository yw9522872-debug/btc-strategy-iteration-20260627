from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from btc_ml_trader.backtest import run_vector_backtest


ARTIFACTS = ROOT / "artifacts"
OUT_DIR = ARTIFACTS / "event_entry_v2_alpha_source_robustness_review_20260625"

ALPHA_SCRIPT = ROOT / "scripts" / "scan_event_entry_v2_alpha_source_20260625.py"
ALPHA_SUMMARY = ARTIFACTS / "event_entry_v2_alpha_source_scan_20260625" / "summary.json"
ALPHA_BEST_SIGNALS = ARTIFACTS / "event_entry_v2_alpha_source_scan_20260625" / "best_selected_signals.csv"
QUALITY_BEST_SIGNALS = (
    ARTIFACTS / "event_entry_v2_quality_cooldown_scan_20260625" / "best_selected_signals.csv"
)

BACKTEST_START = "2024-01-01"
FEE_BPS = 4.0
SLIPPAGE_BPS = 2.0
BARS_PER_YEAR = int(round(525_600 / 3))
REQUIRED_RETURN_PCT = 100.0
REQUIRED_YEARS = ["2025", "2026"]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    alpha = _load_alpha_module()
    alpha_summary = _read_json(ALPHA_SUMMARY)
    best = alpha_summary["best_candidate"]
    best_params = json.loads(best["params_json"])
    base_leverage = float(best["leverage"])

    features = alpha._add_closed_bar_features(alpha._load_feature_frame(alpha.FEATURE_FRAME))
    base_target, trigger_rows = alpha._target_for_params(features, best_params)
    saved_target_mismatches = _saved_best_mismatches(base_target)
    quality_target = _load_quality_target(features)

    variants = _build_variants(features, base_target, quality_target, base_leverage)
    rows: list[dict[str, Any]] = []
    evaluated: dict[str, tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]] = {}
    for variant in variants:
        signals = _signals(features, variant["target"], variant["variant_id"], variant["variant_kind"])
        equity, stats = run_vector_backtest(
            signals,
            fee_bps=FEE_BPS,
            slippage_bps=SLIPPAGE_BPS,
            bars_per_year=BARS_PER_YEAR,
            max_leverage=float(variant["leverage"]),
        )
        monthly = _monthly_breakdown(equity, signals)
        yearly = _yearly_breakdown(monthly)
        row = _variant_row(
            variant=variant,
            stats=stats,
            monthly=monthly,
            yearly=yearly,
            base_drawdown_pct=float(best["max_drawdown_pct"]),
            trigger_rows=trigger_rows,
        )
        rows.append(row)
        evaluated[row["variant_id"]] = (signals, equity, monthly)

    scan = pd.DataFrame(rows).sort_values(_sort_columns(), ascending=_sort_ascending()).reset_index(drop=True)
    scan.to_csv(OUT_DIR / "variant_review.csv", index=False)

    best_row = scan.iloc[0].to_dict() if not scan.empty else {}
    best_signals_path = OUT_DIR / "best_variant_signals.csv"
    best_equity_path = OUT_DIR / "best_variant_equity.csv"
    best_monthly_path = OUT_DIR / "best_variant_monthly.csv"
    best_yearly_path = OUT_DIR / "best_variant_yearly.csv"

    best_signals: pd.DataFrame | None = None
    best_equity: pd.DataFrame | None = None
    best_monthly: pd.DataFrame | None = None
    best_yearly: pd.DataFrame | None = None
    if best_row:
        best_signals, best_equity, best_monthly = evaluated[str(best_row["variant_id"])]
        best_yearly = _yearly_breakdown(best_monthly)
        best_signals.to_csv(best_signals_path, index=False)
        best_equity.to_csv(best_equity_path, index=False)
        best_monthly.to_csv(best_monthly_path, index=False)
        best_yearly.to_csv(best_yearly_path, index=False)

    cost_stress = _cost_stress(best_signals, best_row) if best_signals is not None else pd.DataFrame()
    cost_stress.to_csv(OUT_DIR / "cost_stress.csv", index=False)

    summary = _summary(
        generated_at=generated_at,
        alpha_summary=alpha_summary,
        best_params=best_params,
        scan=scan,
        best_row=best_row,
        best_monthly=best_monthly,
        best_yearly=best_yearly,
        cost_stress=cost_stress,
        saved_target_mismatches=saved_target_mismatches,
        source_forbidden_columns_dropped=features.attrs.get("dropped_forbidden_columns", []),
        best_signals_path=best_signals_path if best_signals is not None else None,
    )
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": summary["status"],
                "review_rows": summary["review_rows"],
                "yearly_gate_pass_variants": summary["yearly_gate_pass_variants"],
                "lower_drawdown_yearly_gate_pass_variants": summary[
                    "lower_drawdown_yearly_gate_pass_variants"
                ],
                "best_variant": summary["best_variant"],
                "cost_stress": summary["cost_stress_summary"],
                "candidate_ready": summary["candidate_ready"],
                "entry_capable": summary["entry_capable"],
                "live_promotion": summary["live_promotion"],
                "hard_veto": summary["hard_veto"],
                "files": summary["files"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def _load_alpha_module():
    spec = importlib.util.spec_from_file_location("event_entry_v2_alpha_source_scan", ALPHA_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load alpha scan module: {ALPHA_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _saved_best_mismatches(base_target: np.ndarray) -> int | None:
    if not ALPHA_BEST_SIGNALS.exists():
        return None
    saved = pd.read_csv(ALPHA_BEST_SIGNALS, usecols=["target_position"])
    saved_target = np.sign(pd.to_numeric(saved["target_position"], errors="coerce").fillna(0.0).to_numpy(float))
    if len(saved_target) != len(base_target):
        return None
    return int(np.count_nonzero(saved_target.astype(np.int8) != base_target.astype(np.int8)))


def _load_quality_target(features: pd.DataFrame) -> np.ndarray | None:
    if not QUALITY_BEST_SIGNALS.exists():
        return None
    quality = pd.read_csv(QUALITY_BEST_SIGNALS, usecols=["timestamp", "target_position"])
    quality["timestamp"] = pd.to_datetime(quality["timestamp"], utc=True, errors="coerce")
    quality = quality.loc[quality["timestamp"].notna()].copy()
    merged = features[["timestamp"]].merge(quality, on="timestamp", how="left")
    target = np.sign(pd.to_numeric(merged["target_position"], errors="coerce").fillna(0.0).to_numpy(float))
    return target.astype(np.int8)


def _build_variants(
    features: pd.DataFrame,
    base_target: np.ndarray,
    quality_target: np.ndarray | None,
    base_leverage: float,
) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for leverage in [1.0, 1.5, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0, 3.2, 3.5]:
        variants.append(_variant("static", base_target, leverage, {"scale_source": "base_alpha"}))

    natr = features["natr_30"]
    for cap in [0.45, 0.55, 0.65, 0.75, 0.90]:
        capped = np.where(natr.le(cap).fillna(False).to_numpy(bool), base_target, 0).astype(np.int8)
        for leverage in [2.0, 2.5, 3.0, 3.5, 4.0]:
            variants.append(_variant("natr_cap", capped, leverage, {"natr_max": cap}))

    for leverage in [2.0, 2.4, 2.8, 3.0, 3.2, 3.5, 4.0]:
        for loss_cap_pct in [-8.0, -12.0, -16.0, -20.0, -25.0]:
            target = _period_loss_stop_target(features, base_target, leverage, loss_cap_pct, period="month")
            variants.append(
                _variant(
                    "monthly_loss_stop",
                    target,
                    leverage,
                    {"loss_cap_pct": loss_cap_pct, "period": "month"},
                )
            )
        for loss_cap_pct in [-2.5, -4.0, -6.0, -8.0]:
            target = _period_loss_stop_target(features, base_target, leverage, loss_cap_pct, period="day")
            variants.append(
                _variant(
                    "daily_loss_stop",
                    target,
                    leverage,
                    {"loss_cap_pct": loss_cap_pct, "period": "day"},
                )
            )

    if quality_target is not None:
        same_side = np.where((quality_target != 0) & (quality_target == base_target), base_target, 0).astype(np.int8)
        opposite_block = np.where((quality_target != 0) & (quality_target != base_target), 0, base_target).astype(np.int8)
        for leverage in [2.0, 2.5, 3.0, 3.5, 4.0]:
            variants.append(_variant("quality_same_side_mask", same_side, leverage, {"quality_mask": "same_side_only"}))
            variants.append(
                _variant("quality_opposite_block", opposite_block, leverage, {"quality_mask": "block_opposite_only"})
            )

    # Keep the original review candidate in the scan even if the caller changes the grid later.
    variants.append(_variant("base_alpha", base_target, base_leverage, {"source_candidate": "alpha_summary_best"}))
    return variants


def _variant(kind: str, target: np.ndarray, leverage: float, params: dict[str, Any]) -> dict[str, Any]:
    digest = hashlib.sha1(
        (kind + json.dumps(params, sort_keys=True) + f"_{leverage}").encode("utf-8")
    ).hexdigest()[:10]
    return {
        "variant_id": f"alpha_robust_{kind}_{digest}_lev{leverage}",
        "variant_kind": kind,
        "target": target.astype(np.int8),
        "leverage": float(leverage),
        "params": params,
    }


def _period_loss_stop_target(
    features: pd.DataFrame,
    base_target: np.ndarray,
    leverage: float,
    loss_cap_pct: float,
    *,
    period: str,
) -> np.ndarray:
    timestamps = pd.to_datetime(features["timestamp"], utc=True)
    if period == "day":
        period_values = timestamps.dt.strftime("%Y-%m-%d").to_numpy()
    elif period == "month":
        period_values = timestamps.dt.strftime("%Y-%m").to_numpy()
    else:
        raise ValueError(f"Unsupported period: {period}")

    raw_return = np.log(features["close"].astype(float)).diff().fillna(0.0).to_numpy(float)
    out = np.zeros(len(base_target), dtype=np.int8)
    cost_per_turnover = (FEE_BPS + SLIPPAGE_BPS) / 10_000.0
    cap_log = np.log(max(1e-9, 1.0 + loss_cap_pct / 100.0))
    active_period = None
    halted = False
    period_log_return = 0.0
    previous_position = 0.0
    for index, period_value in enumerate(period_values):
        if period_value != active_period:
            active_period = period_value
            halted = False
            period_log_return = 0.0
            previous_position = 0.0
        side = 0 if halted else int(base_target[index])
        out[index] = side
        position = side * leverage
        turnover = abs(position - previous_position)
        period_log_return += previous_position * raw_return[index] - turnover * cost_per_turnover
        previous_position = position
        if period_log_return <= cap_log:
            halted = True
    return out


def _signals(features: pd.DataFrame, target: np.ndarray, variant_id: str, variant_kind: str) -> pd.DataFrame:
    out = features[["timestamp", "open", "high", "low", "close"]].copy()
    out["target_position"] = target.astype(float)
    out["component"] = np.where(target != 0, f"v2_alpha_robust_{variant_kind}", "flat")
    out["entry_reason"] = np.where(target != 0, f"v2_alpha_robust_{variant_kind}", "")
    out["exit_reason"] = _exit_reasons(target)
    out["action"] = _actions(target)
    out["confidence"] = np.where(target != 0, 0.6, 1.0)
    out["data_basis"] = "event_entry_v2_alpha_source_robustness_review_closed_bar"
    out["candidate_version"] = variant_id
    return out


def _actions(target: np.ndarray) -> list[str]:
    previous = np.r_[0, target[:-1]]
    actions = []
    for old, new in zip(previous, target):
        old = int(old)
        new = int(new)
        if old == new:
            actions.append("hold")
        elif old == 0 and new == 1:
            actions.append("enter_long")
        elif old == 0 and new == -1:
            actions.append("enter_short")
        elif old == 1 and new == 0:
            actions.append("exit_long")
        elif old == -1 and new == 0:
            actions.append("exit_short")
        elif new == 1:
            actions.append("flip_long")
        elif new == -1:
            actions.append("flip_short")
        else:
            actions.append("hold")
    return actions


def _exit_reasons(target: np.ndarray) -> np.ndarray:
    previous = np.r_[0, target[:-1]]
    reasons = np.full(len(target), "", dtype=object)
    for index, (old, new) in enumerate(zip(previous, target)):
        old = int(old)
        new = int(new)
        if old != 0 and new == 0:
            reasons[index] = "robustness_filter_flatten"
        elif old != 0 and new != 0 and old != new:
            reasons[index] = "alpha_state_flip"
    return reasons


def _variant_row(
    *,
    variant: dict[str, Any],
    stats: Any,
    monthly: pd.DataFrame,
    yearly: pd.DataFrame,
    base_drawdown_pct: float,
    trigger_rows: int,
) -> dict[str, Any]:
    year_map = {str(row["year"]): float(row["compounded_return_pct"]) for _, row in yearly.iterrows()}
    y2025 = year_map.get("2025")
    y2026 = year_map.get("2026")
    yearly_gate_pass = bool(
        y2025 is not None
        and y2026 is not None
        and y2025 >= REQUIRED_RETURN_PCT
        and y2026 >= REQUIRED_RETURN_PCT
    )
    target = variant["target"]
    max_drawdown_pct = float(stats.max_drawdown_pct)
    return {
        "variant_id": variant["variant_id"],
        "variant_kind": variant["variant_kind"],
        "leverage": float(variant["leverage"]),
        **asdict(stats),
        "return_2025_pct": y2025,
        "return_2026_pct": y2026,
        "min_required_year_return_pct": min(
            y2025 if y2025 is not None else -999.0,
            y2026 if y2026 is not None else -999.0,
        ),
        "yearly_return_gate_pass": yearly_gate_pass,
        "drawdown_improved_vs_base": bool(max_drawdown_pct > base_drawdown_pct),
        "drawdown_improvement_pct_points": float(max_drawdown_pct - base_drawdown_pct),
        "active_rows": int(np.count_nonzero(target)),
        "segments": int(_segment_count(target)),
        "trigger_rows": int(trigger_rows),
        "losing_months": int((monthly["return_pct"] < 0).sum()),
        "worst_month_return_pct": float(monthly["return_pct"].min()) if not monthly.empty else None,
        "params_json": json.dumps(_json_ready(variant["params"]), ensure_ascii=False, sort_keys=True),
    }


def _cost_stress(best_signals: pd.DataFrame | None, best_row: dict[str, Any]) -> pd.DataFrame:
    if best_signals is None or not best_row:
        return pd.DataFrame()
    rows = []
    for fee_bps, slippage_bps in [(4.0, 2.0), (8.0, 4.0), (12.0, 6.0), (20.0, 10.0)]:
        equity, stats = run_vector_backtest(
            best_signals,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            bars_per_year=BARS_PER_YEAR,
            max_leverage=float(best_row["leverage"]),
        )
        monthly = _monthly_breakdown(equity, best_signals)
        yearly = _yearly_breakdown(monthly)
        year_map = {str(row["year"]): float(row["compounded_return_pct"]) for _, row in yearly.iterrows()}
        y2025 = year_map.get("2025")
        y2026 = year_map.get("2026")
        rows.append(
            {
                "fee_bps": fee_bps,
                "slippage_bps": slippage_bps,
                **asdict(stats),
                "return_2025_pct": y2025,
                "return_2026_pct": y2026,
                "yearly_return_gate_pass": bool(
                    y2025 is not None
                    and y2026 is not None
                    and y2025 >= REQUIRED_RETURN_PCT
                    and y2026 >= REQUIRED_RETURN_PCT
                ),
            }
        )
    return pd.DataFrame(rows)


def _monthly_breakdown(equity: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    eq = equity.copy()
    sig = signals.copy()
    eq["timestamp"] = pd.to_datetime(eq["timestamp"], utc=True)
    sig["timestamp"] = pd.to_datetime(sig["timestamp"], utc=True)
    eq["month"] = eq["timestamp"].dt.strftime("%Y-%m")
    sig["month"] = sig["timestamp"].dt.strftime("%Y-%m")
    monthly = eq.groupby("month").agg(
        first_equity=("equity", "first"),
        last_equity=("equity", "last"),
        min_drawdown=("drawdown", "min"),
        turnover=("turnover", "sum"),
    )
    monthly["return_pct"] = (monthly["last_equity"] / monthly["first_equity"] - 1.0) * 100.0
    entries = sig.loc[sig["action"].isin(["enter_long", "enter_short", "flip_long", "flip_short"])].groupby("month").size()
    exits = sig.loc[sig["action"].isin(["exit_long", "exit_short", "flip_long", "flip_short"])].groupby("month").size()
    monthly["entries"] = entries
    monthly["exits"] = exits
    monthly[["entries", "exits"]] = monthly[["entries", "exits"]].fillna(0).astype(int)
    monthly["drawdown_pct"] = monthly["min_drawdown"] * 100.0
    return monthly.reset_index()


def _yearly_breakdown(monthly: pd.DataFrame) -> pd.DataFrame:
    if monthly.empty:
        return pd.DataFrame()
    frame = monthly.copy()
    frame["year"] = frame["month"].str[:4]
    return frame.groupby("year").agg(
        compounded_return_pct=("return_pct", lambda values: (values.div(100.0).add(1.0).prod() - 1.0) * 100.0),
        months=("month", "count"),
        losing_months=("return_pct", lambda values: int((values < 0).sum())),
        entries=("entries", "sum"),
        exits=("exits", "sum"),
        min_monthly_return_pct=("return_pct", "min"),
        max_drawdown_pct=("drawdown_pct", "min"),
    ).reset_index()


def _summary(
    *,
    generated_at: str,
    alpha_summary: dict[str, Any],
    best_params: dict[str, Any],
    scan: pd.DataFrame,
    best_row: dict[str, Any],
    best_monthly: pd.DataFrame | None,
    best_yearly: pd.DataFrame | None,
    cost_stress: pd.DataFrame,
    saved_target_mismatches: int | None,
    source_forbidden_columns_dropped: list[str],
    best_signals_path: Path | None,
) -> dict[str, Any]:
    passing = scan.loc[scan["yearly_return_gate_pass"].fillna(False)] if not scan.empty else pd.DataFrame()
    lower_drawdown = (
        passing.loc[passing["drawdown_improved_vs_base"].fillna(False)] if not passing.empty else pd.DataFrame()
    )
    cost_pass = (
        int(cost_stress["yearly_return_gate_pass"].fillna(False).sum()) if not cost_stress.empty else 0
    )
    hard_veto = [
        "research_review_only_not_live_source",
        "entry_capable_false",
        "downstream_rebuild_not_allowed",
        "monthly_meta_late_era_rebuild_not_run",
        "observe_paper_mock_acceptance_not_run",
        "explicit_user_live_confirmation_missing",
        "LIVE_PROMOTION_NO_GO",
    ]
    if lower_drawdown.empty:
        hard_veto.append("no_lower_drawdown_variant_preserved_2025_2026_return_gate")
    else:
        hard_veto.append("lower_drawdown_variant_is_research_only")
    if cost_pass < len(cost_stress):
        hard_veto.append("cost_stress_not_fully_passed")
    hard_veto.append("walk_forward_and_no_lookahead_audit_not_sufficient_for_promotion")
    return {
        "status": "event_entry_v2_alpha_source_robustness_review_ready",
        "generated_at": generated_at,
        "research_only": True,
        "execution_ready": False,
        "execution_ready_source": False,
        "orders_generated": False,
        "orders_submitted": False,
        "live_actions_taken": False,
        "entry_capable": False,
        "candidate_ready": False,
        "downstream_rebuild_allowed": False,
        "live_promotion": "LIVE_PROMOTION_NO_GO",
        "alpha_summary": str(ALPHA_SUMMARY),
        "base_candidate": _json_ready(alpha_summary.get("best_candidate", {})),
        "base_params": _json_ready(best_params),
        "review_rows": int(len(scan)),
        "yearly_gate_pass_variants": int(len(passing)),
        "lower_drawdown_yearly_gate_pass_variants": int(len(lower_drawdown)),
        "best_variant": _json_ready(best_row),
        "best_yearly": _json_ready(best_yearly.to_dict("records") if best_yearly is not None else []),
        "best_monthly_summary": _json_ready(_monthly_summary(best_monthly) if best_monthly is not None else {}),
        "cost_stress_summary": _json_ready(_cost_stress_summary(cost_stress)),
        "yearly_return_gate": {
            "backtest_start": BACKTEST_START,
            "required_return_pct": REQUIRED_RETURN_PCT,
            "required_years": REQUIRED_YEARS,
            "decision_rule": "Reject as final if either 2025 or latest available 2026 YTD return is below 100%.",
        },
        "lineage_audit": {
            "source_forbidden_columns_dropped": source_forbidden_columns_dropped,
            "saved_best_target_recompute_mismatches": saved_target_mismatches,
            "return_timing": "position decided at bar t participates in bar t+1 return",
            "closed_bar_feature_source": str(ALPHA_SCRIPT),
        },
        "assessment": (
            "This review tests sizing and simple causal risk filters around the first closed-bar alpha source that "
            "cleared the 2025/2026 yearly return gate. It does not promote the candidate or rebuild downstream lineage."
        ),
        "hard_veto": hard_veto,
        "hashes": {
            "script_sha256": _sha256(Path(__file__)),
            "alpha_script_sha256": _sha256(ALPHA_SCRIPT),
            "alpha_summary_sha256": _sha256(ALPHA_SUMMARY),
            "best_variant_signals_sha256": _sha256(best_signals_path) if best_signals_path else None,
        },
        "files": {
            "summary": str(OUT_DIR / "summary.json"),
            "report": str(OUT_DIR / "report.md"),
            "variant_review": str(OUT_DIR / "variant_review.csv"),
            "cost_stress": str(OUT_DIR / "cost_stress.csv"),
            "best_variant_signals": str(best_signals_path) if best_signals_path else None,
            "best_variant_equity": str(OUT_DIR / "best_variant_equity.csv") if best_signals_path else None,
            "best_variant_monthly": str(OUT_DIR / "best_variant_monthly.csv") if best_signals_path else None,
            "best_variant_yearly": str(OUT_DIR / "best_variant_yearly.csv") if best_signals_path else None,
        },
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_variant"]
    lines = [
        "# Event Entry V2 Alpha Source Robustness Review",
        "",
        f"- Status: `{summary['status']}`",
        f"- Review rows: `{summary['review_rows']}`",
        f"- Yearly-gate pass variants: `{summary['yearly_gate_pass_variants']}`",
        f"- Lower-drawdown yearly-gate pass variants: `{summary['lower_drawdown_yearly_gate_pass_variants']}`",
        f"- Candidate ready: `{summary['candidate_ready']}`",
        f"- Entry capable: `{summary['entry_capable']}`",
        f"- Live promotion: `{summary['live_promotion']}`",
        "",
        "## Best Variant",
        "",
        f"- Variant: `{best.get('variant_id')}`",
        f"- Kind: `{best.get('variant_kind')}`",
        f"- Leverage: `{best.get('leverage')}`",
        f"- Total return: `{best.get('total_return_pct')}`",
        f"- 2025 return: `{best.get('return_2025_pct')}`",
        f"- 2026 return: `{best.get('return_2026_pct')}`",
        f"- Yearly gate pass: `{best.get('yearly_return_gate_pass')}`",
        f"- Max drawdown: `{best.get('max_drawdown_pct')}`",
        f"- Drawdown improvement: `{best.get('drawdown_improvement_pct_points')}`",
        f"- Exposure: `{best.get('exposure_pct')}`",
        f"- Segments: `{best.get('segments')}`",
        "",
        "## Cost Stress",
        "",
        f"- Rows: `{summary['cost_stress_summary'].get('rows')}`",
        f"- Passing rows: `{summary['cost_stress_summary'].get('passing_rows')}`",
        f"- Worst 2025 return: `{summary['cost_stress_summary'].get('worst_2025_return_pct')}`",
        f"- Worst 2026 return: `{summary['cost_stress_summary'].get('worst_2026_return_pct')}`",
        "",
        "## Guard",
        "",
    ]
    lines.extend(f"- `{item}`" for item in summary["hard_veto"])
    lines.append("")
    return "\n".join(lines)


def _sort_columns() -> list[str]:
    return [
        "yearly_return_gate_pass",
        "drawdown_improved_vs_base",
        "max_drawdown_pct",
        "min_required_year_return_pct",
        "total_return_pct",
        "annualized_sharpe",
    ]


def _sort_ascending() -> list[bool]:
    return [False, False, False, False, False, False]


def _monthly_summary(monthly: pd.DataFrame | None) -> dict[str, Any]:
    if monthly is None or monthly.empty:
        return {}
    positive = monthly.loc[monthly["return_pct"] > 0, "return_pct"].sum()
    best_month_return = float(monthly["return_pct"].max())
    return {
        "months": int(len(monthly)),
        "losing_months": int((monthly["return_pct"] < 0).sum()),
        "worst_month": str(monthly.loc[monthly["return_pct"].idxmin(), "month"]),
        "worst_month_return_pct": float(monthly["return_pct"].min()),
        "best_month": str(monthly.loc[monthly["return_pct"].idxmax(), "month"]),
        "best_month_return_pct": best_month_return,
        "best_month_share_of_positive_month_returns_pct": (
            float(best_month_return / positive * 100.0) if positive > 0 else None
        ),
    }


def _cost_stress_summary(cost_stress: pd.DataFrame) -> dict[str, Any]:
    if cost_stress.empty:
        return {"rows": 0, "passing_rows": 0}
    return {
        "rows": int(len(cost_stress)),
        "passing_rows": int(cost_stress["yearly_return_gate_pass"].fillna(False).sum()),
        "worst_2025_return_pct": float(cost_stress["return_2025_pct"].min()),
        "worst_2026_return_pct": float(cost_stress["return_2026_pct"].min()),
        "worst_max_drawdown_pct": float(cost_stress["max_drawdown_pct"].min()),
    }


def _segment_count(target: np.ndarray) -> int:
    active = target != 0.0
    previous_active = np.r_[False, active[:-1]]
    previous_target = np.r_[0.0, target[:-1]]
    starts = active & (~previous_active | (np.sign(target) != np.sign(previous_target)))
    return int(starts.sum())


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if value is pd.NA:
        return None
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    return value


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
