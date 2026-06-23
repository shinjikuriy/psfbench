from __future__ import annotations

from pathlib import Path

import typer

from psfbench.coordinates import read_points_csv, write_points_csv
from psfbench.detection import DetectionParams, detect_beads
from psfbench.gui import edit_points_with_napari
from psfbench.io import read_tiff_stack
from psfbench.measurement import measure_rois_from_manifest
from psfbench.metadata import MetadataFormat, VoxelSize, resolve_voxel_size
from psfbench.plotting import plot_summary
from psfbench.roi import save_rois
from psfbench.summary import summarize_measurement_files, summarize_measurements


app = typer.Typer(
    help="Analyze PSF beads in 3D TIFF stacks.",
    invoke_without_command=True,
)


@app.callback()
def main(
    ctx: typer.Context,
    input: Path | None = typer.Option(None, "--input", "-i", help="Input stack file or directory for one-shot analysis."),
    output_dir: Path | None = typer.Option(None, "--output-dir", "-o", help="Output directory for one-shot analysis."),
    xy_um_per_px: float | None = typer.Option(None, help="XY pixel size in micrometers per pixel."),
    z_um_per_px: float | None = typer.Option(None, help="Z step size in micrometers per pixel."),
    metadata_format: MetadataFormat = typer.Option(
        MetadataFormat.NONE,
        help="Metadata format used to fill missing voxel size values.",
    ),
    n_beads: int = typer.Option(20, help="Maximum number of bead candidates to keep."),
    threshold_percentile: float = typer.Option(99.8, help="Percentile threshold after smoothing."),
    center_fraction: float = typer.Option(0.6, help="Prefer candidates in this central XY fraction."),
    background_percentile: float = typer.Option(10.0, help="Low percentile used as detection background."),
    min_distance_um: float = typer.Option(2.0, help="Minimum distance between bead candidates."),
    margin_z_um: float = typer.Option(3.0, help="Exclude candidates this close to Z edges."),
    margin_xy_um: float = typer.Option(3.0, help="Exclude candidates this close to XY edges."),
    radius_z_um: float = typer.Option(3.0, help="Half-size of each ROI in Z, in micrometers."),
    radius_xy_um: float = typer.Option(3.0, help="Half-size of each ROI in X and Y, in micrometers."),
    roi_background_percentile: float = typer.Option(10.0, help="Low percentile used as ROI measurement background."),
    condition: str | None = typer.Option(None, help="Condition label written to summary.csv."),
    gui: bool = typer.Option(True, "--gui/--no-gui", help="Open napari for manual point correction."),
) -> None:
    if ctx.invoked_subcommand is not None:
        return
    if input is None or output_dir is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)

    _analyze_one(
        input=input,
        output_dir=output_dir,
        xy_um_per_px=xy_um_per_px,
        z_um_per_px=z_um_per_px,
        metadata_format=metadata_format,
        n_beads=n_beads,
        threshold_percentile=threshold_percentile,
        center_fraction=center_fraction,
        background_percentile=background_percentile,
        min_distance_um=min_distance_um,
        margin_z_um=margin_z_um,
        margin_xy_um=margin_xy_um,
        radius_z_um=radius_z_um,
        radius_xy_um=radius_xy_um,
        roi_background_percentile=roi_background_percentile,
        condition=condition,
        gui=gui,
    )


