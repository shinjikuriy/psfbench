# Pipeline Subcommands

Use these subcommands when you want to inspect or rerun only part of the single-dataset pipeline.

## Detect

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

## Batch Detect

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

## Edit

Load an existing points CSV, correct it in napari, and save a new CSV:

```bash
uv run psfbench edit \
  --input data/condition_001 \
  --points outputs/condition_001_points.csv \
  --output outputs/condition_001_points_corrected.csv \
  --xy-um-per-px 0.11646 \
  --z-um-per-px 0.2
```

## Crop ROIs

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

The command stops if `--output-dir` is not empty. Add `--overwrite` to remove existing
ROI TIFF files and `roi_manifest.csv` before writing the new results. Other files are preserved.

## Measure ROIs

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
