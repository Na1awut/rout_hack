# build_bks_manifest.py
"""Builds bks_manifest.json: the 24 instances this phase uses, with
their vehicle count and best-known cost, extracted from an external,
literature-sourced database -- never inferred by this project's own
code from a filename or from DIMENSION.

Source: VROOM-Project/vroom-scripts, benchmarks/CVRP/BKS.json
(https://github.com/VROOM-Project/vroom-scripts), which aggregates
Best Known Solutions for the classic E/F/M/P/X CVRP instance families
(Christofides & Eilon; Uchoa, Pecin, Pessoa, Poggi, Subramanian &
Vidal 2014; etc.). That file has 10,192 entries covering many more
instances than this project uses -- this script filters it down to
just the 24 selected here and records each one's `proven_optimal` flag
untouched, so a Gap computed later can be labelled correctly as "vs.
proven optimum" or "vs. best known (not proven optimal)".

Run once (output already committed as bks_manifest.json):
    python build_bks_manifest.py path/to/BKS.json
"""

import json
import sys
from pathlib import Path

SELECTED = {
    # tier, instance name
    "tiny":   [],  # tiny tier already covered by phase1_freeze/phase2/phase3's 4 instances
    "small":  ["E-n51-k5", "E-n76-k7", "E-n76-k10"],
    "medium": ["X-n106-k14", "X-n120-k6", "X-n143-k7", "X-n162-k11",
               "X-n186-k15", "X-n214-k11", "X-n237-k14"],
    "large":  ["X-n261-k13", "X-n298-k31", "X-n344-k43", "X-n393-k38", "X-n459-k26"],
    "stress": ["X-n513-k21", "X-n599-k92", "X-n701-k44", "X-n801-k40", "X-n936-k151"],
    "extra_tiny_for_continuity": ["E-n22-k4", "E-n23-k3", "E-n30-k3", "E-n33-k4"],
}


def main():
    if len(sys.argv) != 2:
        print("usage: python build_bks_manifest.py path/to/BKS.json")
        return 1
    with open(sys.argv[1], encoding="utf-8") as f:
        bks = json.load(f)

    manifest = {
        "source": "https://github.com/VROOM-Project/vroom-scripts "
                   "(benchmarks/CVRP/BKS.json), fetched 2026-09-28",
        "note": "vehicles and best_known_cost come from this external file, "
                "not from this project's own parsing of the .vrp filename or "
                "COMMENT line. proven_optimal is carried through unchanged "
                "from the source -- most X-instances are best-known, not proven.",
        "instances": {},
    }
    for tier, names in SELECTED.items():
        for name in names:
            entry = bks[f"{name}"]
            manifest["instances"][f"{name}.vrp"] = {
                "tier": tier,
                "customers": entry["jobs"],
                "max_vehicles": entry["vehicles"],
                "capacity": entry["capacity"],
                "best_known_cost": entry["best_known_cost"],
                "proven_optimal": entry["proven_optimal"],
            }

    out = Path(__file__).resolve().parent / "bks_manifest.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"wrote {out} with {len(manifest['instances'])} instances")


if __name__ == "__main__":
    sys.exit(main())
