"""Recompute representative spike waveforms from raw patch-seq sweeps."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from ephys import CurrentClampSweep, list_current_clamp_sweeps, load_current_clamp_sweep

LONG_SQUARE_RHEO_LABELS = ("X3LP_Rheo_DA_0", "X5LP_Rheo_DA_0")
SPIKE_THRESHOLD_MV = -10.0
SPIKE_WINDOW_MS = (-5.0, 10.0)


@dataclass(frozen=True)
class StimulusPulse:
    """A contiguous nonbaseline stimulus pulse."""

    start_index: int
    stop_index: int
    amplitude_pa: float

    @property
    def sample_count(self) -> int:
        return self.stop_index - self.start_index


@dataclass(frozen=True)
class RepresentativeSpike:
    """The selected rheobase sweep and its averaged peak-aligned waveform."""

    sweep_number: int
    stimulus_amplitude_pa: float
    peak_indices: np.ndarray
    time_ms: np.ndarray
    waveform_mv: np.ndarray


def infer_main_stimulus_pulse(stimulus_pa: np.ndarray) -> StimulusPulse:
    """Return the longest finite pulse relative to the modal stimulus baseline."""
    stimulus_pa = np.asarray(stimulus_pa, dtype=float)
    finite = np.isfinite(stimulus_pa)
    edge_samples = max(1, len(stimulus_pa) // 20)
    edges = np.concatenate((stimulus_pa[:edge_samples], stimulus_pa[-edge_samples:]))
    baseline = float(np.nanmedian(edges))
    active = finite & ~np.isclose(stimulus_pa, baseline, atol=1e-6, rtol=0.0)
    starts = np.flatnonzero(active & np.r_[True, ~active[:-1]])
    stops = np.flatnonzero(active & np.r_[~active[1:], True]) + 1
    start, stop = max(zip(starts, stops), key=lambda bounds: bounds[1] - bounds[0])
    amplitude = float(np.nanmedian(stimulus_pa[start:stop]) - baseline)
    return StimulusPulse(int(start), int(stop), amplitude)


def detect_efel_peak_indices(
    voltage_mv: np.ndarray,
    threshold_mv: float = SPIKE_THRESHOLD_MV,
) -> np.ndarray:
    """Detect peaks using eFEL's strict threshold-crossing pair algorithm.

    eFEL pairs each strict upward threshold crossing with the next strict
    downward crossing and reports the maximum sample in that inclusive span.
    """
    voltage_mv = np.asarray(voltage_mv, dtype=float)
    upward = np.flatnonzero(
        (voltage_mv[1:] > threshold_mv) & (voltage_mv[:-1] < threshold_mv)
    ) + 1
    downward = np.flatnonzero(
        (voltage_mv[1:] < threshold_mv) & (voltage_mv[:-1] > threshold_mv)
    ) + 1

    while len(upward) and len(downward) and downward[0] < upward[0]:
        downward = downward[1:]
    if len(upward) > len(downward):
        upward = upward[: len(downward)]

    peaks = []
    for start, stop in zip(upward, downward):
        segment = voltage_mv[start : stop + 1]
        if np.isfinite(segment).any():
            peaks.append(int(start + np.nanargmax(segment)))
    return np.asarray(peaks, dtype=int)


def detect_efel_peak_times(
    voltage_mv: np.ndarray,
    sampling_rate_hz: float,
    threshold_mv: float = SPIKE_THRESHOLD_MV,
) -> np.ndarray:
    """Interpolate as eFEL does and return peak times in milliseconds."""
    step_ms = 1000.0 / sampling_rate_hz
    raw_time_ms = np.arange(len(voltage_mv)) * step_ms
    interpolated_size = int(np.ceil(raw_time_ms[-1] / step_ms))
    increments = np.full(interpolated_size, step_ms)
    increments[0] = 0.0
    interpolated_time_ms = np.cumsum(increments)
    next_time = interpolated_time_ms[-1] + step_ms
    if interpolated_time_ms[-1] < raw_time_ms[-1]:
        interpolated_time_ms = np.append(interpolated_time_ms, next_time)
    interpolated_voltage_mv = np.interp(
        interpolated_time_ms,
        raw_time_ms,
        np.asarray(voltage_mv, dtype=float),
    )
    peak_indices = detect_efel_peak_indices(interpolated_voltage_mv, threshold_mv)
    return interpolated_time_ms[peak_indices]


def _candidate_rheobase_sweep(sweep: CurrentClampSweep) -> tuple[StimulusPulse, np.ndarray] | None:
    pulse = infer_main_stimulus_pulse(sweep.stimulus_pa)
    if pulse.sample_count < 0.8 * sweep.sampling_rate_hz:
        return None
    peak_times_ms = detect_efel_peak_times(sweep.voltage_mv, sweep.sampling_rate_hz)
    pulse_start_ms = pulse.start_index * 1000.0 / sweep.sampling_rate_hz
    pulse_stop_ms = pulse.stop_index * 1000.0 / sweep.sampling_rate_hz
    peaks_during_pulse = peak_times_ms[
        (peak_times_ms >= pulse_start_ms) & (peak_times_ms < pulse_stop_ms)
    ]
    if not len(peaks_during_pulse):
        return None
    return pulse, peak_times_ms


def extract_representative_spike(path: Path) -> RepresentativeSpike:
    """Reproduce the legacy ``long_square_rheo, min`` average waveform."""
    candidates = []
    for sweep_number, description in sorted(list_current_clamp_sweeps(path).items()):
        if description not in LONG_SQUARE_RHEO_LABELS:
            continue
        sweep = load_current_clamp_sweep(path, sweep_number)
        candidate = _candidate_rheobase_sweep(sweep)
        if candidate is not None:
            pulse, peaks = candidate
            candidates.append((abs(pulse.amplitude_pa), sweep_number, pulse, peaks, sweep))
    if not candidates:
        raise ValueError(f"No spiking long-square rheobase sweep found in {path}")

    _, sweep_number, pulse, _, sweep = min(candidates, key=lambda item: (item[0], item[1]))
    peak_times_ms = detect_efel_peak_times(sweep.voltage_mv, sweep.sampling_rate_hz)
    before = round(abs(SPIKE_WINDOW_MS[0]) * sweep.sampling_rate_hz / 1000.0)
    after = round(SPIKE_WINDOW_MS[1] * sweep.sampling_rate_hz / 1000.0)
    raw_time_ms = np.arange(len(sweep.voltage_mv)) * 1000.0 / sweep.sampling_rate_hz
    waveforms = []
    for peak_time_ms in peak_times_ms:
        indices = np.flatnonzero(
            (raw_time_ms >= peak_time_ms + SPIKE_WINDOW_MS[0])
            & (raw_time_ms < peak_time_ms + SPIKE_WINDOW_MS[1])
        )
        waveforms.append(sweep.voltage_mv[indices])
    expected_samples = before + after
    waveforms = [waveform for waveform in waveforms if len(waveform) == expected_samples]
    time_ms = np.arange(
        SPIKE_WINDOW_MS[0],
        SPIKE_WINDOW_MS[1],
        1000.0 / sweep.sampling_rate_hz,
    )
    return RepresentativeSpike(
        sweep_number=sweep_number,
        stimulus_amplitude_pa=pulse.amplitude_pa,
        peak_indices=np.searchsorted(raw_time_ms, peak_times_ms),
        time_ms=time_ms,
        waveform_mv=np.mean(waveforms, axis=0),
    )


def waveform_frame(representatives: dict[str, RepresentativeSpike]) -> pd.DataFrame:
    first = next(iter(representatives.values()))
    return pd.DataFrame(
        {ephys_roi_id: spike.waveform_mv for ephys_roi_id, spike in representatives.items()},
        index=first.time_ms,
    ).T.rename_axis("ephys_roi_id")


def compute_pc1(waveforms: pd.DataFrame) -> pd.Series:
    time_ms = np.asarray(waveforms.columns, dtype=float)
    values = waveforms.to_numpy(dtype=float)
    normalize = (time_ms >= -2) & (time_ms <= 4)
    minimum = values[:, normalize].min(axis=1, keepdims=True)
    span = np.ptp(values[:, normalize], axis=1, keepdims=True)
    normalized = (values - minimum) / span
    analysis = (time_ms >= -3) & (time_ms <= 6)
    centered = normalized[:, analysis] - normalized[:, analysis].mean(axis=0)
    left_vectors, singular_values, loadings = np.linalg.svd(centered, full_matrices=False)
    signs = np.sign(loadings[np.arange(len(loadings)), np.argmax(np.abs(loadings), axis=1)])
    signs[signs == 0] = 1
    return pd.Series(
        (left_vectors * signs * singular_values)[:, 0],
        index=waveforms.index,
        name="spike_waveform_PC1",
    )