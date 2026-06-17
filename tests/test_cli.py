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
    (input_dir / "Experiment.xml").write_text(
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
            plane[40, 40] = 1000
        tifffile.imwrite(input_dir / f"ChanA_001_001_{z + 1:03d}_001.tif", plane)

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
