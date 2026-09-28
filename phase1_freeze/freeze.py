# freeze.py
"""Phase 1 freeze tooling: everything needed to prove a result came from
this exact frozen solver.

- freeze_id():     one short hash of config + reference values + solver
                   code + benchmark files + OR-Tools version. Printed on
                   every result row, so any number on a slide can be
                   traced back to the exact frozen build that produced it.
- route_fingerprint(): hash of the ROUTE SET, not just the cost -- two
                   different route sets can share the same total distance,
                   so matching costs alone does not prove a re-run
                   reproduced the same answer.
- anytime_score(): signed primal integral over the work axis, see its
                   docstring.
"""

import hashlib
import json
import os
from pathlib import Path

import ortools

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "algorithm_config.json"
REFERENCE_PATH = HERE / "reference_bks.json"
CORE_DIR = HERE / "core"
BENCH_DIR = HERE / "benchmarks"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    required = cfg["engine_version_required"]
    if ortools.__version__ != required:
        raise RuntimeError(
            f"Frozen build requires OR-Tools {required}, found {ortools.__version__}. "
            f"Results from a different engine version are not frozen results.")
    return cfg


def load_reference() -> dict:
    with open(REFERENCE_PATH, encoding="utf-8") as f:
        return json.load(f)


def freeze_id() -> str:
    h = hashlib.sha256()
    files = [CONFIG_PATH, REFERENCE_PATH]
    files += sorted(CORE_DIR.glob("*.py"))
    files += sorted(BENCH_DIR.glob("*.vrp"))
    for p in files:
        h.update(p.name.encode())
        h.update(p.read_bytes())
    h.update(ortools.__version__.encode())
    return h.hexdigest()[:12]


def route_fingerprint(routes) -> str:
    """Order-independent across vehicles (vehicle numbering is arbitrary),
    order-dependent within a route. A route and its reverse have the same
    length but are different plans for a driver, so they fingerprint
    differently on purpose."""
    canon = sorted(tuple(r.node_ids) for r in routes)
    return hashlib.sha256(repr(canon).encode()).hexdigest()[:12]


def anytime_score(points, reference: int, solution_limit: int) -> float:
    """Signed primal integral on the work axis (solution index).

    Follows the idea of "Anytime Solver Evaluation with a Normalized
    Signed Primal Integral" (arXiv 2608.18288): a frozen reference value,
    a bounded gap, a fixed worst value before the first solution, and
    negative contributions if a run ever beats the reference. The exact
    formula below is this project's own choice, stated here so it can be
    checked:

        gap(c) = (c - ref) / max(c, ref)      in (-1, 1)
        gap    = 1 before the first solution
        score  = average of gap over solution indices 1..solution_limit

    0 = optimal from the very first solution. Lower is better. Using the
    solution index instead of seconds keeps the score identical on any
    machine, like the frozen stop rule.
    """
    if not points:
        return 1.0
    total = 0.0
    current_gap = 1.0
    it = iter(points)
    nxt = next(it, None)
    for idx in range(1, solution_limit + 1):
        while nxt is not None and nxt.solution_index <= idx:
            c = nxt.cost
            current_gap = (c - reference) / max(c, reference)
            nxt = next(it, None)
        total += current_gap
    return total / solution_limit


def machine_info() -> str:
    import platform
    return f"{platform.processor() or platform.machine()} | {os.cpu_count()} threads | Python {platform.python_version()}"
