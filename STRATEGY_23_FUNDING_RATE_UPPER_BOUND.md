# 23号资金费率上限测试

本文件用于定位 23号测试。它不是策略，不能交易，也不是固化版。

它只回答一个问题：

Binance USD-M futures 的历史资金费率，作为一个真正不同的数据源，理论上有没有足够好的月度零件？

## 身份

- 测试编号：`strategy_23_funding_rate_upper_bound_20260627`
- 来源脚本：`scripts/audit_strategy_23_funding_rate_upper_bound_20260627.py`
- 结果目录：`artifacts/strategy_23_funding_rate_upper_bound_20260627/`
- 主要结果：`artifacts/strategy_23_funding_rate_upper_bound_20260627/summary.json`
- 报告：`artifacts/strategy_23_funding_rate_upper_bound_20260627/report.md`

## 数据和口径

- 数据源：Binance public USD-M futures monthly fundingRate archive
- 品种：`BTCUSDT`
- 下载范围：`2020-01` 到 `2026-05`
- 资金费率记录：`7029`
- 时间范围：`2020-01-01 00:00 UTC` 到 `2026-05-31 16:00 UTC`
- 重复时间戳：`0`
- 非8小时断档：`0`
- 评估范围：`2023-01` 到 `2026-05`
- 手续费：开平合计 `0.2%`
- 候选：`246` 个，只用资金费率水平、变化、均值、z-score

## 结果

静态候选硬通过数量：`0`。

最好的看答案月度上限是 `monthly_oracle_best_return_order10`：

| 年份 | 收益 |
|---|---:|
| 2023 | `+17263.32%` |
| 2024 | `+45467.21%` |
| 2025 | `+6801.02%` |
| 2026 YTD | `+648.74%` |

并且：

- 亏损月：`0`
- 最差月：`+5.43%`
- 最少月交易：`10`

## 判断

23号结论是：`FUNDING_RATE_UPPER_BOUND_HAS_MONTHLY_PIECES`。

通俗说：资金费率这条新数据源，事后看每个月确实有足够好的候选零件。

但这仍然不能交易，因为月度 oracle 是看答案。下一步必须做 24号严格逐月选择器，看能不能不用未来信息提前选中这些月份。

## 边界

- 这里只做研究和回测。
- 不下实盘，不读取密钥，不启动 supervisor。
- 没有覆盖 0号、2C、4号、14号到22号。
