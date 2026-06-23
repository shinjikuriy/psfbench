from __future__ import annotations

from pathlib import Path

import pytest

from psfbench.metadata import MetadataFormat, read_thorimage_metadata, resolve_voxel_size


def test_read_thorimage_metadata_prefers_width_over_rounded_pixel_size(tmp_path: Path) -> None:
    write_thorimage_xml(tmp_path, width_um="119.26", pixel_x="1024", pixel_size_um="0.116")

    metadata = read_thorimage_metadata(tmp_path)

    assert metadata.format == MetadataFormat.THORIMAGE
    assert metadata.z_um_per_px == 0.2
    assert metadata.xy_um_per_px == pytest.approx(119.26 / 1024)
    assert metadata.size_z_px == 76
    assert metadata.size_x_px == 1024
    assert metadata.size_y_px == 1024
    assert metadata.modality == "Multiphoton"
    assert metadata.objective == "25X OLY"
    assert metadata.pockels_power == 5.18


def test_read_thorimage_metadata_rejects_non_thorimage_xml(tmp_path: Path) -> None:
    (tmp_path / "Experiment.xml").write_text("<Experiment />")

    with pytest.raises(ValueError, match="not 'ThorImageExperiment'"):
        read_thorimage_metadata(tmp_path)


def test_resolve_voxel_size_prefers_cli_values_over_metadata(tmp_path: Path) -> None:
    write_thorimage_xml(tmp_path, width_um="119.26", pixel_x="1024", pixel_size_um="0.116")

    voxel_size = resolve_voxel_size(
        input_path=tmp_path,
        metadata_format=MetadataFormat.THORIMAGE,
        xy_um_per_px=0.12,
        z_um_per_px=None,
    )

    assert voxel_size.xy_um_per_px == 0.12
    assert voxel_size.z_um_per_px == 0.2


def test_resolve_voxel_size_requires_values_without_metadata(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="--xy-um-per-px, --z-um-per-px"):
        resolve_voxel_size(
            input_path=tmp_path,
            metadata_format=MetadataFormat.NONE,
            xy_um_per_px=None,
            z_um_per_px=None,
        )


def write_thorimage_xml(
    directory: Path,
    *,
    width_um: str,
    pixel_x: str,
    pixel_size_um: str,
) -> None:
    (directory / "Experiment.xml").write_text(
        f"""<?xml version="1.0"?>
<ThorImageExperiment>
  <Software version="4.1.2021.9131" />
  <ZStage name="ThorMCM3000" steps="76" stepSizeUM="0.2" />
  <LSM name="ResonanceGalvo" pixelX="{pixel_x}" pixelY="1024" pixelSizeUM="{pixel_size_um}" widthUM="{width_um}" heightUM="119.26" />
  <Magnification mag="27.78" indexOfRefraction="1.3" name="25X OLY" />
  <Pockels start="5.18" stop="5.18" />
  <Modality primaryDetectorType="1" name="Multiphoton" />
</ThorImageExperiment>
"""
    )
