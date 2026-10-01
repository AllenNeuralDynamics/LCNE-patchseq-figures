"""Open the raw NWBs listed in the frozen DANDI manifest."""

from __future__ import annotations

import csv
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator

import remfile

MANIFEST = Path(__file__).resolve().parent / "data" / "dandi_001893_manifest.csv"
CACHE_DIR = Path("/scratch/lcne-patchseq-nwb")


@dataclass(frozen=True)
class DandiAsset:

    ephys_roi_id: str
    asset_id: str
    path: str
    size: int
    sha256: str
    url: str


def load_assets(ephys_roi_ids, manifest: Path = MANIFEST) -> dict[str, DandiAsset]:
    with manifest.open(newline="") as stream:
        assets = {
            row["ephys_roi_id"]: DandiAsset(
                row["ephys_roi_id"],
                row["asset_id"],
                row["path"],
                int(row["size"]),
                row["sha256"],
                row["content_url"],
            )
            for row in csv.DictReader(stream)
        }
    return {str(ephys_roi_id): assets[str(ephys_roi_id)] for ephys_roi_id in ephys_roi_ids}


@contextmanager
def open_nwb(asset: DandiAsset) -> Iterator[BinaryIO]:
    """Yield a seekable file-like object that range-reads the asset from S3; pass it to h5py.File."""
    stream = remfile.File(asset.url, disk_cache=remfile.DiskCache(str(CACHE_DIR)))
    try:
        yield stream
    finally:
        stream.close()