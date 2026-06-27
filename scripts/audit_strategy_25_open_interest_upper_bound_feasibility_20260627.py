import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STRATEGY_ID = "strategy_25_open_interest_upper_bound_feasibility_20260627"
OUT_DIR = ROOT / "artifacts" / STRATEGY_ID
DOC_URL = "https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics"
REST_URL = "https://fapi.binance.com/futures/data/openInterestHist"
SYMBOL = "BTCUSDT"
PERIOD = "15m"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    checks = [
        _request_check("historical_2020_01", "2020-01-01T00:00:00Z", "2020-01-02T00:00:00Z"),
        _request_check("historical_2023_01", "2023-01-01T00:00:00Z", "2023-01-02T00:00:00Z"),
        _request_check("baseline_end_2026_05", "2026-05-31T00:00:00Z", "2026-06-01T00:00:00Z"),
        _request_check("recent_latest", None, None),
    ]
    checks_df = pd.DataFrame(checks)
    checks_df.to_csv(OUT_DIR / "availability_checks.csv", index=False)

    recent_rows = checks[-1].pop("sample_rows", [])
    if recent_rows:
        recent = pd.DataFrame(recent_rows)
        recent.to_csv(OUT_DIR / "recent_open_interest_sample.csv", index=False)

    can_run_historical_upper_bound = bool(
        checks_df.loc[checks_df["check_id"].isin(["historical_2020_01", "historical_2023_01", "baseline_end_2026_05"]), "ok"].all()
    )
    summary = {
        "status": "strategy_25_open_interest_upper_bound_feasibility_ready",
        "strategy_id": STRATEGY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "not_live_trading": True,
        "does_not_overwrite_existing_strategies": True,
        "purpose": "Check whether Binance public open-interest history is sufficient for a 2020-2026 upper-bound backtest.",
        "source": {
            "official_doc": DOC_URL,
            "rest_endpoint": REST_URL,
            "symbol": SYMBOL,
            "period": PERIOD,
            "doc_limit_note": "Official Binance documentation says only the latest 1 month of openInterestHist data is available.",
        },
        "availability_checks": _json_ready(checks_df.to_dict("records")),
        "can_run_2020_2026_upper_bound": can_run_historical_upper_bound,
        "decision": _decision(can_run_historical_upper_bound),
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "availability_checks": _rel(OUT_DIR / "availability_checks.csv"),
            "recent_open_interest_sample": _rel(OUT_DIR / "recent_open_interest_sample.csv") if recent_rows else None,
        },
    }
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def _request_check(check_id: str, start_iso: str | None, end_iso: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {"symbol": SYMBOL, "period": PERIOD, "limit": 500}
    if start_iso and end_iso:
        params["startTime"] = _ms(start_iso)
        params["endTime"] = _ms(end_iso)
    url = REST_URL + "?" + urllib.parse.urlencode(params)
    try:
        data = _get_json(url)
        rows = data if isinstance(data, list) else []
        return {
            "check_id": check_id,
            "ok": bool(rows),
            "http_status": 200,
            "row_count": len(rows),
            "first_timestamp": _iso_from_ms(rows[0]["timestamp"]) if rows else None,
            "last_timestamp": _iso_from_ms(rows[-1]["timestamp"]) if rows else None,
            "error": None,
            "sample_rows": rows[:5],
        }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "check_id": check_id,
            "ok": False,
            "http_status": exc.code,
            "row_count": 0,
            "first_timestamp": None,
            "last_timestamp": None,
            "error": body,
            "sample_rows": [],
        }


def _get_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "strategy-25-open-interest-feasibility/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        time.sleep(0.2)
        return json.loads(response.read())


def _ms(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def _iso_from_ms(value: str | int) -> str:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()


def _decision(can_run: bool) -> dict[str, Any]:
    if can_run:
        return {
            "verdict": "OPEN_INTEREST_HISTORY_AVAILABLE",
            "promote_strategy": False,
            "reason": "公开持仓量历史足够覆盖目标区间，可以另起真正上限测试。",
            "next_step": "另起26号，构造持仓量候选并做月度oracle上限。",
        }
    return {
        "verdict": "OPEN_INTEREST_HISTORY_NOT_AVAILABLE_FOR_2020_2026",
        "promote_strategy": False,
        "reason": "Binance公开openInterestHist接口只返回最近1个月，无法覆盖2020-2026历史硬目标区间。",
        "next_step": "不要用不完整持仓量做2023-2026上限；若要继续，需要先找到可审计的完整历史数据源，或改做最近1个月的观察表。",
    }


def _render_report(summary: dict[str, Any]) -> str:
    decision = summary["decision"]
    rows = "\n".join(
        f"- `{row['check_id']}`：ok `{row['ok']}`，rows `{row['row_count']}`，error `{row['error'] or ''}`"
        for row in summary["availability_checks"]
    )
    return f"""# 25号持仓量上限可行性审计

这不是策略，也不是收益回测。它只检查持仓量历史数据够不够做 2020-2026 上限测试。

## 检查结果

{rows}

## 判断

`{decision["verdict"]}`

{decision["reason"]}

下一步：{decision["next_step"]}
"""


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
