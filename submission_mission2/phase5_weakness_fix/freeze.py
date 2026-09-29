# freeze.py -- freeze tooling for CORE-CVRP v1.1
"""Same contract as phase1_freeze/freeze.py (v1.0), pointed at the v1.1
build:

- load_config(): refuses to run on any PyVRP version other than the one
  pinned in algorithm_config.json (the engine's search path depends on
  its version, same reasoning as the OR-Tools pin in v1.0).
- freeze_id(): hash of v1.1 config + solver code + every benchmark file
  v1.1 is evaluated on + the engine version.
- route_fingerprint(): unchanged from v1.0.
- anytime_score(): v1.0's signed primal integral, now on HGS's
  iteration axis instead of OR-Tools' solution index.

v1.0 stays frozen and untouched in phase1_freeze/; both builds can be
run side by side, which Phase 10 (baseline comparison) will need.
"""

import hashlib
import json
import os
import platform
from importlib.metadata import version
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONFIG_PATH = HERE / "algorithm_config.json"
CORE_DIR = HERE / "core_v1_1"
BENCH_DIRS = [ROOT / "phase1_freeze" / "benchmarks",
              ROOT / "phase3_sanity_test" / "instances",
              ROOT / "phase4_cvrplib_benchmark" / "benchmarks"]
REFERENCE_FILES = [ROOT / "phase1_freeze" / "reference_bks.json",
                   ROOT / "phase3_sanity_test" / "expected_results.json",
                   ROOT / "phase4_cvrplib_benchmark" / "bks_manifest.json"]


def engine_version() -> str:
    return version("pyvrp")


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    required = cfg["engine_version_required"]
    if engine_version() != required:
        raise RuntimeError(f"CORE-CVRP v1.1 requires pyvrp {required}, found {engine_version()}. "
                           f"Results from a different engine version are not frozen results.")
    return cfg


def freeze_id() -> str:
    h = hashlib.sha256()
    files = [CONFIG_PATH] + REFERENCE_FILES + sorted(CORE_DIR.glob("*.py"))
    for d in BENCH_DIRS:
        files += sorted(d.glob("*.vrp"))
    for p in files:
        h.update(p.name.encode())
        h.update(p.read_bytes())
    h.update(engine_version().encode())
    return h.hexdigest()[:12]


def route_fingerprint(routes) -> str:
    canon = sorted(tuple(r.node_ids) for r in routes)
    return hashlib.sha256(repr(canon).encode()).hexdigest()[:12]


def anytime_score(points, reference: int, horizon: int) -> float:
    """points = [(iteration, best_feasible_cost)], ascending iteration.
    gap(c) = (c - ref) / max(c, ref); 1 before the first feasible
    solution; averaged over iterations 1..horizon. 0 = optimal from the
    first iteration; lower is better; identical on any machine."""
    if not points or horizon <= 0:
        return 1.0
    total, current, j = 0.0, 1.0, 0
    for it in range(1, horizon + 1):
        while j < len(points) and points[j][0] <= it:
            c = points[j][1]
            current = (c - reference) / max(c, reference)
            j += 1
        total += current
    return total / horizon


def machine_info() -> str:
    return f"{platform.processor() or platform.machine()} | {os.cpu_count()} threads | Python {platform.python_version()}"
