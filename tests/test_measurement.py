from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import tifffile

from psfbench.measurement import (
    AxisProfile,
    estimate_fwhm_from_profile,
    extract_roi_profiles,
    fit_gaussian_profile,
    measure_roi,
    measure_rois_from_manifest,
)


def test_extract_roi_profiles_returns_peak_centered_axes() -> None:
    roi = np.arange(5 * 7 * 9, dtype=np.float32).reshape(5, 7, 9)

    profiles = extract_roi_profiles(
        roi,
        peak_zyx=(2, 3, 4),
        z_um_per_px=0.5,
        xy_um_per_px=0.2,
    )

    np.testing.assert_array_equal(profiles.z.values, roi[:, 3, 4])
    np.testing.assert_array_equal(profiles.y.values, roi[2, :, 4])
    np.testing.assert_array_equal(profiles.x.values, roi[2, 3, :])
    np.testing.assert_allclose(profiles.z.coordinates_um, [-1.0, -0.5, 0.0, 0.5, 1.0])
    np.testing.assert_allclose(profiles.y.coordinates_um, [-0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6])
    np.testing.assert_allclose(profiles.x.coordinates_um, [-0.8, -0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8])
    assert profiles.z.peak_index == 2
    assert profiles.y.peak_index == 3
    assert profiles.x.peak_index == 4


def test_extract_roi_profiles_rejects_peak_outside_roi() -> None:
    roi = np.zeros((3, 3, 3), dtype=np.float32)

    with pytest.raises(ValueError, match="outside ROI shape"):
        extract_roi_profiles(
            roi,
            peak_zyx=(3, 1, 1),
            z_um_per_px=0.5,
            xy_um_per_px=0.2,
        )


def test_estimate_fwhm_from_profile_interpolates_crossings() -> None:
    profile = np.array([0, 2, 4, 8, 4, 2, 0], dtype=float)

    fwhm = estimate_fwhm_from_profile(profile, um_per_px=0.5)

    assert fwhm == pytest.approx(1.0)


def test_fit_gaussian_profile_recovers_known_parameters() -> None:
    coordinates_um = np.linspace(-2.0, 2.0, 41)
    offset = 3.0
    amplitude = 20.0
    center_um = 0.15
    sigma_um = 0.42
    values = offset + amplitude * np.exp(-0.5 * ((coordinates_um - center_um) / sigma_um) ** 2)
    profile = AxisProfile(
        values=values,
        coordinates_um=coordinates_um,
        peak_index=int(np.argmax(values)),
        um_per_px=0.1,
    )

    fit = fit_gaussian_profile(profile)

    assert fit.success
    assert fit.failure_reason == ""
    assert fit.offset == pytest.approx(offset, rel=1e-5)
    assert fit.amplitude == pytest.approx(amplitude, rel=1e-5)
    assert fit.center_um == pytest.approx(center_um, abs=1e-5)
    assert fit.sigma_um == pytest.approx(sigma_um, rel=1e-5)
    assert fit.rmse == pytest.approx(0.0, abs=1e-6)
    assert fit.r_squared == pytest.approx(1.0)


def test_fit_gaussian_profile_reports_failure_for_flat_profile() -> None:
    profile = AxisProfile(
        values=np.ones(7),
        coordinates_um=np.linspace(-0.3, 0.3, 7),
        peak_index=3,
        um_per_px=0.1,
    )

    fit = fit_gaussian_profile(profile)

    assert not fit.success
    assert "no positive intensity range" in fit.failure_reason


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
