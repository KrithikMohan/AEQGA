"""Draw the four-panel Kingston comparison used in the poster results.

Read the scored runs and contour grid from aeqga.analysis.kingston_noise_reconstruction
and export the PNG, PDF, and SVG.
"""
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

from aeqga.paths import PROJECT_ROOT, output_path
from aeqga.visualization.scientific_plots import joint_levels

METHODS = {
    "hardware": ("IBM Kingston hardware", "#087970", "o"),
    "ideal": ("Noiseless simulator", "#6846a2", "^"),
    "noisy": ("Kingston noise model", "#a8510b", "s"),
}
INK = "#183346"
GRAY = "#516779"


def parameter_axes(ax, result, *, zoom):
    reference = result["classical_reference"]
    retained = result["retained_elites"]
    for name, (_, color, marker) in METHODS.items():
        run = result["runs"][name]
        population = np.asarray(run["final_population"])[retained:]
        ax.scatter(*population.T, s=31, marker=marker, color=color, alpha=.76,
                   linewidth=.5, edgecolor="white", zorder=4)
    ax.scatter(reference["H0"], reference["Omega_m"], color=INK, edgecolor="white",
               linewidth=.7, marker="*", s=210, zorder=6)
    ax.annotate("Classical objective minimum", (reference["H0"], reference["Omega_m"]),
                xytext=(14, -19), textcoords="offset points", fontsize=9, color=INK,
                bbox=dict(facecolor="white", edgecolor="none", alpha=.9, pad=2), zorder=8)
    # Plot the coincident markers largest to smallest so each method stays visible.
    for (name, (_, color, marker)), size in zip(METHODS.items(), (210, 106, 35), strict=True):
        ax.scatter(*result["runs"][name]["best_x"], s=size, color=color,
                   marker=marker, edgecolor="white", linewidth=.9, zorder=7)
    ax.annotate("All three retained this best fit", result["runs"]["hardware"]["best_x"],
                xytext=(14, 10), textcoords="offset points", fontsize=9, color=INK,
                bbox=dict(facecolor="white", edgecolor="none", alpha=.9, pad=2), zorder=8)
    ax.set_xlabel("Expansion rate H₀ (km/s/Mpc)")
    ax.set_ylabel("Matter density fraction Ωₘ")
    if not zoom:
        ax.set(xlim=(59.5, 80.5), ylim=(-.015, .52))
        ax.grid(color="#e4ecf0")
        ax.set_axisbelow(True)


def scores_panel(ax, result):
    reference = result["classical_reference"]["chi2"]
    retained = result["retained_elites"]
    for name, (_, color, marker) in METHODS.items():
        scores = np.sort(np.asarray(result["runs"][name]["final_chi2"])[retained:] - reference)
        ax.step(np.r_[0, scores, 13000], np.r_[0, np.arange(1, len(scores) + 1), len(scores)],
                where="post", color=color, lw=2)
        ax.scatter(scores, np.arange(1, len(scores) + 1), marker=marker,
                   color=color, s=13, zorder=4)
    ax.axvline(0, color=INK, lw=1.4)
    ax.set_xscale("symlog", linthresh=30)
    ax.set(xlim=(-4, 13000), ylim=(0, 25), yticks=(0, 6, 12, 18, 24),
           xlabel="Fit score above classical minimum (Δχ², compressed scale)",
           ylabel="Number of new candidates at or below score")
    ticks = [0, 30, 100, 300, 1000, 3000, 10000]
    ax.set_xticks(ticks, [f"{value:,}" for value in ticks])
    ax.grid(color="#e4ecf0")
    ax.set_axisbelow(True)


def best_panel(ax, result):
    reference = result["classical_reference"]["chi2"]
    retained = result["retained_elites"]
    best_new_scores = {}
    for y, (name, (label, color, marker)) in enumerate(METHODS.items()):
        run = result["runs"][name]
        final_best = run["best_chi2"] - reference
        best_new = min(run["final_chi2"][retained:]) - reference
        best_new_scores[name] = best_new
        ax.hlines(y, final_best, best_new, color=color, alpha=.55, lw=2)
        ax.scatter(final_best, y, marker=marker, s=80, color=color, zorder=4)
        ax.scatter(best_new, y, marker=marker, s=80, facecolor="white", edgecolor=color,
                   linewidth=1.7, zorder=4)
        ax.annotate(f"{final_best:.2f}", (final_best, y), xytext=(-8, 0),
                    textcoords="offset points", ha="right", va="center", fontsize=9, color=INK)
        ax.annotate(f"{best_new:.2f}", (best_new, y), xytext=(8, 0),
                    textcoords="offset points", va="center", fontsize=9, color=INK)
    ax.axvline(0, color=INK, lw=1.4)
    ax.set(xlim=(-2, max(best_new_scores.values()) + 17), ylim=(2.95, -.6),
           xlabel="Fit score above classical minimum (Δχ², lower is better)")
    ax.set_yticks(range(3), [label for label, _, _ in METHODS.values()])
    ax.grid(axis="x", color="#e4ecf0")
    ax.set_axisbelow(True)
    ax.legend(handles=[
        Line2D([], [], color=INK, marker="o", linestyle="none", label="Retained best"),
        Line2D([], [], color=INK, marker="o", markerfacecolor="white",
               linestyle="none", label="Best new candidate"),
    ], loc="lower right", frameon=False, ncol=2, fontsize=9)


