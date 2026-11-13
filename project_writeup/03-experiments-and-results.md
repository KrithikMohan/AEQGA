# 3. From a simulator to real hardware

[Previous: The search and the quantum circuit](02-search-and-circuit.md) · [Next: Reproduce it and read the code](04-reproduce-and-explore.md)

## Four ways to run a circuit

The same circuit recipe can be evaluated in different ways. An **execution engine** is the program or device that performs that step.

| Engine | What produces the result | What it tells us |
|---|---|---|
| Exact ideal probabilities | An ordinary computer calculates the statevector and squares the amplitudes. | Expected outcome probabilities with perfect gates and no finite-shot variation. |
| Ideal finite-shot simulation | An ordinary computer samples a specified number of outcomes from the ideal circuit. `statevector_shots` is the main fast implementation; **Aer**, a Qiskit circuit simulator, also has a finite-shot mode. | How ordinary sampling can vary even with perfect gates. |
| Noisy simulation | A program adds a **noise model**, rules that approximate preparation, gate, idle or readout errors. | What might happen under those specified error assumptions. |
| Physical QPU | A real **quantum processing unit** prepares, operates on and measures physical qubits. | What that device returned for those submitted circuits at that time. |

**Qiskit** is the software toolkit that builds and analyzes circuits. **IBM Runtime** connects to IBM's cloud service. The **Sampler** runs measured circuits and returns bitstrings or their counts. A **backend** is the simulator or device selected to execute them. A **job** is a submission to the service. Four independent circuits can be grouped into one submission for a generation; the next generation still needs the decoded results from the previous one. A **session** is an optional service mode for related jobs and depends on account support. [IBM Sampler guide](https://quantum.cloud.ibm.com/docs/en/guides/get-started-with-sampler)

**Transpilation** rewrites a logical circuit to use the device's available **native gates** and its allowed connections. A logical qubit is one wire in our algorithm; a physical qubit is an actual site on the device. A **layout** assigns logical wires to physical sites. **Routing** may insert operations to move information between sites. **Circuit depth** counts sequential layers of operations; it is different from the total gate count. Two-qubit gate count and circuit depth help describe cost, but neither alone determines accuracy. A **calibration snapshot** is a dated set of measured device properties. It is not a fresh measurement every time we simulate it.

## How we compare the outcomes

1. **Same circuit, different measurements.** Keep the input and gates fixed. Compare the ideal probability distribution with the measured histogram. This asks whether the circuit behaved like its ideal model. **Total variation distance (TVD)** is half the sum of the absolute probability differences across all outcomes. For example, `[0.6, 0.4]` and `[0.5, 0.5]` differ by `(0.1 + 0.1)/2 = 0.1`. TVD is between 0 and 1; it is not a gate's error probability.
2. **Same starting conditions, separate searches.** Match the dataset, scoring rule, starting population, seed, gate probabilities, shots and update budget. Let the hardware-count search and simulator search evolve independently. Once their populations differ, the next circuits can differ too. This compares optimizer behavior, not the fidelity of the same circuit at every update.
3. **Compare with a classical reference.** Check the final score and the parameter pair against the independently fitted minimum for *that same objective*. Report the number of evaluations and updates. A noisy run can sometimes find a better candidate than an ideal run by chance; that does not mean its circuits are more accurate.

To ask whether an observed TVD is large for a finite number of shots, use a **Monte Carlo** experiment: repeat the ideal sampling many times by computer and count how often its TVD is at least as large. A **percentile** is a cutoff: the 99th percentile has about 99% of those simulated values at or below it. Zero exceedances in 10,000 trials is a statement about that finite experiment, not proof that the chance is exactly zero.

## What the main repository has demonstrated

### The 300-run supernova simulation

An **ensemble** is a collection of separate runs. The committed report contains 300 independent seeded **simulations**, each with 32 candidates, 50 updates and 4,096 shots per circuit. The configured classical reference is H₀ = 72.83204, Ωₘ = 0.362876 and χ² = 1752.90405. The ensemble mean is H₀ = 72.86454 and Ωₘ = 0.35689. The median final Δχ² is 0.29270: half the runs end at or below approximately that gap. In this experiment, 265 of 300 runs (88.3%) reach Δχ² below 2.30. The largest gap is about 17.98. The outliers are part of the result, not discarded trials. [Committed run report](../docs/SNE_PLOT_RESULTS.md)

The cutoff 2.30 is a stated diagnostic threshold for this comparison. The 88.3% means “fraction of these independent searches that got this close to the fit.” The report's **95% Wilson interval** (about 84.2%–91.5%) describes uncertainty in that success fraction under comparable independent repeats. It does not assign a probability that a cosmological parameter is true. The same returned candidates also get rescored with direct distances; they are not polished or moved to a new optimum during this check.

### Physical IBM Kingston: two small archived experiments

| Experiment | What was run | What the record shows |
|---|---|---|
| Single-circuit pilot | Four logical qubits; 1,024 shots; crossover and mutation both forced on. | All 16 basis outcomes were seen. TVD from the reconstructed ideal distribution was 0.110565. The ideal finite-shot 99th percentile was 0.064987. |
| One complete AEQGA update | 32 candidates, four circuits with widths `[4, 3, 4, 3]`, 1,024 shots each. | Best H₀ ≈ 71.958, Ωₘ ≈ 0.46094, χ² ≈ 1778.75567, Δχ² ≈ 25.85162; 64 classical objective evaluations. |

