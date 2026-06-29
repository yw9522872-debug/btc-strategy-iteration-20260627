# 40号多币种 Funding 提前识别审计

这不是策略，不能交易。它只检查 funding 能不能帮39号的“活跃山寨币动量/反转”规律提前选对。

## 做法

- 下载 Binance 免费 USD-M futures fundingRate REST 历史。
- 币种：ETH、SOL、DOGE、XRP、ADA、AVAX、LINK。
- 每个月只用上个月已经知道的 funding、涨跌幅和波动率。
- 不下载 premium，不下载成交流；先测最小的 funding 信号。

## Funding 对赢家的解释

- 有 funding 数据的赢家月份：`40`
- 赢家上月 funding 绝对值排名中位数：`3.5`
- 赢家上月 funding 绝对值排前3比例：`50.0%`
- 赢家上月 funding 为正比例：`82.5%`

## 不看未来选择器

最好测试：`hot_abs_funding_abs_both`

- 2023：`6662.64%`
- 2024：`-90.19%`
- 2025：`203.32%`
- 2026 YTD：`18.01%`
- 交易月份：`17`
- 亏损交易月份：`6`

## 判断

`FUNDING_SIGNAL_WEAK_NOT_TRADEABLE`

Funding 有一点“拥挤度”信息，但还不能把39号规律变成合格策略。

下一步如果继续，不要扩 funding-only 小规则，应测试 premium 或成交流这类更早、更细的信号。
