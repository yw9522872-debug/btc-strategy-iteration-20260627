from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ID = "strategy_40_multisymbol_funding_alpha_selector_20260629"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID

SOURCE_33 = ROOT / "artifacts" / "strategy_33_multisymbol_free_futures_strict_selector_20260629"
SOURCE_38 = ROOT / "artifacts" / "strategy_38_forced_overfit_alpha_mining_20260629"
FUNDING_PATH = OUT_DIR / "multisymbol_funding_rate_2022_12_2026_05.csv"

SYMBOLS = ["ETHUSDT", "SOLUSDT", "DOGEUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT"]
START_MONTH = pd.Period("2022-12", freq="M")
END_MONTH = pd.Period("2026-05", freq="M")
EVAL_MONTHS = [str(m) for m in pd.period_range("2023-01", "2026-05", freq="M")]
REST_URL = "https://fapi.binance.com/fapi/v1/fundingRate"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    funding = _load_or_fetch_funding()
    funding_monthly = _funding_monthly(funding)
    close = _load_close()
    monthly_ret, monthly_vol = _monthly_features(close)
    winner_funding = _winner_funding_diagnostics(funding_monthly)
    selector_tests = _selector_tests(funding_monthly, monthly_ret, monthly_vol)

    funding_monthly.to_csv(OUT_DIR / "funding_monthly_features.csv", index=False)
    winner_funding.to_csv(OUT_DIR / "winner_funding_diagnostics.csv", index=False)
    selector_tests.to_csv(OUT_DIR / "selector_tests.csv", index=False)

    best = selector_tests.iloc[0].to_dict()
    summary = {
        "status": "strategy_40_multisymbol_funding_alpha_selector_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "purpose": "Test whether funding-rate history can identify Strategy 39 hot-altcoin momentum/reversal winners before the month.",
        "method": {
            "new_market_data_downloaded": True,
            "downloaded_dataset": "Binance public USD-M futures fundingRate REST history for Strategy 39 frequent winner symbols",
            "premium_or_trade_downloads_skipped": "Funding is tiny and already directly tied to crowding. Premium/order-flow downloads are left for later only if funding helps.",
            "selection_timing": "Each evaluated month uses only prior-month funding and prior-month price/volatility features.",
        },
        "funding_quality": _funding_quality(funding),
        "winner_funding_pattern": _winner_pattern_summary(winner_funding),
        "best_selector_test": _json_ready(best),
        "selector_tests_top10": _json_ready(selector_tests.head(10).to_dict("records")),
        "decision": _decision(best),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "funding_raw": _rel(FUNDING_PATH),
            "funding_monthly_features": _rel(OUT_DIR / "funding_monthly_features.csv"),
            "winner_funding_diagnostics": _rel(OUT_DIR / "winner_funding_diagnostics.csv"),
            "selector_tests": _rel(OUT_DIR / "selector_tests.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def _load_or_fetch_funding() -> pd.DataFrame:
    if FUNDING_PATH.exists():
        frame = pd.read_csv(FUNDING_PATH)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, format="mixed")
        return frame

    frames: list[pd.DataFrame] = []
    for symbol in SYMBOLS:
        frames.append(_fetch_funding_rest(symbol))
    funding = pd.concat(frames, ignore_index=True).drop_duplicates(["symbol", "timestamp"], keep="last")
    funding = funding.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
    funding.to_csv(FUNDING_PATH, index=False)
    return funding


def _fetch_funding_rest(symbol: str) -> pd.DataFrame:
    start = int(START_MONTH.start_time.tz_localize("UTC").timestamp() * 1000)
    end = int(END_MONTH.end_time.tz_localize("UTC").timestamp() * 1000)
    rows: list[dict[str, Any]] = []
    while start <= end:
        url = f"{REST_URL}?symbol={symbol}&startTime={start}&endTime={end}&limit=1000"
        payload = _download_json(url)
        if not payload:
            break
        rows.extend(payload)
        last_time = int(payload[-1]["fundingTime"])
        next_start = last_time + 1
        if next_start <= start:
            break
        start = next_start
        time.sleep(0.05)
    return pd.DataFrame(
        {
            "symbol": symbol,
            "timestamp": pd.to_datetime([int(row["fundingTime"]) for row in rows], unit="ms", utc=True),
            "funding_interval_hours": 8,
            "funding_rate": [float(row["fundingRate"]) for row in rows],
        }
    )


def _download_json(url: str) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "strategy-40-funding-alpha-research/1.0"})
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            if attempt == 3:
                raise RuntimeError(f"Failed to download {url}: {last_error!r}") from exc
            time.sleep(1.0 + attempt)
    return []


