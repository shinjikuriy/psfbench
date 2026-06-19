from __future__ import annotations

import pandas as pd
import pytest

from psfbench.plotting import plot_summary


def test_plot_summary_writes_image(tmp_path) -> None:
    summary = tmp_path / "summary.csv"
    output = tmp_path / "plot.png"
    pd.DataFrame(
        {
            "condition": ["B", "A"],
            "filling_rate": [80.0, 40.0],
            "FWHM_Z_um_mean": [1.4, 1.2],
            "FWHM_Z_um_sem": [0.1, 0.05],
        }
    ).to_csv(summary, index=False)

    plot_summary(
        summary,
        output=output,
        x="filling_rate",
        y="FWHM_Z_um_mean",
        yerr="FWHM_Z_um_sem",
    )

    assert output.exists()
    assert output.stat().st_size > 0


def test_plot_summary_rejects_missing_columns(tmp_path) -> None:
    summary = tmp_path / "summary.csv"
    pd.DataFrame({"condition": ["A"], "FWHM_Z_um_mean": [1.2]}).to_csv(summary, index=False)

    with pytest.raises(ValueError, match="missing required columns"):
        plot_summary(
            summary,
            output=tmp_path / "plot.png",
            x="filling_rate",
            y="FWHM_Z_um_mean",
        )
