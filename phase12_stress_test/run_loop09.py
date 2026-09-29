"""Loop 9: stress scenarios + deliberate faults. Everything goes through
guarded code paths; any exception that escapes is itself recorded as a crash.
"""
import csv
import hashlib
import json
import math
import shutil
import sys
import traceback
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from readymix.ai.predictor import SiteReadyPredictor
from readymix.application.buffered_dispatch import BufferedDispatch
from readymix.application.dispatch_policies import StaticPlanned
from readymix.application.execution_validator import validate_execution
from readymix.application.fleet_check import check_fleet
from readymix.application.kpi import compute_kpis
from readymix.application.safe_dispatch import run_safely
from readymix.simulation.build_dataset import SIM_CFG, generate, load_configs
from readymix.simulation.executor import run_day

CFG = json.loads((HERE / "config.json").read_text())
SEL = json.loads((ROOT / CFG["buffers_from"]).read_text())
SCEN = ROOT / CFG["scenario_file"]
FLEET10 = ROOT / CFG["fleet_shortage_simulation_file"]
COMMON = dict(refresh_min=15, step_min=5, waiting_weight=1, late_weight=1)
_model = None


def buf(name):
    return dict(first_buffer_min=SEL[name]["first_buffer_min"], next_buffer_min=SEL[name]["next_buffer_min"])


def make_dataset(scenario, seed, out):
    sim = FLEET10 if scenario == "X7_fleet_shortage" else SIM_CFG
    return generate(scenario, seed, out, sim_path=sim, scen_path=SCEN, world_seed=CFG["world_seed"])


def stress_task(task):
    global _model
    if _model is None:
        _model = SiteReadyPredictor("site_ready_v3.joblib")
    scenario, seed = task
    rows = []
    try:
        root = make_dataset(scenario, seed, HERE / "datasets")
        pre = check_fleet(root)
    except Exception as e:
        return [dict(scenario=scenario, seed=seed, policy="-", status="ERROR", error=repr(e))]
    policies = {"A_static_planned": lambda: StaticPlanned(5),
                "B_dynamic_buffered": lambda: BufferedDispatch(None, **buf("B_dynamic_buffered"), **COMMON),
                "C_ai_rolling_buffered": lambda: BufferedDispatch(_model, **buf("C_ai_rolling_buffered"), **COMMON)}
    for name, make in policies.items():
        row = dict(scenario=scenario, seed=seed, policy=name, preflight=pre["status"],
                   preflight_extra_trucks=pre["extra_trucks"], preflight_forecast_unserved=pre["forecast_unserved"],
                   preflight_message=pre["message"])
        try:
            pol = make()
            result = run_day(root, pol, 5)
            issues = validate_execution(result, root)
            k = compute_kpis(result, root)
            row.update(status="INVALID_PLAN" if issues else "RAN", issues=len(issues),
                       predictor_failures=getattr(pol, "failures", 0),
                       log_sha256=hashlib.sha256(json.dumps(result["log"], sort_keys=True).encode()).hexdigest(),
                       operational_score_min=k["total_waiting_min"] + k["site_idle_min"] + 1000 * k["unserved_trips"],
                       **{f: k[f] for f in ("trips", "unserved_trips", "total_waiting_min", "site_idle_min",
                                            "on_time_rate", "fuel_liters", "pour_gaps_over_30")})
        except Exception as e:
            row.update(status="ERROR", error=repr(e), trace=traceback.format_exc(limit=3))
        rows.append(row)
    print(scenario, seed, pre["status"], [r["status"] for r in rows], flush=True)
    return rows


