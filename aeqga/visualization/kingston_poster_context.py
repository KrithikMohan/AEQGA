"""Draw the packing diagram and separate historical noise study for poster context."""
import ast
import csv
import hashlib
from html import escape
from io import StringIO
import json
from pathlib import Path
import struct
import subprocess
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from aeqga.paths import PROJECT_ROOT

NOISE_COMMIT = "ebeb6ba28a6bea1f01c7ef9ba1ce06d3cf5f3fe2"
NOISE_CSV = "noise_validation/results/ibm_device_noise_validation/training_results.csv"
SVG_NS = "{http://www.w3.org/2000/svg}"
NAVY, MUTED = "#122d40", "#496171"
TEAL, PURPLE, AMBER = "#007b73", "#6846a2", "#a95308"


def read_population(archive, name):
    # The historical archive contains simple little-endian NumPy v1 matrices.
    with archive.open(name + ".npy") as stream:
        if stream.read(8) != b"\x93NUMPY\x01\x00":
            raise ValueError(f"Unexpected NumPy format for {name}")
        header = ast.literal_eval(stream.read(int.from_bytes(stream.read(2), "little")).decode())
        if header != {"descr": "<f8", "fortran_order": False, "shape": (32, 2)}:
            raise ValueError(f"Unexpected population matrix for {name}")
        pairs = list(struct.iter_unpack("<dd", stream.read()))
        if len(pairs) != 32:
            raise ValueError(f"Wrong population size for {name}")
        return pairs


class Figure:
    def __init__(self):
        self.parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="1000" '
                      'viewBox="0 0 1440 1000" role="img" aria-labelledby="title desc">',
                      '<title id="title">From quantum measurements to a supernova fit</title>',
                      '<desc id="desc">Archived IBM hardware and ideal results land on the same '
                      'best fit. A separate model study shows shifts in matter density, and '
                      'a schematic shows how subpopulations are packed onto qubits.</desc>',
                      '<g font-family="DejaVu Sans, sans-serif">']

    def rect(self, x, y, width, height, fill, radius=0):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
                          f'rx="{radius}" fill="{fill}"/>')

    def text(self, x, y, content, size=16, color=NAVY, bold=False, anchor="start"):
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
                          f'font-weight="{700 if bold else 400}" text-anchor="{anchor}">'
                          f'{escape(content)}</text>')

    def line(self, x1, y1, x2, y2, color="#dbe5ea", width=1):
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                          f'stroke="{color}" stroke-width="{width}"/>')

    def dot(self, x, y, radius, fill, stroke="none", width=0):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{fill}" '
                          f'stroke="{stroke}" stroke-width="{width}"/>')

    def finish(self, output):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join([*self.parts, "</g></svg>"]), encoding="utf-8")


