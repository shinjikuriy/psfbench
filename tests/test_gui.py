from __future__ import annotations

import os

from psfbench.gui import _filter_stderr_lines, _is_macos_qt_keyboard_warning


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
