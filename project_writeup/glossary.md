# Glossary: symbols and terms

[Start here](README.md)

## Astronomy and the score

| Term | Meaning in this project |
|---|---|
| BAO | Baryon acoustic oscillations: a characteristic spacing in matter caused by sound waves in the early universe. A standard-ruler measurement. |
| Calibration | Anchoring a scale to a reference, such as using Cepheid distances to set the brightness scale for supernovae. |
| CAMB / PICO | CAMB calculates predictions such as the CMB temperature pattern. PICO quickly approximates such predictions within a tested range of inputs. |
| CMB / TT / ℓ | Cosmic microwave background; its temperature–temperature power spectrum; the index of an angular scale in that spectrum. |
| Critical density | Reference density associated with flat spatial geometry in the standard expansion equations. |
| Covariance | A measure of how two errors vary together. A covariance matrix records this for all pairs of measurements, including each measurement's own variance. |
| Distance modulus (μ) | A number expressing distance on the magnitude scale. Larger μ means farther away. |
| Flat ΛCDM | The model with flat spatial geometry, a constant dark-energy term Λ, and cold dark matter. |
| H₀ | The expansion-rate parameter today, in kilometers per second per megaparsec. |
| Luminosity distance | The distance inferred from the relation between an object's light output and observed brightness in the expanding universe. |
| M | Absolute magnitude: intrinsic brightness expressed as the apparent magnitude at 10 parsecs. |
| Mpc | Megaparsec: one million parsecs, approximately 3.26 million light-years. |
| Ωₘ | Today's matter density divided by the critical density. A unitless ratio. |
| Pantheon+ / SH0ES | The supernova dataset and the distance-scale calibration program used for this fit. |
| Profiling | For each setting of the main parameters, find the best allowed value of an extra parameter. |
| Redshift (z) | Fractional stretching of a wavelength. |
| Residual | Predicted value minus observed value (or the negative of this if the same sign convention is used consistently). |
| Statistical / systematic uncertainty | Random measurement variation / uncertainty from effects such as shared calibration. Both are included in the supplied STAT+SYS table. |
| Type Ia / light curve | A type of stellar explosion used as a standardizable candle / the measured brightness history of an object. |
| χ² | Chi-squared, the numerical mismatch score. Smaller is better for this search. |
| Δχ² | Candidate χ² minus the minimum χ² for the same scoring rule and data. |

## Search and measurement

| Term | Meaning in this project |
|---|---|
| AEQGA | Amplitude-Encoded Quantum Genetic Algorithm. An ordinary computer manages the search; circuits help generate proposals. |
| Candidate / individual | One proposed `[H₀, Ωₘ]` pair. |
| Classical | Here, ordinary nonquantum computation. A classical reference is the independent best fit found by ordinary calculations. |
| Convergence | Progress toward a stable or good answer. A stable answer can still be far from the minimum. |
| Elite / elitism | A best-scoring candidate / the rule that keeps it unchanged so progress is not lost. |
| Ensemble | A collection of separate runs, used to show variation in outcomes. |
| Evaluation | Scoring one candidate; different from measuring one circuit shot. |
| Fitness / objective function | The candidate's score / the calculation that returns the score. |
| Generation / update | One round of replacing proposals and scoring the new group. Generation 0 is the initial group. |
| Global best | The best candidate found up to that moment, including earlier rounds. |
| Hyperparameter | A user-chosen search setting, such as population size or number of shots. |
| Local interval / global bounds | The range near elites / the full allowed search range. |
| Optimization | Searching for a better score, such as a smaller χ². |
| Population / subpopulation | A list of candidates / one smaller group of that list. |
| Seed | A number that initializes a repeatable computer random-number sequence. |
| Uniform draw | A random choice for which equal-sized portions of the range have equal chances. |

## Quantum computing and execution

| Term | Meaning in this project |
|---|---|
| Amplitude | A signed or complex contribution to a quantum state. Its squared magnitude gives a basis-outcome probability. |
| Amplitude encoding | Normalize a list and use it as the amplitudes of the starting state. |
| Basis state / bitstring | One of the standard possible outcomes / its label made of zeros and ones. |
| Backend | The chosen simulator or device that executes a circuit. |
| Circuit / gate | A sequence of quantum operations / one such operation. |
| CNOT / CRy / Rx | Controlled bit flip / controlled y-rotation / x-rotation. AEQGA uses two reversed-direction CRy gates and a one-wire Rx mutation. |
| Counts / shot | Number of observations of each outcome / one preparation, gate sequence and measurement. |
| Crossover / mutation | The two-wire mixing step / the one-wire variation step, each applied with a chosen probability. |
| Decode | Convert measured counts into proposed parameter values. |
| Depth / width | Number of sequential circuit layers / number of qubit wires. |
| Ideal simulator | Ordinary software that calculates circuit behavior assuming perfect operations. It can still sample only a finite number of shots. |
| Interference | Combining amplitudes can reinforce some contributions and cancel others. |
| Logical / physical qubit | A wire in the algorithm / a real device site assigned to that wire. |
| Noise model | An approximation of how imperfect operations or readout change outcomes. |
| QPU | Quantum processing unit, a physical quantum device. |
| Readout | Measuring the qubits and recording ordinary bits. |
| Reset | Return a qubit to its starting state. |
| Shot noise | Random variation because we took a finite number of measurements. |
| Statevector / superposition | List of quantum amplitudes / a state with contributions from multiple basis states. |
| Transpile / native gates | Rewrite a circuit for a backend / operations the backend directly supports. |
| TVD | Total variation distance: half the sum of absolute probability differences. Zero means the two distributions agree. |

## Plots, comparisons and records

| Term | Meaning in this project |
|---|---|
| Bias | Mean signed difference from the specified fitted reference. |
| Checkpoint / replay | A saved progress record / using archived inputs or counts again without resubmitting them. |
| Contour | A line joining locations with the same value. Check whether that value is a fit score or an estimated density. |
| Degeneracy | Different parameter choices produce nearly the same predicted observations or scores. |
| KDE | Kernel density estimation: smooth a set of points to show where they tend to concentrate. |
| Likelihood | How well a model setting explains the data under the specified error model. For the fixed Gaussian error calculation here, smaller χ² gives higher likelihood. |
| MAE / RMSE | Mean absolute error / root mean squared error. The second gives larger misses more weight. |
| Median / percentile | Middle value / a cutoff with a specified fraction of values at or below it. |
| Monte Carlo | Using repeated random simulations to estimate typical outcomes or variation. |
| Posterior | A probability distribution for parameters after combining observations with prior assumptions in Bayesian statistics. An optimizer's endpoint scatter is not automatically a posterior. |
| Provenance / fingerprint | Evidence about the inputs, code and settings behind a result / a content-based identifier used to check that evidence matches. |
| Reference / threshold | A comparison target / a chosen cutoff such as Δχ² < 2.30. |
| Wall time / QPU time | Time on an ordinary clock / device usage time as reported by the service, when available. |
| Wilson interval | An uncertainty interval for the fraction of independent trials that met a specified criterion. |
