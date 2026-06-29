# Strategy 61：新数据源是否值得继续

本文件记录 61 号研究结论。

这不是策略，不是回测，也不能交易。它只回答一个问题：

> 现在旧路线都失败后，要不要花钱或花时间找新数据源？

## 结论

61号结论：

`ONLY_TARDIS_SAMPLE_THEN_UPPER_BOUND`

通俗说：

> 不要马上买大数据包。
> 如果还想继续，只优先找 Tardis.dev 要最小样本或最小导出。
> 样本过不了质量检查，就不买；样本过了，再考虑完整 CSV。
> 拿到完整 CSV 后，也先做“看答案上限测试”，上限不过就马上停。

## 为什么不能继续用免费数据

Binance 官方公开 REST 不够做多年回测：

- open interest history 只保留最近 `1` 个月。
- global long/short ratio 只保留最近 `30` 天。

我们需要检查的是多年历史，至少覆盖 `2023-01` 到 `2026-05`，所以官方免费接口不够。

项目里 16号到60号已经反复证明：

- 免费K线小规则不行。
- funding-only 不行。
- spot-perp aggTrades 样本不行。
- BTC/HYPE 尾部事件严格动作选择和极简风控也不行。

所以继续研究只能靠真正不同的数据源，不能再补旧规则。

## 优先级

### 1. Tardis.dev：唯一优先

适合原因：

- Binance USDS-M Futures 历史覆盖从 `2019-11-17` 开始。
- open interest 生成频道从 `2020-05-12` 开始。
- `derivative_ticker` 里的 open interest 从 `2020-05-13` 开始。
- `topLongShortAccountRatio`、`topLongShortPositionRatio`、`globalLongShortAccountRatio` 从 `2020-10-28` 开始。
- `takerlongshortRatio` 从 `2021-12-01` 开始。
- 有 CSV/API，字段带交易所时间和本地时间，方便查断档和防未来函数。

这正好覆盖我们最关心的 `2023-01` 到 `2026-05`。

### 2. CoinGlass：只做备选

适合原因：

- 有 open interest history 接口。
- 有 global/top long-short ratio history 接口。
- 支持 15m 等周期。

限制：

- 低级套餐历史范围不够多年。
- CSV/bulk export 和自定义历史范围更偏 Enterprise。
- 如果不能确认给出 `2020-10-28` 到 `2026-05-31` 的完整 Binance BTCUSDT futures 导出，就不适合本项目。

### 3. Amberdata：机构级备选

适合原因：

- 产品说明包含 funding、open interest、long/short ratios。
- 支持 API、AWS S3、Snowflake 等交付方式。
- 数据质量和机构审计可能更强。

限制：

- 通常更偏机构级，价格和交付要先问清。
- 如果不给样本或明确字段口径，不建议先买。

## 最小样本要求

如果继续，只要下面这些，不要先买大包：

数据源优先：`Tardis.dev`

交易所和品种：

- `binance-futures`
- `BTCUSDT`

频道：

- `openInterest`
- `derivative_ticker`，至少要有 `open_interest`
- `globalLongShortAccountRatio`
- `topLongShortAccountRatio`
- `topLongShortPositionRatio`
- 可选：`takerlongshortRatio`

最小样本月份：

- `2023-07`
- `2024-06`
- `2025-08`
- `2026-05`

这四个月都是此前多次暴露问题的关键月份。样本先过关，再谈完整历史。

完整历史要求：

- 多空比：`2020-10-28` 到 `2026-05-31`
- 持仓量：`2020-05-13` 到 `2026-05-31`

## 买之前必须满足

1. 能导出 CSV 或等价可复查文件。
2. 文件里有明确时间戳，最好同时有交易所时间和本地接收时间。
3. 覆盖完整，不是只给最近几个月。
4. 不需要把 API key 写进项目。
5. 允许我们本地保存数据做研究回测。

不满足任意一条，就不买。

## 拿到数据后怎么做

不能直接做策略。

下一步顺序必须是：

1. 62号：数据质量审计
   检查覆盖、重复、断档、字段缺失、和15m K线底座对齐。

2. 63号：看答案上限测试
   故意看答案，先问“历史上有没有足够空间”。

3. 如果63号上限不过，停止。
   不做严格选择器，不写策略。

4. 只有上限过了，才做64号严格不看未来选择器。

## 来源

- Binance Open Interest Statistics: `https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Open-Interest-Statistics`
- Binance Long/Short Ratio: `https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Long-Short-Ratio`
- Tardis Binance USDS-M Futures: `https://docs.tardis.dev/historical-data-details/binance-futures`
- Tardis Binance Futures metadata API: `https://api.tardis.dev/v1/exchanges/binance-futures`
- CoinGlass Pricing: `https://www.coinglass.com/pricing`
- CoinGlass Open Interest History: `https://docs.coinglass.com/reference/oi-ohlc-histroy`
- CoinGlass Global Long/Short Account Ratio: `https://docs.coinglass.com/reference/global-longshort-account-ratio`
- Amberdata Market Data: `https://www.amberdata.io/market-data`
- Amberdata Open Interest Data Dictionary: `https://docs.amberdata.io/data-dictionary/market/open-interest`
