from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage


@dataclass(frozen=True)
class DetectionParams:
    xy_um_per_px: float
    z_um_per_px: float
    n_beads: int = 20
    background_percentile: float = 10.0
    threshold_percentile: float = 99.8
    gaussian_sigma: tuple[float, float, float] = (0.5, 1.0, 1.0)
    min_distance_um: float = 2.0
    margin_z_um: float = 3.0
    margin_xy_um: float = 3.0
    center_fraction: float = 0.6


def preprocess_stack(
    stack: np.ndarray,
    *,
    background_percentile: float = 10.0,
    gaussian_sigma: tuple[float, float, float] = (0.5, 1.0, 1.0),
) -> np.ndarray:
    stack_float = np.asarray(stack, dtype=np.float32)
    background = np.percentile(stack_float, background_percentile)
    stack_bg = np.clip(stack_float - background, a_min=0, a_max=None)
    return ndimage.gaussian_filter(stack_bg, sigma=gaussian_sigma)


def detect_beads(stack: np.ndarray, params: DetectionParams) -> np.ndarray:
    if stack.ndim != 3:
        raise ValueError(f"Expected stack with shape (z, y, x), got {stack.shape}")
    if not 0 < params.center_fraction <= 1:
        raise ValueError("center_fraction must be in the range (0, 1].")

    smoothed = preprocess_stack(
        stack,
        background_percentile=params.background_percentile,
        gaussian_sigma=params.gaussian_sigma,
    )
    candidate_points = find_local_maxima(smoothed, params)
    ranked_points = rank_candidates(candidate_points, smoothed, params)
    selected_points = select_spaced_candidates(ranked_points, params)
    return selected_points[: params.n_beads]


def find_local_maxima(smoothed: np.ndarray, params: DetectionParams) -> np.ndarray:
    min_distance_z_px = max(1, round(params.min_distance_um / params.z_um_per_px))
    min_distance_xy_px = max(1, round(params.min_distance_um / params.xy_um_per_px))
    footprint_size = (
        2 * min_distance_z_px + 1,
        2 * min_distance_xy_px + 1,
        2 * min_distance_xy_px + 1,
    )
    local_max = smoothed == ndimage.maximum_filter(smoothed, size=footprint_size)
    threshold = np.percentile(smoothed, params.threshold_percentile)
    candidate_mask = local_max & (smoothed >= threshold) & (smoothed > 0)
    candidate_points = np.argwhere(candidate_mask)
    return exclude_edges(candidate_points, smoothed.shape, params)


def exclude_edges(
    points: np.ndarray,
    shape: tuple[int, int, int],
    params: DetectionParams,
) -> np.ndarray:
    if points.size == 0:
        return np.empty((0, 3), dtype=float)

    margin_z_px = round(params.margin_z_um / params.z_um_per_px)
    margin_xy_px = round(params.margin_xy_um / params.xy_um_per_px)
    z_size, y_size, x_size = shape
    z, y, x = points.T
    keep = (
        (z >= margin_z_px)
        & (z < z_size - margin_z_px)
        & (y >= margin_xy_px)
        & (y < y_size - margin_xy_px)
        & (x >= margin_xy_px)
        & (x < x_size - margin_xy_px)
    )
    return points[keep].astype(float)


def rank_candidates(
    points: np.ndarray,
    smoothed: np.ndarray,
    params: DetectionParams,
) -> np.ndarray:
    if points.size == 0:
        return np.empty((0, 3), dtype=float)

    z_size, y_size, x_size = smoothed.shape
    center_y = (y_size - 1) / 2
    center_x = (x_size - 1) / 2
    half_center_y = y_size * params.center_fraction / 2
    half_center_x = x_size * params.center_fraction / 2

    y = points[:, 1]
    x = points[:, 2]
    in_center = (
        (np.abs(y - center_y) <= half_center_y)
        & (np.abs(x - center_x) <= half_center_x)
    )
    center_distance = np.sqrt(
        ((y - center_y) / max(center_y, 1)) ** 2
        + ((x - center_x) / max(center_x, 1)) ** 2
    )
    intensities = smoothed[
        points[:, 0].astype(int),
        points[:, 1].astype(int),
        points[:, 2].astype(int),
    ]
    order = np.lexsort((-intensities, center_distance, ~in_center))
    return points[order].astype(float)


def select_spaced_candidates(points: np.ndarray, params: DetectionParams) -> np.ndarray:
    """Greedily keep candidates that are not too close in physical distance."""
    selected: list[np.ndarray] = []
    min_distance_sq = params.min_distance_um**2
    scale = np.array([params.z_um_per_px, params.xy_um_per_px, params.xy_um_per_px])

    for point in points:
        if all(np.sum(((point - other) * scale) ** 2) >= min_distance_sq for other in selected):
            selected.append(point)
        if len(selected) >= params.n_beads:
            break

    if not selected:
        return np.empty((0, 3), dtype=float)
    return np.vstack(selected).astype(float)


# TODO: corrected pointsを入力にROI切り出し、Gaussian fit、FWHM計算へ進む。
