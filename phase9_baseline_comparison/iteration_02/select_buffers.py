"""Loop 7 iteration 02, step 1: choose B/C buffers on dev days only.

Writes dev_metrics.csv and selection.json. Evaluation days are not touched.
"""
import json
import sys
import tempfile
from itertools import product
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from readymix.ai.predictor import SiteReadyPredictor
from readymix.application.buffered_dispatch import BufferedDispatch
from readymix.application.execution_validator import validate_execution
from readymix.application.kpi import compute_kpis
from readymix.simulation.build_dataset import generate, load_configs
from readymix.simulation.executor import run_day

CFG = json.loads((HERE / "config.json").read_text())
_model = None


def score(k):
    s = CFG["score"]
    return (s["waiting"] * k["total_waiting_min"] + s["site_idle"] * k["site_idle_min"]
            + s["unserved_trip_penalty_min"] * k["unserved_trips"])


def run_task(task):
    global _model
    if _model is None:
        _model = SiteReadyPredictor(CFG["model"])
    seed, scenario = task
    common = {k: CFG[k] for k in ("refresh_min", "step_min", "waiting_weight", "late_weight")}
    grid = CFG["buffer_grid_min"]
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        root = generate(scenario, seed, Path(tmp), world_seed=CFG["world_seed"])
        for (first, nxt), (label, predictor) in product(product(grid["first"], grid["next"]),
                                                          (("B", None), ("C", _model))):
            policy = BufferedDispatch(predictor, first, nxt, **common)
            result = run_day(root, policy, CFG["step_min"])
            k = compute_kpis(result, root)
            rows.append(dict(seed=seed, scenario=scenario, policy=label, first=first, next=nxt,
                             valid=not validate_execution(result, root), predictor_failures=policy.failures,
                             operational_score_min=score(k), total_waiting_min=k["total_waiting_min"],
                             site_idle_min=k["site_idle_min"], unserved_trips=k["unserved_trips"],
                             on_time_rate=k["on_time_rate"], fuel_liters=k["fuel_liters"]))
    print(seed, scenario, "complete", flush=True)
    return rows


def select(df):
    tol = CFG["gate"]["on_time_tolerance"]
    m = df.groupby(["policy", "first", "next"])[["operational_score_min", "on_time_rate", "unserved_trips",
                                                 "total_waiting_min", "site_idle_min"]].mean().reset_index()
    m["size"] = m["first"] + m["next"]
    order = ["operational_score_min", "size", "first"]
    b = m[m.policy == "B"].sort_values(order).iloc[0]
    c_ok = m[(m.policy == "C") & (m.on_time_rate >= b.on_time_rate - tol) & (m.unserved_trips <= b.unserved_trips)]
    if c_ok.empty:
        raise SystemExit("no C buffer satisfies the dev constraints; iteration 02 stops here")
    c = c_ok.sort_values(order).iloc[0]
    pick = lambda r: dict(first_buffer_min=int(r["first"]), next_buffer_min=int(r["next"]),
                          dev_mean={k: round(float(r[k]), 4) for k in ("operational_score_min", "on_time_rate",
                                    "unserved_trips", "total_waiting_min", "site_idle_min")})
    return m, dict(B_dynamic_buffered=pick(b), C_ai_rolling_buffered=pick(c),
                   rule=CFG["selection_rule"], dev_day_seeds=CFG["dev_day_seeds"])


def main():
    _, sc = load_configs()
    tasks = [(s, n) for s in CFG["dev_day_seeds"] for n in sc["scenarios"]]
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 4) as pool:
        rows = [r for part in pool.map(run_task, tasks, chunksize=1) for r in part]
    df = pd.DataFrame(rows).sort_values(["seed", "scenario", "policy", "first", "next"])
    df.to_csv(HERE / "dev_metrics.csv", index=False)
    assert df.valid.all() and (df.predictor_failures == 0).all()
    grid, selection = select(df)
    grid.round(4).to_csv(HERE / "dev_grid_summary.csv", index=False)
    (HERE / "selection.json").write_text(json.dumps(selection, indent=2))
    print(json.dumps(selection, indent=2))


if __name__ == "__main__":
    main()
