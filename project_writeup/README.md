# AEQGA Project Write-up

**Cosmological parameter estimation with an amplitude-encoded quantum genetic algorithm** · Updated November 13, 2026

Imagine turning two dials on a model of the universe. One controls how fast space is expanding today. The other controls how much matter the model contains. Each setting predicts how bright a distant exploding star should look. Which dial settings make the predictions fit real measurements best?

This project tries many settings, keeps promising ones, and uses a small quantum circuit to help suggest new ones. Its name is **Amplitude-Encoded Quantum Genetic Algorithm (AEQGA)**. We will unpack every part of that name: an *algorithm* is a recipe, *genetic* describes the way the recipe keeps and changes groups of guesses, *quantum* refers to the circuit used to make some of the new guesses, and *amplitude encoding* is how the guesses are put into that circuit.

The project is an experiment in **optimization**, the search for the best answer according to a defined score. It does not claim to measure the true universe without uncertainty, and its hardware tests do not establish a quantum speed advantage.

## Reading order

| Chapter | The question it answers |
|---|---|
| [1. The universe and the score](01-universe-and-score.md) | How can exploding stars tell us about expansion, and how do we score a guess? |
| [2. The search and the quantum circuit](02-search-and-circuit.md) | What happens during one generation, from the first guesses to the new population? |
| [3. From a simulator to real hardware](03-experiments-and-results.md) | What did we run, what did we find, and what do the plots actually mean? |
| [4. Reproduce it and read the code](04-reproduce-and-explore.md) | How do I run a small example safely, find its output, and check my understanding? |
| [Glossary](glossary.md) | What does that symbol or technical term mean again? |
| [Repository snapshot and sources](sources-and-update.md) | What changed upstream, and where can I verify the numbers? |

You need only basic algebra, percentages and the idea of a graph. Equations are accompanied by plain-language explanations and small numerical examples. Follow the [main notebook](../notebooks/AEQGA.ipynb) once the story makes sense. Check the hardware switches and read the [safe first-run instructions](04-reproduce-and-explore.md) before running all cells.

## The whole project in six steps

```text
Measurements of supernova brightness and redshift
        ↓
Predict the observations for a guessed pair [H₀, Ωₘ]
        ↓
Score the mismatch on the ordinary computer (χ²; smaller is better)
        ↓
Save the best guesses; prepare copies and fresh guesses for the circuits
        ↓
Run the circuits, count outcomes, and turn the counts into new guesses
        ↓
Repeat; compare the best guesses with a classical reference fit
```

This is a **hybrid** workflow: an ordinary computer runs the search and the astronomy calculation, while the circuit step can run on a simulator or a real quantum processor. The two computers have different jobs. That distinction is the key to interpreting the results.