# ---------------------------------------------------------------- faults
def _read(p):
    with open(p, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def _write(p, fields, rows):
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def refresh_manifest(root):
    """A legitimate upstream data update: files changed AND the manifest says so."""
    m = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    m["files"] = {rel: hashlib.sha256((root / rel).read_bytes()).hexdigest() for rel in m["files"]}
    m["fault_injected"] = True
    (root / "manifest.json").write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")


def filter_csv(root, rel, keep):
    f, rows = _read(root / rel)
    _write(root / rel, f, [r for r in rows if keep(r)])


class CrashingPredictor:
    def predict(self, *a, **k):
        raise RuntimeError("injected predictor crash")


class GarbagePredictor:
    def __init__(self, inner):
        self.inner = inner

    def predict(self, *a, **k):
        p = dict(self.inner.predict(*a, **k))
        p.update(predicted_ready_time="not-a-time", confidence=math.nan)
        return p


def build_fault(name, base, work):
    root = work / name
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(base, root)
    kw = {}
    if name == "F01_all_trucks_break":
        ev = json.loads((root / "runtime/events.json").read_text(encoding="utf-8"))
        _, vs = _read(root / "master/vehicles.csv")
        ev += [dict(timestamp="2026-10-01T09:00", event_type="TRUCK_BREAKDOWN", vehicle_id=v["vehicle_id"]) for v in vs]
        (root / "runtime/events.json").write_text(json.dumps(ev, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        refresh_manifest(root)
    elif name == "F02_unreachable_site":
        cut = lambda r: "S001" not in (r["from_node"], r["to_node"])
        filter_csv(root, "runtime/traffic.csv", cut)
        filter_csv(root, "master/travel_profile.csv", cut)
        refresh_manifest(root)
    elif name == "F03_missing_site_reports":
        filter_csv(root, "runtime/site_state.csv", lambda r: False)
        refresh_manifest(root)
    elif name == "F04_predictor_crash":
        kw["predictor"] = CrashingPredictor()
    elif name == "F05_model_file_missing":
        kw["model"] = "does_not_exist.joblib"
    elif name == "F06_trip_bigger_than_truck":
        f, trips = _read(root / "orders/trips.csv")
        trips[0]["volume_m3"] = "9.0"
        _write(root / "orders/trips.csv", f, trips)
        refresh_manifest(root)
    elif name == "F07_tampered_file":
        f, orders = _read(root / "orders/orders.csv")
        orders[0]["priority"] = "5" if orders[0]["priority"] != "5" else "1"
        _write(root / "orders/orders.csv", f, orders)                     # manifest NOT refreshed
    elif name == "F08_no_orders":
        for rel in ("orders/orders.csv", "orders/trips.csv", "runtime/site_state.csv",
                    "ground_truth/order_readiness.csv", "ground_truth/trip_service.csv"):
            filter_csv(root, rel, lambda r: False)
        ev = json.loads((root / "runtime/events.json").read_text(encoding="utf-8"))
        ev = [e for e in ev if "order_id" not in e]
        (root / "runtime/events.json").write_text(json.dumps(ev, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        refresh_manifest(root)
    elif name == "F09_no_trucks_on_shift":
        f, vs = _read(root / "master/vehicles.csv")
        for v in vs:
            v["available_from"] = "2026-10-01T19:00"
        _write(root / "master/vehicles.csv", f, vs)
        refresh_manifest(root)
    elif name == "F10_missing_traffic_hour":
        filter_csv(root, "runtime/traffic.csv", lambda r: r["timestamp"][11:13] != "12")
        refresh_manifest(root)
    elif name == "F11_predictor_garbage":
        kw["predictor"] = GarbagePredictor(SiteReadyPredictor("site_ready_v3.joblib"))
    return root, kw


def run_faults():
    fb = CFG["fault_base"]
    base = make_dataset(fb["scenario"], fb["seed"], HERE / "datasets")
    work = HERE / "faults"
    work.mkdir(exist_ok=True)
    rows = []
    for name, spec in CFG["faults"].items():
        row = dict(fault=name, what=spec["what"], expected="|".join(spec["expect"]))
        try:
            root, kw = build_fault(name, base, work)
            r = run_safely(root, **buf("C_ai_rolling_buffered"), **kw)
            k = r["kpi"] or {}
            row.update(status=r["status"], policy=r["policy"], messages=" | ".join(m.splitlines()[0] for m in r["messages"]),
                       preflight=(r["preflight"] or {}).get("status"), unserved_trips=k.get("unserved_trips"),
                       trips=k.get("trips"),
                       predictor_failures=r["predictor_failures"])
        except Exception as e:                                   # would be a crash of the harness itself
            row.update(status="UNCAUGHT", messages=repr(e))
        row["handled"] = row["status"] in spec["expect"] and bool(row.get("messages") or row["status"] == "OK")
        rows.append(row)
        print(name, row["status"], row["handled"], row.get("messages", "")[:120], flush=True)
    return pd.DataFrame(rows)


def main():
    _, sc = load_configs(scen_path=SCEN)
    tasks = [(s, d) for s in sc["scenarios"] for d in CFG["day_seeds"]]
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as pool:
        stress = pd.DataFrame([r for part in pool.map(stress_task, tasks, chunksize=1) for r in part])
    stress.to_csv(HERE / "stress_metrics.csv", index=False)
    faults = run_faults()
    faults.to_csv(HERE / "fault_results.csv", index=False)

    ran = stress[stress.status != "ERROR"]
    summary = ran.groupby(["scenario", "policy"])[["operational_score_min", "unserved_trips", "total_waiting_min",
                                                   "site_idle_min", "on_time_rate", "fuel_liters"]].mean().round(2)
    summary.to_csv(HERE / "stress_summary.csv")
    a = ran[ran.policy == "A_static_planned"].set_index(["scenario", "seed"])
    flagged, unserved = a.preflight == "INFEASIBLE", a.unserved_trips > 0
    gates = dict(
        G1_no_crash=bool((stress.status != "ERROR").all() and (faults.status != "UNCAUGHT").all()
                         and (faults.status != "ERROR").all()),
        G2_plans_valid=bool((ran.status == "RAN").all() and (faults.status != "INVALID_PLAN").all()),
        G3_faults_handled=bool(faults.handled.all()),
        G4_preflight_honest=bool((~flagged | unserved).all() and (~unserved | a.preflight.isin(["INFEASIBLE", "AT_RISK"])).all()))
    detail = dict(stress_runs=int(len(stress)), faults=int(len(faults)),
                  infeasible_flags=int(flagged.sum()), infeasible_flags_with_unserved=int((flagged & unserved).sum()),
                  static_days_with_unserved=int(unserved.sum()),
                  static_days_with_unserved_flagged_infeasible=int((flagged & unserved).sum()),
                  preflight_counts=a.preflight.value_counts().to_dict())
    (HERE / "gates.json").write_text(json.dumps(dict(gates=gates, detail=detail), indent=2, ensure_ascii=False))
    pd.set_option("display.width", 250)
    print(summary.to_string())
    print(json.dumps(dict(gates=gates, detail=detail), indent=2, ensure_ascii=False))
    return 0 if all(gates.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
