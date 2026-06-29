from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_ml_trader.backtest import run_vector_backtest  # noqa: E402


DATA = ROOT / "artifacts" / "strategy_21_volume_upper_bound_20260627" / "btc_15m_2020_2026_05_public_volume_klines.csv"
OUT_DIR = ROOT / "artifacts" / "public_jesse_strategy_backtests_20260629"
COST_PER_SIDE_BPS = 10.0
TIMEFRAMES = {"15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h"}
BARS_PER_YEAR = {"15m": 365 * 24 * 4, "30m": 365 * 24 * 2, "1h": 365 * 24, "4h": 365 * 6}


def main() -> None:
    args = _args()
    if args.self_test:
        _self_test()
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = _load_15m()
    frames = {tf: _resample(base, tf) for tf in TIMEFRAMES}

    rows, monthly_parts, yearly_parts, skipped = [], [], [], []
    for spec in _specs():
        if spec.get("status") == "skip":
            skipped.append(spec)
            continue
        df = frames[spec["timeframe"]]
        signals = spec["fn"](df).copy()
        out, stats = run_vector_backtest(
            signals[["timestamp", "close", "target_position"]],
            fee_bps=COST_PER_SIDE_BPS,
            slippage_bps=0.0,
            bars_per_year=BARS_PER_YEAR[spec["timeframe"]],
        )
        monthly = _period(out, "M")
        yearly = _period(out, "Y")
        monthly.insert(0, "strategy", spec["name"])
        yearly.insert(0, "strategy", spec["name"])
        monthly_parts.append(monthly)
        yearly_parts.append(yearly)
        rows.append(_row(spec, stats, monthly, yearly))

    summary_df = pd.DataFrame(rows).sort_values(["return_2025_pct", "return_2026_ytd_pct"], ascending=False)
    monthly_df = pd.concat(monthly_parts, ignore_index=True) if monthly_parts else pd.DataFrame()
    yearly_df = pd.concat(yearly_parts, ignore_index=True) if yearly_parts else pd.DataFrame()
    skipped_df = pd.DataFrame(skipped)

    summary_df.to_csv(OUT_DIR / "backtest_summary.csv", index=False)
    monthly_df.to_csv(OUT_DIR / "monthly.csv", index=False)
    yearly_df.to_csv(OUT_DIR / "yearly.csv", index=False)
    skipped_df.to_csv(OUT_DIR / "skipped.csv", index=False)

    summary = {
        "status": "public_jesse_strategy_backtests_ready",
        "strategy_id": "public_jesse_strategy_backtests_20260629",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "not_live_trading": True,
        "orders_generated": False,
        "orders_submitted": False,
        "secret_access": False,
        "data": {
            "symbol": "BTCUSDT",
            "source": _rel(DATA),
            "base_timeframe": "15m",
            "start": str(base["timestamp"].min()),
            "end": str(base["timestamp"].max()),
            "resampled_timeframes": sorted(TIMEFRAMES),
        },
        "cost_model": {"round_trip_cost_pct": 0.2, "cost_per_side": 0.001},
        "execution_model": {
            "proxy_backtest": True,
            "uses_closed_bars_only": True,
            "enters_next_bar": True,
            "not_exact_jesse_engine": True,
            "position_notional": "1x target-position proxy",
        },
        "tested_count": int(len(summary_df)),
        "skipped_count": int(len(skipped_df)),
        "decision": {
            "verdict": "PUBLIC_JESSE_STRATEGY_PROXY_BACKTEST_DONE",
            "promote_strategy": False,
            "reason": "这些是公开 Jesse 策略的本地代理回测；周期尽量按源码/路径识别，结果只能用于筛想法，不能直接升级策略。",
        },
        "files": {
            "summary": _rel(OUT_DIR / "summary.json"),
            "report": _rel(OUT_DIR / "report.md"),
            "backtest_summary": _rel(OUT_DIR / "backtest_summary.csv"),
            "monthly": _rel(OUT_DIR / "monthly.csv"),
            "yearly": _rel(OUT_DIR / "yearly.csv"),
            "skipped": _rel(OUT_DIR / "skipped.csv"),
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT_DIR / "report.md").write_text(_report(summary, summary_df, skipped_df), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    return p.parse_args()


def _specs() -> list[dict]:
    return [
        {"name": "jesse_example_macd_ema", "source": "jesse-ai/example-strategies/MACD_EMA", "timeframe": "1h", "timeframe_basis": "docstring says Timeframe: 1h", "fn": _macd_ema},
        {"name": "devon_macd_ema", "source": "Devon-ODell/quant/macd-ema_v1", "timeframe": "1h", "timeframe_basis": "same Jesse MACD_EMA source family says 1h", "fn": _macd_ema},
        {"name": "devon_donchian", "source": "Devon-ODell/quant/donchian_v1", "timeframe": "15m", "timeframe_basis": "no explicit timeframe; project default 15m", "fn": _donchian},
        {"name": "jesse_example_turtle_rules", "source": "jesse-ai/example-strategies/TurtleRules", "timeframe": "15m", "timeframe_basis": "no explicit timeframe; project default 15m", "fn": _turtle},
        {"name": "ben_walker_turtle_rules", "source": "ben-walker/jesse-trade/TurtleRules", "timeframe": "15m", "timeframe_basis": "no explicit timeframe; project default 15m", "fn": _turtle},
        {"name": "brainctl_sma_sample", "source": "TSchonleber/brainctl/sample_strategy", "timeframe": "15m", "timeframe_basis": "no explicit timeframe; project default 15m", "fn": _sma_sample},
        {"name": "dcupmusic_always_long_demo", "source": "dcupmusic/strategies/backtest_demo", "timeframe": "1h", "timeframe_basis": "source route sets timeframe='1h'", "fn": _always_long},
        {"name": "bitmania_trendtype", "source": "Justant-source/Bit-Mania/trendtype/4h", "timeframe": "4h", "timeframe_basis": "source path contains 4h", "fn": _trendtype},
        {"name": "bitmania_tradeiq_cci_ce", "source": "Justant-source/Bit-Mania/tradeiq_cci_ce/4h", "timeframe": "4h", "timeframe_basis": "source path contains 4h", "fn": _tradeiq_cci_ce},
        {"name": "strat16_three_rails_reverse", "source": "arti-st/JesseTrade-strategies/Strat16", "status": "skip", "reason": "limit-entry plus intrabar stop/take-profit; no explicit timeframe; proxy would be misleading"},
        {"name": "range_reversal", "source": "deemzie/jesse/RangeReversal", "status": "skip", "timeframe": "4h", "reason": "recommended 4h, but depends on custom_indicators and hard-coded ETH-like zones 1700-4200; BTC backtest is not meaningful"},
        {"name": "triple_supertrend_tf", "source": "deemzie/jesse/TripleSupertrendTF", "status": "skip", "reason": "multi-timeframe limit-entry/add-on order strategy; not faithful without Jesse order engine"},
        {"name": "astro_strategy_rsi", "source": "financial-astrology-research/AstroStrategyRSI", "status": "skip", "reason": "requires external daily astrology CSV files not present in downloaded source"},
        {"name": "amt_trend_continuation", "source": "nishimweprince/trading-algos/AMTTrendContinuation", "status": "skip", "reason": "requires custom volume-profile indicators and partial exits; not faithful in simple OHLCV proxy"},
        {"name": "ysdede_helpers", "source": "ysdede/jesse_strategies helpers", "status": "skip", "reason": "downloaded files are helper/playground code, not complete Jesse strategies"},
    ]


def _load_15m() -> pd.DataFrame:
    df = pd.read_csv(DATA, parse_dates=["timestamp"])
    return df[["timestamp", "open", "high", "low", "close", "volume"]].sort_values("timestamp")


def _resample(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    if tf == "15m":
        return df.copy()
    out = df.set_index("timestamp").resample(TIMEFRAMES[tf], label="left", closed="left").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).dropna().reset_index()
    return out


def _macd_ema(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"]
    ema100 = close.ewm(span=100, adjust=False).mean()
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    sig = macd.ewm(span=9, adjust=False).mean()
    return _state(df, close.gt(ema100) & macd.gt(sig), pd.Series(False, index=df.index), macd.lt(sig) & close.lt(ema100), None)


def _donchian(df: pd.DataFrame) -> pd.DataFrame:
    upper = df["high"].shift(1).rolling(20).max()
    lower = df["low"].shift(1).rolling(20).min()
    sma200 = df["close"].rolling(200).mean()
    return _state(df, df["close"].gt(upper) & df["close"].gt(sma200), pd.Series(False, index=df.index), df["close"].lt(lower), None)


def _turtle(df: pd.DataFrame) -> pd.DataFrame:
    upper = df["high"].shift(1).rolling(20).max()
    lower = df["low"].shift(1).rolling(20).min()
    exit_upper = df["high"].shift(1).rolling(10).max()
    exit_lower = df["low"].shift(1).rolling(10).min()
    atr = _atr(df, 20)
    return _state(
        df,
        df["high"].ge(upper),
        df["low"].le(lower),
        df["low"].le(exit_lower),
        df["high"].ge(exit_upper),
        atr=atr,
        atr_mult=2.0,
    )


def _sma_sample(df: pd.DataFrame) -> pd.DataFrame:
    fast = df["close"].rolling(9).mean()
    slow = df["close"].rolling(21).mean()
    long = fast.shift(1).le(slow.shift(1)) & fast.gt(slow)
    return _state(df, long, pd.Series(False, index=df.index), None, None, stop_pct=-0.05, take_pct=0.05)


def _always_long(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["target_position"] = 1.0
    return out


def _trendtype(df: pd.DataFrame) -> pd.DataFrame:
    trend = _trend_type(df)
    atr = _atr(df, 14)
    return _state(df, trend.eq(2), trend.eq(-2), trend.ne(2), trend.ne(-2), atr=atr, atr_mult=3.0)


def _tradeiq_cci_ce(df: pd.DataFrame) -> pd.DataFrame:
    cci = _cci(df, 20)
    direction = _chandelier_dir(df, 22, 3.0)
    long = cci.shift(1).lt(-100) & cci.gt(-100) & direction.eq(1)
    short = cci.shift(1).gt(100) & cci.lt(100) & direction.eq(-1)
    return _state(df, long, short, None, None, atr=_atr(df, 14), atr_mult=3.0, exit_on_profit=True)


def _state(
    df: pd.DataFrame,
    long: pd.Series,
    short: pd.Series,
    exit_long: pd.Series | None,
    exit_short: pd.Series | None,
    *,
    atr: pd.Series | None = None,
    atr_mult: float | None = None,
    stop_pct: float | None = None,
    take_pct: float | None = None,
    exit_on_profit: bool = False,
) -> pd.DataFrame:
    close = df["close"].to_numpy()
    target = np.zeros(len(df))
    pos = 0.0
    entry = math.nan
    for i in range(len(df)):
        xl = bool(exit_long.iloc[i]) if exit_long is not None and not pd.isna(exit_long.iloc[i]) else False
        xs = bool(exit_short.iloc[i]) if exit_short is not None and not pd.isna(exit_short.iloc[i]) else False
        if pos > 0 and (xl or _hit(close[i], entry, 1, atr.iloc[i] if atr is not None else math.nan, atr_mult, stop_pct, take_pct, exit_on_profit)):
            pos = 0.0
        elif pos < 0 and (xs or _hit(close[i], entry, -1, atr.iloc[i] if atr is not None else math.nan, atr_mult, stop_pct, take_pct, exit_on_profit)):
            pos = 0.0
        if pos == 0:
            if bool(long.iloc[i]) if not pd.isna(long.iloc[i]) else False:
                pos, entry = 1.0, close[i]
            elif bool(short.iloc[i]) if not pd.isna(short.iloc[i]) else False:
                pos, entry = -1.0, close[i]
        target[i] = pos
    out = df.copy()
    out["target_position"] = target
    return out


def _hit(price: float, entry: float, side: int, atr: float, atr_mult: float | None, stop_pct: float | None, take_pct: float | None, exit_on_profit: bool) -> bool:
    if not math.isfinite(entry):
        return False
    ret = side * (price / entry - 1.0)
    if stop_pct is not None and ret <= stop_pct:
        return True
    if take_pct is not None and ret >= take_pct:
        return True
    if atr_mult is None or not math.isfinite(atr):
        return False
    move = side * (price - entry)
    return move <= -atr_mult * atr or (exit_on_profit and move >= atr_mult * atr)


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([(df["high"] - df["low"]), (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _cci(df: pd.DataFrame, period: int) -> pd.Series:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    ma = tp.rolling(period).mean()
    md = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (tp - ma) / (0.015 * md)


def _trend_type(df: pd.DataFrame) -> pd.Series:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    prev = df["close"].shift(1)
    tr = pd.concat([(df["high"] - df["low"]), (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    tr_sum = tr.rolling(14).sum()
    plus_di = 100 * plus_dm.rolling(14).sum() / tr_sum
    minus_di = 100 * minus_dm.rolling(14).sum() / tr_sum
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.rolling(14).mean()
    active = adx.gt(20) & atr.gt(atr.rolling(20).mean())
    return pd.Series(np.where(active & plus_di.gt(minus_di), 2, np.where(active & minus_di.gt(plus_di), -2, 0)), index=df.index)


def _chandelier_dir(df: pd.DataFrame, period: int, mult: float) -> pd.Series:
    atr = _atr(df, period)
    long_stop = df["high"].rolling(period).max() - mult * atr
    short_stop = df["low"].rolling(period).min() + mult * atr
    out = np.zeros(len(df))
    last = 0.0
    for i, close in enumerate(df["close"]):
        if i and close > short_stop.iloc[i - 1]:
            last = 1.0
        elif i and close < long_stop.iloc[i - 1]:
            last = -1.0
        out[i] = last
    return pd.Series(out, index=df.index)


def _period(out: pd.DataFrame, freq: str) -> pd.DataFrame:
    key = out["timestamp"].dt.tz_localize(None).dt.to_period(freq).astype(str)
    g = out.groupby(key)
    res = g.agg(log_return=("strategy_log_return", "sum"), trades=("turnover", lambda x: int((x > 0).sum())), max_drawdown_pct=("drawdown", "min")).reset_index(names="period")
    res["return_pct"] = (np.exp(res["log_return"]) - 1.0) * 100
    res["max_drawdown_pct"] *= 100
    return res[["period", "return_pct", "max_drawdown_pct", "trades"]]


def _row(spec: dict, stats, monthly: pd.DataFrame, yearly: pd.DataFrame) -> dict:
    target_months = monthly[monthly["period"].between("2025-01", "2026-12")]
    yr = dict(zip(yearly["period"], yearly["return_pct"]))
    return {
        "strategy": spec["name"],
        "source": spec["source"],
        "timeframe": spec["timeframe"],
        "timeframe_basis": spec["timeframe_basis"],
        "total_return_pct": stats.total_return_pct,
        "max_drawdown_pct": stats.max_drawdown_pct,
        "trade_count": stats.trade_count,
        "turnover": stats.turnover,
        "return_2025_pct": yr.get("2025", 0.0),
        "return_2026_ytd_pct": yr.get("2026", 0.0),
        "monthly_loss_count_2025_2026": int((target_months["return_pct"] <= 0).sum()) if len(target_months) else 0,
        "min_monthly_trades_2025_2026": int(target_months["trades"].min()) if len(target_months) else 0,
    }


def _report(summary: dict, rows: pd.DataFrame, skipped: pd.DataFrame) -> str:
    lines = [
        "# Jesse 公开策略代理回测",
        "",
        "这是本项目统一口径下的代理回测，不是 Jesse 原生撮合结果。",
        "",
        f"- 数据：BTCUSDT USD-M futures，`{summary['data']['start']}` 到 `{summary['data']['end']}`",
        "- 手续费：开仓 `0.1%`，平仓 `0.1%`，开平合计 `0.2%`",
        "- 执行：信号只用已收盘K线，下一根K线开始吃收益",
        f"- 已回测：`{summary['tested_count']}` 个；跳过：`{summary['skipped_count']}` 个",
        "",
        "## 回测汇总",
        "",
        "| 策略 | 周期 | 周期依据 | 2025 | 2026 YTD | 最大回撤 | 交易次数 | 2025-2026亏损月 |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in rows.iterrows():
        lines.append(
            f"| `{r['strategy']}` | `{r['timeframe']}` | {r['timeframe_basis']} | "
            f"{r['return_2025_pct']:.2f}% | {r['return_2026_ytd_pct']:.2f}% | {r['max_drawdown_pct']:.2f}% | "
            f"{int(r['trade_count'])} | {int(r['monthly_loss_count_2025_2026'])} |"
        )
    lines += ["", "## 跳过项", "", "| 策略 | 原因 |", "|---|---|"]
    for _, r in skipped.iterrows():
        lines.append(f"| `{r['name']}` | {r['reason']} |")
    lines += ["", "结论：这些公开策略没有直接成为本项目候选；只能挑规则形状继续二次改造。"]
    return "\n".join(lines) + "\n"


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _self_test() -> None:
    toy = pd.DataFrame({
        "timestamp": pd.date_range("2020-01-01", periods=30, freq="15min", tz="UTC"),
        "open": np.arange(30.0) + 100,
        "high": np.arange(30.0) + 101,
        "low": np.arange(30.0) + 99,
        "close": np.arange(30.0) + 100,
        "volume": 1.0,
    })
    assert len(_resample(toy, "1h")) == 8
    assert _macd_ema(toy)["target_position"].abs().max() <= 1
    assert _cci(toy, 5).notna().sum() > 0
    print("self-test ok")


if __name__ == "__main__":
    main()
