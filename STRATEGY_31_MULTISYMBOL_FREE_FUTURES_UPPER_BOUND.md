# 31号多币种免费期货样本上限测试

本文件用于定位 31号审计。它不是策略，不能交易，也不是固化版。

31号只做一件事：

先拿少数关键月份，检查免费 Binance USD-M futures 15分钟K线里，多币种是否比 BTC 单币多给一些机会。

## 身份

- 审计编号：`strategy_31_multisymbol_free_futures_sample_upper_bound_20260628`
- 来源脚本：`scripts/audit_strategy_31_multisymbol_free_futures_upper_bound_20260628.py`
- 结果目录：`artifacts/strategy_31_multisymbol_free_futures_sample_upper_bound_20260628/`
- 主要结果：`artifacts/strategy_31_multisymbol_free_futures_sample_upper_bound_20260628/summary.json`
- 报告：`artifacts/strategy_31_multisymbol_free_futures_sample_upper_bound_20260628/report.md`

## 币种

- `BTCUSDT`
- `ETHUSDT`
- `SOLUSDT`
- `BNBUSDT`
- `HYPEUSDT`
- `DOGEUSDT`
- `XRPUSDT`
- `ADAUSDT`
- `AVAXUSDT`
- `LINKUSDT`

## 口径

- 只做研究回测，不下实盘。
- 不读取密钥。
- 不启动 supervisor。
- 不改真实仓位。
- 手续费沿用旧口径：开平合计 `0.2%`。
- 信号只用已收盘15分钟K线，下一根15分钟K线才吃收益。
- 月度 oracle 会“看答案”，只能说明上限，不能交易。

## 样本月份

- `2023-07`
- `2024-06`
- `2025-08`
- `2026-05`

## 结果

31号结论是：`MULTISYMBOL_FREE_FUTURES_SAMPLE_UPPER_BOUND_HAS_SIGNAL`。

通俗说：

多币种这条免费路线，比 BTC 单币更有希望，但现在还只是“看答案”。

关键结果：

- 数据质量通过。
- `HYPEUSDT` 只覆盖 2 个样本月，`DOGEUSDT` 覆盖 3 个样本月，其余主要币覆盖 4 个样本月。
- 候选数量：`816` 个。
- 18 个静态候选四个样本月都为正。
- 每月10单 oracle 四个样本月都为正。
- 最差样本月：`+244.10%`。
- 最少月交易：`18`。

但这些数字是事后挑出来的，不能交易。

下一步应该另起32号，扩到完整历史，再做严格逐月选择器。
