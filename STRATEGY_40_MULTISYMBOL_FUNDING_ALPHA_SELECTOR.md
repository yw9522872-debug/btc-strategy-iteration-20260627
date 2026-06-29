# 40号多币种 Funding 提前识别审计

本文件用于定位 40号审计。它不是策略，不能交易，也不是固化版。

40号只做一件事：

按39号发现的规律，检查 funding 能不能提前识别“近期活跃山寨币本月该做动量还是反转”。

## 身份

- 审计编号：`strategy_40_multisymbol_funding_alpha_selector_20260629`
- 来源脚本：`scripts/audit_strategy_40_multisymbol_funding_alpha_selector_20260629.py`
- 结果目录：`artifacts/strategy_40_multisymbol_funding_alpha_selector_20260629/`
- 主要结果：`artifacts/strategy_40_multisymbol_funding_alpha_selector_20260629/summary.json`
- 报告：`artifacts/strategy_40_multisymbol_funding_alpha_selector_20260629/report.md`

## 口径

- 只做研究回测，不下实盘。
- 不读取密钥。
- 不启动 supervisor。
- 不改真实仓位。
- 新下载的数据只包括 Binance 免费 USD-M futures fundingRate REST 历史。
- 币种只取39号常见赢家：`ETH`、`SOL`、`DOGE`、`XRP`、`ADA`、`AVAX`、`LINK`。
- 时间从 `2022-12` 到 `2026-05`，因为评估从 `2023-01` 开始，每个月只用上个月已经知道的 funding。
- 没有下载 premium，也没有下载成交流；先测最小的 funding 信号。

## 数据质量

每个币都有：

- 行数：`3834`
- 月份：`42`
- 首月：`2022-12`
- 末月：`2026-05`
- 重复时间戳：`0`
- 非8小时 funding 间隔：`0`

## Funding 对赢家的解释

40号发现 funding 有一点解释力：

- 有 funding 数据的赢家月份：`40`
- 赢家上月 funding 绝对值排名中位数：`3.5`
- 赢家上月 funding 绝对值排前3比例：`50.0%`
- 赢家上月 funding 为正比例：`82.5%`

按规则拆：

- 动量赢家上月 funding 为正：`79.17%`
- 反转赢家上月 funding 为正：`87.50%`
- 反转赢家上月 funding 绝对值排名中位数：`3.0`

通俗说：赢家币常常已经有正 funding，说明市场有点拥挤；但这个信号不够强，不能单独告诉我们本月该追涨还是反打。

## 不看未来选择器

最好测试是：`hot_abs_funding_abs_both`

意思是：

- 先找上月涨跌幅绝对值靠前的热币；
- 再要求上月 funding 绝对值也靠前；
- 再在已有33号单币动量/反转候选里选。

结果：

- 2023：`+6662.64%`
- 2024：`-90.19%`
- 2025：`+203.32%`
- 2026 YTD：`+18.01%`
- 交易月份：`17`
- 亏损交易月份：`6`
- 最差交易月：`-76.35%`

这比39号只看K线的简单选择器更有信息，但仍不能达到原始硬目标。

## 判断

40号结论是：`FUNDING_SIGNAL_WEAK_NOT_TRADEABLE`。

Funding 确实给了“拥挤度”线索，但还不能把39号规律变成合格策略。

后续不要继续扩 funding-only 小规则。若继续，应另起41号测试 premium 或成交流这类更早、更细的信号。
