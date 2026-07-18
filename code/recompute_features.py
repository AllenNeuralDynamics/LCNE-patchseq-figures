"""Orchestrate raw-DANDI spike waveform and PC1 recomputation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from pathlib import Path

import pandas as pd

from dandi_assets import DandiNWBAsset, download_nwb_asset, resolve_manifest_assets
from spike_pca import compute_spike_pc1, representative_waveform_frame
from spike_waveforms import RepresentativeSpike, extract_representative_spike

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecomputedFeatures:
    """Recomputed metadata and the intermediate artifacts used to produce it."""

    metadata: pd.DataFrame
    comparison: pd.DataFrame
    provenance: pd.DataFrame
    waveforms: pd.DataFrame


def recompute_spike_features(
    frame: pd.DataFrame,
    cache_dir: Path,
    *,
    resolve_assets: Callable = resolve_manifest_assets,
    download_asset: Callable = download_nwb_asset,
    extract_spike: Callable = extract_representative_spike,
) -> RecomputedFeatures:
    """Download raw NWBs and replace the publication PC1 with recomputed values."""
    ephys_roi_ids = frame["ephys_roi_id"].astype(str).tolist()
    assets: dict[str, DandiNWBAsset] = resolve_assets(ephys_roi_ids)
    representatives: dict[str, RepresentativeSpike] = {}
    provenance_rows = []

    for position, ephys_roi_id in enumerate(ephys_roi_ids, start=1):
        asset = assets[ephys_roi_id]
        LOGGER.info("Recomputing %s (%d/%d)", ephys_roi_id, position, len(ephys_roi_ids))
        nwb_path = download_asset(asset, cache_dir)
        representative = extract_spike(nwb_path)
        representatives[ephys_roi_id] = representative
        provenance_rows.append(
            {
                "ephys_roi_id": ephys_roi_id,
                "dandi_asset_id": asset.asset_id,
                "dandi_asset_path": asset.path,
                "dandi_asset_size_bytes": asset.size,
                "dandi_asset_sha256": asset.sha256,
                "selected_sweep_number": representative.sweep_number,
                "stimulus_amplitude_pa": representative.stimulus_amplitude_pa,
                "spike_count": len(representative.peak_indices),
            }
        )

    waveforms = representative_waveform_frame(representatives)
    pc1 = compute_spike_pc1(waveforms)
    original = frame.set_index("ephys_roi_id")["spike_waveform_PC1"].astype(float)
    comparison = pd.DataFrame(
        {
            "spike_waveform_PC1_frozen": original,
            "spike_waveform_PC1_recomputed": pc1,
        }
    )
    comparison["difference"] = (
        comparison["spike_waveform_PC1_recomputed"]
        - comparison["spike_waveform_PC1_frozen"]
    )
    comparison.index.name = "ephys_roi_id"

    metadata = frame.copy().set_index("ephys_roi_id")
    metadata["spike_waveform_PC1"] = pc1
    metadata = metadata.reset_index()
    provenance = pd.DataFrame(provenance_rows)
    return RecomputedFeatures(metadata, comparison, provenance, waveforms)


def write_recomputed_features(result: RecomputedFeatures, output_dir: Path) -> list[Path]:
    """Write recomputed metadata, discrepancy, provenance, and waveform tables."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        output_dir / "AIBS_spreadsheet_recomputed.csv",
        output_dir / "S14jk_spike_PC1_comparison.csv",
        output_dir / "S14jk_spike_recomputation_provenance.csv",
        output_dir / "S14jk_representative_spike_waveforms.csv",
    ]
    result.metadata.to_csv(paths[0], index=False)
    result.comparison.to_csv(paths[1])
    result.provenance.to_csv(paths[2], index=False)
    result.waveforms.to_csv(paths[3])
    return paths