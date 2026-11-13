# 1. The universe and the score

[Start here](README.md) · [Next: The search and the quantum circuit](02-search-and-circuit.md)

## The two dials

**Cosmology** is the study of the universe on its largest scales. **Expansion** means that, on average, distances between far-apart galaxies grow as space expands. At short enough cosmological distances, the simple approximation `recession speed ≈ H₀ × distance` helps describe the trend. It does not describe every nearby galaxy's individual motion, and the full project calculation does not use that straight line for distant objects.

| Dial | Meaning | Range searched in the main notebook |
|---|---|---|
| **H₀** (Hubble constant) | How fast the universe is expanding today, expressed as recession speed per unit distance in the nearby-universe approximation. | 60–80 km/s/Mpc |
| **Ωₘ** (omega-m) | The present-day density of matter, including ordinary and dark matter, divided by the critical density. It is a ratio with no units. | 0–0.5 |

An **Mpc** is a megaparsec, about 3.26 million light-years. At H₀ = 70 km/s/Mpc, the simple nearby trend says that each additional Mpc corresponds to about 70 km/s more recession speed. The **critical density** is the reference density associated with flat spatial geometry in the standard expansion equations. If Ωₘ = 0.3, matter accounts for 30% of that reference density. It does not mean 30% of the matter is dark matter.

These dials are **parameters**: numbers that specify one version of a model. The project uses **flat ΛCDM**. “Flat” describes the model's large-scale spatial geometry; Λ represents a constant dark-energy contribution; CDM means *cold dark matter*, matter that interacts gravitationally and was moving slowly enough to cluster in the model. In the simplified late-time distance calculation, the dark-energy fraction is `1 − Ωₘ`. Radiation is neglected in that calculation; it is relevant in the separate early-universe calculation. A **model assumption** is a choice like flatness that the calculation starts from, rather than a conclusion it proves.

## What we measure

A **Type Ia supernova** is a bright stellar explosion involving a white dwarf, a compact remnant of a star. Astronomers observe how its brightness changes over time; this record is a **light curve**. After correcting for features such as light-curve shape and color, Type Ia supernovae can be used as **standardizable candles**: objects with an estimated intrinsic brightness, useful for judging distances. A far-away candle looks dimmer than a nearby candle of the same intrinsic brightness.

**Redshift** measures how much light wavelengths have stretched. If a recognizable feature was emitted at 500 nanometers and is seen at 550 nanometers, its redshift is `(550 − 500) / 500 = 0.10`. Expansion changes wavelengths, and the motions of the observer and host galaxy can also affect the measurement. The main calculation uses the table's `zHD` redshift in its expansion-history calculation and `zHEL` (redshift in the Sun's frame) in a separate brightness-distance factor. These are named input columns, not two different supernovae.

Astronomers use **magnitudes**, a logarithmic scale on which smaller numbers mean brighter objects. *Apparent magnitude* is how bright something looks; *absolute magnitude*, often called **M**, is how bright it would look at a standard distance of 10 parsecs. Their difference is the **distance modulus**, written μ. It increases with distance. A logarithm turns multiplication into addition: multiplying the distance by ten increases μ by five.

