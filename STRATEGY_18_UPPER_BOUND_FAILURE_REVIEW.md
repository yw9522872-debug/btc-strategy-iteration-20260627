# 18号上限失败月份复盘

本文件用于定位 18号复盘。它不是策略，也不是候选。

它只回答一个问题：

17号已经是“看答案”的上限测试，为什么仍然过不了每月盈利和每月10次交易硬条件？

## 身份

- 复盘编号：`strategy_18_upper_bound_failure_review_20260627`
- 来源脚本：`scripts/audit_strategy_18_upper_bound_failure_review_20260627.py`
- 结果目录：`artifacts/strategy_18_upper_bound_failure_review_20260627/`
- 主要结果：`artifacts/strategy_18_upper_bound_failure_review_20260627/summary.json`
- 报告：`artifacts/strategy_18_upper_bound_failure_review_20260627/report.md`

## 复盘对象

来源是 17号的失败月份。

17号最宽松上限仍有 `6` 个不盈利月份；要求每月交易不少于 `10` 后，失败月份扩到 `10` 个。

18号把这 `10` 个月统一复盘。

## 失败类型

| 类型 | 月份数 | 含义 |
|---|---:|---|
| `no_positive_candidate` | `6` | 144个简单候选里，没有任何一个当月正收益 |
| `positive_only_with_too_few_orders` | `4` | 有正收益候选，但交易次数不到10；满足10次交易的候选全亏 |

## 失败月份

| 月份 | 类型 | BTC月涨跌 | 最佳全候选 | 最佳10单候选 |
|---|---|---:|---:|---:|
| 2023-07 | no_positive_candidate | `-4.00%` | `+0.00%` / `0`单 | `-0.08%` / `34`单 |
| 2023-09 | positive_only_with_too_few_orders | `+3.73%` | `+0.16%` / `8`单 | `-2.44%` / `24`单 |
| 2024-04 | positive_only_with_too_few_orders | `-14.85%` | `+22.66%` / `7`单 | `-1.78%` / `39`单 |
| 2024-06 | positive_only_with_too_few_orders | `-7.17%` | `+21.68%` / `7`单 | `-1.60%` / `16`单 |
| 2024-12 | no_positive_candidate | `-3.19%` | `-3.00%` / `26`单 | `-3.00%` / `26`单 |
| 2025-06 | no_positive_candidate | `+2.55%` | `+0.00%` / `0`单 | `-2.04%` / `16`单 |
| 2025-07 | positive_only_with_too_few_orders | `+7.85%` | `+4.65%` / `2`单 | `-0.32%` / `13`单 |
| 2025-09 | no_positive_candidate | `+5.62%` | `+0.00%` / `0`单 | `-3.36%` / `46`单 |
| 2026-04 | no_positive_candidate | `+12.21%` | `+0.00%` / `0`单 | `-1.52%` / `18`单 |
| 2026-05 | no_positive_candidate | `-3.63%` | `+0.00%` / `0`单 | `-0.49%` / `10`单 |

## 判断

18号结论是：`FAILURE_MONTHS_EXPLAIN_SIMPLE_FAMILY_STOP`。

通俗说：这批简单规则在很多失败月份里，最好的选择其实是“不交易”；一旦要求每月10次交易，就变成亏钱。

所以问题不是再多加几个均线参数就能解决。下一步不要继续扩这批均线、Donchian、RSI、布林带、ATR突破简单规则。

## 边界

- 这里只做研究和回测。
- 不下实盘，不读取密钥，不启动 supervisor。
- 没有覆盖 0号、1F、1G、2C、4号、10号、11号、12号、13号、14号、15号、16号或17号。
