# 48号 公开 Jesse 策略代理回测

本文件用于定位 48号审计。它不是实盘策略，不能交易，也不是固化版。

## 身份

- 审计编号：`public_jesse_strategy_backtests_20260629`
- 来源脚本：`scripts/backtest_public_jesse_strategies_20260629.py`
- 结果目录：`artifacts/public_jesse_strategy_backtests_20260629/`
- 主要结果：`artifacts/public_jesse_strategy_backtests_20260629/summary.json`
- 报告：`artifacts/public_jesse_strategy_backtests_20260629/report.md`

## 口径

- 只做研究回测，不下实盘。
- 不读取密钥。
- 不启动 supervisor。
- 不改真实仓位。
- 数据：Binance USD-M futures BTCUSDT 15m公开K线，`2020-01-01 00:00 UTC` 到 `2026-05-31 23:45 UTC`。
- 周期：源码明确写周期的按源码；路径写 `4h` 的按4小时；没写周期的先按本项目默认15分钟。
- 手续费：开仓 `0.1%`，平仓 `0.1%`，开平合计 `0.2%`。
- 执行：信号只用已收盘K线，下一根K线才吃收益。
- 注意：这是本地代理回测，不是 Jesse 原生撮合。限价单、分批止盈、复杂多周期加仓等没有硬凑。

## 回测结果

共处理公开 Jesse 来源策略/示例：

- 可代理回测：`9` 个。
- 跳过：`6` 个。

最好的一条也没有达到本项目目标：

- `bitmania_tradeiq_cci_ce`
- 周期：`4h`
- 2025：`-2.32%`
- 2026 YTD：`+7.61%`
- 最大回撤：`-34.02%`
- 2025-2026 亏损月：`8`

其它主要结果：

- `jesse_example_macd_ema`，周期 `1h`：2025 `-41.91%`，2026 YTD `-11.21%`。
- `devon_donchian`，周期不明，按 `15m`：2025 `-42.31%`，2026 YTD `-36.02%`。
- `jesse_example_turtle_rules`，周期不明，按 `15m`：2025 `-95.65%`，2026 YTD `-74.59%`。
- `bitmania_trendtype`，周期 `4h`：2025 `-33.94%`，2026 YTD `-12.75%`。

## 跳过原因

- `strat16_three_rails_reverse`：限价入场和K线内止盈止损太重，且周期不明，简单代理容易误导。
- `range_reversal`：推荐 `4h`，但依赖自定义指标，并写死类似 ETH 价格区间，不适合直接拿 BTC 测。
- `triple_supertrend_tf`：多周期、限价补仓、分批止盈，离不开 Jesse 撮合。
- `astro_strategy_rsi`：缺少外部每日星象 CSV。
- `amt_trend_continuation`：依赖自定义 volume profile 和分批止盈。
- `ysdede_helpers`：下载到的是辅助代码，不是完整策略。

## 判断

48号结论：`PUBLIC_JESSE_STRATEGY_PROXY_BACKTEST_DONE`。

通俗说：这些公开 Jesse 策略可以当“想法库”，不能当现成策略。按它们自己的周期或可识别周期跑到 BTCUSDT 上，没有一条接近本项目历史目标。
