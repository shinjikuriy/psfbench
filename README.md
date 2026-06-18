# psfbench

`psfbench` is a small Python/uv project for detecting fluorescent bead centers in 3D TIFF stacks and correcting those candidates in napari.

The current implementation covers:

- load a 3D TIFF stack
- convert the image to float
- subtract a low-percentile background
- lightly smooth with a 3D Gaussian filter
- detect 3D local maxima
- remove low-intensity, edge, and too-close candidates
- prefer candidates near the XY center
- keep about 20 bead candidates
- open napari for manual point editing
- save corrected `(z, y, x)` point coordinates to CSV

FWHM analysis is planned for a later step.

## Setup

Install uv, then create the environment and install dependencies:

```bash
uv sync
```

Run the CLI through uv:

```bash
uv run psfbench --help
```

## TIFF Stack Assumptions

Input can be either:

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

## Metadata

Metadata is not used by default. Specify a metadata source explicitly if you want `psfbench` to fill missing voxel size values from acquisition metadata.

ThorImage directory input is supported:

```bash
uv run psfbench detect \
  --input ../260616_psf/D100per_pow5.18per \
  --output outputs/D100per_pow5.18per_points.csv \
  --metadata-source thorimage
```

For ThorImage, `psfbench` expects `Experiment.xml` in the input directory and checks that the XML root is `ThorImageExperiment`.

The following fields are used:

- `ZStage.stepSizeUM` for `z_um_per_px`
- `LSM.widthUM / LSM.pixelX` for `xy_um_per_px`
- `LSM.pixelSizeUM` as a fallback for `xy_um_per_px`

CLI values always take precedence over metadata values. For example, this uses the CLI value for XY and ThorImage metadata for Z:

```bash
uv run psfbench detect \
  --input ../260616_psf/D100per_pow5.18per \
  --output outputs/D100per_pow5.18per_points.csv \
  --metadata-source thorimage \
  --xy-um-per-px 0.11646
```

## Detect Command

Detect bead candidates, open napari for correction, and save the corrected points:

```bash
uv run psfbench detect \
  --input data/beads_filling_80 \
  --output outputs/beads_filling_80_points.csv \
  --xy-um-per-px 0.11646 \
  --z-um-per-px 0.2 \
  --n-beads 20 \
  --threshold-percentile 99.8 \
  --center-fraction 0.6
```

To detect and save without opening napari:

```bash
uv run psfbench detect \
  --input data/beads_filling_80 \
  --output outputs/beads_filling_80_points.csv \
  --xy-um-per-px 0.11646 \
  --z-um-per-px 0.2 \
  --no-gui
```

## Batch Detect Command

Run detection for every condition directory immediately under an input root:

```bash
uv run psfbench batch-detect \
  --input-root ../260616_psf \
  --output-dir outputs \
  --metadata-source thorimage \
  --n-beads 20
```

This writes one CSV per condition:

```text
outputs/D40per_pow2.24per_points.csv
outputs/D60per_pow1.98per_points.csv
...
```

`batch-detect` defaults to `--no-gui`. To open napari for each stack in sequence, add `--gui`.

## Edit Command

Load an existing points CSV, correct it in napari, and save a new CSV:

```bash
uv run psfbench edit \
  --input data/beads_filling_80 \
  --points outputs/beads_filling_80_points.csv \
  --output outputs/beads_filling_80_points_corrected.csv \
  --xy-um-per-px 0.11646 \
  --z-um-per-px 0.2
```

## Crop ROIs Command

After point correction, crop one 3D ROI around each bead center:

```bash
uv run psfbench crop-rois \
  --input ../260616_psf/D100per_pow5.18per \
  --points outputs/D100per_pow5.18per_points_corrected.csv \
  --output-dir outputs/D100per_pow5.18per_rois \
  --metadata-source thorimage \
  --radius-z-um 3.0 \
  --radius-xy-um 3.0
```

This writes ROI TIFF files and a manifest:

```text
outputs/D100per_pow5.18per_rois/bead_0001.tif
outputs/D100per_pow5.18per_rois/bead_0002.tif
outputs/D100per_pow5.18per_rois/roi_manifest.csv
```

ROIs that would extend beyond the stack bounds are skipped and recorded in `roi_manifest.csv`.

## Measure ROIs Command

Measure each saved ROI with a simple peak-centered line-profile FWHM estimate:

```bash
uv run psfbench measure-rois \
  --roi-dir outputs/D100per_pow5.18per_rois \
  --output outputs/D100per_pow5.18per_measurements.csv
```

The current measurement is a first-pass implementation. It subtracts a low-percentile ROI background, finds the ROI peak, extracts X/Y/Z line profiles through that peak, and estimates FWHM by linear interpolation at half maximum.

The output CSV includes:

- `FWHM_X_um`
- `FWHM_Y_um`
- `FWHM_Z_um`
- `FWHM_XY_mean_um`
- `FWHM_X_over_Y`
- `peak_intensity`
- `integrated_intensity`

## Editing Points In Napari

When napari opens, the TIFF stack is shown together with a `bead candidates` points layer.

Use the normal napari points-layer tools to:

- select and delete incorrect points
- add missed bead centers
- drag existing points to better center positions

Close the napari window when correction is finished. The CLI then writes the final points to the requested CSV path.

## Output CSV

The output CSV contains pixel coordinates and physical coordinates:

```text
z,y,x,z_um,y_um,x_um
```

Coordinate meanings:

- `z`, `y`, `x`: point locations in pixel coordinates, ordered for a `(z, y, x)` stack
- `z_um`: `z * z_um_per_px`
- `y_um`: `y * xy_um_per_px`
- `x_um`: `x * xy_um_per_px`

## Detection Details

Default detection parameters:

- background percentile: `10`
- Gaussian sigma: `(0.5, 1.0, 1.0)`
- threshold percentile: `99.8`
- minimum candidate distance: `2.0 um`
- edge margins: `3.0 um` in Z and XY
- center preference: central `60%` of the XY field
- maximum candidates: `20`

The local maximum filter size is computed from the physical minimum distance and voxel size.

## Planned FWHM Analysis

The next step is to use corrected points as input for ROI cropping, Gaussian fitting, and FWHM calculation for `FWHM_X`, `FWHM_Y`, `FWHM_Z`, `FWHM_XY_mean`, intensity metrics, and filling-rate summaries.
