# 4. Reproduce it and read the code

[Previous: Experiments and results](03-experiments-and-results.md) · [Glossary](glossary.md)

## Start with a small run on your own computer

A **repository** is a project folder with recorded history. **Git** is the tool that records that history. A **commit** is one saved version; a **branch** is a named line of development; `main` is the maintained line. **Fetch** gets new version information, and **pull** updates the current work with the chosen remote history. A **pull request** proposes changes for review. The [repository snapshot](sources-and-update.md) says which results come from which branch.

You can read the plots and explanations without setting up any software. To run the code, open a **terminal** (a window for typing commands) in the repository folder. The following example is for macOS or Linux. **Python** is the language that runs the project. A **virtual environment** (`venv`) keeps this project's installed software separate from your other projects. A **dependency** is a package the code needs. `requirements.txt` records the intended package versions; `pip` installs them.

If `venv` is already set up, activate it and skip creating it again. A fresh setup uses Python 3.12:

```bash
python3.12 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
```

The last line registers this project as an importable Python package while continuing to use its source files from this folder. The `--no-deps` flag tells that step not to repeat the dependency installation.

The observations are stored separately from the code. If `sn_data` is not already present, download the data repository and select the documented version:

```bash
git clone https://github.com/CobayaSampler/sn_data.git sn_data
git -C sn_data checkout 61d96434cafc2770928322c38e5a750e686368ae
```

Try an **offline rehearsal**, a local run that exercises the same circuit-execution interface without contacting IBM:

```bash
python -m scripts.run_ibm_generation --population 8 --generations 1 --shots 128 \
  --directory outputs/json/guide_offline_pilot
```

Here `python -m` runs a named module; the words starting with `--` are **command-line options** that change its settings. This command uses actual Pantheon+ data and local Aer simulation. It starts with eight candidates and evaluates eight more after one update. It needs no IBM account. With eight candidates the random group has four entries and the elite-copy group has two, so the logical circuit widths are `[2, 1, 2, 1]`. A one-qubit circuit has no pair of wires for crossover, so that operation is skipped there.

Look for `result.json` in the chosen directory. **JSON** is a text format for named values and lists. Find the best pair, best χ², and evaluation count. An initial and final entry are both expected. Run the following to make a plot from that completed rehearsal:

```bash
python -m scripts.analyze_hardware_runs --directory outputs/json/guide_offline_pilot
```

The `hardware_` names here describe the analysis tools' output format. This particular run was still a simulator rehearsal. `hardware_convergence.png` shows the best pair and score history. A **PNG** is a pixel image; **SVG** stores drawings as scalable shapes; **PDF** is useful for sharing and printing. The script also writes a numeric summary. For larger parameter sweeps, **CSV** stores a table as text rows and **NPZ** stores compressed NumPy arrays (lists or tables of numbers used by Python).

## Use the notebook as a lesson

A **Jupyter notebook** is a document with text and executable code blocks called **cells**. Its **kernel** is the Python process that remembers variables and imports between cells. Open [the maintained notebook](../notebooks/AEQGA.ipynb) and select the kernel using your project environment. Restart the kernel after changing code or software so old imported definitions do not linger.

**For your first notebook run, check that `RUN_IBM_PILOT = False` before using Run All.** The reviewed `main` version defaults to off, but a local notebook can have live submission enabled. Also leave the earlier `RUN_IBM` example off. Select `MODE = "demo"` for a shorter experiment, and set `RUN_ENSEMBLE = False` if you only want one trajectory. The hardware, CMB+BAO and HQGA options are independent; you do not need them to learn the basic search.

| Notebook area | What to look for |
|---|---|
| Setup, configuration and data checks | Which Python is running, which files are used, and which switches are on. |
| Classical fit and circuit example | The target score and a small demonstration of the proposal circuit. |
| Section 7 | The four panels showing score and the two values in the same best pair. |
| Section 9 and 9a | Repeated searches, how their outcomes scatter, and agreement with the reference. |
| IBM pilot and recovery | A separately configured execution, with real-hardware switches and recorded job information. |
| Kingston evolution and matched simulator performance (local development) | Plots a completed hardware record against a local run with the same initial conditions and budget. This plotting cell alone does not submit another job. The comparison code is not part of this documentation PR or the reviewed `main` commit. |

## When you are ready for a physical device

