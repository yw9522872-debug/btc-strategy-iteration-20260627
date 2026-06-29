from __future__ import annotations

import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_42_btc_hype_state_predictability_20260629"
SOURCE_41 = ROOT / "artifacts" / "strategy_41_btc_hype_relaxed_drawdown_20260629"
SYMBOLS = ["BTCUSDT", "HYPEUSDT"]
MONTHS = [str(p) for p in pd.period_range("2025-06", "2026-05", freq="M")]
BASE = "https://fapi.binance.com"
START_MS = int(pd.Timestamp("2025-05-01T00:00:00Z").timestamp() * 1000)
END_MS = int(pd.Timestamp("2026-06-01T00:00:00Z").timestamp() * 1000)
INTERVAL_MS = 15 * 60 * 1000


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scan = pd.read_csv(SOURCE_41 / "candidate_scan.csv")
    monthly = pd.read_csv(SOURCE_41 / "candidate_monthly.csv").merge(
        scan[["candidate_id", "symbol", "lookback", "threshold_bps"]], on="candidate_id", how="left"
    )
    oracle = pd.read_csv(SOURCE_41 / "oracle_drawdown_capped_monthly.csv")
    klines = _load_or_fetch_klines()
    funding = _load_or_fetch_funding()
    premium = _load_or_fetch_series("premiumIndexKlines", "premium_close")
    mark = _load_or_fetch_series("markPriceKlines", "mark_close")

    features = _month_symbol_features(klines, funding, premium, mark)
    scored = _score_candidates(scan, monthly, features)
    topk, strict, retention = _evaluate(scored, monthly, oracle)

    features.to_csv(OUT_DIR / "month_symbol_features.csv", index=False)
    scored.to_csv(OUT_DIR / "candidate_scores.csv", index=False)
    topk.to_csv(OUT_DIR / "topk_oracle_monthly.csv", index=False)
    strict.to_csv(OUT_DIR / "strict_top1_monthly.csv", index=False)
    retention.to_csv(OUT_DIR / "retention_by_month.csv", index=False)

    summary = _summary(topk, strict, retention)
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _load_or_fetch_klines() -> pd.DataFrame:
    path = OUT_DIR / "btc_hype_15m_klines_rest_2025_05_2026_05.csv.gz"
    if path.exists():
        df = pd.read_csv(path)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="mixed")
        return df
    frames = []
    for symbol in SYMBOLS:
        rows = _paged_klines("/fapi/v1/klines", {"symbol": symbol, "interval": "15m"}, START_MS, END_MS)
        names = [
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trades",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ]
        df = pd.DataFrame(rows, columns=names)
        if df.empty:
            continue
        for col in ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_quote"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["trades"] = pd.to_numeric(df["trades"], errors="coerce")
        df["timestamp"] = pd.to_datetime(pd.to_numeric(df["open_time"]), unit="ms", utc=True)
        df["symbol"] = symbol
        frames.append(df[["timestamp", "symbol", "close", "quote_volume", "trades", "taker_buy_quote"]])
    out = pd.concat(frames, ignore_index=True).sort_values(["symbol", "timestamp"])
    out.to_csv(path, index=False)
    return out


def _load_or_fetch_funding() -> pd.DataFrame:
    path = OUT_DIR / "btc_hype_funding_rate_2025_05_2026_05.csv"
    if path.exists():
        df = pd.read_csv(path)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="mixed")
        return df
    rows = []
    for symbol in SYMBOLS:
        cursor = START_MS
        while cursor < END_MS:
            data = _get_json("/fapi/v1/fundingRate", {"symbol": symbol, "startTime": cursor, "endTime": END_MS, "limit": 1000})
            if not data:
                cursor += 7 * 24 * 60 * 60 * 1000
                continue
            for row in data:
                rows.append({"timestamp": pd.to_datetime(row["fundingTime"], unit="ms", utc=True), "symbol": symbol, "funding_rate": float(row["fundingRate"])})
            next_cursor = int(data[-1]["fundingTime"]) + 1
            if next_cursor <= cursor:
                break
            cursor = next_cursor
            time.sleep(0.05)
    out = pd.DataFrame(rows).drop_duplicates(["timestamp", "symbol"]).sort_values(["symbol", "timestamp"])
    out.to_csv(path, index=False)
    return out


