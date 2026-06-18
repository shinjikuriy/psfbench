from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import tifffile
from typer.testing import CliRunner

from psfbench.cli import app


def test_detect_uses_thorimage_metadata_source(tmp_path: Path) -> None:
    input_dir = tmp_path / "thorimage_stack"
    input_dir.mkdir()
    output = tmp_path / "points.csv"
    write_tiny_thorimage_stack(input_dir, peak_yx=(40, 40))

    result = CliRunner().invoke(
        app,
        [
            "detect",
            "--input",
            str(input_dir),
            "--output",
            str(output),
            "--metadata-source",
            "thorimage",
            "--n-beads",
            "1",
            "--threshold-percentile",
            "99.5",
            "--margin-z-um",
            "2.0",
            "--margin-xy-um",
            "2.0",
            "--no-gui",
        ],
    )

    assert result.exit_code == 0, result.output
    df = pd.read_csv(output)
    assert len(df) == 1
    assert df.loc[0, "z_um"] == 10.0
    assert df.loc[0, "y_um"] == 8.0
    assert df.loc[0, "x_um"] == 8.0


def test_batch_detect_processes_condition_directories(tmp_path: Path) -> None:
    input_root = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    condition_a = input_root / "D40per_pow2.24per"
    condition_b = input_root / "D80per_pow3.97per"
    condition_a.mkdir(parents=True)
    condition_b.mkdir(parents=True)
    write_tiny_thorimage_stack(condition_a, peak_yx=(40, 40))
    write_tiny_thorimage_stack(condition_b, peak_yx=(30, 50))

    result = CliRunner().invoke(
        app,
        [
            "batch-detect",
            "--input-root",
            str(input_root),
            "--output-dir",
            str(output_dir),
            "--metadata-source",
            "thorimage",
            "--n-beads",
            "1",
            "--threshold-percentile",
            "99.5",
        ],
    )

    assert result.exit_code == 0, result.output
    output_a = output_dir / "D40per_pow2.24per_points.csv"
    output_b = output_dir / "D80per_pow3.97per_points.csv"
    assert output_a.exists()
    assert output_b.exists()
    assert len(pd.read_csv(output_a)) == 1
    assert len(pd.read_csv(output_b)) == 1


def test_crop_rois_command_writes_roi_outputs(tmp_path: Path) -> None:
    input_dir = tmp_path / "thorimage_stack"
    input_dir.mkdir()
    write_tiny_thorimage_stack(input_dir, peak_yx=(40, 40))
    points_csv = tmp_path / "points.csv"
    points_csv.write_text("z,y,x,z_um,y_um,x_um\n20,40,40,10,8,8\n")
    output_dir = tmp_path / "rois"

    result = CliRunner().invoke(
        app,
        [
            "crop-rois",
            "--input",
            str(input_dir),
            "--points",
            str(points_csv),
            "--output-dir",
            str(output_dir),
            "--metadata-source",
            "thorimage",
            "--radius-z-um",
            "1.0",
            "--radius-xy-um",
            "0.6",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (output_dir / "bead_0001.tif").exists()
    assert (output_dir / "roi_manifest.csv").exists()
    manifest = pd.read_csv(output_dir / "roi_manifest.csv")
    assert len(manifest) == 1
    assert not bool(manifest.loc[0, "skipped"])


def test_measure_rois_command_writes_measurement_csv(tmp_path: Path) -> None:
    roi_dir = tmp_path / "rois"
    roi_dir.mkdir()
    roi = np.zeros((7, 7, 7), dtype=np.uint16)
    roi[:, 3, 3] = [0, 2, 4, 8, 4, 2, 0]
    roi[3, :, 3] = [0, 2, 4, 8, 4, 2, 0]
    roi[3, 3, :] = [0, 2, 4, 8, 4, 2, 0]
    tifffile.imwrite(roi_dir / "bead_0001.tif", roi)
    pd.DataFrame(
        [
            {
                "bead_index": 1,
                "roi_path": "bead_0001.tif",
                "skipped": False,
                "z_um_per_px": 0.5,
                "xy_um_per_px": 0.2,
            }
        ]
    ).to_csv(roi_dir / "roi_manifest.csv", index=False)
    output = tmp_path / "measurements.csv"

    result = CliRunner().invoke(
        app,
        [
            "measure-rois",
            "--roi-dir",
            str(roi_dir),
            "--output",
            str(output),
            "--background-percentile",
            "0",
        ],
    )

    assert result.exit_code == 0, result.output
    measurements = pd.read_csv(output)
    assert len(measurements) == 1
    assert measurements.loc[0, "FWHM_Z_um"] == 1.0


def test_aggregate_measurements_command_writes_summary_csv(tmp_path: Path) -> None:
    input_dir = tmp_path / "measurements"
    input_dir.mkdir()
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
    ).to_csv(input_dir / "condition_a_measurements.csv", index=False)
    metadata = tmp_path / "condition_metadata.csv"
    pd.DataFrame(
        {
            "condition": ["condition_a"],
            "filling_rate": [40.0],
            "power_percent": [2.24],
        }
    ).to_csv(metadata, index=False)
    output = tmp_path / "summary.csv"

    result = CliRunner().invoke(
        app,
        [
            "aggregate-measurements",
            "--input-dir",
            str(input_dir),
            "--output",
            str(output),
            "--condition-metadata",
            str(metadata),
        ],
    )

    assert result.exit_code == 0, result.output
    summary = pd.read_csv(output)
    assert len(summary) == 1
    assert summary.loc[0, "condition"] == "condition_a"
    assert summary.loc[0, "filling_rate"] == 40.0
    assert summary.loc[0, "FWHM_X_um_mean"] == 2.0


def write_tiny_thorimage_stack(directory: Path, *, peak_yx: tuple[int, int]) -> None:
    (directory / "Experiment.xml").write_text(
        """<?xml version="1.0"?>
<ThorImageExperiment>
  <ZStage steps="41" stepSizeUM="0.5" />
  <LSM pixelX="80" pixelY="80" pixelSizeUM="0.19" widthUM="16.0" heightUM="16.0" />
</ThorImageExperiment>
"""
    )
    for z in range(41):
        plane = np.zeros((80, 80), dtype=np.uint16)
        if z == 20:
            plane[peak_yx] = 1000
        tifffile.imwrite(directory / f"ChanA_001_001_{z + 1:03d}_001.tif", plane)
