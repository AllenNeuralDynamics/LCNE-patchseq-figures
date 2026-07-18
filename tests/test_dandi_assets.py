import unittest
import csv
from io import BytesIO
import hashlib
from pathlib import Path
import tempfile

from lcne_patchseq_figures.dandi_assets import (
    DEFAULT_MANIFEST,
    DandiNWBAsset,
    download_nwb_asset,
    resolve_manifest_assets,
    resolve_nwb_assets,
)


class ResolveNWBAssetsTest(unittest.TestCase):
    def test_committed_manifest_pins_all_publication_cells(self):
        frozen_table = DEFAULT_MANIFEST.with_name("AIBS_spreadsheet_pub.csv")
        with frozen_table.open(newline="") as stream:
            ephys_roi_ids = [row["ephys_roi_id"] for row in csv.DictReader(stream)]
        resolved = resolve_manifest_assets(ephys_roi_ids, DEFAULT_MANIFEST)

        self.assertEqual(len(resolved), 96)
        self.assertEqual(sum(asset.size for asset in resolved.values()), 5_671_769_779)
        self.assertEqual(resolved["1388239233"].size, 62_569_344)
        self.assertEqual(
            resolved["1388239233"].sha256,
            "55609608e1736f8f2f4e459663e83f3b01faf969cd20bdec0ee0e3929416b8fa",
        )

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

    def test_download_verifies_and_reuses_cached_asset(self):
        content = b"example nwb bytes"
        digest = hashlib.sha256(content).hexdigest()
        calls = []

        def open_url(url, timeout):
            calls.append((url, timeout))
            return BytesIO(content)

        details = {
            "contentUrl": ["https://dandiarchive.s3.amazonaws.com/blobs/example"],
            "digest": {"dandi:sha2-256": digest},
        }
        asset = DandiNWBAsset("111", "asset-a", "sub-1_ses-111_icephys.nwb", len(content))
        with tempfile.TemporaryDirectory() as directory:
            path = download_nwb_asset(
                asset,
                Path(directory),
                get_json=lambda _url: details,
                open_url=open_url,
            )
            cached = download_nwb_asset(
                asset,
                Path(directory),
                get_json=lambda _url: details,
                open_url=open_url,
            )

            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(cached, path)
            self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()