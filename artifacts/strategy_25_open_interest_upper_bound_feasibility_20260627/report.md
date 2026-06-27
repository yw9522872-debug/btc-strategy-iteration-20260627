# 25号持仓量上限可行性审计

这不是策略，也不是收益回测。它只检查持仓量历史数据够不够做 2020-2026 上限测试。

## 检查结果

- `historical_2020_01`：ok `False`，rows `0`，error `{"msg":"parameter 'startTime' is invalid.","code":-1130}`
- `historical_2023_01`：ok `False`，rows `0`，error `{"msg":"parameter 'startTime' is invalid.","code":-1130}`
- `baseline_end_2026_05`：ok `True`，rows `97`，error ``
- `recent_latest`：ok `True`，rows `500`，error ``

## 判断

`OPEN_INTEREST_HISTORY_NOT_AVAILABLE_FOR_2020_2026`

Binance公开openInterestHist接口只返回最近1个月，无法覆盖2020-2026历史硬目标区间。

下一步：不要用不完整持仓量做2023-2026上限；若要继续，需要先找到可审计的完整历史数据源，或改做最近1个月的观察表。
