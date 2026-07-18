# LCNE patch-seq figures

This GitHub-backed Code Ocean capsule reproduces supplementary figure S14k
directly from the frozen `code/AIBS_spreadsheet_pub.csv` publication table. It
has no dependency on the LCNE analysis package, S3, eFEL, or an attached
`/data` dataset.

The frozen table contains the PC1 and membrane-time-constant values needed for
S14k, but not the raw voltage arrays used by S14j. The combined output therefore
shows a labeled placeholder for panel j. A later revision will add a small path
for obtaining those traces from NWB files on DANDI.

## Reproducible run

In Code Ocean, **Reproducible Run** executes `code/run` and writes the figure,
SVG, and four underlying-data CSV files to `/results`.

Set the Reproducible Run argument to `1` to recompute spike waveform PC1 from
the 96 raw NWB files in DANDI dandiset
[001893](https://dandiarchive.org/dandiset/001893/) before rendering the figure.
The default argument `0` uses the frozen publication PC1 values.

The heavy run also writes the recomputed metadata table, frozen-versus-current
PC1 differences, selected sweep and DANDI asset provenance, representative
spike waveforms, and the nine raw traces underlying S14j to `/results`.
Because dandiset `001893` currently has only a draft version, the repository
pins every input asset, immutable blob URL, and SHA-256 in
`code/dandi_001893_manifest.csv`.

To reproduce the same run from the repository root:

```bash
./code/run
./code/run 1
```

For local package development:

```bash
python -m pip install -e .
generate-s14jk
```

By default, the command reads the bundled CSV and writes PNG, SVG, and four
underlying-data CSV files to `results/`. Paths can be overridden:

```bash
generate-s14jk --input path/to/AIBS_spreadsheet_pub.csv --output-dir path/to/results
```

The frozen table was exported from the analysis underlying the LCNE patch-seq
publication in
[AllenNeuralDynamics/LCNE-patchseq-analysis](https://github.com/AllenNeuralDynamics/LCNE-patchseq-analysis).

## Repository layout

- `code/`: capsule entry point, generator, frozen input table, and tests
- `environment/`: pinned Code Ocean container definition
- `metadata/`: capsule name, description, and author metadata
