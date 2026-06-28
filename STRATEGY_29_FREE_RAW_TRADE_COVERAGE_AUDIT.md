# 29号免费 raw trade 数据覆盖审计

本文件用于定位 29号审计。它不是策略，不能交易，也不是固化版。

它只回答一个问题：

免费 Binance 公开数据，够不够做“现货-永续合约成交流错位”研究？

## 身份

- 审计编号：`strategy_29_free_raw_trade_coverage_audit_20260628`
- 来源脚本：`scripts/audit_strategy_29_free_raw_trade_coverage_20260628.py`
- 结果目录：`artifacts/strategy_29_free_raw_trade_coverage_audit_20260628/`
- 主要结果：`artifacts/strategy_29_free_raw_trade_coverage_audit_20260628/summary.json`
- 报告：`artifacts/strategy_29_free_raw_trade_coverage_audit_20260628/report.md`

## 审计口径

29号不下载大文件，只用 HTTP HEAD 检查 Binance 免费公开月包是否存在。

检查月份：

- `2020-01` 到 `2026-05`
- 共 `77` 个月

## 覆盖结果

全部通过：

| 数据 | 作用 | 覆盖 |
|---|---|---:|
| futures `aggTrades` | 合约主动买卖成交流 | `77/77` |
| spot `aggTrades` | 现货主动买卖成交流 | `77/77` |
| futures `trades` | 更重的原始合约逐笔 | `77/77` |
| spot `trades` | 更重的原始现货逐笔 | `77/77` |
| futures 1m K线 | 合约校验/低成本特征 | `77/77` |
| spot 1m K线 | 现货校验/价差 | `77/77` |
| fundingRate | 资金费率过滤 | `77/77` |
| markPriceKlines 1m | 标记价格 | `77/77` |
| indexPriceKlines 1m | 指数价格 | `77/77` |
| premiumIndexKlines 1m | 溢价指数 | `77/77` |

可选的 `bookTicker` 月包探针不通过，2020-01 返回 `404`。因此不要把秒级盘口纳入主研究。

## 数据大小

压缩包大概很大：

- futures `aggTrades`：约 `39.56 GB`
- spot `aggTrades`：约 `50.70 GB`
- futures `trades`：约 `61.40 GB`
- spot `trades`：约 `67.99 GB`

所以下一步如果下载，优先用 `aggTrades`，不要一开始就下载更重的 `trades`。

## 判断

29号结论是：`FREE_SPOT_PERP_RAW_TRADE_DATA_AVAILABLE`。

通俗说：

这条免费路线还能再试一次。

不是继续调均线、RSI、ATR，也不是继续修旧 `ret_state 64/100`。

下一次只做一个方向：

现货 BTCUSDT 和 USD-M 永续 BTCUSDT 的成交流错位，也就是看现货和合约谁先动、谁没跟上。

## 下一步

另起 30号。

30号只做：

- spot-perp `aggTrades` 成交流错位上限测试。
- funding / mark / index / premium 只能当过滤器。
- 不扫一堆币。
- 不继续扩免费K线小规则。
