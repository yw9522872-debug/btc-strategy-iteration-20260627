# 15号统一数据底座体检

这不是新策略，也不是收益回测。它只确认以后换新策略族时，先从哪份 K 线数据开始。

## 数据底座

- 文件：`artifacts/strategy_14_pre2023_expanding_crowding_stress_audit_20260627/btc_15m_2020_2026_05_combined_ohlc.csv`
- 数据：`Binance USD-M futures public klines plus local event_entry_fullscan tail`
- 时间：`2020-01-01T00:00:00+00:00` 到 `2026-05-31T23:45:00+00:00`
- 行数：`224928`
- 月份数：`77`

## 质量检查

- 重复时间戳：`0`
- 非 15分钟间隔：`0`
- OHLC 异常行：`0`
- 补齐K线行：`0`
- 不完整月份：`0`
- 缺失月份：`0`

## 继承 14号的重要结论

- 2024 public futures 行数：`35136`
- 2024 event 行数：`35136`
- close 不匹配行数：`0`
- 14号策略族判断：`STOP_FAMILY`

## 判断

`DATA_BASELINE_READY`

下一步不要继续修 `ret_state 64/100` 老家族。更合适的是在这份统一 futures 数据底座上，另起 16号做新策略族或新特征探针。
