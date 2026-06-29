# Strategy 56：尾部事件亏损根因审计

- 这是亏损归因，不是策略。
- 复用55号结果，不新增候选、不调参数。

## 根因结论

- `LOSS_ROOT_CAUSE_UNSTABLE_ACTION_SELECTION`
- 亏损根因不是事件不存在，而是事件后的正确动作每月切换太快；过去表现很难提前告诉我们该顺势还是反转。严格选择器为了控制回撤，长期偏向低杠杆BTC动作，结果错过HYPE大机会，收益被磨成小亏。

## 关键证据

- oracle 月份数：`13`
- oracle 不同候选数：`10`
- oracle 动作切换次数：`10`
- 严格选择器选中同一个候选的月份：`0`
- 严格选择器选中同一种动作的月份：`2`
- 严格选择器错过正收益oracle的月份：`10`
- oracle赢家在训练期排序中位名次：`98.0`
- oracle赢家训练期排前10的月份：`0/12`
- 跟随上月oracle赢家为正的月份：`5/12`
- 跟随上月oracle赢家收益简单求和：`22.81%`
- 当月oracle收益简单求和：`652.46%`

## 文件

- oracle_vs_strict_by_month: `artifacts/strategy_56_tail_event_loss_root_cause_20260630/oracle_vs_strict_by_month.csv`
- oracle_train_rank_by_month: `artifacts/strategy_56_tail_event_loss_root_cause_20260630/oracle_train_rank_by_month.csv`
- follow_previous_oracle_by_month: `artifacts/strategy_56_tail_event_loss_root_cause_20260630/follow_previous_oracle_by_month.csv`
- action_summary: `artifacts/strategy_56_tail_event_loss_root_cause_20260630/action_summary.csv`