def _funding_monthly(funding: pd.DataFrame) -> pd.DataFrame:
    frame = funding.copy()
    frame["month"] = frame["timestamp"].dt.to_period("M").astype(str)
    frame["funding_bps"] = frame["funding_rate"] * 10_000.0
    monthly = frame.groupby(["symbol", "month"], as_index=False).agg(
        funding_mean_bps=("funding_bps", "mean"),
        funding_abs_mean_bps=("funding_bps", lambda s: float(s.abs().mean())),
        funding_last_bps=("funding_bps", "last"),
        funding_min_bps=("funding_bps", "min"),
        funding_max_bps=("funding_bps", "max"),
        funding_rows=("funding_bps", "size"),
    )
    return monthly.sort_values(["symbol", "month"]).reset_index(drop=True)


def _load_close() -> pd.DataFrame:
    panel = pd.read_csv(SOURCE_33 / "multisymbol_close_panel_15m_2020_2026_05.csv.gz")
    panel["timestamp"] = pd.to_datetime(panel["timestamp"], utc=True)
    close_cols = [c for c in panel.columns if c.startswith("close_")]
    return panel.set_index("timestamp")[close_cols].rename(columns=lambda c: c.replace("close_", ""))


def _monthly_features(close: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    period = close.index.to_period("M")
    monthly_ret = (close.groupby(period).last() / close.groupby(period).first() - 1.0) * 100.0
    monthly_vol = close.pct_change(fill_method=None).groupby(period).std() * math.sqrt(30 * 24 * 4) * 100.0
    return monthly_ret, monthly_vol


def _winner_funding_diagnostics(funding_monthly: pd.DataFrame) -> pd.DataFrame:
    winners = pd.read_csv(SOURCE_38 / "combined_oracle_monthly.csv")
    winners = winners.loc[(winners["source_id"] == "strategy_33") & winners["symbol"].notna()].copy()
    rows: list[dict[str, Any]] = []
    for winner in winners.itertuples(index=False):
        prev_month = str(pd.Period(winner.month, freq="M") - 1)
        month_funding = funding_monthly.loc[funding_monthly["month"] == prev_month].copy()
        if month_funding.empty or winner.symbol not in set(month_funding["symbol"]):
            continue
        month_funding["abs_rank"] = month_funding["funding_abs_mean_bps"].rank(ascending=False, method="min")
        month_funding["mean_rank"] = month_funding["funding_mean_bps"].rank(ascending=False, method="min")
        row = month_funding.loc[month_funding["symbol"] == winner.symbol].iloc[0]
        rows.append(
            {
                "month": winner.month,
                "symbol": winner.symbol,
                "rule": winner.rule,
                "return_pct": float(winner.return_pct),
                "prev_month": prev_month,
                "prev_funding_mean_bps": float(row["funding_mean_bps"]),
                "prev_funding_abs_mean_bps": float(row["funding_abs_mean_bps"]),
                "prev_funding_abs_rank": int(row["abs_rank"]),
                "prev_funding_mean_rank": int(row["mean_rank"]),
            }
        )
    return pd.DataFrame(rows)


def _selector_tests(funding_monthly: pd.DataFrame, monthly_ret: pd.DataFrame, monthly_vol: pd.DataFrame) -> pd.DataFrame:
    scan = pd.read_csv(SOURCE_33 / "candidate_scan.csv")[["candidate_id", "family", "rule", "leverage", "lookback", "threshold_bps", "symbol"]]
    monthly = pd.read_csv(SOURCE_33 / "candidate_monthly.csv").merge(scan, on=["candidate_id", "family", "rule", "leverage"], how="left")
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
        ("hot_abs_funding_abs_reversal", "prev_abs", 3, "abs_top", 3, ["symbol_reversal"], 0.0),
        ("hot_vol_funding_abs_reversal", "prev_vol", 3, "abs_top", 3, ["symbol_reversal"], 0.0),
        ("hot_abs_positive_funding_reversal", "prev_abs", 3, "positive", 0, ["symbol_reversal"], 0.0),
        ("hot_abs_negative_funding_momentum", "prev_abs", 3, "negative", 0, ["symbol_momentum"], 0.0),
        ("funding_abs_top2_reversal", "none", 9, "abs_top", 2, ["symbol_reversal"], 0.0),
        ("funding_abs_top2_momentum", "none", 9, "abs_top", 2, ["symbol_momentum"], 0.0),
        ("hot_abs_funding_abs_both", "prev_abs", 3, "abs_top", 3, ["symbol_momentum", "symbol_reversal"], 0.0),
        ("hot_vol_funding_abs_both", "prev_vol", 3, "abs_top", 3, ["symbol_momentum", "symbol_reversal"], 0.0),
        ("hot_abs_funding_abs_reversal_strict", "prev_abs", 3, "abs_top", 3, ["symbol_reversal"], 0.05),
    ]
    results = []
    for config in configs:
        test_id, hot_metric, hot_n, funding_filter, funding_n, rules, min_mean3 = config
        month_rows = []
        for month in EVAL_MONTHS:
            symbols = _eligible_symbols(month, hot_metric, hot_n, funding_filter, funding_n, monthly_ret, monthly_vol, funding_monthly)
            picks = base.loc[
                (base["month"] == month)
                & base["symbol"].isin(symbols)
                & base["rule"].isin(rules)
                & (base["orders"] >= 10)
                & (base["mean3"] >= min_mean3)
            ].sort_values("mean3", ascending=False).head(1)
            if picks.empty:
                month_rows.append({"month": month, "log_return": 0.0, "return_pct": 0.0, "orders": 0})
            else:
                lr = float(picks["log_return"].mean())
                month_rows.append({"month": month, "log_return": lr, "return_pct": (math.exp(lr) - 1.0) * 100.0, "orders": int(picks["orders"].sum())})
        results.append({"selector_test": test_id, **_summary_from_months(pd.DataFrame(month_rows))})
    return pd.DataFrame(results).sort_values(["return_2025_pct", "return_2026_ytd_pct"], ascending=[False, False])


