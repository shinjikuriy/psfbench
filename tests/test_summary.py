from __future__ import annotations

import pandas as pd
import pytest

from psfbench.summary import (
    infer_condition_name,
    join_condition_metadata,
    summarize_measurement_files,
    summarize_measurements,
)


def test_infer_condition_name_removes_suffix() -> None:
    assert infer_condition_name("D80per_pow3.97per_measurements.csv") == "D80per_pow3.97per"


def test_summarize_measurements_computes_stats_by_condition() -> None:
    measurements = pd.DataFrame(
        {
            "condition": ["A", "A", "B"],
            "FWHM_X_um": [1.0, 3.0, 10.0],
            "peak_intensity": [100.0, 300.0, 500.0],
        }
    )

    summary = summarize_measurements(
        measurements,
        measurement_columns=["FWHM_X_um", "peak_intensity"],
    ).set_index("condition")

    assert summary.loc["A", "FWHM_X_um_count"] == 2
    assert summary.loc["A", "FWHM_X_um_mean"] == 2.0
    assert summary.loc["A", "FWHM_X_um_sd"] == pytest.approx(2**0.5)
    assert summary.loc["A", "FWHM_X_um_sem"] == pytest.approx(1.0)
    assert summary.loc["B", "FWHM_X_um_count"] == 1
    assert pd.isna(summary.loc["B", "FWHM_X_um_sd"])
    assert pd.isna(summary.loc["B", "FWHM_X_um_sem"])


def test_summarize_measurement_files_reads_directory(tmp_path) -> None:
    pd.DataFrame(
        {
            "FWHM_X_um": [1.0, 3.0],
            "FWHM_Y_um": [2.0, 4.0],
            "FWHM_Z_um": [5.0, 7.0],
            "FWHM_XY_mean_um": [1.5, 3.5],
            "FWHM_X_over_Y": [0.5, 0.75],
            "peak_intensity": [100.0, 300.0],
            "integrated_intensity": [1000.0, 3000.0],
        }
    ).to_csv(tmp_path / "D40per_pow2.24per_measurements.csv", index=False)
    pd.DataFrame(
        {
            "FWHM_X_um": [10.0],
            "FWHM_Y_um": [20.0],
            "FWHM_Z_um": [30.0],
            "FWHM_XY_mean_um": [15.0],
            "FWHM_X_over_Y": [0.5],
            "peak_intensity": [500.0],
            "integrated_intensity": [5000.0],
        }
    ).to_csv(tmp_path / "D80per_pow3.97per_measurements.csv", index=False)
    output = tmp_path / "summary.csv"

    summary = summarize_measurement_files(tmp_path, output=output)

    assert output.exists()
    assert summary["condition"].tolist() == ["D40per_pow2.24per", "D80per_pow3.97per"]
    assert summary.loc[0, "FWHM_X_um_count"] == 2
    assert summary.loc[0, "FWHM_X_um_mean"] == 2.0


def test_summarize_measurement_files_joins_condition_metadata(tmp_path) -> None:
    pd.DataFrame(
        {
            "FWHM_X_um": [1.0, 3.0],
            "FWHM_Y_um": [2.0, 4.0],
            "FWHM_Z_um": [5.0, 7.0],
            "FWHM_XY_mean_um": [1.5, 3.5],
            "FWHM_X_over_Y": [0.5, 0.75],
            "peak_intensity": [100.0, 300.0],
            "integrated_intensity": [1000.0, 3000.0],
        }
    ).to_csv(tmp_path / "D40per_pow2.24per_measurements.csv", index=False)
    metadata_path = tmp_path / "condition_metadata.csv"
    pd.DataFrame(
        {
            "condition": ["D40per_pow2.24per"],
            "filling_rate": [40.0],
            "power_percent": [2.24],
        }
    ).to_csv(metadata_path, index=False)

    summary = summarize_measurement_files(
        tmp_path,
        output=tmp_path / "summary.csv",
        condition_metadata=metadata_path,
    )

    assert summary.loc[0, "filling_rate"] == 40.0
    assert summary.loc[0, "power_percent"] == 2.24


def test_join_condition_metadata_rejects_duplicate_conditions(tmp_path) -> None:
    summary = pd.DataFrame({"condition": ["A"], "FWHM_X_um_mean": [1.0]})
    metadata_path = tmp_path / "condition_metadata.csv"
    pd.DataFrame({"condition": ["A", "A"], "filling_rate": [40, 50]}).to_csv(metadata_path, index=False)

    with pytest.raises(ValueError, match="duplicate condition"):
        join_condition_metadata(summary, metadata_path)
