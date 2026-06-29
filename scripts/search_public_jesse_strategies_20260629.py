from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "public_jesse_strategy_sources_20260629"
DEFAULT_QUERIES = [
    "from jesse.strategies import Strategy",
    "from jesse import utils",
    "from jesse.indicators import",
    "def should_long def should_short jesse",
    "def go_long def go_short jesse",
]


def main() -> None:
    args = _parse_args()
    if args.self_test:
        _self_test()
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _search(args.limit)
    rows = _dedupe(rows)
    _add_repo_meta(rows)
    rows.sort(key=lambda r: (r["kind"], r["repo"], r["path"]))

    if args.download:
        _download_sources(rows)

    _write_csv(OUT_DIR / "sources.csv", rows)
    summary = _summary(rows, args.download)
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_report(summary, rows), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Search public GitHub code for Jesse strategy examples.")
    p.add_argument("--limit", type=int, default=25, help="Max code results per query.")
    p.add_argument("--download", action="store_true", help="Download matched public files into the artifact folder.")
    p.add_argument("--self-test", action="store_true", help="Run small internal checks and exit.")
    return p.parse_args()


def _search(limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for query in DEFAULT_QUERIES:
        cmd = [
            "gh",
            "search",
            "code",
            query,
            "--limit",
            str(limit),
            "--json",
            "repository,path,url",
        ]
        try:
            raw = subprocess.check_output(cmd, cwd=ROOT, text=True, encoding="utf-8", stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exc:
            rows.append({
                "query": query,
                "repo": "",
                "repo_url": "",
                "path": "",
                "url": "",
                "raw_url": "",
                "kind": "search_error",
                "license": "",
                "stars": "",
                "repo_updated_at": "",
                "is_archived": "",
                "downloaded_path": "",
                "note": exc.output.strip()[:500],
            })
            continue
        for item in json.loads(raw or "[]"):
            repo = item.get("repository") or {}
            url = item.get("url", "")
            rows.append({
                "query": query,
                "repo": repo.get("nameWithOwner", ""),
                "repo_url": repo.get("url", ""),
                "path": item.get("path", ""),
                "url": url,
                "raw_url": _raw_url(url),
                "kind": _kind(repo.get("nameWithOwner", ""), item.get("path", "")),
                "license": "",
                "stars": "",
                "repo_updated_at": "",
                "is_archived": "",
                "downloaded_path": "",
                "note": "",
            })
    return rows


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for row in rows:
        key = row["url"] or (row["repo"], row["path"], row["query"])
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _kind(repo: str, path: str) -> str:
    text = f"{repo}/{path}".lower()
    if "hack" in text or "cheat" in text:
        return "skip_bad_terms"
    if "indicator" in text:
        return "supporting_code"
    if "freqtrade" in text:
        return "other_framework_strategy"
    if repo == "jesse-ai/example-strategies":
        return "official_example"
    if repo == "jesse-ai/jesse" or "/docs/" in text or text.endswith(".md") or "/test" in text:
        return "framework_or_docs"
    if "strateg" in text or path.endswith("__init__.py"):
        return "candidate_strategy"
    return "other"


def _add_repo_meta(rows: list[dict[str, Any]]) -> None:
    repos = sorted({row["repo"] for row in rows if row.get("repo")})
    cache: dict[str, dict[str, Any]] = {}
    for repo in repos:
        try:
            raw = subprocess.check_output(
                ["gh", "repo", "view", repo, "--json", "licenseInfo,stargazerCount,updatedAt,isArchived"],
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                stderr=subprocess.DEVNULL,
            )
            data = json.loads(raw or "{}")
            license_info = data.get("licenseInfo") or {}
            cache[repo] = {
                "license": license_info.get("spdxId") or "",
                "stars": data.get("stargazerCount", ""),
                "repo_updated_at": data.get("updatedAt", ""),
                "is_archived": data.get("isArchived", ""),
            }
        except Exception:  # noqa: BLE001
            cache[repo] = {"license": "", "stars": "", "repo_updated_at": "", "is_archived": ""}
    for row in rows:
        row.update(cache.get(row.get("repo", ""), {}))


def _raw_url(url: str) -> str:
    m = re.match(r"https://github.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)$", url)
    if not m:
        return ""
    owner, repo, rev, path = m.groups()
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{rev}/{path}"


def _download_sources(rows: list[dict[str, Any]]) -> None:
    dst = OUT_DIR / "downloaded"
    dst.mkdir(parents=True, exist_ok=True)
    for old in dst.iterdir():
        if old.is_file():
            old.unlink()
    for row in rows:
        if row["kind"] not in {"candidate_strategy", "official_example"} or not row["raw_url"]:
            continue
        name = re.sub(r"[^A-Za-z0-9_.-]+", "__", f"{row['repo']}__{row['path']}")
        target = dst / name
        try:
            with urllib.request.urlopen(row["raw_url"], timeout=20) as response:
                target.write_bytes(response.read())
            row["downloaded_path"] = str(target.relative_to(ROOT))
        except Exception as exc:  # noqa: BLE001
            row["note"] = f"download_failed: {exc}"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ["kind", "repo", "license", "stars", "repo_updated_at", "is_archived", "path", "url", "raw_url", "query", "downloaded_path", "note"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _summary(rows: list[dict[str, Any]], downloaded: bool) -> dict[str, Any]:
    counts = Counter(row["kind"] for row in rows)
    candidate_count = counts.get("candidate_strategy", 0) + counts.get("official_example", 0)
    archived_count = sum(1 for row in rows if str(row.get("is_archived")).lower() == "true")
    return {
        "status": "public_jesse_strategy_sources_ready",
        "strategy_id": "public_jesse_strategy_sources_20260629",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "purpose": "Search public GitHub code for Jesse strategy examples and record sources.",
        "queries": DEFAULT_QUERIES,
        "download_requested": downloaded,
        "result_count": len(rows),
        "candidate_or_example_count": candidate_count,
        "counts_by_kind": dict(sorted(counts.items())),
        "archived_repo_result_count": archived_count,
        "decision": {
            "verdict": "PUBLIC_JESSE_STRATEGY_SOURCES_FOUND_REVIEW_ONLY" if candidate_count else "NO_PUBLIC_JESSE_STRATEGY_SOURCE_FOUND",
            "promote_strategy": False,
            "reason": "找到的公开 Jesse 策略只能当学习材料；必须先改成本项目统一回测口径，不能直接当策略用。",
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "sources": _rel(OUT_DIR / "sources.csv"),
            "downloaded": _rel(OUT_DIR / "downloaded") if downloaded else "",
        },
    }


def _report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    top = [row for row in rows if row["kind"] in {"candidate_strategy", "official_example"}][:20]
    lines = [
        "# Jesse 公开策略来源搜索",
        "",
        "本报告只记录公开来源，不代表这些策略有效，也不代表可以实盘。",
        "",
        f"- 搜索结果总数：`{summary['result_count']}`",
        f"- 候选策略/官方示例数量：`{summary['candidate_or_example_count']}`",
        f"- 是否下载源码：`{summary['download_requested']}`",
        f"- 结论：`{summary['decision']['verdict']}`",
        "",
        "## 前20个可看来源",
        "",
        "| 类型 | 仓库 | 许可证 | 星标 | 路径 | 链接 |",
        "|---|---|---|---:|---|---|",
    ]
    for row in top:
        lines.append(f"| `{row['kind']}` | `{row['repo']}` | `{row.get('license', '')}` | `{row.get('stars', '')}` | `{row['path']}` | {row['url']} |")
    lines.extend([
        "",
        "## 使用要求",
        "",
        "- 先看许可证和来源，不明来源不要混进本项目主策略。",
        "- 不相信原作者收益图，必须用本项目手续费、下一根K线执行、月度表重新跑。",
        "- 任何下载代码都只能放在本 artifacts 目录里，不能覆盖已有策略。",
    ])
    return "\n".join(lines) + "\n"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _self_test() -> None:
    assert _raw_url("https://github.com/a/b/blob/main/x/y.py") == "https://raw.githubusercontent.com/a/b/main/x/y.py"
    assert _kind("jesse-ai/example-strategies", "MACD_EMA/__init__.py") == "official_example"
    assert _kind("x/y", "strategies/MyStrategy/__init__.py") == "candidate_strategy"
    assert _kind("x/y", "strategies/TestEntry/__init__.py") == "framework_or_docs"
    assert _kind("x/y", "jesse/indicators/kvo.py") == "supporting_code"
    assert _kind("jesse-ai/jesse", "docs/a.md") == "framework_or_docs"
    print("self-test ok")


if __name__ == "__main__":
    sys.exit(main())
