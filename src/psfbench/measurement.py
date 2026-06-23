from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
import tifffile


_GAUSSIAN_FWHM_FACTOR = 2.3548200450309493


@dataclass(frozen=True)
class AxisProfile:
    values: np.ndarray
    coordinates_um: np.ndarray
    peak_index: int
    um_per_px: float


@dataclass(frozen=True)
class RoiProfiles:
    z: AxisProfile
    y: AxisProfile
    x: AxisProfile


@dataclass(frozen=True)
class GaussianFitResult:
    success: bool
    offset: float
    amplitude: float
    center_um: float
    sigma_um: float
    rmse: float
    r_squared: float
    failure_reason: str = ""


@dataclass(frozen=True)
class RoiMeasurement:
    bead_index: int
    roi_path: Path
    peak_z: int
    peak_y: int
    peak_x: int
    fwhm_z_um: float
    fwhm_y_um: float
    fwhm_x_um: float
    fwhm_xy_mean_um: float
    fwhm_x_over_y: float
    peak_intensity: float
    integrated_intensity: float
    background: float


def extract_roi_profiles(
    roi: np.ndarray,
    *,
    peak_zyx: tuple[int, int, int],
    z_um_per_px: float,
    xy_um_per_px: float,
) -> RoiProfiles:
    if roi.ndim != 3:
        raise ValueError(f"Expected ROI with shape (z, y, x), got {roi.shape}")

    peak_z, peak_y, peak_x = peak_zyx
    z_size, y_size, x_size = roi.shape
    if not (0 <= peak_z < z_size and 0 <= peak_y < y_size and 0 <= peak_x < x_size):
        raise ValueError(f"Peak index {peak_zyx} is outside ROI shape {roi.shape}")

    return RoiProfiles(
        z=_make_axis_profile(roi[:, peak_y, peak_x], peak_index=peak_z, um_per_px=z_um_per_px),
        y=_make_axis_profile(roi[peak_z, :, peak_x], peak_index=peak_y, um_per_px=xy_um_per_px),
        x=_make_axis_profile(roi[peak_z, peak_y, :], peak_index=peak_x, um_per_px=xy_um_per_px),
    )


def _make_axis_profile(profile: np.ndarray, *, peak_index: int, um_per_px: float) -> AxisProfile:
    values = np.asarray(profile, dtype=float).copy()
    coordinates_um = (np.arange(values.size, dtype=float) - peak_index) * um_per_px
    return AxisProfile(
        values=values,
        coordinates_um=coordinates_um,
        peak_index=int(peak_index),
        um_per_px=float(um_per_px),
    )


def fit_gaussian_profile(profile: AxisProfile) -> GaussianFitResult:
    x = np.asarray(profile.coordinates_um, dtype=float)
    y = np.asarray(profile.values, dtype=float)
    if x.ndim != 1 or y.ndim != 1 or x.size != y.size:
        return _failed_gaussian_fit("Profile coordinates and values must be matching 1D arrays.")
    if x.size < 4:
        return _failed_gaussian_fit("At least 4 profile points are required for Gaussian fitting.")
    if not (np.all(np.isfinite(x)) and np.all(np.isfinite(y))):
        return _failed_gaussian_fit("Profile contains non-finite values.")
    if profile.um_per_px <= 0:
        return _failed_gaussian_fit("um_per_px must be positive.")

    y_min = float(np.min(y))
    y_max = float(np.max(y))
    if y_max <= y_min:
        return _failed_gaussian_fit("Profile has no positive intensity range.")

    offset0 = _estimate_profile_offset(y)
    amplitude0 = max(y_max - offset0, np.finfo(float).eps)
    center0 = float(x[int(np.argmax(y))])
    sigma0 = _initial_sigma_um(y, profile.um_per_px)
    x_min = float(np.min(x))
    x_max = float(np.max(x))
    span_um = max(x_max - x_min, profile.um_per_px)

    lower_bounds = [y_min - amplitude0, 0.0, x_min, profile.um_per_px / 10.0]
    upper_bounds = [y_max, np.inf, x_max, span_um]

    try:
        params, _ = curve_fit(
            _gaussian_1d,
            x,
            y,
            p0=[offset0, amplitude0, center0, sigma0],
            bounds=(lower_bounds, upper_bounds),
            maxfev=10000,
        )
    except (RuntimeError, ValueError, FloatingPointError) as exc:
        return _failed_gaussian_fit(str(exc))

    offset, amplitude, center_um, sigma_um = (float(value) for value in params)
    sigma_um = abs(sigma_um)
    fitted = _gaussian_1d(x, offset, amplitude, center_um, sigma_um)
    residuals = y - fitted
    rmse = float(np.sqrt(np.mean(residuals**2)))
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r_squared = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else np.nan

    return GaussianFitResult(
        success=True,
        offset=offset,
        amplitude=amplitude,
        center_um=center_um,
        sigma_um=sigma_um,
        rmse=rmse,
        r_squared=r_squared,
    )


def _gaussian_1d(
    x: np.ndarray,
    offset: float,
    amplitude: float,
    center_um: float,
    sigma_um: float,
) -> np.ndarray:
    return offset + amplitude * np.exp(-0.5 * ((x - center_um) / sigma_um) ** 2)