A real device requires an IBM account with access to the chosen backend and an allocation for running jobs. An **API key** is a private password-like credential that software uses to sign in. An **instance** is the service resource the account uses; its **CRN** is its cloud resource name, a unique identifier. Save credentials locally using IBM's SDK account setup, never in a notebook, project file, plot, chat or Git commit. The runner loads the saved default account. [IBM credential instructions](https://quantum.cloud.ibm.com/docs/en/guides/save-credentials)

After setting up your account, check access without submitting a circuit:

```bash
python -m scripts.ibm_preflight --backend ibm_kingston
```

A **preflight** is a check before starting a run. If Kingston is unavailable to your account, choose an accessible backend before running the pilot. The physical notebook cell requires `RUN_IBM_PILOT`, `SUBMIT_IBM_HARDWARE` and `CONFIRM_IBM_QPU`. With one update and 1,024 shots per circuit at population 32, it requests four circuits and 4,096 total circuit-shots. That is a circuit sampling budget, not an estimate of queue time or charges. Review settings before enabling or executing that cell. You can keep learning from the archived Kingston results with no hardware access.

## Why saved runs can be checked and resumed

**Provenance** is the record of where a result came from: data versions, settings, seed, software versions and code. A **hash** or **fingerprint** is a short digital identifier computed from file contents or settings. If a file changes, its hash normally changes. It helps check whether two experiments really used the same input. It does not verify that the experiment's reasoning is correct.

A **checkpoint** is a saved point in a run. The simulation ensemble saves completed runs. The newer hardware workflow saves generation state, the random-number state, circuit archives, the service's job ID, and counts. **QPY** is Qiskit's format for saving a circuit. **Logical** and **ISA** archives save the original circuit recipe and the rewritten recipe in the device's *instruction set architecture* (its supported operations), respectively. The checkpoint should be used by one process at a time. A **job ID** is the service's tracking number; recovering that job is different from sending a new one. If a run stopped while submitting and no job ID is recorded, check the service's job list before retrying. A changed dataset, seed or configuration needs its own output directory. Old Kingston ledgers can be read for analysis but lack the information required to resume a modern job. [Hardware recovery details](../docs/IBM_HARDWARE.md)

## Where the work happens in the code

| Location | Plain-language job |
|---|---|
| [`aeqga/likelihoods/`](../aeqga/likelihoods/) | Load observations, predict distances and compute the score. |
| [`aeqga/steps/`](../aeqga/steps/) | Select candidates, encode their values, apply gates, decode counts and repeat. |
| [`aeqga/execution/`](../aeqga/execution/) | Run the circuit in a simulator or on IBM; archive and recover the work. |
| [`aeqga/experiments/`](../aeqga/experiments/) | Organize many seeded runs and validate their histories. |
| [`aeqga/analysis/`](../aeqga/analysis/) | Compare results, measure errors and replay old results. |
| [`aeqga/visualization/`](../aeqga/visualization/) | Draw plots from the recorded scores and pairs. |
| [`scripts/`](../scripts/) and [`tests/`](../tests/) | Commands to run the project and checks for known expected behavior. |

Use the maintained `aeqga/` package, not the old root-level likelihood file. The latter can silently fall back to synthetic data (made-up values), which is unsuitable for a real supernova fit. The separately published width studies are different experiments with their own instructions and software versions.

## Check your understanding

1. **Why does 4 qubits give 16 possible results?** Each wire has two possible measured values. Multiply `2 × 2 × 2 × 2`.
2. **Does `0111` mean H₀ is 7?** No. Seven is the basis-list index. Its count contributes to a proposal through a decoding rule.
3. **A candidate scores 1760 and its reference scores 1752.90. What is the gap?** `1760 − 1752.90 = 7.10`. A raw score does not tell you that gap on its own.
4. **Can a perfect simulator have a noisy-looking histogram?** Yes. With finitely many shots, random sampling causes variation even when the circuit is ideal.
5. **Why might the best-pair graph stay flat when the circuit does something?** The older elite can still beat all new proposals. Check the other population members if you want to see what changed.
6. **Does the Forte-1 study mean we ran on a real IonQ computer?** No. Its remote service simulated a noise model for that processor. The archived Kingston counts came from physical hardware.
7. **What would convince you one width is generally better?** Repeat across seeds, control what changes besides width, compare under a shared budget and report the variation across trials.
