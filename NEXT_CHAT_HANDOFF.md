# 下一窗口交接

本文件用于开启新的 Codex 对话时交接本项目。

## 项目身份

- 本地路径：`C:\Users\WHR\Documents\策略迭代`
- GitHub：`https://github.com/yw9522872-debug/btc-strategy-iteration-20260627`
- 1F/1G 策略结果提交：`e4232d3`
- 固化标签：`strategy-freeze-monthly-profit-lock-20260627`
- 固化标签对应提交：`910d99a`
- 当前固化策略源提交：`0c69585`
- 0号策略定位文件：`STRATEGY_0.md`
- 1号F保存标签：`strategy-1f-selective-runner-20260627`
- 1号G保存标签：`strategy-1g-cap7-selective-runner-20260627`

不要和其他 Codex 线程、其他 Chrome/GPT Pro 页面、其他仓库混用。

## 必读文件

1. `AGENTS.md`
2. `STRATEGY_0.md`
3. `STRATEGY_1_CANDIDATE.md`
4. `STRATEGY_1B_CANDIDATE.md`
5. `STRATEGY_1C_CANDIDATE.md`
6. `STRATEGY_1F_CANDIDATE.md`
7. `STRATEGY_1G_CANDIDATE.md`
8. `CURRENT_STRATEGY_FREEZE.md`
9. `GPT_PRO_REVIEW_BRIEF.md`
10. `artifacts/strategy_freeze_monthly_profit_lock_20260627/freeze.json`

## 当前固化策略

- 策略编号：`0号策略`
- 固化编号：`monthly_profit_lock_research_freeze_20260627`
- 品种：`BTCUSDT`
- 周期：`15m`
- 信号：`ret_state`
- 回看窗口：`64` 根 15分钟K线
- 阈值：`100 bps`
- 杠杆：`8x`
- 手续费：开平合计 `0.2%`，代码里单边 `0.001`
- 月度锁利：当月至少 `10` 次交易且当月净对数收益达到 `0.04` 后，本月剩余时间空仓
- 月内补交易控制：当月净对数收益达到 `0.12` 但交易次数未满 `10` 次时，仓位降到 `0.1x` 直到交易次数补够

## 已知结果

按固化版历史结果：

| 年份 | 收益率 | 胜率 | 交易次数 | 最大回撤 |
|---|---:|---:|---:|---:|
| 2025 | `+326.26%` | `50.00%` | `148` | `-48.53%` |
| 2026 | `+106.93%` | `50.66%` | `72` | `-18.21%` |

胜率口径是“持仓中的 15分钟K线正收益占比”，不是严格单笔完整交易胜率。

## 1号策略候选

- 候选编号：`strategy_1_candidate_20260627`
- 定位文件：`STRATEGY_1_CANDIDATE.md`
- 脚本：`scripts/search_strategy_1_candidate_20260627.py`
- 结果：`artifacts/strategy_1_candidate_20260627/summary.json`
- 2025：`+171.35%`，交易 `152` 次，最大回撤 `-24.01%`
- 2026：`+126.55%`，交易 `74` 次，最大回撤 `-19.42%`
- 每个评估月份都盈利，最低月交易次数 `12`
- 注意：它还不是固化版；固定信号 `ret_state 64/100` 仍来自前期历史研究。
- 另一个更自由的测试 `artifacts/strategy_1_walkforward_20260627/summary.json` 失败：2025 `-22.09%`，说明信号自由滚动选会追错参数。

## 1号B策略候选

- 候选编号：`strategy_1b_expanded_controls_20260627`
- 定位文件：`STRATEGY_1B_CANDIDATE.md`
- 脚本：`scripts/search_strategy_1b_expanded_controls_20260627.py`
- 结果：`artifacts/strategy_1b_expanded_controls_20260627/summary.json`
- 2025：`+419.18%`，交易 `150` 次，最大回撤 `-31.28%`
- 2026：`+199.48%`，交易 `74` 次，最大回撤 `-26.09%`
- 每个评估月份都盈利，最低月交易次数 `12`
- 相对 0号：2025/2026收益更高，2025回撤更小，但 2026 回撤更大。
- 风险：固定信号仍来自前期研究；会选到 `12x` 杠杆；开平合计手续费压到 `0.4%` 会失败。

## 1号C策略候选

- 候选编号：`strategy_1c_trend_runner_20260627`
- 定位文件：`STRATEGY_1C_CANDIDATE.md`
- 脚本：`scripts/search_strategy_1c_trend_runner_20260627.py`
- 结果：`artifacts/strategy_1c_trend_runner_20260627/summary.json`
- 2025：`+503.36%`，交易 `180` 次，最大回撤 `-31.28%`
- 2026：`+199.61%`，交易 `82` 次，最大回撤 `-26.09%`
- 每个评估月份都盈利，最低月交易次数 `12`
- 改进点：针对图上“月度锁利后错过大趋势”的问题，锁利后只在强趋势条件下用 `0.25x` 小仓位继续跟随。
- 风险：固定信号仍来自前期研究；趋势跟随规则是本轮看图后追加的研究规则；开平合计手续费压到 `0.4%` 会失败。

## 1号F策略候选

- 候选编号：`strategy_1f_selective_runner_20260627`
- 定位文件：`STRATEGY_1F_CANDIDATE.md`
- 脚本：`scripts/search_strategy_1f_selective_runner_20260627.py`
- 结果：`artifacts/strategy_1f_selective_runner_20260627/summary.json`
- 图片：
  - `artifacts/strategy_1f_selective_runner_20260627/strategy1f_trades_2025.png`
  - `artifacts/strategy_1f_selective_runner_20260627/strategy1f_trades_2026.png`
