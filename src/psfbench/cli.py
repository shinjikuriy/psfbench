from __future__ import annotations

from pathlib import Path

import typer

from psfbench.coordinates import read_points_csv, write_points_csv
from psfbench.detection import DetectionParams, detect_beads
from psfbench.gui import edit_points_with_napari
from psfbench.io import read_tiff_stack
from psfbench.metadata import MetadataSource, VoxelSize, resolve_voxel_size


app = typer.Typer(help="Detect and manually correct PSF bead centers in 3D TIFF stacks.")


@app.command()
def detect(
    input: Path = typer.Option(..., "--input", "-i", help="Input 3D TIFF stack file or directory of 2D TIFF planes."),
    output: Path = typer.Option(..., "--output", "-o", help="Output CSV path."),
    xy_um_per_px: float | None = typer.Option(None, help="XY pixel size in micrometers per pixel."),
    z_um_per_px: float | None = typer.Option(None, help="Z step size in micrometers per pixel."),
    metadata_source: MetadataSource = typer.Option(
        MetadataSource.NONE,
        help="Metadata source used to fill missing voxel size values.",
    ),
    n_beads: int = typer.Option(20, help="Maximum number of bead candidates to keep."),
    threshold_percentile: float = typer.Option(99.8, help="Percentile threshold after smoothing."),
    center_fraction: float = typer.Option(0.6, help="Prefer candidates in this central XY fraction."),
    background_percentile: float = typer.Option(10.0, help="Low percentile used as background."),
    min_distance_um: float = typer.Option(2.0, help="Minimum distance between bead candidates."),
    margin_z_um: float = typer.Option(3.0, help="Exclude candidates this close to Z edges."),
    margin_xy_um: float = typer.Option(3.0, help="Exclude candidates this close to XY edges."),
    gui: bool = typer.Option(True, "--gui/--no-gui", help="Open napari for manual correction."),
) -> None:
    points = _detect_one(
        input=input,
        output=output,
        xy_um_per_px=xy_um_per_px,
        z_um_per_px=z_um_per_px,
        metadata_source=metadata_source,
        n_beads=n_beads,
        threshold_percentile=threshold_percentile,
        center_fraction=center_fraction,
        background_percentile=background_percentile,
        min_distance_um=min_distance_um,
        margin_z_um=margin_z_um,
        margin_xy_um=margin_xy_um,
        gui=gui,
    )
    typer.echo(f"Saved {len(points)} points to {output}")


@app.command("batch-detect")
def batch_detect(
    input_root: Path = typer.Option(..., "--input-root", "-i", help="Directory containing one stack directory per condition."),
    output_dir: Path = typer.Option(..., "--output-dir", "-o", help="Directory for output point CSV files."),
    xy_um_per_px: float | None = typer.Option(None, help="XY pixel size in micrometers per pixel."),
    z_um_per_px: float | None = typer.Option(None, help="Z step size in micrometers per pixel."),
    metadata_source: MetadataSource = typer.Option(
        MetadataSource.NONE,
        help="Metadata source used to fill missing voxel size values.",
    ),
    n_beads: int = typer.Option(20, help="Maximum number of bead candidates to keep per stack."),
    threshold_percentile: float = typer.Option(99.8, help="Percentile threshold after smoothing."),
    center_fraction: float = typer.Option(0.6, help="Prefer candidates in this central XY fraction."),
    background_percentile: float = typer.Option(10.0, help="Low percentile used as background."),
    min_distance_um: float = typer.Option(2.0, help="Minimum distance between bead candidates."),
    margin_z_um: float = typer.Option(3.0, help="Exclude candidates this close to Z edges."),
    margin_xy_um: float = typer.Option(3.0, help="Exclude candidates this close to XY edges."),
    suffix: str = typer.Option("_points.csv", help="Suffix appended to each condition directory name."),
    gui: bool = typer.Option(False, "--gui/--no-gui", help="Open napari for manual correction for each stack."),
) -> None:
    if not input_root.is_dir():
        raise typer.BadParameter(f"--input-root must be a directory: {input_root}")

    stack_dirs = sorted(path for path in input_root.iterdir() if path.is_dir())
    if not stack_dirs:
        raise typer.BadParameter(f"No condition directories found under: {input_root}")

    output_dir.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Found {len(stack_dirs)} condition directories under {input_root}")

    for index, stack_dir in enumerate(stack_dirs, start=1):
        output = output_dir / f"{stack_dir.name}{suffix}"
        typer.echo(f"[{index}/{len(stack_dirs)}] Detecting {stack_dir} -> {output}")
        points = _detect_one(
            input=stack_dir,
            output=output,
            xy_um_per_px=xy_um_per_px,
            z_um_per_px=z_um_per_px,
            metadata_source=metadata_source,
            n_beads=n_beads,
            threshold_percentile=threshold_percentile,
            center_fraction=center_fraction,
            background_percentile=background_percentile,
            min_distance_um=min_distance_um,
            margin_z_um=margin_z_um,
            margin_xy_um=margin_xy_um,
            gui=gui,
        )
        typer.echo(f"Saved {len(points)} points to {output}")


