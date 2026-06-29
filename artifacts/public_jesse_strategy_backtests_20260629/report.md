# Jesse 公开策略代理回测

这是本项目统一口径下的代理回测，不是 Jesse 原生撮合结果。

- 数据：BTCUSDT USD-M futures，`2020-01-01 00:00:00+00:00` 到 `2026-05-31 23:45:00+00:00`
- 手续费：开仓 `0.1%`，平仓 `0.1%`，开平合计 `0.2%`
- 执行：信号只用已收盘K线，下一根K线开始吃收益
- 已回测：`9` 个；跳过：`6` 个

## 回测汇总

| 策略 | 周期 | 周期依据 | 2025 | 2026 YTD | 最大回撤 | 交易次数 | 2025-2026亏损月 |
|---|---:|---|---:|---:|---:|---:|---:|
| `bitmania_tradeiq_cci_ce` | `4h` | source path contains 4h | -2.32% | 7.61% | -34.02% | 253 | 8 |
| `dcupmusic_always_long_demo` | `1h` | source route sets timeframe='1h' | -6.35% | -15.93% | -77.24% | 1 | 9 |
| `brainctl_sma_sample` | `15m` | no explicit timeframe; project default 15m | -21.84% | -20.70% | -86.68% | 1183 | 10 |
| `bitmania_trendtype` | `4h` | source path contains 4h | -33.94% | -12.75% | -74.42% | 1408 | 11 |
| `jesse_example_macd_ema` | `1h` | docstring says Timeframe: 1h | -41.91% | -11.21% | -77.70% | 1610 | 15 |
| `devon_macd_ema` | `1h` | same Jesse MACD_EMA source family says 1h | -41.91% | -11.21% | -77.70% | 1610 | 15 |
| `devon_donchian` | `15m` | no explicit timeframe; project default 15m | -42.31% | -36.02% | -96.63% | 3821 | 16 |
| `jesse_example_turtle_rules` | `15m` | no explicit timeframe; project default 15m | -95.65% | -74.59% | -100.00% | 18385 | 17 |
| `ben_walker_turtle_rules` | `15m` | no explicit timeframe; project default 15m | -95.65% | -74.59% | -100.00% | 18385 | 17 |

## 跳过项

| 策略 | 原因 |
|---|---|
| `strat16_three_rails_reverse` | limit-entry plus intrabar stop/take-profit; no explicit timeframe; proxy would be misleading |
| `range_reversal` | recommended 4h, but depends on custom_indicators and hard-coded ETH-like zones 1700-4200; BTC backtest is not meaningful |
| `triple_supertrend_tf` | multi-timeframe limit-entry/add-on order strategy; not faithful without Jesse order engine |
| `astro_strategy_rsi` | requires external daily astrology CSV files not present in downloaded source |
| `amt_trend_continuation` | requires custom volume-profile indicators and partial exits; not faithful in simple OHLCV proxy |
| `ysdede_helpers` | downloaded files are helper/playground code, not complete Jesse strategies |

结论：这些公开策略没有直接成为本项目候选；只能挑规则形状继续二次改造。