def _eligible_symbols(
    month: str,
    hot_metric: str,
    hot_n: int,
    funding_filter: str,
    funding_n: int,
    monthly_ret: pd.DataFrame,
    monthly_vol: pd.DataFrame,
    funding_monthly: pd.DataFrame,
) -> set[str]:
    period = pd.Period(month, freq="M")
    symbols: set[str]
    if hot_metric == "none":
        symbols = set(SYMBOLS)
    elif hot_metric == "prev_abs":
        symbols = set(monthly_ret.loc[period - 1].abs().dropna().sort_values(ascending=False).head(hot_n).index)
    elif hot_metric == "prev_vol":
        symbols = set(monthly_vol.loc[period - 1].dropna().sort_values(ascending=False).head(hot_n).index)
    else:
        raise ValueError(hot_metric)

    prev_funding = funding_monthly.loc[funding_monthly["month"] == str(period - 1)].copy()
    if prev_funding.empty:
        return set()
    if funding_filter == "abs_top":
        funded = set(prev_funding.sort_values("funding_abs_mean_bps", ascending=False).head(funding_n)["symbol"])
    elif funding_filter == "positive":
        funded = set(prev_funding.loc[prev_funding["funding_mean_bps"] > 0, "symbol"])
    elif funding_filter == "negative":
        funded = set(prev_funding.loc[prev_funding["funding_mean_bps"] < 0, "symbol"])
    else:
        raise ValueError(funding_filter)
    return symbols & funded


def _summary_from_months(frame: pd.DataFrame) -> dict[str, Any]:
    traded = frame.loc[frame["orders"] > 0]
    yearly = {year: (math.exp(group["log_return"].sum()) - 1.0) * 100.0 for year, group in frame.groupby(frame["month"].str[:4])}
    return {
        "return_2023_pct": yearly.get("2023", 0.0),
        "return_2024_pct": yearly.get("2024", 0.0),
        "return_2025_pct": yearly.get("2025", 0.0),
        "return_2026_ytd_pct": yearly.get("2026", 0.0),
        "traded_months": int((frame["orders"] > 0).sum()),
        "losing_traded_months": int((traded["return_pct"] <= 0).sum()),
        "orders": int(frame["orders"].sum()),
        "min_traded_return_pct": float(traded["return_pct"].min()) if len(traded) else 0.0,
    }


