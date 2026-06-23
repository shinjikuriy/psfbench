# Review Action Plan

This file records follow-up work from the Cursor Opus 4.8 review. The goal is to keep actionable review items visible without relying on chat history.

## Immediate Items

### 1. Documentation Cleanup

Status: completed.

- Remove outdated statements that FWHM analysis is still planned.
- Update package descriptions to mention Gaussian FWHM measurement, summary, and plotting.
- Document that current FWHM measurement intentionally uses 1D axis-profile Gaussian fits.
- Document that candidate ranking prefers near-axis beads by default.
- Document current measurement limitations and likely future improvements.

### 2. Numeric Option Validation

Status: planned.

Add CLI-level validation for options that can currently fail late or silently produce invalid measurements:

- `n_beads > 0`
- `threshold_percentile` in `[0, 100]`
- `background_percentile` and `roi_background_percentile` in `[0, 100]`
- `center_fraction` in `(0, 1]`
- `min_distance_um > 0`
- `margin_z_um >= 0`
- `margin_xy_um >= 0`
- `radius_z_um > 0`
- `radius_xy_um > 0`

Prefer clear `typer.BadParameter` messages at the CLI boundary.

### 3. Voxel Size Plausibility Checks

Status: planned.

Add checks after voxel size resolution:

- `xy_um_per_px > 0`
- `z_um_per_px > 0`
- warn or reject implausible values outside a conservative range, initially `0.01 <= value <= 10.0`
- when metadata and CLI values are both present, warn if the CLI value differs substantially from metadata, initially by more than 10%

The warning should be explicit because voxel size errors silently scale every physical FWHM value.

### 4. ROI Radius and Candidate Spacing Warning

Status: planned.

The default detection spacing and ROI radius are currently independent:

- detection `min_distance_um` default: `2.0`
- ROI `radius_xy_um` default: `3.0`

This is not always invalid, but it allows neighboring beads to enter the ROI. Add a warning when:

```text
min_distance_um < 2 * radius_xy_um
```

Do not make this an error yet. The right threshold should be checked against real data.

### 5. Output Overwrite Protection

Status: planned.

Add basic protection against accidental overwrite of existing outputs:

- warn when one-shot output files already exist
- warn when individual command output paths already exist
- consider a later `--force/--no-force` policy after seeing how the tool is used

For now, warning-only behavior is preferable because repeated exploratory runs are common during development and data inspection.

### 6. Version Flag

Status: planned.

Expose package version from the CLI:

```bash
uv run psfbench --version
```

This helps reproduce analysis results and debug reports.
