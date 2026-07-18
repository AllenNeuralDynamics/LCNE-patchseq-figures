"""Compute the publication spike-waveform PC1 from representative spikes."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from spike_waveforms import RepresentativeSpike

NORMALIZATION_WINDOW_MS = (-2.0, 4.0)
ANALYSIS_WINDOW_MS = (-3.0, 6.0)


def representative_waveform_frame(
    representatives: Mapping[str, RepresentativeSpike],
) -> pd.DataFrame:
    """Assemble representative waveforms with one shared millisecond time axis."""
    if not representatives:
        raise ValueError("No representative spike waveforms were provided")
    rows = []
    ephys_roi_ids = []
    reference_time = None
    for ephys_roi_id, representative in representatives.items():
        if reference_time is None:
            reference_time = representative.time_ms
        elif not np.array_equal(representative.time_ms, reference_time):
            raise ValueError(f"Spike time axis differs for {ephys_roi_id}")
        rows.append(representative.waveform_mv)
        ephys_roi_ids.append(str(ephys_roi_id))
    return pd.DataFrame(
        rows,
        index=pd.Index(ephys_roi_ids, name="ephys_roi_id"),
        columns=np.asarray(reference_time, dtype=float),
    )


def normalize_waveforms(
    waveforms: pd.DataFrame,
    window_ms: tuple[float, float] = NORMALIZATION_WINDOW_MS,
) -> pd.DataFrame:
    """Apply the legacy per-cell min-max normalization within a time window."""
    time_ms = np.asarray(waveforms.columns, dtype=float)
    in_window = (time_ms >= window_ms[0]) & (time_ms <= window_ms[1])
    if not in_window.any():
        raise ValueError(f"No waveform samples fall in normalization window {window_ms}")
    values = waveforms.to_numpy(dtype=float)
    reference = values[:, in_window]
    minimum = np.min(reference, axis=1, keepdims=True)
    span = np.ptp(reference, axis=1, keepdims=True)
    invalid = np.flatnonzero(~np.isfinite(span[:, 0]) | (span[:, 0] == 0))
    if len(invalid):
        ids = ", ".join(waveforms.index[invalid].astype(str))
        raise ValueError(f"Waveforms cannot be normalized: {ids}")
    return pd.DataFrame(
        (values - minimum) / span,
        index=waveforms.index,
        columns=waveforms.columns,
    )


def compute_spike_pc1(
    waveforms: pd.DataFrame,
    analysis_window_ms: tuple[float, float] = ANALYSIS_WINDOW_MS,
) -> pd.Series:
    """Return PCA1 scores with the same SVD sign convention as scikit-learn."""
    normalized = normalize_waveforms(waveforms)
    time_ms = np.asarray(normalized.columns, dtype=float)
    in_window = (time_ms >= analysis_window_ms[0]) & (time_ms <= analysis_window_ms[1])
    if not in_window.any():
        raise ValueError(f"No waveform samples fall in analysis window {analysis_window_ms}")
    values = normalized.to_numpy(dtype=float)[:, in_window]
    if not np.isfinite(values).all():
        raise ValueError("Normalized PCA input contains non-finite values")

    centered = values - values.mean(axis=0)
    left_vectors, singular_values, loadings = np.linalg.svd(centered, full_matrices=False)
    maximum_loading = np.argmax(np.abs(loadings), axis=1)
    signs = np.sign(loadings[np.arange(len(loadings)), maximum_loading])
    signs[signs == 0] = 1
    scores = left_vectors * signs * singular_values
    return pd.Series(scores[:, 0], index=waveforms.index, name="spike_waveform_PC1")