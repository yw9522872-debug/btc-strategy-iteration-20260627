# 当前策略迭代包

策略名：`event_entry_v2_alpha_robust_static`

这是从 `C:\Users\WHR\Documents\量化策略` 复制来的只读研究包，用来做策略迭代，不包含 API key、secret，也不包含实盘下单/撤单操作。

## 先看这两个脚本

1. `scripts/scan_event_entry_v2_alpha_source_20260625.py`
   - 原始 alpha 规则扫描。
   - 当前核心参数来自 `gap_adx_regime / momentum / adx_min=36 / gap_min=50`。

2. `scripts/review_event_entry_v2_alpha_source_robustness_20260625.py`
   - 在原始 alpha 上做杠杆和稳健性筛选。
   - 当前上线过的版本是 `alpha_robust_static_a742e1d0c3_lev2.2`。

## 关键回测结果

结果文件在：

- `artifacts/event_entry_v2_alpha_source_robustness_review_20260625/summary.json`
- `artifacts/event_entry_v2_alpha_source_robustness_review_20260625/best_variant_yearly.csv`
- `artifacts/event_entry_v2_alpha_source_robustness_review_20260625/best_variant_monthly.csv`
- `artifacts/event_entry_v2_alpha_source_robustness_review_20260625/best_variant_signals.csv`
- `artifacts/event_entry_v2_alpha_source_robustness_review_20260625/best_variant_equity.csv`

已知年度结果：

| year | return_pct | max_drawdown_pct | entries | exits |
|---|---:|---:|---:|---:|
| 2025 | 149.6532 | -56.5246 | 1 | 1 |
| 2026 YTD | 106.4083 | -50.1982 | 0 | 0 |

## 迭代边界

- 这里先做研究和回测。
- 不读、不打印、不保存 API key 或 secret。
- 不启动实盘 supervisor。
- 不下单、不撤单、不改仓。
- 新策略要重新过回测、风控、mock/observe acceptance，才能考虑上线。
