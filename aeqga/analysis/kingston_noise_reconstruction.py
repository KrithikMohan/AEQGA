"""Generate the data for the four-panel Kingston hardware and noise comparison.

Replay the archived hardware and noiseless runs, simulate the same update with
Kingston calibration noise, and score all three against the Pantheon+ objective.
Read the result with aeqga.visualization.kingston_noise_comparison.
"""
from contextlib import redirect_stdout
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
import argparse
import io
import json
import os
import subprocess
import sys

import numpy as np
from qiskit import qpy

from aeqga.analysis.pr10_compatibility import HistoricalReplayExecutor
from aeqga.execution.ibm_sampler import BaseExecutor
from aeqga.experiments.runner import atomic_json, file_digest
from aeqga.likelihoods.pantheon_problem import PantheonPlusProblem
from aeqga.paths import PROJECT_ROOT, output_path
from aeqga.steps.evolution.aeqga_algorithm import AEQGAParameters, run_aeqga_dual


SNAPSHOT_COMMIT = "ebeb6ba28a6bea1f01c7ef9ba1ce06d3cf5f3fe2"
EXPERIMENT_SEED = 42
SAMPLER_SEED = 42
SNAPSHOT_FILES = [
    "aeqga.py", "aeqga_parallel.py", "aeqga_ibm_noise.py",
    "ibm_backend_snapshots/kingston/conf_kingston.json",
    "ibm_backend_snapshots/kingston/props_kingston.json",
]

# The archived code has a top-level aeqga.py. Give it its own Python process
# so it can load its calibration tools without shadowing the current package.
SIMULATE = """
import json
from pathlib import Path
from qiskit import qpy
from aeqga_ibm_noise import SnapshotBackend, compile_native, measurement_order, simulator

with Path("logical.qpy").open("rb") as stream:
    circuits = qpy.load(stream)
request = json.loads(Path("request.json").read_text())
records = []
compiled_circuits = []
for circuit, seed in zip(circuits, request["circuit_seeds"], strict=True):
    backend = SnapshotBackend("kingston", width=circuit.num_qubits)
    compiled = compile_native(circuit, backend, seed=seed)
    result = simulator(backend).run(compiled, shots=request["shots"], seed_simulator=seed).result()
    if not result.success:
        raise RuntimeError(result.status)
    compiled_circuits.append(compiled)
    records.append({
        "seed": seed,
        "counts": dict(result.get_counts()),
        "physical_qubits": backend.physical_ids,
        "measurement_physical_order": [backend.physical_ids[i] for i in measurement_order(compiled)],
        "native_operations": dict(compiled.count_ops()),
    })
Path("records.json").write_text(json.dumps(records))
with Path("native.qpy").open("wb") as stream:
    qpy.dump(compiled_circuits, stream)
"""


def archived_file(name):
    return subprocess.check_output(
        ["git", "show", f"{SNAPSHOT_COMMIT}:noise_validation/{name}"], cwd=PROJECT_ROOT)


class KingstonSnapshotExecutor(BaseExecutor):
    """Use the archived snapshot's native compilation and noise channels locally."""

    def __init__(self, shots, artifacts):
        super().__init__(shots=shots)
        self.artifacts = artifacts
        self.records = None

    def run(self, circuits, generation=0, optimizer_state=None):
        self.validate_circuits(circuits)
        if generation != 1 or self.records is not None:
            raise ValueError("This executor reconstructs one generation")
        circuit_seeds = np.random.default_rng(SAMPLER_SEED).integers(
            0, 2**31 - 1, size=len(circuits)).tolist()
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in SNAPSHOT_FILES:
                destination = directory / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archived_file(name))
            with (directory / "logical.qpy").open("wb") as stream:
                qpy.dump(circuits, stream)
            atomic_json(directory / "request.json", dict(shots=self.shots, circuit_seeds=circuit_seeds))
            env = {**os.environ, "PYTHONPATH": str(directory)}
            subprocess.run([sys.executable, "-c", SIMULATE], cwd=directory, env=env, check=True)
            self.records = json.loads((directory / "records.json").read_text())
            for name in ("logical.qpy", "native.qpy"):
                (self.artifacts / name).write_bytes((directory / name).read_bytes())
        counts = [record["counts"] for record in self.records]
        if len(counts) != len(circuits) or any(sum(c.values()) != self.shots for c in counts):
            raise ValueError("Noisy simulator returned an unexpected shot count")
        return counts


