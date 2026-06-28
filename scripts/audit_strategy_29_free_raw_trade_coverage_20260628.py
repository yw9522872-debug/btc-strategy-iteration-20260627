from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ID = "strategy_29_free_raw_trade_coverage_audit_20260628"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID

SYMBOL = "BTCUSDT"
START_MONTH = pd.Period("2020-01", freq="M")
END_MONTH = pd.Period("2026-05", freq="M")
USER_AGENT = "strategy-29-free-raw-trade-coverage-audit/1.0"

DATASETS = [
    {
        "dataset_id": "futures_um_aggTrades",
        "role": "main",
        "description": "USD-M futures aggregate trades; rebuild aggressive flow with isBuyerMaker.",
        "url": "https://data.binance.vision/data/futures/um/monthly/aggTrades/{symbol}/{symbol}-aggTrades-{yyyy}-{mm}.zip",
    },
    {
        "dataset_id": "spot_aggTrades",
        "role": "main",
        "description": "Spot aggregate trades; spot lead/lag against USD-M futures.",
        "url": "https://data.binance.vision/data/spot/monthly/aggTrades/{symbol}/{symbol}-aggTrades-{yyyy}-{mm}.zip",
    },
    {
        "dataset_id": "futures_um_trades",
        "role": "main_optional",
        "description": "USD-M futures raw trades; heavier alternative to aggTrades.",
        "url": "https://data.binance.vision/data/futures/um/monthly/trades/{symbol}/{symbol}-trades-{yyyy}-{mm}.zip",
    },
    {
        "dataset_id": "spot_trades",
        "role": "main_optional",
        "description": "Spot raw trades; heavier alternative to aggTrades.",
        "url": "https://data.binance.vision/data/spot/monthly/trades/{symbol}/{symbol}-trades-{yyyy}-{mm}.zip",
    },
    {
        "dataset_id": "futures_um_1m_klines",
        "role": "support",
        "description": "USD-M futures 1m klines for validation and low-cost features.",
        "url": "https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/1m/{symbol}-1m-{yyyy}-{mm}.zip",
    },
    {
        "dataset_id": "spot_1m_klines",
        "role": "support",
        "description": "Spot 1m klines for spot-perp spread and validation.",
        "url": "https://data.binance.vision/data/spot/monthly/klines/{symbol}/1m/{symbol}-1m-{yyyy}-{mm}.zip",
    },
    {
        "dataset_id": "futures_um_fundingRate",
        "role": "filter",
        "description": "Funding history; use only after fundingTime is known.",
        "url": "https://data.binance.vision/data/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{yyyy}-{mm}.zip",
    },
    {
        "dataset_id": "futures_um_markPriceKlines_1m",
        "role": "filter",
        "description": "Mark price 1m klines for mark/index divergence.",
        "url": "https://data.binance.vision/data/futures/um/monthly/markPriceKlines/{symbol}/1m/{symbol}-1m-{yyyy}-{mm}.zip",
    },
    {
        "dataset_id": "futures_um_indexPriceKlines_1m",
        "role": "filter",
        "description": "Index price 1m klines for fair-price reference.",
        "url": "https://data.binance.vision/data/futures/um/monthly/indexPriceKlines/{symbol}/1m/{symbol}-1m-{yyyy}-{mm}.zip",
    },
    {
        "dataset_id": "futures_um_premiumIndexKlines_1m",
        "role": "filter",
        "description": "Premium index 1m klines for premium/basis filter.",
        "url": "https://data.binance.vision/data/futures/um/monthly/premiumIndexKlines/{symbol}/1m/{symbol}-1m-{yyyy}-{mm}.zip",
    },
]

