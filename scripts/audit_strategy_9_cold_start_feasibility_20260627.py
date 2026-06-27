from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

import search_monthly_profit_lock_20260627 as lock_search
import search_online_expert_pool_20260627 as source_pool


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "strategy_9_cold_start_feasibility_20260627"
SELECTIONS = ROOT / "artifacts" / "strategy_1b_expanded_controls_20260627" / "strategy_1b_selections.csv"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    features = source_pool._add_features(source_pool._load_features(source_pool.FEATURE_FRAME))
    feature_months = pd.Series(features["timestamp"].dt.strftime("%Y-%m").unique()).sort_values().tolist()
    selections = pd.read_csv(SELECTIONS)
    selection_months = sorted(selections["eval_month"].astype(str).unique().tolist())

    month_table = pd.DataFrame(
        {
            "month": feature_months,
            "has_feature_data": True,
            "has_2c_3_4_selection": [month in selection_months for month in feature_months],
            "clean_direct_test_role": [
                "training_only_for_saved_candidates" if month < selection_months[0] else "evaluated_or_available_month"
                for month in feature_months
            ],
        }
    )
    month_table.to_csv(OUT_DIR / "month_coverage.csv", index=False)

    summary = {
        "status": "strategy_9_cold_start_feasibility_ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_a_strategy": True,
        "feature_month_start": feature_months[0],
        "feature_month_end": feature_months[-1],
        "selection_month_start": selection_months[0],
        "selection_month_end": selection_months[-1],
        "direct_2024_test_clean": False,
        "reason": "2C、3号、4号保存的月度控制参数从 2025-01 开始，而且 2024 已经作为训练历史参与。把这些参数倒回去测 2024，就是用未来选好的参数测过去。",
        "clean_next_options": [
            "Fetch earlier pre-2024 data, train controls before each 2024 month, then evaluate 2024 walk-forward.",
            "Keep 2024 as training history only and evaluate future newly arriving months without changing rules.",
            "If no earlier data is available, label any 2024 replay as leaky demonstration, not validation.",
        ],
        "files": {
            "month_coverage": _rel(OUT_DIR / "month_coverage.csv"),
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
        },
    }
    assert summary["direct_2024_test_clean"] is False
    _write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "report.md").write_text(_render_report(summary), encoding="utf-8")
    print(json.dumps(lock_search._json_ready(summary), indent=2, ensure_ascii=False))


def _render_report(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# 9号冷启动可行性审计",
            "",
            "这不是新策略，只判断能不能干净地把 2C、3号、4号直接拿去测 2024。",
            "",
            "## 结论",
            "",
            f"- 数据月份：`{summary['feature_month_start']}` 到 `{summary['feature_month_end']}`。",
            f"- 已保存月度控制参数：`{summary['selection_month_start']}` 到 `{summary['selection_month_end']}`。",
            f"- 能否干净直接测 2024：`{summary['direct_2024_test_clean']}`。",
            f"- 原因：{summary['reason']}",
            "",
            "## 干净做法",
            "",
            "- 要测 2024，需要更早的 2023 或更早数据来提前选参数。",
            "- 如果没有更早数据，2024 只能作为训练历史，不能又训练又验证。",
            "- 未来真正新来的月份，才是最干净的继续观察样本。",
        ]
    ) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(lock_search._json_ready(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


if __name__ == "__main__":
    main()
