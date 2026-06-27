# 15号统一数据底座体检

本文件用于定位 15号数据体检。它不是新策略，也不是收益回测。

它只回答一个问题：

以后换新策略族时，能不能先统一使用 14号确认过的 USD-M futures 15分钟K线底座？

## 身份

- 体检编号：`strategy_15_unified_data_baseline_20260627`
- 来源脚本：`scripts/audit_strategy_15_unified_data_baseline_20260627.py`
- 结果目录：`artifacts/strategy_15_unified_data_baseline_20260627/`
- 主要结果：`artifacts/strategy_15_unified_data_baseline_20260627/summary.json`
- 报告：`artifacts/strategy_15_unified_data_baseline_20260627/report.md`

## 数据底座

15号不重新下载数据，只检查 14号已经生成的合并K线：

- 文件：`artifacts/strategy_14_pre2023_expanding_crowding_stress_audit_20260627/btc_15m_2020_2026_05_combined_ohlc.csv`
- 品种：`BTCUSDT`
- 周期：`15m`
- 数据口径：Binance USD-M futures 公共K线，加本地 `event_entry_fullscan` 尾部
- 时间范围：`2020-01-01 00:00 UTC` 到 `2026-05-31 23:45 UTC`
- 总行数：`224928`
- 月份数：`77`

来源拆分：

- `2020-2024`：Binance public USD-M futures archive，`175392` 行
- `2025-2026-05`：本地 `event_entry_fullscan`，`49536` 行

## 质量检查

- 重复时间戳：`0`
- 非 15分钟断档：`0`
- OHLC 异常行：`0`
- 补齐K线行：`0`
- 不完整月份：`0`
- 缺失月份：`0`

继承 14号对齐检查：

- 2024 public futures：`35136` 行
- 2024 本地 event：`35136` 行
- close 差异：`0`

## 判断

15号结论是：`DATA_BASELINE_READY`。

通俗说：以后如果另起新策略族，先用这份 futures 统一K线当底座，不要再混用 spot 探针和旧 event 口径。

同时，14号已经把 `ret_state 64/100` 家族判为 `STOP_FAMILY`。15号只是准备新底座，不恢复这个老家族。

## 边界

- 这里只做数据体检。
- 不下实盘，不读取密钥，不启动 supervisor。
- 没有覆盖 0号、1F、1G、2C、4号、10号、11号、12号、13号或 14号。
