from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PIXEL_COLUMNS = ["z", "y", "x"]
CSV_COLUMNS = ["z", "y", "x", "z_um", "y_um", "x_um"]


def ensure_zyx_points(points: np.ndarray) -> np.ndarray:
    """Return points as a float array with shape (n, 3)."""
    points = np.asarray(points, dtype=float)
    if points.size == 0:
        return np.empty((0, 3), dtype=float)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError(f"Expected points with shape (n, 3), got {points.shape}")
    return points


def points_to_dataframe(
    points: np.ndarray,
    *,
    z_um_per_px: float,
    xy_um_per_px: float,
) -> pd.DataFrame:
    points = ensure_zyx_points(points)
    df = pd.DataFrame(points, columns=PIXEL_COLUMNS)
    df["z_um"] = df["z"] * z_um_per_px
    df["y_um"] = df["y"] * xy_um_per_px
    df["x_um"] = df["x"] * xy_um_per_px
    return df[CSV_COLUMNS]


def dataframe_to_points(df: pd.DataFrame) -> np.ndarray:
    missing = [column for column in PIXEL_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Points CSV is missing required columns: {missing}")
    return ensure_zyx_points(df[PIXEL_COLUMNS].to_numpy(dtype=float))


def read_points_csv(path: str | Path) -> np.ndarray:
    return dataframe_to_points(pd.read_csv(path))


def write_points_csv(
    path: str | Path,
    points: np.ndarray,
    *,
    z_um_per_px: float,
    xy_um_per_px: float,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = points_to_dataframe(
        points,
        z_um_per_px=z_um_per_px,
        xy_um_per_px=xy_um_per_px,
    )
    df.to_csv(output_path, index=False)
