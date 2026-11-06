IONQ FORTE-1 CIRCUIT-WIDTH STUDY

Results and runnable code from the completed six-width experiment. Each width
has 100 updates under official Forte-1 cloud simulator noise and an independent
100-shot local ideal control. The 29-qubit packing budget, seed 7, and analytic
M profiling are documented in results/study_plan.json and results/findings.txt.

Start with results/findings.txt and results/training_comparison.png.
results/final_parameters_vs_qubits.png shows the final H0, Omega_m, and M.
results/audit.json documents the checks on the full set of saved runs.

Reproduce on Windows in a separate Python 3.11 environment:

  cd reproduction
  python -m pip install -r requirements.txt
  python -m unittest -v test_ionq_forte test_ionq_transport_recovery test_ionq_supervisor
  python supervise_ionq_forte.py --output output/ionq_forte_29q --workers 6

Set IONQ_API_KEY in the process environment before starting the cloud run.
The supervisor resumes matching saved runs, retries transient reads and restarts
recoverable process failures. For offline analysis of a complete saved run:

  python analyze_ionq_forte_study.py --output output/ionq_forte_29q

This publication contains aggregated results, best-per-generation trajectories,
figures, audit summaries, reproduction code, pinned dependencies, and inputs.
The full candidate and measurement archives are retained locally. Cloud job
records, credentials, and machine-specific logs are excluded from publication.
SHA256SUMS.txt covers the publication files. results/original_full_archive.txt
identifies the separately retained full archive.
