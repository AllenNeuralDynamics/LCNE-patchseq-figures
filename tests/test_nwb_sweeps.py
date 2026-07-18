import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np

from lcne_patchseq_figures.nwb_sweeps import list_current_clamp_sweeps, load_current_clamp_sweep


class NWBSweepsTest(unittest.TestCase):
    def _create_nwb(self, path: Path):
        with h5py.File(path, "w") as nwb:
            acquisition = nwb.create_group("acquisition/data_00007_AD0")
            acquisition.attrs["neurodata_type"] = "CurrentClampSeries"
            acquisition.attrs["sweep_number"] = 7
            acquisition.attrs["stimulus_description"] = "X3LP_Rheo_DA_0"
            voltage = acquisition.create_dataset("data", data=[-70.0, 20.0])
            voltage.attrs["unit"] = "volts"
            voltage.attrs["conversion"] = 0.001
            acquisition_time = acquisition.create_dataset("starting_time", data=[0.0])
            acquisition_time.attrs["rate"] = 50000.0

            stimulus = nwb.create_group("stimulus/presentation/data_00007_DA0")
            stimulus.attrs["stimulus_description"] = "X3LP_Rheo_DA_0"
            current = stimulus.create_dataset("data", data=[0.0, 40.0])
            current.attrs["unit"] = "amperes"
            current.attrs["conversion"] = 1e-12
            stimulus_time = stimulus.create_dataset("starting_time", data=[0.0])
            stimulus_time.attrs["rate"] = 50000.0

    def test_lists_and_converts_current_clamp_sweep(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.nwb"
            self._create_nwb(path)

            self.assertEqual(list_current_clamp_sweeps(path), {7: "X3LP_Rheo_DA_0"})
            sweep = load_current_clamp_sweep(path, 7)

            self.assertEqual(sweep.sweep_number, 7)
            self.assertEqual(sweep.stimulus_description, "X3LP_Rheo_DA_0")
            self.assertEqual(sweep.sampling_rate_hz, 50000.0)
            np.testing.assert_allclose(sweep.voltage_mv, [-70.0, 20.0])
            np.testing.assert_allclose(sweep.stimulus_pa, [0.0, 40.0])


if __name__ == "__main__":
    unittest.main()