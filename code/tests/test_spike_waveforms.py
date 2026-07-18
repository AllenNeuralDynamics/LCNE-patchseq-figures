import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np

from spike_waveforms import (
    detect_efel_peak_indices,
    extract_representative_spike,
    infer_main_stimulus_pulse,
)


class SpikeWaveformsTest(unittest.TestCase):
    def test_detector_matches_efel_crossing_pair_algorithm(self):
        voltage = np.array([-20, -11, 5, 8, -12, -11, 4, 3, -20], dtype=float)
        np.testing.assert_array_equal(detect_efel_peak_indices(voltage), [3, 6])

    def test_main_pulse_excludes_short_test_pulse(self):
        stimulus = np.zeros(100)
        stimulus[5:10] = -40
        stimulus[25:85] = 20
        pulse = infer_main_stimulus_pulse(stimulus)
        self.assertEqual((pulse.start_index, pulse.stop_index), (25, 85))
        self.assertEqual(pulse.amplitude_pa, 20)

    def test_selects_lowest_amplitude_spiking_rheobase_and_averages_spikes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.nwb"
            with h5py.File(path, "w") as nwb:
                for sweep_number, amplitude, spike_positions in (
                    (1, 10, []),
                    (2, 20, [30_000, 40_000]),
                    (3, 30, [35_000]),
                ):
                    samples = 80_000
                    voltage = np.full(samples, -70.0)
                    for peak in spike_positions:
                        voltage[peak - 1 : peak + 2] = [-20.0, 25.0 + sweep_number, -20.0]
                    stimulus = np.zeros(samples)
                    stimulus[100:601] = -40
                    stimulus[10_000:60_000] = amplitude
                    self._add_sweep(nwb, sweep_number, voltage, stimulus)

            result = extract_representative_spike(path)

            self.assertEqual(result.sweep_number, 2)
            self.assertEqual(result.stimulus_amplitude_pa, 20)
            np.testing.assert_array_equal(result.peak_indices, [30_000, 40_000])
            self.assertEqual(len(result.waveform_mv), 750)
            self.assertEqual(result.waveform_mv[250], 27.0)

    @staticmethod
    def _add_sweep(nwb, sweep_number, voltage_mv, stimulus_pa):
        acquisition = nwb.create_group(f"acquisition/data_{sweep_number:05}_AD0")
        acquisition.attrs["neurodata_type"] = "CurrentClampSeries"
        acquisition.attrs["sweep_number"] = sweep_number
        acquisition.attrs["stimulus_description"] = "X3LP_Rheo_DA_0"
        voltage = acquisition.create_dataset("data", data=voltage_mv)
        voltage.attrs["unit"] = "volts"
        voltage.attrs["conversion"] = 0.001
        acquisition_time = acquisition.create_dataset("starting_time", data=[0.0])
        acquisition_time.attrs["rate"] = 50_000.0

        stimulus = nwb.create_group(f"stimulus/presentation/data_{sweep_number:05}_DA0")
        stimulus.attrs["stimulus_description"] = "X3LP_Rheo_DA_0"
        current = stimulus.create_dataset("data", data=stimulus_pa)
        current.attrs["unit"] = "amperes"
        current.attrs["conversion"] = 1e-12
        stimulus_time = stimulus.create_dataset("starting_time", data=[0.0])
        stimulus_time.attrs["rate"] = 50_000.0


if __name__ == "__main__":
    unittest.main()