def _funding_quality(funding: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    funding = funding.copy()
    funding["month"] = funding["timestamp"].dt.to_period("M").astype(str)
    for symbol, group in funding.groupby("symbol"):
        months = sorted(group["month"].unique())
        rows.append(
            {
                "symbol": symbol,
                "rows": int(len(group)),
                "months": int(len(months)),
                "first_month": months[0] if months else None,
                "last_month": months[-1] if months else None,
                "duplicate_timestamp_rows": int(group["timestamp"].duplicated().sum()),
                "invalid_interval_rows": int((group["funding_interval_hours"] != 8).sum()),
            }
        )
    return rows


def _winner_pattern_summary(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "winner_rows_with_funding": int(len(frame)),
        "prev_funding_abs_rank_median": float(frame["prev_funding_abs_rank"].median()) if len(frame) else None,
        "prev_funding_abs_rank_top3_pct": float((frame["prev_funding_abs_rank"] <= 3).mean() * 100.0) if len(frame) else None,
        "prev_funding_mean_positive_pct": float((frame["prev_funding_mean_bps"] > 0).mean() * 100.0) if len(frame) else None,
        "by_rule": _json_ready(frame.groupby("rule").agg(
            rows=("month", "size"),
            mean_prev_funding_bps=("prev_funding_mean_bps", "mean"),
            positive_pct=("prev_funding_mean_bps", lambda s: float((s > 0).mean() * 100.0)),
            abs_rank_median=("prev_funding_abs_rank", "median"),
        ).reset_index().to_dict("records")),
    }


def _decision(best: dict[str, Any]) -> dict[str, Any]:
    target_ok = best["return_2025_pct"] > 0 and best["return_2026_ytd_pct"] > 0
    return {
        "verdict": "FUNDING_SIGNAL_WEAK_NOT_TRADEABLE" if target_ok else "FUNDING_SIGNAL_DOES_NOT_SOLVE_SELECTOR",
        "promote_strategy": False,
        "reason": "Funding gives an extra crowding clue, but the simple no-future selector still does not meet the original target.",
        "next_step": "Do not expand funding-only rules. If continuing, test premium/order-flow as the next independent early signal.",
    }


def _render_report(summary: dict[str, Any]) -> str:
    best = summary["best_selector_test"]
    pattern = summary["winner_funding_pattern"]
    return f"""# 40号多币种 Funding 提前识别审计

这不是策略，不能交易。它只检查 funding 能不能帮39号的“活跃山寨币动量/反转”规律提前选对。

## 做法

- 下载 Binance 免费 USD-M futures fundingRate REST 历史。
- 币种：ETH、SOL、DOGE、XRP、ADA、AVAX、LINK。
- 每个月只用上个月已经知道的 funding、涨跌幅和波动率。
- 不下载 premium，不下载成交流；先测最小的 funding 信号。

## Funding 对赢家的解释

- 有 funding 数据的赢家月份：`{pattern["winner_rows_with_funding"]}`
- 赢家上月 funding 绝对值排名中位数：`{pattern["prev_funding_abs_rank_median"]:.1f}`
- 赢家上月 funding 绝对值排前3比例：`{pattern["prev_funding_abs_rank_top3_pct"]:.1f}%`
- 赢家上月 funding 为正比例：`{pattern["prev_funding_mean_positive_pct"]:.1f}%`

## 不看未来选择器

最好测试：`{best["selector_test"]}`

- 2023：`{best["return_2023_pct"]:.2f}%`
- 2024：`{best["return_2024_pct"]:.2f}%`
- 2025：`{best["return_2025_pct"]:.2f}%`
- 2026 YTD：`{best["return_2026_ytd_pct"]:.2f}%`
- 交易月份：`{best["traded_months"]}`
- 亏损交易月份：`{best["losing_traded_months"]}`

## 判断

`{summary["decision"]["verdict"]}`

Funding 有一点“拥挤度”信息，但还不能把39号规律变成合格策略。

下一步如果继续，不要扩 funding-only 小规则，应测试 premium 或成交流这类更早、更细的信号。
"""


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if pd.isna(value):
        return None
    return value


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