def run_comparison(artifacts):
    artifacts.mkdir(parents=True, exist_ok=True)
    audit = json.loads((PROJECT_ROOT / "docs/PR10_COMPATIBILITY.json").read_text())
    provenance = json.loads((PROJECT_ROOT / "outputs/json/notebook_sne_likelihood_figure_provenance.json").read_text())
    datasets = provenance["experiment"]["provenance"]["datasets"]
    source_root = "Pantheon+_Data/4_DISTANCES_AND_COVAR"
    with TemporaryDirectory() as temporary:
        data_dir = Path(temporary)
        for dataset in datasets.values():
            name = Path(dataset["path"]).name
            local = data_dir / name
            local.write_bytes(archived_file(f"{source_root}/{name}"))
            if file_digest(local) != dataset["sha256"]:
                raise ValueError(f"Wrong Pantheon+ dataset hash for {name}")
        result = evaluate(data_dir, artifacts, audit)
    result["dataset_sha256"] = {key: entry["sha256"] for key, entry in datasets.items()}
    atomic_json(artifacts / "comparison.json", result)
    return result


def evaluate(data_dir, artifacts, audit):
    ledger_path = "outputs/json/ibm_generation_01/generation_0001.json"
    archive_path = "outputs/json/ibm_generation_01/population_comparison.npz"
    for path in (ledger_path, archive_path):
        if file_digest(PROJECT_ROOT / path) != audit["artifact_sha256"][path]:
            raise ValueError(f"Original artifact differs from the PR #10 audit: {path}")
    ledger = json.loads((PROJECT_ROOT / ledger_path).read_text())
    reference = audit["generation"]["configured_classical_reference"]
    problem = PantheonPlusProblem(data_dir, selection=reference["selection"],
                                  redshift=reference["redshift"], grid_size=reference["grid_size"])
    calculated_reference = problem.classical_minimum()
    if any(not np.isclose(calculated_reference[key], reference[key], atol=1e-7, rtol=0)
           for key in ("H0", "Omega_m", "chi2")):
        raise ValueError("Recomputed classical minimum differs from the audit")
    h0 = np.linspace(reference["H0"] - 2, reference["H0"] + 2, 240)
    omega = problem.omega_grid[np.abs(problem.omega_grid - reference["Omega_m"]) <= .12]
    np.savez_compressed(artifacts / "contours.npz", h0=h0, omega=omega,
                        delta_chi2=problem.objective_grid(h0, omega) - reference["chi2"])
    params = AEQGAParameters(pop_size=32, max_gen=1, num_shots=ledger["shots"], progress_bar=False)
    noisy_executor = KingstonSnapshotExecutor(ledger["shots"], artifacts)
    configurations = {
        "hardware": {"hardware_executor": HistoricalReplayExecutor(ledger)},
        "ideal": {"execution_mode": "statevector_shots"},
        "noisy": {"hardware_executor": noisy_executor},
    }
    runs = {}
    with np.load(PROJECT_ROOT / archive_path) as archived:
        for name, configuration in configurations.items():
            with redirect_stdout(io.StringIO()):
                best, populations, _ = run_aeqga_dual(
                    problem, params, seed=EXPERIMENT_SEED, quiet=True, **configuration)
            initial, final = populations
            archive_name = "hardware" if name == "hardware" else "simulator"
            if not np.array_equal(initial, archived[f"{archive_name}_initial"]):
                raise ValueError(f"{name} did not reproduce the starting population")
            if name != "noisy" and not np.array_equal(final, archived[f"{archive_name}_final"]):
                raise ValueError(f"{name} did not reproduce the audited final population")
            if not np.array_equal(final[:8], archived["hardware_final"][:8]):
                raise ValueError(f"{name} did not retain the shared eight elites")
            scores = [float(problem.compute_fitness(pair)) for pair in final]
            runs[name] = dict(best_x=best.x.tolist(), best_chi2=float(best.fitness),
                              best_generation=best.gen, final_population=final.tolist(),
                              final_chi2=scores)
    return dict(
        hardware_job_id=ledger["job_id"], classical_reference=reference, runs=runs,
        shots=ledger["shots"], updates=params.max_gen, seed=EXPERIMENT_SEED,
        sampler_seed=SAMPLER_SEED, retained_elites=8,
        noise_snapshot_commit=SNAPSHOT_COMMIT, noise_snapshot_date="2026-04-15",
        noisy_circuits=noisy_executor.records,
        circuit_sha256={name: file_digest(artifacts / name) for name in ("logical.qpy", "native.qpy")},
        versions={package: version(package) for package in ("numpy", "scipy", "qiskit", "qiskit-aer")},
        limitation="Calibration-based reconstruction. Original IBM compiled circuits and layout are unavailable.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path,
                        default=output_path("json", "kingston_noise_reconstruction"))
    args = parser.parse_args()
    result = run_comparison(args.directory)
    for name, run in result["runs"].items():
        print(f"{name:8} H0={run['best_x'][0]:.6f} Omega_m={run['best_x'][1]:.6f} "
              f"chi2={run['best_chi2']:.6f}")
    print(args.directory / "comparison.json")


if __name__ == "__main__":
    main()
