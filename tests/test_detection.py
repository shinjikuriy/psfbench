from __future__ import annotations

import numpy as np

from psfbench.detection import DetectionParams, detect_beads


def test_detect_beads_finds_bright_center_candidate() -> None:
    stack = np.zeros((41, 80, 80), dtype=np.float32)
    stack[20, 40, 40] = 1000
    stack[10, 10, 10] = 900

    params = DetectionParams(
        xy_um_per_px=0.2,
        z_um_per_px=0.5,
        n_beads=1,
        threshold_percentile=99.5,
        min_distance_um=2.0,
        margin_z_um=2.0,
        margin_xy_um=2.0,
        center_fraction=0.5,
    )

    points = detect_beads(stack, params)

    assert points.shape == (1, 3)
    np.testing.assert_allclose(points[0], [20, 40, 40], atol=1)


def test_detect_beads_excludes_edges() -> None:
    stack = np.zeros((41, 80, 80), dtype=np.float32)
    stack[20, 40, 40] = 1000
    stack[2, 40, 40] = 5000
    stack[20, 2, 40] = 5000

    params = DetectionParams(
        xy_um_per_px=0.2,
        z_um_per_px=0.5,
        n_beads=5,
        threshold_percentile=99.5,
        margin_z_um=2.0,
        margin_xy_um=2.0,
    )

    points = detect_beads(stack, params)

    assert [20, 40, 40] in points.astype(int).tolist()
    assert [2, 40, 40] not in points.astype(int).tolist()
    assert [20, 2, 40] not in points.astype(int).tolist()
