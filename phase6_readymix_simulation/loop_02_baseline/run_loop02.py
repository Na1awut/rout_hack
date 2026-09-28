# run_loop02.py -- Loop 2 measure + gate: non-AI baselines on every scenario
"""  python phase6_readymix_simulation/loop_02_baseline/run_loop02.py

Needs the Loop 1 datasets (python -m readymix.simulation.build_dataset
--scenario all); the S0 seed panel is generated here if missing. Writes
metrics.csv, seed_panel.csv and one trip log per run in logs/.
"""

import csv
import hashlib
import json
import math
import statistics as st
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
DEV_ROOT = HERE.parents[1]                       # 05_core_development/
sys.path.insert(0, str(DEV_ROOT))

from readymix.application.dispatch_policies import ReactiveRule, StaticPlanned   # noqa: E402
from readymix.application.execution_validator import validate_execution          # noqa: E402
from readymix.application.kpi import compute_kpis                                # noqa: E402
from readymix.simulation.build_dataset import DEFAULT_OUT, generate, load_configs  # noqa: E402
from readymix.simulation.executor import run_day                                 # noqa: E402

POLICIES = {"A_static_planned": StaticPlanned, "R_reactive_rule": ReactiveRule}
LOG_COLS = ["trip_id", "truck", "released", "load_start", "depart", "arrive", "unload_start", "unload_end",
            "back", "free", "travel_out", "travel_back", "unload_dur"]


def hhmm(v):
    return "" if v is None else f"{v // 60:02d}:{v % 60:02d}"


def log_hash(log):
    return hashlib.sha256(json.dumps(log, sort_keys=True).encode()).hexdigest()[:12]


def run(d, pname, step):
    r = run_day(d, POLICIES[pname](), step)
    again = run_day(d, POLICIES[pname](), step)
    k = compute_kpis(r, d)
    problems = validate_execution(r, d)
    return r, k, problems, log_hash(r["log"]) == log_hash(again["log"])


def main():
    lc = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
    _, scen_cfg = load_configs()
    step = lc["step_minutes"]
    (HERE / "logs").mkdir(exist_ok=True)
    print(f"Loop 2 Non-AI Baseline  seed={lc['seed']}  step={step} min\n")

    rows = []
    for name in scen_cfg["scenarios"]:
        d = DEFAULT_OUT / f"{name}_seed{lc['seed']}"
        if not d.exists():
            d = generate(name, lc["seed"])
        for pname in lc["policies"]:
            r, k, problems, repro = run(d, pname, step)
            rows.append({"scenario": name, "policy": pname, "seed": lc["seed"], "execution_problems": len(problems),
                         "reproducible": repro, "log_sha256_12": log_hash(r["log"]), **k})
            with open(HERE / "logs" / f"{name}__{pname}.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=LOG_COLS, lineterminator="\n")
                w.writeheader()
                for tid, lg in r["log"].items():
                    w.writerow({c: (tid if c == "trip_id" else lg.get(c, "") if c in ("truck", "travel_out",
                                "travel_back", "unload_dur") else hhmm(lg.get(c))) for c in LOG_COLS})
            print(f"   {name:24s} {pname:17s} ok={len(problems) == 0} repro={repro} "
                  f"served={k['delivered_trips']}/{k['trips']} wait={k['total_waiting_min']:4d} "
                  f"idle={k['site_idle_min']:5d} on_time={k['on_time_rate']:.3f} util={k['fleet_utilization']:.3f} "
                  f"fuel={k['fuel_liters']:7.1f}")
            for p in problems[:3]:
                print(f"      - {p}")

    panel = []
    sp = lc["seed_panel"]
    for seed in sp["seeds"]:
        d = DEFAULT_OUT / f"{sp['scenario']}_seed{seed}"
        if not d.exists():
            d = generate(sp["scenario"], seed)
        for pname in lc["policies"]:
            r, k, problems, repro = run(d, pname, step)
            panel.append({"scenario": sp["scenario"], "seed": seed, "policy": pname,
                          "execution_problems": len(problems), "reproducible": repro, **k})

    for fname, data in (("metrics.csv", rows), ("seed_panel.csv", panel)):
        with open(HERE / fname, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(data)

    print("\nS0 seed panel (mean over seeds, min-max):")
    for pname in lc["policies"]:
        ps = [x for x in panel if x["policy"] == pname]
        for key in ("total_waiting_min", "site_idle_min", "on_time_rate", "fleet_utilization", "fuel_liters"):
            vals = [x[key] for x in ps]
            print(f"   {pname:17s} {key:18s} {st.mean(vals):9.3f}  [{min(vals)} .. {max(vals)}]")

    by = {(r["scenario"], r["policy"]): r for r in rows}
    A = lambda s: by[(s, "A_static_planned")]                      # noqa: E731
    kpi_keys = [k for k in rows[0] if k not in ("co2_kg",)]
    gates = {
        "G1_execution_valid": all(r["execution_problems"] == 0 for r in rows + panel),
        "G2_reproducible": all(r["reproducible"] for r in rows + panel),
        "G5_complete": all(r[k] is not None and not (isinstance(r[k], float) and math.isnan(r[k]))
                           for r in rows for k in kpi_keys),
        "G6_baseline_sane": (A("S0_normal")["unserved_trips"] == 0 and A("S0_normal")["on_time_rate"] >= 0.70
                             and (A("S6_high_demand")["unserved_trips"] > 0
                                  or A("S6_high_demand")["on_time_rate"] < A("S0_normal")["on_time_rate"])
                             and all(A(s)["total_waiting_min"] >= A("S0_normal")["total_waiting_min"]
                                     for s in ("S3_site_delay", "S4_multi_site_delay", "S5_pump_failure",
                                               "S7_mixed_disruption"))),
    }
    print("\nGates:")
    for g, ok in gates.items():
        print(f"   [{'PASS' if ok else 'FAIL'}] {g}")
    ok = all(gates.values())
    print(f"\nLOOP 2 (G1, G2, G5, G6): {'PASS' if ok else 'FAIL'}   -- G3/G4 in pytest, G7 run separately")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
