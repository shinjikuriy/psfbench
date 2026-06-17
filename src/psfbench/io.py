from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile


def read_tiff_stack(path: str | Path) -> np.ndarray:
    input_path = Path(path)
    if input_path.is_dir():
        tiff_paths = sorted(
            [
                *input_path.glob("*.tif"),
                *input_path.glob("*.tiff"),
                *input_path.glob("*.TIF"),
                *input_path.glob("*.TIFF"),
            ]
        )
        if not tiff_paths:
            raise ValueError(f"No TIFF files found in directory: {input_path}")
        planes = []
        for tiff_path in tiff_paths:
            with tifffile.TiffFile(tiff_path) as tif:
                planes.append(tif.pages[0].asarray())
        stack = np.stack(planes, axis=0)
    else:
        stack = tifffile.imread(input_path)

    if stack.ndim != 3:
        raise ValueError(f"Expected a 3D TIFF stack with shape (z, y, x), got {stack.shape}")
    return np.asarray(stack, dtype=np.float32)
