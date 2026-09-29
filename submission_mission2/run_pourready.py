"""Self-created case: PourReady ready-mix dispatch (simulated world).

    python run_pourready.py                     # S4 multi-site delay, day 9101 (~10 s)
    python run_pourready.py --all               # all 9 scenarios, day 9101 (~1 min)
    python run_pourready.py --scenario S6_high_demand --day 9105

For each scenario it regenerates the simulated day from its seeds (world_seed
42, day seed), runs 3 dispatch policies, validates every executed day, and
writes KPIs plus per-truck routes. When the day is one of the evaluation days
(9101-9110) it also checks the run against the recorded Phase 9 result
(log sha256 must be identical).
"""
import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from readymix.ai.predictor import SiteReadyPredictor                  # noqa: E402
from readymix.application.buffered_dispatch import BufferedDispatch   # noqa: E402
from readymix.application.dispatch_policies import StaticPlanned      # noqa: E402
from readymix.application.execution_validator import validate_execution  # noqa: E402
from readymix.application.fleet_check import check_fleet              # noqa: E402
from readymix.application.impact import breakdown, load_factors, monetize  # noqa: E402
from readymix.application.kpi import compute_kpis                     # noqa: E402
from readymix.simulation.build_dataset import generate, load_configs  # noqa: E402
from readymix.simulation.executor import run_day                      # noqa: E402

P9 = ROOT / "phase9_baseline_comparison" / "iteration_02"
OUT = ROOT / "results" / "pourready"
POLICIES = ["A_static_planned", "B_dynamic_buffered", "C_ai_rolling_buffered"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="S4_multi_site_delay")
    ap.add_argument("--day", type=int, default=9101)
    ap.add_argument("--all", action="store_true", help="run all 9 scenarios")
    args = ap.parse_args()

    cfg = json.loads((P9 / "config.json").read_text())
    sel = json.loads((P9 / "selection.json").read_text())
    common = {k: cfg[k] for k in ("refresh_min", "step_min", "waiting_weight", "late_weight")}
    recorded = {(int(r["seed"]), r["scenario"], r["policy"]): r for r in csv.DictReader(open(P9 / "metrics.csv"))}
    model = SiteReadyPredictor(cfg["model"])
    factors = load_factors()["value"]
    _, sc = load_configs()
    scenarios = sc["scenarios"] if args.all else [args.scenario]

    OUT.mkdir(parents=True, exist_ok=True)
    rows, all_ok = [], True
    print(f"world_seed {cfg['world_seed']} · day {args.day} · step {cfg['step_min']} min · AI refresh {cfg['refresh_min']} min · "
          f"buffers B {sel['B_dynamic_buffered']['first_buffer_min']}/{sel['B_dynamic_buffered']['next_buffer_min']} "
          f"C {sel['C_ai_rolling_buffered']['first_buffer_min']}/{sel['C_ai_rolling_buffered']['next_buffer_min']} min\n")
    for scenario in scenarios:
        root = generate(scenario, args.day, OUT / "datasets", world_seed=cfg["world_seed"])
        pre = check_fleet(root)
        make = {"A_static_planned": lambda: StaticPlanned(cfg["step_min"]),
                "B_dynamic_buffered": lambda: BufferedDispatch(None, sel["B_dynamic_buffered"]["first_buffer_min"],
                                                               sel["B_dynamic_buffered"]["next_buffer_min"], **common),
                "C_ai_rolling_buffered": lambda: BufferedDispatch(model, sel["C_ai_rolling_buffered"]["first_buffer_min"],
                                                                  sel["C_ai_rolling_buffered"]["next_buffer_min"], **common)}
        print(f"{scenario} · fleet pre-check: {pre['status']} — {pre['message']}")
        for name in POLICIES:
            result = run_day(root, make[name](), cfg["step_min"])
            issues = validate_execution(result, root)
            k = compute_kpis(result, root)
            money = monetize(breakdown(result["log"], root), factors)
            log = json.dumps(result["log"], sort_keys=True)
            sha = hashlib.sha256(log.encode()).hexdigest()
            rec = recorded.get((args.day, scenario, name))
            match = None if rec is None else (rec["log_sha256"] == sha)
            all_ok &= not issues and match is not False
            (OUT / f"{scenario}_{args.day}_{name}_log.json").write_text(log)
            write_routes(OUT / f"{scenario}_{args.day}_{name}_routes.csv", result)
            rows.append(dict(scenario=scenario, day=args.day, policy=name, valid=not issues,
                             trips=k["trips"], delivered=k["delivered_trips"], unserved=k["unserved_trips"],
                             truck_wait_min=k["total_waiting_min"], site_idle_min=k["site_idle_min"],
                             on_time_rate=k["on_time_rate"], pour_gaps_over_30=k["pour_gaps_over_30"],
                             fuel_l=k["fuel_liters"], co2_kg=round(money["co2_kg"], 1),
                             cost_thb=round(money["cost_proxy_thb"]), log_sha256=sha, matches_phase9=match))
            print(f"   {name:22s} valid {not issues}  delivered {k['delivered_trips']}/{k['trips']}  "
                  f"truck wait {k['total_waiting_min']:4d}  site idle {k['site_idle_min']:4d}  on-time {k['on_time_rate']:.3f}  "
                  f"cost {money['cost_proxy_thb']:8,.0f} THB  phase9 {'match' if match else ('-' if match is None else 'DIFF')}")
    with open(OUT / "summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {OUT / 'summary.csv'}, per-policy route tables and logs · all valid and reproduced: {all_ok}")
    return 0 if all_ok else 1


def write_routes(path, result):
    """One row per delivered truckload: which truck, which site, and when."""
    trips = {t["trip_id"]: t for t in result["plan"].trips}
    rows = []
    for tid, lg in result["log"].items():
        t = trips[tid]
        row = dict(trip=tid, order=t["order_id"], site=t["site_id"], volume_m3=t["volume_m3"], truck=lg.get("truck", ""))
        for key in ("released", "load_start", "depart", "arrive", "unload_start", "unload_end", "back"):
            v = lg.get(key)
            row[key] = "" if v is None else f"{v // 60:02d}:{v % 60:02d}"
        row["status"] = "delivered" if "unload_end" in lg else "unserved"
        rows.append(row)
    rows.sort(key=lambda r: (r["truck"] == "", r["truck"], r["load_start"]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    sys.exit(main())
