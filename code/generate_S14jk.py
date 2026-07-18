"""Generate supplementary figure S14 from the frozen publication table."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import logging
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import ttest_ind

from dandi import download_nwb, load_assets
from example_traces import (
    EXAMPLE_CELLS,
    SUPRA_OFFSET_MV,
    ExampleTrace,
    example_trace_frame,
    extract_example_traces,
)
from spikes import compute_pc1, extract_representative_spike, waveform_frame

LOGGER = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "data" / "LCNE_patchseq_S14_cell_table.csv"
DEFAULT_OUTPUT = ROOT.parent / "results"
DEFAULT_CACHE = Path(os.environ.get("DANDI_NWB_CACHE", "/scratch/lcne-patchseq-nwb"))
DEFAULT_WORKERS = min(8, os.cpu_count() or 1)

REQUIRED_COLUMNS = {
    "ephys_roi_id",
    "Donor",
    "projection_target",
    "membrane_time_constant_ms",
}

GROUPS = (
    ("Spinal cord", "#f2b705"),
    ("Cortex", "#5b2a86"),
    ("Cerebellum", "#e2703a"),
)
GROUP_COLORS = dict(GROUPS)

MANUSCRIPT_TESTS = (
    ("action_potential_waveform_pc1", "spike_waveform_PC1", "Spinal cord", "Cortex", 0.01),
    (
        "action_potential_waveform_pc1",
        "spike_waveform_PC1",
        "Spinal cord",
        "Cerebellum",
        0.05,
    ),
    (
        "membrane_time_constant",
        "membrane_time_constant_ms",
        "Spinal cord",
        "Cortex",
        0.001,
    ),
    (
        "membrane_time_constant",
        "membrane_time_constant_ms",
        "Cerebellum",
        "Cortex",
        0.001,
    ),
)


def load_frozen_table(path: Path) -> pd.DataFrame:
    """Load and validate the frozen per-cell publication table."""
    frame = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    unknown_groups = sorted(set(frame["projection_target"].dropna()) - {g[0] for g in GROUPS})
    if unknown_groups:
        raise ValueError(f"Unexpected projection targets: {', '.join(unknown_groups)}")

    frame = frame.copy()
    frame["ephys_roi_id"] = frame["ephys_roi_id"].astype(str)
    frame["membrane_time_constant_ms"] = pd.to_numeric(
        frame["membrane_time_constant_ms"], errors="raise"
    )
    return frame


def _extract_cell(task):
    ephys_roi_id, asset, cache_dir = task
    spike = extract_representative_spike(download_nwb(asset, cache_dir))
    return ephys_roi_id, spike


def recompute_features(frame: pd.DataFrame, cache_dir: Path, workers: int):
    ephys_roi_ids = frame["ephys_roi_id"].tolist()
    assets = load_assets(ephys_roi_ids)
    tasks = [(ephys_roi_id, assets[ephys_roi_id], cache_dir) for ephys_roi_id in ephys_roi_ids]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        representatives = dict(pool.map(_extract_cell, tasks))

    provenance = []
    for position, ephys_roi_id in enumerate(ephys_roi_ids, start=1):
        asset = assets[ephys_roi_id]
        spike = representatives[ephys_roi_id]
        LOGGER.info("Recomputed %s (%d/%d)", ephys_roi_id, position, len(ephys_roi_ids))
        provenance.append(
            {
                "ephys_roi_id": ephys_roi_id,
                "dandi_asset_id": asset.asset_id,
                "dandi_asset_path": asset.path,
                "dandi_asset_size_bytes": asset.size,
                "dandi_asset_sha256": asset.sha256,
                "selected_sweep_number": spike.sweep_number,
                "stimulus_amplitude_pa": spike.stimulus_amplitude_pa,
                "spike_count": len(spike.peak_indices),
            }
        )

    waveforms = waveform_frame(representatives)
    recomputed_pc1 = compute_pc1(waveforms)
    updated = frame.set_index("ephys_roi_id")
    updated["spike_waveform_PC1"] = recomputed_pc1
    return updated.reset_index(), pd.DataFrame(provenance), waveforms


def write_projection_statistics(frame: pd.DataFrame, output_dir: Path) -> Path:
    tests = []
    for measurement, column, group_a, group_b, threshold in MANUSCRIPT_TESTS:
        values_a = frame.loc[frame["projection_target"] == group_a, column].dropna().to_numpy()
        values_b = frame.loc[frame["projection_target"] == group_b, column].dropna().to_numpy()
        result = ttest_ind(values_a, values_b, equal_var=False)
        tests.append(
            {
                "measurement": measurement,
                "column": column,
                "comparison": f"{group_a} vs. {group_b}",
                "group_a": {
                    "name": group_a,
                    "n_cells": len(values_a),
                    "mean": float(np.mean(values_a)),
                    "standard_deviation": float(np.std(values_a, ddof=1)),
                },
                "group_b": {
                    "name": group_b,
                    "n_cells": len(values_b),
                    "mean": float(np.mean(values_b)),
                    "standard_deviation": float(np.std(values_b, ddof=1)),
                },
                "t_statistic": float(result.statistic),
                "degrees_of_freedom": float(result.df),
                "p_value_two_sided": float(result.pvalue),
                "manuscript_threshold": threshold,
                "meets_manuscript_threshold": bool(result.pvalue < threshold),
            }
        )

    artifact = {
        "test": "Welch independent two-sample t-test",
        "alternative": "two-sided",
        "unit_of_analysis": "cell",
        "note": (
            "The manuscript says paired t-tests, but the source analysis used "
            "scipy.stats.ttest_ind(equal_var=False); projection groups also have unequal sizes."
        ),
        "tests": tests,
    }
    path = output_dir / "S14_projection_target_statistics.json"
    with path.open("w") as stream:
        json.dump(artifact, stream, indent=2)
    return path


def _group_values(frame: pd.DataFrame, column: str):
    groups = []
    for label, color in GROUPS:
        rows = frame.loc[frame["projection_target"] == label]
        values = rows[column].dropna().to_numpy(dtype=float)
        groups.append((label, values, color, rows["Donor"].nunique()))
    return groups


def _plot_cdf(ax, groups, title: str, xlabel: str) -> None:
    for label, values, color, donor_count in groups:
        sorted_values = np.sort(values)
        fractions = np.arange(1, len(sorted_values) + 1) / len(sorted_values)
        ax.step(
            sorted_values,
            fractions,
            where="post",
            color=color,
            linewidth=1.8,
            label=f"{label} (n={len(values)}, {donor_count} mice)",
        )
    ax.set(title=title, xlabel=xlabel, ylabel="Cumulative fraction", ylim=(0, 1))
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="best")


def _raw_data(frame: pd.DataFrame, source_column: str, output_column: str) -> pd.DataFrame:
    raw = frame.loc[
        frame[source_column].notna(),
        ["ephys_roi_id", "Donor", "projection_target", source_column],
    ].copy()
    return raw.rename(columns={source_column: output_column}).reset_index(drop=True)


def _cumulative_data(groups, value_column: str) -> pd.DataFrame:
    tables = []
    for label, values, *_ in groups:
        sorted_values = np.sort(values)
        tables.append(
            pd.DataFrame(
                {
                    "projection_target": label,
                    value_column: sorted_values,
                    "cumulative_fraction": np.arange(1, len(sorted_values) + 1)
                    / len(sorted_values),
                }
            )
        )
    return pd.concat(tables, ignore_index=True)


def _add_scale_bar(ax, x_ms=200, y_mv=50, x0=0.02, y0=0.05) -> None:
    (x_low, x_high), (y_low, y_high) = ax.get_xlim(), ax.get_ylim()
    x_span, y_span = x_high - x_low, y_high - y_low
    x_start = x_low + x0 * x_span
    y_start = y_low + y0 * y_span
    ax.plot([x_start, x_start], [y_start, y_start + y_mv], color="black", linewidth=1.5)
    ax.plot([x_start, x_start + x_ms], [y_start, y_start], color="black", linewidth=1.5)
    ax.text(
        x_start - 0.01 * x_span,
        y_start + y_mv / 2,
        f"{y_mv} mV",
        ha="right",
        va="center",
        fontsize=8,
        rotation=90,
    )
    ax.text(
        x_start + x_ms / 2,
        y_start - 0.02 * y_span,
        f"{x_ms} ms",
        ha="center",
        va="top",
        fontsize=8,
    )


def _plot_example_panel(figure, grid_spec, trace_sets: dict[str, dict[str, ExampleTrace]]) -> None:
    trace_grid = grid_spec.subgridspec(1, 3, wspace=0.05)
    axes = []
    for index, cell in enumerate(EXAMPLE_CELLS):
        axis = figure.add_subplot(trace_grid[index])
        traces = trace_sets[cell.ephys_roi_id]
        color = GROUP_COLORS[cell.region]
        for kind in ("hyperpol", "rheo"):
            trace = traces[kind]
            axis.plot(trace.time_ms, trace.voltage_mv, color=color, linewidth=1.0)
        supra = traces["supra"]
        axis.plot(
            supra.time_ms,
            supra.voltage_mv + SUPRA_OFFSET_MV,
            color=color,
            linewidth=1.0,
        )
        axis.set_title(cell.label, fontsize=11)
        axis.axis("off")
        axes.append(axis)

    y_low = min(axis.get_ylim()[0] for axis in axes)
    y_high = max(axis.get_ylim()[1] for axis in axes)
    for axis in axes:
        axis.set_ylim(y_low, y_high)
    _add_scale_bar(axes[0])
    axes[0].annotate(
        "j", xy=(-0.12, 1.08), xycoords="axes fraction", fontsize=18, fontweight="bold"
    )
    figure.text(0.31, 0.94, "LC-NE projections to:", ha="center", fontstyle="italic")


def generate_figure(
    frame: pd.DataFrame,
    output_dir: Path,
    example_trace_sets: dict[str, dict[str, ExampleTrace]] | None = None,
) -> list[Path]:
    """Render the combined figure and export the S14k underlying data."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pc1_groups = _group_values(frame, "spike_waveform_PC1")
    tau_groups = _group_values(frame, "membrane_time_constant_ms")

    plt.rcParams.update({"font.size": 11, "svg.fonttype": "none"})
    figure = plt.figure(figsize=(16, 4.5))
    figure.subplots_adjust(left=0.04, right=0.98, bottom=0.18, top=0.84, wspace=0.24)
    grid = figure.add_gridspec(1, 2, width_ratios=(3, 2))

    _plot_example_panel(figure, grid[0], example_trace_sets)

    cdf_grid = grid[1].subgridspec(1, 2, wspace=0.38)
    pc1_axis = figure.add_subplot(cdf_grid[0])
    tau_axis = figure.add_subplot(cdf_grid[1])
    _plot_cdf(pc1_axis, pc1_groups, "PC1", "PC1")
    _plot_cdf(
        tau_axis,
        tau_groups,
        "Membrane time constant",
        "Membrane time constant (ms)",
    )
    pc1_axis.annotate(
        "k", xy=(-0.22, 1.02), xycoords="axes fraction", fontsize=18, fontweight="bold"
    )

    outputs = [output_dir / "S14jk.png", output_dir / "S14jk.svg"]
    for path in outputs:
        figure.savefig(path, dpi=300)
    plt.close(figure)

    tables = {
        "S14jk_PC1_raw.csv": _raw_data(frame, "spike_waveform_PC1", "PC1"),
        "S14jk_PC1_cumulative.csv": _cumulative_data(pc1_groups, "PC1"),
        "S14jk_membrane_time_constant_raw.csv": _raw_data(
            frame, "membrane_time_constant_ms", "membrane_time_constant_ms"
        ),
        "S14jk_membrane_time_constant_cumulative.csv": _cumulative_data(
            tau_groups, "membrane_time_constant_ms"
        ),
    }
    for filename, table in tables.items():
        path = output_dir / filename
        table.to_csv(path, index=False)
        outputs.append(path)
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Frozen CSV path")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="Output directory")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE, help="NWB cache directory")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Parallel workers")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame = load_frozen_table(args.input)
    frame, provenance, waveforms = recompute_features(frame, args.cache_dir, args.workers)
    for filename, table in (
        ("S14jk_spike_recomputation_provenance.csv", provenance),
        ("S14jk_representative_spike_waveforms.csv", waveforms),
    ):
        path = args.output_dir / filename
        table.to_csv(path, index=filename.endswith("waveforms.csv"))
        LOGGER.info("Wrote %s", path)
    example_trace_sets = {
        cell.ephys_roi_id: extract_example_traces(args.cache_dir / f"{cell.ephys_roi_id}.nwb")
        for cell in EXAMPLE_CELLS
    }
    trace_path = args.output_dir / "S14j_example_traces.csv"
    example_trace_frame(example_trace_sets).to_csv(trace_path, index=False)
    LOGGER.info("Wrote %s", trace_path)
    metadata_path = args.output_dir / "LCNE_patchseq_S14_cell_table.csv"
    frame.to_csv(metadata_path, index=False)
    LOGGER.info("Wrote %s", metadata_path)
    statistics_path = write_projection_statistics(frame, args.output_dir)
    LOGGER.info("Wrote %s", statistics_path)
    for path in generate_figure(frame, args.output_dir, example_trace_sets):
        LOGGER.info("Wrote %s", path)


if __name__ == "__main__":
    main()