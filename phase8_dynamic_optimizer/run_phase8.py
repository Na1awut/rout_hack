"""Run reproducible loop 5/6 scenarios with shared B/C scheduling mechanics."""
import csv
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from readymix.ai.predictor import SiteReadyPredictor
from readymix.application.dynamic_dispatch import DynamicDispatch
from readymix.application.dispatch_policies import StaticPlanned
from readymix.application.execution_validator import validate_execution
from readymix.application.kpi import compute_kpis
from readymix.simulation.build_dataset import generate, load_configs
from readymix.simulation.executor import run_day


def main():
    cfg = json.loads((HERE / "config.json").read_text())
    _, scenarios = load_configs()
    predictor = SiteReadyPredictor(cfg["model"])
    rows = []
    (HERE / "logs").mkdir(exist_ok=True)
    common = {k: cfg[k] for k in ("refresh_min", "step_min", "waiting_weight", "late_weight")}
    for scenario in scenarios["scenarios"]:
        root = generate(scenario, cfg["seed"], HERE / "datasets", world_seed=cfg["world_seed"])
        policies = [StaticPlanned(cfg["step_min"]), DynamicDispatch(**common),
                    DynamicDispatch(predictor, rolling=False, **common), DynamicDispatch(predictor, **common)]
        for policy in policies:
            result = run_day(root, policy, cfg["step_min"])
            issues = validate_execution(result, root)
            log = json.dumps(result["log"], sort_keys=True)
            (HERE / "logs" / f"{scenario}__{policy.name}.json").write_text(log)
            if hasattr(policy, "audit"):
                (HERE / "logs" / f"{scenario}__{policy.name}_decisions.json").write_text(json.dumps(policy.audit))
            row = dict(scenario=scenario, policy=policy.name, valid=not issues,
                       predictor_calls=getattr(policy, "calls", 0), predictor_failures=getattr(policy, "failures", 0),
                       log_sha256=hashlib.sha256(log.encode()).hexdigest(), **compute_kpis(result, root))
            rows.append(row)
            print(scenario, policy.name, 'valid', not issues, 'wait', row['total_waiting_min'],
                  'idle', row['site_idle_min'], 'unserved', row['unserved_trips'], flush=True)
            if issues:
                print(issues, flush=True)
    with open(HERE / "metrics.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    by = {(r["scenario"], r["policy"]): r for r in rows}
    gates = dict(execution_valid=all(r["valid"] for r in rows),
                 prediction_changes_decisions=any(by[s,"B_dynamic"]["log_sha256"] != by[s,"C_ai_snapshot"]["log_sha256"] for s in scenarios["scenarios"]),
                 rolling_changes_decisions=any(by[s,"C_ai_snapshot"]["log_sha256"] != by[s,"C_ai_rolling"]["log_sha256"] for s in scenarios["scenarios"]),
                 no_predictor_failures=all(r["predictor_failures"] == 0 for r in rows),
                 normal_orders_served=all(r["unserved_trips"] == 0 for r in rows if r["scenario"] == "S0_normal"))
    (HERE / "gates.json").write_text(json.dumps(gates, indent=2))
    print(gates, flush=True)
    return 0 if all(gates.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
