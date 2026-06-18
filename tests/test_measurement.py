from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import tifffile

from psfbench.measurement import estimate_fwhm_from_profile, measure_roi, measure_rois_from_manifest


def test_estimate_fwhm_from_profile_interpolates_crossings() -> None:
    profile = np.array([0, 2, 4, 8, 4, 2, 0], dtype=float)

    fwhm = estimate_fwhm_from_profile(profile, um_per_px=0.5)

    assert fwhm == pytest.approx(1.0)


def test_measure_roi_reports_line_profile_fwhm_and_intensity() -> None:
    z_profile = np.array([0, 2, 4, 8, 4, 2, 0], dtype=np.float32)
    y_profile = np.array([0, 1, 4, 8, 4, 1, 0], dtype=np.float32)
    x_profile = np.array([0, 3, 6, 8, 6, 3, 0], dtype=np.float32)
    roi = np.zeros((7, 7, 7), dtype=np.float32)
    roi[:, 3, 3] = z_profile
    roi[3, :, 3] = y_profile
    roi[3, 3, :] = x_profile

    measurement = measure_roi(roi, z_um_per_px=0.5, xy_um_per_px=0.2, background_percentile=0)

    assert measurement.peak_z == 3
    assert measurement.peak_y == 3
    assert measurement.peak_x == 3
    assert measurement.fwhm_z_um == pytest.approx(1.0)
    assert measurement.fwhm_y_um == pytest.approx(0.4)
    assert measurement.fwhm_x_um == pytest.approx(2 / 3)
    assert measurement.fwhm_xy_mean_um == pytest.approx((0.4 + 2 / 3) / 2)
    assert measurement.fwhm_x_over_y == pytest.approx((2 / 3) / 0.4)
    assert measurement.peak_intensity == 8


def test_measure_rois_from_manifest_writes_measurement_csv(tmp_path) -> None:
    roi = np.zeros((7, 7, 7), dtype=np.uint16)
    roi[:, 3, 3] = [0, 2, 4, 8, 4, 2, 0]
    roi[3, :, 3] = [0, 2, 4, 8, 4, 2, 0]
    roi[3, 3, :] = [0, 2, 4, 8, 4, 2, 0]
    roi_path = tmp_path / "bead_0001.tif"
    tifffile.imwrite(roi_path, roi)
    pd.DataFrame(
        [
            {
                "bead_index": 1,
                "roi_path": str(roi_path),
                "skipped": False,
                "z_um_per_px": 0.5,
                "xy_um_per_px": 0.2,
            },
            {
                "bead_index": 2,
                "roi_path": "",
                "skipped": True,
                "z_um_per_px": 0.5,
                "xy_um_per_px": 0.2,
            },
        ]
    ).to_csv(tmp_path / "roi_manifest.csv", index=False)
    output = tmp_path / "measurements.csv"

    measurements = measure_rois_from_manifest(tmp_path, output=output, background_percentile=0)

    assert output.exists()
    assert len(measurements) == 1
    assert measurements.loc[0, "bead_index"] == 1
    assert measurements.loc[0, "FWHM_Z_um"] == pytest.approx(1.0)
