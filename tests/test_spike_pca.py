import unittest

import numpy as np
import pandas as pd

from spikes import compute_pc1


class SpikePCATest(unittest.TestCase):
    def setUp(self):
        self.time_ms = np.arange(-5.0, 10.0, 0.02)

    def test_pc1_is_centered_and_has_loading_based_sign(self):
        peak = np.exp(-(self.time_ms / 0.8) ** 2)
        frame = pd.DataFrame(
            [0.8 * peak, peak, 1.3 * peak + 0.1 * self.time_ms],
            index=pd.Index(["a", "b", "c"], name="ephys_roi_id"),
            columns=self.time_ms,
        )

        pc1 = compute_pc1(frame)

        self.assertAlmostEqual(pc1.mean(), 0.0)
        self.assertEqual(pc1.name, "spike_waveform_PC1")
        self.assertGreater(pc1.loc["c"], pc1.loc["a"])

if __name__ == "__main__":
    unittest.main()