For the single circuit, the measured TVD was larger than all 10,000 ideal finite-shot trials using the reconstructed logical input. This supports a discrepancy beyond the ideal sampling baseline; it does not identify a particular faulty gate. For example, the figure's `0111` bar represents 200 of the 1,024 shots, about 19.5%. [Original basis-state histogram](../outputs/png/ibm_first_comparison.png)

For the update, the current code can **replay** the saved counts without submitting work to IBM. It reproduces the four archived population arrays. Both the replay and its matched ideal simulation retained the same initial best elite, so the best-pair curves are flat and overlap. Other candidates can still differ. The old records lack the original compiled circuit archive, so replay verifies what the software does with the saved counts; it cannot independently authenticate the physical circuit. The archive also does not supply comparable wall-time data. One update is not a full hardware reproduction of the 300-run experiment. [Kingston audit](../docs/PR10_SUMMARY.md)

## How to read the notebook figures

| Plot | Read it this way | Avoid this conclusion |
|---|---|---|
| Section 7 **evolution** | The horizontal axis is update number. Raw χ², Δχ², H₀ and Ωₘ refer to the same global-best pair at each update. | A flat line means the whole population stopped changing. |
| **Likelihood contour** | A contour joins points at the same objective level, like an elevation line on a map. Tilted contours show a trade-off between parameters. | The lines describe the measured scatter of the optimizer. |
| **Optimizer scatter and density** | One dot is one run's final pair. A covariance ellipse summarizes their spread and direction. **KDE** means *kernel density estimation*: smooth a cloud by placing a small bump at each point and adding the bumps. Its labeled regions enclose fractions of the estimated outcome distribution. | The dots are new astronomical observations, or the smoothed regions are automatically the universe's uncertainty. |
| **Accuracy against reference** | Signed error says which direction a parameter misses; **bias** is the mean signed error; **MAE** averages absolute misses; **RMSE** takes the square root of the mean squared miss, giving bigger errors more weight. | A small percentage error is a percentage probability of being right. |
| **Kingston vs CPU performance** | Read the matched best-pair histories, gap versus number of objective evaluations, final gaps and available recorded wall time. | Different overheads or one lucky run prove quantum speedup. |

**Wall time** is ordinary clock time. A hardware run can include queueing, communication and recovery; the CPU simulator has different overheads. Device **QPU usage** and a *gate-time estimate* are separate from wall time. Fair claims about speed would need repeated matched experiments, defined resource budgets and a meaningful classical competitor. In this project even the hardware workflow still calculates every cosmological score classically. [Plot interpretation](../docs/GRAPH_ACCURACY.md)

## The separate width studies on `parallel_to_fill`

These are research additions on a fetched branch, not part of the maintained notebook on `main`. They use a different supernova selection (1,657 observations) and an explicitly fitted **nuisance parameter**, a parameter needed for the prediction but not the main target. Here the nuisance parameter is the absolute magnitude M. At each `(H₀, Ωₘ)` proposal they find the best allowed M from the covariance-weighted residuals, called **profiling M**. Its bounds are −19.6 to −19.0; Ωₘ is searched from 0.1 to 0.5 in these studies. Their classical reference is around `[73.53278, 0.331812, −19.24406]`, with χ² ≈ 1452.01595. That score uses different data and an objective that includes M, so it cannot be compared directly with 1752.90405 as if the smaller number won.

**Circuit width** is the number of qubit wires. The width studies split the candidate list into **subpopulations**, smaller groups, and pack their circuits onto separate wires under a total qubit budget. Each group has `2^q` candidates for width `q`. **Local** proposals explore near elites and **global** proposals explore the full range. Elites are selected across groups and distributed by rank in repeated turns. Each update works through four stages: local and global proposals for H₀, then for Ωₘ. Packing circuits does not by itself demonstrate simultaneous physical execution or speedup.

| Study | What actually ran | Recorded result and limit |
|---|---|---|
| [Marrakesh width study](https://github.com/KrithikMohan/AEQGA/tree/0e84df3/noise_validation/marrakesh_profiled_156q) | Local simulation from a dated IBM Marrakesh calibration, with a 156-wire budget. Six widths (3–8), ideal and noisy controls, one seed and 100 updates per case. | Width 4 had the smallest final noisy gap in that set, about `3.45 × 10⁻⁷`. No physical Marrakesh jobs ran. The model omits some real-device effects, such as interference between nearby wires and changes in calibration over time. |
| [IonQ Forte-1 width study](https://github.com/KrithikMohan/AEQGA/tree/111b29b/noise_validation/ionq_forte_29q) | Hosted IonQ cloud **simulator** with the Forte-1 noise model, a 29-wire packing budget, and matched local ideal finite-shot runs. Widths 3–8, one seed, 100 updates, 100 shots per stage. | Width 4 had the lowest final noisy gap in that set, about `2.65 × 10⁻⁷`. These are returned cloud-simulator histograms, not results from a physical Forte-1 device. |

Width changes several things at once: group count, candidates per group, the elite search intervals, native gates, and how often outcomes are unseen. At 100 shots, an eight-qubit distribution with 256 possible outcomes must leave some bins unseen. The decoder can then use more classical random replacements. A smaller final gap does not prove wider or narrower circuits were inherently better. Comparing vendors is also confounded by different wire budgets and noise models. Both studies need more seeds and controlled comparisons before claiming a generally best width. [IonQ explanation of noisy simulation](https://docs.ionq.com/features/simulation-with-noise-models)