@app.command()
def detect(
    input: Path = typer.Option(..., "--input", "-i", help="Input 3D TIFF stack file or directory of 2D TIFF planes."),
    output: Path = typer.Option(..., "--output", "-o", help="Output CSV path."),
    xy_um_per_px: float | None = typer.Option(None, help="XY pixel size in micrometers per pixel."),
    z_um_per_px: float | None = typer.Option(None, help="Z step size in micrometers per pixel."),
    metadata_format: MetadataFormat = typer.Option(
        MetadataFormat.NONE,
        help="Metadata format used to fill missing voxel size values.",
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
        metadata_format=metadata_format,
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
    metadata_format: MetadataFormat = typer.Option(
        MetadataFormat.NONE,
        help="Metadata format used to fill missing voxel size values.",
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
            metadata_format=metadata_format,
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
    metadata_format: MetadataFormat,
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
        metadata_format=metadata_format,
        xy_um_per_px=xy_um_per_px,
        z_um_per_px=z_um_per_px,
    )
    stack = read_tiff_stack(input)
    points = _detect_points(
        stack=stack,
        voxel_size=voxel_size,
        n_beads=n_beads,
        threshold_percentile=threshold_percentile,
        center_fraction=center_fraction,
        background_percentile=background_percentile,
        min_distance_um=min_distance_um,
        margin_z_um=margin_z_um,
        margin_xy_um=margin_xy_um,
        gui=gui,
    )
    write_points_csv(
        output,
        points,
        z_um_per_px=voxel_size.z_um_per_px,
        xy_um_per_px=voxel_size.xy_um_per_px,
    )
    return points


def _detect_points(
    *,
    stack,
    voxel_size: VoxelSize,
    n_beads: int,
    threshold_percentile: float,
    center_fraction: float,
    background_percentile: float,
    min_distance_um: float,
    margin_z_um: float,
    margin_xy_um: float,
    gui: bool,
):
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
    return points


def _analyze_one(
    *,
    input: Path,
    output_dir: Path,
    xy_um_per_px: float | None,
    z_um_per_px: float | None,
    metadata_format: MetadataFormat,
    n_beads: int,
    threshold_percentile: float,
    center_fraction: float,
    background_percentile: float,
    min_distance_um: float,
    margin_z_um: float,
    margin_xy_um: float,
    radius_z_um: float,
    radius_xy_um: float,
    roi_background_percentile: float,
    condition: str | None,
    gui: bool,
) -> None:
    voxel_size = _resolve_voxel_size_or_exit(
        input_path=input,
        metadata_format=metadata_format,
        xy_um_per_px=xy_um_per_px,
        z_um_per_px=z_um_per_px,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    points_path = output_dir / "points.csv"
    roi_dir = output_dir / "rois"
    measurements_path = output_dir / "measurements.csv"
    summary_path = output_dir / "summary.csv"

    stack = read_tiff_stack(input)
    points = _detect_points(
        stack=stack,
        voxel_size=voxel_size,
        n_beads=n_beads,
        threshold_percentile=threshold_percentile,
        center_fraction=center_fraction,
        background_percentile=background_percentile,
        min_distance_um=min_distance_um,
        margin_z_um=margin_z_um,
        margin_xy_um=margin_xy_um,
        gui=gui,
    )
    write_points_csv(
        points_path,
        points,
        z_um_per_px=voxel_size.z_um_per_px,
        xy_um_per_px=voxel_size.xy_um_per_px,
    )
    typer.echo(f"Saved {len(points)} points to {points_path}")

    roi_results = save_rois(
        stack,
        points,
        output_dir=roi_dir,
        z_um_per_px=voxel_size.z_um_per_px,
        xy_um_per_px=voxel_size.xy_um_per_px,
        radius_z_um=radius_z_um,
        radius_xy_um=radius_xy_um,
    )
    saved_rois = sum(not result.skipped for result in roi_results)
    skipped_rois = len(roi_results) - saved_rois
    typer.echo(f"Saved {saved_rois} ROI TIFF files to {roi_dir} ({skipped_rois} skipped)")

    measurements = measure_rois_from_manifest(
        roi_dir,
        output=measurements_path,
        background_percentile=roi_background_percentile,
    )
    typer.echo(f"Saved {len(measurements)} ROI measurements to {measurements_path}")

    measurements_for_summary = measurements.copy()
    measurements_for_summary.insert(0, "condition", condition or _default_condition_name(input))
    summary = summarize_measurements(measurements_for_summary)
    summary.to_csv(summary_path, index=False)
    typer.echo(f"Saved summary to {summary_path}")


def _default_condition_name(input: Path) -> str:
    return input.name if input.is_dir() else input.stem


@app.command()
def edit(
    input: Path = typer.Option(..., "--input", "-i", help="Input 3D TIFF stack file or directory of 2D TIFF planes."),
    points: Path = typer.Option(..., "--points", "-p", help="Existing points CSV."),
    output: Path = typer.Option(..., "--output", "-o", help="Corrected output CSV path."),
    xy_um_per_px: float | None = typer.Option(None, help="XY pixel size in micrometers per pixel."),
    z_um_per_px: float | None = typer.Option(None, help="Z step size in micrometers per pixel."),
    metadata_format: MetadataFormat = typer.Option(
        MetadataFormat.NONE,
        help="Metadata format used to fill missing voxel size values.",
    ),
) -> None:
    voxel_size = _resolve_voxel_size_or_exit(
        input_path=input,
        metadata_format=metadata_format,
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


@app.command("crop-rois")
def crop_rois(
    input: Path = typer.Option(..., "--input", "-i", help="Input 3D TIFF stack file or directory of 2D TIFF planes."),
    points: Path = typer.Option(..., "--points", "-p", help="Corrected points CSV."),
    output_dir: Path = typer.Option(..., "--output-dir", "-o", help="Directory for ROI TIFF files and manifest."),
    xy_um_per_px: float | None = typer.Option(None, help="XY pixel size in micrometers per pixel."),
    z_um_per_px: float | None = typer.Option(None, help="Z step size in micrometers per pixel."),
    metadata_format: MetadataFormat = typer.Option(
        MetadataFormat.NONE,
        help="Metadata format used to fill missing voxel size values.",
    ),
    radius_z_um: float = typer.Option(3.0, help="Half-size of each ROI in Z, in micrometers."),
    radius_xy_um: float = typer.Option(3.0, help="Half-size of each ROI in X and Y, in micrometers."),
    prefix: str = typer.Option("bead", help="Prefix for ROI TIFF filenames."),
) -> None:
    voxel_size = _resolve_voxel_size_or_exit(
        input_path=input,
        metadata_format=metadata_format,
        xy_um_per_px=xy_um_per_px,
        z_um_per_px=z_um_per_px,
    )
    stack = read_tiff_stack(input)
    point_array = read_points_csv(points)
    results = save_rois(
        stack,
        point_array,
        output_dir=output_dir,
        z_um_per_px=voxel_size.z_um_per_px,
        xy_um_per_px=voxel_size.xy_um_per_px,
        radius_z_um=radius_z_um,
        radius_xy_um=radius_xy_um,
        prefix=prefix,
    )
    saved = sum(not result.skipped for result in results)
    skipped = len(results) - saved
    typer.echo(
        f"Saved {saved} ROI TIFF files to {output_dir} "
        f"({skipped} skipped; manifest: {output_dir / 'roi_manifest.csv'})"
    )


@app.command("measure-rois")
def measure_rois(
    roi_dir: Path = typer.Option(..., "--roi-dir", "-r", help="Directory containing ROI TIFF files and roi_manifest.csv."),
    output: Path = typer.Option(..., "--output", "-o", help="Output measurement CSV path."),
    background_percentile: float = typer.Option(10.0, help="Low percentile used as ROI background."),
) -> None:
    measurements = measure_rois_from_manifest(
        roi_dir,
        output=output,
        background_percentile=background_percentile,
    )
    typer.echo(f"Saved {len(measurements)} ROI measurements to {output}")


@app.command("aggregate-measurements")
def aggregate_measurements(
    input_dir: Path = typer.Option(..., "--input-dir", "-i", help="Directory containing measurement CSV files."),
    output: Path = typer.Option(..., "--output", "-o", help="Output summary CSV path."),
    pattern: str = typer.Option("*_measurements.csv", help="Glob pattern for measurement CSV files."),
    condition_suffix: str = typer.Option("_measurements", help="Suffix removed from each measurement filename to infer condition."),
    condition_metadata: Path | None = typer.Option(None, "--condition-metadata", help="Optional CSV joined by the condition column."),
) -> None:
    try:
        summary = summarize_measurement_files(
            input_dir,
            output=output,
            pattern=pattern,
            condition_suffix=condition_suffix,
            condition_metadata=condition_metadata,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Saved summary for {len(summary)} conditions to {output}")


@app.command("plot-summary")
def plot_summary_command(
    summary: Path = typer.Option(..., "--summary", "-s", help="Input summary CSV path."),
    output: Path = typer.Option(..., "--output", "-o", help="Output plot path, such as PNG, PDF, or SVG."),
    x: str = typer.Option(..., "--x", help="Summary column used for the x-axis."),
    y: str = typer.Option(..., "--y", help="Summary column used for the y-axis."),
    yerr: str | None = typer.Option(None, "--yerr", help="Optional summary column used for y error bars."),
    title: str | None = typer.Option(None, "--title", help="Optional plot title."),
    x_label: str | None = typer.Option(None, "--x-label", help="Optional x-axis label."),
    y_label: str | None = typer.Option(None, "--y-label", help="Optional y-axis label."),
) -> None:
    try:
        plot_summary(
            summary,
            output=output,
            x=x,
            y=y,
            yerr=yerr,
            title=title,
            x_label=x_label,
            y_label=y_label,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Saved plot to {output}")


def _resolve_voxel_size_or_exit(
    *,
    input_path: Path,
    metadata_format: MetadataFormat,
    xy_um_per_px: float | None,
    z_um_per_px: float | None,
) -> VoxelSize:
    try:
        voxel_size = resolve_voxel_size(
            input_path=input_path,
            metadata_format=metadata_format,
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
