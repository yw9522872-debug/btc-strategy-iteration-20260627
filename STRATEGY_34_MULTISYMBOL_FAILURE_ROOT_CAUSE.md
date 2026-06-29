# 34号多币种失败根因审计

本文件用于定位 34号审计。它不是策略，不能交易，也不是固化版。

34号只做一件事：

拆解 33号为什么失败，看能不能通过修根因让策略盈利。

## 身份

- 审计编号：`strategy_34_multisymbol_failure_root_cause_20260629`
- 来源脚本：`scripts/audit_strategy_34_multisymbol_failure_root_cause_20260629.py`
- 结果目录：`artifacts/strategy_34_multisymbol_failure_root_cause_20260629/`
- 主要结果：`artifacts/strategy_34_multisymbol_failure_root_cause_20260629/summary.json`
- 报告：`artifacts/strategy_34_multisymbol_failure_root_cause_20260629/report.md`
- 来源：33号多币种完整历史严格选择器

## 口径

- 只做研究回测，不下实盘。
- 不读取密钥。
- 不启动 supervisor。
- 不改真实仓位。
- 不新增交易规则。
- 不重新下载数据。
- 只复用 33号已经生成的 `candidate_monthly.csv`、`selector_monthly.csv`、`selected_params.csv` 和 `oracle_monthly.csv`。

## 结果

34号结论是：`ROOT_CAUSE_UNSTABLE_HINDSIGHT_SELECTION`。

通俗说：

33号不是完全没有赚钱机会，而是当月开始前选不准。看答案能挑到好候选；只看过去数据时，好候选通常排不靠前，上月赢家下月也不稳定。

关键结果：

- 评估月份：`41`
- 严格选择器不达标月份：`33`
- 有“每月10单且正收益”候选的月份：`41`
- 训练期没有硬通过候选的月份：`41`
- 当月 oracle 赢家在月初训练排序里的中位名次：`222`
- oracle 赢家月初排进前10的月份：`0`
- 跟随上月 oracle 赢家：2025 `-99.9983%`，2026 YTD `-96.7508%`

失败月份拆分：

- 严格选择器净亏损月份：`21`
- 手续费把毛盈利打成净亏：`3` 个月
- 行情方向本身亏：`18` 个月
- 交易次数不足10次：`13` 个月

## 判断

通过拆根因可以看清问题，但不能直接把这批规则修成可靠盈利策略。

主因不是“缺一个小补丁”，而是多币种免费K线候选的赢家换得太快：过去表现很难提前选中当月赢家。

后续不要先加交易规则。若继续，只能另起新编号测试真正不同的选择方法，并先做上限/泄漏审计。