The main notebook uses the **Pantheon+** collection with the **SH0ES** distance-scale calibration. SH0ES stands for *Supernovae and H₀ for the Equation of State of dark energy*. A **calibration** anchors a measurement scale to known references. For instance, distances estimated using stars called **Cepheids**, whose brightness cycles provide a distance clue, help anchor the absolute brightness of nearby supernovae. Without an absolute distance scale, a change in H₀ can be confused with a change in assumed intrinsic brightness. The main notebook uses the published calibrated distance-modulus column `MU_SH0ES` instead of freely adjusting M. It uses 1,701 light-curve rows from 1,550 distinct supernovae, so “rows” and “different explosions” are not interchangeable. [Pantheon+ data release](https://arxiv.org/abs/2112.03863) · [Pantheon+ cosmology analysis](https://arxiv.org/abs/2202.04077)

## Turning a dial setting into a prediction

1. Pick a candidate, such as `[72, 0.35]`, in the repository's order `[H₀, Ωₘ]`.
2. Use the model and each supernova's redshift to predict its **luminosity distance**. This is the distance defined by how faint an object of known light output appears, accounting for expansion.
3. Convert the predicted distance into the predicted distance modulus: `μ = 5 log₁₀(distance in Mpc) + 25`. For example, 100 Mpc gives `5 × 2 + 25 = 35`.
4. Compare the predicted and observed μ for each row. A **residual** is the difference between prediction and observation.

The code adds contributions from across the expansion history along the light's path. An **integral** is the mathematical version of adding many tiny contributions; **quadrature** is a numerical method that approximates that sum using carefully chosen sample points and weights. The main fit speeds this up with a **grid**, a list of 300 equally spaced Ωₘ values whose distance calculations are prepared in advance. A candidate uses the nearest grid point for that part of the calculation. H₀'s distance scaling is calculated directly. Using no grid makes a useful **direct-distance check**, which still uses numerical quadrature but removes the nearest-grid-point approximation. See [the actual distance code](../aeqga/likelihoods/cosmology.py) and [Pantheon+ scoring code](../aeqga/likelihoods/pantheon_problem.py).

## Scoring a guess: chi-squared

An **objective function** takes a candidate and returns a score. The project's objective is **chi-squared**, written χ² and pronounced *kai squared*. Lower χ² means closer agreement with the measurements under the stated model and measurement errors.

For a simple example, suppose a model misses two independent measurements by 0.10 and 0.40 magnitudes. If their typical uncertainties are 0.10 and 0.20, the misses are one and two uncertainty units. The simple χ² is `1² + 2² = 5`. Squaring prevents positive and negative misses from canceling, and dividing by the uncertainty gives a bigger penalty to a miss on a more precise measurement.

Real measurements are not all independent. If a telescope's brightness calibration shifts, it can move several measurements together. A **covariance matrix** is a square table that records measurement variances (uncertainties squared) on its diagonal and shared error patterns off the diagonal. Pantheon+ supplies the full **STAT+SYS** covariance: statistical uncertainty (variation in measurement) and systematic uncertainty (effects such as shared calibration). The code uses that table once; it does not add the same errors again. When reading the optional notation `χ² = rᵀ C⁻¹ r`, `r` is the list of residuals, `C` is the covariance table, and the expression means “combine the misses while accounting for both their sizes and shared errors.” The implementation uses **Cholesky factorization**, a way of breaking that table into simpler triangular tables so the calculation can be done accurately and reused. No matrix algebra is needed to follow the search.

**Fitness** is the score used to rank candidates. In biology a larger fitness might be better; here fitness is χ², so *smaller* wins. Even a good fit has nonzero residuals. With 1,701 measured rows, a raw χ² around 1,753 for this particular objective is not by itself a sign of failure.

## A fair target for the algorithm

The **classical reference minimum** is the best score found by an independent ordinary-computer calculation on the same model and data. The main configured grid gives approximately `[72.83204, 0.362876]` with χ² = 1752.90405. The code can find the best H₀ for each tested Ωₘ using the way H₀ shifts all predicted moduli together, then compare those minima. This is **profiling**: choosing the best value of one parameter while holding another fixed. The direct-distance calculation is an additional numerical check.

The **optimization gap** `Δχ² = candidate χ² − reference minimum χ²` measures how far the search is from this target in score. If a candidate scores 1753.90405, its gap is about 1. A gap near zero means a good optimizer result under the configured assumptions. It does not mean zero measurement uncertainty, or proof of the exact true H₀. Also, different pairs can score similarly: increasing one dial and decreasing the other can partly compensate. This is a **parameter trade-off**, also called a degeneracy.

## Other evidence: BAO and CMB

The notebook has a separate optional experiment using **BAO + CMB**. **Baryon acoustic oscillations (BAO)** are a characteristic spacing pattern left in the distribution of matter by sound waves in the early universe. The associated distance scale, the **sound horizon**, acts like a standard ruler. The **cosmic microwave background (CMB)** is early-universe light now seen as microwaves. Its tiny temperature variations can be summarized by a **temperature power spectrum (TT)**, showing how much variation occurs at different angular scales. A **multipole**, written ℓ, is an index for those scales: larger ℓ generally describes finer details on the sky. Planck supplies observations used by the reference implementation.

**CAMB** is a numerical program that predicts cosmological quantities, including the CMB spectrum. **PICO** is an *emulator*: a fast approximation trained to predict what a more expensive calculation would give. A trained approximation has a **training domain**, a region of inputs it is meant to handle. The public PICO model does not cover everything needed to match the paper's setup, and the exact author model and temperature-data choices are unresolved. The repository labels CAMB as a reference alternative. BAO and CMB are scored together in their own experiment; the default supernova fit does not include them. [Replication details](../docs/REPLICATION_SPEC.md)
