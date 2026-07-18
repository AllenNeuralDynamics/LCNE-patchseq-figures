import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np

from lcne_patchseq_figures.example_traces import (
    EXAMPLE_CELLS,
    example_trace_frame,
    extract_example_traces,
)


class ExampleTracesTest(unittest.TestCase):
    def test_selects_legacy_sweep_types_and_amplitudes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.nwb"
            with h5py.File(path, "w") as nwb:
                self._add_sweep(nwb, 1, "X4PS_SupraThresh_DA_0", 40, [30_000])
                self._add_sweep(nwb, 2, "X4PS_SupraThresh_DA_0", 30, [30_000])
                self._add_sweep(nwb, 3, "X3LP_Rheo_DA_0", 20, [30_000])
                self._add_sweep(nwb, 4, "X3LP_Rheo_DA_0", 10, [])
                self._add_sweep(nwb, 5, "X1PS_SubThresh_DA_0", -50, [])
                self._add_sweep(nwb, 6, "X1PS_SubThresh_DA_0", -100, [])

            traces = extract_example_traces(path)

            self.assertEqual(traces["supra"].sweep_number, 2)
            self.assertEqual(traces["rheo"].sweep_number, 3)
            self.assertEqual(traces["hyperpol"].sweep_number, 6)
            self.assertEqual(len(traces["rheo"].voltage_mv), 85_000)
            self.assertEqual(traces["rheo"].time_ms[0], 0.0)

            trace_sets = {cell.ephys_roi_id: traces for cell in EXAMPLE_CELLS}
            table = example_trace_frame(trace_sets)
            self.assertEqual(len(table), 9 * 85_000)
            self.assertEqual(set(table["sweep_type"]), {"hyperpol", "rheo", "supra"})

    @staticmethod
    def _add_sweep(nwb, sweep_number, description, amplitude, spike_positions):
        samples = 100_000
        voltage_mv = np.full(samples, -70.0)
        for peak in spike_positions:
            voltage_mv[peak - 1 : peak + 2] = [-20.0, 30.0, -20.0]
        stimulus_pa = np.zeros(samples)
        stimulus_pa[5_000:5_501] = -40
        stimulus_pa[20_000:70_000] = amplitude

        acquisition = nwb.create_group(f"acquisition/data_{sweep_number:05}_AD0")
        acquisition.attrs["neurodata_type"] = "CurrentClampSeries"
        acquisition.attrs["sweep_number"] = sweep_number
        acquisition.attrs["stimulus_description"] = description
        voltage = acquisition.create_dataset("data", data=voltage_mv)
        voltage.attrs["unit"] = "volts"
        voltage.attrs["conversion"] = 0.001
        acquisition_time = acquisition.create_dataset("starting_time", data=[0.0])
        acquisition_time.attrs["rate"] = 50_000.0

        stimulus = nwb.create_group(f"stimulus/presentation/data_{sweep_number:05}_DA0")
        stimulus.attrs["stimulus_description"] = description
        current = stimulus.create_dataset("data", data=stimulus_pa)
        current.attrs["unit"] = "amperes"
        current.attrs["conversion"] = 1e-12
        stimulus_time = stimulus.create_dataset("starting_time", data=[0.0])
        stimulus_time.attrs["rate"] = 50_000.0


if __name__ == "__main__":
    unittest.main()