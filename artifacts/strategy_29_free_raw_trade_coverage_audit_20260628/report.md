# 29号免费 raw trade 数据覆盖审计

这不是策略，也不是收益回测。它只检查免费公开数据够不够做下一步成交流错位研究。

## 覆盖结果

- `futures_um_aggTrades`：coverage `True`，missing `0`，size `39.558` GB
- `spot_aggTrades`：coverage `True`，missing `0`，size `50.699` GB
- `futures_um_trades`：coverage `True`，missing `0`，size `61.396` GB
- `spot_trades`：coverage `True`，missing `0`，size `67.988` GB
- `futures_um_1m_klines`：coverage `True`，missing `0`，size `0.135` GB
- `spot_1m_klines`：coverage `True`，missing `0`，size `0.156` GB
- `futures_um_fundingRate`：coverage `True`，missing `0`，size `0.0` GB
- `futures_um_markPriceKlines_1m`：coverage `True`，missing `0`，size `0.08` GB
- `futures_um_indexPriceKlines_1m`：coverage `True`，missing `0`，size `0.086` GB
- `futures_um_premiumIndexKlines_1m`：coverage `True`，missing `0`，size `0.058` GB

## 可选盘口探针

- `futures_um_bookTicker_2020_01`：ok `False`，status `404`
- `spot_bookTicker_2020_01`：ok `False`，status `404`

## 判断

`FREE_SPOT_PERP_RAW_TRADE_DATA_AVAILABLE`

现货/合约aggTrades、1m K线、funding、mark/index/premium 月包都覆盖 2020-01 到 2026-05，可以继续做一次成交流错位上限测试。

下一步：另起30号，只做 spot-perp raw trade lead-lag + basis/funding filter 的上限测试；不要再扩免费K线小规则。
