from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ID = "strategy_39_alpha_pattern_discovery_20260629"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID

WINNERS = ROOT / "artifacts" / "strategy_38_forced_overfit_alpha_mining_20260629" / "combined_oracle_monthly.csv"
PANEL = ROOT / "artifacts" / "strategy_33_multisymbol_free_futures_strict_selector_20260629" / "multisymbol_close_panel_15m_2020_2026_05.csv.gz"
CANDIDATE_MONTHLY = ROOT / "artifacts" / "strategy_33_multisymbol_free_futures_strict_selector_20260629" / "candidate_monthly.csv"
CANDIDATE_SCAN = ROOT / "artifacts" / "strategy_33_multisymbol_free_futures_strict_selector_20260629" / "candidate_scan.csv"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    winners = pd.read_csv(WINNERS)
    winners33 = winners.loc[(winners["source_id"] == "strategy_33") & winners["symbol"].notna()].copy()
    close = _load_close()
    monthly_ret, monthly_vol = _monthly_features(close)
    feature_rows = _winner_feature_rows(winners33, monthly_ret, monthly_vol)
    feature_frame = pd.DataFrame(feature_rows)
    rule_tests = _simple_no_future_rule_tests(monthly_ret, monthly_vol)

    feature_frame.to_csv(OUT_DIR / "winner_predictive_features.csv", index=False)
    rule_tests.to_csv(OUT_DIR / "simple_rule_tests.csv", index=False)

    pattern = {
        "winner_months_with_symbol": int(len(winners33)),
        "winner_count_by_symbol_rule": _count_records(winners33, ["symbol", "rule"]),
        "winner_count_by_lookback": _value_counts(winners33["lookback"]),
        "winner_count_by_threshold_bps": _value_counts(winners33["threshold_bps"]),
        "winner_count_by_leverage": _value_counts(winners33["leverage"]),
        "prior_rank_stats": _rank_stats(feature_frame),
        "best_simple_rule_tests": _records(rule_tests.head(10)),
    }
    summary = {
        "status": "strategy_39_alpha_pattern_discovery_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "purpose": "Explain Strategy 38 hindsight winners and test whether the visible pattern transfers to simple no-future rules.",
        "method": {
            "new_market_data_downloaded": False,
            "new_trade_rules_added": False,
            "source": "Strategy 38 winners plus Strategy 33 candidate monthly table and close panel.",
            "warning": "The discovered pattern is selected after seeing history. Rule tests are no-future, but this meta-choice is still research.",
        },
        "pattern": pattern,
        "decision": {
            "verdict": "ALPHA_PATTERN_FOUND_BUT_SIMPLE_SELECTOR_STILL_FAILS",
            "promote_strategy": False,
            "alpha_pattern": "历史赢家集中在多币种山寨币、4倍、单币动量/反转，尤其是近期波动或涨跌幅靠前的币。",
            "why_not_tradeable_yet": "把这个规律改成月初不看未来的简单选择器后，2025/2026不能同时盈利。",
            "next_step": "若继续，应只围绕这个规律找提前识别信号，例如 funding/premium/成交流/持仓量，而不是继续扩普通K线小规则。",
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "winner_predictive_features": _rel(OUT_DIR / "winner_predictive_features.csv"),
            "simple_rule_tests": _rel(OUT_DIR / "simple_rule_tests.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def _load_close() -> pd.DataFrame:
    panel = pd.read_csv(PANEL)
    panel["timestamp"] = pd.to_datetime(panel["timestamp"], utc=True)
    cols = [c for c in panel.columns if c.startswith("close_")]
    close = panel.set_index("timestamp")[cols].rename(columns=lambda c: c.replace("close_", ""))
    return close


def _monthly_features(close: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    period = close.index.to_period("M")
    monthly_ret = (close.groupby(period).last() / close.groupby(period).first() - 1.0) * 100.0
    monthly_vol = close.pct_change(fill_method=None).groupby(period).std() * math.sqrt(30 * 24 * 4) * 100.0
    return monthly_ret, monthly_vol


def _winner_feature_rows(winners: pd.DataFrame, monthly_ret: pd.DataFrame, monthly_vol: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in winners.itertuples(index=False):
        month = pd.Period(row.month, freq="M")
        symbol = str(row.symbol)
        out = {
            "month": str(month),
            "symbol": symbol,
            "rule": row.rule,
            "lookback": int(row.lookback),
            "threshold_bps": int(row.threshold_bps),
            "return_pct": float(row.return_pct),
        }
        for lag in [1, 2, 3]:
            prev = month - lag
            if prev in monthly_ret.index:
                ret = monthly_ret.loc[prev].dropna()
                vol = monthly_vol.loc[prev].dropna()
                out[f"prev{lag}_ret_pct"] = float(ret[symbol])
                out[f"prev{lag}_abs_rank"] = int(ret.abs().rank(ascending=False, method="min")[symbol])
                out[f"prev{lag}_vol_rank"] = int(vol.rank(ascending=False, method="min")[symbol])
        rows.append(out)
    return rows


def _simple_no_future_rule_tests(monthly_ret: pd.DataFrame, monthly_vol: pd.DataFrame) -> pd.DataFrame:
    meta = pd.read_csv(CANDIDATE_SCAN)[["candidate_id", "family", "rule", "leverage", "lookback", "threshold_bps", "symbol"]]
    monthly = pd.read_csv(CANDIDATE_MONTHLY).merge(meta, on=["candidate_id", "family", "rule", "leverage"], how="left")
    base = monthly.loc[
        (monthly["family"] == "single_symbol")
        & (monthly["leverage"] == 4.0)
        & monthly["symbol"].notna()
        & (monthly["lookback"] == 384)
        & monthly["threshold_bps"].isin([20, 50, 100])
    ].copy()
    base = base.sort_values(["candidate_id", "month"])
    base["mean3"] = base.groupby("candidate_id")["log_return"].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())

    configs = [
        ("prev_vol_top2_momentum", "prev_vol", 2, ["symbol_momentum"], 0.0),
        ("prev_vol_top2_reversal", "prev_vol", 2, ["symbol_reversal"], 0.0),
        ("prev_abs_top2_reversal", "prev_abs", 2, ["symbol_reversal"], 0.0),
        ("max3_abs_top2_reversal", "max3_abs", 2, ["symbol_reversal"], 0.0),
        ("max3_vol_top2_reversal", "max3_vol", 2, ["symbol_reversal"], 0.0),
        ("max3_vol_top2_reversal_strict", "max3_vol", 2, ["symbol_reversal"], 0.05),
        ("prev_vol_top2_both", "prev_vol", 2, ["symbol_momentum", "symbol_reversal"], 0.0),
    ]
    rows = []
    months = [str(m) for m in pd.period_range("2023-01", "2026-05", freq="M")]
    for name, metric, top_n, rules, min_score in configs:
        monthly_rows = []
        for month in months:
            symbols = _top_symbols(pd.Period(month, freq="M"), metric, top_n, monthly_ret, monthly_vol)
            picks = base.loc[
                (base["month"] == month)
                & base["symbol"].isin(symbols)
                & base["rule"].isin(rules)
                & (base["orders"] >= 10)
                & (base["mean3"] >= min_score)
            ].sort_values("mean3", ascending=False).head(1)
            if picks.empty:
                monthly_rows.append({"month": month, "log_return": 0.0, "return_pct": 0.0, "orders": 0})
            else:
                lr = float(picks["log_return"].mean())
                monthly_rows.append({"month": month, "log_return": lr, "return_pct": (math.exp(lr) - 1.0) * 100.0, "orders": int(picks["orders"].sum())})
        frame = pd.DataFrame(monthly_rows)
        traded = frame.loc[frame["orders"] > 0]
        year = {yr: (math.exp(g["log_return"].sum()) - 1.0) * 100.0 for yr, g in frame.groupby(frame["month"].str[:4])}
        rows.append(
            {
                "rule_test": name,
                "return_2023_pct": year.get("2023", 0.0),
                "return_2024_pct": year.get("2024", 0.0),
                "return_2025_pct": year.get("2025", 0.0),
                "return_2026_ytd_pct": year.get("2026", 0.0),
                "traded_months": int((frame["orders"] > 0).sum()),
                "losing_traded_months": int((traded["return_pct"] <= 0).sum()),
                "orders": int(frame["orders"].sum()),
                "min_traded_return_pct": float(traded["return_pct"].min()) if len(traded) else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values(["return_2025_pct", "return_2026_ytd_pct"], ascending=[False, False])


def _top_symbols(month: pd.Period, metric: str, top_n: int, monthly_ret: pd.DataFrame, monthly_vol: pd.DataFrame) -> set[str]:
    prev = [month - i for i in [1, 2, 3] if month - i in monthly_ret.index]
    if metric == "prev_vol":
        score = monthly_vol.loc[month - 1]
    elif metric == "prev_abs":
        score = monthly_ret.loc[month - 1].abs()
    elif metric == "max3_abs":
        score = monthly_ret.loc[prev].abs().max()
    elif metric == "max3_vol":
        score = monthly_vol.loc[prev].max()
    else:
        raise ValueError(metric)
    return set(score.dropna().sort_values(ascending=False).head(top_n).index)


def _rank_stats(frame: pd.DataFrame) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    for prefix in ["prev1", "prev2", "prev3"]:
        for field in ["abs_rank", "vol_rank"]:
            col = f"{prefix}_{field}"
            values = frame[col].dropna()
            stats[col] = {
                "median": float(values.median()),
                "top3_pct": float((values <= 3).mean() * 100.0),
                "top5_pct": float((values <= 5).mean() * 100.0),
            }
    return stats


def _count_records(frame: pd.DataFrame, cols: list[str]) -> list[dict[str, Any]]:
    return _records(frame.groupby(cols, dropna=False).size().reset_index(name="months").sort_values("months", ascending=False))


def _value_counts(series: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in series.value_counts().sort_index().items()}


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(frame.replace({np.nan: None}).to_json(orient="records", force_ascii=False))


def _render_report(summary: dict[str, Any]) -> str:
    stats = summary["pattern"]["prior_rank_stats"]
    best = summary["pattern"]["best_simple_rule_tests"][0]
    return f"""# 39号 Alpha 规律挖掘

这不是策略，不能交易。它把38号的看答案赢家拆开，看能不能找到规律。

## 发现的规律

- 历史赢家主要是多币种山寨币，不是 BTC 单币。
- 赢家集中在 `4倍`、`single_symbol`、`symbol_momentum/symbol_reversal`。
- `384` 根15分钟窗口最多，说明约4天左右的强弱变化最重要。
- 常见币种是 AVAX、SOL、LINK、XRP、DOGE、ADA、ETH。
- 赢家币在上月或近几个月通常已经很活跃：
  - 上月涨跌幅绝对值排前5：`{stats["prev1_abs_rank"]["top5_pct"]:.1f}%`
  - 上月波动率排前5：`{stats["prev1_vol_rank"]["top5_pct"]:.1f}%`
  - 三个月前波动率排前5：`{stats["prev3_vol_rank"]["top5_pct"]:.1f}%`

通俗说：真正有肉的地方，是最近已经很活跃的山寨币，然后做短周期动量或反转。

## 搬到不看未来后的结果

测试了几个简单规则：只用月初以前的数据，选前月/前三月最活跃的币，再选384窗口、4倍、动量或反转。

最好的一条简单规则：

- 规则：`{best["rule_test"]}`
- 2023：`{best["return_2023_pct"]:.2f}%`
- 2024：`{best["return_2024_pct"]:.2f}%`
- 2025：`{best["return_2025_pct"]:.2f}%`
- 2026 YTD：`{best["return_2026_ytd_pct"]:.2f}%`
- 交易月份：`{best["traded_months"]}`
- 亏损交易月份：`{best["losing_traded_months"]}`

## 判断

`{summary["decision"]["verdict"]}`

我们已经找到了历史赢家的形状：近期高波动山寨币的4倍动量/反转。

但只用免费K线和简单月初选择，还不能把它稳定变成赚钱策略。下一步不要继续扩普通K线规则，而要找能提前判断“哪个热币本月会延续还是反转”的数据，比如 funding、premium、成交流或持仓量。
"""


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
