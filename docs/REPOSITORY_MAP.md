# Repository map

## Start here

- [Main notebook](../notebooks/AEQGA.ipynb) walks through the cosmology, optimization runs, and plots interactively.
- [Poster results](../project_writeup/poster-results.md) explains the Kingston comparison and parallel qubit packing. The [four-panel poster figure](../project_writeup/assets/kingston_four_way_comparison.svg) is ready to open.
- [Project write-up](../project_writeup/README.md) explains the physics and algorithm in plain language. [README](../README.md) covers setup and commands.

## Kingston comparison from data to figure

| Step | File | What it does |
|---|---|---|
| 1. Run and score | [aeqga/analysis/kingston_noise_reconstruction.py](../aeqga/analysis/kingston_noise_reconstruction.py) | Replays the archived hardware and noiseless results, runs the calibration-based noisy simulation, and scores all three against Pantheon+. It saves the candidate data, counts, circuits, and contour grid. |
| 2. Draw the figure | [aeqga/visualization/kingston_noise_comparison.py](../aeqga/visualization/kingston_noise_comparison.py) | Reads the comparison data and draws the four panels with the classical minimum as the common reference. |
| Poster context | [aeqga/visualization/kingston_poster_context.py](../aeqga/visualization/kingston_poster_context.py) | Draws the separate context figure about parallel packing and the earlier 100-update noise study. |

From the repository root, run these in order. The experiment reads saved hardware results and runs the noisy simulation locally.

```bash
python -m aeqga.analysis.kingston_noise_reconstruction
MPLBACKEND=Agg python -m aeqga.visualization.kingston_noise_comparison
```

The older `scripts.run_kingston_noise_reconstruction` and `scripts.plot_kingston_noise_reconstruction` commands still work.

## Maintained Python package

| What you want to change | Where to look |
|---|---|
| The optimizer loop | [aeqga/steps/evolution/aeqga_algorithm.py](../aeqga/steps/evolution/aeqga_algorithm.py), the maintained implementation of `run_aeqga_dual`. |
| The pieces inside one update | [aeqga/steps/](../aeqga/steps) groups population selection, amplitude encoding, crossover and mutation gates, and measurement decoding. |
| The astronomy and fit score | [aeqga/likelihoods/](../aeqga/likelihoods) contains the calibrated Pantheon+ likelihood, cosmological distance calculations, and the separate BAO/CMB likelihood. [aeqga/emulators/](../aeqga/emulators) contains the PICO runtime used for CMB. |
| Where and how circuits run | [aeqga/execution/](../aeqga/execution) contains IBM and offline simulator adapters, checkpointing, and restart logic. |
| Repeating an experiment across seeds | [aeqga/experiments/runner.py](../aeqga/experiments/runner.py) runs ensembles and keeps each run's settings, data identity, and checkpoint together. |
| Reading and comparing results | [aeqga/analysis/](../aeqga/analysis) contains accuracy summaries, circuit comparisons, hardware validation, and historical replay. |
| Making other figures | [aeqga/visualization/](../aeqga/visualization) has reusable scientific plots and a circuit diagram renderer. |
| Connecting to HQGA | [aeqga/integrations/hqga.py](../aeqga/integrations/hqga.py) adapts HQGA-style problems and runs. |
| Shared project paths | [aeqga/paths.py](../aeqga/paths.py) defines repository and output locations. |

## Commands, notebooks, and checks

| Group | Files |
|---|---|
| Run a science experiment | [scripts/](../scripts) contains `run_pantheon_aeqga.py` for a supernova fit, `run_sne_ensemble.py` for repeated supernova runs, and `run_bao_cmb_aeqga.py` for BAO/CMB. |
| Run, recover, or review IBM work | In [scripts/](../scripts), `ibm_preflight.py` checks the setup, `run_ibm_generation.py` runs updates, `run_first_qpu_experiment.py` handles the first-pilot workflow, and `recover_ibm_job.py` retrieves existing results. `analyze_first_qpu_experiment.py`, `compare_generation_populations.py`, and `analyze_hardware_runs.py` analyze the saved records. |
| Setup, benchmarks, and reports | In [scripts/](../scripts), `setup_env.py` and `fetch_cmb_data.py` prepare inputs, `benchmark_hardware.py` and `benchmark_replication.py` report resource and replication checks, `test_full_generation.py` and `test_hardware_compilation.py` are runnable checks, and `build_pr10_summary.py` produces the archived Kingston report. |
| Interactive notebooks | [notebooks/AEQGA.ipynb](../notebooks/AEQGA.ipynb) is the maintained walkthrough and calls into the package. [examples/qml_demo_noisy_and_qpu/](../examples/qml_demo_noisy_and_qpu) contains standalone IBM and noise demos and an IonQ simulation notebook. The original ZIP is in [old versons](../old%20versons/). |
| Automated checks | [tests/](../tests) covers quantum primitives, calculations, accuracy, experiment checkpoints, IBM and HQGA integration, and the archived Kingston replay. |
| Archived versions | [old versons/root-scripts/](../old%20versons/root-scripts/) holds the superseded root optimizer and likelihood, plus the historical PR #10 launchers. |

## Where files end up

| Location | What belongs there |
|---|---|
| [outputs/](../outputs) | Experiment artifacts. `json/` holds numerical results, checkpoints, and run archives. `png/`, `pdf/`, and `svg/` hold plot exports and reports, including the [PR #10 summary PDF](../outputs/pdf/PR10_SUMMARY.pdf). The Kingston inputs and replay outputs are under `outputs/json/`. |
| [project_writeup/assets/](../project_writeup/assets) | Figures referenced directly from the write-up, including the poster SVGs. |
| [docs/](.) and [project_writeup/](../project_writeup) | Technical records and explanatory material, respectively. |
