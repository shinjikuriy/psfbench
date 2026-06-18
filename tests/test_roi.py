from __future__ import annotations

import numpy as np
import pandas as pd
import tifffile

from psfbench.roi import crop_roi, save_rois


def test_crop_roi_returns_centered_substack() -> None:
    stack = np.arange(10 * 20 * 30, dtype=np.uint16).reshape(10, 20, 30)

    result = crop_roi(
        stack,
        np.array([5, 10, 15]),
        radius_z_px=2,
        radius_xy_px=3,
    )

    assert result is not None
    roi, bounds = result
    assert roi.shape == (5, 7, 7)
    assert bounds.z_start == 3
    assert bounds.z_stop == 8
    assert bounds.y_start == 7
    assert bounds.y_stop == 14
    assert bounds.x_start == 12
    assert bounds.x_stop == 19
    np.testing.assert_array_equal(roi, stack[3:8, 7:14, 12:19])


def test_crop_roi_returns_none_when_out_of_bounds() -> None:
    stack = np.zeros((10, 20, 30), dtype=np.uint16)

    result = crop_roi(
        stack,
        np.array([1, 10, 15]),
        radius_z_px=2,
        radius_xy_px=3,
    )

    assert result is None


def test_save_rois_writes_tiffs_and_manifest(tmp_path) -> None:
    stack = np.zeros((10, 20, 30), dtype=np.uint16)
    stack[5, 10, 15] = 100
    points = np.array(
        [
            [5, 10, 15],
            [1, 10, 15],
        ],
        dtype=float,
    )

    results = save_rois(
        stack,
        points,
        output_dir=tmp_path,
        z_um_per_px=0.5,
        xy_um_per_px=0.2,
        radius_z_um=1.0,
        radius_xy_um=0.6,
    )

    assert len(results) == 2
    assert not results[0].skipped
    assert results[1].skipped
    roi = tifffile.imread(tmp_path / "bead_0001.tif")
    assert roi.shape == (5, 7, 7)
    manifest = pd.read_csv(tmp_path / "roi_manifest.csv")
    assert manifest["skipped"].tolist() == [False, True]
    assert manifest.loc[0, "z_um"] == 2.5
    assert manifest.loc[0, "y_um"] == 2.0
    assert manifest.loc[0, "x_um"] == 3.0
    assert manifest.loc[0, "z_um_per_px"] == 0.5
    assert manifest.loc[0, "xy_um_per_px"] == 0.2
