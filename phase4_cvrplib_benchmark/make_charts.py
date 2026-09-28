# make_charts.py
"""Turns the two experiment CSVs into the charts PLAN.md's Phase 4
section asks for: Instance Size vs Runtime, Instance Size vs Gap, and
the solution_limit diminishing-returns curve. Run after both
run_breadth.py and run_limit_sweep.py have produced their CSVs.
"""

import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def chart_size_vs_gap_and_runtime():
    rows = read_csv(RESULTS / "experiment_a_breadth.csv")
    sizes = [int(r["customers"]) for r in rows]
    gaps = [float(r["gap_percent"]) if r["gap_percent"] else None for r in rows]
    times = [float(r["runtime_sec"]) for r in rows]
    reached = [r["reached_solution_limit"] == "True" for r in rows]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    for x, y, r in zip(sizes, gaps, reached):
        if y is None:
            continue
        ax1.scatter(x, y, color="tab:green" if r else "tab:red", s=40)
    ax1.set_xlabel("Customers")
    ax1.set_ylabel("Gap vs best-known (%)")
    ax1.set_title(f"Instance Size vs Gap\n(fixed {rows[0].get('runtime_sec','?')}... "
                   f"30s budget; green=reached solution_limit, red=time-capped)")
    ax1.grid(alpha=0.3)

    ax2.scatter(sizes, times, color="tab:blue", s=40)
    ax2.axhline(30, color="gray", linestyle="--", linewidth=1, label="30s fixed cap")
    ax2.set_xlabel("Customers")
    ax2.set_ylabel("Runtime (s)")
    ax2.set_title("Instance Size vs Runtime")
    ax2.legend()
    ax2.grid(alpha=0.3)

    fig.tight_layout()
    out = RESULTS / "size_vs_gap_and_runtime.png"
    fig.savefig(out, dpi=130)
    print(f"wrote {out}")


def chart_solution_limit_sweep():
    rows = read_csv(RESULTS / "experiment_b_limit_sweep.csv")
    instances = sorted(set(r["instance"] for r in rows))

    fig, ax = plt.subplots(figsize=(8, 5))
    for name in instances:
        sub = [r for r in rows if r["instance"] == name]
        sub.sort(key=lambda r: int(r["solution_limit"]))
        limits = [int(r["solution_limit"]) for r in sub]
        gaps = [float(r["gap_percent"]) for r in sub]
        reached = [r["reached_limit"] == "True" for r in sub]
        ax.plot(limits, gaps, marker="o", label=name)
        for x, y, r in zip(limits, gaps, reached):
            if not r:
                ax.scatter([x], [y], marker="x", color="red", s=80, zorder=5)

    ax.set_xlabel("solution_limit")
    ax.set_ylabel("Gap vs best-known (%)")
    ax.set_title("Diminishing returns: Gap vs solution_limit\n(red X = safety cap hit before reaching that limit)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = RESULTS / "solution_limit_sweep.png"
    fig.savefig(out, dpi=130)
    print(f"wrote {out}")


if __name__ == "__main__":
    chart_solution_limit_sweep()
    if (RESULTS / "experiment_a_breadth.csv").exists():
        chart_size_vs_gap_and_runtime()
    else:
        print("experiment_a_breadth.csv not ready yet -- run run_breadth.py first")
