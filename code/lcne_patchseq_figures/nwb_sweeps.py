"""Read raw current-clamp sweeps from AIBS patch-seq NWB files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import h5py
import numpy as np


@dataclass(frozen=True)
class CurrentClampSweep:
    """One converted current-clamp acquisition and its stimulus."""

    sweep_number: int
    stimulus_description: str
    sampling_rate_hz: float
    voltage_mv: np.ndarray
    stimulus_pa: np.ndarray


def _text(value) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


def _converted_data(dataset: h5py.Dataset, expected_unit: str, scale: float) -> np.ndarray:
    unit = _text(dataset.attrs.get("unit", ""))
    if unit != expected_unit:
        raise ValueError(f"Expected {expected_unit}, found {unit or 'no unit'} at {dataset.name}")
    conversion = float(dataset.attrs.get("conversion", 1.0))
    offset = float(dataset.attrs.get("offset", 0.0))
    return (np.asarray(dataset, dtype=float) * conversion + offset) * scale


def list_current_clamp_sweeps(path: Path) -> dict[int, str]:
    """Return sweep numbers and descriptions for current-clamp recordings."""
    sweeps = {}
    with h5py.File(path, "r") as nwb:
        for group in nwb["acquisition"].values():
            if _text(group.attrs.get("neurodata_type", "")) != "CurrentClampSeries":
                continue
            sweep_number = int(group.attrs["sweep_number"])
            sweeps[sweep_number] = _text(group.attrs.get("stimulus_description", ""))
    return sweeps


def load_current_clamp_sweep(path: Path, sweep_number: int) -> CurrentClampSweep:
    """Load and convert one paired acquisition/stimulus sweep."""
    acquisition_path = f"acquisition/data_{sweep_number:05}_AD0"
    stimulus_path = f"stimulus/presentation/data_{sweep_number:05}_DA0"
    with h5py.File(path, "r") as nwb:
        if acquisition_path not in nwb or stimulus_path not in nwb:
            raise KeyError(f"Sweep {sweep_number} is not present in {path}")
        acquisition = nwb[acquisition_path]
        stimulus = nwb[stimulus_path]
        acquisition_rate = float(acquisition["starting_time"].attrs["rate"])
        stimulus_rate = float(stimulus["starting_time"].attrs["rate"])
        if acquisition_rate != stimulus_rate:
            raise ValueError(
                f"Sweep {sweep_number} rates differ: {acquisition_rate} vs {stimulus_rate}"
            )
        voltage_mv = _converted_data(acquisition["data"], "volts", 1000.0)
        stimulus_pa = _converted_data(stimulus["data"], "amperes", 1e12)
        if voltage_mv.shape != stimulus_pa.shape:
            raise ValueError(f"Sweep {sweep_number} acquisition and stimulus lengths differ")
        return CurrentClampSweep(
            sweep_number=sweep_number,
            stimulus_description=_text(stimulus.attrs.get("stimulus_description", "")),
            sampling_rate_hz=acquisition_rate,
            voltage_mv=voltage_mv,
            stimulus_pa=stimulus_pa,
        )