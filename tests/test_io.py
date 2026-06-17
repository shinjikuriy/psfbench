from __future__ import annotations

import numpy as np
import tifffile

from psfbench.io import read_tiff_stack


def test_read_tiff_stack_accepts_directory_of_2d_tiffs(tmp_path) -> None:
    expected = np.stack(
        [
            np.full((4, 5), 1, dtype=np.uint16),
            np.full((4, 5), 2, dtype=np.uint16),
            np.full((4, 5), 3, dtype=np.uint16),
        ]
    )
    for index, plane in enumerate(expected, start=1):
        tifffile.imwrite(tmp_path / f"ChanA_001_001_{index:03d}_001.tif", plane)
    (tmp_path / "Experiment.xml").write_text("<ThorImageExperiment />")

    stack = read_tiff_stack(tmp_path)

    assert stack.shape == (3, 4, 5)
    assert stack.dtype == np.float32
    np.testing.assert_array_equal(stack, expected.astype(np.float32))


def test_read_tiff_stack_accepts_3d_tiff_file(tmp_path) -> None:
    expected = np.ones((3, 4, 5), dtype=np.uint16)
    path = tmp_path / "stack.tif"
    tifffile.imwrite(path, expected)

    stack = read_tiff_stack(path)

    assert stack.shape == (3, 4, 5)
    assert stack.dtype == np.float32
