import unittest

from dandi_assets import DandiNWBAsset, resolve_nwb_assets


class ResolveNWBAssetsTest(unittest.TestCase):
    def test_resolves_requested_ids_across_pages(self):
        pages = {
            "first": {
                "results": [
                    {
                        "asset_id": "asset-a",
                        "path": "sourcedata/raw/sub-1/sub-1_ses-111_icephys.nwb",
                        "size": 10,
                    },
                    {"asset_id": "other", "path": "README.md", "size": 2},
                ],
                "next": "second",
            },
            "second": {
                "results": [
                    {
                        "identifier": "asset-b",
                        "path": "sourcedata/raw/sub-2/sub-2_ses-222_icephys.nwb",
                        "size": 20,
                    }
                ],
                "next": None,
            },
        }

        def get_json(url):
            return pages["first" if "dandisets/" in url else url]

        resolved = resolve_nwb_assets([111, "222"], get_json=get_json)

        self.assertEqual(
            resolved,
            {
                "111": DandiNWBAsset(
                    "111", "asset-a", "sourcedata/raw/sub-1/sub-1_ses-111_icephys.nwb", 10
                ),
                "222": DandiNWBAsset(
                    "222", "asset-b", "sourcedata/raw/sub-2/sub-2_ses-222_icephys.nwb", 20
                ),
            },
        )

    def test_rejects_missing_and_ambiguous_ids(self):
        page = {
            "results": [
                {
                    "asset_id": "asset-a",
                    "path": "sourcedata/raw/sub-1/sub-1_ses-111_icephys.nwb",
                    "size": 10,
                },
                {
                    "asset_id": "asset-b",
                    "path": "other/sub-2_ses-111_icephys.nwb",
                    "size": 20,
                },
            ],
            "next": None,
        }

        with self.assertRaisesRegex(ValueError, r"missing: 222; ambiguous: 111"):
            resolve_nwb_assets(["111", "222"], get_json=lambda _url: page)


if __name__ == "__main__":
    unittest.main()