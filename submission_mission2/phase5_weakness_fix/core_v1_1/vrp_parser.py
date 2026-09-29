# vrp_parser.py
"""Parser for standard CVRPLIB .vrp instance files (Augerat et al. format).

Supports exactly the sections the qualifier benchmarks use:
    NAME, TYPE, DIMENSION, EDGE_WEIGHT_TYPE, CAPACITY,
    NODE_COORD_SECTION, DEMAND_SECTION, DEPOT_SECTION

Deliberately narrow scope (matches the qualifier's stated boundaries):
    - TYPE must be CVRP
    - EDGE_WEIGHT_TYPE must be EUC_2D
    - exactly one depot
    - all vehicles share the same capacity (as given in the file)

If a file falls outside this scope, parsing stops with a clear error
instead of guessing -- this mirrors the qualifier's own instructions
("ถ้าไฟล์ไม่ตรงกับขอบเขตนี้ ให้หยุดและแจ้งสาเหตุอย่างชัดเจน ห้ามเดาหรือแก้ข้อมูลเอง").
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional


@dataclass
class VRPInstance:
    name: str
    dimension: int
    capacity: int
    coords: Dict[int, Tuple[float, float]]   # node_id -> (x, y), includes depot
    demands: Dict[int, int]                   # node_id -> demand, includes depot (=0)
    depot_id: int
    optimal: Optional[int]                    # parsed from COMMENT if present, else None
    n_trucks_hint: Optional[int]               # parsed from COMMENT if present, else None

    @property
    def customer_ids(self) -> List[int]:
        return sorted(i for i in self.coords if i != self.depot_id)

    @property
    def total_demand(self) -> int:
        return sum(self.demands[i] for i in self.customer_ids)


class VRPFormatError(ValueError):
    pass


def parse_vrp_file(path: str) -> VRPInstance:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return parse_vrp_text(text)


def parse_vrp_text(text: str) -> VRPInstance:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    name = None
    dimension = None
    edge_weight_type = None
    vrp_type = None
    capacity = None
    optimal = None
    n_trucks_hint = None

    comment_line = next((ln for ln in lines if ln.upper().startswith("COMMENT")), "")
    m_opt = re.search(r"Optimal value:\s*(\d+)", comment_line, re.IGNORECASE)
    if m_opt:
        optimal = int(m_opt.group(1))
    m_trucks = re.search(r"No of trucks:\s*(\d+)", comment_line, re.IGNORECASE)
    if m_trucks:
        n_trucks_hint = int(m_trucks.group(1))

    section = None
    coords: Dict[int, Tuple[float, float]] = {}
    demands: Dict[int, int] = {}
    depot_ids: List[int] = []

    for ln in lines:
        upper = ln.upper()
        if upper.startswith("NAME"):
            name = ln.split(":", 1)[1].strip()
            continue
        if upper.startswith("TYPE"):
            vrp_type = ln.split(":", 1)[1].strip()
            continue
        if upper.startswith("DIMENSION"):
            dimension = int(re.search(r"\d+", ln).group())
            continue
        if upper.startswith("EDGE_WEIGHT_TYPE"):
            edge_weight_type = ln.split(":", 1)[1].strip()
            continue
        if upper.startswith("CAPACITY"):
            capacity = int(re.search(r"\d+", ln).group())
            continue
        if upper.startswith("COMMENT"):
            continue
        if upper.startswith("NODE_COORD_SECTION"):
            section = "coord"
            continue
        if upper.startswith("DEMAND_SECTION"):
            section = "demand"
            continue
        if upper.startswith("DEPOT_SECTION"):
            section = "depot"
            continue
        if upper.startswith("EOF"):
            break

        parts = ln.split()
        if section == "coord" and len(parts) >= 3:
            node_id = int(parts[0])
            coords[node_id] = (float(parts[1]), float(parts[2]))
        elif section == "demand" and len(parts) >= 2:
            node_id = int(parts[0])
            demands[node_id] = int(parts[1])
        elif section == "depot":
            val = int(parts[0])
            if val != -1:
                depot_ids.append(val)

    if vrp_type != "CVRP":
        raise VRPFormatError(f"Unsupported TYPE: {vrp_type!r} (only CVRP is supported)")
    if edge_weight_type != "EUC_2D":
        raise VRPFormatError(
            f"Unsupported EDGE_WEIGHT_TYPE: {edge_weight_type!r} (only EUC_2D is supported)")
    if len(depot_ids) != 1:
        raise VRPFormatError(f"Expected exactly one depot, found {len(depot_ids)}: {depot_ids}")
    if dimension is None or len(coords) != dimension:
        raise VRPFormatError(
            f"DIMENSION={dimension} does not match number of coordinate rows={len(coords)}")
    if set(coords.keys()) != set(demands.keys()):
        raise VRPFormatError("NODE_COORD_SECTION and DEMAND_SECTION reference different node IDs")
    if capacity is None:
        raise VRPFormatError("CAPACITY not found in file")

    return VRPInstance(
        name=name or "UNKNOWN",
        dimension=dimension,
        capacity=capacity,
        coords=coords,
        demands=demands,
        depot_id=depot_ids[0],
        optimal=optimal,
        n_trucks_hint=n_trucks_hint,
    )
