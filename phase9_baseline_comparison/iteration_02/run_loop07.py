"""Loop 7 iteration 02, step 2: paired comparison on fresh eval days.

Buffers come from selection.json (dev days only). Gates and score are the
same as iteration 01. Refuses to run if selection.json is missing.
"""
import hashlib
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from readymix.ai.predictor import SiteReadyPredictor
from readymix.application.buffered_dispatch import BufferedDispatch
from readymix.application.dynamic_dispatch import DynamicDispatch
from readymix.application.dispatch_policies import StaticPlanned
from readymix.application.execution_validator import validate_execution
from readymix.application.kpi import compute_kpis
from readymix.simulation.build_dataset import generate, load_configs
from readymix.simulation.executor import run_day

CFG = json.loads((HERE / "config.json").read_text())
SEL = json.loads((HERE / "selection.json").read_text())
_model = None


def factories(model):
    common = {k: CFG[k] for k in ("refresh_min", "step_min", "waiting_weight", "late_weight")}
    buf = lambda name: dict(first_buffer_min=SEL[name]["first_buffer_min"], next_buffer_min=SEL[name]["next_buffer_min"])
    return {"A_static_planned": lambda: StaticPlanned(CFG["step_min"]),
            "B_dynamic": lambda: DynamicDispatch(**common),
            "C_ai_rolling": lambda: DynamicDispatch(model, **common),
            "B_dynamic_buffered": lambda: BufferedDispatch(None, **buf("B_dynamic_buffered"), **common),
            "C_ai_rolling_buffered": lambda: BufferedDispatch(model, **buf("C_ai_rolling_buffered"), **common)}


def run_task(task):
    global _model
    if _model is None:
        _model = SiteReadyPredictor(CFG["model"])
    seed, scenario = task
    root = generate(scenario, seed, HERE / "datasets", world_seed=CFG["world_seed"])
    rows = []
    for name, factory in factories(_model).items():
        policy = factory()
        result = run_day(root, policy, CFG["step_min"])
        issues = validate_execution(result, root)
        k = compute_kpis(result, root)
        k["operational_score_min"] = (CFG["score"]["waiting"] * k["total_waiting_min"]
            + CFG["score"]["site_idle"] * k["site_idle_min"]
            + CFG["score"]["unserved_trip_penalty_min"] * k["unserved_trips"])
        log = json.dumps(result["log"], sort_keys=True)
        fname = f"{scenario}_{seed}_{name}.json"
        (HERE / "logs" / fname).write_text(log)
        rows.append(dict(seed=seed, scenario=scenario, policy=name, valid=not issues,
                         predictor_failures=getattr(policy, "failures", 0), log_file="logs/" + fname,
                         log_sha256=hashlib.sha256(log.encode()).hexdigest(), **k))
        if issues:
            print(seed, scenario, name, issues, flush=True)
    print(seed, scenario, "complete", flush=True)
    return rows


def main():
    (HERE / "logs").mkdir(exist_ok=True)
    provenance = [ROOT / "readymix/application/buffered_dispatch.py", ROOT / "readymix/application/dynamic_dispatch.py",
                  ROOT / "readymix/application/extended_solver.py", ROOT / "readymix/ai/models" / CFG["model"],
                  HERE / "config.json", HERE / "selection.json"]
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in provenance}
    (HERE / "evaluation_lock.json").write_text(json.dumps(hashes, indent=2))
    _, sc = load_configs()
    tasks = [(s, n) for s in CFG["eval_day_seeds"] for n in sc["scenarios"]]
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as pool:
        rows = [r for part in pool.map(run_task, tasks, chunksize=1) for r in part]
    df = pd.DataFrame(rows)
    df.to_csv(HERE / "metrics.csv", index=False)
    fields = ["total_waiting_min", "site_idle_min", "operational_score_min", "unserved_trips", "on_time_rate",
              "fuel_liters", "total_distance_km", "pour_gaps_over_30"]
    summary = df.groupby("policy")[fields].mean()
    summary.to_csv(HERE / "summary.csv")
    df.groupby(["scenario", "policy"])[fields].mean().to_csv(HERE / "scenario_summary.csv")

    b, c = CFG["gated_policies"]["B"], CFG["gated_policies"]["C"]
    panel = df.pivot(index=["seed", "scenario"], columns="policy", values="operational_score_min")
    gain = (panel[b] - panel[c]).groupby("seed").mean().to_numpy()
    rng = np.random.default_rng(CFG["gate"]["bootstrap_seed"])
    samples = rng.choice(gain, size=(CFG["gate"]["paired_day_bootstrap_resamples"], len(gain)), replace=True).mean(axis=1)
    lo, hi = np.quantile(samples, [0.025, 0.975])
    gates = dict(all_execution_valid=bool(df.valid.all()), no_predictor_failure=bool((df.predictor_failures == 0).all()),
        operational_gain_ci_positive=bool(lo > CFG["gate"]["minimum_ci95_gain_min"]),
        no_more_unserved=bool(summary.loc[c, "unserved_trips"] <= summary.loc[b, "unserved_trips"]),
        on_time_within_tolerance=bool(summary.loc[c, "on_time_rate"] >= summary.loc[b, "on_time_rate"] - CFG["gate"]["on_time_tolerance"]))
    evidence = dict(compared=f"{c} vs {b}", gates=gates, mean_gain_min=float(gain.mean()), ci95=[float(lo), float(hi)],
                    paired_day_gains=gain.tolist(), independent_day_seeds=len(gain), runs=len(df),
                    caveat="10 independent day seeds, each with 9 paired scenarios; SIMULATED data; CI is exploratory.")
    (HERE / "gates.json").write_text(json.dumps(evidence, indent=2))
    print(summary.to_string(), flush=True)
    print(json.dumps(evidence, indent=2), flush=True)
    return 0 if all(gates.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