def hardware_panel(fig):
    audit = json.loads((PROJECT_ROOT / "docs/PR10_COMPATIBILITY.json").read_text())
    generation = audit["generation"]
    archive_path = "outputs/json/ibm_generation_01/population_comparison.npz"
    archive_file = PROJECT_ROOT / archive_path
    if hashlib.sha256(archive_file.read_bytes()).hexdigest() != audit["artifact_sha256"][archive_path]:
        raise ValueError("Population archive differs from the audited record")
    with ZipFile(archive_file) as archive:
        hardware = read_population(archive, "hardware_final")
        ideal = read_population(archive, "simulator_final")
    best = tuple(generation["best_x"])
    if (best != tuple(generation["simulator_best_x"]) or best not in hardware[:8]
            or hardware[:8] != ideal[:8]):
        raise ValueError("Unexpected historical best fit or retained candidates")
    reference = generation["configured_classical_reference"]

    source = PROJECT_ROOT / "outputs/svg/notebook_sne_likelihood.svg"
    provenance = json.loads((PROJECT_ROOT / "outputs/json/notebook_sne_likelihood_figure_provenance.json").read_text())
    objective = provenance["experiment"]["provenance"]
    if any(reference[key] != objective[key] for key in ("selection", "redshift", "grid_size")):
        raise ValueError("Likelihood objective differs from the audited Kingston objective")
    expected = next(item["sha256"] for item in provenance["exports"] if item["path"].endswith(source.name))
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Likelihood SVG differs from the archived figure with calibrated axes")
    source_svg = ET.fromstring(raw)
    contours = source_svg.find(".//*[@id='QuadContourSet_1']")
    bounds = source_svg.find(f".//{SVG_NS}clipPath/{SVG_NS}rect").attrib
    sx, sy, sw, sh = (float(bounds[key]) for key in ("x", "y", "width", "height"))
    left, top, width, height = 132, 240, 595, 332

    def coordinates(hubble, matter):
        # SVG coordinates at two labeled ticks on each original linear axis.
        source_x = 68.703872 + (hubble - 71.0) * (120.020609 - 68.703872) / 0.5
        source_y = 305.764049 + (matter - 0.25) * (244.572474 - 305.764049) / 0.05
        return left + (source_x - sx) * width / sw, top + (source_y - sy) * height / sh

    fig.rect(40, 145, 725, 557, "#ffffff", 18)
    fig.text(66, 185, "Where did the hardware fit land?", 26, bold=True)
    fig.text(66, 215, "Pantheon+ likelihood contours · 1 update · 32 candidates per run", 16, MUTED)
    fig.rect(left, top, width, height, "#f7fafb")
    fig.parts.append(f'<svg x="{left}" y="{top}" width="{width}" height="{height}" '
                     f'viewBox="{sx} {sy} {sw} {sh}" preserveAspectRatio="none" overflow="hidden">')
    for path in contours.findall(f"{SVG_NS}path"):
        fig.parts.append(f'<path d="{path.attrib["d"]}" style="{path.attrib["style"]}"/>')
    fig.parts.append("</svg>")
    for value in (71, 72, 73, 74):
        x, _ = coordinates(value, 0)
        fig.line(x, top + height, x, top + height + 5, MUTED)
        fig.text(x, top + height + 22, str(value), 14, MUTED, anchor="middle")
    for value in (0.25, 0.30, 0.35, 0.40, 0.45):
        _, y = coordinates(71, value)
        fig.line(left - 5, y, left, y, MUTED)
        fig.text(left - 11, y + 5, f"{value:.2f}", 14, MUTED, anchor="end")
    fig.text(64, 260, "Ωₘ", 19, bold=True)
    fig.text(428, 618, "Expansion rate H₀ (km/s/Mpc)", 15, MUTED, anchor="middle")
    visible_counts = []
    for population, color in ((ideal, PURPLE), (hardware, TEAL)):
        visible = 0
        for point in population[8:]:
            x, y = coordinates(*point)
            if left <= x <= left + width and top <= y <= top + height:
                fig.dot(x, y, 4, color, "#ffffff", 0.8)
                visible += 1
        visible_counts.append(visible)
    x, y = coordinates(reference["H0"], reference["Omega_m"])
    fig.dot(x, y, 7, NAVY, "#ffffff", 1.5)
    fig.line(x + 8, y, x + 105, y, NAVY)
    fig.rect(x + 107, y - 14, 146, 25, "#ffffff", 5)
    fig.text(x + 115, y + 4, "Classical best fit", 14, NAVY, True)
    x, y = coordinates(*best)
    fig.dot(x, y, 10, TEAL, "#ffffff", 1.5)
    fig.dot(x, y, 5, PURPLE, "#ffffff", 1)
    fig.text(x + 16, y + 1, "Hardware and ideal tie", 16, NAVY, True)
    fig.text(x + 16, y + 23, f"Ωₘ = {best[1]:.3f}  ·  Δχ² = +{generation['delta_chi2']:.2f}", 14, MUTED)
    fig.dot(76, 646, 5, TEAL)
    fig.text(89, 651, f"Kingston QPU ({visible_counts[1]}/24 new candidates in view)", 14)
    fig.dot(424, 646, 5, PURPLE)
    fig.text(437, 651, f"Ideal simulation ({visible_counts[0]}/24 in view)", 14)
    fig.text(66, 679, "Both retained the best starting candidate. Darker contours indicate better fits.", 14, MUTED)


