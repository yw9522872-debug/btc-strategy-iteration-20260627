# Freqtrade/Jesse 式研究规范

本文件只管研究流程，不代表任何策略可以实盘。

## 核心原则

- 0号策略永久不覆盖；任何新参数、新数据、新规则都另起新编号。
- 每次研究都要有三件东西：`STRATEGY_xx_*.md`、`scripts/*_2026*.py`、`artifacts/*/summary.json`。
- 信号只能用已经收盘的数据；如果在第 `t` 根K线收盘后产生信号，只能从第 `t+1` 根K线开始吃收益。
- 手续费默认保持开平合计 `0.2%`，代码里就是单边 `0.001`。
- 任何结果都必须写明：年度收益、月度收益、交易次数、手续费口径、是否看未来。

## 每个新策略的目录

新策略用这个格式：

```text
STRATEGY_48_简短名字.md
scripts/audit_strategy_48_简短名字_20260629.py
artifacts/strategy_48_简短名字_20260629/
```

目录里至少放：

```text
summary.json
report.md
monthly.csv
yearly.csv
trades.csv 或 signals.csv
```

如果只是查资料，例如搜索 Jesse 策略，也放到 `artifacts/资料名_日期/`，不要混进策略结果目录。

## summary.json 必填字段

以后新脚本的 `summary.json` 尽量统一写这些字段：

```json
{
  "status": "xxx_ready",
  "strategy_id": "strategy_48_xxx_20260629",
  "generated_at": "UTC时间",
  "research_only": true,
  "not_live_trading": true,
  "orders_generated": false,
  "orders_submitted": false,
  "secret_access": false,
  "data": {
    "symbols": ["BTCUSDT"],
    "timeframe": "15m",
    "start": "2020-01-01 00:00 UTC",
    "end": "2026-05-31 23:45 UTC",
    "quality_checked": true
  },
  "cost_model": {
    "round_trip_cost_pct": 0.2,
    "cost_per_side": 0.001
  },
  "parameters": {},
  "leakage": {
    "uses_closed_bars_only": true,
    "enters_next_bar": true,
    "current_month_labels_used_for_current_month": false,
    "tradable_strategy": false
  },
  "metrics": {
    "yearly": {},
    "monthly_loss_count": 0,
    "min_monthly_trades": 0,
    "max_drawdown_pct": 0.0
  },
  "dry_run": {
    "paper_or_dry_run_required_before_live": true,
    "live_orders_allowed": false
  },
  "decision": {
    "verdict": "XXX",
    "promote_strategy": false,
    "reason": "一句话说明"
  },
  "files": {}
}
```

通俗说：以后看一个 `summary.json`，不用翻代码，也能知道数据从哪来、参数是什么、有没有未来函数、有没有下单。

## 回测口径

- 回测先跑数据质量：重复、断档、缺失月份、OHLC 异常。
- 年度表必须至少包含 2025 和 2026 YTD。
- 月度表必须有每月收益和每月交易次数。
- 交易次数口径要写清楚，是完整交易笔数，还是持仓切换次数。
- 胜率不要混用：如果是“持仓K线正收益占比”，就不要叫完整交易胜率。

## 干跑口径

借 Freqtrade/Jesse 的思路，实盘前必须先过干跑，但本项目现在只做研究：

- 默认禁止真实下单。
- 默认禁止读取 `.env`、API key、secret、token。
- 如果以后要接 Freqtrade 或 Jesse，只能先用 dry-run、paper、sandbox、testnet。
- 干跑也要输出 `summary.json`，并写明 `orders_submitted=false`。

## 参数记录

每次扫描都要把参数完整落盘：

- 全量扫描结果：`scan.csv` 或 `config_scan.csv`。
- 最好参数：放进 `summary.json` 的 `parameters` 或 `best_policy`。
- 被淘汰原因：写进 `report.md`。
- 如果参数是同一段历史里挑出来的，必须写明“样本内挑参，不能实盘”。

## Jesse 公共策略处理

可以搜索和下载公开仓库里的 Jesse 策略，但只当学习材料：

- 先记录来源链接、仓库、路径和许可证情况。
- 不直接把别人策略当成我们策略。
- 不直接相信别人回测图。
- 必须改造成本项目统一回测口径，再检查未来函数、手续费、月度收益和交易次数。

配套脚本：

```powershell
python scripts/search_public_jesse_strategies_20260629.py
```

默认只保存清单。如果确认许可证和用途没问题，再用：

```powershell
python scripts/search_public_jesse_strategies_20260629.py --download
```

跳过项：明显黑灰产、偷盗、hack、cheat、需要密钥才能运行的仓库。
