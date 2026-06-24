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
- `--metadata-format thorimage`: load voxel size metadata from ThorImage files instead of specifying voxel size manually

### Detect Command

Use individual subcommands when you want to inspect or rerun only part of the pipeline.

Detect bead candidates, open napari for correction, and save the corrected points:

```bash
uv run psfbench detect \
  --input data/condition_001 \
  --output outputs/condition_001_points.csv \
  --xy-um-per-px 0.11646 \
  --z-um-per-px 0.2 \
  --n-beads 20 \
  --threshold-percentile 99.8 \
  --center-fraction 0.6
```

Add `--no-gui` to save automatically detected points without opening napari.

### Batch Detect Command

Run detection for every condition directory immediately under an input root:

```bash
uv run psfbench batch-detect \
  --input-root data \
  --output-dir outputs \
  --metadata-format thorimage \
  --n-beads 20
```

This writes one CSV per condition:

```text
outputs/condition_001_points.csv
outputs/condition_002_points.csv
...
```

`batch-detect` defaults to `--no-gui`. To open napari for each stack in sequence, add `--gui`.

### Edit Command

Load an existing points CSV, correct it in napari, and save a new CSV:

```bash
uv run psfbench edit \
  --input data/condition_001 \
  --points outputs/condition_001_points.csv \
  --output outputs/condition_001_points_corrected.csv \
  --xy-um-per-px 0.11646 \
  --z-um-per-px 0.2
```

### Crop ROIs Command

After point correction, crop one 3D ROI around each bead center:

```bash
uv run psfbench crop-rois \
  --input data/condition_001 \
  --points outputs/condition_001_points_corrected.csv \
  --output-dir outputs/condition_001_rois \
  --metadata-format thorimage \
  --radius-z-um 3.0 \
  --radius-xy-um 3.0
```

This writes ROI TIFF files and a manifest:

```text
outputs/condition_001_rois/bead_0001.tif
outputs/condition_001_rois/bead_0002.tif
outputs/condition_001_rois/roi_manifest.csv
```

ROIs that would extend beyond the stack bounds are skipped and recorded in `roi_manifest.csv`.

### Measure ROIs Command

Measure each saved ROI with Gaussian FWHM estimates and line-profile diagnostic widths:

```bash
uv run psfbench measure-rois \
  --roi-dir outputs/condition_001_rois \
  --output outputs/condition_001_measurements.csv
```

The measurement subtracts a low-percentile ROI background, finds the ROI peak, extracts X/Y/Z line profiles through that peak, fits each profile with a 1D Gaussian, and computes FWHM from the fitted sigma. It also reports direct line-profile FWHM values by linear interpolation at half maximum as diagnostic columns.

This is intentionally a 1D axis-profile measurement. It is suitable for consistent condition-to-condition comparison of bead PSFs, especially near the optical axis. It does not currently perform sub-voxel center estimation or full 3D Gaussian fitting. Those approaches may improve absolute accuracy, but they also add assumptions and fitting failure modes. The current implementation keeps the simpler 1D Gaussian FWHM as the primary metric and exposes QC columns so suspicious beads can be reviewed.

The output CSV includes:

- `FWHM_X_um`
- `FWHM_Y_um`
- `FWHM_Z_um`
- `FWHM_XY_mean_um`
- `FWHM_X_over_Y`
- `FWHM_X_line_um`
- `FWHM_Y_line_um`
- `FWHM_Z_line_um`
- `FWHM_XY_mean_line_um`
- `FWHM_X_over_Y_line`
- Gaussian fit status and quality columns such as `gaussian_x_success`, `gaussian_x_sigma_um`, and `gaussian_x_r_squared`
- QC columns such as `qc_any_warning`, `qc_fit_failed`, `qc_peak_near_roi_edge`, `qc_low_r_squared`, and `line_gaussian_rel_diff_x`
- `peak_intensity`
- `integrated_intensity`

QC columns are diagnostic flags only. They do not exclude beads from the output CSV.

### Aggregate Measurements Command

Summarize multiple measurement CSV files by condition:

```bash
uv run psfbench aggregate-measurements \
  --input-dir outputs \
  --output outputs/summary.csv
```

By default, the command reads files matching `*_measurements.csv`. The condition name is inferred from the filename by removing `_measurements`.

The summary includes count, mean, SD, and SEM for each measurement column.

You can optionally join experiment-level condition metadata:

```bash
uv run psfbench aggregate-measurements \
  --input-dir outputs \
  --output outputs/summary.csv \
  --condition-metadata condition_metadata.csv
```

The metadata CSV must include a `condition` column. Other columns are copied into the summary:

```csv
condition,filling_rate,power_percent
condition_001,40,2.0
condition_002,80,3.0
condition_003,100,5.0
```

### Plot Summary Command

Plot any columns from a summary CSV:

```bash
uv run psfbench plot-summary \
  --summary outputs/summary.csv \
  --x filling_rate \
  --y FWHM_Z_um_mean \
  --yerr FWHM_Z_um_sem \
  --output outputs/fwhm_z_vs_filling_rate.png
```

Without condition metadata, plot by condition label:

```bash
uv run psfbench plot-summary \
  --summary outputs/summary.csv \
  --x condition \
  --y FWHM_Z_um_mean \
  --yerr FWHM_Z_um_sem \
  --output outputs/fwhm_z_by_condition.png
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

### Metadata

Metadata is not used by default. Specify a metadata format explicitly if you want `psfbench` to fill missing voxel size values from acquisition metadata.

For ThorImage, `psfbench` expects `Experiment.xml` in the input directory and checks that the XML root is `ThorImageExperiment`.

The following fields are used:

- `ZStage.stepSizeUM` for `z_um_per_px`
- `LSM.widthUM / LSM.pixelX` for `xy_um_per_px`
- `LSM.pixelSizeUM` as a fallback for `xy_um_per_px`

CLI values always take precedence over metadata values. For example, `--xy-um-per-px 0.11646 --metadata-format thorimage` uses the CLI value for XY and ThorImage metadata for Z.

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