def _detect_one(
    *,
    input: Path,
    output: Path,
    xy_um_per_px: float | None,
    z_um_per_px: float | None,
    metadata_source: MetadataSource,
    n_beads: int,
    threshold_percentile: float,
    center_fraction: float,
    background_percentile: float,
    min_distance_um: float,
    margin_z_um: float,
    margin_xy_um: float,
    gui: bool,
):
    voxel_size = _resolve_voxel_size_or_exit(
        input_path=input,
        metadata_source=metadata_source,
        xy_um_per_px=xy_um_per_px,
        z_um_per_px=z_um_per_px,
    )
    stack = read_tiff_stack(input)
    params = DetectionParams(
        xy_um_per_px=voxel_size.xy_um_per_px,
        z_um_per_px=voxel_size.z_um_per_px,
        n_beads=n_beads,
        background_percentile=background_percentile,
        threshold_percentile=threshold_percentile,
        min_distance_um=min_distance_um,
        margin_z_um=margin_z_um,
        margin_xy_um=margin_xy_um,
        center_fraction=center_fraction,
    )
    points = detect_beads(stack, params)
    if gui:
        points = edit_points_with_napari(
            stack,
            points,
            z_um_per_px=voxel_size.z_um_per_px,
            xy_um_per_px=voxel_size.xy_um_per_px,
        )
    write_points_csv(
        output,
        points,
        z_um_per_px=voxel_size.z_um_per_px,
        xy_um_per_px=voxel_size.xy_um_per_px,
    )
    return points


@app.command()
def edit(
    input: Path = typer.Option(..., "--input", "-i", help="Input 3D TIFF stack file or directory of 2D TIFF planes."),
    points: Path = typer.Option(..., "--points", "-p", help="Existing points CSV."),
    output: Path = typer.Option(..., "--output", "-o", help="Corrected output CSV path."),
    xy_um_per_px: float | None = typer.Option(None, help="XY pixel size in micrometers per pixel."),
    z_um_per_px: float | None = typer.Option(None, help="Z step size in micrometers per pixel."),
    metadata_source: MetadataSource = typer.Option(
        MetadataSource.NONE,
        help="Metadata source used to fill missing voxel size values.",
    ),
) -> None:
    voxel_size = _resolve_voxel_size_or_exit(
        input_path=input,
        metadata_source=metadata_source,
        xy_um_per_px=xy_um_per_px,
        z_um_per_px=z_um_per_px,
    )
    stack = read_tiff_stack(input)
    initial_points = read_points_csv(points)
    corrected_points = edit_points_with_napari(
        stack,
        initial_points,
        z_um_per_px=voxel_size.z_um_per_px,
        xy_um_per_px=voxel_size.xy_um_per_px,
    )
    write_points_csv(
        output,
        corrected_points,
        z_um_per_px=voxel_size.z_um_per_px,
        xy_um_per_px=voxel_size.xy_um_per_px,
    )
    typer.echo(f"Saved {len(corrected_points)} points to {output}")


def _resolve_voxel_size_or_exit(
    *,
    input_path: Path,
    metadata_source: MetadataSource,
    xy_um_per_px: float | None,
    z_um_per_px: float | None,
) -> VoxelSize:
    try:
        voxel_size = resolve_voxel_size(
            input_path=input_path,
            metadata_source=metadata_source,
            xy_um_per_px=xy_um_per_px,
            z_um_per_px=z_um_per_px,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if voxel_size.metadata is not None:
        typer.echo(
            "Using metadata from "
            f"{voxel_size.metadata.path} "
            f"(xy_um_per_px={voxel_size.xy_um_per_px:.6g}, "
            f"z_um_per_px={voxel_size.z_um_per_px:.6g})"
        )
    return voxel_size


if __name__ == "__main__":
    app()
