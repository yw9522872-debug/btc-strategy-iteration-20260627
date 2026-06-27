# 13号低换手/低反手预防规则

本文件用于定位 13号实验。它不是固化版，也不能升级候选。

它只回答一个问题：

只用 `2023` 训练期，能不能选出一个“少反手、低换手”的确认规则，让完整 `2024` 通过硬条件？

## 身份

- 实验编号：`strategy_13_low_turnover_prevention_20260627`
- 来源脚本：`scripts/search_strategy_13_low_turnover_prevention_20260627.py`
- 结果目录：`artifacts/strategy_13_low_turnover_prevention_20260627/`
- 主要结果：`artifacts/strategy_13_low_turnover_prevention_20260627/summary.json`
- 报告：`artifacts/strategy_13_low_turnover_prevention_20260627/report.md`

## 规则

基础信号仍是 `ret_state window=64 threshold=100 bps`。

新增的低反手规则很简单：

新方向连续出现 `confirm_bars` 根 15分钟K线后，才允许切换方向。

测试的 `confirm_bars`：`1, 2, 4, 8, 12`。

`confirm_bars=1` 就等于原始直接反手。

## 结果

只用 `2023` 选择后，选中的还是：

- `confirm_bars=1`
- `leverage=6`
- `lock_log=0.04`
- `quota_arm_log=0.08`
- `quota_leverage=0.25`

完整 `2024` 测试：

- 年收益：`+114.96%`
- 亏损月：`1`
- 最差月：`-6.45%`
- 最少月交易：`12`
- 是否通过：`False`

也就是说，严格用 `2023` 选择时，系统没有选择低反手确认规则，`2024-12` 亏损仍然存在。

## 事后诊断

事后看 `2024`，确实有 `24` 个候选能通过完整 2024。

事后最佳 2024 收益约 `+183.61%`，对应 `confirm_bars=4`。

但这是看答案，不能交易，不能拿来升级策略。

## 判断

13号是负面实验。

它说明“确认几根再反手”这个方向有潜力，但只靠 `2023` 训练期并不会自然选出它。

下一步如果继续，不应该直接拿 `confirm_bars=4` 固化；更好的做法是先请 GPT Pro 复核 10/11/12/13，再决定是否需要更严格的数据或更保守的评估方法。

## 边界

- 这里只做研究和回测。
- 不下实盘，不读取密钥，不启动 supervisor。
- 没有覆盖 0号、1F、1G、2C、3号、4号、10号、11号或 12号。
