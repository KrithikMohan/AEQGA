# 2. The search and the quantum circuit

[Previous: The universe and the score](01-universe-and-score.md) · [Next: Experiments and results](03-experiments-and-results.md)

## A search inspired by evolution

A **candidate**, also called an **individual**, is one pair `[H₀, Ωₘ]`. A **population** is a list of candidates. A **generation** is one update to that list. **Generation 0** is the starting list, before the first update. The **global best** is the lowest-scoring pair seen so far, not the average of the population.

A **genetic algorithm** uses ideas inspired by evolution: select strong candidates, preserve some, and produce variations. Here **crossover** and **mutation** are names for circuit operations that help create variation; they do not literally exchange DNA or swap decimal digits between two people. **Exploration** means searching new territory; **exploitation** means searching near good answers. The algorithm does both.

| Portion of a 32-candidate population | How it is made | What happens to it |
|---|---|---|
| 8 **elites** (25%) | Pick the lowest eight χ² scores. | Keep the exact pairs. They bypass the circuit. |
| 8 **elite copies** (25%) | Make a copy of each elite. | Use a circuit and then decode near the elites. |
| 16 **random candidates** (50%) | Draw new values across the allowed ranges. | Use a circuit and then decode across the full ranges. |

Drawing **uniformly** means equal-width parts of an interval are equally likely. **Elitism**, keeping the best unchanged, guarantees the best score cannot get worse if the scoring rule stays the same. It can stay flat for many updates. A lower average score for the entire population is not guaranteed, because half the proposals explore the wider search range.

**Hyperparameters** are settings of the search, rather than quantities it is trying to learn. Examples are population size, update count, shots, and the probabilities of applying gates. A **random seed** is a starting number for the computer's random-number recipe. Reusing a seed with the same code and settings helps reproduce simulation choices; it does not force real hardware to repeat its measurement results.

## A bit, a qubit and a circuit

A **bit** is an ordinary 0 or 1. A **qubit** is a quantum system with two basic measurement outcomes, also labeled 0 and 1. A qubit can be prepared in a **superposition**: a state described by an amplitude for each possible outcome. An **amplitude** is a number that contributes to the state. Its squared magnitude gives a probability when measured in the stated basis. Amplitudes can have signs and phases (angle-like parts of complex numbers); probabilities cannot be negative. When gates combine contributions, amplitudes can reinforce or cancel. This is **interference**.

