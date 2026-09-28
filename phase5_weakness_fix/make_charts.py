# make_charts.py -- Phase 5 figures from the experiment CSVs.
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = Path(__file__).resolve().parent / "results"


def rows(name):
    with open(R / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fig_v10_vs_v11():
    data = rows("v1_1_vs_v1_0.csv")
    fig, ax = plt.subplots(figsize=(10, 5))
    for r in data:
        n = int(r["customers"])
        if r["v1_0_gap_percent"]:
            ax.scatter(n, float(r["v1_0_gap_percent"]), color="tab:red", marker="o", s=40)
        else:
            ax.scatter(n, 0, color="tab:red", marker="x", s=90)
        if r["v1_1_gap_percent"]:
            ax.scatter(n, float(r["v1_1_gap_percent"]), color="tab:green", marker="o", s=40)
    ax.scatter([], [], color="tab:red", label="v1.0 OR-Tools (30 s cap)")
    ax.scatter([], [], color="tab:red", marker="x", label="v1.0: no feasible solution")
    ax.scatter([], [], color="tab:green", label="v1.1 HGS (deterministic stop)")
    ax.set_xlabel("customers")
    ax.set_ylabel("gap vs best-known (%)")
    ax.set_title("CORE-CVRP v1.0 vs v1.1 on 24 CVRPLIB instances")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(R / "v1_0_vs_v1_1_gap.png", dpi=130)


def fig_budget_rule():
    data = rows("e6_budget_rule.csv")
    fig, ax = plt.subplots(figsize=(9, 5))
    for name in dict.fromkeys(r["instance"] for r in data):
        sub = [r for r in data if r["instance"] == name and r["rule"].startswith("iter_")]
        ax.plot([int(r["iterations_used"]) for r in sub], [float(r["gap_percent"]) for r in sub],
                marker="o", label=name)
        ad = next(r for r in data if r["instance"] == name and r["rule"] == "noimp_5000_cap50k")
        ax.scatter(int(ad["iterations_used"]), float(ad["gap_percent"]), marker="*", s=200,
                   color=ax.lines[-1].get_color(), edgecolor="black", zorder=5)
    ax.set_xscale("log")
    ax.set_xlabel("HGS iterations (log)")
    ax.set_ylabel("gap vs best-known (%)")
    ax.set_title("Fixed iteration budgets (lines) vs adaptive no-improvement-5000 rule (stars)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(R / "budget_rule.png", dpi=130)


if __name__ == "__main__":
    fig_budget_rule()
    if (R / "v1_1_vs_v1_0.csv").exists():
        fig_v10_vs_v11()
    print("charts written to", R)
