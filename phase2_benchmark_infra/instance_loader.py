# instance_loader.py
"""Single entry point for turning a .vrp file (and its .sol, if any)
into the objects the rest of Phase 2 uses.

Deliberately thin: `vrp_parser.parse_vrp_file` (frozen in Phase 1) is the
only thing that reads .vrp syntax, and it is imported from
phase1_freeze/core, not copied here. Phase 2 code must never open a
.vrp file itself -- every caller goes through load_instance() so that
if the dataset grows (Phase 4's larger CVRPLIB sets), nothing outside
this one function needs to change.

Reference-cost resolution order (most to least authoritative):
    1. a same-named .sol file next to the .vrp file (sol_parser.py)
    2. the "Optimal value: N" already parsed out of the .vrp COMMENT
       line by vrp_parser (this covers all 4 of this project's current
       benchmark files -- none of them ship a .sol)
    3. none -- Gap can't be computed, and callers must handle that
       instead of guessing.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PHASE1_CORE = Path(__file__).resolve().parent.parent / "phase1_freeze" / "core"
sys.path.insert(0, str(PHASE1_CORE))

from vrp_parser import parse_vrp_file, VRPInstance  # noqa: E402
from sol_parser import parse_sol_file, SolutionReference  # noqa: E402


@dataclass
class LoadedInstance:
    instance: VRPInstance
    reference_cost: Optional[float]
    reference_source: str          # "sol_file" | "comment" | "none"
    reference_routes: Optional[list] = None   # only set when source == "sol_file"


def load_instance(vrp_path: Path) -> LoadedInstance:
    vrp_path = Path(vrp_path)
    instance = parse_vrp_file(str(vrp_path))

    sol_path = vrp_path.with_suffix(".sol")
    if sol_path.exists():
        sol_ref: SolutionReference = parse_sol_file(str(sol_path))
        if sol_ref.cost is not None:
            return LoadedInstance(instance, sol_ref.cost, "sol_file", sol_ref.routes)

    if instance.optimal is not None:
        return LoadedInstance(instance, float(instance.optimal), "comment")

    return LoadedInstance(instance, None, "none")


def discover_vrp_files(directory: Path) -> list:
    return sorted(Path(directory).glob("*.vrp"))
