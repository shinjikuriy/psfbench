from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_MEASUREMENT_COLUMNS = [
    "FWHM_X_um",
    "FWHM_Y_um",
    "FWHM_Z_um",
    "FWHM_XY_mean_um",
    "FWHM_X_over_Y",
    "FWHM_X_line_um",
    "FWHM_Y_line_um",
    "FWHM_Z_line_um",
    "FWHM_XY_mean_line_um",
    "FWHM_X_over_Y_line",
    "peak_intensity",
    "integrated_intensity",
]


def summarize_measurement_files(
    input_dir: str | Path,
    *,
    output: str | Path,
    pattern: str = "*_measurements.csv",
    condition_suffix: str = "_measurements",
    condition_metadata: str | Path | None = None,
    measurement_columns: list[str] | None = None,
) -> pd.DataFrame:
    input_dir = Path(input_dir)
    paths = sorted(input_dir.glob(pattern))
    if not paths:
        raise ValueError(f"No measurement CSV files matching {pattern!r} found in {input_dir}")

    combined = load_measurement_files(paths, condition_suffix=condition_suffix)
    summary = summarize_measurements(
        combined,
        measurement_columns=measurement_columns or DEFAULT_MEASUREMENT_COLUMNS,
    )
    if condition_metadata is not None:
        summary = join_condition_metadata(summary, condition_metadata)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False)
    return summary


def load_measurement_files(paths: list[Path], *, condition_suffix: str = "_measurements") -> pd.DataFrame:
    frames = []
    for path in paths:
        df = pd.read_csv(path)
        if "condition" not in df.columns:
            df.insert(0, "condition", infer_condition_name(path, condition_suffix=condition_suffix))
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def infer_condition_name(path: str | Path, *, condition_suffix: str = "_measurements") -> str:
    name = Path(path).stem
    if condition_suffix and name.endswith(condition_suffix):
        return name[: -len(condition_suffix)]
    return name


def summarize_measurements(
    measurements: pd.DataFrame,
    *,
    measurement_columns: list[str] = DEFAULT_MEASUREMENT_COLUMNS,
) -> pd.DataFrame:
    if "condition" not in measurements.columns:
        raise ValueError("Measurements must include a condition column.")

    rows = []
    for condition, group in measurements.groupby("condition", sort=True):
        row = {"condition": condition}
        for column in measurement_columns:
            if column not in group.columns:
                continue
            values = pd.to_numeric(group[column], errors="coerce").dropna()
            count = int(values.count())
            row[f"{column}_count"] = count
            row[f"{column}_mean"] = float(values.mean()) if count else np.nan
            row[f"{column}_sd"] = float(values.std(ddof=1)) if count > 1 else np.nan
            row[f"{column}_sem"] = float(values.std(ddof=1) / np.sqrt(count)) if count > 1 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def join_condition_metadata(summary: pd.DataFrame, metadata_path: str | Path) -> pd.DataFrame:
    if "condition" not in summary.columns:
        raise ValueError("Summary must include a condition column.")

    metadata = pd.read_csv(metadata_path)
    if "condition" not in metadata.columns:
        raise ValueError("Condition metadata CSV must include a condition column.")
    if metadata["condition"].duplicated().any():
        duplicated = sorted(metadata.loc[metadata["condition"].duplicated(), "condition"].astype(str).unique())
        raise ValueError(f"Condition metadata contains duplicate condition values: {duplicated}")

    metadata_columns = [column for column in metadata.columns if column != "condition"]
    overlapping = [column for column in metadata_columns if column in summary.columns]
    if overlapping:
        raise ValueError(f"Condition metadata columns overlap summary columns: {overlapping}")

    return summary.merge(metadata, on="condition", how="left")
