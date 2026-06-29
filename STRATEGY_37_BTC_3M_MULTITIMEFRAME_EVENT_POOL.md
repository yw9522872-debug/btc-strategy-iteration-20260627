# 37号 BTC 3m 多周期事件池审计

本文件用于定位 37号审计。它不是策略，不能交易，也不是固化版。

37号只做一件事：

借旧 BTC 3m 项目的“多周期事件池”框架，但不照搬旧参数，重新用 BTCUSDT 3m 公开K线做严格审计。

## 身份

- 审计编号：`strategy_37_btc_3m_multitimeframe_event_pool_20260629`
- 来源脚本：`scripts/audit_strategy_37_btc_3m_multitimeframe_event_pool_20260629.py`
- 结果目录：`artifacts/strategy_37_btc_3m_multitimeframe_event_pool_20260629/`
- 主要结果：`artifacts/strategy_37_btc_3m_multitimeframe_event_pool_20260629/summary.json`
- 报告：`artifacts/strategy_37_btc_3m_multitimeframe_event_pool_20260629/report.md`

## 口径

- 只做研究回测，不下实盘。
- 不读取密钥。
- 不启动 supervisor。
- 不改真实仓位。
- 数据使用 Binance 免费 USD-M futures `BTCUSDT` 3m 月包。
- 数据范围：`2020-01-01 00:00 UTC` 到 `2026-05-31 23:57 UTC`。
- 手续费沿用旧口径：开平合计 `0.2%`。
- 信号只用已收盘3分钟K线，下一根3分钟K线才吃收益。
- 严格选择器每个月只用该月之前的数据选事件。
- 月度 oracle 会“看答案”，只能说明上限，不能交易。

## 数据质量

- K线数量：`1124640`
- 覆盖月份：`77`
- 重复时间戳：`0`
- 3分钟断档：`0`
- 缺失月份：`0`

## 候选池

候选数量：`496`

候选家族：

- `event_trend`
- `event_range`
- `event_volume`

候选规则：

- `trend_breakout`
- `trend_pullback`
- `range_reversal`
- `volume_trend_breakout`

这些规则只借“多周期事件池”的框架，没有照搬旧项目的7条规则、阈值或10x毛暴露。

## 结果

37号结论是：`BTC_3M_MULTITIMEFRAME_EVENT_POOL_FAILS`。

关键结果：

- 静态硬通过数量：`0`
- 最好每月10单看答案 oracle：
  - 2025：`+503.35%`
  - 2026 YTD：`+157.89%`
  - 不盈利月份：`2` 个，分别是 `2024-04`、`2025-10`
  - 最差月：`-1.37%`
  - 最少月交易：`12`
- 最好严格选择器：`range_events`
  - 2023：`-2.17%`
  - 2024：`-8.69%`
  - 2025：`-6.49%`
  - 2026 YTD：`-7.45%`
  - 不盈利月份：`27`
  - 最少月交易：`2`
- 便宜组合近似也失败：
  - 最好配置 2025：`-9.44%`
  - 2026 YTD：`0.00%`
  - 不盈利月份：`34`

## 判断

37号不能升级为候选策略。

通俗说：这次换成 BTC 3m 多周期事件池以后，看答案结果比单币3m小规则强很多，但仍然差两个月过不了“每个月都盈利”。严格不看未来选择器更差，说明月初仍选不准。

后续不要继续小修这批 BTC 3m 多周期事件。除非拿到真正不同的数据源，否则更适合把目标改成更现实的影子跟踪/低年化验证。
