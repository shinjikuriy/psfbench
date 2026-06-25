# Maintenance Backlog

This file records medium-priority improvements from code review. These are not blockers for current PSF measurement work, but they are worth revisiting.

## Numerical Improvements

- Add sub-voxel bead center refinement before profile extraction.
- Add averaged profile extraction around the peak instead of using a single-pixel-wide axis line.
- Consider full 3D Gaussian fitting for higher absolute accuracy.
- Consider optional local background plane fitting for sloped backgrounds.
- Consider weighted Gaussian fitting if detector noise assumptions are defined.
- Add explicit documentation that `integrated_intensity` depends on ROI size, neighboring objects, and background estimation.
- Add an option to sample beads across the whole field of view for off-axis PSF analysis.
- Consider physical-unit smoothing parameters for detection instead of pixel-unit `gaussian_sigma`.

## Code Structure

- Reduce duplicated Typer option definitions in `cli.py`.
- Split `measurement.py` into smaller modules, for example:
  - profile extraction
  - Gaussian fitting and FWHM calculation
  - measurement QC
  - manifest/CSV I/O
- Remove `bead_index=-1` and `roi_path=Path()` placeholders from `RoiMeasurement`; keep those in manifest/CSV-level records instead.
- Add return type annotations to internal CLI helpers such as `_detect_one`, `_detect_points`, and `_analyze_one`.
- Consider a metadata reader registry instead of `if/elif` dispatch when more vendor formats are added.
- Consider a project-specific exception hierarchy if CLI error handling becomes more complex.
- Consider using `logging` for batch diagnostics while keeping CLI output concise.

## CLI and User Experience

- Improve napari/Qt failure messages, especially for headless environments, with a hint to use `--no-gui`.
- Improve `plot-summary` errors by showing available columns when a requested column is missing.
- Revisit output CSV naming conventions if downstream analysis becomes inconvenient. Current names intentionally preserve common PSF-style names such as `FWHM_X_um`.
- Consider stronger overwrite protection after the exploratory workflow stabilizes.

## Project Infrastructure

- Add a lightweight CI workflow that runs `pytest`.
- Add a license if the project will be shared outside the lab.