def render(result, contours):
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "figure.facecolor": "#eff5f7",
        "axes.labelcolor": INK,
        "axes.edgecolor": "#a6bbc7",
        "xtick.color": GRAY,
        "ytick.color": GRAY,
        "text.color": INK,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    })
    fig, axes = plt.subplots(2, 2, figsize=(15.6, 10.6))
    fig.subplots_adjust(left=.082, right=.978, bottom=.104, top=.797, wspace=.38, hspace=.49)
    fig.text(.056, .953, "The noise model changed the search, but the best fit held",
             fontsize=25, weight="bold")
    fig.text(.057, .911, "Pantheon+ supernova fit · One update · 32 starting candidates · "
             "1,024 measurements per circuit", fontsize=12, color=GRAY)
    handles = [
        Line2D([], [], color=color, marker=marker, linestyle="none", markersize=7, label=label)
        for label, color, marker in METHODS.values()
    ]
    handles.append(Line2D([], [], color=INK, marker="*", linestyle="none", markersize=12,
                          label="Classical objective reference"))
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(.05, .884),
               frameon=False, ncol=4, fontsize=11)

    zoom, full, scores, best = axes.flat
    h0, omega, delta = (contours[key] for key in ("h0", "omega", "delta_chi2"))
    levels = joint_levels((1, 2, 3, 4, 5))
    zoom.contourf(h0, omega, np.maximum(delta, 0), levels=[0, *levels], cmap="Blues_r", alpha=.72)
    zoom.contour(h0, omega, delta, levels=levels, colors="#5886a2", linewidths=.45)
    parameter_axes(zoom, result, zoom=True)
    zoom.set(xlim=(h0.min(), h0.max()), ylim=(omega.min(), omega.max()))
    parameter_axes(full, result, zoom=False)
    full.set_ylabel("Matter density fraction Ωₘ")
    scores_panel(scores, result)
    best_panel(best, result)
    titles = [
        ("Physics fit near the classical minimum", "Darker contours indicate better fits to the supernova data."),
        ("Where the three searches proposed new candidates", "Small markers show all 24 new candidates per run, with overlaps."),
        ("How well the new candidates fit", "A curve farther left finds more low-scoring candidates."),
        ("Did a new candidate beat the retained best?", "The three runs kept the same best starting candidate."),
    ]
    for ax, (title, subtitle) in zip(axes.flat, titles, strict=True):
        ax.set_title(title, loc="left", y=1.095, size=13, weight="bold")
        ax.text(0, 1.027, subtitle, transform=ax.transAxes, fontsize=9.5, color=GRAY)
        ax.spines[["top", "right"]].set_visible(False)

    fig.text(.057, .042, "Noiseless means no device errors, with finite-shot sampling. "
             "The noisy run uses the 15 Apr 2026 Kingston snapshot and a reconstructed layout.",
             fontsize=9.5, color=GRAY)
    fig.text(.057, .021, f"IBM job {result['hardware_job_id']}. "
             "The original compiled hardware circuits and layout are unavailable.",
             fontsize=9.5, color=GRAY)
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path,
                        default=output_path("json", "kingston_noise_reconstruction"))
    args = parser.parse_args()
    result = json.loads((args.directory / "comparison.json").read_text())
    with np.load(args.directory / "contours.npz") as contours:
        fig = render(result, contours)
    name = "kingston_four_way_comparison"
    fig.savefig(output_path("png", name + ".png"), dpi=190)
    fig.savefig(output_path("pdf", name + ".pdf"))
    asset = PROJECT_ROOT / "project_writeup" / "assets" / (name + ".svg")
    fig.savefig(asset)
    plt.close(fig)
    print(asset)


if __name__ == "__main__":
    main()