def _estimate_profile_offset(values: np.ndarray) -> float:
    edge_width = max(1, values.size // 5)
    edge_values = np.concatenate([values[:edge_width], values[-edge_width:]])
    return float(np.median(edge_values))


def _initial_sigma_um(values: np.ndarray, um_per_px: float) -> float:
    fwhm_um = estimate_fwhm_from_profile(values - np.min(values), um_per_px)
    if np.isfinite(fwhm_um) and fwhm_um > 0:
        return float(fwhm_um / _GAUSSIAN_FWHM_FACTOR)
    return float(max(um_per_px, values.size * um_per_px / 6.0))


def _failed_gaussian_fit(reason: str) -> GaussianFitResult:
    return GaussianFitResult(
        success=False,
        offset=np.nan,
        amplitude=np.nan,
        center_um=np.nan,
        sigma_um=np.nan,
        rmse=np.nan,
        r_squared=np.nan,
        failure_reason=reason,
    )


def measure_roi(
    roi: np.ndarray,
    *,
    z_um_per_px: float,
    xy_um_per_px: float,
    background_percentile: float = 10.0,
) -> RoiMeasurement:
    if roi.ndim != 3:
        raise ValueError(f"Expected ROI with shape (z, y, x), got {roi.shape}")

    roi_float = np.asarray(roi, dtype=np.float32)
    background = float(np.percentile(roi_float, background_percentile))
    corrected = np.clip(roi_float - background, a_min=0, a_max=None)
    peak_z, peak_y, peak_x = np.unravel_index(int(np.argmax(corrected)), corrected.shape)
    peak_intensity = float(roi_float[peak_z, peak_y, peak_x])
    integrated_intensity = float(corrected.sum())
    profiles = extract_roi_profiles(
        corrected,
        peak_zyx=(int(peak_z), int(peak_y), int(peak_x)),
        z_um_per_px=z_um_per_px,
        xy_um_per_px=xy_um_per_px,
    )

    fwhm_z_um = estimate_fwhm_from_profile(profiles.z.values, profiles.z.um_per_px)
    fwhm_y_um = estimate_fwhm_from_profile(profiles.y.values, profiles.y.um_per_px)
    fwhm_x_um = estimate_fwhm_from_profile(profiles.x.values, profiles.x.um_per_px)
    fwhm_xy_mean_um = float(np.nanmean([fwhm_x_um, fwhm_y_um]))
    fwhm_x_over_y = float(fwhm_x_um / fwhm_y_um) if fwhm_y_um > 0 else np.nan

    return RoiMeasurement(
        bead_index=-1,
        roi_path=Path(),
        peak_z=int(peak_z),
        peak_y=int(peak_y),
        peak_x=int(peak_x),
        fwhm_z_um=fwhm_z_um,
        fwhm_y_um=fwhm_y_um,
        fwhm_x_um=fwhm_x_um,
        fwhm_xy_mean_um=fwhm_xy_mean_um,
        fwhm_x_over_y=fwhm_x_over_y,
        peak_intensity=peak_intensity,
        integrated_intensity=integrated_intensity,
        background=background,
    )


def estimate_fwhm_from_profile(profile: np.ndarray, um_per_px: float) -> float:
    profile = np.asarray(profile, dtype=float)
    if profile.ndim != 1:
        raise ValueError("Expected a 1D profile.")
    peak_index = int(np.argmax(profile))
    peak_value = float(profile[peak_index])
    if peak_value <= 0:
        return np.nan

    half_value = peak_value / 2
    left = _crossing_position(profile, peak_index, -1, half_value)
    right = _crossing_position(profile, peak_index, 1, half_value)
    if left is None or right is None:
        return np.nan
    return float((right - left) * um_per_px)


def _crossing_position(
    profile: np.ndarray,
    peak_index: int,
    step: int,
    half_value: float,
) -> float | None:
    index = peak_index
    while 0 <= index + step < profile.size:
        next_index = index + step
        if profile[next_index] <= half_value:
            y0 = float(profile[index])
            y1 = float(profile[next_index])
            if y0 == y1:
                return float(next_index)
            fraction = (half_value - y0) / (y1 - y0)
            return float(index + fraction * step)
        index = next_index
    return None


def measure_rois_from_manifest(
    roi_dir: str | Path,
    *,
    output: str | Path,
    background_percentile: float = 10.0,
) -> pd.DataFrame:
    roi_dir = Path(roi_dir)
    manifest_path = roi_dir / "roi_manifest.csv"
    manifest = pd.read_csv(manifest_path)
    required = {"bead_index", "roi_path", "skipped", "z_um_per_px", "xy_um_per_px"}
    missing = required - set(manifest.columns)
    if missing:
        raise ValueError(f"ROI manifest is missing required columns: {sorted(missing)}")

    rows = []
    for row in manifest.to_dict(orient="records"):
        if bool(row["skipped"]):
            continue
        roi_path = Path(str(row["roi_path"]))
        if not roi_path.is_absolute() and not roi_path.exists():
            roi_path = roi_dir / roi_path.name
        roi = tifffile.imread(roi_path)
        measurement = measure_roi(
            roi,
            z_um_per_px=float(row["z_um_per_px"]),
            xy_um_per_px=float(row["xy_um_per_px"]),
            background_percentile=background_percentile,
        )
        rows.append(
            {
                "bead_index": int(row["bead_index"]),
                "roi_path": str(roi_path),
                "peak_z_roi": measurement.peak_z,
                "peak_y_roi": measurement.peak_y,
                "peak_x_roi": measurement.peak_x,
                "FWHM_X_um": measurement.fwhm_x_um,
                "FWHM_Y_um": measurement.fwhm_y_um,
                "FWHM_Z_um": measurement.fwhm_z_um,
                "FWHM_XY_mean_um": measurement.fwhm_xy_mean_um,
                "FWHM_X_over_Y": measurement.fwhm_x_over_y,
                "peak_intensity": measurement.peak_intensity,
                "integrated_intensity": measurement.integrated_intensity,
                "background": measurement.background,
            }
        )

    df = pd.DataFrame(rows)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return df
