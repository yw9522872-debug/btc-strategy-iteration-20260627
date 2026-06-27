# 10号 pre-2024 数据探针

本文件用于定位 10号数据探针。它不是新策略，也不做收益回测。

它只回答一个问题：

能不能补到一份干净的 `2023` 年 BTCUSDT 15分钟公开K线，作为下一步 2024 真正 walk-forward 的基础？

## 身份

- 探针编号：`strategy_10_pre2024_data_probe_20260627`
- 来源脚本：`scripts/audit_strategy_10_pre2024_data_probe_20260627.py`
- 结果目录：`artifacts/strategy_10_pre2024_data_probe_20260627/`
- 主要结果：`artifacts/strategy_10_pre2024_data_probe_20260627/summary.json`
- 报告：`artifacts/strategy_10_pre2024_data_probe_20260627/report.md`
- 官方原始OHLC文件：`artifacts/strategy_10_pre2024_data_probe_20260627/btc_15m_2023_official_ohlc.csv`
- 补齐日历OHLC文件：`artifacts/strategy_10_pre2024_data_probe_20260627/btc_15m_2023_ohlc.csv`
- 特征探针文件：`artifacts/strategy_10_pre2024_data_probe_20260627/btc_15m_2023_feature_probe.csv`
- 官方缺口 REST 复查：`artifacts/strategy_10_pre2024_data_probe_20260627/official_gap_rest_probe.csv`

## 判断

10号只补数据，不改策略规则。

如果数据检查通过，下一步应该另起 11号：

- 用 2023 或更早数据提前选择规则/参数；
- 再测 2024；
- 不能把 2025 以后保存下来的参数倒回去测 2024。

## 风险

- Binance 官方 2023 数据在 `2023-03-24` 有 5 根15分钟K线缺口；公开 REST 接口复查也没有返回这 5 根。
- 补齐版用上一根收盘价补平，并用 `calendar_filled=True` 标记。
- 这里的指标是从公开K线重新计算的“探针版特征”，不是原始 `event_entry_fullscan` 文件的精确复刻。
- 它适合做下一步严格 walk-forward 的数据底座检查。
- 它不代表策略盈利，也不代表未来实盘稳定。
- 本项目仍然只做研究和回测，不下实盘，不读取密钥，不启动 supervisor。
