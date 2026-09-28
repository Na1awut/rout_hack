"""Paired fresh-day operational comparison. No policy selection on these days."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from readymix.ai.predictor import SiteReadyPredictor
from readymix.application.dynamic_dispatch import DynamicDispatch
from readymix.application.dispatch_policies import StaticPlanned
from readymix.application.execution_validator import validate_execution
from readymix.application.kpi import compute_kpis
from readymix.simulation.build_dataset import generate, load_configs
from readymix.simulation.executor import run_day


def main():
    cfg = json.loads((HERE / "config.json").read_text())
    _, sc = load_configs()
    model = SiteReadyPredictor(cfg["model"])
    common = {k: cfg[k] for k in ("refresh_min", "step_min", "waiting_weight", "late_weight")}
    factories = {"A_static_planned": lambda: StaticPlanned(cfg["step_min"]),
                 "B_dynamic": lambda: DynamicDispatch(**common),
                 "C_ai_rolling": lambda: DynamicDispatch(model, **common)}
    rows = []
    (HERE / "logs").mkdir(exist_ok=True)
    provenance = [ROOT / "readymix/application/dynamic_dispatch.py", ROOT / "readymix/application/extended_solver.py",
                  ROOT / "readymix/ai/models" / cfg["model"], HERE / "config.json"]
    hashes = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in provenance}
    (HERE / "evaluation_lock.json").write_text(json.dumps(hashes, indent=2))
    for seed in cfg["day_seeds"]:
        for scenario in sc["scenarios"]:
            root = generate(scenario, seed, HERE / "datasets", world_seed=cfg["world_seed"])
            for name, factory in factories.items():
                policy = factory()
                result = run_day(root, policy, cfg["step_min"])
                issues = validate_execution(result, root)
                k = compute_kpis(result, root)
                k["operational_score_min"] = (cfg["score"]["waiting"] * k["total_waiting_min"]
                    + cfg["score"]["site_idle"] * k["site_idle_min"]
                    + cfg["score"]["unserved_trip_penalty_min"] * k["unserved_trips"])
                log = json.dumps(result["log"], sort_keys=True)
                fname = f"{scenario}_{seed}_{name}.json"
                (HERE / "logs" / fname).write_text(log)
                rows.append(dict(seed=seed, scenario=scenario, policy=name, valid=not issues,
                                 predictor_failures=getattr(policy, "failures", 0), log_file="logs/"+fname,
                                 log_sha256=hashlib.sha256(log.encode()).hexdigest(), **k))
                if issues:
                    print(issues, flush=True)
            print(seed, scenario, "complete", flush=True)
            pd.DataFrame(rows).to_csv(HERE / "metrics.csv", index=False)
    df = pd.DataFrame(rows)
    fields = ["total_waiting_min", "site_idle_min", "operational_score_min", "unserved_trips", "on_time_rate", "fuel_liters", "total_distance_km"]
    df.groupby("policy")[fields].mean().to_csv(HERE / "summary.csv")
    df.groupby(["scenario", "policy"])[fields].mean().to_csv(HERE / "scenario_summary.csv")
    panel = df.pivot(index=["seed", "scenario"], columns="policy", values="operational_score_min")
    gain = (panel.B_dynamic - panel.C_ai_rolling).groupby("seed").mean().to_numpy()
    rng = np.random.default_rng(cfg["gate"]["bootstrap_seed"])
    samples = rng.choice(gain, size=(cfg["gate"]["paired_day_bootstrap_resamples"], len(gain)), replace=True).mean(axis=1)
    lo, hi = np.quantile(samples, [0.025, 0.975])
    summary = df.groupby("policy")[fields].mean()
    gates = dict(all_execution_valid=bool(df.valid.all()), no_predictor_failure=bool((df.predictor_failures == 0).all()),
        operational_gain_ci_positive=bool(lo > cfg["gate"]["minimum_ci95_gain_min"]),
        no_more_unserved=bool(summary.loc["C_ai_rolling", "unserved_trips"] <= summary.loc["B_dynamic", "unserved_trips"]),
        on_time_within_tolerance=bool(summary.loc["C_ai_rolling", "on_time_rate"] >= summary.loc["B_dynamic", "on_time_rate"] - cfg["gate"]["on_time_tolerance"]))
    evidence = dict(gates=gates, mean_gain_min=float(gain.mean()), ci95=[float(lo),float(hi)],
                    paired_day_gains=gain.tolist(), independent_day_seeds=len(gain), runs=len(df),
                    caveat="Only 5 independent day seeds, each with 9 paired scenarios; CI is exploratory.")
    (HERE / "gates.json").write_text(json.dumps(evidence, indent=2))
    print(summary.to_string(), flush=True)
    print(evidence, flush=True)
    return 0 if all(gates.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
