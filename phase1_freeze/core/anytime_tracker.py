# anytime_tracker.py
"""Records the convergence curve: one point every time OR-Tools finds a
strictly better solution.

Copied from 04_hackathon_qualifier/solver/anytime_tracker.py. Phase-1
change: each point now also stores `solution_index` (how many solutions
the search had found so far). Wall-clock time depends on the machine;
the solution index does not -- so the curve plotted against
solution_index is reproducible on any machine, same as the frozen stop
rule in cvrp_solver.py.
"""

import time
from dataclasses import dataclass
from typing import List, Optional
from ortools.constraint_solver import pywrapcp


@dataclass
class AnytimePoint:
    solution_index: int
    elapsed_s: float
    cost: int


class AnytimeTracker(pywrapcp.SearchMonitor):
    def __init__(self, solver, routing):
        super().__init__(solver)
        self.routing = routing
        self.points: List[AnytimePoint] = []
        self.solutions_seen = 0
        self.first_feasible_s: Optional[float] = None
        self.best_cost = float("inf")
        self._t0 = time.perf_counter()

    def AtSolution(self):
        self.solutions_seen += 1
        elapsed = time.perf_counter() - self._t0
        cost = self.routing.CostVar().Value()
        if self.first_feasible_s is None:
            self.first_feasible_s = elapsed
        if cost < self.best_cost:
            self.best_cost = cost
            self.points.append(AnytimePoint(self.solutions_seen, elapsed, int(cost)))
        return True
