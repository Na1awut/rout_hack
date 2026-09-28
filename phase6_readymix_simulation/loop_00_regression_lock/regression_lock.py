# regression_lock.py -- Loop 0: lock benchmark mode of CORE-CVRP v1.1
"""Snapshot once, then check against the snapshot after every change.

  python regression_lock.py --snapshot   write snapshot.json (refuses to
                                         overwrite; the lock is written once)
  python regression_lock.py              verify against snapshot.json and
                                         write metrics.csv; exit 1 on FAIL

A snapshot is only written if the run already passes every gate that does
not need a snapshot: freeze_id and PyVRP version match, the validator
passes, gap is 0.00 %, and repeated runs give identical routes.

Runtime is recorded but never gated: it depends on the machine.
"""

import csv
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
DEV_ROOT = HERE.parents[1]                       # 05_core_development/
sys.path.insert(0, str(DEV_ROOT))

from readymix.core import frozen_core as core   # noqa: E402

SNAPSHOT = HERE / "snapshot.json"
METRICS = HERE / "metrics.csv"
BENCH_DIR = DEV_ROOT / "phase1_freeze" / "benchmarks"
REFERENCE = DEV_ROOT / "phase1_freeze" / "reference_bks.json"


def run_instance(fname, meta, cfg, runs):
    inst = core.parse_vrp_file(str(BENCH_DIR / fname))
    results = []
    for i in range(1, runs + 1):
        s = core.solve_cvrp(inst, meta["max_vehicles"], cfg)
        valid = bool(s.routes) and core.validate_solution(inst, s).overall_pass
        results.append({
            "instance": inst.name, "run": i, "status": s.status,
            "cost": s.total_distance, "bks": meta["bks"],
            "gap_percent": round((s.total_distance - meta["bks"]) / meta["bks"] * 100, 6),
            "vehicles_used": s.vehicles_used, "max_vehicles": meta["max_vehicles"],
            "iterations": s.iterations, "stop_reason": s.stop_reason,
            "fingerprint": core.freeze.route_fingerprint(s.routes), "valid": valid,
            "runtime_s": round(s.runtime_s, 3),
            "routes": sorted([r.node_ids for r in s.routes]),
            "route_loads": [r.demand for r in sorted(s.routes, key=lambda r: r.node_ids)],
            "route_distances": [r.distance for r in sorted(s.routes, key=lambda r: r.node_ids)],
        })
    return results


def base_checks(results):
    """Gates that need no snapshot. Returns a list of problems."""
    problems = []
    first = results[0]
    for r in results:
        if not r["valid"]:
            problems.append(f"{r['instance']} run {r['run']}: validator FAIL")
        if r["status"] != "FEASIBLE":
            problems.append(f"{r['instance']} run {r['run']}: status {r['status']}")
        if abs(r["gap_percent"]) > 1e-9:
            problems.append(f"{r['instance']} run {r['run']}: gap {r['gap_percent']}%")
        if r["routes"] != first["routes"] or r["iterations"] != first["iterations"]:
            problems.append(f"{r['instance']} run {r['run']}: differs from run 1")
    return problems


def snapshot_checks(results, snap):
    problems = []
    for r in results:
        want = snap["instances"].get(r["instance"])
        if want is None:
            problems.append(f"{r['instance']}: not in snapshot")
            continue
        for key in ("status", "cost", "vehicles_used", "iterations", "stop_reason", "fingerprint", "routes"):
            if r[key] != want[key]:
                problems.append(f"{r['instance']} run {r['run']}: {key} changed ({want[key]!r} -> {r[key]!r})"
                                if key != "routes" else f"{r['instance']} run {r['run']}: routes changed")
    return problems


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    make_snapshot = "--snapshot" in sys.argv
    lock = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))
    cfg = core.load_frozen_config()                       # raises on a wrong PyVRP version
    fid = core.check_freeze()                             # raises on a drifted freeze_id
    engine = core.freeze.engine_version()
    machine = core.freeze.machine_info()
    ref = json.loads(REFERENCE.read_text(encoding="utf-8"))["instances"]
    print(f"Loop 0 Regression Lock  CORE-CVRP {cfg['algorithm_version']}  freeze_id={fid}  pyvrp {engine}")
    print(f"machine: {machine}\n")

    problems = []
    if engine != lock["core"]["engine_version"]:
        problems.append(f"pyvrp {engine} != locked {lock['core']['engine_version']}")
    if fid != lock["core"]["freeze_id"]:
        problems.append(f"freeze_id {fid} != locked {lock['core']['freeze_id']}")

    all_results = []
    for fname in lock["instances"]:
        res = run_instance(fname, ref[fname], cfg, lock["runs_per_instance"])
        all_results += res
        r = res[0]
        print(f"   {r['instance']:10s} cost={r['cost']} bks={r['bks']} gap={r['gap_percent']:.2f}% "
              f"vehicles={r['vehicles_used']} iters={r['iterations']} fp={r['fingerprint']} "
              f"t={'/'.join(str(x['runtime_s']) for x in res)}s")
    for fname in lock["instances"]:
        name = fname.removesuffix(".vrp")
        problems += base_checks([r for r in all_results if r["instance"] == name])

    if make_snapshot:
        if SNAPSHOT.exists():
            print(f"\nREFUSED: {SNAPSHOT.name} already exists. The lock is written once; "
                  f"delete it by hand only if the core was deliberately re-frozen.")
            return 1
        if problems:
            print("\nSNAPSHOT NOT WRITTEN -- base gates failed:")
            for p in problems:
                print(f"   - {p}")
            return 1
        snap = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "freeze_id": fid, "engine": "pyvrp", "engine_version": engine,
            "algorithm_config_sha256": sha256(core.freeze.CONFIG_PATH),
            "reference_bks_sha256": sha256(REFERENCE),
            "machine": machine,
            "instances": {r["instance"]: {k: r[k] for k in (
                "status", "cost", "bks", "vehicles_used", "max_vehicles", "iterations", "stop_reason",
                "fingerprint", "routes", "route_loads", "route_distances", "runtime_s")}
                for r in all_results if r["run"] == 1},
        }
        SNAPSHOT.write_text(json.dumps(snap, indent=2), encoding="utf-8")
        print(f"\nwrote {SNAPSHOT}")
    else:
        if not SNAPSHOT.exists():
            print("\nFAIL: no snapshot.json -- run with --snapshot first")
            return 1
        snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        if snap["algorithm_config_sha256"] != sha256(core.freeze.CONFIG_PATH):
            problems.append("algorithm_config.json changed since the snapshot")
        problems += snapshot_checks(all_results, snap)

    run_at = datetime.now().isoformat(timespec="seconds")
    cols = ["run_at", "mode", "freeze_id", "engine_version", "instance", "run", "status", "cost", "bks",
            "gap_percent", "vehicles_used", "max_vehicles", "iterations", "stop_reason", "fingerprint",
            "valid", "runtime_s", "machine"]
    with open(METRICS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in all_results:
            w.writerow({**r, "run_at": run_at, "mode": "snapshot" if make_snapshot else "verify",
                        "freeze_id": fid, "engine_version": engine, "machine": machine})
    print(f"wrote {METRICS}")

    ok = not problems
    for p in problems:
        print(f"   - {p}")
    print(f"\nLOOP 0 REGRESSION LOCK: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
