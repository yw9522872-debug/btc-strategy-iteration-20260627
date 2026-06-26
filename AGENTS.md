# 项目工作说明

## 沟通方式

- 用户是一位 80 岁老人，尽量用中文，用最通俗的话说明。
- 除非必须确认危险操作，否则不要频繁打扰用户。
- 如需通过浏览器询问 GPT Pro，问题开头必须标明本项目路径 `C:\Users\WHR\Documents\策略迭代` 和本线程目标，避免和其他 Codex 线程混淆。
- 不混用其他线程的浏览器结论、文件路径或运行结果。

## 当前究极任务

目标是在本项目里继续研究策略，寻找一个历史回测满足下面条件的版本：

- 2025 年收益率大于 100%。
- 2026 年收益率大于 100%。
- 不能使用未来函数，信号只能用当时已经收盘的数据。
- 市价开仓和平仓的总交易成本按 0.2% 计算。
- 历史回测中每个月都盈利。
- 每个月交易次数最低 10 次。

当前已固化研究版：`monthly_profit_lock_research_freeze_20260627`，见 `CURRENT_STRATEGY_FREEZE.md` 和 `artifacts/strategy_freeze_monthly_profit_lock_20260627/freeze.json`。以后改参数、手续费、规则或数据时，不要覆盖这个固化版，要另起新版本。

## GitHub 与 GPT Pro 协作

- 本项目身份：`C:\Users\WHR\Documents\策略迭代`，BTC 15m 策略迭代研究。
- GitHub 仓库：`https://github.com/yw9522872-debug/btc-strategy-iteration-20260627`。
- GitHub 仓库只用于同步本项目文件和给 GPT Pro 读取，不要混用其他项目或其他 Codex 线程的仓库。
- 给 GPT Pro 的问题开头必须同时写本地路径和 GitHub 仓库 URL。
- GPT Pro 优先阅读 `GPT_PRO_REVIEW_BRIEF.md`，再看 `AGENTS.md`、`scripts/` 和 `artifacts/*/summary.json`。
- 推送前先检查不要包含 API key、secret、token、`.env` 或实盘下单配置。

## 工作边界

- 这里只做研究、回测、检查，不下实盘订单。
- 不读取、不打印、不保存 API key、secret、token 或 `.env`。
- 不启动实盘 supervisor。
- 不改真实仓位。

## 验证要求

- 任何候选策略都要输出年度、月度、交易次数和手续费口径。
- 发现结果太好时，优先检查是否有未来函数或标签泄漏。
- “每个月都盈利”只能表示历史回测月份盈利，不能承诺未来真实市场一定盈利。
