# 持仓量和多空比历史数据源审查

本文件不是策略，不是回测结果，也不能交易。

它只回答一个问题：

后面如果要测试“持仓量/多空比”这类新数据，应该先找哪种完整、能复查的数据源？

## 结论

当前结论：不要用 Binance 官方公开 REST 接口直接做多年历史回测。

原因很简单：

- Binance 官方 `openInterestHist` 只保留最近 `1` 个月。
- Binance 官方多空比接口只保留最近 `30` 天。
- 我们要测的是 `2023-01` 到 `2026-05`，所以官方公开接口不够。

优先数据源排序：

1. `Tardis.dev`，最优先。
2. `CoinGlass`，可以作为备选，但要先确认套餐能否给足够长的 15m 历史。
3. `Amberdata`，机构级备选，适合有账号或 CSV/S3 导出的情况。
4. `Coin Metrics`、`Kaiko`、`CCData/CoinDesk Data`，更适合做持仓量补充；多空比覆盖不如前面明确。

## 1. Tardis.dev

优先级：最高。

适合原因：

- 有 Binance USDS-M Futures 历史数据说明。
- 能通过 API 或 CSV 拿数据。
- 数据带 `exchange`、`symbol`、`timestamp`、`local_timestamp` 等字段，后面方便审计。
- 文档说明 Binance USDS-M Futures 历史数据从 `2019-11-17` 开始。
- `openInterest` 生成频道从 `2020-05-12` 开始。
- `derivative_ticker` 里的 `open_interest` 从 `2020-05-13` 开始。
- `topLongShortAccountRatio`、`topLongShortPositionRatio`、`globalLongShortAccountRatio` 从 `2020-10-28` 开始。
- `takerlongshortRatio` 从 `2021-12-01` 开始。

我已现场抽查过公开 CSV 样例：

- 样例地址：`https://datasets.tardis.dev/v1/binance-futures/derivative_ticker/2020/06/01/BTCUSDT.csv.gz`
- 能正常下载。
- 字段包含 `exchange,symbol,timestamp,local_timestamp,funding_timestamp,funding_rate,predicted_funding_rate,open_interest,last_price,index_price,mark_price`。
- 2020-06-01 样例里能看到 `open_interest = 34653.577`。

限制：

- 多空比不是从 2020-01 开始，而是从 `2020-10-28` 开始。
- 完整多年历史一般需要账号或付费导出。
- 后面不要在脚本里保存 API key；最好让用户把 CSV 导出后放到本地目录。

适合我们项目吗？

适合。因为我们的主要评估期是 `2023-01` 到 `2026-05`，Tardis 的持仓量和多空比覆盖这个评估期，也有足够多的评估前历史做训练。

## 2. CoinGlass

优先级：第二。

适合原因：

- 文档有 futures open interest history 接口。
- 文档有 global long/short account ratio history。
- 文档有 top trader account ratio history。
- 文档有 top trader position ratio history。
- 查询参数支持 Binance、BTCUSDT、1m/15m/1h/1d 等周期。

限制：

- 需要 API key。
- 套餐历史范围有限制：公开价格页显示，低级套餐的 15m 历史只给最近几十到一百多天；多年 15m 历史可能需要更高套餐或 Enterprise 的自定义历史范围/CSV 导出。
- CoinGlass 是整理后的指标数据，审计深度不如 Tardis 这种带原始交易所时间和采集说明的数据。

适合我们项目吗？

可以作为备选。若能拿到 `2020-10-28` 到 `2026-05-31` 的 BTCUSDT Binance 15m 或更细粒度导出，可以另起新编号做数据质量审计。若只能拿最近几个月，不适合做多年硬目标回测。

## 3. Amberdata

优先级：第三。

适合原因：

- 文档和产品页说明有历史 futures open interest、funding、long/short ratio 等数据。
- 支持 REST API、S3、CSV 等交付方式。
- 偏机构级，适合需要正式数据来源和审计说明的场景。

限制：

- 需要账号或商务导出。
- 使用前必须确认 Binance BTCUSDT USD-M futures 的具体历史起点、时间粒度、字段口径。
- 如果 REST 历史窗口有限，要用 bulk/S3/CSV，而不是只用 REST。

适合我们项目吗？

适合作为 Tardis 之外的机构级备选。拿到导出文件后再做数据质量审计。

## 不建议当主数据源

Binance 官方 REST：

- 适合核对最近数据。
- 不适合多年回测。

Kaggle、Gigasheet、论坛整理表：

- 可以临时看一眼。
- 不适合作为主审计来源，除非它同时给出原始采集脚本、不可变历史快照、字段口径和缺失记录。

网页截图、交易软件图表：

- 不适合回测。
- 不能逐行复查，不能严格防未来函数。

## 下一步建议

最稳妥的下一步：

先用 `Tardis.dev`。

需要导出的数据：

- `binance-futures / BTCUSDT / derivative_ticker`，至少包含 `open_interest`。
- `binance-futures / BTCUSDT / globalLongShortAccountRatio`。
- `binance-futures / BTCUSDT / topLongShortAccountRatio`。
- `binance-futures / BTCUSDT / topLongShortPositionRatio`。
- 可选：`binance-futures / BTCUSDT / takerlongshortRatio`。

建议时间范围：

- 多空比：`2020-10-28` 到 `2026-05-31`。
- 如果只测持仓量：`2020-05-13` 到 `2026-05-31`。
- 评估期仍用 `2023-01` 到 `2026-05`。

拿到 CSV 后，下一步才另起新编号：

1. 先做数据质量审计：时间覆盖、重复、断档、字段缺失、和 15号 K线底座对齐。
2. 再做“看答案”的上限测试。
3. 如果上限不过，停止这条线。
4. 如果上限过，再做严格逐月选择器。

在拿到完整 CSV 前，不要硬做持仓量/多空比多年回测。

## 来源

- Binance Open Interest Statistics: `https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics`
- Binance Long/Short Ratio: `https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Long-Short-Ratio`
- Binance Top Trader Long/Short Account Ratio: `https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Top-Long-Short-Account-Ratio`
- Binance Top Trader Long/Short Position Ratio: `https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Top-Trader-Long-Short-Ratio`
- Tardis Binance USDS-M Futures: `https://docs.tardis.dev/historical-data-details/binance-futures`
- CoinGlass Open Interest History: `https://docs.coinglass.com/reference/oi-ohlc-histroy`
- CoinGlass Global Long/Short Account Ratio: `https://docs.coinglass.com/reference/global-longshort-account-ratio`
- CoinGlass Top Long/Short Account Ratio: `https://docs.coinglass.com/reference/top-longshort-account-ratio`
- CoinGlass Top Long/Short Position Ratio: `https://docs.coinglass.com/reference/top-longshort-position-ratio`
- CoinGlass Pricing / Historical Range: `https://www.coinglass.com/pricing`
- Amberdata Open Interest Data Dictionary: `https://docs.amberdata.io/data-dictionary/market/open-interest`
- Amberdata Market Data: `https://www.amberdata.io/market-data`
- Amberdata Binance Market Data: `https://www.amberdata.io/binance-market-data`
- Coin Metrics Market Level Open Interest: `https://gitbook-docs.coinmetrics.io/market-data/market-data-overview/open_interest/market-open-interest`
- Kaiko Level 1 and Level 2 Market Data: `https://www.kaiko.com/products/l1-l2-data`
- CoinDesk Data Futures Historical Open Interest Minute: `https://developers.coindesk.com/documentation/data-api/futures_v1_historical_open_interest_minutes`
