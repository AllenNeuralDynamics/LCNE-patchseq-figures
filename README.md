# LCNE patch-seq figures

This lightweight repository reproduces supplementary figure S14k directly from
the frozen `AIBS_spreadsheet_pub.csv` publication table. It has no dependency on
the LCNE analysis package, S3, eFEL, or an attached `/data` dataset.

The frozen table contains the PC1 and membrane-time-constant values needed for
S14k, but not the raw voltage arrays used by S14j. The combined output therefore
shows a labeled placeholder for panel j. A later revision will add a small path
for obtaining those traces from NWB files on DANDI.

## Run

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
