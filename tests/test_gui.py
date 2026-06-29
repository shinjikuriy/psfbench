from __future__ import annotations

import os

import numpy as np

from psfbench.gui import (
    _filter_stderr_lines,
    _is_macos_qt_keyboard_warning,
    _points_layer_name,
    _update_point_annotations,
)


class FakePointsLayer:
    def __init__(self, data: np.ndarray) -> None:
        self.data = data
        self.name = ""
        self.features: object = None


def test_update_point_annotations_numbers_points_and_updates_count() -> None:
    layer = FakePointsLayer(np.zeros((3, 3)))

    _update_point_annotations(layer)

    assert layer.name == "bead candidates (3)"
    assert isinstance(layer.features, dict)
    np.testing.assert_array_equal(layer.features["bead_index"], [1, 2, 3])

    layer.data = np.zeros((2, 3))
    _update_point_annotations(layer)

    assert layer.name == "bead candidates (2)"
    np.testing.assert_array_equal(layer.features["bead_index"], [1, 2])


def test_points_layer_name_handles_empty_layer() -> None:
    assert _points_layer_name(0) == "bead candidates (0)"


def test_is_macos_qt_keyboard_warning_matches_cocoa_carbon_message() -> None:
    line = (
        "WARNING: Mismatch between Cocoa '\\x8' and Carbon '\\x0' "
        "for virtual key 51 with QFlags<Qt::KeyboardModifier>(AltModifier|MetaModifier)"
    )

    assert _is_macos_qt_keyboard_warning(line)
    assert not _is_macos_qt_keyboard_warning("WARNING: something else")


def test_filter_stderr_lines_suppresses_only_matching_lines(capfd) -> None:
    warning = b"WARNING: Mismatch between Cocoa '\\x8' and Carbon '\\x0' for virtual key 51\n"
    normal = b"real error message\n"

    with _filter_stderr_lines(_is_macos_qt_keyboard_warning):
        os.write(2, warning)
        os.write(2, normal)

    captured = capfd.readouterr()
    assert "Mismatch between Cocoa" not in captured.err
    assert "real error message" in captured.err