The **computational basis** is the list of all standard bitstring outcomes. Two qubits have `00`, `01`, `10`, `11`; four qubits have 16 outcomes, `0000` to `1111`. A **statevector** is the list of amplitudes in that basis. **Measurement** produces one bitstring in a single execution, not the whole statevector. In the Qiskit count strings used by the project, the rightmost bit is qubit 0, so `0001` has only qubit 0 measured as 1. [Qiskit bit ordering](https://quantum.cloud.ibm.com/docs/en/qiskit/bit-ordering)

A **quantum circuit** is a sequence of operations. Each horizontal wire in a diagram follows a qubit from preparation on the left to readout on the right. A **gate** changes a quantum state in a specified way. A **controlled gate** applies a change to a target when a control qubit is in the `1` part of the basis. A **CNOT** (controlled NOT) is the controlled gate that flips its target. A **rotation** changes amplitudes using a specified angle; the axes x and y are directions in a mathematical picture of the qubit's state, not physical tracks traveled by a particle. `π/2` radians is a quarter-turn, or 90 degrees.

## Putting a list into amplitudes

**Amplitude encoding** uses the entries of a list as amplitudes after **normalization**, rescaling so their squared magnitudes add up to 1. For a two-entry example, start with `[3, 4]`. The length of the list as a vector is `√(3² + 4²) = 5`. Divide each entry by 5 to get amplitudes `[0.6, 0.8]`. Before any gates, the probabilities are `0.6² = 0.36` for `0` and `0.8² = 0.64` for `1`. If the whole input list is zero, the implementation prepares equal amplitudes instead of dividing by zero. This example explains preparation; the full population algorithm uses more entries.

**State preparation** is the actual operation that makes the desired starting state. The ordinary-computer program creates circuit instructions for it. The default `initialize` prepares a state including reset; **reset** returns a qubit to its starting state. The optional `state_preparation` route assumes qubits already start at zero and can avoid that reset operation. Either way, packing a list into amplitudes does not make every original entry readable in one shot. The gates needed to prepare a state and the shots needed to sample it are real costs.

For 32 candidates, the code uses a separate circuit for each parameter and each group of proposals. A list of 16 numbers needs four qubits because `2⁴ = 16`. A list of eight needs three because `2³ = 8`. The main measured circuit order is:

| Position | Values encoded | Logical qubits |
|---:|---|---:|
| 1 | Random H₀ values | 4 |
| 2 | Elite-copy H₀ values | 3 |
| 3 | Random Ωₘ values | 4 |
| 4 | Elite-copy Ωₘ values | 3 |

The two parameter lists are processed separately. The project does not encode a whole `(H₀, Ωₘ)` pair as one basis label. The code uses power-of-two populations of at least eight so the two proposal groups fill their basis lists exactly. [Encoding implementation](../aeqga/steps/encoding/amplitude_encoding.py)

## Changing the state and collecting measurements

For each circuit, the ordinary-computer program first chooses whether to apply **crossover**. When selected and there are at least two wires, it picks two different qubits, applies a controlled y-rotation `CRy(π/2)` one way, then applies it with control and target swapped. This mixes amplitude contributions in the two-qubit part of the state. The diagram may draw a controlled rotation using simpler gates such as CNOTs and single-qubit rotations; that is a decomposition of the same operation. **Mutation** then independently has a chance to apply a single x-rotation `Rx(π/2)` to one selected qubit. In the standard run, each choice has probability 0.5. The gates operate on amplitudes, so the output distribution can differ from the starting distribution. [Research paper, Sections 3.1–3.2](https://arxiv.org/html/2602.15459v1) · [Gate code](../aeqga/steps/genetic_operators/quantum_gates.py)

A **shot** is one preparation, gate sequence, and measurement of a circuit. One thousand twenty-four shots yield 1,024 bitstrings. A **count histogram** groups them by bitstring. If `0111` occurs 200 times, its **relative frequency** is `200/1024 ≈ 19.5%`. A histogram gives estimates of the output probabilities. A zero count means that outcome was not seen in this sample; it does not prove its true probability is zero. Variation from sampling only finitely many times is **shot noise**. It exists even with perfect gates.

## Turning counts into new candidates

**Decoding** means converting the count histogram back into ordinary numerical proposals. Each basis label is a list position, not a binary spelling of H₀ or Ωₘ. The two proposal groups use different rules:

- **Random group: full-range min–max scaling.** Find the smallest and largest counts. Put the smallest at the lower bound and the largest at the upper bound, with the other counts spread proportionally in between. For example, counts `[10, 30, 40, 20]` in the H₀ range 60–80 give `[60, 73.33, 80, 66.67]` before the lower-bound replacement described below. The count 30 is two-thirds of the way from 10 to 40, so its value is two-thirds of the way from 60 to 80.
- **Elite-copy group: square-root scaling inside a local interval.** Use the smallest and largest elite values for the parameter as the default **elite interval**. For each count, divide it by the sum of counts to get a frequency, take the square root, and use that fraction of the interval. If the interval is 70–74 and a state gets 25% of the shots, `√0.25 = 0.5`, so the decoded value is `70 + 0.5 × 4 = 72`. The square root is part of this proposal rule; it does not invert all the gates and recover the original input.

In either group, an exact lower-bound result is replaced by a uniform draw inside the appropriate interval. If the random counts are all equal, the min–max calculation would divide by zero, so the code draws that group uniformly. A zero-width elite interval stays fixed at its one value. This detail matters when comparing wider circuits: extra unseen outcomes can change how much classical random exploration the decoder performs. [Decoder code](../aeqga/steps/decoding/measurement_decoding.py)

Pair the new H₀ and Ωₘ values by index within each group, add the eight untouched elites, and score the 32 pairs again. Repeat. An **objective evaluation** is one scoring call. With 32 starting candidates and 50 updates, the main runner records `32 × (1 + 50) = 1,632` evaluations per run, including the initial population. Those calls still happen on the ordinary computer. Four measured circuits per update are 200 circuit executions, or 819,200 requested circuit-shots at 4,096 per circuit. A **circuit-shot** counts one shot of one circuit; it is not a unit of elapsed time or a billing estimate.

## How the paper fits in

The repository follows Sarracino and colleagues' design for the population split, circuit operations and decoding. It uses documented choices where details are missing, including the finite-shot budget and default elite interval. The separate **HQGA bridge** connects to the earlier hybrid quantum genetic algorithm project through an **adapter**, code that translates between interfaces. HQGA uses its own encoding and gate rules; the bridge does not turn AEQGA into HQGA or guarantee that the upstream HQGA software runs in the same environment. [Replication choices](../docs/REPLICATION_SPEC.md) · [HQGA bridge](../docs/HQGA_INTEGRATION.md)
