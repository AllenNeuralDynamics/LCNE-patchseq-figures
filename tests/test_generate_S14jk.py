import tempfile
import unittest
from pathlib import Path

import matplotlib.image as mpimg
import numpy as np
import pandas as pd

from generate_S14jk import (
    DEFAULT_INPUT,
    generate_figure,
    load_frozen_table,
)


class GenerateS14Test(unittest.TestCase):
    def test_frozen_table_and_outputs(self):
        frame = load_frozen_table(DEFAULT_INPUT)

        self.assertEqual(len(frame), 96)
        self.assertEqual(
            frame["projection_target"].value_counts().to_dict(),
            {"Spinal cord": 54, "Cortex": 27, "Cerebellum": 15},
        )
        self.assertNotIn("spike_waveform_PC1", frame.columns)
        frame["spike_waveform_PC1"] = np.linspace(-2, 2, len(frame))

        with tempfile.TemporaryDirectory() as directory:
            trace = type("Trace", (), {"time_ms": np.arange(10), "voltage_mv": np.arange(10)})
            traces = {
                ephys_roi_id: {"hyperpol": trace, "rheo": trace, "supra": trace}
                for ephys_roi_id in ("1388239233", "1426757704", "1410640556")
            }
            outputs = generate_figure(frame, Path(directory), traces)
            self.assertEqual(len(outputs), 6)
            self.assertTrue(all(path.exists() and path.stat().st_size > 0 for path in outputs))
            self.assertEqual(mpimg.imread(Path(directory) / "S14jk.png").shape[:2], (1350, 4800))

            pc1 = pd.read_csv(Path(directory) / "S14jk_PC1_cumulative.csv")
            endpoints = pc1.groupby("projection_target")["cumulative_fraction"].max()
            self.assertTrue((endpoints == 1.0).all())

    def test_missing_required_column_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            pd.DataFrame({"ephys_roi_id": [1]}).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "Missing required columns"):
                load_frozen_table(path)


if __name__ == "__main__":
    unittest.main()