from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from xml.etree import ElementTree


class MetadataFormat(str, Enum):
    NONE = "none"
    THORIMAGE = "thorimage"


@dataclass(frozen=True)
class ImageMetadata:
    format: MetadataFormat
    path: Path
    xy_um_per_px: float | None = None
    z_um_per_px: float | None = None
    size_x_px: int | None = None
    size_y_px: int | None = None
    size_z_px: int | None = None
    width_um: float | None = None
    height_um: float | None = None
    modality: str | None = None
    objective: str | None = None
    pockels_power: float | None = None


@dataclass(frozen=True)
class VoxelSize:
    xy_um_per_px: float
    z_um_per_px: float
    metadata: ImageMetadata | None = None


def read_metadata(input_path: str | Path, metadata_format: MetadataFormat) -> ImageMetadata | None:
    input_path = Path(input_path)
    if metadata_format == MetadataFormat.NONE:
        return None
    if metadata_format == MetadataFormat.THORIMAGE:
        return read_thorimage_metadata(input_path)
    raise ValueError(f"Unsupported metadata format: {metadata_format}")


def read_thorimage_metadata(input_path: str | Path) -> ImageMetadata:
    input_path = Path(input_path)
    if not input_path.is_dir():
        raise ValueError("--metadata-format thorimage requires --input to be a directory.")

    xml_path = input_path / "Experiment.xml"
    if not xml_path.exists():
        raise ValueError(f"--metadata-format thorimage was specified, but {xml_path} was not found.")

    root = ElementTree.parse(xml_path).getroot()
    if root.tag != "ThorImageExperiment":
        raise ValueError(
            "--metadata-format thorimage was specified, but Experiment.xml root "
            f"was {root.tag!r}, not 'ThorImageExperiment'."
        )

    z_stage = root.find("ZStage")
    lsm = root.find("LSM")
    modality = root.find("Modality")
    magnification = root.find("Magnification")
    pockels = root.find("Pockels")

    z_um_per_px = _float_attr(z_stage, "stepSizeUM")
    size_z_px = _int_attr(z_stage, "steps")
    size_x_px = _int_attr(lsm, "pixelX")
    size_y_px = _int_attr(lsm, "pixelY")
    width_um = _float_attr(lsm, "widthUM")
    height_um = _float_attr(lsm, "heightUM")
    pixel_size_um = _float_attr(lsm, "pixelSizeUM")

    xy_um_per_px = None
    if width_um is not None and size_x_px:
        xy_um_per_px = width_um / size_x_px
    elif pixel_size_um is not None:
        xy_um_per_px = pixel_size_um

    return ImageMetadata(
        format=MetadataFormat.THORIMAGE,
        path=xml_path,
        xy_um_per_px=xy_um_per_px,
        z_um_per_px=z_um_per_px,
        size_x_px=size_x_px,
        size_y_px=size_y_px,
        size_z_px=size_z_px,
        width_um=width_um,
        height_um=height_um,
        modality=_str_attr(modality, "name"),
        objective=_str_attr(magnification, "name"),
        pockels_power=_float_attr(pockels, "start"),
    )


def resolve_voxel_size(
    *,
    input_path: str | Path,
    metadata_format: MetadataFormat,
    xy_um_per_px: float | None,
    z_um_per_px: float | None,
) -> VoxelSize:
    metadata = read_metadata(input_path, metadata_format)

    resolved_xy = xy_um_per_px
    resolved_z = z_um_per_px
    if metadata is not None:
        resolved_xy = resolved_xy if resolved_xy is not None else metadata.xy_um_per_px
        resolved_z = resolved_z if resolved_z is not None else metadata.z_um_per_px

    missing = []
    if resolved_xy is None:
        missing.append("--xy-um-per-px")
    if resolved_z is None:
        missing.append("--z-um-per-px")
    if missing:
        hint = " or specify --metadata-format thorimage" if metadata_format == MetadataFormat.NONE else ""
        raise ValueError(f"Missing required voxel size option(s): {', '.join(missing)}{hint}.")

    return VoxelSize(
        xy_um_per_px=resolved_xy,
        z_um_per_px=resolved_z,
        metadata=metadata,
    )


def _str_attr(element: ElementTree.Element | None, name: str) -> str | None:
    if element is None:
        return None
    value = element.get(name)
    return value if value != "" else None


def _float_attr(element: ElementTree.Element | None, name: str) -> float | None:
    value = _str_attr(element, name)
    if value is None:
        return None
    return float(value)


def _int_attr(element: ElementTree.Element | None, name: str) -> int | None:
    value = _str_attr(element, name)
    if value is None:
        return None
    return int(value)
