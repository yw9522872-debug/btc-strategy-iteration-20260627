# Strategy 60：尾部事件极简因果风控上限测试

这是研究审计，不是实盘策略。

## 口径

- 复用58号最好收益配置的逐K收益。
- 不重新训练动作模型，不新增入场规则。
- 风控只看上一根K线已经发生后的月内亏损、月内回撤、账户回撤。
- 这是偏乐观上限：直接缩放58号逐K收益，没有重新撮合真实开平仓成本。

## 58号基线复放

- 2025: `144.16%`
- 2026: `151.71%`
- 最大回撤: `-65.31%`

## 选中展示配置

- month_loss_trigger: `-0.2`
- month_dd_trigger: `None`
- account_dd_trigger: `-0.25`
- triggered_scale: `0.5`
- 2025: `167.25%`
- 2026: `52.75%`
- 最大回撤: `-49.66%`
- 是否过放宽门槛: `False`

## 回撤合格里收益最高

- month_loss_trigger: `-0.2`
- month_dd_trigger: `None`
- account_dd_trigger: `-0.25`
- triggered_scale: `0.5`
- 2025: `167.25%`
- 2026: `52.75%`
- 最大回撤: `-49.66%`
- 是否过放宽门槛: `False`

## 结论

- `SIMPLE_CAUSAL_RISK_OVERLAY_UPPER_BOUND_FAILS_RELAXED_GATE`
- 回撤能压到 -49.66%，但最低目标年收益只有 52.75%，达不到100%。
