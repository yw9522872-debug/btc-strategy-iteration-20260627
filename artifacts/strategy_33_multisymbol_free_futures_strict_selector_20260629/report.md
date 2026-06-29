# 33号多币种完整历史严格选择器

这不是策略，不能交易，也不是固化版。它只检查 31号“四个月样本看答案”信号，扩到完整历史后，能不能严格不看未来地提前选中。

## 数据

- 主币种：BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, DOGEUSDT, XRPUSDT, ADAUSDT, AVAXUSDT, LINKUSDT
- 附加观察但不参与选择：HYPEUSDT
- 数据：Binance 免费 USD-M futures 15m 月包
- 范围：`2020-01-01T00:00:00+00:00` 到 `2026-05-31T23:45:00+00:00`
- 行数：`224928`
- 重复时间：`0`
- 15分钟断档：`0`
- 手续费：开平合计 `0.20%`
- 时序：信号只用已收盘K线，下一根15分钟K线才吃收益

## 候选

- 候选数：`744`
- 静态事后硬通过数：`0`
- 最好静态候选：`single_symbol_symbol_momentum_lev1p0_symbolLINKUSDT_lookback1536_threshold_bps20`

## 最好每月10单看答案上限

- oracle：`monthly_oracle_best_return_order10`
- 2025：`17665719.09%`
- 2026 YTD：`4414.40%`
- 不盈利月份数：`0`
- 最差月：`25.64%`
- 最少月交易：`14`

## 最好严格选择器

- selector：`all_multisymbol`
- 2023：`17.72%`
- 2024：`-21.17%`
- 2025：`-46.85%`
- 2026 YTD：`-5.64%`
- 不盈利月份数：`21`
- 最差月：`-21.89%`
- 最少月交易：`1`
- 最大回撤：`-69.49%`

## 判断

`MULTISYMBOL_ORACLE_HAS_PIECES_BUT_STRICT_SELECTOR_FAILS`

看答案的月度oracle能过，但严格逐月选择器不能提前选中正确候选。

下一步：不要升级为策略；除非换真正新的选择方法或新数据，否则不要继续堆同类小规则。
