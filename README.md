# LCNE patch-seq figures

This GitHub-backed Code Ocean capsule reproduces supplementary figure S14j/k.
The frozen table in `code/data/` contains publication metadata but no spike PC1
values. Every run downloads the pinned raw NWBs from DANDI, recomputes the
spike-waveform matrix and PC1, and reconstructs the S14j example traces.

## Reproducible run

In Code Ocean, **Reproducible Run** executes `code/run` and writes the figure,
SVG, and four underlying-data CSV files to `/results`.

The run downloads 96 raw NWB files from DANDI dandiset
[001893](https://dandiarchive.org/dandiset/001893/) and processes cells in
parallel. Set `--workers` when running the Python script to override the default
of up to eight worker processes.

The input metadata has no `spike_waveform_PC1` column. The output
`/results/LCNE_patchseq_S14_cell_table.csv` adds that newly computed column while
retaining all input metadata columns.

The run also writes selected sweep and DANDI asset provenance, representative
spike waveforms, and the nine raw traces underlying S14j to `/results`.
Because dandiset `001893` currently has only a draft version, the repository
pins every input asset, immutable blob URL, and SHA-256 in the committed
`dandi_001893_manifest.csv` resource.

To reproduce the same run from the repository root:

```bash
./code/run
```

To run directly:

```bash
python code/generate_S14jk.py
```

By default, the command reads the bundled CSV and writes PNG, SVG, and four
underlying-data CSV files to `results/`. Paths can be overridden:

```bash
python code/generate_S14jk.py --input path/to/LCNE_patchseq_S14_cell_table.csv --output-dir path/to/results
```

The frozen table was exported from the analysis underlying the LCNE patch-seq
publication in
[AllenNeuralDynamics/LCNE-patchseq-analysis](https://github.com/AllenNeuralDynamics/LCNE-patchseq-analysis).

## Repository layout

- `code/run`: Code Ocean entry point
- `code/generate_S14jk.py`: figure generation and recomputation entry point
- `code/data/`: frozen publication table and DANDI asset manifest
- `code/*.py`: small helpers for DANDI, NWB, spikes, and example traces
- `tests/`: unit tests
- `environment/`: pinned Code Ocean container definition
- `metadata/`: capsule name, description, and author metadata
