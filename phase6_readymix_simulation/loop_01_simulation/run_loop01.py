# run_loop01.py -- Loop 1 measure + gate over every scenario
"""  python phase6_readymix_simulation/loop_01_simulation/run_loop01.py

Generates every scenario into readymix/data/simulation/, validates it,
measures it, feeds it to the frozen core, regenerates it in a temp folder
to prove reproducibility, and checks gates G1-G7 (config.yaml). G8
(regression lock) and G9 (pytest) are run separately and recorded in
notes.md.
"""

import csv
import json
import sys
import tempfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
DEV_ROOT = HERE.parents[1]                       # 05_core_development/
sys.path.insert(0, str(DEV_ROOT))

from readymix.application.capacity_projection import solve_projection   # noqa: E402
from readymix.application.data_validator import validate_dataset        # noqa: E402
from readymix.core import frozen_core as core                           # noqa: E402
from readymix.simulation.build_dataset import generate, load_configs    # noqa: E402
from readymix.simulation.data_dictionary import FIELDS                  # noqa: E402
from readymix.simulation.stats import dataset_stats                     # noqa: E402


def files_of(d):
    return json.loads((Path(d) / "manifest.json").read_text(encoding="utf-8"))["files"]


def main():
    lc = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
    sim_cfg, scen_cfg = load_configs()
    seed = lc["seed"]
    out = DEV_ROOT / lc["output"]
    fid = core.check_freeze()
    print(f"Loop 1 Ready-Mix Simulation  seed={seed}  core freeze_id={fid}\n")

    rows, datasets, gates = [], {}, {}
    tmp = Path(tempfile.mkdtemp(prefix="loop01_"))
    for name in scen_cfg["scenarios"]:
        d = generate(name, seed, out)
        datasets[name] = d
        problems = validate_dataset(d)
        stats = dataset_stats(d)
        proj = solve_projection(d)
        again = generate(name, seed, tmp)
        reproducible = files_of(d) == files_of(again)
        rows.append({"scenario": name, "seed": seed, "validator_problems": len(problems),
                     "reproducible": reproducible, **stats,
                     **{f"proj_{k}": v for k, v in proj.items()}})
        print(f"   {name:24s} problems={len(problems)} repro={reproducible} trips={stats['trips']:3d} "
              f"load={stats['fleet_load_ratio']:.3f} delay={stats['mean_ready_delay_min']:5.1f} "
              f"traffic={stats['mean_traffic_multiplier_7_18']:.3f} events={stats['events']} "
              f"core={proj['status']}/{'OK' if proj['matches_analytic'] else 'MISMATCH'} {proj['distance_km']} km")
        for p in problems[:5]:
            print(f"      - {p}")

    by = {r["scenario"]: r for r in rows}
    f = {n: files_of(d) for n, d in datasets.items()}

    gates["G1_validates"] = all(r["validator_problems"] == 0 for r in rows)
    gates["G2_reproducible"] = all(r["reproducible"] for r in rows)
    gates["G3_shared_world"] = (
        all(f[n][k] == f["S0_normal"][k] for n in f
            for k in ("master/plants.csv", "master/vehicles.csv", "master/travel_profile.csv"))
        and all(f[n][k] == f["S0_normal"][k] for n in f if n != "S6_high_demand"
                for k in ("master/sites.csv", "orders/orders.csv")))
    gates["G4_core_accepts"] = all(r["proj_status"] == "FEASIBLE" and r["proj_validator_pass"]
                                   and r["proj_one_trip_per_route"] and r["proj_matches_analytic"]
                                   and r["proj_pairing_impossible"] for r in rows)
    gates["G5_labelled"] = (not any(s in ("REAL", "PUBLIC_SOURCE") for _, _, s, *_ in FIELDS)
                            and all(src.strip() for _, _, s, _, _, src in FIELDS if s == "ASSUMED"))
    lo, hi = sim_cfg["plausibility"]["fleet_load_ratio"]
    gates["G6_plausible_load"] = lo <= by["S0_normal"]["fleet_load_ratio"] <= hi
    t = lambda n: by[n]["mean_traffic_multiplier_7_18"]           # noqa: E731
    dl = lambda n: by[n]["mean_ready_delay_min"]                   # noqa: E731
    gates["G7_scenario_effects"] = (
        t("S1_light_traffic") < t("S0_normal") < t("S2_peak_traffic")
        and all(dl(n) > dl("S0_normal") for n in ("S3_site_delay", "S4_multi_site_delay",
                                                  "S5_pump_failure", "S7_mixed_disruption"))
        and by["S6_high_demand"]["trips"] > by["S0_normal"]["trips"]
        and "SITE_READY_LATE" in by["S8_ai_prediction_error"]["event_types"]
        and "SITE_READY_EARLY" in by["S8_ai_prediction_error"]["event_types"])

    with open(HERE / "metrics.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {HERE / 'metrics.csv'}")
    print("\nGates:")
    for g, ok in gates.items():
        print(f"   [{'PASS' if ok else 'FAIL'}] {g}")
    ok = all(gates.values())
    print(f"\nLOOP 1 (G1-G7): {'PASS' if ok else 'FAIL'}   -- G8 regression lock and G9 pytest run separately")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
