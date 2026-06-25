# psfbench

*End-to-end PSF bead analysis from 3D TIFF stacks: detect fluorescent beads, review centers, measure FWHM, and export summaries and plots.*

`psfbench` is a Python/uv project that lets you:

- load a 3D TIFF stack or a ThorImage acquisition directory
- detect fluorescent bead candidates automatically
- review, add, move, or delete bead centers manually
- crop bead-centered 3D ROIs
- measure X, Y, and Z PSF FWHM values using Gaussian fits
- export per-bead measurements, condition summaries, QC flags, and plots

## Setup

Install uv, then create the environment and install dependencies:

```bash
uv sync
```

Run the CLI through uv:

```bash
uv run psfbench --help
```

## Usage

### One-Shot Analysis

For a single measurement dataset, run `psfbench`.

```bash
uv run psfbench \
  --input data/condition_001.tif \
  --output-dir outputs/condition_001 \
  --xy-um-per-px 0.11646 \
  --z-um-per-px 0.2
```

Bead candidates will be automatically selected and shown in napari.  
You can add, remove, or move them there.  
After napari is closed, analysis continues automatically.

The output directory contains:

```text
outputs/condition_001/
  points.csv
  rois/
    bead_0001.tif
    ...
    roi_manifest.csv
  measurements.csv
  summary.csv
```

Common optional arguments:

- `--no-gui`: skip napari and use automatically detected bead centers as-is
- `--n-beads 20`: change the maximum number of bead candidates
- `--threshold-percentile 99.8`: change the brightness threshold for candidate detection
- `--center-fraction 0.6`: prefer candidates within the central fraction of the XY field
- `--radius-z-um 3.0` and `--radius-xy-um 3.0`: change the ROI half-size used for FWHM measurement
- `--metadata-format thorimage`: load voxel size metadata from ThorImage files

Each step of the single-dataset pipeline can also be run independently. See [Pipeline subcommands](docs/pipeline-subcommands.md).

### Use Vendor Metadata

By default, you must specify voxel size parameters such as `--xy-um-per-px` and `--z-um-per-px`. `psfbench` can use acquisition metadata from supported vendor software when you pass `--metadata-format`.

Currently, only `thorimage` is supported:

```bash
uv run psfbench \
  --input data/condition_001 \
  --output-dir outputs/condition_001 \
  --metadata-format thorimage
```

For `--metadata-format thorimage`, `psfbench` expects `Experiment.xml` in the input directory and checks that the XML root is `ThorImageExperiment`.

The following fields are used:

- `ZStage.stepSizeUM` for `z_um_per_px`
- `LSM.widthUM / LSM.pixelX` for `xy_um_per_px`
- `LSM.pixelSizeUM` as a fallback for `xy_um_per_px`

CLI values always take precedence over metadata values. For example, `--xy-um-per-px 0.11646 --metadata-format thorimage` uses the CLI value for XY and ThorImage metadata for Z.

### Aggregate Measurements

After measuring multiple conditions, summarize per-bead measurement CSV files by condition:

```bash
uv run psfbench aggregate-measurements \
  --input-dir outputs \
  --output outputs/summary.csv
```

The summary includes count, mean, SD, and SEM for each measurement column. You can optionally join condition-level metadata:

```bash
uv run psfbench aggregate-measurements \
  --input-dir outputs \
  --output outputs/summary.csv \
  --condition-metadata condition_metadata.csv
```

The metadata CSV must include a `condition` column:

```csv
condition,filling_rate,power_percent
condition_001,40,2.0
condition_002,80,3.0
condition_003,100,5.0
```

### Plot Summary

Plot columns from a summary CSV:

```bash
uv run psfbench plot-summary \
  --summary outputs/summary.csv \
  --x filling_rate \
  --y FWHM_Z_um_mean \
  --yerr FWHM_Z_um_sem \
  --output outputs/fwhm_z_vs_filling_rate.png
```

The output extension controls the file type, for example `.png`, `.pdf`, or `.svg`.

## Details

### Input Stacks And Coordinates

`--input` can be either:

- a 3D TIFF stack file
- a directory containing 2D TIFF planes

Directories are read by sorting `*.tif`, `*.tiff`, `*.TIF`, and `*.TIFF` files and stacking them along Z. Non-TIFF files in the same directory are ignored.

The resulting stack is expected to have shape:

```text
(z, y, x)
```

For the stated acquisition settings:

- `xy_um_per_px = 119.26 / 1024 = 0.11646`
- `z_um_per_px = 0.2`

napari receives the image scale as:

```python
scale=(z_um_per_px, xy_um_per_px, xy_um_per_px)
```

The points layer also uses `(z, y, x)` pixel coordinate order.

### Point Coordinate CSV

The output CSV contains pixel coordinates and physical coordinates:

```text
z,y,x,z_um,y_um,x_um
```

Coordinate meanings:

- `z`, `y`, `x`: point locations in pixel coordinates, ordered for a `(z, y, x)` stack
- `z_um`: `z * z_um_per_px`
- `y_um`: `y * xy_um_per_px`
- `x_um`: `x * xy_um_per_px`

### Detection Details

Default detection parameters:

- background percentile: `10`
- Gaussian sigma: `(0.5, 1.0, 1.0)`
- threshold percentile: `99.8`
- minimum candidate distance: `2.0 um`
- edge margins: `3.0 um` in Z and XY
- center preference: central `60%` of the XY field
- maximum candidates: `20`

The local maximum filter size is computed from the physical minimum distance and voxel size.

Candidate ranking intentionally prefers beads near the XY center by default. This matches the current use case of comparing near-axis PSF measurements across filling-rate conditions. If off-axis PSF variation is the target, adjust `--center-fraction` or use the lower-level commands to review a broader set of beads.
