"""Recompute representative spike waveforms from raw patch-seq sweeps."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from nwb_sweeps import CurrentClampSweep, list_current_clamp_sweeps, load_current_clamp_sweep

LONG_SQUARE_RHEO = "X3LP_Rheo_DA_0"
LEGACY_SAMPLING_RATE_HZ = 50_000.0
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
    if not finite.any():
        raise ValueError("Stimulus has no finite samples")

    edge_samples = max(1, len(stimulus_pa) // 20)
    edges = np.concatenate((stimulus_pa[:edge_samples], stimulus_pa[-edge_samples:]))
    baseline = float(np.nanmedian(edges))
    if not np.isfinite(baseline):
        raise ValueError("Stimulus endpoints have no finite baseline samples")
    active = finite & ~np.isclose(stimulus_pa, baseline, atol=1e-6, rtol=0.0)
    starts = np.flatnonzero(active & np.r_[True, ~active[:-1]])
    stops = np.flatnonzero(active & np.r_[~active[1:], True]) + 1
    if not len(starts):
        raise ValueError("Stimulus has no nonbaseline pulse")

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


def _candidate_rheobase_sweep(sweep: CurrentClampSweep) -> tuple[StimulusPulse, np.ndarray] | None:
    if sweep.sampling_rate_hz != LEGACY_SAMPLING_RATE_HZ:
        raise ValueError(
            f"Sweep {sweep.sweep_number} has sampling rate {sweep.sampling_rate_hz}, "
            f"expected {LEGACY_SAMPLING_RATE_HZ}"
        )
    pulse = infer_main_stimulus_pulse(sweep.stimulus_pa)
    if pulse.sample_count < 0.8 * sweep.sampling_rate_hz:
        return None
    peaks = detect_efel_peak_indices(sweep.voltage_mv)
    peaks_during_pulse = peaks[
        (peaks >= pulse.start_index) & (peaks < pulse.stop_index)
    ]
    if not len(peaks_during_pulse):
        return None
    return pulse, peaks


def extract_representative_spike(path: Path) -> RepresentativeSpike:
    """Reproduce the legacy ``long_square_rheo, min`` average waveform."""
    candidates = []
    for sweep_number, description in sorted(list_current_clamp_sweeps(path).items()):
        if description != LONG_SQUARE_RHEO:
            continue
        sweep = load_current_clamp_sweep(path, sweep_number)
        candidate = _candidate_rheobase_sweep(sweep)
        if candidate is not None:
            pulse, peaks = candidate
            candidates.append((abs(pulse.amplitude_pa), sweep_number, pulse, peaks, sweep))
    if not candidates:
        raise ValueError(f"No spiking {LONG_SQUARE_RHEO} sweep found in {path}")

    _, sweep_number, pulse, peaks, sweep = min(candidates, key=lambda item: (item[0], item[1]))
    before = round(abs(SPIKE_WINDOW_MS[0]) * sweep.sampling_rate_hz / 1000.0)
    after = round(SPIKE_WINDOW_MS[1] * sweep.sampling_rate_hz / 1000.0)
    waveforms = [
        sweep.voltage_mv[peak - before : peak + after]
        for peak in peaks
        if peak >= before and peak + after <= len(sweep.voltage_mv)
    ]
    expected_samples = before + after
    waveforms = [waveform for waveform in waveforms if len(waveform) == expected_samples]
    if not waveforms:
        raise ValueError(f"Sweep {sweep_number} has no complete spike windows")

    time_ms = np.arange(
        SPIKE_WINDOW_MS[0],
        SPIKE_WINDOW_MS[1],
        1000.0 / sweep.sampling_rate_hz,
    )
    if len(time_ms) != expected_samples:
        raise ValueError("Spike time axis does not match the extracted waveform length")
    return RepresentativeSpike(
        sweep_number=sweep_number,
        stimulus_amplitude_pa=pulse.amplitude_pa,
        peak_indices=peaks,
        time_ms=time_ms,
        waveform_mv=np.mean(waveforms, axis=0),
    )