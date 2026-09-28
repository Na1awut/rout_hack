# sol_parser.py
"""Reader for CVRPLIB-convention .sol reference-solution files.

Format (documented convention used by the VRPLIB/PyVRP reference reader,
https://github.com/PyVRP/VRPLIB):

    Route #1: 21 31 19 17 13 7 26
    Route #2: 12 1 16 30
    Cost 458

Notes on this format, spelled out because they are easy to get wrong:
    - The depot is NOT listed in a route line -- only customer node ids.
    - "Cost" may or may not have a trailing colon ("Cost 458" or
      "Cost: 458") depending on which tool produced the file; both are
      accepted here.
    - Any other "Key: value" or "Key value" line (e.g. "Vehicle types:")
      is captured into `extra_fields` instead of being ignored silently,
      so a caller can notice if a file carries information this parser
      isn't using.

This is a DIFFERENT format from the Li & Lim PDPTW .sol convention
("Route 1 : ..." with a header block of Instance name/Authors/Date) that
03_campus_food_delivery/.claude/skills/vrp-benchmarks parses -- that is a
pickup-and-delivery competition format, not this project's plain-CVRP one.
Do not reuse that parser here; the two are not interchangeable.

Important limitation (state this whenever these results are reported):
none of this project's 4 benchmark files shipped with a matching .sol
file when they were collected for Phase 1 -- only the optimal COST is
known, from each .vrp file's own COMMENT line. This parser is exercised
in Phase 2 via a round-trip test (write our own solver's route in this
exact format, read it back, and confirm both sides match), not against
a CVRPLIB-published .sol file. If the team obtains real .sol files later
(e.g. from CVRPLIB directly), this parser should be re-validated against
one before being trusted for a benchmark where only the route -- not
just the cost -- matters.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SolutionReference:
    routes: List[List[int]]          # customer ids only, no depot, in visit order
    cost: Optional[float]
    extra_fields: Dict[str, str] = field(default_factory=dict)

    @property
    def n_vehicles_used(self) -> int:
        return len(self.routes)


_ROUTE_RE = re.compile(r"^Route\s*#?\s*(\d+)\s*:\s*(.*)$", re.IGNORECASE)


def parse_sol_text(text: str) -> SolutionReference:
    routes_by_index: Dict[int, List[int]] = {}
    cost: Optional[float] = None
    extra: Dict[str, str] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m = _ROUTE_RE.match(line)
        if m:
            idx = int(m.group(1))
            node_ids = [int(tok) for tok in m.group(2).split()]
            routes_by_index[idx] = node_ids
            continue

        if ":" in line:
            key, _, value = line.partition(":")
        else:
            key, _, value = line.partition(" ")
        key, value = key.strip(), value.strip()

        if key.lower() == "cost":
            try:
                cost = float(value)
            except ValueError:
                extra[key] = value
        elif key:
            extra[key] = value

    routes = [routes_by_index[i] for i in sorted(routes_by_index)]
    return SolutionReference(routes=routes, cost=cost, extra_fields=extra)


def parse_sol_file(path: str) -> SolutionReference:
    with open(path, "r", encoding="utf-8") as f:
        return parse_sol_text(f.read())


def format_sol_text(routes: List[List[int]], cost: float) -> str:
    """Inverse of parse_sol_text -- used by the Phase 2 round-trip test,
    and usable later to publish our own solver's answer in the standard
    format for anyone who wants to check it with an outside tool."""
    lines = [f"Route #{i + 1}: {' '.join(str(n) for n in route)}"
             for i, route in enumerate(routes)]
    lines.append(f"Cost {cost:g}")
    return "\n".join(lines) + "\n"
