# 30号 spot-perp aggTrades 样本上限测试

本文件用于定位 30号审计。它不是策略，不能交易，也不是固化版。

30号只做一件事：

先拿少数几个月的 Binance 免费 spot `aggTrades` 和 USD-M futures `aggTrades`，测试“现货-合约成交流错位”这条路有没有明显希望。

## 身份

- 审计编号：`strategy_30_spot_perp_aggtrade_sample_upper_bound_20260628`
- 来源脚本：`scripts/audit_strategy_30_spot_perp_aggtrade_sample_upper_bound_20260628.py`
- 结果目录：`artifacts/strategy_30_spot_perp_aggtrade_sample_upper_bound_20260628/`
- 主要结果：`artifacts/strategy_30_spot_perp_aggtrade_sample_upper_bound_20260628/summary.json`
- 报告：`artifacts/strategy_30_spot_perp_aggtrade_sample_upper_bound_20260628/report.md`

## 样本月份

- `2023-07`
- `2024-06`
- `2025-08`
- `2026-05`

## 口径

- 只做研究回测，不下实盘。
- 不读取密钥。
- 不启动 supervisor。
- 不改真实仓位。
- 手续费沿用旧口径：开平合计 `0.2%`。
- 信号只用已收盘15分钟内的 `aggTrades`，下一根15分钟K线才吃收益。
- 这里的月度 oracle 会“看答案”，只能说明上限，不能交易。

## 结果

- 数据质量通过：`11808` 根15分钟特征，spot/futures 都没有缺15分钟行。
- 实际下载压缩包约 `2.586 GB`，处理完后已删除原始 zip，只保留聚合特征。
- 候选数量：`204` 个。
- 不要求交易次数时，最好的月度 oracle 只是“不交易”，样本总收益 `0.00%`。
- 要求每月至少10单时，最好的月度 oracle 四个样本月全部亏，样本总收益 `-25.33%`，最差月 `-12.67%`，最少月交易 `39`。

## 判断

30号结论是：`SPOT_PERP_AGGTRADE_SAMPLE_UPPER_BOUND_FAILS`。

通俗说：

这条免费 `aggTrades` 现货-合约错位路线，在小样本上已经不值得继续。

不要下载全量约90GB做 30B。
