import csv
import unittest

from dandi import MANIFEST, load_assets


class ResolveNWBAssetsTest(unittest.TestCase):
    def test_committed_manifest_pins_all_publication_cells(self):
        frozen_table = MANIFEST.with_name("LCNE_patchseq_S14_cell_table.csv")
        with frozen_table.open(newline="") as stream:
            ephys_roi_ids = [row["ephys_roi_id"] for row in csv.DictReader(stream)]
        resolved = load_assets(ephys_roi_ids)

        self.assertEqual(len(resolved), 96)
        self.assertEqual(sum(asset.size for asset in resolved.values()), 5_671_769_779)
        self.assertEqual(resolved["1388239233"].size, 62_569_344)
        self.assertEqual(
            resolved["1388239233"].sha256,
            "55609608e1736f8f2f4e459663e83f3b01faf969cd20bdec0ee0e3929416b8fa",
        )


if __name__ == "__main__":
    unittest.main()