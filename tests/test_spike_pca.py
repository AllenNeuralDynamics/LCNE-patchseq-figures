import unittest

import numpy as np
import pandas as pd

from lcne_patchseq_figures.spike_pca import compute_spike_pc1, normalize_waveforms


class SpikePCATest(unittest.TestCase):
    def setUp(self):
        self.time_ms = np.arange(-5.0, 10.0, 0.02)

    def test_normalizes_using_only_legacy_window(self):
        first = np.linspace(-2, 3, len(self.time_ms))
        second = 10 + 2 * first
        frame = pd.DataFrame([first, second], index=["a", "b"], columns=self.time_ms)
        normalized = normalize_waveforms(frame)
        in_window = (self.time_ms >= -2) & (self.time_ms <= 4)

        np.testing.assert_allclose(normalized.to_numpy()[:, in_window].min(axis=1), 0)
        np.testing.assert_allclose(normalized.to_numpy()[:, in_window].max(axis=1), 1)

    def test_pc1_is_centered_and_has_loading_based_sign(self):
        peak = np.exp(-(self.time_ms / 0.8) ** 2)
        frame = pd.DataFrame(
            [0.8 * peak, peak, 1.3 * peak + 0.1 * self.time_ms],
            index=pd.Index(["a", "b", "c"], name="ephys_roi_id"),
            columns=self.time_ms,
        )

        pc1 = compute_spike_pc1(frame)

        self.assertAlmostEqual(pc1.mean(), 0.0)
        self.assertEqual(pc1.name, "spike_waveform_PC1")
        self.assertGreater(pc1.loc["c"], pc1.loc["a"])

    def test_rejects_constant_waveform(self):
        frame = pd.DataFrame(
            [np.ones(len(self.time_ms)), np.arange(len(self.time_ms))],
            index=["constant", "variable"],
            columns=self.time_ms,
        )
        with self.assertRaisesRegex(ValueError, "constant"):
            compute_spike_pc1(frame)


if __name__ == "__main__":
    unittest.main()