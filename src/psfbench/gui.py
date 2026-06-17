from __future__ import annotations

import numpy as np

from psfbench.coordinates import ensure_zyx_points


def edit_points_with_napari(
    stack: np.ndarray,
    points: np.ndarray,
    *,
    z_um_per_px: float,
    xy_um_per_px: float,
) -> np.ndarray:
    """Open napari and return edited point coordinates in (z, y, x) pixel order."""
    import napari

    points = ensure_zyx_points(points)
    scale = (z_um_per_px, xy_um_per_px, xy_um_per_px)

    viewer = napari.Viewer(ndisplay=3)
    viewer.add_image(stack, name="3D TIFF stack", scale=scale)
    points_layer = viewer.add_points(
        points,
        name="bead candidates",
        scale=scale,
        size=8,
        face_color="magenta",
        ndim=3,
    )
    napari.run()
    return ensure_zyx_points(points_layer.data)
