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

initial_difference = np.max(
    np.abs(populations_hw[0] - populations_sim[0])
)

final_difference = np.max(
    np.abs(populations_hw[1] - populations_sim[1])
)

print("\n=== EXPLORATORY REPLAY: ORIGINAL CIRCUIT IDENTITY UNVERIFIED ===")
print("Initial population max difference:", initial_difference)
print("Generation 1 population max difference:", final_difference)
print("Hardware best:", best_hw.x, best_hw.fitness)
print("Simulator best:", best_sim.x, best_sim.fitness)

np.savez(
    "outputs/json/ibm_generation_01/population_comparison_reconstructed.npz",
    circuit_identity_verified=False,
    hardware_initial=populations_hw[0],
    hardware_final=populations_hw[1],
    simulator_initial=populations_sim[0],
    simulator_final=populations_sim[1],
)

print("Population comparison saved.")