PROBES = [
    {
        "probe_id": "futures_um_bookTicker_2020_01",
        "description": "Optional bookTicker archive sample. Not required for Strategy 29.",
        "url": "https://data.binance.vision/data/futures/um/monthly/bookTicker/{symbol}/{symbol}-bookTicker-2020-01.zip",
    },
    {
        "probe_id": "spot_bookTicker_2020_01",
        "description": "Optional spot bookTicker archive sample. Not required for Strategy 29.",
        "url": "https://data.binance.vision/data/spot/monthly/bookTicker/{symbol}/{symbol}-bookTicker-2020-01.zip",
    },
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    months = list(pd.period_range(START_MONTH, END_MONTH, freq="M"))
    rows = []
    for dataset in DATASETS:
        for month in months:
            url = _format_url(dataset["url"], month)
            rows.append({**_head_check(url), **{k: v for k, v in dataset.items() if k != "url"}, "month": str(month), "url": url})
            time.sleep(0.05)

    availability = pd.DataFrame(rows)
    summary_rows = [_dataset_summary(dataset, availability, months) for dataset in DATASETS]
    dataset_summary = pd.DataFrame(summary_rows)
    probe_rows = []
    for probe in PROBES:
        url = probe["url"].format(symbol=SYMBOL)
        probe_rows.append({**probe, **_head_check(url), "url": url})

    probe_frame = pd.DataFrame(probe_rows)
    availability.to_csv(OUT_DIR / "availability_matrix.csv", index=False)
    dataset_summary.to_csv(OUT_DIR / "dataset_summary.csv", index=False)
    probe_frame.to_csv(OUT_DIR / "optional_probe_summary.csv", index=False)

    decision = _decision(dataset_summary)
    summary = {
        "status": "strategy_29_free_raw_trade_coverage_audit_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Check whether free Binance public data can support a spot-perp raw-trade lead/lag Strategy 29 research path.",
        "gpt_pro_direction": {
            "most_recommended": "spot-perp raw trade lead-lag plus basis/premium/funding filters",
            "secondary": "small cross-asset lead-lag with very few major symbols",
            "not_recommended": "more K-line micro-rules, OI/long-short public REST history, funding-only selector",
        },
        "coverage_window": {"start_month": str(START_MONTH), "end_month": str(END_MONTH), "months": len(months)},
        "source": {
            "kind": "Binance public data archive HEAD checks only",
            "symbol": SYMBOL,
            "note": "This audit checks archive availability and size only; it does not download or parse the large trade zip files.",
        },
        "dataset_summary": _json_ready(dataset_summary.to_dict("records")),
        "optional_probes": _json_ready(probe_frame.to_dict("records")),
        "decision": decision,
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "availability_matrix": _rel(OUT_DIR / "availability_matrix.csv"),
            "dataset_summary": _rel(OUT_DIR / "dataset_summary.csv"),
            "optional_probe_summary": _rel(OUT_DIR / "optional_probe_summary.csv"),
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(_json_ready(summary), indent=2, ensure_ascii=False))


def _format_url(template: str, month: pd.Period) -> str:
    return template.format(symbol=SYMBOL, yyyy=month.year, mm=f"{month.month:02d}")


def _head_check(url: str) -> dict[str, Any]:
    last_error = None
    for attempt in range(3):
        try:
            headers = {"User-Agent": USER_AGENT}
            request = urllib.request.Request(url, method="HEAD", headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                return {
                    "ok": True,
                    "http_status": int(response.status),
                    "content_length": _int_or_none(response.headers.get("Content-Length")),
                    "attempts": attempt + 1,
                    "error": None,
                }
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"ok": False, "http_status": 404, "content_length": None, "attempts": attempt + 1, "error": str(exc)}
            last_error = str(exc)
        except Exception as exc:
            last_error = repr(exc)
        time.sleep(0.3 + attempt * 0.2)

    # Some archive HEAD requests intermittently fail behind the CDN. A 1-byte
    # range GET verifies existence without downloading the large trade file.
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            length = response.headers.get("Content-Length")
            content_range = response.headers.get("Content-Range")
            return {
                "ok": True,
                "http_status": int(response.status),
                "content_length": _content_length_from_range(length, content_range),
                "attempts": 4,
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        return {"ok": False, "http_status": int(exc.code), "content_length": None, "attempts": 4, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "http_status": None, "content_length": None, "attempts": 4, "error": last_error or repr(exc)}


def _dataset_summary(dataset: dict[str, Any], availability: pd.DataFrame, months: list[pd.Period]) -> dict[str, Any]:
    subset = availability.loc[availability["dataset_id"] == dataset["dataset_id"]].copy()
    missing = subset.loc[~subset["ok"], "month"].astype(str).tolist()
    total_bytes = int(subset["content_length"].fillna(0).sum())
    ok_months = int(subset["ok"].sum())
    return {
        "dataset_id": dataset["dataset_id"],
        "role": dataset["role"],
        "description": dataset["description"],
        "required_months": len(months),
        "ok_months": ok_months,
        "missing_months": len(missing),
        "missing_month_list": ",".join(missing),
        "coverage_pass": bool(ok_months == len(months)),
        "total_size_gb": round(total_bytes / 1024**3, 3),
        "min_month_size_mb": round(float(subset["content_length"].fillna(0).min()) / 1024**2, 3),
        "max_month_size_mb": round(float(subset["content_length"].fillna(0).max()) / 1024**2, 3),
    }


def _decision(dataset_summary: pd.DataFrame) -> dict[str, Any]:
    coverage = dict(zip(dataset_summary["dataset_id"], dataset_summary["coverage_pass"]))
    main_ok = bool(coverage.get("futures_um_aggTrades") and coverage.get("spot_aggTrades"))
    filters_ok = bool(
        coverage.get("futures_um_fundingRate")
        and coverage.get("futures_um_markPriceKlines_1m")
        and coverage.get("futures_um_indexPriceKlines_1m")
        and coverage.get("futures_um_premiumIndexKlines_1m")
    )
    support_ok = bool(coverage.get("futures_um_1m_klines") and coverage.get("spot_1m_klines"))
    if main_ok and filters_ok and support_ok:
        return {
            "verdict": "FREE_SPOT_PERP_RAW_TRADE_DATA_AVAILABLE",
            "promote_strategy": False,
            "reason": "现货/合约aggTrades、1m K线、funding、mark/index/premium 月包都覆盖 2020-01 到 2026-05，可以继续做一次成交流错位上限测试。",
            "next_step": "另起30号，只做 spot-perp raw trade lead-lag + basis/funding filter 的上限测试；不要再扩免费K线小规则。",
        }
    return {
        "verdict": "FREE_SPOT_PERP_RAW_TRADE_DATA_INCOMPLETE",
        "promote_strategy": False,
        "reason": "Strategy 29 所需免费数据没有完整覆盖目标月份，不适合做 2020-2026 严格回测。",
        "next_step": "停止免费数据挖掘，改做影子跟踪/低年化验证。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    decision = summary["decision"]
    rows = "\n".join(
        f"- `{row['dataset_id']}`：coverage `{row['coverage_pass']}`，missing `{row['missing_months']}`，size `{row['total_size_gb']}` GB"
        for row in summary["dataset_summary"]
    )
    probes = "\n".join(
        f"- `{row['probe_id']}`：ok `{row['ok']}`，status `{row['http_status']}`"
        for row in summary["optional_probes"]
    )
    return f"""# 29号免费 raw trade 数据覆盖审计

这不是策略，也不是收益回测。它只检查免费公开数据够不够做下一步成交流错位研究。

## 覆盖结果

{rows}

## 可选盘口探针

{probes}

## 判断

`{decision["verdict"]}`

{decision["reason"]}

下一步：{decision["next_step"]}
"""


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _int_or_none(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _content_length_from_range(length: str | None, content_range: str | None) -> int | None:
    if content_range and "/" in content_range:
        return _int_or_none(content_range.rsplit("/", 1)[-1])
    return _int_or_none(length)


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if pd.isna(value):
        return None
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
