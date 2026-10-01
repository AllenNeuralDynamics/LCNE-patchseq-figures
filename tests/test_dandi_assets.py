import unittest
from unittest import mock

from dandi_assets import load_assets, load_donors, open_nwb


class ResolveNWBAssetsTest(unittest.TestCase):
    def test_pinned_dandiset_resolves_all_publication_cells(self):
        resolved = load_assets()

        self.assertEqual(len(resolved), 96)
        self.assertEqual(sum(asset.size for asset in resolved.values()), 5_671_769_779)
        self.assertEqual(resolved["1388239233"].size, 62_569_344)
        self.assertEqual(
            resolved["1388239233"].get_raw_digest("dandi:sha2-256"),
            "55609608e1736f8f2f4e459663e83f3b01faf969cd20bdec0ee0e3929416b8fa",
        )

    def test_participants_give_donor_and_projection_target_per_cell(self):
        donors = load_donors(load_assets())

        self.assertEqual(len(donors), 96)
        self.assertEqual(
            donors["projection_target"].value_counts().to_dict(),
            {"Spinal cord": 54, "Cortex": 27, "Cerebellum": 15},
        )
        self.assertEqual(
            donors.groupby("projection_target")["Donor"].nunique().to_dict(),
            {"Spinal cord": 13, "Cortex": 8, "Cerebellum": 7},
        )


class OpenNWBTest(unittest.TestCase):
    def test_streams_asset_url_and_closes(self):
        asset = mock.Mock()
        with mock.patch("dandi_assets.remfile.File") as remote_file, mock.patch(
            "dandi_assets.remfile.DiskCache"
        ) as cache:
            with open_nwb(asset) as stream:
                remote_file.assert_called_once_with(
                    asset.get_content_url.return_value, disk_cache=cache.return_value
                )
                self.assertIs(stream, remote_file.return_value)
            stream.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()