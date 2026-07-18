"""Reconstruct the three S14j example-cell traces from raw NWB files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .nwb_sweeps import CurrentClampSweep, list_current_clamp_sweeps, load_current_clamp_sweep
from .spike_waveforms import detect_efel_peak_times, infer_main_stimulus_pulse

SUPRA_OFFSET_MV = 120.0


@dataclass(frozen=True)
class ExampleCell:
    label: str
    region: str
    ephys_roi_id: str


@dataclass(frozen=True)
class ExampleTrace:
    kind: str
    sweep_number: int
    stimulus_amplitude_pa: float
    time_ms: np.ndarray
    voltage_mv: np.ndarray


EXAMPLE_CELLS = (
    ExampleCell("Isocortex", "Cortex", "1388239233"),
    ExampleCell("Cerebellum", "Cerebellum", "1426757704"),
    ExampleCell("Spinal cord", "Spinal cord", "1410640556"),
)

STIMULUS_LABELS = {
    "supra": "X4PS_SupraThresh_DA_0",
    "rheo": "X3LP_Rheo_DA_0",
    "hyperpol": "X1PS_SubThresh_DA_0",
}


def _extract_peri_stimulus_trace(
    kind: str,
    sweep: CurrentClampSweep,
) -> ExampleTrace:
    pulse = infer_main_stimulus_pulse(sweep.stimulus_pa)
    sample_period_ms = 1000.0 / sweep.sampling_rate_hz
    before_samples = max(
        round(0.010 * sweep.sampling_rate_hz),
        round(0.2 * pulse.sample_count),
    )
    after_samples = max(
        round(0.100 * sweep.sampling_rate_hz),
        round(0.5 * pulse.sample_count),
    )
    begin_index = max(0, pulse.start_index - before_samples)
    end_index = min(len(sweep.voltage_mv), pulse.stop_index + after_samples)
    voltage_mv = sweep.voltage_mv[begin_index:end_index]
    relative_time_ms = np.arange(len(voltage_mv)) * sample_period_ms
    return ExampleTrace(
        kind=kind,
        sweep_number=sweep.sweep_number,
        stimulus_amplitude_pa=pulse.amplitude_pa,
        time_ms=relative_time_ms,
        voltage_mv=voltage_mv,
    )


def extract_example_traces(path: Path) -> dict[str, ExampleTrace]:
    """Select and extract the legacy supra/rheo/hyperpolarizing sweeps."""
    candidates = []
    relevant_labels = set(STIMULUS_LABELS.values())
    for sweep_number, description in sorted(list_current_clamp_sweeps(path).items()):
        if description not in relevant_labels:
            continue
        sweep = load_current_clamp_sweep(path, sweep_number)
        pulse = infer_main_stimulus_pulse(sweep.stimulus_pa)
        if pulse.sample_count < 0.8 * sweep.sampling_rate_hz:
            continue
        spike_count = len(detect_efel_peak_times(sweep.voltage_mv, sweep.sampling_rate_hz))
        candidates.append((description, pulse.amplitude_pa, spike_count, sweep))

    selected = {}
    for kind, label in STIMULUS_LABELS.items():
        matching = [item for item in candidates if item[0] == label]
        if kind != "hyperpol":
            matching = [item for item in matching if item[2] > 0]
        if not matching:
            raise ValueError(f"No valid {kind} sweep found in {path}")
        if kind == "hyperpol":
            choice = max(matching, key=lambda item: (abs(item[1]), -item[3].sweep_number))
        else:
            choice = min(matching, key=lambda item: (abs(item[1]), item[3].sweep_number))
        selected[kind] = _extract_peri_stimulus_trace(kind, choice[3])
    return selected


def example_trace_frame(
    trace_sets: dict[str, dict[str, ExampleTrace]],
) -> pd.DataFrame:
    """Return all S14j traces as an underlying-data table."""
    tables = []
    for cell in EXAMPLE_CELLS:
        for kind in ("hyperpol", "rheo", "supra"):
            trace = trace_sets[cell.ephys_roi_id][kind]
            tables.append(
                pd.DataFrame(
                    {
                        "ephys_roi_id": cell.ephys_roi_id,
                        "projection_target": cell.region,
                        "sweep_type": kind,
                        "sweep_number": trace.sweep_number,
                        "stimulus_amplitude_pa": trace.stimulus_amplitude_pa,
                        "time_ms": trace.time_ms,
                        "voltage_mv": trace.voltage_mv,
                    }
                )
            )
    return pd.concat(tables, ignore_index=True)