def noise_panel(fig):
    archived = subprocess.check_output(
        ["git", "show", f"{NOISE_COMMIT}:{NOISE_CSV}"], cwd=PROJECT_ROOT, text=True)
    runs = {(int(row["population"]), int(row["seed"]), row["mode"]): float(row["Omega_m"])
            for row in csv.DictReader(StringIO(archived)) if row["device"] == "kingston"}
    fig.rect(785, 145, 615, 557, "#ffffff", 18)
    fig.text(810, 185, "How did modeled noise shift Ωₘ?", 25, bold=True)
    fig.text(810, 215, "Separate simulator study · 100 updates · 1,024 shots per circuit", 15, MUTED)
    fig.dot(816, 242, 5, "#ffffff", PURPLE, 2.5)
    fig.text(829, 247, "Ideal", 14)
    fig.dot(900, 242, 5, AMBER)
    fig.text(913, 247, "With Kingston calibration noise", 14)
    fig.text(810, 278, "Candidates", 13, MUTED, True)
    fig.text(914, 278, "Seed", 13, MUTED, True)

    def plot_x(value):
        return 963 + (value - 0.28) * 395 / 0.14

    for tick in (0.28, 0.30, 0.32, 0.34, 0.36, 0.38, 0.40, 0.42):
        x = plot_x(tick)
        fig.line(x, 286, x, 595)
        fig.text(x, 615, f"{tick:.2f}", 13, MUTED, anchor="middle")
    shifts = []
    for index, count in enumerate((8, 16, 32, 64)):
        start = 302 + index * 76
        fig.text(818, start + 27, str(count), 17, bold=True)
        for offset, seed in enumerate((7, 17, 27)):
            y = start + offset * 21
            ideal, noisy = (runs[count, seed, mode] for mode in ("ideal", "noisy"))
            shifts.append(noisy - ideal)
            fig.text(934, y + 4, str(seed), 12, MUTED, anchor="end")
            fig.line(plot_x(ideal), y, plot_x(noisy), y, "#9aabb5", 2)
            fig.dot(plot_x(ideal), y, 5.5, "#ffffff", PURPLE, 2)
            fig.dot(plot_x(noisy), y, 3.2, AMBER)
    fig.text(1160, 640, "Final matter density fraction Ωₘ", 15, MUTED, anchor="middle")
    fig.text(810, 665, f"Noise shifted Ωₘ lower in {sum(s < 0 for s in shifts)} of {len(shifts)} matched pairs.", 16, bold=True)
    fig.text(810, 686, "This study also fit supernova brightness and used a different data selection.", 13, MUTED)


def packing_panel(fig):
    fig.rect(40, 722, 1360, 211, "#ffffff", 18)
    fig.text(66, 760, "Parallel qubit packing", 26, bold=True)
    fig.text(66, 791, "Each four-qubit block handles a small group", 16)
    fig.text(66, 815, "of candidates. The best candidates are selected", 16)
    fig.text(66, 839, "across all groups before the next update.", 16)
    fig.text(66, 891, "Illustrated with the Marrakesh simulator layout.", 14, MUTED)
    for group in range(39):
        column, row = group % 13, group // 13
        x, y = 536 + column * 63, 758 + row * 39
        used = group < 38
        fig.rect(x, y, 55, 27, "#d8efec" if used else "#edf2f5", 5)
        for bit in range(4):
            fig.dot(x + 9 + bit * 12, y + 13.5, 3.5, TEAL if used else "#acbdc7")
    fig.text(536, 903, "38 connected groups × 4 qubits = 152 of 156 qubits used  ·  608 candidates per update", 16, bold=True)


def main():
    fig = Figure()
    fig.rect(0, 0, 1440, 1000, "#eff5f7")
    fig.text(44, 44, "AEQGA  /  SUPERNOVA COSMOLOGY", 15, TEAL, True)
    fig.text(42, 95, "From quantum measurements to a supernova fit", 38, bold=True)
    fig.text(44, 123, "Ωₘ is the fraction of the universe’s energy density in matter. Δχ² is the increase in fit score above the classical minimum.", 16, MUTED)
    hardware_panel(fig)
    noise_panel(fig)
    packing_panel(fig)
    fig.text(45, 962, "Sources  Kingston job db5r25imb58s738at2v0 and PR #10 audit · Pantheon+ likelihood archive · IBM noise validation · Marrakesh layout study", 13, MUTED)
    fig.text(45, 983, "The original Kingston compiled circuits are unavailable. Packing was studied in simulation.", 13, MUTED)
    fig.finish(PROJECT_ROOT / "project_writeup/assets/kingston_poster_physics.svg")


if __name__ == "__main__":
    main()
