# 25号持仓量上限可行性审计

本文件用于定位 25号审计。它不是策略，不能交易，也不是固化版。

它只回答一个问题：

Binance 公开持仓量数据，够不够做 2020-2026 的历史上限测试？

## 身份

- 审计编号：`strategy_25_open_interest_upper_bound_feasibility_20260627`
- 来源脚本：`scripts/audit_strategy_25_open_interest_upper_bound_feasibility_20260627.py`
- 结果目录：`artifacts/strategy_25_open_interest_upper_bound_feasibility_20260627/`
- 主要结果：`artifacts/strategy_25_open_interest_upper_bound_feasibility_20260627/summary.json`
- 报告：`artifacts/strategy_25_open_interest_upper_bound_feasibility_20260627/report.md`

## 结果

官方接口：`https://fapi.binance.com/futures/data/openInterestHist`

Binance 官方文档说明：openInterestHist 只提供最近 `1` 个月数据。

实际检查：

| 检查 | 结果 |
|---|---|
| 2020-01 | 失败，`startTime` invalid |
| 2023-01 | 失败，`startTime` invalid |
| 2026-05-31 到 2026-06-01 | 成功，返回 `97` 行 |
| 最近数据 | 成功，返回 `500` 行 |

## 判断

25号结论是：`OPEN_INTEREST_HISTORY_NOT_AVAILABLE_FOR_2020_2026`。

通俗说：公开接口能拿到最近持仓量，但拿不到 2020-2026 完整历史。因此不能用它做我们这套 2023-2026 硬目标上限测试。

下一步不要用不完整持仓量硬做 2023-2026 上限。若继续，必须先找到可审计的完整历史持仓量数据源，或者只做最近1个月观察表。

## 边界

- 这里只做研究和回测。
- 不下实盘，不读取密钥，不启动 supervisor。
- 没有覆盖 0号、2C、4号、14号到24号。
