"""Resolve and open the raw NWBs in the pinned DANDI dandiset."""

from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator

import remfile
from dandi.dandiapi import BaseRemoteAsset, DandiAPIClient

DANDISET_ID = "001893"
DANDISET_VERSION = "0.260817.1647"
NWB_GLOB = "sourcedata/raw/*/*_icephys.nwb"
EPHYS_ROI_ID = re.compile(r"_ses-(\d+)_icephys\.nwb$")
CACHE_DIR = Path("/scratch/lcne-patchseq-nwb")


def load_assets(ephys_roi_ids) -> dict[str, BaseRemoteAsset]:
    wanted = {str(ephys_roi_id) for ephys_roi_id in ephys_roi_ids}
    assets = {}
    with DandiAPIClient() as client:
        dandiset = client.get_dandiset(DANDISET_ID, DANDISET_VERSION)
        for asset in dandiset.get_assets_by_glob(NWB_GLOB):
            ephys_roi_id = EPHYS_ROI_ID.search(asset.path).group(1)
            if ephys_roi_id in wanted:
                assets[ephys_roi_id] = asset
    missing = sorted(wanted - assets.keys())
    if missing:
        raise KeyError(f"No NWB asset in {DANDISET_ID}/{DANDISET_VERSION} for: {', '.join(missing)}")
    return {str(ephys_roi_id): assets[str(ephys_roi_id)] for ephys_roi_id in ephys_roi_ids}


@contextmanager
def open_nwb(asset: BaseRemoteAsset) -> Iterator[BinaryIO]:
    """Yield a seekable file-like object that range-reads the asset from S3; pass it to h5py.File."""
    url = asset.get_content_url(follow_redirects=1, strip_query=True)
    stream = remfile.File(url, disk_cache=remfile.DiskCache(str(CACHE_DIR)))
    try:
        yield stream
    finally:
        stream.close()