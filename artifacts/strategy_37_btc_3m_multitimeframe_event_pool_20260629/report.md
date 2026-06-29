# 37号 BTC 3m 多周期事件池审计

这不是策略，不能交易，也不是固化版。

## 数据和口径

- 数据：Binance 免费 USD-M futures `BTCUSDT` 3m K线
- 范围：`2020-01-01T00:00:00+00:00` 到 `2026-05-31T23:57:00+00:00`
- 行数：`1124640`
- 缺3分钟断档：`0`
- 手续费：开平合计 `0.20%`
- 时序：信号只用已收盘3分钟K线，下一根3分钟K线才吃收益
- 选择器：每个月只用该月之前的数据选事件

## 候选池

- 候选数：`496`
- 家族：`event_range, event_trend, event_volume`
- 规则：`range_reversal, trend_breakout, trend_pullback, volume_trend_breakout`
- 静态硬通过数：`0`
- 最好静态候选：`event_range_range_reversal_lev1p0_trigger_window5_trend_window960_trigger_threshold_bps100_trend_threshold_bps50_hold_bars32`

## 最好每月10单看答案上限

- oracle：`monthly_oracle_best_return_order10`
- 2025：`503.35%`
- 2026 YTD：`157.89%`
- 不盈利月份数：`2`
- 最差月：`-1.37%`
- 最少月交易：`12`

## 最好严格选择器

- selector：`range_events`
- 2023：`-2.17%`
- 2024：`-8.69%`
- 2025：`-6.49%`
- 2026 YTD：`-7.45%`
- 不盈利月份数：`27`
- 最差月：`-5.74%`
- 最少月交易：`2`

## 便宜组合近似

- 配置数：`48`
- 最好配置：top_k `10`，lookback `24`，min_pos_rate `0.45`，score `mean`
- 2025：`-9.44%`
- 2026 YTD：`0.00%`
- 不盈利月份数：`34`
- 注意：这只是月度收益层面的便宜筛查，不是逐K资金重放。

## 判断

`BTC_3M_MULTITIMEFRAME_EVENT_POOL_FAILS`

新的3m多周期事件池里，静态候选、看答案月度上限、严格选择器和便宜组合近似都没过硬目标。

下一步：不要继续小修这批事件；除非换真正不同的数据源，否则更适合降低目标做影子跟踪。
