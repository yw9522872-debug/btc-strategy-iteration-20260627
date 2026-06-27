from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--equity", required=True)
    parser.add_argument("--features", default="artifacts/event_entry_fullscan/event_entry_best_signals.csv")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    equity = pd.read_csv(ROOT / args.equity)
    features = pd.read_csv(ROOT / args.features, usecols=["timestamp", "trend_close_ema_gap_bps_60", "trend_adx_30"])
    equity["timestamp"] = pd.to_datetime(equity["timestamp"], utc=True)
    features["timestamp"] = pd.to_datetime(features["timestamp"], utc=True)
    frame = equity.merge(features, on="timestamp", how="left")
    frame["delta_position"] = frame["position"] - frame["active_position"]
    frame["strong_trend"] = (frame["trend_adx_30"] >= 30) & (frame["trend_close_ema_gap_bps_60"].abs() >= 350)
    frame["flat"] = frame["active_position"].abs() < 1e-12

    _configure_plot_font()
    paths = []
    for year in ["2025", "2026"]:
        path = _plot_year(frame.loc[frame["timestamp"].dt.strftime("%Y") == year].copy(), out_dir, args.name, year)
        if path:
            paths.append(path)
    print("\n".join(str(path.relative_to(ROOT)).replace("\\", "/") for path in paths))


def _plot_year(data: pd.DataFrame, out_dir: Path, name: str, year: str) -> Path | None:
    if data.empty:
        return None
    buys = data.loc[data["delta_position"] > 0]
    sells = data.loc[data["delta_position"] < 0]
    strong_flat = data["strong_trend"] & data["flat"]

    fig, (ax_price, ax_pos) = plt.subplots(
        2,
        1,
        figsize=(22, 10),
        dpi=140,
        sharex=True,
        gridspec_kw={"height_ratios": [4, 1]},
    )
    ax_price.plot(data["timestamp"], data["close"], color="#222831", linewidth=0.7, label="BTC收盘价")
    ax_price.scatter(
        buys["timestamp"],
        buys["close"],
        marker="^",
        s=_marker_sizes(buys["delta_position"].abs()),
        color="#0a9f6a",
        edgecolors="white",
        linewidths=0.25,
        label="买点/减空",
        zorder=4,
    )
    ax_price.scatter(
        sells["timestamp"],
        sells["close"],
        marker="v",
        s=_marker_sizes(sells["delta_position"].abs()),
        color="#d93b52",
        edgecolors="white",
        linewidths=0.25,
        label="卖点/减多",
        zorder=4,
    )
    _shade_mask(ax_price, data, data["strong_trend"], "#f2c94c", 0.10, "强趋势")
    _shade_mask(ax_price, data, strong_flat, "#7b61ff", 0.14, "强趋势但空仓")

    ax_price.set_title(f"{name} {year} BTC 15分钟买卖点", fontsize=18)
    ax_price.set_ylabel("BTC价格 USDT")
    ax_price.grid(True, linestyle="--", alpha=0.25)
    ax_price.legend(loc="upper left")
    ax_price.text(
        0.01,
        0.02,
        f"买点 {len(buys)}；卖点 {len(sells)}；黄色=强趋势；紫色=强趋势但空仓",
        transform=ax_price.transAxes,
        fontsize=11,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#dddddd", "alpha": 0.9},
    )

    ax_pos.plot(data["timestamp"], data["active_position"], color="#2f80ed", linewidth=0.7)
    ax_pos.axhline(0, color="#444444", linewidth=0.6)
    ax_pos.set_ylabel("持仓")
    ax_pos.grid(True, linestyle="--", alpha=0.2)
    fig.autofmt_xdate(rotation=35)
    fig.tight_layout()
    path = out_dir / f"{name.lower()}_trades_{year}.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def _shade_mask(ax: plt.Axes, data: pd.DataFrame, mask: pd.Series, color: str, alpha: float, label: str) -> None:
    if not mask.any():
        return
    starts = data.loc[mask & ~mask.shift(fill_value=False), "timestamp"].to_list()
    ends = data.loc[mask & ~mask.shift(-1, fill_value=False), "timestamp"].to_list()
    for i, (start, end) in enumerate(zip(starts, ends)):
        ax.axvspan(start, end, color=color, alpha=alpha, linewidth=0, label=label if i == 0 else None)


def _marker_sizes(values: pd.Series) -> np.ndarray:
    if values.empty:
        return np.array([])
    clipped = values.clip(lower=0.05, upper=8.0)
    return 18.0 + (clipped / 8.0).to_numpy(float) * 58.0


def _configure_plot_font() -> None:
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if font_path.exists():
        from matplotlib import font_manager

        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    plt.rcParams["axes.unicode_minus"] = False


if __name__ == "__main__":
    main()
