# AEQGA poster results

**Hardware sampling changed the candidates proposed by the search. In the one-update Kingston test, the hardware and ideal simulator retained the same best starting candidate.**

[Four-way poster figure (SVG)](assets/kingston_four_way_comparison.svg) · [Parallel qubit packing diagram and historical noise study](assets/kingston_poster_physics.svg)

## From measurements to a physics result

AEQGA uses a quantum circuit to propose candidate values for the present-day expansion rate H₀ and the matter density fraction Ωₘ. An ordinary computer scores each pair against Pantheon+ supernova observations. The contour plot shows the regions of H₀ and Ωₘ with similar fit scores. Darker bands indicate better fits. The hardware and ideal markers show the best parameter pairs returned after one update of the same 32-candidate starting population.

| Result | H₀ (km/s/Mpc) | Ωₘ | Best χ² | Best Δχ² | Best new candidate Δχ² |
|---|---:|---:|---:|---:|---:|
| Classical objective minimum | 72.832 | 0.3629 | 1752.904 | 0.00 | |
| IBM Kingston, one update | 71.958 | 0.4609 | 1778.756 | +25.85 | +91.35 |
| Noiseless finite-shot simulator, one update | 71.958 | 0.4609 | 1778.756 | +25.85 | +40.96 |
| Kingston noise model, one update | 71.958 | 0.4609 | 1778.756 | +25.85 | +121.35 |

All 24 new candidates differed at corresponding positions across the two populations. Both retained their eight classical elites, including the shared best starting point. The contour zoom shows the subset of new candidates near the fit region. The hardware ledger records four circuits at 1,024 shots each. Its archived counts and populations support the overlay. The original compiled circuits are unavailable for an exact hardware-to-simulator circuit check. The measured fit statistic is χ², and Ωₘ is a dimensionless matter fraction. [Kingston audit](../docs/PR10_SUMMARY.md) · [Numeric record](../docs/PR10_COMPATIBILITY.json)

The separate single-circuit pilot gives context for the difference in candidates. Its measured **total variation distance** from reconstructed ideal probabilities was **0.1106**. The 99th percentile across 10,000 ideal repeats with 1,024 shots was **0.0650**, and none reached the hardware gap. This statistic measures how much probability would need to move between outcomes to make the two distributions agree. [Pilot counts](../outputs/json/ibm_first_pilot/recovered_counts.json) · [Kingston audit](../docs/PR10_SUMMARY.md)

## What the matched noise reconstruction shows

All three runs retained the same best starting point. Their best new candidates scored differently, and none improved the starting best. The four-panel figure combines the fit contours, full parameter scatter, cumulative distribution of new-candidate scores, and the comparison of the retained best and the best new candidate. Lower Δχ² indicates a better fit.

The noisy run used the same 32 starting candidates, seed, Pantheon+ objective, decoding, one update, and shot budget as the archived comparison. Qiskit Aer simulated gate and thermal errors and asymmetric readout using the April 15, 2026 Kingston snapshot. The native circuits used physical qubits 0–3 or 0–2, depending on circuit width. The original physical layout and compiled circuits are unavailable. These are finite-shot snapshots of a single search update, so the candidate score differences can include sampling variation. [Archived calibration](https://github.com/KrithikMohan/AEQGA/tree/ebeb6ba28a6bea1f01c7ef9ba1ce06d3cf5f3fe2/noise_validation/ibm_backend_snapshots/kingston)

## Parallel qubit packing

The packing approach gives each candidate subgroup its own connected block of qubits. A four-qubit block can encode 16 candidates. The algorithm selects elites across the whole population, then redistributes them among blocks for the next update. The Marrakesh simulation placed **38 four-qubit blocks** on **152 of 156** available qubits, for **608 candidates per update**. The diagram counts occupied blocks and spare qubits. The packing result comes from a simulation, and the one-update Kingston job used four separate circuits. [Marrakesh study and layout evidence](https://github.com/KrithikMohan/AEQGA/tree/111b29bb2f91854c88814a0e6142e90a3619dfe2/noise_validation/marrakesh_profiled_156q)

## Reproduce the figure and run matched simulator controls

The run uses Qiskit, Aer, NumPy, and SciPy. The script extracts and verifies the Pantheon+ data from the pinned local Git commit and checks that the hardware and noiseless replays match the saved populations. The plot uses Matplotlib.

- [Run and score the comparison](../aeqga/analysis/kingston_noise_reconstruction.py)
- [Draw the four-panel figure](../aeqga/visualization/kingston_noise_comparison.py)
- [Draw the separate packing and historical-study figure](../aeqga/visualization/kingston_poster_context.py)

```bash
python -m aeqga.analysis.kingston_noise_reconstruction
MPLBACKEND=Agg python -m aeqga.visualization.kingston_noise_comparison
```

The run writes candidate positions, scores, and noisy shot counts to `outputs/json/kingston_noise_reconstruction/comparison.json`. The same directory holds the reconstructed logical and native circuit archives and the contour grid.

The main supernova ensemble runner accepts an Aer noise model serialized as JSON using `NoiseModel.to_dict(serializable=True)`. It records the model in the experiment configuration and checkpoint identity. With the Pantheon+ inputs and runtime dependencies installed, these commands run an ideal and a noisy control on the same objective, starting seeds and budget.

```bash
python -m scripts.run_sne_ensemble --name poster_ideal --engine aer --runs 3 --pop 32 --gen 1 --shots 1024 --seed 42
python -m scripts.run_sne_ensemble --name poster_noisy --engine aer --runs 3 --pop 32 --gen 1 --shots 1024 --seed 42 --noise-model kingston_noise.json
```

To produce `kingston_noise.json`, use a checkout of the pinned noise-study commit. From its `noise_validation` directory, with its dependencies installed, export the archived snapshot's Aer channels. Use the resulting file path in the noisy command above.

```bash
python - <<'PY'
import json
from pathlib import Path
from aeqga_ibm_noise import SnapshotBackend, device_noise

model = device_noise(SnapshotBackend("kingston", width=4))
Path("kingston_noise.json").write_text(json.dumps(model.to_dict(serializable=True)))
PY
```

The two commands run new simulator controls using seed 42 to derive the same set of run seeds. The serialized channels can change Aer's compilation basis. Reproducing the historical study's custom layout and scheduling requires its archived runner.
