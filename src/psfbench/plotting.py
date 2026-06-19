from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def plot_summary(
    summary: str | Path,
    *,
    output: str | Path,
    x: str,
    y: str,
    yerr: str | None = None,
    title: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
) -> None:
    df = pd.read_csv(summary)
    _validate_columns(df, [x, y] + ([yerr] if yerr else []))
    df = _sort_for_plot(df, x)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    x_values = df[x]
    y_values = pd.to_numeric(df[y], errors="coerce")
    yerr_values = pd.to_numeric(df[yerr], errors="coerce") if yerr else None

    fig, ax = plt.subplots(figsize=(7, 4.5), constrained_layout=True)
    if _is_numeric_series(x_values):
        x_numeric = pd.to_numeric(x_values, errors="coerce")
        ax.errorbar(
            x_numeric,
            y_values,
            yerr=yerr_values,
            marker="o",
            linestyle="-",
            capsize=4,
        )
    else:
        positions = np.arange(len(x_values))
        ax.errorbar(
            positions,
            y_values,
            yerr=yerr_values,
            marker="o",
            linestyle="-",
            capsize=4,
        )
        ax.set_xticks(positions)
        ax.set_xticklabels([str(value) for value in x_values], rotation=35, ha="right")

    ax.set_xlabel(x_label or x)
    ax.set_ylabel(y_label or y)
    if title:
        ax.set_title(title)
    ax.grid(True, axis="y", alpha=0.3)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def _validate_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"Summary CSV is missing required columns: {missing}")


def _sort_for_plot(df: pd.DataFrame, x: str) -> pd.DataFrame:
    x_numeric = pd.to_numeric(df[x], errors="coerce")
    if x_numeric.notna().all():
        return df.assign(_x_numeric=x_numeric).sort_values("_x_numeric").drop(columns=["_x_numeric"])
    return df.sort_values(x)


def _is_numeric_series(series: pd.Series) -> bool:
    return pd.to_numeric(series, errors="coerce").notna().all()
