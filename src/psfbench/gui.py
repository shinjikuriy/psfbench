from __future__ import annotations

from contextlib import contextmanager
import os
import sys
import threading
from collections.abc import Callable, Iterator

import numpy as np

from psfbench.coordinates import ensure_zyx_points


_MACOS_QT_KEYBOARD_WARNING_PARTS = (
    "Mismatch between Cocoa",
    "Carbon",
    "virtual key",
)


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
    with suppress_macos_qt_keyboard_warnings():
        napari.run()
    return ensure_zyx_points(points_layer.data)


@contextmanager
def suppress_macos_qt_keyboard_warnings() -> Iterator[None]:
    if sys.platform != "darwin":
        yield
        return

    with _filter_stderr_lines(_is_macos_qt_keyboard_warning):
        yield


@contextmanager
def _filter_stderr_lines(should_suppress: Callable[[str], bool]) -> Iterator[None]:
    stderr_fd = 2
    saved_stderr_fd = os.dup(stderr_fd)
    read_fd, write_fd = os.pipe()

    def forward_filtered_stderr() -> None:
        buffer = b""
        with os.fdopen(read_fd, "rb", closefd=True) as stream:
            while True:
                chunk = stream.readline()
                if not chunk:
                    break
                buffer += chunk
                if chunk.endswith(b"\n"):
                    _write_stderr_line(saved_stderr_fd, buffer, should_suppress)
                    buffer = b""
            if buffer:
                _write_stderr_line(saved_stderr_fd, buffer, should_suppress)

    thread = threading.Thread(target=forward_filtered_stderr, daemon=True)
    thread.start()
    os.dup2(write_fd, stderr_fd)
    os.close(write_fd)
    try:
        yield
    finally:
        sys.stderr.flush()
        os.dup2(saved_stderr_fd, stderr_fd)
        thread.join(timeout=1.0)
        os.close(saved_stderr_fd)


def _write_stderr_line(saved_stderr_fd: int, line: bytes, should_suppress: Callable[[str], bool]) -> None:
    text = line.decode(errors="replace")
    if not should_suppress(text):
        os.write(saved_stderr_fd, line)


def _is_macos_qt_keyboard_warning(line: str) -> bool:
    return all(part in line for part in _MACOS_QT_KEYBOARD_WARNING_PARTS)
