"""Generate supplementary figure S14 from the frozen publication table."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .example_traces import (
    EXAMPLE_CELLS,
    SUPRA_OFFSET_MV,
    ExampleTrace,
    example_trace_frame,
    extract_example_traces,
)
from .recompute_features import (
    recompute_spike_features,
    write_pc1_comparison_figure,
    write_recomputed_features,
)

LOGGER = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "data" / "AIBS_spreadsheet_pub.csv"
DEFAULT_OUTPUT = Path.cwd() / "results"
DEFAULT_CACHE = Path(os.environ.get("DANDI_NWB_CACHE", "/scratch/lcne-patchseq-nwb"))

REQUIRED_COLUMNS = {
    "ephys_roi_id",
    "Donor",
    "projection_target",
    "spike_waveform_PC1",
    "membrane_time_constant_ms",
}

GROUPS = (
    ("Spinal cord", "#f2b705"),
    ("Cortex", "#5b2a86"),
    ("Cerebellum", "#e2703a"),
)
GROUP_COLORS = dict(GROUPS)


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
    for column in ("spike_waveform_PC1", "membrane_time_constant_ms"):
        converted = pd.to_numeric(frame[column], errors="coerce")
        invalid = frame[column].notna() & converted.isna()
        if invalid.any():
            raise ValueError(f"Column {column} contains non-numeric values")
        frame[column] = converted
    return frame


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

    if example_trace_sets is None:
        placeholder = figure.add_subplot(grid[0])
        placeholder.set_facecolor("#f4f4f2")
        placeholder.text(
            0.5,
            0.55,
            "Example voltage traces are not available\nin the frozen publication CSV",
            ha="center",
            va="center",
            fontsize=14,
        )
        placeholder.text(
            0.5,
            0.37,
            "Run with recompute features = 1 to restore panel j from DANDI.",
            ha="center",
            va="center",
            color="#555555",
        )
        placeholder.set(xticks=[], yticks=[])
        for spine in placeholder.spines.values():
            spine.set_visible(False)
        placeholder.set_title("LC-NE projections to:", fontstyle="italic")
        placeholder.annotate(
            "j", xy=(0, 1.02), xycoords="axes fraction", fontsize=18, fontweight="bold"
        )
    else:
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
    parser.add_argument(
        "--recompute-features",
        type=int,
        choices=(0, 1),
        default=0,
        help="Recompute spike waveform PC1 from DANDI NWBs when set to 1",
    )
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE, help="NWB cache directory")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    frame = load_frozen_table(args.input)
    example_trace_sets = None
    if args.recompute_features:
        recomputed = recompute_spike_features(frame, args.cache_dir)
        frame = recomputed.metadata
        for path in write_recomputed_features(recomputed, args.output_dir):
            LOGGER.info("Wrote %s", path)
        for path in write_pc1_comparison_figure(recomputed.comparison, args.output_dir):
            LOGGER.info("Wrote %s", path)
        example_trace_sets = {
            cell.ephys_roi_id: extract_example_traces(
                args.cache_dir / f"{cell.ephys_roi_id}.nwb"
            )
            for cell in EXAMPLE_CELLS
        }
        trace_path = args.output_dir / "S14j_example_traces.csv"
        example_trace_frame(example_trace_sets).to_csv(trace_path, index=False)
        LOGGER.info("Wrote %s", trace_path)
    for path in generate_figure(frame, args.output_dir, example_trace_sets):
        LOGGER.info("Wrote %s", path)


if __name__ == "__main__":
    main()