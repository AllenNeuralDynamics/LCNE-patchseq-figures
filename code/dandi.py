"""Download the raw NWBs listed in the frozen DANDI manifest."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlretrieve

MANIFEST = Path(__file__).resolve().parent / "data" / "dandi_001893_manifest.csv"


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


def download_nwb(asset: DandiAsset, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / f"{asset.ephys_roi_id}.nwb"
    if destination.exists() and destination.stat().st_size == asset.size:
        return destination
    temporary = destination.with_suffix(".nwb.part")
    try:
        urlretrieve(asset.url, temporary)
        if temporary.stat().st_size != asset.size:
            raise IOError(f"Incomplete download for {asset.ephys_roi_id}")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination