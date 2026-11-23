"""Exploratory offline replay of historical counts with reconstructed circuits."""
import json
import numpy as np
from aeqga.execution.ibm_sampler import _counts

from aeqga.likelihoods.pantheon_problem import PantheonPlusProblem
from aeqga.steps.evolution.aeqga_algorithm import (
    AEQGAParameters,
    run_aeqga_dual,
)

class ReplayExecutor:
    def __init__(self, counts, shots):
        self.counts = counts
        self.shots = shots
        self.calls = 0

    def run(self, circuits, *, generation, optimizer_state=None):
        assert generation == 1
        assert len(circuits) == 4
        self.calls += 1
        return [_counts(counts, '', self.shots, circuit.num_qubits)
                for circuit, counts in zip(circuits, self.counts)]

with open(
    "outputs/json/ibm_generation_01/generation_0001.json",
    encoding="utf-8",
) as f:
    checkpoint = json.load(f)

assert checkpoint["state"] == "completed"

problem = PantheonPlusProblem(
    "sn_data/PantheonPlus",
    selection="all",
    redshift="hd_hel",
    grid_size=300,
)

params = AEQGAParameters(
    pop_size=32,
    max_gen=1,
    p_cross=0.5,
    p_mut=0.5,
    num_shots=checkpoint["shots"],
    progress_bar=False,
)

# Replay the actual hardware counts locally.
# This does not connect to IBM.
replay = ReplayExecutor(checkpoint["counts"], checkpoint["shots"])

best_hw, populations_hw, history_hw = run_aeqga_dual(
    problem, params,
    seed=42,
    hardware_executor=replay,
    quiet=True,
)

assert replay.calls == 1

# Run the ideal finite-shot simulator using the reconstructed setup
best_sim, populations_sim, history_sim = run_aeqga_dual(
    problem, params,
    seed=42,
    execution_mode="statevector_shots",
    quiet=True,
)

def describe_population(initial, final):
    """Report marginal quantiles in native units and score complete pairs.

    Row-wise differences mix arbitrary pairings and decoding draws.
    Best chi-square improvement is measured against the initial best
    because the optimizer can preserve that candidate through elitism.
    Circuit identity is unverified, so this replay cannot isolate noise.
    """
    initial_best = min(map(problem.compute_fitness, initial))
    scores = np.array(list(map(problem.compute_fitness, final)))
    return {
        "H0_quantiles_10_50_90": np.quantile(final[:, 0], [.1, .5, .9]).tolist(),
        "Omega_m_quantiles_10_50_90": np.quantile(final[:, 1], [.1, .5, .9]).tolist(),
        "initial_best_chi2": float(initial_best),
        "final_best_chi2": float(scores.min()),
        "final_median_chi2": float(np.median(scores)),
        "best_chi2_improvement": float(initial_best - scores.min()),
    }


print("Exploratory replay with unverified circuit identity.")
print(json.dumps({
    "initial_populations_match": bool(np.array_equal(populations_hw[0], populations_sim[0])),
    "hardware_replay": describe_population(*populations_hw[:2]),
    "ideal_simulator": describe_population(*populations_sim[:2]),
}, indent=2))

np.savez(
    "outputs/json/ibm_generation_01/population_comparison_reconstructed.npz",
    circuit_identity_verified=False,
    hardware_initial=populations_hw[0],
    hardware_final=populations_hw[1],
    simulator_initial=populations_sim[0],
    simulator_final=populations_sim[1],
)

print("Population comparison saved.")