- 2025：`+433.74%`，交易 `158` 次，最大回撤 `-29.40%`
- 2026：`+260.59%`，交易 `72` 次，最大回撤 `-29.25%`
- 每个评估月份都盈利，最低月交易次数 `11`
- 诊断：强趋势反向大仓仅 `1` 根 15分钟K线；弱趋势区大仓开单 `0` 次。
- 压力测试：开平合计 `0.3%`、`0.4%`、信号晚 1 根K线、`0.3% + 晚1根` 都通过。
- 当前判断：比 1B/1C 图形更干净，是更稳的 1号候选。

## 1号G策略候选

- 候选编号：`strategy_1g_cap7_selective_runner_20260627`
- 定位文件：`STRATEGY_1G_CANDIDATE.md`
- 脚本：`scripts/search_strategy_1g_cap7_selective_runner_20260627.py`
- 结果：`artifacts/strategy_1g_cap7_selective_runner_20260627/summary.json`
- 图片：
  - `artifacts/strategy_1g_cap7_selective_runner_20260627/strategy1g_trades_2025.png`
  - `artifacts/strategy_1g_cap7_selective_runner_20260627/strategy1g_trades_2026.png`
- 2025：`+471.14%`，交易 `160` 次，最大回撤 `-27.87%`
- 2026：`+246.16%`，交易 `72` 次，最大回撤 `-28.67%`
- 每个评估月份都盈利，最低月交易次数 `11`
- 诊断：强趋势反向大仓仅 `1` 根 15分钟K线；弱趋势区大仓开单 `0` 次。
- 压力测试：开平合计 `0.3%` 和信号晚 1 根K线通过；开平合计 `0.4%`、`0.3% + 晚1根` 失败。
- 当前判断：固定 `0.2%` 手续费下，1G 数字更漂亮；如果更重视压力测试，1F 更稳。

## 重要风险

- 当前执行逻辑没有发现明显未来函数：信号只用已收盘K线，下一根K线才吃收益。
- 参数是事后从历史中挑出来的，过拟合风险高。
- 已做过更严格检查：用 2024 年选参数，再测 2025/2026，没有达到每年 100%。
- 本轮新增 `artifacts/profit_lock_walkforward_20260627/summary.json`：固定老信号 `ret_state window=64 threshold=100`，但每个月只用前面月份选择锁利/补交易/杠杆参数。这个检查在本地特征数据上通过：2025 `+171.35%`，2026 `+126.55%`，无亏损评估月份，最低月交易次数 `12`。注意：固定信号本身仍来自历史研究，所以还不能说完全不过拟合。
- 2026 主结果用本地数据到 `2026-06-19 23:45 UTC`。
- 另有 Binance 补测到 `2026-06-26 18:30 UTC`，补测后 6 月已锁利空仓。
- 本项目只做研究和回测，不下实盘，不读取密钥，不启动 supervisor。

## 下一轮建议

0号策略不要覆盖。下一轮如果继续做，只能另起新编号、新目录，例如：

- 做更严格的 walk-forward / out-of-sample 验证；
- 降低过拟合风险；
- 补最新数据后复测；
- 对 `profit_lock_walkforward_20260627` 做二次检查：尤其检查固定 `ret_state 64/100` 信号是否也能用更早数据独立选出来；
- 重新设计更稳健的非事后选参规则；
- 对 1F/1G 做更严格的独立样本验证，尤其不要只看 2025/2026 图形继续加规则；
- 每次新结果都写清楚手续费、未来函数检查、月度收益、交易次数、最大回撤。

## 发到下一个窗口的内容

```text
请接着这个项目继续工作：

本地路径：C:\Users\WHR\Documents\策略迭代
GitHub：https://github.com/yw9522872-debug/btc-strategy-iteration-20260627

请先阅读：
1. AGENTS.md
2. NEXT_CHAT_HANDOFF.md
3. STRATEGY_0.md
4. STRATEGY_1_CANDIDATE.md
5. STRATEGY_1B_CANDIDATE.md
6. STRATEGY_1C_CANDIDATE.md
7. STRATEGY_1F_CANDIDATE.md
8. STRATEGY_1G_CANDIDATE.md
9. CURRENT_STRATEGY_FREEZE.md
10. GPT_PRO_REVIEW_BRIEF.md
11. artifacts/strategy_freeze_monthly_profit_lock_20260627/freeze.json

重要：不要和其他 Codex 线程、其他浏览器 GPT Pro 页面、其他仓库混淆。

当前已有固化研究版：
monthly_profit_lock_research_freeze_20260627

这一版已经定位为 0号策略，必须永久保留。后续优化必须另起新编号、新文件夹，不能覆盖 0号策略。

它的历史结果：
2025 收益 +326.26%，胜率 50.00%，交易次数 148，最大回撤 -48.53%。
2026 收益 +106.93%，胜率 50.66%，交易次数 72，最大回撤 -18.21%。

手续费按开平合计 0.2%。
当前执行逻辑没发现明显未来函数。
但参数是历史事后挑出来的，过拟合风险高。
2024 选参再测 2025/2026 没达到每年 100%。

当前保存的 1号候选：
1F：标签 strategy-1f-selective-runner-20260627，2025 +433.74%，2026 +260.59%，更稳，0.4% 开平合计手续费压力测试通过。
1G：标签 strategy-1g-cap7-selective-runner-20260627，2025 +471.14%，2026 +246.16%，当前 0.2% 手续费下数字更漂亮，但 0.4% 手续费压力测试失败。

后续如果继续开发，不能覆盖 0号策略，必须另起新编号、新文件夹。
这里只做研究和回测，不下实盘，不读取密钥，不启动 supervisor。

请用中文、通俗的话和我沟通。
```
