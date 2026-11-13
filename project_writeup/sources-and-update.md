# Repository snapshot and sources

[Start here](README.md)

## What was pulled and reviewed

On November 13, 2026, both configured GitHub remotes were fetched. The fast-forward-only update from `origin/main` reported **already up to date**. The checked-out code and remote `main` both point to [`1d08695`](https://github.com/KrithikMohan/AEQGA/commit/1d086950e4b7e4f94ca4d22533aa7cc6a3475330), the PR #9 merge. Local changes to the notebook, matched-comparison code and regenerated figures were preserved. The guide distinguishes those local improvements from the results committed to `main`.

| Fetched work | Location and meaning |
|---|---|
| [`111b29b`](https://github.com/KrithikMohan/AEQGA/commit/111b29b), IonQ Forte-1 study | New tip of `parallel_to_fill`. Adds a six-width cloud-noise simulation study, local ideal controls, results and standalone reproduction code. |
| [`0e84df3`](https://github.com/KrithikMohan/AEQGA/commit/0e84df3), Marrakesh study | Earlier commit on that branch. Adds the profiled-M width study with a dated IBM noise snapshot, saved results and reproduction code. |
| [`2356e43`](https://github.com/KrithikMohan/AEQGA/commit/2356e43), parallel tutorial | Earlier commit on that branch. Adds a separate parallel AEQGA teaching notebook and code bundle. |

The research branch was fetched and inspected without merging it into `main`. Its experiment settings, data selection and dependency versions belong to that branch. The `noise-validation` branch also remains separate from `main`. None of the hosted or physical experiments was rerun to prepare this guide.

## Checks performed for this guide

- The local repository test suite passed all 78 tests.
- The small [offline walkthrough](04-reproduce-and-explore.md) completed with the real Pantheon+ input: eight candidates, one update, four circuits and 512 simulated circuit-shots. Its analysis command also completed and generated the diagnostic plots. A temporary output directory kept existing results untouched.
- The guide's local file and chapter links were checked. No cloud or physical-device jobs were submitted.

## Where the numbers come from

- **Main simulation:** [Committed 300-run report at the reviewed commit](https://github.com/KrithikMohan/AEQGA/blob/1d08695/docs/SNE_PLOT_RESULTS.md), with its [numeric report](https://github.com/KrithikMohan/AEQGA/blob/1d08695/outputs/json/sne_production_notebook_accuracy.json). The guide uses these committed results rather than combining them with regenerated local files. At review time, the local report also contained 300 runs and 265 below the threshold, but its median configured gap was about 0.30781 versus the committed 0.29270. A report's fingerprint identifies which experiment produced it.
- **Physical Kingston experiments:** [PR #10](https://github.com/KrithikMohan/AEQGA/pull/10), [compatibility audit](../docs/PR10_SUMMARY.md), [numeric evidence](../docs/PR10_COMPATIBILITY.json) and [PR #9 resolution](https://github.com/KrithikMohan/AEQGA/pull/9). The six original numeric and graphical artifacts were retained when the older analysis code was adapted to the current interface.
- **Marrakesh noise study:** [Published findings](https://github.com/KrithikMohan/AEQGA/blob/0e84df3/noise_validation/marrakesh_profiled_156q/results/findings.txt) and [method report](https://github.com/KrithikMohan/AEQGA/blob/0e84df3/noise_validation/marrakesh_profiled_156q/results/report.txt). The branch reports 38 connected groups for width four under the studied layout, using 152 of 156 available wires.
- **IonQ cloud noise study:** [Published findings](https://github.com/KrithikMohan/AEQGA/blob/111b29b/noise_validation/ionq_forte_29q/results/findings.txt) and [reproduction notes](https://github.com/KrithikMohan/AEQGA/blob/111b29b/noise_validation/ionq_forte_29q/README.txt). The archive reports 2,400 training jobs: six widths × 100 updates × four submitted stages. The ideal controls ran locally. These were simulator jobs.

## Primary reading

- Sarracino et al., [A Quantum Genetic Algorithm with application to Cosmological Parameters Estimation](https://arxiv.org/html/2602.15459v1), Sections 2–4 and Algorithms 1–2. The original model, circuit, decoding and experimental design. The guide explains the actual repository behavior where implementation choices differ.
- Scolnic et al., [The Pantheon+ Analysis: The Full Dataset and Light-Curve Release](https://arxiv.org/abs/2112.03863), and Brout et al., [The Pantheon+ Analysis: Cosmological Constraints](https://arxiv.org/abs/2202.04077). The supernova observations and the independent astronomical analysis.
- IBM, [Bit ordering](https://quantum.cloud.ibm.com/docs/en/qiskit/bit-ordering), [Sampler quickstart](https://quantum.cloud.ibm.com/docs/en/guides/get-started-with-sampler) and [credential setup](https://quantum.cloud.ibm.com/docs/en/guides/save-credentials). Definitions of measurement strings and the actual submission interface.
- IonQ, [Simulation with noise models](https://docs.ionq.com/features/simulation-with-noise-models). Why a hosted noisy simulation is different from using the physical processor.

## Further reading in the repository

- [Replication specification](../docs/REPLICATION_SPEC.md): what follows the paper, and which choices cannot be independently matched.
- [Tasks 1–7](../docs/TASKS_1_TO_7_REPORT.md) and [tasks 8–12](../docs/TASKS_8_TO_12_REPORT.md): implementation, checks, and earlier experiment records.
- [Graph interpretation](../docs/GRAPH_ACCURACY.md): how the reference, residuals and optimizer scatter are calculated.
- [IBM integration](../docs/IBM_HARDWARE.md): hardware access, circuit archives and recovery.
- [HQGA integration](../docs/HQGA_INTEGRATION.md): the connection to the earlier algorithm's interfaces.
