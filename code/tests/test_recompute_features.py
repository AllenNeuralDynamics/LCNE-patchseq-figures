import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from dandi_assets import DandiNWBAsset
from recompute_features import recompute_spike_features, write_recomputed_features
from spike_waveforms import RepresentativeSpike


class RecomputeFeaturesTest(unittest.TestCase):
    def test_recomputes_pc1_and_writes_audit_tables(self):
        frame = pd.DataFrame(
            {
                "ephys_roi_id": ["111", "222", "333"],
                "spike_waveform_PC1": [10.0, 20.0, 30.0],
            }
        )
        time_ms = np.arange(-5.0, 10.0, 0.02)
        waveforms = {
            "111": np.exp(-(time_ms / 0.7) ** 2),
            "222": np.exp(-(time_ms / 1.0) ** 2),
            "333": np.exp(-(time_ms / 1.4) ** 2),
        }

        def resolve_assets(ephys_roi_ids):
            return {
                ephys_roi_id: DandiNWBAsset(
                    ephys_roi_id, f"asset-{ephys_roi_id}", f"ses-{ephys_roi_id}.nwb", 100
                )
                for ephys_roi_id in ephys_roi_ids
            }

        def download_asset(asset, cache_dir):
            return cache_dir / f"{asset.ephys_roi_id}.nwb"

        def extract_spike(path):
            ephys_roi_id = path.stem
            return RepresentativeSpike(
                sweep_number=7,
                stimulus_amplitude_pa=20.0,
                peak_indices=np.array([100, 200]),
                time_ms=time_ms,
                waveform_mv=waveforms[ephys_roi_id],
            )

        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "results"
            result = recompute_spike_features(
                frame,
                Path(directory) / "cache",
                resolve_assets=resolve_assets,
                download_asset=download_asset,
                extract_spike=extract_spike,
            )
            outputs = write_recomputed_features(result, output_dir)

            self.assertEqual(len(result.metadata), 3)
            self.assertAlmostEqual(result.metadata["spike_waveform_PC1"].mean(), 0.0)
            self.assertEqual(result.provenance["spike_count"].tolist(), [2, 2, 2])
            self.assertTrue(all(path.exists() and path.stat().st_size > 0 for path in outputs))


if __name__ == "__main__":
    unittest.main()