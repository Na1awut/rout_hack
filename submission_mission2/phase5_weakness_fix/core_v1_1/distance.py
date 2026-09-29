# distance.py
"""EUC_2D distance per the CVRPLIB / TSPLIB convention.

Standard TSPLIB EUC_2D distances are integers, rounded with
nint(x) = floor(x + 0.5) rather than banker's rounding -- this matters
because Python's round() uses round-half-to-even and would silently
disagree with the published optimal costs (784 / 672 / 458 / 212) on the
half-integer cases. Using floor(x + 0.5) everywhere keeps our solver's
distance matrix bit-for-bit consistent with what CVRPLIB's own optimal
values were computed against.
"""

import math
from typing import Dict, List, Tuple


def euc_2d_rounded(p1: Tuple[float, float], p2: Tuple[float, float]) -> int:
    raw = math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)
    return int(math.floor(raw + 0.5))


def build_distance_matrix(coords: Dict[int, Tuple[float, float]],
                           node_order: List[int]) -> List[List[int]]:
    """node_order fixes the row/column index -> node_id mapping used
    everywhere else (OR-Tools manager, route reconstruction, validator)."""
    n = len(node_order)
    matrix = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                matrix[i][j] = euc_2d_rounded(coords[node_order[i]], coords[node_order[j]])
    return matrix