def _load_or_fetch_series(endpoint: str, value_name: str) -> pd.DataFrame:
    path = OUT_DIR / f"btc_hype_{endpoint}_15m_2025_05_2026_05.csv.gz"
    if path.exists():
        df = pd.read_csv(path)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, format="mixed")
        return df
    frames = []
    for symbol in SYMBOLS:
        rows = _paged_klines(f"/fapi/v1/{endpoint}", {"symbol": symbol, "interval": "15m"}, START_MS, END_MS)
        df = pd.DataFrame(rows)
        if df.empty:
            continue
        frames.append(
            pd.DataFrame(
                {
                    "timestamp": pd.to_datetime(pd.to_numeric(df.iloc[:, 0]), unit="ms", utc=True),
                    "symbol": symbol,
                    value_name: pd.to_numeric(df.iloc[:, 4], errors="coerce"),
                }
            )
        )
    out = pd.concat(frames, ignore_index=True).drop_duplicates(["timestamp", "symbol"]).sort_values(["symbol", "timestamp"])
    out.to_csv(path, index=False)
    return out


def _paged_klines(path: str, params: dict[str, Any], start_ms: int, end_ms: int) -> list[list[Any]]:
    rows: list[list[Any]] = []
    cursor = start_ms
    while cursor < end_ms:
        data = _get_json(path, {**params, "startTime": cursor, "endTime": min(end_ms, cursor + INTERVAL_MS * 1499), "limit": 1500})
        if not data:
            cursor += INTERVAL_MS * 1500
            continue
        rows.extend(data)
        next_cursor = int(data[-1][0]) + INTERVAL_MS
        cursor = max(next_cursor, cursor + INTERVAL_MS)
        time.sleep(0.03)
    return rows


def _get_json(path: str, params: dict[str, Any]) -> Any:
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise
            time.sleep(1.0 + attempt)


