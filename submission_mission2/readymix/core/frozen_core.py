# frozen_core.py -- the only door from readymix/ into CORE-CVRP v1.1
"""Read-only bridge to the frozen core in phase5_weakness_fix/core_v1_1/.

Nothing here changes the solver: it puts the frozen folder on sys.path
and re-exports what the application layer is allowed to call. Every
other readymix/ module imports the core through this file, so if the
freeze_id ever drifts, it is caught in one place.

Dependency direction (skill.md section 23):  ai -> application -> core.
This module must never import anything from ai/, application/ or
simulation/.
"""

import sys
from pathlib import Path

DEV_ROOT = Path(__file__).resolve().parents[2]          # 05_core_development/
PHASE5_DIR = DEV_ROOT / "phase5_weakness_fix"
CORE_DIR = PHASE5_DIR / "core_v1_1"
EXPECTED_FREEZE_ID = "bf63a542f2de"

for p in (CORE_DIR, PHASE5_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import freeze                                           # noqa: E402  (phase5 freeze tooling)
from vrp_parser import VRPInstance, parse_vrp_file      # noqa: E402
from cvrp_solver import CVRPSolution, Route, solve_cvrp  # noqa: E402
from validator import validate_solution                 # noqa: E402
from distance import euc_2d_rounded                     # noqa: E402

__all__ = ["DEV_ROOT", "EXPECTED_FREEZE_ID", "freeze", "VRPInstance", "parse_vrp_file",
           "CVRPSolution", "Route", "solve_cvrp", "validate_solution", "euc_2d_rounded",
           "load_frozen_config", "check_freeze"]


def load_frozen_config() -> dict:
    """The v1.1 config, after freeze.load_config() has checked the PyVRP pin."""
    return freeze.load_config()


def check_freeze() -> str:
    """Return the current freeze_id; raise if it is not the frozen one."""
    fid = freeze.freeze_id()
    if fid != EXPECTED_FREEZE_ID:
        raise RuntimeError(f"CORE-CVRP v1.1 freeze_id is {fid}, expected {EXPECTED_FREEZE_ID}. "
                           f"The frozen core, its config, a benchmark file or the PyVRP version changed.")
    return fid
