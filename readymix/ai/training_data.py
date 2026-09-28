# training_data.py -- many simulated days of one company -> train/val/test tables
"""Every day is simulated in memory from (world_seed, day_seed) and turned
into feature rows. Splits are by day, so no order, site-day or event
appears in two splits. Tables are cached as CSV under
readymix/data/training/ with a manifest of seeds and sha256.
"""

import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

from readymix.simulation.build_dataset import load_configs, simulate
from readymix.simulation.common import rng

from .features import records_from_day, service_records_from_day

READYMIX = Path(__file__).resolve().parents[1]
AI_CFG = READYMIX / "config" / "ai.yaml"
OUT = READYMIX / "data" / "training"


def load_ai_config():
    return yaml.safe_load(AI_CFG.read_text(encoding="utf-8"))


def day_scenario(day_seed, weights):
    names = list(weights)
    u = rng(day_seed, "day_scenario").random()
    acc = 0.0
    for n in names:
        acc += weights[n]
        if u < acc:
            return n
    return names[-1]


def split_days(cfg, split):
    lo, hi = cfg["splits"][split]
    return list(range(lo, hi + 1))


def build_split(cfg, split, force_scenario=None):
    sim_cfg, scen_cfg = load_configs()
    ready_rows, service_rows = [], []
    for day in split_days(cfg, split):
        name = force_scenario or day_scenario(day, cfg["scenario_weights"])
        _, tables = simulate(sim_cfg, scen_cfg, name, day, cfg["world_seed"])
        ready_rows += records_from_day(tables, day, name)
        service_rows += service_records_from_day(tables, day, name)
    return pd.DataFrame(ready_rows), pd.DataFrame(service_rows)


def load_splits(refresh=False):
    """{split: (ready_df, service_df)} for train/val/test/robust_s8, cached."""
    cfg = load_ai_config()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_p = OUT / "manifest.json"
    cfg_sha = hashlib.sha256(AI_CFG.read_bytes()).hexdigest()
    source_sha = hashlib.sha256(b"".join(p.read_bytes() for p in
        sorted((READYMIX / "simulation").glob("*.py"))) +
        Path(__file__).with_name("features.py").read_bytes()).hexdigest()
    manifest = json.loads(manifest_p.read_text(encoding="utf-8")) if manifest_p.exists() else {}
    out, files = {}, {}
    for split in cfg["splits"]:
        rp, sp = OUT / f"ready_{split}.csv", OUT / f"service_{split}.csv"
        intact = all(p.exists() and manifest.get("files", {}).get(p.name) ==
                     hashlib.sha256(p.read_bytes()).hexdigest() for p in (rp, sp))
        if (refresh or manifest.get("ai_yaml_sha256") != cfg_sha
                or manifest.get("source_sha256") != source_sha or not intact):
            r, s = build_split(cfg, split, "S8_ai_prediction_error" if split == "robust_s8" else None)
            r.to_csv(rp, index=False, lineterminator="\n")
            s.to_csv(sp, index=False, lineterminator="\n")
        out[split] = (pd.read_csv(rp), pd.read_csv(sp))
        files[rp.name] = hashlib.sha256(rp.read_bytes()).hexdigest()
        files[sp.name] = hashlib.sha256(sp.read_bytes()).hexdigest()
    manifest = {"ai_yaml_sha256": cfg_sha, "source_sha256": source_sha,
                "world_seed": cfg["world_seed"], "splits": cfg["splits"], "files": files}
    manifest_p.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return out