def _month_symbol_features(klines: pd.DataFrame, funding: pd.DataFrame, premium: pd.DataFrame, mark: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month in MONTHS:
        start = pd.Timestamp(f"{month}-01T00:00:00Z")
        for symbol in SYMBOLS:
            k = klines[(klines["symbol"] == symbol) & (klines["timestamp"] < start)]
            f = funding[(funding["symbol"] == symbol) & (funding["timestamp"] < start)]
            p = premium[(premium["symbol"] == symbol) & (premium["timestamp"] < start)]
            m = mark[(mark["symbol"] == symbol) & (mark["timestamp"] < start)]
            row = {"month": month, "symbol": symbol}
            for days in [7, 30]:
                since = start - pd.Timedelta(days=days)
                kk = k[k["timestamp"] >= since]
                ff = f[f["timestamp"] >= since]
                pp = p[p["timestamp"] >= since]
                mm = m[m["timestamp"] >= since]
                returns = np.log(kk["close"] / kk["close"].shift(1)).dropna() if len(kk) else pd.Series(dtype=float)
                quote = kk["quote_volume"].sum() if len(kk) else np.nan
                taker = kk["taker_buy_quote"].sum() if len(kk) else np.nan
                row[f"ret_{days}d"] = math.log(kk["close"].iloc[-1] / kk["close"].iloc[0]) if len(kk) > 1 else np.nan
                row[f"abs_ret_{days}d"] = abs(row[f"ret_{days}d"]) if pd.notna(row[f"ret_{days}d"]) else np.nan
                row[f"rv_{days}d"] = float(returns.std() * math.sqrt(len(returns))) if len(returns) else np.nan
                row[f"quote_{days}d"] = float(quote) if pd.notna(quote) else np.nan
                row[f"taker_imb_{days}d"] = float((2.0 * taker - quote) / quote) if quote and quote > 0 else np.nan
                row[f"fund_sum_{days}d"] = float(ff["funding_rate"].sum()) if len(ff) else np.nan
                row[f"fund_abs_{days}d"] = abs(row[f"fund_sum_{days}d"]) if pd.notna(row[f"fund_sum_{days}d"]) else np.nan
                row[f"premium_mean_{days}d"] = float(pp["premium_close"].mean()) if len(pp) else np.nan
                row[f"premium_abs_{days}d"] = abs(row[f"premium_mean_{days}d"]) if pd.notna(row[f"premium_mean_{days}d"]) else np.nan
                row[f"mark_ret_{days}d"] = math.log(mm["mark_close"].iloc[-1] / mm["mark_close"].iloc[0]) if len(mm) > 1 else np.nan
            row["history_days"] = float((k["timestamp"].max() - k["timestamp"].min()).days) if len(k) else 0.0
            rows.append(row)
    df = pd.DataFrame(rows)
    for month, idx in df.groupby("month").groups.items():
        for col in ["abs_ret_7d", "abs_ret_30d", "rv_7d", "rv_30d", "fund_abs_7d", "fund_abs_30d", "premium_abs_7d", "premium_abs_30d", "quote_7d", "quote_30d"]:
            df.loc[idx, f"{col}_rank"] = df.loc[idx, col].rank(pct=True, na_option="bottom")
    return df


def _score_candidates(scan: pd.DataFrame, monthly: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    prior = monthly[monthly["month"].isin(MONTHS)].copy()
    prior["next_month"] = (pd.PeriodIndex(prior["month"], freq="M") + 1).astype(str)
    prior = prior[["next_month", "candidate_id", "return_pct", "max_drawdown_pct"]].rename(
        columns={"next_month": "month", "return_pct": "prev_candidate_return_pct", "max_drawdown_pct": "prev_candidate_dd_pct"}
    )
    rows = []
    feature_rows = {(r.month, r.symbol): r for r in features.itertuples(index=False)}
    for month in MONTHS:
        btc = feature_rows.get((month, "BTCUSDT"))
        hype = feature_rows.get((month, "HYPEUSDT"))
        for c in scan.itertuples(index=False):
            score = _score_one(c, btc, hype)
            rows.append({"month": month, "candidate_id": c.candidate_id, "score": score})
    out = pd.DataFrame(rows).merge(scan, on="candidate_id", how="left").merge(prior, on=["month", "candidate_id"], how="left")
    out["score"] += (out["prev_candidate_return_pct"].fillna(0.0).clip(-50, 50) / 100.0) * 0.15
    out["score"] += np.where(out["prev_candidate_dd_pct"].fillna(0.0) < -50.0, -0.5, 0.0)
    return out.sort_values(["month", "score"], ascending=[True, False])


def _score_one(c: Any, btc: Any, hype: Any) -> float:
    symbol = str(c.symbol) if pd.notna(c.symbol) else None
    leverage = float(c.leverage)
    lookback = int(c.lookback)
    if c.family == "single_symbol":
        f = hype if symbol == "HYPEUSDT" else btc
        if f is None:
            return -999.0
        hot = _get(f, "abs_ret_30d_rank") + _get(f, "rv_30d_rank") + _get(f, "fund_abs_7d_rank") + _get(f, "premium_abs_7d_rank")
        trend = _get(f, "ret_7d") + 0.5 * _get(f, "ret_30d")
        crowd = abs(_get(f, "fund_sum_7d")) * 500 + abs(_get(f, "premium_mean_7d")) * 300 + _get(f, "quote_7d_rank")
        mode = 0.0
        if c.rule == "symbol_reversal":
            mode = crowd + max(0.0, abs(trend) * 20)
        elif c.rule == "symbol_momentum":
            mode = max(0.0, abs(trend) * 20) + max(0.0, _get(f, "taker_imb_7d") * np.sign(trend)) - 0.5 * crowd
        lev_penalty = abs(leverage - (1.0 if _get(f, "rv_7d") > 0.35 else 4.0)) * 0.08
        look_bonus = 0.25 if lookback in [384, 768, 1536] else 0.0
        history_penalty = -2.0 if _get(f, "history_days") < 7 else 0.0
        return hot + mode + look_bonus + history_penalty - lev_penalty

    if btc is None or hype is None:
        return -999.0
    rel = _get(hype, "ret_30d") - _get(btc, "ret_30d")
    rel_hot = abs(rel) * 20 + abs(_get(hype, "fund_sum_7d") - _get(btc, "fund_sum_7d")) * 500
    reversal_pref = abs(_get(hype, "premium_mean_7d") - _get(btc, "premium_mean_7d")) * 300
    if c.rule == "long_weak_short_strong":
        mode = reversal_pref + max(0.0, abs(rel) * 10)
    else:
        mode = max(0.0, abs(rel) * 10) - 0.3 * reversal_pref
    return rel_hot + mode - abs(leverage - 1.0) * 0.12 + (0.2 if lookback in [384, 768, 1536] else 0.0)


def _get(row: Any, name: str) -> float:
    value = getattr(row, name, np.nan)
    return 0.0 if pd.isna(value) else float(value)


def _evaluate(scored: pd.DataFrame, monthly: pd.DataFrame, oracle: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    monthly = monthly[monthly["month"].isin(MONTHS)].copy()
    out = []
    ret = []
    for month in MONTHS:
        scores = scored[scored["month"] == month].reset_index(drop=True)
        winner = oracle.loc[oracle["month"] == month, "candidate_id"].iloc[0]
        rank = int(scores.index[scores["candidate_id"] == winner][0]) + 1 if winner in set(scores["candidate_id"]) else None
        row = {"month": month, "winner_candidate_id": winner, "winner_score_rank": rank}
        for k in [10, 20, 50]:
            ids = set(scores.head(k)["candidate_id"])
            pool = monthly[(monthly["month"] == month) & (monthly["candidate_id"].isin(ids))]
            best = pool.sort_values("log_return", ascending=False).iloc[0]
            safe_pool = pool[pool["max_drawdown_pct"] >= -50.0]
            safe_best = safe_pool.sort_values("log_return", ascending=False).iloc[0] if len(safe_pool) else _cash_row(month)
            row[f"k{k}_contains_winner"] = bool(winner in ids)
            row[f"k{k}_best_candidate_id"] = best["candidate_id"]
            row[f"k{k}_return_pct"] = float(best["return_pct"])
            row[f"k{k}_max_drawdown_pct"] = float(best["max_drawdown_pct"])
            out.append({"month": month, "k": k, "mode": "any", **best.to_dict()})
            out.append({"month": month, "k": k, "mode": "dd_capped", **safe_best.to_dict()})
        ret.append(row)
    topk = pd.DataFrame(out)
    retention = pd.DataFrame(ret)
    strict_rows = []
    for month in MONTHS:
        best_id = scored[scored["month"] == month].iloc[0]["candidate_id"]
        strict_rows.append(monthly[(monthly["month"] == month) & (monthly["candidate_id"] == best_id)].iloc[0])
    strict = pd.DataFrame(strict_rows)
    return topk, strict, retention


def _cash_row(month: str) -> pd.Series:
    return pd.Series(
        {
            "candidate_id": "cash_no_safe_candidate_in_shortlist",
            "family": "cash",
            "rule": "cash",
            "leverage": 0.0,
            "month": month,
            "log_return": 0.0,
            "turnover": 0.0,
            "orders": 0,
            "max_drawdown_pct": 0.0,
            "return_pct": 0.0,
            "symbol": None,
            "lookback": None,
            "threshold_bps": None,
        }
    )


def _summarize_monthly(df: pd.DataFrame) -> dict[str, Any]:
    yearly = {year: (math.exp(group["log_return"].sum()) - 1.0) * 100.0 for year, group in df.groupby(df["month"].str[:4])}
    return {
        "return_2025_pct": yearly.get("2025", 0.0),
        "return_2026_ytd_pct": yearly.get("2026", 0.0),
        "max_drawdown_pct": float(df["max_drawdown_pct"].min()) if len(df) else 0.0,
        "orders": int(df["orders"].sum()) if "orders" in df.columns else 0,
        "selected_candidate_count": int(df["candidate_id"].nunique()) if "candidate_id" in df.columns else 0,
    }


def _summary(topk: pd.DataFrame, strict: pd.DataFrame, retention: pd.DataFrame) -> dict[str, Any]:
    k20 = topk[(topk["k"] == 20) & (topk["mode"] == "any")].copy()
    k20_safe = topk[(topk["k"] == 20) & (topk["mode"] == "dd_capped")].copy()
    k20_summary = _summarize_monthly(k20)
    k20_safe_summary = _summarize_monthly(k20_safe)
    strict_summary = _summarize_monthly(strict)
    retention_summary = {}
    for k in [10, 20, 50]:
        retention_summary[f"k{k}_contains_winner_rate"] = float(retention[f"k{k}_contains_winner"].mean())
    verdict = "BTC_HYPE_STATE_FEATURES_FAIL_FIRST_PASS"
    if strict_summary["return_2025_pct"] > 100 and strict_summary["return_2026_ytd_pct"] > 100 and strict_summary["max_drawdown_pct"] >= -50:
        verdict = "BTC_HYPE_STATE_STRICT_TOP1_PASSES"
    elif retention_summary["k20_contains_winner_rate"] >= 0.6 and k20_safe_summary["return_2025_pct"] > 200 and k20_safe_summary["return_2026_ytd_pct"] > 150 and k20_safe_summary["max_drawdown_pct"] >= -45:
        verdict = "BTC_HYPE_STATE_SHORTLIST_HAS_UPPER_BOUND"
    return {
        "status": "strategy_42_btc_hype_state_predictability_ready",
        "strategy_id": "strategy_42_btc_hype_state_predictability_20260629",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "source": "GPT Pro suggested 42-1 predictability audit after strategy 41.",
        "gate": {"target_years": ["2025", "2026"], "required_return_pct": 100.0, "max_drawdown_limit_pct": -50.0},
        "data": {"symbols": SYMBOLS, "months": MONTHS, "rest_endpoints": ["klines", "fundingRate", "premiumIndexKlines", "markPriceKlines"]},
        "retention": retention_summary,
        "k20_shortlist_oracle": _json_ready(k20_summary),
        "k20_drawdown_capped_shortlist_oracle": _json_ready(k20_safe_summary),
        "strict_top1_selector": _json_ready(strict_summary),
        "decision": {"verdict": verdict, "promote_strategy": bool(verdict == "BTC_HYPE_STATE_STRICT_TOP1_PASSES")},
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "features": _rel(OUT_DIR / "month_symbol_features.csv"),
            "candidate_scores": _rel(OUT_DIR / "candidate_scores.csv"),
            "topk_oracle_monthly": _rel(OUT_DIR / "topk_oracle_monthly.csv"),
            "strict_top1_monthly": _rel(OUT_DIR / "strict_top1_monthly.csv"),
            "retention_by_month": _rel(OUT_DIR / "retention_by_month.csv"),
        },
    }


def _report(summary: dict[str, Any]) -> str:
    return f"""# 42号 BTC+HYPE 状态可预测性审计

本审计不是实盘策略，只检查 41号看答案赢家能不能被提前状态特征缩小范围。

## 结果

- K20 是否包含 41号安全 oracle 赢家比例：`{summary["retention"]["k20_contains_winner_rate"]:.2%}`
- K20 看答案上限 2025：`{summary["k20_shortlist_oracle"]["return_2025_pct"]:.2f}%`
- K20 看答案上限 2026 YTD：`{summary["k20_shortlist_oracle"]["return_2026_ytd_pct"]:.2f}%`
- K20 看答案上限最大回撤：`{summary["k20_shortlist_oracle"]["max_drawdown_pct"]:.2f}%`
- K20 回撤过滤上限 2025：`{summary["k20_drawdown_capped_shortlist_oracle"]["return_2025_pct"]:.2f}%`
- K20 回撤过滤上限 2026 YTD：`{summary["k20_drawdown_capped_shortlist_oracle"]["return_2026_ytd_pct"]:.2f}%`
- K20 回撤过滤上限最大回撤：`{summary["k20_drawdown_capped_shortlist_oracle"]["max_drawdown_pct"]:.2f}%`

严格 top1 状态打分：

- 2025：`{summary["strict_top1_selector"]["return_2025_pct"]:.2f}%`
- 2026 YTD：`{summary["strict_top1_selector"]["return_2026_ytd_pct"]:.2f}%`
- 最大回撤：`{summary["strict_top1_selector"]["max_drawdown_pct"]:.2f}%`

## 判断

`{summary["decision"]["verdict"]}`
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
