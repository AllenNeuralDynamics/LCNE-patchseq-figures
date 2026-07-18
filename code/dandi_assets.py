"""Resolve LC-NE patch-seq NWB assets from the DANDI API."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Callable, Iterable
from urllib.request import urlopen

DANDI_API = "https://api.dandiarchive.org/api"
DANDISET_ID = "001893"
DANDI_VERSION = "draft"

ROI_ID_PATTERN = re.compile(r"_ses-(\d+)_icephys\.nwb$")


@dataclass(frozen=True)
class DandiNWBAsset:
    """The DANDI identity and location of one cell's raw NWB file."""

    ephys_roi_id: str
    asset_id: str
    path: str
    size: int


def _get_json(url: str) -> dict:
    with urlopen(url, timeout=120) as response:
        return json.load(response)


def resolve_nwb_assets(
    ephys_roi_ids: Iterable[str],
    *,
    get_json: Callable[[str], dict] = _get_json,
    dandiset_id: str = DANDISET_ID,
    version: str = DANDI_VERSION,
) -> dict[str, DandiNWBAsset]:
    """Resolve each requested ROI ID to exactly one NWB in a Dandiset version."""
    requested = {str(ephys_roi_id) for ephys_roi_id in ephys_roi_ids}
    matches: dict[str, list[DandiNWBAsset]] = {ephys_roi_id: [] for ephys_roi_id in requested}
    url = (
        f"{DANDI_API}/dandisets/{dandiset_id}/versions/{version}/assets/"
        "?page_size=1000&order=path"
    )

    while url:
        page = get_json(url)
        for item in page.get("results", []):
            path = item.get("path", "")
            match = ROI_ID_PATTERN.search(path)
            if match is None or match.group(1) not in requested:
                continue
            ephys_roi_id = match.group(1)
            asset_id = item.get("asset_id") or item.get("identifier")
            if not asset_id:
                raise ValueError(f"DANDI asset has no identifier: {path}")
            matches[ephys_roi_id].append(
                DandiNWBAsset(
                    ephys_roi_id=ephys_roi_id,
                    asset_id=str(asset_id),
                    path=path,
                    size=int(item.get("size", 0)),
                )
            )
        url = page.get("next")

    missing = sorted(ephys_roi_id for ephys_roi_id, assets in matches.items() if not assets)
    ambiguous = sorted(ephys_roi_id for ephys_roi_id, assets in matches.items() if len(assets) > 1)
    if missing or ambiguous:
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if ambiguous:
            details.append(f"ambiguous: {', '.join(ambiguous)}")
        raise ValueError("Could not uniquely resolve DANDI NWB assets (" + "; ".join(details) + ")")

    return {ephys_roi_id: assets[0] for ephys_roi_id, assets in matches.items()}