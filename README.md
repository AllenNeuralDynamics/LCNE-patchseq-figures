# LCNE patch-seq figures

This repository is the GitHub source for a Code Ocean capsule that reproduces
supplementary figure S14j/k from the publication
[Topographic structure and function of locus coeruleus norepinephrine neurons](https://doi.org/10.64898/2026.04.10.717727)
(Su et al., 2026). The analysis downloads intracellular electrophysiology
recordings from DANDI, recomputes the action-potential waveform PC1, restores
the example current-clamp traces in panel j, and writes the figure and all
supporting data to `/results`.

## Resources

| Resource | Description |
| --- | --- |
| [Figures repository](https://github.com/AllenNeuralDynamics/LCNE-patchseq-figures) | This capsule's code, environment, metadata, and frozen inputs |
| [Code Ocean capsule](https://codeocean.allenneuraldynamics.org/capsule/9190472/tree) | Reproducible environment and run interface for figure S14j/k |
| [DANDIset 001893](https://dandiarchive.org/dandiset/001893/) | Raw intracellular current-clamp NWB recordings |
| [NeMO collection](https://assets.nemoarchive.org/col-p9d5w39) | Associated publication data collection |
| [Analysis repository](https://github.com/AllenNeuralDynamics/LCNE-patchseq-analysis) | Original multimodal analysis and metadata-export code |

## Inputs

### Intracellular electrophysiology

The primary input is 96 NWB files from DANDIset 001893. Each file contains
intracellular current-clamp voltage recordings and injected-current stimuli for
one `ephys_roi_id`. Recordings are sampled at 50 kHz. The exact DANDI asset ID,
path, immutable blob URL, size, and SHA-256 value for every cell are frozen in
[`code/data/dandi_001893_manifest.csv`](code/data/dandi_001893_manifest.csv).
The current DANDIset version is a draft; the committed manifest fixes the input
assets used by this capsule.

[`code/dandi.py`](code/dandi.py) reads the manifest and downloads or reuses the
NWB files in `/scratch/lcne-patchseq-nwb`. [`code/ephys.py`](code/ephys.py)
loads the current-clamp acquisition and stimulus arrays with `h5py` and applies
their NWB unit conversions.

### Cell metadata

[`code/data/LCNE_patchseq_S14_cell_table.csv`](code/data/LCNE_patchseq_S14_cell_table.csv)
contains one row per publication cell with its donor, projection target,
slicing plane, identifiers, membrane time constant, and S14j example-cell flag.
It deliberately does **not** contain `spike_waveform_PC1`; every run recomputes
that column from the raw NWBs. The table was exported from the analysis behind
the publication in
[LCNE-patchseq-analysis](https://github.com/AllenNeuralDynamics/LCNE-patchseq-analysis).

`membrane_time_constant_ms` is a frozen intermediate value from the original
IPFX analysis (`ipfx_tau` converted from seconds to milliseconds), rather than
being recomputed by this capsule. It is unavailable for 14 of the 96 cells;
those cells are omitted only from membrane-time-constant analyses and remain in
the spike-waveform analysis.

## Analysis

[`code/generate_S14jk.py`](code/generate_S14jk.py) is the top-level workflow.
It processes cells concurrently and performs the following steps:

1. **Representative spike waveform.**
	 [`extract_representative_spike`](code/spikes.py) examines the long-square
	 rheobase protocols (`X3LP_Rheo_DA_0` and `X5LP_Rheo_DA_0`) and selects the
	 lowest absolute stimulus amplitude that evokes at least one spike. Spike
	 peaks are detected with the legacy eFEL-compatible algorithm: interpolate at
	 0.02 ms, pair strict upward and downward crossings of -10 mV, and select the
	 voltage maximum between each pair. Raw waveforms from -5 to 10 ms around all
	 detected peaks in the selected sweep are averaged for each cell.

2. **Spike-waveform PC1.**
	 [`compute_pc1`](code/spikes.py) min-max normalizes each representative
	 waveform using the -2 to 4 ms window, restricts the PCA input to -3 to 6 ms,
	 mean-centers the complete 96-cell matrix, and calculates PC1 with NumPy SVD.
	 The newly computed `spike_waveform_PC1` is added to the output cell table and
	 is used for every downstream S14k file and plot.

3. **S14j example traces.**
	 [`extract_example_traces`](code/example_traces.py) reconstructs the published
	 Isocortex (`1388239233`), Cerebellum (`1426757704`), and Spinal cord
	 (`1410640556`) examples. For each cell it selects the minimum-amplitude
	 spiking suprathreshold and rheobase long-square sweeps and the
	 maximum-amplitude hyperpolarizing subthreshold sweep.

4. **Projection-target statistics.**
	 [`write_projection_statistics`](code/generate_S14jk.py) recomputes the four
	 manuscript contrasts for spike PC1 and membrane time constant. It uses the
	 original source-code method: two-sided Welch independent-samples t-tests
	 (`scipy.stats.ttest_ind(..., equal_var=False)`) at the cell level.

## Reproducible run

In the [Code Ocean capsule](https://codeocean.allenneuraldynamics.org/capsule/9190472/tree),
**Reproducible Run** executes [`code/run`](code/run). The run downloads or
reuses all 96 NWBs, computes cells in parallel, and writes to `/results`. In the
Reproducible Run arguments field, use `--workers 4` to choose four worker
processes. The default is the smaller of eight workers or the available CPU
count; choosing more workers than available CPUs is not useful.

The same command can be run from the repository root:

```bash
./code/run --workers 4
```

The Python entry point additionally accepts custom paths:

```bash
python code/generate_S14jk.py \
		--input code/data/LCNE_patchseq_S14_cell_table.csv \
		--output-dir results \
		--cache-dir /scratch/lcne-patchseq-nwb \
		--workers 4
```

The first run downloads approximately 5.67 GB. Later runs reuse NWBs whose
cached file size matches the frozen manifest.

## Outputs

Every non-cache output is written to `/results`:

| File | Description |
| --- | --- |
| `S14jk.png`, `S14jk.svg` | Combined supplementary figure S14j/k |
| `LCNE_patchseq_S14_cell_table.csv` | Input cell metadata plus the newly computed `spike_waveform_PC1` |
| `S14j_example_traces.csv` | Long-form time and voltage data for the nine example traces in panel j |
| `S14jk_PC1_raw.csv` | Per-cell PC1 values used in panel k |
| `S14jk_PC1_cumulative.csv` | Sorted PC1 values and cumulative fractions by projection target |
| `S14jk_membrane_time_constant_raw.csv` | Per-cell non-missing membrane time constants used in panel k |
| `S14jk_membrane_time_constant_cumulative.csv` | Sorted time constants and cumulative fractions by projection target |
| `S14jk_representative_spike_waveforms.csv` | The 96 peak-aligned, averaged waveforms used to fit PCA |
| `S14jk_spike_recomputation_provenance.csv` | DANDI asset, selected sweep, stimulus amplitude, and spike count for every cell |
| `S14_projection_target_statistics.json` | Group summaries and exact Welch test statistics, degrees of freedom, p-values, and manuscript thresholds |

## Tests and environment

All direct third-party dependencies are pinned in
[`environment/Dockerfile`](environment/Dockerfile). Run the focused tests with:

```bash
PYTHONPATH=code python -m unittest discover -s tests -v
```

## Repository layout

- `code/`: capsule entry point and analysis helpers
- `code/data/`: frozen cell metadata and DANDI asset manifest
- `environment/`: pinned Code Ocean container definition
- `metadata/`: capsule name, description, and author
- `tests/`: focused unit tests for manifest loading, NWB conversion, spike
	extraction, PCA, S14j sweep selection, figure exports, and statistics
- `LICENSE`: MIT license
