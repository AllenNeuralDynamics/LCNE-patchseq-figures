import csv
import unittest
from unittest import mock

from dandi import MANIFEST, load_assets, open_nwb


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


class OpenNWBTest(unittest.TestCase):
    def test_streams_asset_url_and_closes(self):
        asset = load_assets(["1388239233"])["1388239233"]
        with mock.patch("dandi.remfile.File") as remote_file, mock.patch("dandi.remfile.DiskCache") as cache:
            with open_nwb(asset) as stream:
                remote_file.assert_called_once_with(asset.url, disk_cache=cache.return_value)
                self.assertIs(stream, remote_file.return_value)
            stream.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()