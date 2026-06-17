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
