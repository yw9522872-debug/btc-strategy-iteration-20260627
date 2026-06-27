# 18号上限失败月份复盘

这不是新策略，只解释17号为什么连看答案上限都没过。

- 失败月份数：`10`
- 失败类型：`{'no_positive_candidate': 6, 'positive_only_with_too_few_orders': 4}`

## 失败月份

- `2023-07`：`no_positive_candidate`，BTC月涨跌 `-4.00%`，最佳全候选 `0.00%`/0单，最佳10单候选 `-0.08%`/34单
- `2023-09`：`positive_only_with_too_few_orders`，BTC月涨跌 `3.73%`，最佳全候选 `0.16%`/8单，最佳10单候选 `-2.44%`/24单
- `2024-04`：`positive_only_with_too_few_orders`，BTC月涨跌 `-14.85%`，最佳全候选 `22.66%`/7单，最佳10单候选 `-1.78%`/39单
- `2024-06`：`positive_only_with_too_few_orders`，BTC月涨跌 `-7.17%`，最佳全候选 `21.68%`/7单，最佳10单候选 `-1.60%`/16单
- `2024-12`：`no_positive_candidate`，BTC月涨跌 `-3.19%`，最佳全候选 `-3.00%`/26单，最佳10单候选 `-3.00%`/26单
- `2025-06`：`no_positive_candidate`，BTC月涨跌 `2.55%`，最佳全候选 `0.00%`/0单，最佳10单候选 `-2.04%`/16单
- `2025-07`：`positive_only_with_too_few_orders`，BTC月涨跌 `7.85%`，最佳全候选 `4.65%`/2单，最佳10单候选 `-0.32%`/13单
- `2025-09`：`no_positive_candidate`，BTC月涨跌 `5.62%`，最佳全候选 `0.00%`/0单，最佳10单候选 `-3.36%`/46单
- `2026-04`：`no_positive_candidate`，BTC月涨跌 `12.21%`，最佳全候选 `0.00%`/0单，最佳10单候选 `-1.52%`/18单
- `2026-05`：`no_positive_candidate`，BTC月涨跌 `-3.63%`，最佳全候选 `0.00%`/0单，最佳10单候选 `-0.49%`/10单

## 判断

`FAILURE_MONTHS_EXPLAIN_SIMPLE_FAMILY_STOP`

失败月里多次出现最佳候选是空仓或交易不足，说明继续微调这批简单规则意义不大。
