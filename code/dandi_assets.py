"""Resolve LC-NE patch-seq NWB assets from the DANDI API."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import json
from pathlib import Path
import re
from typing import Callable, Iterable
from urllib.request import urlopen

DANDI_API = "https://api.dandiarchive.org/api"
DANDISET_ID = "001893"
DANDI_VERSION = "draft"
DEFAULT_MANIFEST = Path(__file__).resolve().with_name("dandi_001893_manifest.csv")

ROI_ID_PATTERN = re.compile(r"_ses-(\d+)_icephys\.nwb$")


@dataclass(frozen=True)
class DandiNWBAsset:
    """The DANDI identity and location of one cell's raw NWB file."""

    ephys_roi_id: str
    asset_id: str
    path: str
    size: int
    sha256: str | None = None
    content_url: str | None = None


def _get_json(url: str) -> dict:
    with urlopen(url, timeout=120) as response:
        return json.load(response)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def resolve_manifest_assets(
    ephys_roi_ids: Iterable[str],
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, DandiNWBAsset]:
    """Resolve requested ROI IDs from the committed immutable asset manifest."""
    requested = {str(ephys_roi_id) for ephys_roi_id in ephys_roi_ids}
    matches: dict[str, list[DandiNWBAsset]] = {ephys_roi_id: [] for ephys_roi_id in requested}
    with manifest_path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            ephys_roi_id = row["ephys_roi_id"]
            if ephys_roi_id not in requested:
                continue
            matches[ephys_roi_id].append(
                DandiNWBAsset(
                    ephys_roi_id=ephys_roi_id,
                    asset_id=row["asset_id"],
                    path=row["path"],
                    size=int(row["size"]),
                    sha256=row["sha256"],
                    content_url=row["content_url"],
                )
            )

    missing = sorted(ephys_roi_id for ephys_roi_id, assets in matches.items() if not assets)
    ambiguous = sorted(ephys_roi_id for ephys_roi_id, assets in matches.items() if len(assets) > 1)
    if missing or ambiguous:
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if ambiguous:
            details.append(f"ambiguous: {', '.join(ambiguous)}")
        raise ValueError("Could not uniquely resolve manifest NWBs (" + "; ".join(details) + ")")
    return {ephys_roi_id: assets[0] for ephys_roi_id, assets in matches.items()}


def download_nwb_asset(
    asset: DandiNWBAsset,
    cache_dir: Path,
    *,
    get_json: Callable[[str], dict] = _get_json,
    open_url=urlopen,
) -> Path:
    """Download an NWB to a cache and verify its DANDI SHA-256 digest."""
    details = None
    expected_digest = asset.sha256
    download_url = asset.content_url
    if not expected_digest or not download_url:
        details = get_json(f"{DANDI_API}/assets/{asset.asset_id}/")
    if not expected_digest:
        expected_digest = details.get("digest", {}).get("dandi:sha2-256")
    if not expected_digest:
        raise ValueError(f"DANDI asset has no SHA-256 digest: {asset.asset_id}")

    if not download_url:
        content_urls = details.get("contentUrl", [])
        download_url = next(
            (url for url in content_urls if "dandiarchive.s3.amazonaws.com" in url),
            content_urls[0] if content_urls else None,
        )
    if not download_url:
        raise ValueError(f"DANDI asset has no content URL: {asset.asset_id}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / f"{asset.ephys_roi_id}.nwb"
    if destination.exists() and _sha256(destination) == expected_digest:
        return destination

    temporary = destination.with_suffix(".nwb.part")
    try:
        with open_url(download_url, timeout=300) as response, temporary.open("wb") as stream:
            while block := response.read(1024 * 1024):
                stream.write(block)
        actual_digest = _sha256(temporary)
        if actual_digest != expected_digest:
            raise ValueError(
                f"SHA-256 mismatch for {asset.ephys_roi_id}: "
                f"expected {expected_digest}, got {actual_digest}"
            )
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination