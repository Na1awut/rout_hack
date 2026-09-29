# build_dataset.py -- write one scenario x seed as a dataset folder
"""
  python -m readymix.simulation.build_dataset --scenario S0_normal --seed 42
  python -m readymix.simulation.build_dataset --scenario all

Output: readymix/data/simulation/<scenario>_seed<seed>/
    master/     plants.csv  sites.csv  vehicles.csv
    orders/     orders.csv  trips.csv
    runtime/    traffic.csv  events.json
    ground_truth/  order_readiness.csv  trip_service.csv  site_traits.csv
                   (labels -- never read at decision time)
    data_dictionary.csv   source label for every column
    manifest.json         seed, scenario, config hashes, sha256 of every file

Same scenario + seed + configs -> byte-identical files (no timestamps are
written anywhere).
"""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

import yaml

from . import data_dictionary
from .disruption_generator import generate_events
from .site_simulator import build_ground_truth
from .site_state import build_site_state
from .traffic_simulator import build_traffic, build_travel_profile
from .world import build_world

GENERATOR_VERSION = "loop03-v3"     # v2 (Loop 2): + travel_profile, causality; v3 (Loop 3): + site_state, world_seed
CAUSALITY = {
    "master/*, orders/*": "known before the day starts",
    "runtime/traffic.csv": "realized travel times: a decision at time t may read only slots starting <= t",
    "runtime/events.json": "a decision at time t may read only events with timestamp <= t",
    "runtime/site_state.csv": "a decision at time t may read only rows with timestamp <= t",
    "ground_truth/*": "labels: never read at decision time",
}
READYMIX = Path(__file__).resolve().parents[1]
SIM_CFG = READYMIX / "config" / "simulation.yaml"
SCEN_CFG = READYMIX / "config" / "scenarios.yaml"
DEFAULT_OUT = READYMIX / "data" / "simulation"


def load_configs(sim_path=SIM_CFG, scen_path=SCEN_CFG):
    sim = yaml.safe_load(Path(sim_path).read_text(encoding="utf-8"))
    scen = yaml.safe_load(Path(scen_path).read_text(encoding="utf-8"))
    return sim, scen


def scenario_params(scen_cfg, name):
    if name not in scen_cfg["scenarios"]:
        raise KeyError(f"unknown scenario {name!r}; known: {', '.join(scen_cfg['scenarios'])}")
    return {**scen_cfg["defaults"], **(scen_cfg["scenarios"][name] or {})}


def simulate(sim_cfg, scen_cfg, name, seed, world_seed=None):
    """All tables for one scenario x day seed (x world seed), in memory."""
    params = scenario_params(scen_cfg, name)
    mags = scen_cfg["magnitudes"]
    date = sim_cfg["simulation"]["date"]
    world = build_world(sim_cfg, params, seed, world_seed)
    events = generate_events(world, params, mags, seed, date)
    traffic = build_traffic(world, sim_cfg, params, mags, events, seed)
    orders_gt, trips_gt, traits = build_ground_truth(world, sim_cfg, params, mags, events, seed)
    return params, {
        "master/plants.csv": world["plants"], "master/sites.csv": world["sites"],
        "master/vehicles.csv": world["vehicles"],
        "master/travel_profile.csv": build_travel_profile(world, sim_cfg),
        "orders/orders.csv": world["orders"], "orders/trips.csv": world["trips"],
        "runtime/traffic.csv": traffic, "runtime/events.json": events,
        "runtime/site_state.csv": build_site_state(world, orders_gt, events, sim_cfg, params, seed),
        "ground_truth/order_readiness.csv": orders_gt, "ground_truth/trip_service.csv": trips_gt,
        "ground_truth/site_traits.csv": traits,
    }


def _fmt(v):
    return "true" if v is True else "false" if v is False else v


def _csv_bytes(rows, columns):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: _fmt(r[c]) for c in columns})
    return buf.getvalue().encode("utf-8")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def dataset_name(name, seed, world_seed=None):
    if world_seed is None or world_seed == seed:
        return f"{name}_seed{seed}"
    return f"{name}_world{world_seed}_day{seed}"


def generate(name, seed, out_root=DEFAULT_OUT, sim_path=SIM_CFG, scen_path=SCEN_CFG, world_seed=None) -> Path:
    sim_cfg, scen_cfg = load_configs(sim_path, scen_path)
    params, tables = simulate(sim_cfg, scen_cfg, name, seed, world_seed)
    out = Path(out_root) / dataset_name(name, seed, world_seed)
    blobs = {}
    for rel, rows in tables.items():
        if rel.endswith(".json"):
            blobs[rel] = (json.dumps(rows, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        else:
            blobs[rel] = _csv_bytes(rows, data_dictionary.COLUMNS[rel])
    blobs["data_dictionary.csv"] = _csv_bytes(data_dictionary.rows(),
                                              ["file", "field", "source_type", "unit", "meaning", "source"])
    for rel, b in blobs.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)
    manifest = {
        "generator_version": GENERATOR_VERSION, "scenario": name, "seed": seed,
        "world_seed": seed if world_seed is None else world_seed,
        "scenario_params": params,
        "simulation_yaml_sha256": sha256_bytes(Path(sim_path).read_bytes()),
        "scenarios_yaml_sha256": sha256_bytes(Path(scen_path).read_bytes()),
        "causality": CAUSALITY,
        "decision_time_files": sorted(r for r in blobs if not r.startswith("ground_truth/")),
        "label_files": sorted(r for r in blobs if r.startswith("ground_truth/")),
        "files": {rel: sha256_bytes(b) for rel, b in sorted(blobs.items())},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="S0_normal", help="scenario name or 'all'")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args()
    sim_cfg, scen_cfg = load_configs()
    seed = a.seed if a.seed is not None else sim_cfg["simulation"]["seed"]
    names = list(scen_cfg["scenarios"]) if a.scenario == "all" else [a.scenario]
    for n in names:
        print(generate(n, seed, a.out))


if __name__ == "__main__":
    main()
