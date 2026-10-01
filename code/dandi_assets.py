"""Resolve and open the raw NWBs in the pinned DANDI dandiset."""

from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator

import pandas as pd
import remfile
from dandi.dandiapi import BaseRemoteAsset, DandiAPIClient

DANDISET_ID = "001893"
DANDISET_VERSION = "0.260817.1647"
NWB_GLOB = "sourcedata/raw/*/*_icephys.nwb"
EPHYS_ROI_ID = re.compile(r"_ses-(\d+)_icephys\.nwb$")
CACHE_DIR = Path("/scratch/lcne-patchseq-nwb")


def load_assets() -> dict[str, BaseRemoteAsset]:
    """Return every raw NWB asset keyed by ephys_roi_id."""
    with DandiAPIClient() as client:
        dandiset = client.get_dandiset(DANDISET_ID, DANDISET_VERSION)
        return {
            EPHYS_ROI_ID.search(asset.path).group(1): asset
            for asset in dandiset.get_assets_by_glob(NWB_GLOB)
        }


def load_donors(assets: dict[str, BaseRemoteAsset]) -> pd.DataFrame:
    """Return Donor and projection_target per ephys_roi_id from participants.tsv."""
    with DandiAPIClient() as client:
        dandiset = client.get_dandiset(DANDISET_ID, DANDISET_VERSION)
        participants_url = dandiset.get_asset_by_path("participants.tsv").get_content_url(
            follow_redirects=1, strip_query=True
        )
    participants = pd.read_csv(participants_url, sep="\t", dtype=str).set_index("participants_id")
    subjects = [asset.path.split("/")[2] for asset in assets.values()]
    rows = participants.loc[subjects]
    return pd.DataFrame(
        {
            "ephys_roi_id": list(assets),
            "Donor": rows["donor_local_id"].to_numpy(),
            "projection_target": rows["injection_target_region"].to_numpy(),
        }
    )


@contextmanager
def open_nwb(asset: BaseRemoteAsset) -> Iterator[BinaryIO]:
    """Yield a seekable file-like object that range-reads the asset from S3; pass it to h5py.File."""
    url = asset.get_content_url(follow_redirects=1, strip_query=True)
    stream = remfile.File(url, disk_cache=remfile.DiskCache(str(CACHE_DIR)))
    try:
        yield stream
    finally:
        stream.close()