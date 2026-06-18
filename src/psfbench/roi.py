from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import tifffile

from psfbench.coordinates import ensure_zyx_points


@dataclass(frozen=True)
class RoiBounds:
    z_start: int
    z_stop: int
    y_start: int
    y_stop: int
    x_start: int
    x_stop: int


@dataclass(frozen=True)
class RoiResult:
    bead_index: int
    center_zyx: tuple[float, float, float]
    rounded_center_zyx: tuple[int, int, int]
    bounds: RoiBounds | None
    roi_path: Path | None
    skipped: bool
    skip_reason: str | None = None


def crop_roi(
    stack: np.ndarray,
    center_zyx: np.ndarray,
    *,
    radius_z_px: int,
    radius_xy_px: int,
) -> tuple[np.ndarray, RoiBounds] | None:
    if stack.ndim != 3:
        raise ValueError(f"Expected stack with shape (z, y, x), got {stack.shape}")

    center_z, center_y, center_x = np.rint(center_zyx).astype(int)
    bounds = RoiBounds(
        z_start=center_z - radius_z_px,
        z_stop=center_z + radius_z_px + 1,
        y_start=center_y - radius_xy_px,
        y_stop=center_y + radius_xy_px + 1,
        x_start=center_x - radius_xy_px,
        x_stop=center_x + radius_xy_px + 1,
    )
    z_size, y_size, x_size = stack.shape
    if (
        bounds.z_start < 0
        or bounds.y_start < 0
        or bounds.x_start < 0
        or bounds.z_stop > z_size
        or bounds.y_stop > y_size
        or bounds.x_stop > x_size
    ):
        return None

    roi = stack[
        bounds.z_start : bounds.z_stop,
        bounds.y_start : bounds.y_stop,
        bounds.x_start : bounds.x_stop,
    ]
    return roi, bounds


def save_rois(
    stack: np.ndarray,
    points: np.ndarray,
    *,
    output_dir: str | Path,
    z_um_per_px: float,
    xy_um_per_px: float,
    radius_z_um: float = 3.0,
    radius_xy_um: float = 3.0,
    prefix: str = "bead",
) -> list[RoiResult]:
    points = ensure_zyx_points(points)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    radius_z_px = max(1, round(radius_z_um / z_um_per_px))
    radius_xy_px = max(1, round(radius_xy_um / xy_um_per_px))

    results: list[RoiResult] = []
    for bead_index, point in enumerate(points, start=1):
        rounded_center = tuple(int(value) for value in np.rint(point))
        crop = crop_roi(
            stack,
            point,
            radius_z_px=radius_z_px,
            radius_xy_px=radius_xy_px,
        )
        if crop is None:
            results.append(
                RoiResult(
                    bead_index=bead_index,
                    center_zyx=tuple(float(value) for value in point),
                    rounded_center_zyx=rounded_center,
                    bounds=None,
                    roi_path=None,
                    skipped=True,
                    skip_reason="ROI extends beyond stack bounds",
                )
            )
            continue

        roi, bounds = crop
        roi_path = output_dir / f"{prefix}_{bead_index:04d}.tif"
        tifffile.imwrite(roi_path, roi)
        results.append(
            RoiResult(
                bead_index=bead_index,
                center_zyx=tuple(float(value) for value in point),
                rounded_center_zyx=rounded_center,
                bounds=bounds,
                roi_path=roi_path,
                skipped=False,
            )
        )

    write_roi_manifest(
        output_dir / "roi_manifest.csv",
        results,
        z_um_per_px=z_um_per_px,
        xy_um_per_px=xy_um_per_px,
        radius_z_um=radius_z_um,
        radius_xy_um=radius_xy_um,
        radius_z_px=radius_z_px,
        radius_xy_px=radius_xy_px,
    )
    return results


def write_roi_manifest(
    path: str | Path,
    results: list[RoiResult],
    *,
    z_um_per_px: float,
    xy_um_per_px: float,
    radius_z_um: float,
    radius_xy_um: float,
    radius_z_px: int,
    radius_xy_px: int,
) -> None:
    rows = []
    for result in results:
        z, y, x = result.center_zyx
        rounded_z, rounded_y, rounded_x = result.rounded_center_zyx
        bounds = result.bounds
        rows.append(
            {
                "bead_index": result.bead_index,
                "z": z,
                "y": y,
                "x": x,
                "z_um": z * z_um_per_px,
                "y_um": y * xy_um_per_px,
                "x_um": x * xy_um_per_px,
                "rounded_z": rounded_z,
                "rounded_y": rounded_y,
                "rounded_x": rounded_x,
                "z_start": bounds.z_start if bounds else None,
                "z_stop": bounds.z_stop if bounds else None,
                "y_start": bounds.y_start if bounds else None,
                "y_stop": bounds.y_stop if bounds else None,
                "x_start": bounds.x_start if bounds else None,
                "x_stop": bounds.x_stop if bounds else None,
                "radius_z_um": radius_z_um,
                "radius_xy_um": radius_xy_um,
                "radius_z_px": radius_z_px,
                "radius_xy_px": radius_xy_px,
                "z_um_per_px": z_um_per_px,
                "xy_um_per_px": xy_um_per_px,
                "roi_path": str(result.roi_path) if result.roi_path else "",
                "skipped": result.skipped,
                "skip_reason": result.skip_reason or "",
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)
